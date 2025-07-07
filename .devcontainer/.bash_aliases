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

# Git workflow helpers
function git-clean-branches() {
    git branch --merged | grep -v "\*\|main\|master\|develop" | xargs -n 1 git branch -d
}

function git-sync() {
    git fetch --prune
    git pull origin $(git branch --show-current)
}

# Quick git status
function gst() {
    git status --porcelain | while read status file; do
        case "$status" in
            M*) echo -e "\033[33m$status\033[0m $file";;
            A*) echo -e "\033[32m$status\033[0m $file";;
            D*) echo -e "\033[31m$status\033[0m $file";;
            ??) echo -e "\033[36m$status\033[0m $file";;
            *) echo "$status $file";;
        esac
    done
}

# Better ls with tree-like output
function ltree() {
    find ${1:-.} -print | sed -e 's;[^/]*/;|____;g;s;____|; |;g'
}

function mkcd() {
    mkdir -p "$1" && cd "$1"
}

# Poetry aliases
alias pi='poetry install'

# Development shortcuts
alias check='make check'
alias test='make test'
alias lint='make lint'

# Streetrace shortcuts
alias sr-sonnet-4='poetry run streetrace --model="anthropic/claude-sonnet-4-20250514"'
alias sr-gpt-4-1='poetry run streetrace --model="gpt-4.1"'

function help() {
    echo "Available commands:"
    echo "StreetRace commands:"
    echo "  sr-sonnet-4      - Run StreetRace with Sonnet 4 model"
    echo "  sr-gpt-4-1      - Run StreetRace with GPT-4.1 model"
    echo "Development commands:"
    echo "  check            - Run checks"
    echo "  test             - Run tests"
    echo "  lint             - Run linters"
    echo "  findfile <name>   - Find files matching <name>"
    echo "  finddir <name>    - Find directories matching <name>"
    echo "  psgrep <pattern>  - Search for processes matching <pattern>"
    echo "  streetrace        - Run the StreetRace command"
    echo "  sr                - Alias for streetrace"
    echo "  pytest            - Run tests with pytest"
    echo "  mypy              - Run type checks with mypy"
    echo "  ruff              - Run code linting with ruff"
    echo "GIT commands:"
    echo "  git-clean-branches - Clean up merged branches"
    echo "  git-sync          - Sync current branch with remote"
    echo "  gst               - Quick git status"
    echo "File commands:"
    echo "  ltree             - List files and directories in a tree-like format"
    echo "  mkcd              - Create a directory and cd into it"
    echo "Poetry commands:"
    echo "  pi                - Install dependencies"
}