#!/usr/bin/env python3
"""gc packman info — show pack metadata and available versions."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    find_pack_in_taps, resolve_tap,
    taps_cache_dir, git_tags, resolve_version, parse_semver,
    read_toml_simple,
)


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: gc packman info <pack>", file=sys.stderr)
        sys.exit(1)

    pack_ref = args[0]
    tap_name, pack_name = resolve_tap(pack_ref)

    result = find_pack_in_taps(pack_name, tap_name)
    if not result:
        print(f"Pack \"{pack_ref}\" not found in any registered tap.", file=sys.stderr)
        sys.exit(1)

    tap_name, tap_url, pack_path = result

    # Read pack metadata
    meta = read_toml_simple(os.path.join(pack_path, "pack.toml"))
    pack_info = meta.get("pack", {})

    print(f"  Name:        {pack_info.get('name', pack_name)}")
    print(f"  Tap:         {tap_name}")
    print(f"  Source:      {tap_url}")
    if pack_info.get("description"):
        print(f"  Description: {pack_info['description']}")
    if pack_info.get("version"):
        print(f"  Version:     {pack_info['version']}")
    if pack_info.get("requires_gc"):
        print(f"  Requires gc: {pack_info['requires_gc']}")

    # List available versions from tags
    tap_cache = os.path.join(taps_cache_dir(), tap_name)
    tags = git_tags(cwd=tap_cache)

    # Filter to this pack's tags
    versions = []
    for tag in tags:
        ver_str = None
        if tag.startswith(f"{pack_name}/v"):
            ver_str = tag[len(pack_name) + 1:]
        elif tag.startswith("v"):
            ver_str = tag
        if ver_str:
            parsed = parse_semver(ver_str)
            if parsed:
                versions.append((parsed, ver_str))

    if versions:
        versions.sort(key=lambda x: x[0], reverse=True)
        print(f"\n  Versions ({len(versions)}):")
        for _, ver in versions[:10]:
            print(f"    {ver}")
        if len(versions) > 10:
            print(f"    ... and {len(versions) - 10} more")
    else:
        print("\n  No tagged versions found.")

    # Show pack contents
    print(f"\n  Contents:")
    for subdir in ["agents", "formulas", "scripts", "commands", "doctor", "skills", "mcp"]:
        full = os.path.join(pack_path, subdir)
        if os.path.isdir(full):
            count = len([f for f in os.listdir(full) if not f.startswith(".")])
            print(f"    {subdir}/  ({count} items)")


if __name__ == "__main__":
    main()
