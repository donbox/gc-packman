#!/usr/bin/env python3
"""gc packman remove — remove a pack from imports and update lock."""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import city_root, pack_toml_path, pack_lock_path, packs_cache_dir, read_toml_simple


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: gc packman remove <pack>", file=sys.stderr)
        sys.exit(1)

    pack_name = args[0]

    # Remove from pack.toml
    toml_path = pack_toml_path()
    if os.path.exists(toml_path):
        remove_import_from_file(toml_path, pack_name)
        print(f"  Removed [imports.{pack_name}] from pack.toml")
    else:
        print(f"  No pack.toml found", file=sys.stderr)

    # Remove from pack.lock
    lock_path = pack_lock_path()
    if os.path.exists(lock_path):
        remove_pack_from_lock(lock_path, pack_name)
        print(f"  Removed {pack_name} from pack.lock")

    # Remove cached contents
    cache = os.path.join(packs_cache_dir(), pack_name)
    if os.path.isdir(cache):
        shutil.rmtree(cache)
        print(f"  Removed .gc/cache/packs/{pack_name}/")

    print(f"Removed {pack_name}.")


def remove_import_from_file(path, pack_name):
    """Remove an [imports.<name>] section from a TOML file.

    This does line-level surgery to preserve formatting and comments.
    Removes from the section header to the next section or blank line.
    """
    with open(path) as f:
        lines = f.readlines()

    section_header = f"[imports.{pack_name}]"
    output = []
    skipping = False

    for line in lines:
        stripped = line.strip()

        if stripped == section_header:
            skipping = True
            continue

        if skipping:
            # Stop skipping at next section header or double blank line
            if stripped.startswith("[") or stripped == "":
                skipping = False
                if stripped == "":
                    continue  # eat the trailing blank line
            else:
                continue  # skip key = value lines in the removed section

        output.append(line)

    with open(path, "w") as f:
        f.writelines(output)


def remove_pack_from_lock(path, pack_name):
    """Remove a pack entry from pack.lock."""
    with open(path) as f:
        lines = f.readlines()

    section_header = f"[packs.{pack_name}]"
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
