"""Shared utilities for packman commands.

Provides path resolution, config reading, and git helpers
used by all packman command scripts.
"""

import json
import os
import subprocess
import sys


# ── Paths ───────────────────────────────────────────────────────────

def city_root():
    """Return the city root from GC_CITY_PATH env var."""
    path = os.environ.get("GC_CITY_PATH", "")
    if not path:
        print("error: GC_CITY_PATH not set (are you inside a city?)", file=sys.stderr)
        sys.exit(1)
    return path


def pack_dir():
    """Return this pack's directory from GC_PACK_DIR env var."""
    return os.environ.get("GC_PACK_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def taps_file():
    """Return the path to the user-global taps registry."""
    gc_home = os.path.join(os.path.expanduser("~"), ".gc")
    os.makedirs(gc_home, exist_ok=True)
    return os.path.join(gc_home, "taps.toml")


def taps_cache_dir():
    """Return the user-global tap cache directory."""
    d = os.path.join(os.path.expanduser("~"), ".gc", "cache", "taps")
    os.makedirs(d, exist_ok=True)
    return d


def packs_cache_dir():
    """Return the city-local pack cache directory."""
    d = os.path.join(city_root(), ".gc", "cache", "packs")
    os.makedirs(d, exist_ok=True)
    return d


def pack_toml_path():
    """Return the path to the city's pack.toml."""
    return os.path.join(city_root(), "pack.toml")


def pack_lock_path():
    """Return the path to the city's pack.lock."""
    return os.path.join(city_root(), "pack.lock")


# ── Git helpers ─────────────────────────────────────────────────────

def git(*args, cwd=None, check=True):
    """Run a git command and return stdout. Strips git env vars."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")}
    result = subprocess.run(
        ["git"] + list(args),
        cwd=cwd, env=env,
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        print(f"error: git {' '.join(args)}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def git_tags(cwd=None):
    """List all tags in a repo."""
    out = git("tag", "-l", cwd=cwd)
    return [t for t in out.splitlines() if t]


def git_remote_tags(url):
    """List all tags from a remote URL without cloning."""
    out = git("ls-remote", "--tags", "--refs", url)
    tags = []
    for line in out.splitlines():
        # Format: <sha>\trefs/tags/<tagname>
        if "\t" in line:
            ref = line.split("\t", 1)[1]
            tag = ref.removeprefix("refs/tags/")
            tags.append(tag)
    return tags


def git_clone(url, dest, ref=None, depth=1):
    """Clone a repo. Optionally shallow and at a specific ref."""
    args = ["clone"]
    if ref:
        args += ["--branch", ref]
    if depth:
        args += ["--depth", str(depth)]
    args += [url, dest]
    git(*args)


def git_rev_parse(cwd, ref="HEAD"):
    """Get the commit SHA for a ref."""
    return git("rev-parse", ref, cwd=cwd)


# ── TOML helpers (stdlib-only, minimal) ─────────────────────────────

def read_toml_simple(path):
    """Read a TOML file into a dict. Handles basic cases only.

    For full TOML support with formatting preservation, this should
    be replaced with tomlkit when available. This minimal parser
    handles the subset packman needs: [section.subsection], key = "value",
    and key = true/false/integers.
    """
    if not os.path.exists(path):
        return {}

    result = {}
    current_section = result

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Section header
            if line.startswith("[") and line.endswith("]"):
                section_path = line[1:-1].strip()
                current_section = result
                for part in section_path.split("."):
                    part = part.strip()
                    if part not in current_section:
                        current_section[part] = {}
                    current_section = current_section[part]
                continue

            # Key = value
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip quotes from strings
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value == "true":
                    value = True
                elif value == "false":
                    value = False
                else:
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                current_section[key] = value

    return result


def write_toml_simple(path, data, header=None):
    """Write a dict as TOML. Handles nested sections."""
    lines = []
    if header:
        lines.append(f"# {header}")
        lines.append("")

    def write_section(d, prefix=""):
        scalars = {k: v for k, v in d.items() if not isinstance(v, dict)}
        sections = {k: v for k, v in d.items() if isinstance(v, dict)}

        for k, v in scalars.items():
            if isinstance(v, str):
                lines.append(f'{k} = "{v}"')
            elif isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            else:
                lines.append(f"{k} = {v}")

        for k, v in sections.items():
            section_key = f"{prefix}.{k}" if prefix else k
            lines.append("")
            lines.append(f"[{section_key}]")
            write_section(v, section_key)

    write_section(data)
    lines.append("")  # trailing newline

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))


# ── Tap registry ────────────────────────────────────────────────────

def load_taps():
    """Load the tap registry from ~/.gc/taps.toml."""
    data = read_toml_simple(taps_file())
    return data.get("taps", {})


def save_taps(taps):
    """Save the tap registry to ~/.gc/taps.toml."""
    write_toml_simple(taps_file(), {"taps": taps},
                      header="Tap registry — managed by gc packman")


def resolve_tap(pack_ref):
    """Resolve a pack reference to (tap_name, pack_name).

    'gastown'              → (default_tap, 'gastown')
    'gastownhall/gastown'  → ('gastownhall', 'gastown')
    """
    if "/" in pack_ref:
        tap_name, pack_name = pack_ref.split("/", 1)
        return tap_name, pack_name
    # TODO: default tap support
    # For now, search all taps for a matching pack
    return None, pack_ref


def find_pack_in_taps(pack_name, tap_name=None):
    """Find a pack across registered taps.

    Returns (tap_name, tap_url, pack_dir_in_tap) or None.
    """
    taps = load_taps()

    if tap_name and tap_name in taps:
        tap_url = taps[tap_name].get("url", "")
        cache = os.path.join(taps_cache_dir(), tap_name)
        pack_path = os.path.join(cache, pack_name)
        if os.path.isfile(os.path.join(pack_path, "pack.toml")):
            return tap_name, tap_url, pack_path
        # Single-pack tap: pack.toml at repo root
        if os.path.isfile(os.path.join(cache, "pack.toml")):
            meta = read_toml_simple(os.path.join(cache, "pack.toml"))
            if meta.get("pack", {}).get("name") == pack_name:
                return tap_name, tap_url, cache
        return None

    # Search all taps
    for tname, tdata in taps.items():
        tap_url = tdata.get("url", "")
        cache = os.path.join(taps_cache_dir(), tname)
        pack_path = os.path.join(cache, pack_name)
        if os.path.isfile(os.path.join(pack_path, "pack.toml")):
            return tname, tap_url, pack_path
        # Single-pack tap
        if os.path.isfile(os.path.join(cache, "pack.toml")):
            meta = read_toml_simple(os.path.join(cache, "pack.toml"))
            if meta.get("pack", {}).get("name") == pack_name:
                return tname, tap_url, cache

    return None


# ── Semver helpers ──────────────────────────────────────────────────

import re

_SEMVER_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)"
    r"(?:-([\w.]+))?"       # pre-release
    r"(?:\+([\w.]+))?$"     # build metadata
)


def parse_semver(s):
    """Parse a semver string into (major, minor, patch, pre, build) or None."""
    m = _SEMVER_RE.match(s)
    if not m:
        return None
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre = m.group(4) or ""
    build = m.group(5) or ""
    return (major, minor, patch, pre, build)


def semver_sort_key(version_tuple):
    """Sort key for semver tuples. Pre-release sorts before release."""
    major, minor, patch, pre, build = version_tuple
    # No pre-release → sorts after any pre-release
    pre_key = (1, "") if not pre else (0, pre)
    return (major, minor, patch, pre_key)


def matches_constraint(version_tuple, constraint):
    """Check if a semver tuple matches a constraint string.

    Supports:
      ^1.2    → >=1.2.0, <2.0.0
      ~1.2.3  → >=1.2.3, <1.3.0
      1.2.3   → exact match
      >=1.0   → greater or equal
    """
    major, minor, patch, pre, _ = version_tuple
    constraint = constraint.strip()

    # Skip pre-release versions unless constraint explicitly names one
    if pre and "-" not in constraint:
        return False

    if constraint.startswith("^"):
        target = parse_semver(constraint[1:])
        if not target:
            return False
        t_maj, t_min, t_patch, _, _ = target
        if major != t_maj:
            return False
        if major == 0:
            # ^0.x is more restrictive: minor must match
            return minor == t_min and patch >= t_patch
        return (minor, patch) >= (t_min, t_patch)

    if constraint.startswith("~"):
        target = parse_semver(constraint[1:])
        if not target:
            return False
        t_maj, t_min, t_patch, _, _ = target
        return major == t_maj and minor == t_min and patch >= t_patch

    if constraint.startswith(">="):
        target = parse_semver(constraint[2:].strip())
        if not target:
            return False
        return (major, minor, patch) >= (target[0], target[1], target[2])

    if constraint.startswith("<="):
        target = parse_semver(constraint[2:].strip())
        if not target:
            return False
        return (major, minor, patch) <= (target[0], target[1], target[2])

    # Exact match
    target = parse_semver(constraint)
    if not target:
        return False
    return (major, minor, patch) == (target[0], target[1], target[2])


def resolve_version(tags, pack_name, constraint=None):
    """Find the best matching version from a list of git tags.

    For multi-pack taps, filters tags by pack_name prefix.
    Returns (version_string, tag_string) or None.
    """
    candidates = []

    for tag in tags:
        # Multi-pack tag: gastown/v1.2.3
        if tag.startswith(f"{pack_name}/"):
            ver_str = tag[len(pack_name) + 1:]
        elif tag.startswith("v"):
            ver_str = tag
        else:
            continue

        parsed = parse_semver(ver_str)
        if not parsed:
            continue

        if constraint and not matches_constraint(parsed, constraint):
            continue

        candidates.append((parsed, ver_str, tag))

    if not candidates:
        return None

    # Sort by semver, pick highest
    candidates.sort(key=lambda x: semver_sort_key(x[0]))
    best = candidates[-1]
    return best[1], best[2]  # version_string, tag
