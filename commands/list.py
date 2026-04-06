#!/usr/bin/env python3
"""gc packman list — show imported packs with locked versions."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import city_root, pack_toml_path, pack_lock_path, packs_cache_dir, read_toml_simple


def main():
    toml_path = pack_toml_path()
    lock_path = pack_lock_path()

    config = read_toml_simple(toml_path) if os.path.exists(toml_path) else {}
    lock = read_toml_simple(lock_path) if os.path.exists(lock_path) else {}

    imports = config.get("imports", {})
    locked = lock.get("packs", {})

    if not imports and not locked:
        print("No packs imported.")
        print("  Use 'gc packman add <pack>' to add one.")
        return

    print(f"Packs in {os.path.relpath(toml_path)}:\n")

    for name in sorted(set(list(imports.keys()) + list(locked.keys()))):
        imp = imports.get(name, {})
        lck = locked.get(name, {})

        tap = imp.get("tap", lck.get("tap", ""))
        constraint = imp.get("version", "")
        locked_ver = lck.get("version", "")
        commit = lck.get("commit", "")[:12] if lck.get("commit") else ""

        # Check if cached
        cache = os.path.join(packs_cache_dir(), name)
        cached = os.path.isfile(os.path.join(cache, "pack.toml"))

        status = "\u2713" if cached else "\u2717 not cached"

        parts = [f"  {name:20s}"]
        if tap:
            parts.append(f"tap={tap}")
        if locked_ver:
            parts.append(f"v{locked_ver}")
        if constraint:
            parts.append(f"({constraint})")
        if commit:
            parts.append(f"[{commit}]")
        parts.append(status)

        print("  ".join(parts))

    in_toml = set(imports.keys())
    in_lock = set(locked.keys())
    if in_lock - in_toml:
        print(f"\n  Warning: locked but not in imports: {', '.join(in_lock - in_toml)}")
    if in_toml - in_lock:
        print(f"\n  Warning: imported but not locked: {', '.join(in_toml - in_lock)}")
        print(f"  Run 'gc packman install' to resolve.")


if __name__ == "__main__":
    main()
