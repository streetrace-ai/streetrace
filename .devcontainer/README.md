# StreetRace🚗💨 Development Container

Provides a consistent development environment with Python 3.12, Poetry, and all project dependencies pre-configured.

## Quick Start

### VS Code (Recommended)

1. Install [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open project in VS Code
3. Click "Reopen in Container" when prompted

### GitHub Codespaces

1. Go to [repository](https://github.com/krmrn42/street-race)
2. Click "Code" → "Codespaces" → "Create codespace on main"

## Features

- **Cross-platform**: Linux, macOS (Apple Silicon), Windows
- **Pre-configured**: Python 3.12, Poetry, dev tools, VS Code extensions
- **Enhanced terminal**: Persistent history, smart completion, git shortcuts
- **Live config**: Bash files mounted from host (no rebuild needed)

## Development Commands

See .devcontainer/.bash_aliases for a full list of commands.

```sh
help            # Show all commands
```

## Terminal Features

- **Persistent history**: Commands saved between restarts
- **Smart completion**: Tab completion for commands, files, git branches
- **Git shortcuts**: `gs`, `ga`, `gc`, `gp`, etc.
- **streetrace shortcuts**: `sr`, `sr-sonnet-4`, etc.
- **History search**: `Ctrl+R` for reverse search
