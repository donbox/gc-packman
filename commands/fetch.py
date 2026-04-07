#!/usr/bin/env python3
"""gc packman fetch — download a pack to the local cache without installing it."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    packs_cache_dir, load_taps, taps_cache_dir, find_pack_in_taps,
    git, git_tags, git_rev_parse, git_clone,
    resolve_version, resolve_tap, parse_semver,
)


def main():
    args = sys.argv[1:]

    constraint = None
    pack_ref = None
    i = 0
    while i < len(args):
        if args[i] in ("--version", "-v") and i + 1 < len(args):
            constraint = args[i + 1]
            i += 2
        elif args[i].startswith("--"):
            print(f"Unknown flag: {args[i]}", file=sys.stderr)
            sys.exit(1)
        else:
            pack_ref = args[i]
            i += 1

    if not pack_ref:
        print("usage: gc packman fetch <pack> [--version <constraint>]", file=sys.stderr)
        sys.exit(1)

    tap_name, pack_name = resolve_tap(pack_ref)

    print(f"Fetching {pack_ref}...")

    result = find_pack_in_taps(pack_name, tap_name)
    if not result:
        if tap_name:
            print(f"  Pack \"{pack_name}\" not found in tap \"{tap_name}\".", file=sys.stderr)
        else:
            print(f"  Pack \"{pack_name}\" not found in any registered tap.", file=sys.stderr)
        sys.exit(1)

    tap_name, tap_url, pack_path_in_tap = result
    print(f"  Tap: {tap_name}")

    tap_cache = os.path.join(taps_cache_dir(), tap_name)
    is_single_pack = os.path.isfile(os.path.join(tap_cache, "pack.toml")) and pack_path_in_tap == tap_cache

    tags = git_tags(cwd=tap_cache)
    best = resolve_version(tags, pack_name if not is_single_pack else "", constraint)

    if not best and constraint:
        print(f"  No version matching \"{constraint}\" found.", file=sys.stderr)
        sys.exit(1)

    if best:
        version_str, tag = best
        print(f"  Selected: {version_str}")
    else:
        version_str = None
        tag = None
        print("  No tagged versions found, using HEAD")

    dest = os.path.join(packs_cache_dir(), pack_name)
    if os.path.isdir(os.path.join(dest, ".git")):
        git("fetch", "origin", cwd=dest)
        git("checkout", "--force", ".", cwd=dest, check=False)
        git("clean", "-fd", cwd=dest, check=False)
        if tag:
            git("checkout", tag, cwd=dest, check=False)
    else:
        import shutil
        if os.path.exists(dest):
            shutil.rmtree(dest)
        git_clone(tap_url, dest, ref=tag, depth=1)

    # Verify the pack exists at the expected path
    pack_subdir = pack_name if not is_single_pack else ""
    pack_root = os.path.join(dest, pack_subdir) if pack_subdir else dest
    if not os.path.isfile(os.path.join(pack_root, "pack.toml")):
        print(f"  Pack directory not found at {pack_subdir}/ in cloned repo", file=sys.stderr)
        sys.exit(1)

    print(f"  Cached \u2192 .gc/cache/packs/{pack_name}/")
    print(f"  Use 'gc packman add {pack_ref}' to install into this city.")


if __name__ == "__main__":
    main()
