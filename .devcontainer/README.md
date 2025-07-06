# StreetRace🚗💨 Development Container

This directory contains the development container configuration for StreetRace🚗💨, providing a consistent development environment across different platforms.

## Features

- **Cross-platform support**: Works on Linux, macOS (including Apple Silicon), and Windows
- **Pre-configured environment**: Python 3.12, Poetry, and all project dependencies
- **VS Code integration**: Recommended extensions and settings for optimal development
- **Development tools**: All linting, testing, and security tools pre-installed
- **Git integration**: Full Git support with GitLens extension
- **Docker support**: Docker-outside-of-Docker for containerized development
- **Enhanced terminal**: Bash history persistence, autocompletion, and developer-friendly aliases
- **Smart shell**: Command history search, git branch display, and intelligent tab completion

## Quick Start

### Using VS Code

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the project folder in VS Code
3. When prompted, click "Reopen in Container" or use the Command Palette:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Type "Dev Containers: Reopen in Container"
   - Select the command

### Using GitHub Codespaces

1. Navigate to the [StreetRace repository](https://github.com/krmrn42/street-race)
2. Click the "Code" button and select "Codespaces"
3. Click "Create codespace on main"

### Using Docker Compose (Alternative)

```bash
# Build and start the development container
docker-compose -f .devcontainer/docker-compose.yml up -d

# Attach to the running container
docker-compose -f .devcontainer/docker-compose.yml exec streetrace-dev bash
```

## Development Workflow

Once inside the container, you can use all the standard development commands:

```bash
# Install dependencies (already done during container creation)
poetry install

# Run tests
make test

# Run linting
make lint

# Run type checking
make typed

# Run security checks
make security

# Run all checks
make check

# Run StreetRace
poetry run streetrace --help
```

## Enhanced Terminal Features

The development container includes an enhanced bash terminal with:

### Command History
- **Persistent history**: Command history is saved between container restarts
- **History search**: Use `Ctrl+R` for reverse search or Up/Down arrows to navigate
- **Extended history**: Stores 10,000 commands in memory and 20,000 in the history file
- **Timestamped entries**: Each command includes a timestamp for better tracking

### Autocompletion
- **Tab completion**: Smart completion for commands, file paths, and Git branches
- **Case-insensitive**: Completion works regardless of case
- **Poetry completion**: Tab completion for Poetry commands and package names
- **Git completion**: Tab completion for Git commands, branches, and remotes
- **Make completion**: Tab completion for Makefile targets

### Developer Aliases
- **Git shortcuts**: `gs` (status), `ga` (add), `gc` (commit), `gp` (push), etc.
- **Poetry shortcuts**: `pi` (install), `pr` (run), `ps` (shell), `pa` (add)
- **Development shortcuts**: `check`, `test`, `lint`, `format`
- **Navigation**: `..`, `...`, `....` for quick directory navigation
- **Utilities**: `mkcd`, `findfile`, `ltree`, and more

### Smart Features
- **Git branch in prompt**: Current Git branch is displayed in the terminal prompt
- **Colorized output**: Git status, ls, and grep commands use colors for better readability
- **Smart history**: Commands are saved immediately and shared across terminal sessions
- **Welcome message**: Shows useful information when opening a new terminal

### Getting Help
```bash
# Show all available commands and aliases
help

# Quick navigation
root    # Go to /workspace
src     # Go to /workspace/src
tests   # Go to /workspace/tests

# Development workflow
dev-setup   # Set up the development environment
dev-check   # Run all checks
dev-test    # Run tests
dev-clean   # Clean temporary files
```

## Environment Variables

The development container automatically sets up the following environment variables:

- `PYTHONPATH=/workspace/src` - Makes the source code importable
- `POETRY_VIRTUALENVS_IN_PROJECT=true` - Creates virtual environment in project
- `POETRY_NO_INTERACTION=1` - Prevents interactive prompts during setup

## VS Code Extensions

The development container includes these pre-installed extensions:

- **Python development**: Python, MyPy, Ruff, Black formatter
- **Git integration**: GitLens
- **File support**: TOML, YAML, Markdown, JSON
- **Development tools**: Makefile tools, Jupyter notebooks

## Container Architecture

The development container uses a multi-stage build process:

- **Base image**: Python 3.12 slim (automatic multi-architecture support)
- **Package manager**: Poetry for dependency management
- **Multi-stage build**: Optimized for caching and smaller final image
- **User setup**: Non-root user `devuser` for security
- **Volume mounting**: Source code mounted for live editing
- **Docker support**: Docker-outside-of-Docker for container operations

## Troubleshooting

### Container build fails

If the container fails to build, try:

```bash
# Rebuild the container from scratch
docker-compose -f .devcontainer/docker-compose.yml build --no-cache
```

### Poetry installation issues

If Poetry dependencies aren't installed correctly:

```bash
# Inside the container
poetry install --no-root
```

### Platform-specific issues

The container automatically detects and supports both AMD64 and ARM64 architectures. Docker will build the appropriate image for your platform automatically.