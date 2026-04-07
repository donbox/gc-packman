#!/usr/bin/env python3
"""gc packman search — search for packs across registered taps and city packs."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import (
    load_taps, taps_cache_dir, city_toml_path, packs_cache_dir,
    git_tags, resolve_version, read_toml_simple,
)


def main():
    args = sys.argv[1:]
    query = args[0].lower() if args else ""

    results = []

    # ── Tap packs ───────────────────────────────────────────────────
    taps = load_taps()

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

            if not query or query in name.lower() or query in entry.lower() or query in description.lower():
                tags = git_tags(cwd=cache)
                best = resolve_version(tags, entry)
                ver_display = best[0] if best else (f"v{version}" if version else "")
                results.append((f"{tap_name}/{entry}", description, ver_display, "tap"))

        # Single-pack taps
        root_toml = os.path.join(cache, "pack.toml")
        if os.path.isfile(root_toml):
            meta = read_toml_simple(root_toml)
            pack_info = meta.get("pack", {})
            name = pack_info.get("name", "")
            description = pack_info.get("description", "")
            if name and (not query or query in name.lower() or query in description.lower()):
                version = pack_info.get("version", "")
                tags = git_tags(cwd=cache)
                best = resolve_version(tags, name)
                ver_display = best[0] if best else (f"v{version}" if version else "")
                results.append((f"{tap_name}/{name}", description, ver_display, "tap"))

    # ── Direct packs from city.toml ─────────────────────────────────
    tap_pack_names = {r[0].split("/")[-1] for r in results}

    try:
        toml_path = city_toml_path()
        config = read_toml_simple(toml_path) if os.path.exists(toml_path) else {}
        city_packs = config.get("packs", {})

        for name, src in city_packs.items():
            if name in tap_pack_names:
                continue  # already shown via tap
            if not isinstance(src, dict):
                continue
            source = src.get("source", "")
            ref = src.get("ref", "")

            # Try to read pack metadata from cache
            cache = os.path.join(packs_cache_dir(), name)
            pack_path = src.get("path", "")
            check_dir = os.path.join(cache, pack_path) if pack_path else cache
            pt = os.path.join(check_dir, "pack.toml")
            description = ""
            version = ""
            if os.path.isfile(pt):
                meta = read_toml_simple(pt)
                pack_info = meta.get("pack", {})
                description = pack_info.get("description", "")
                version = pack_info.get("version", "")

            if not query or query in name.lower() or query in description.lower() or query in source.lower():
                ver_display = f"v{version}" if version else (ref if ref else "")
                results.append((name, description, ver_display, "direct"))
    except SystemExit:
        pass  # no city context (GC_CITY_PATH not set)

    # ── Output ──────────────────────────────────────────────────────
    if not results:
        if query:
            print(f"No packs matching \"{query}\" found.")
        else:
            print("No packs found. Use 'gc packman tap add <name> <url>' to register a tap.")
        sys.exit(0)

    for ref_name, description, ver, source_type in results:
        desc = f"  {description}" if description else ""
        ver_str = f" ({ver})" if ver else ""
        label = "" if source_type == "tap" else "  [direct]"
        print(f"  {ref_name}{ver_str}{desc}{label}")


if __name__ == "__main__":
    main()
