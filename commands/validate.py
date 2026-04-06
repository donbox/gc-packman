#!/usr/bin/env python3
"""gc packman validate — check pack structure and self-containment."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from common import read_toml_simple


def main():
    args = sys.argv[1:]
    target = args[0] if args else "."

    if not os.path.isdir(target):
        print(f"Not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    pack_toml = os.path.join(target, "pack.toml")
    if not os.path.isfile(pack_toml):
        print(f"No pack.toml found in {target}", file=sys.stderr)
        sys.exit(2)

    errors = []
    warnings = []

    meta = read_toml_simple(pack_toml)
    pack_info = meta.get("pack", {})

    # Check required fields
    if not pack_info.get("name"):
        errors.append("[pack].name is required")
    if not pack_info.get("schema"):
        errors.append("[pack].schema is required")

    # Check for path escapes
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d != ".git" and d != ".gc"]
        for f in files:
            full = os.path.join(root, f)
            if f.endswith(".toml"):
                check_toml_paths(full, target, warnings)

    # Check standard directories
    has_content = False
    for subdir in ["agents", "formulas", "scripts", "commands", "doctor",
                    "skills", "mcp", "overlays", "prompts"]:
        if os.path.isdir(os.path.join(target, subdir)):
            has_content = True

    if not has_content:
        warnings.append("No standard directories found (agents/, formulas/, scripts/, etc.)")

    # Report
    name = pack_info.get("name", os.path.basename(os.path.abspath(target)))
    print(f"Validating pack \"{name}\" at {target}/\n")

    if errors:
        for e in errors:
            print(f"  \u2717 {e}")
    if warnings:
        for w in warnings:
            print(f"  \u26a0 {w}")
    if not errors and not warnings:
        print(f"  \u2713 Pack structure is valid")

    sys.exit(2 if errors else 0)


def check_toml_paths(toml_file, pack_root, warnings):
    """Check for path references that escape the pack boundary."""
    try:
        with open(toml_file) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if "=" not in line:
                    continue
                _, _, value = line.partition("=")
                value = value.strip().strip('"')
                if value.startswith("../") or value.startswith("/"):
                    rel = os.path.relpath(toml_file, pack_root)
                    warnings.append(f"{rel}:{lineno}: path escapes pack boundary: {value}")
    except (OSError, UnicodeDecodeError):
        pass


if __name__ == "__main__":
    main()
