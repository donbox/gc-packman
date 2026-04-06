#!/usr/bin/env python3
"""gc packman install — install all packs from lock file (clean install)."""

import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    city_root, packs_cache_dir, pack_lock_path,
    load_taps, taps_cache_dir,
    git, git_clone,
    read_toml_simple,
)


def content_hash(directory):
    """Compute SHA-256 hash of all files in a directory."""
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
    lock_path = pack_lock_path()
    if not os.path.exists(lock_path):
        print("No pack.lock found. Nothing to install.")
        print("  Use 'gc packman add <pack>' to add packs.")
        sys.exit(0)

    lock = read_toml_simple(lock_path)
    packs = lock.get("packs", {})

    if not packs:
        print("pack.lock is empty. Nothing to install.")
        sys.exit(0)

    taps = load_taps()
    cache_dir = packs_cache_dir()
    errors = []

    print(f"Installing from pack.lock ({len(packs)} pack(s))...\n")

    for name, info in sorted(packs.items()):
        tap_name = info.get("tap", "")
        source = info.get("source", "")
        ref = info.get("ref", "HEAD")
        expected_commit = info.get("commit", "")
        expected_hash = info.get("hash", "")
        version = info.get("version", "")

        dest = os.path.join(cache_dir, name)

        # Check if already cached and hash matches
        if os.path.isdir(dest) and expected_hash:
            actual = "sha256:" + content_hash(dest)
            if actual == expected_hash:
                print(f"  {name} v{version} \u2713 (cached, hash matches)")
                continue

        # Need to fetch — find the tap cache
        tap_cache = None
        if tap_name:
            tap_cache = os.path.join(taps_cache_dir(), tap_name)
            if not os.path.isdir(os.path.join(tap_cache, ".git")):
                # Try to clone from source
                if source:
                    print(f"  {name}: cloning tap {tap_name}...")
                    git_clone(source, tap_cache, depth=None)
                else:
                    print(f"  {name}: tap \"{tap_name}\" not cached and no source URL", file=sys.stderr)
                    errors.append(name)
                    continue
            else:
                # Update tap cache
                git("fetch", "origin", cwd=tap_cache)

        elif source:
            # No tap — use source directly
            tap_cache = os.path.join(taps_cache_dir(), f"_direct_{name}")
            if not os.path.isdir(tap_cache):
                git_clone(source, tap_cache, depth=None)
            else:
                git("fetch", "origin", cwd=tap_cache)

        if not tap_cache:
            print(f"  {name}: no tap or source URL", file=sys.stderr)
            errors.append(name)
            continue

        # Checkout the locked ref
        git("checkout", "--force", ".", cwd=tap_cache, check=False)
        if ref != "HEAD":
            git("checkout", ref, cwd=tap_cache, check=False)
        elif expected_commit:
            git("checkout", expected_commit, cwd=tap_cache, check=False)

        # Clone source repo into pack cache (matches gc pack fetch behavior)
        if os.path.isdir(os.path.join(dest, ".git")):
            git("fetch", "origin", cwd=dest)
            git("checkout", "--force", ".", cwd=dest, check=False)
            git("clean", "-fd", cwd=dest, check=False)
            if ref != "HEAD":
                git("checkout", ref, cwd=dest, check=False)
            elif expected_commit:
                git("checkout", expected_commit, cwd=dest, check=False)
        else:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            git_clone(source, dest, ref=ref if ref != "HEAD" else None, depth=1)

        # Verify hash against the pack subdirectory
        pack_root = os.path.join(dest, name)
        if not os.path.isfile(os.path.join(pack_root, "pack.toml")):
            pack_root = dest  # single-pack tap

        if expected_hash:
            actual = "sha256:" + content_hash(pack_root)
            if actual != expected_hash:
                print(f"  {name} v{version} \u2717 HASH MISMATCH", file=sys.stderr)
                print(f"    expected: {expected_hash}", file=sys.stderr)
                print(f"    actual:   {actual}", file=sys.stderr)
                errors.append(name)
                continue

        print(f"  {name} v{version} \u2713")

    if errors:
        print(f"\n{len(errors)} pack(s) failed: {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nDone.")


if __name__ == "__main__":
    main()
