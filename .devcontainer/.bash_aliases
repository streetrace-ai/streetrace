# StreetRace Development Environment Aliases
# This file contains useful aliases and functions for the development environment

# Help function to show available commands
function help() {
    echo "🚗💨 StreetRace Development Environment - Available Commands:"
    echo ""
    echo "📦 Poetry Commands:"
    echo "  pi         - poetry install"
    echo "  pr         - poetry run"
    echo "  ps         - poetry shell"
    echo "  pa         - poetry add"
    echo "  pad        - poetry add --group dev"
    echo ""
    echo "🐍 Python Commands:"
    echo "  py         - python"
    echo "  py3        - python3"
    echo "  pip        - python -m pip"
    echo ""
    echo "🔧 Development Commands:"
    echo "  check      - make check (run all checks)"
    echo "  test       - make test (run tests)"
    echo "  lint       - make lint (run linting)"
    echo "  format     - make format (format code)"
    echo ""
    echo "🌳 Git Commands:"
    echo "  gs         - git status"
    echo "  ga         - git add"
    echo "  gc         - git commit"
    echo "  gp         - git push"
    echo "  gl         - git pull"
    echo "  gd         - git diff"
    echo "  gb         - git branch"
    echo "  gco        - git checkout"
    echo "  glog       - git log --oneline --graph --decorate"
    echo "  gst        - colorized git status"
    echo ""
    echo "📁 File System Commands:"
    echo "  ll         - ls -alF (detailed list)"
    echo "  la         - ls -A (show hidden files)"
    echo "  l          - ls -CF (compact list)"
    echo "  ..         - cd .."
    echo "  ...        - cd ../.."
    echo "  ....       - cd ../../.."
    echo "  mkcd       - mkdir and cd into directory"
    echo "  ltree      - show directory tree"
    echo ""
    echo "🔍 Search Commands:"
    echo "  grep       - grep --color=auto"
    echo "  fgrep      - fgrep --color=auto"
    echo "  egrep      - egrep --color=auto"
    echo ""
    echo "⌨️  History Features:"
    echo "  Up/Down Arrow - Navigate command history"
    echo "  Ctrl+R        - Reverse search in history"
    echo "  Tab           - Auto-complete commands and paths"
    echo ""
    echo "💡 Tips:"
    echo "  - History is preserved across container restarts"
    echo "  - Tab completion works for git, poetry, make, and file paths"
    echo "  - Use 'find_and_edit <pattern>' to quickly find and edit files"
    echo "  - Git branch is shown in the prompt"
    echo ""
}

# Additional useful functions
function findfile() {
    find . -name "*$1*" -type f 2>/dev/null
}

function finddir() {
    find . -name "*$1*" -type d 2>/dev/null
}

function psgrep() {
    ps aux | grep "$1" | grep -v grep
}

function mkbak() {
    cp "$1" "$1.bak"
}

function h() {
    history | grep "$1"
}

function ports() {
    netstat -tuln
}

function myip() {
    curl -s ipinfo.io/ip
}

function weather() {
    curl -s "wttr.in/${1:-}"
}

# Quick project navigation
function root() {
    cd /workspace
}

function src() {
    cd /workspace/src
}

function tests() {
    cd /workspace/tests
}

function docs() {
    cd /workspace/docs
}

# StreetRace specific commands
function streetrace() {
    poetry run streetrace "$@"
}

function sr() {
    poetry run streetrace "$@"
}

# Quick test runners
function pytest() {
    poetry run pytest "$@"
}

function mypy() {
    poetry run mypy "$@"
}

function ruff() {
    poetry run ruff "$@"
}

# Development workflow shortcuts
function dev-setup() {
    echo "🔧 Setting up development environment..."
    poetry install
    echo "✅ Development environment ready!"
}

function dev-check() {
    echo "🔍 Running development checks..."
    make check
}

function dev-test() {
    echo "🧪 Running tests..."
    make test
}

function dev-clean() {
    echo "🧹 Cleaning development environment..."
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    echo "✅ Development environment cleaned!"
}

# Git workflow helpers
function git-clean-branches() {
    git branch --merged | grep -v "\*\|main\|master\|develop" | xargs -n 1 git branch -d
}

function git-sync() {
    git fetch --prune
    git pull origin $(git branch --show-current)
}

function git-squash() {
    git reset --soft HEAD~${1:-2}
    git commit --edit -m"$(git log --format=%B --reverse HEAD..HEAD@{1})"
}

echo "💡 Type 'help' to see available commands and aliases"