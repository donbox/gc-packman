#!/usr/bin/env python3
"""gc packman init — scaffold a new pack directory."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import city_root


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: gc packman init <name> [--dir <path>]", file=sys.stderr)
        sys.exit(1)

    name = args[0]
    target_dir = None

    i = 1
    while i < len(args):
        if args[i] == "--dir" and i + 1 < len(args):
            target_dir = args[i + 1]
            i += 2
        else:
            i += 1

    if not target_dir:
        target_dir = os.path.join("packs", name)

    if os.path.exists(target_dir):
        print(f"Directory {target_dir} already exists.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(target_dir)

    # Create pack.toml
    with open(os.path.join(target_dir, "pack.toml"), "w") as f:
        f.write(f"""[pack]
name = "{name}"
version = "0.1.0"
schema = 1
""")

    # Create standard directories
    for subdir in ["agents", "formulas", "scripts"]:
        os.makedirs(os.path.join(target_dir, subdir), exist_ok=True)
        # Add .gitkeep so empty dirs are tracked
        open(os.path.join(target_dir, subdir, ".gitkeep"), "w").close()

    print(f"Created pack \"{name}\" at {target_dir}/")
    print(f"  pack.toml     — pack metadata")
    print(f"  agents/       — agent definitions")
    print(f"  formulas/     — formula files")
    print(f"  scripts/      — helper scripts")


if __name__ == "__main__":
    main()
