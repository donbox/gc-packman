#!/usr/bin/env python3
"""gc packman list — show packs from city.toml with locked versions.

Pre-v2 format: reads [packs] from city.toml and pack.lock.
Output matches gc pack list format, with additional version/tap info.
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

    for name in sorted(set(list(packs.keys()) + list(locked.keys()))):
        src = packs.get(name, {})
        lck = locked.get(name, {})

        source = src.get("source", lck.get("source", "")) if isinstance(src, dict) else ""
        ref = src.get("ref", "") if isinstance(src, dict) else ""
        locked_ver = lck.get("version", "")
        tap = lck.get("tap", "")
        commit = lck.get("commit", "")[:12] if lck.get("commit") else ""

        # Check if cached
        cache = os.path.join(packs_cache_dir(), name)
        pack_path = src.get("path", "") if isinstance(src, dict) else ""
        check_dir = os.path.join(cache, pack_path) if pack_path else cache
        cached = os.path.isfile(os.path.join(check_dir, "pack.toml"))
        status = "cached" if cached else "not cached"

        # Build ref/version display
        if locked_ver:
            v = locked_ver if locked_ver.startswith("v") else f"v{locked_ver}"
            ref_display = f"ref={ref}" if ref else ""
        elif ref:
            v = ""
            ref_display = f"ref={ref}"
        else:
            v = ""
            ref_display = "ref=HEAD"

        # Format: name  source  ref=  version  tap  commit  status
        # Match gc pack list column widths
        parts = f"{'%-20s' % name} {'%-40s' % source}"
        extras = []
        if ref_display:
            extras.append(f"{'%-16s' % ref_display}")
        if v:
            extras.append(v)
        if tap:
            extras.append(f"tap={tap}")
        if commit:
            extras.append(f"commit={commit}")
        extras.append(status)

        print(f"{parts} {'  '.join(extras)}")


if __name__ == "__main__":
    main()
