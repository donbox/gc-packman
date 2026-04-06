#!/usr/bin/env python3
"""gc packman search — search for packs across registered taps."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import load_taps, taps_cache_dir, git_tags, resolve_version, read_toml_simple


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: gc packman search <query>", file=sys.stderr)
        sys.exit(1)

    query = args[0].lower()
    taps = load_taps()

    if not taps:
        print("No taps registered. Use 'gc packman tap add <name> <url>' first.")
        sys.exit(0)

    results = []

    for tap_name in sorted(taps.keys()):
        cache = os.path.join(taps_cache_dir(), tap_name)
        if not os.path.isdir(cache):
            continue

        # Scan subdirectories for packs
        try:
            entries = sorted(os.listdir(cache))
        except OSError:
            continue

        for entry in entries:
            if entry.startswith("."):
                continue
            pack_toml = os.path.join(cache, entry, "pack.toml")
            if not os.path.isfile(pack_toml):
                continue

            meta = read_toml_simple(pack_toml)
            pack_info = meta.get("pack", {})
            name = pack_info.get("name", entry)
            description = pack_info.get("description", "")
            version = pack_info.get("version", "")

            # Match against name or description
            if query in name.lower() or query in entry.lower() or query in description.lower():
                # Try to find latest version from tags
                tags = git_tags(cwd=cache)
                best = resolve_version(tags, entry)
                ver_display = f"v{best[0]}" if best else (f"v{version}" if version else "")

                results.append((tap_name, entry, description, ver_display))

        # Also check root pack.toml for single-pack taps
        root_toml = os.path.join(cache, "pack.toml")
        if os.path.isfile(root_toml):
            meta = read_toml_simple(root_toml)
            pack_info = meta.get("pack", {})
            name = pack_info.get("name", "")
            description = pack_info.get("description", "")
            if name and (query in name.lower() or query in description.lower()):
                version = pack_info.get("version", "")
                tags = git_tags(cwd=cache)
                best = resolve_version(tags, name)
                ver_display = f"v{best[0]}" if best else (f"v{version}" if version else "")
                results.append((tap_name, name, description, ver_display))

    if not results:
        print(f"No packs matching \"{query}\" found.")
        sys.exit(0)

    for tap_name, pack_name, description, ver in results:
        desc = f"  {description}" if description else ""
        ver_str = f" ({ver})" if ver else ""
        print(f"  {tap_name}/{pack_name}{ver_str}{desc}")


if __name__ == "__main__":
    main()
