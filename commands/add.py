#!/usr/bin/env python3
"""gc packman add — add a pack to imports, resolve version, fetch, lock."""

import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    city_root, packs_cache_dir, pack_toml_path, pack_lock_path,
    load_taps, taps_cache_dir, find_pack_in_taps,
    git, git_tags, git_rev_parse, git_clone,
    resolve_version, resolve_tap, parse_semver,
    read_toml_simple, write_toml_simple,
)


def content_hash(directory):
    """Compute SHA-256 hash of all files in a directory (matches Go packDirHash)."""
    paths = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, directory)
            paths.append(rel)
    paths.sort()

    h = hashlib.sha256()
    for rel in paths:
        data = open(os.path.join(directory, rel), "rb").read()
        h.update(rel.encode())
        h.update(b"\x00")
        h.update(data)
        h.update(b"\x00")
    return h.hexdigest()


def main():
    args = sys.argv[1:]

    # Parse flags
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
        print("usage: gc packman add <pack> [--version <constraint>]", file=sys.stderr)
        sys.exit(1)

    # Resolve tap and pack name
    tap_name, pack_name = resolve_tap(pack_ref)

    print(f"Resolving {pack_ref}...")

    # Find the pack in registered taps
    result = find_pack_in_taps(pack_name, tap_name)
    if not result:
        if tap_name:
            print(f"  Pack \"{pack_name}\" not found in tap \"{tap_name}\".", file=sys.stderr)
        else:
            print(f"  Pack \"{pack_name}\" not found in any registered tap.", file=sys.stderr)
            print(f"  Use 'gc packman tap list' to see registered taps.", file=sys.stderr)
        sys.exit(1)

    tap_name, tap_url, pack_path_in_tap = result
    print(f"  Tap: {tap_name}")

    # Determine if this is a multi-pack or single-pack tap
    tap_cache = os.path.join(taps_cache_dir(), tap_name)
    is_single_pack = os.path.isfile(os.path.join(tap_cache, "pack.toml")) and pack_path_in_tap == tap_cache

    # Find available versions from tags
    tags = git_tags(cwd=tap_cache)

    best = resolve_version(tags, pack_name if not is_single_pack else "", constraint)

    if not best and constraint:
        print(f"  No version matching \"{constraint}\" found.", file=sys.stderr)
        # Show what's available
        all_versions = resolve_version(tags, pack_name if not is_single_pack else "")
        if all_versions:
            print(f"  Latest available: {all_versions[0]}", file=sys.stderr)
        sys.exit(1)

    if best:
        version_str, tag = best
        print(f"  Selected: {version_str}")

        # Default constraint: ^major.minor
        if not constraint:
            parsed = parse_semver(version_str)
            if parsed:
                constraint = f"^{parsed[0]}.{parsed[1]}"
    else:
        version_str = None
        tag = None
        print("  No tagged versions found, using HEAD")
        if not constraint:
            constraint = None

    # Check out the pack at the resolved version
    dest = os.path.join(packs_cache_dir(), pack_name)
    if os.path.exists(dest):
        shutil.rmtree(dest)

    if tag:
        # For multi-pack taps, we need to checkout the tag and copy the subdirectory
        git("checkout", tag, cwd=tap_cache, check=False)

    if is_single_pack:
        # Copy entire repo (minus .git)
        shutil.copytree(tap_cache, dest, ignore=shutil.ignore_patterns(".git"))
    else:
        # Copy just the pack subdirectory
        src = os.path.join(tap_cache, pack_name)
        if os.path.isdir(src):
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
        else:
            print(f"  Pack directory not found at tag {tag}", file=sys.stderr)
            sys.exit(1)

    commit = git_rev_parse(tap_cache)
    chash = content_hash(dest)

    print(f"  Fetched \u2192 .gc/cache/packs/{pack_name}/")

    # Update pack.toml — append import
    update_pack_toml(pack_name, tap_name, constraint)
    print(f"  Added [imports.{pack_name}] to pack.toml")

    # Update pack.lock
    update_pack_lock(pack_name, tap_name, tap_url, version_str, tag, commit, chash)
    print(f"  Updated pack.lock")


def update_pack_toml(pack_name, tap_name, constraint):
    """Append an import section to the city's pack.toml."""
    path = pack_toml_path()

    # Read existing content to append
    existing = ""
    if os.path.exists(path):
        with open(path) as f:
            existing = f.read()

    # Check if import already exists
    if f"[imports.{pack_name}]" in existing:
        print(f"  Warning: [imports.{pack_name}] already exists in pack.toml, skipping")
        return

    lines = [f"\n[imports.{pack_name}]"]
    lines.append(f'tap = "{tap_name}"')
    if constraint:
        lines.append(f'version = "{constraint}"')
    lines.append("")

    with open(path, "a") as f:
        f.write("\n".join(lines))


def update_pack_lock(pack_name, tap_name, tap_url, version, tag, commit, chash):
    """Update or create pack.lock with the resolved pack."""
    path = pack_lock_path()

    # Read existing lock
    lock = read_toml_simple(path) if os.path.exists(path) else {}
    if "packs" not in lock:
        lock["packs"] = {}

    lock["packs"][pack_name] = {
        "tap": tap_name,
        "version": version or "",
        "source": tap_url,
        "ref": tag or "HEAD",
        "commit": commit,
        "hash": f"sha256:{chash}",
    }

    write_toml_simple(path, lock, header="Auto-generated by gc packman. Commit for reproducibility.")


if __name__ == "__main__":
    main()
