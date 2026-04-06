#!/usr/bin/env python3
"""gc packman add — add a pack to city.toml, resolve version, fetch, lock.

Pre-v2 format: adds [packs.<name>] source entry and appends the name
to workspace.includes in city.toml.
"""

import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    city_root, packs_cache_dir, city_toml_path, pack_lock_path,
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

    # Clone the source repo into the pack cache.
    # This matches what gc pack fetch does: .gc/cache/packs/<name>/ is a git
    # clone of the source repo. For multi-pack taps, path=<name> tells the
    # loader which subdirectory within the clone is the actual pack.
    dest = os.path.join(packs_cache_dir(), pack_name)
    if os.path.isdir(os.path.join(dest, ".git")):
        # Already cloned — fetch and checkout the right ref
        git("fetch", "origin", cwd=dest)
        git("checkout", "--force", ".", cwd=dest, check=False)
        git("clean", "-fd", cwd=dest, check=False)
        if tag:
            git("checkout", tag, cwd=dest, check=False)
    else:
        if os.path.exists(dest):
            shutil.rmtree(dest)
        git_clone(tap_url, dest, ref=tag, depth=1)

    commit = git_rev_parse(dest)

    # For multi-pack taps, the pack lives in a subdirectory
    pack_subdir = pack_name if not is_single_pack else ""
    pack_root = os.path.join(dest, pack_subdir) if pack_subdir else dest
    if not os.path.isfile(os.path.join(pack_root, "pack.toml")):
        print(f"  Pack directory not found at {pack_subdir}/ in cloned repo", file=sys.stderr)
        sys.exit(1)

    chash = content_hash(pack_root)

    print(f"  Fetched \u2192 .gc/cache/packs/{pack_name}/")

    # Update city.toml — add [packs.<name>] and workspace.includes entry
    update_city_toml(pack_name, tap_url, tag, pack_subdir)
    print(f"  Updated city.toml")

    # Update pack.lock
    update_pack_lock(pack_name, tap_name, tap_url, version_str, tag, commit, chash)
    print(f"  Updated pack.lock")


def update_city_toml(pack_name, source_url, ref, path_in_repo):
    """Add a [packs.<name>] entry and append to workspace.includes in city.toml."""
    path = city_toml_path()

    with open(path) as f:
        lines = f.readlines()

    # Check if [packs.<name>] already exists
    packs_header = f"[packs.{pack_name}]"
    for line in lines:
        if line.strip() == packs_header:
            print(f"  Warning: {packs_header} already exists in city.toml, skipping")
            return

    # Find workspace.includes line and append pack name
    includes_updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("includes") and "=" in stripped:
            # Parse the includes array and add our pack name
            # Handle both inline [...] and multi-line formats
            if f'"{pack_name}"' in stripped:
                includes_updated = True  # already there
                break
            # Simple case: includes = ["a", "b"]
            if stripped.endswith("]"):
                # Insert before the closing ]
                idx = line.rindex("]")
                # Check if array is empty
                bracket_start = line.index("[")
                content = line[bracket_start+1:idx].strip()
                if content:
                    lines[i] = line[:idx] + f', "{pack_name}"' + line[idx:]
                else:
                    lines[i] = line[:idx] + f'"{pack_name}"' + line[idx:]
                includes_updated = True
                break

    if not includes_updated:
        # No includes line found — add one after [workspace]
        for i, line in enumerate(lines):
            if line.strip() == "[workspace]":
                # Find the end of the [workspace] section
                insert_at = i + 1
                while insert_at < len(lines):
                    s = lines[insert_at].strip()
                    if s.startswith("[") and s != "[workspace]":
                        break
                    if s == "":
                        break
                    insert_at += 1
                lines.insert(insert_at, f'includes = ["{pack_name}"]\n')
                includes_updated = True
                break

    # Append [packs.<name>] section at end
    lines.append(f"\n{packs_header}\n")
    lines.append(f'source = "{source_url}"\n')
    if ref:
        lines.append(f'ref = "{ref}"\n')
    if path_in_repo:
        lines.append(f'path = "{path_in_repo}"\n')

    with open(path, "w") as f:
        f.writelines(lines)


def update_pack_lock(pack_name, tap_name, tap_url, version, tag, commit, chash):
    """Update or create pack.lock with the resolved pack."""
    path = pack_lock_path()

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
