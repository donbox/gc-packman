#!/usr/bin/env python3
"""gc packman outdated — show packs with newer versions available."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    pack_toml_path, pack_lock_path,
    load_taps, taps_cache_dir,
    git_tags, resolve_version,
    read_toml_simple,
)


def main():
    toml_path = pack_toml_path()
    lock_path = pack_lock_path()

    config = read_toml_simple(toml_path) if os.path.exists(toml_path) else {}
    lock = read_toml_simple(lock_path) if os.path.exists(lock_path) else {}

    imports = config.get("imports", {})
    locked = lock.get("packs", {})

    if not imports:
        print("No packs imported.")
        return

    found_outdated = False

    for name in sorted(imports.keys()):
        imp = imports.get(name, {})
        lck = locked.get(name, {})

        tap_name = imp.get("tap", lck.get("tap", ""))
        constraint = imp.get("version", "")
        locked_ver = lck.get("version", "")

        if not tap_name:
            continue

        tap_cache = os.path.join(taps_cache_dir(), tap_name)
        if not os.path.isdir(tap_cache):
            continue

        tags = git_tags(cwd=tap_cache)
        best = resolve_version(tags, name, constraint if constraint else None)

        if not best:
            continue

        latest_ver = best[0]
        if latest_ver != locked_ver:
            found_outdated = True
            constraint_str = f"  (constraint: {constraint})" if constraint else ""
            print(f"  {name:20s} {locked_ver} \u2192 {latest_ver}{constraint_str}")

    if not found_outdated:
        print("All packs are up to date.")


if __name__ == "__main__":
    main()
