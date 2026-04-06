#!/usr/bin/env python3
"""gc packman remove — remove a pack from city.toml and update lock.

Pre-v2 format: removes [packs.<name>] entry and the name from
workspace.includes in city.toml.
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import city_root, city_toml_path, pack_lock_path, packs_cache_dir


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: gc packman remove <pack>", file=sys.stderr)
        sys.exit(1)

    pack_name = args[0]

    # Remove from city.toml
    toml_path = city_toml_path()
    if os.path.exists(toml_path):
        remove_from_city_toml(toml_path, pack_name)
        print(f"  Removed from city.toml")
    else:
        print(f"  No city.toml found", file=sys.stderr)

    # Remove from pack.lock
    lock_path = pack_lock_path()
    if os.path.exists(lock_path):
        remove_section_from_file(lock_path, f"[packs.{pack_name}]")
        print(f"  Removed from pack.lock")

    # Remove cached contents
    cache = os.path.join(packs_cache_dir(), pack_name)
    if os.path.isdir(cache):
        shutil.rmtree(cache)
        print(f"  Removed .gc/cache/packs/{pack_name}/")

    print(f"Removed {pack_name}.")


def remove_from_city_toml(path, pack_name):
    """Remove [packs.<name>] section and name from workspace.includes."""
    with open(path) as f:
        lines = f.readlines()

    # Remove pack_name from includes line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("includes") and "=" in stripped and f'"{pack_name}"' in stripped:
            # Remove the pack name from the array
            line = line.replace(f', "{pack_name}"', '')
            line = line.replace(f'"{pack_name}", ', '')
            line = line.replace(f'"{pack_name}"', '')
            lines[i] = line
            break

    # Remove [packs.<name>] section
    section_header = f"[packs.{pack_name}]"
    output = []
    skipping = False

    for line in lines:
        stripped = line.strip()

        if stripped == section_header:
            skipping = True
            # Also eat a preceding blank line if present
            if output and output[-1].strip() == "":
                output.pop()
            continue

        if skipping:
            if stripped.startswith("[") or stripped == "":
                skipping = False
                if stripped == "":
                    continue
            else:
                continue

        output.append(line)

    with open(path, "w") as f:
        f.writelines(output)


def remove_section_from_file(path, section_header):
    """Remove a TOML section from a file."""
    with open(path) as f:
        lines = f.readlines()

    output = []
    skipping = False

    for line in lines:
        stripped = line.strip()

        if stripped == section_header:
            skipping = True
            continue

        if skipping:
            if stripped.startswith("[") or stripped == "":
                skipping = False
                if stripped == "":
                    continue
            else:
                continue

        output.append(line)

    with open(path, "w") as f:
        f.writelines(output)


if __name__ == "__main__":
    main()
