# gc-packman

Tap-based package manager for [Gas City](https://github.com/gastownhall/gascity) packs.

Implemented as a Gas City pack — no modifications to the `gc` binary required. Include it in your city and all `gc packman` commands become available.

## Quick start

Add packman to your city's includes:

```toml
# city.toml
[workspace]
includes = ["path/to/gc-packman"]
```

Or via a git reference:

```toml
[workspace]
includes = ["https://github.com/gastownhall/gc-packman/tree/v0.1.0"]
```

Then register a tap and start adding packs:

```
gc packman tap add gastownhall https://github.com/gastownhall/packs
gc packman search gastown
gc packman add gastown
```

## Commands

| Command | Description |
|---|---|
| `gc packman tap add/remove/list/update` | Manage tap registrations |
| `gc packman add <pack>` | Add a pack to imports |
| `gc packman remove <pack>` | Remove a pack |
| `gc packman install` | Install all packs from lock file |
| `gc packman update [<pack>]` | Update to latest compatible versions |
| `gc packman list` | Show imported packs |
| `gc packman outdated` | Show available updates |
| `gc packman search <query>` | Search across taps |
| `gc packman info <pack>` | Show pack details |
| `gc packman init <name>` | Scaffold a new pack |
| `gc packman validate [<path>]` | Check pack structure |

## Requirements

- Python 3 (for command scripts)
- Git (for tap cloning and version resolution)

## Design

See [doc-packman.md](https://github.com/donbox/workproducts-gascity/blob/main/issues/doc-packman.md) for the full design document.
