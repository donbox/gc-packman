#!/usr/bin/env python3
"""gc packman tap — manage tap registrations.

Subcommands:
  gc packman tap add <name> <url>     Register a tap
  gc packman tap remove <name>        Unregister a tap
  gc packman tap list                 List registered taps
  gc packman tap update [<name>]      Fetch latest from tap repos
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    load_taps, save_taps, taps_cache_dir,
    git_clone, git,
)


def cmd_add(args):
    if len(args) < 2:
        print("usage: gc packman tap add <name> <url>", file=sys.stderr)
        sys.exit(1)

    name, url = args[0], args[1]
    taps = load_taps()

    if name in taps:
        print(f"Tap \"{name}\" already registered ({taps[name].get('url', '')})")
        print(f"Use 'gc packman tap remove {name}' first to re-register.")
        sys.exit(1)

    # Clone the tap repo to user cache
    cache = os.path.join(taps_cache_dir(), name)
    if os.path.exists(cache):
        print(f"Cache exists at {cache}, updating...", file=sys.stderr)
        git("fetch", "origin", cwd=cache)
        git("checkout", "--force", ".", cwd=cache, check=False)
        git("clean", "-fd", cwd=cache, check=False)
        git("checkout", "origin/HEAD", cwd=cache, check=False)
    else:
        print(f"Cloning {url}...", file=sys.stderr)
        git_clone(url, cache, depth=1)

    taps[name] = {"url": url}
    save_taps(taps)

    # Report what packs are in this tap
    packs = discover_packs_in_cache(cache)
    print(f"Added tap \"{name}\" \u2192 {url}")
    if packs:
        print(f"  Packs: {', '.join(packs)}")
    else:
        print("  (no packs found)")


def cmd_remove(args):
    if not args:
        print("usage: gc packman tap remove <name>", file=sys.stderr)
        sys.exit(1)

    name = args[0]
    taps = load_taps()

    if name not in taps:
        print(f"Tap \"{name}\" is not registered.", file=sys.stderr)
        sys.exit(1)

    del taps[name]
    save_taps(taps)
    print(f"Removed tap \"{name}\"")
    print(f"  (cache at ~/.gc/cache/taps/{name}/ left in place; delete manually if wanted)")


def cmd_list(args):
    taps = load_taps()
    if not taps:
        print("No taps registered.")
        print("  Use 'gc packman tap add <name> <url>' to register one.")
        return

    for name, data in sorted(taps.items()):
        url = data.get("url", "(no url)")
        cache = os.path.join(taps_cache_dir(), name)
        cached = "cached" if os.path.isdir(os.path.join(cache, ".git")) else "not cached"
        packs = discover_packs_in_cache(cache) if cached == "cached" else []
        pack_info = f"  ({len(packs)} packs)" if packs else ""
        print(f"  {name:20s} {url:40s} [{cached}]{pack_info}")


def cmd_update(args):
    taps = load_taps()
    if not taps:
        print("No taps registered.")
        return

    names = args if args else list(taps.keys())

    for name in names:
        if name not in taps:
            print(f"  {name}: not registered, skipping", file=sys.stderr)
            continue

        cache = os.path.join(taps_cache_dir(), name)
        if not os.path.isdir(os.path.join(cache, ".git")):
            url = taps[name].get("url", "")
            print(f"  {name}: cloning {url}...")
            git_clone(url, cache, depth=1)
        else:
            print(f"  {name}: updating...")
            git("fetch", "origin", cwd=cache)
            git("checkout", "--force", ".", cwd=cache, check=False)
            git("clean", "-fd", cwd=cache, check=False)
            # Try origin/HEAD, fall back to origin/main
            result = git("checkout", "origin/HEAD", cwd=cache, check=False)
            if not result and result != "":
                git("checkout", "origin/main", cwd=cache, check=False)

        packs = discover_packs_in_cache(cache)
        print(f"  {name}: {len(packs)} pack(s)")


def discover_packs_in_cache(cache_dir):
    """Find pack names in a cached tap directory."""
    packs = []
    if not os.path.isdir(cache_dir):
        return packs

    # Single-pack tap: pack.toml at root
    if os.path.isfile(os.path.join(cache_dir, "pack.toml")):
        # Could be single-pack or multi-pack with root pack
        pass

    # Multi-pack tap: subdirectories with pack.toml
    try:
        for entry in sorted(os.listdir(cache_dir)):
            full = os.path.join(cache_dir, entry)
            if os.path.isdir(full) and not entry.startswith("."):
                if os.path.isfile(os.path.join(full, "pack.toml")):
                    packs.append(entry)
    except OSError:
        pass

    # If no subdirectory packs found but root has pack.toml, it's a single-pack tap
    if not packs and os.path.isfile(os.path.join(cache_dir, "pack.toml")):
        # Use the pack name from pack.toml
        try:
            with open(os.path.join(cache_dir, "pack.toml")) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("name") and "=" in line:
                        name = line.split("=", 1)[1].strip().strip('"')
                        packs.append(name)
                        break
        except OSError:
            packs.append("(root)")

    return packs


# ── Dispatch ────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__.strip())
        sys.exit(0)

    subcmd = args[0]
    rest = args[1:]

    commands = {
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "update": cmd_update,
    }

    if subcmd in ("--help", "-h", "help"):
        print(__doc__.strip())
        sys.exit(0)

    if subcmd not in commands:
        print(f"Unknown tap subcommand: {subcmd}", file=sys.stderr)
        print(f"Available: {', '.join(commands)}", file=sys.stderr)
        sys.exit(1)

    commands[subcmd](rest)


if __name__ == "__main__":
    main()
