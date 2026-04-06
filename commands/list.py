#!/usr/bin/env python3
"""gc packman list — show packs from city.toml with locked versions.

Pre-v2 format: reads [packs] from city.toml and pack.lock.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import city_root, city_toml_path, pack_lock_path, packs_cache_dir, read_toml_simple


def main():
    toml_path = city_toml_path()
    lock_path = pack_lock_path()

    config = read_toml_simple(toml_path) if os.path.exists(toml_path) else {}
    lock = read_toml_simple(lock_path) if os.path.exists(lock_path) else {}

    packs = config.get("packs", {})
    locked = lock.get("packs", {})

    if not packs and not locked:
        print("No packs configured.")
        print("  Use 'gc packman add <pack>' to add one.")
        return

    print(f"Packs in {os.path.relpath(toml_path)}:\n")

    for name in sorted(set(list(packs.keys()) + list(locked.keys()))):
        src = packs.get(name, {})
        lck = locked.get(name, {})

        tap = lck.get("tap", "")
        source = src.get("source", lck.get("source", "")) if isinstance(src, dict) else ""
        ref = src.get("ref", "") if isinstance(src, dict) else ""
        locked_ver = lck.get("version", "")
        commit = lck.get("commit", "")[:12] if lck.get("commit") else ""

        # Check if cached — pack.toml may be at root (single-pack) or in
        # a subdirectory matching the pack name (multi-pack tap with path=)
        cache = os.path.join(packs_cache_dir(), name)
        pack_path = src.get("path", "") if isinstance(src, dict) else ""
        check_dir = os.path.join(cache, pack_path) if pack_path else cache
        cached = os.path.isfile(os.path.join(check_dir, "pack.toml"))

        status = "\u2713" if cached else "\u2717 not cached"

        parts = [f"  {name:20s}"]
        if tap:
            parts.append(f"tap={tap}")
        if locked_ver:
            v = locked_ver if locked_ver.startswith("v") else f"v{locked_ver}"
            parts.append(v)
        elif ref:
            parts.append(f"ref={ref}")
        if commit:
            parts.append(f"[{commit}]")
        parts.append(status)

        print("  ".join(parts))


if __name__ == "__main__":
    main()
