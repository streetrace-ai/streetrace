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
    echo -e "\n\033[1;36m🚗💨 StreetRace Development Environment\033[0m\n"
    
    echo -e "\033[1;33m🏁 StreetRace Aliases:\033[0m"
    echo -e "  \033[32msr\033[0m                 - Run StreetRace (short alias for 'poetry run streetrace')"    
    echo -e "  \033[32msr-sonnet-4\033[0m        - Run with Claude Sonnet 4 model (alias for 'poetry run streetrace --model=\"anthropic/claude-sonnet-4-20250514\"')"
    echo -e "  \033[32msr-gpt-4-1\033[0m         - Run with GPT-4.1 model (alias for 'poetry run streetrace --model=\"gpt-4.1\"')\n"

    echo -e "\033[1;33m⚡ Development Commands:\033[0m"
    echo -e "  \033[32mcheck\033[0m              - Run all checks (make check)"
    echo -e "  \033[32mtest\033[0m               - Run tests (make test)"
    echo -e "  \033[32mlint\033[0m               - Run linters (make lint)"        
    echo -e "  \033[32mruff\033[0m               - Run code linting\n"
    
    echo -e "\033[1;33m🔍 Search & Find:\033[0m"
    echo -e "  \033[32mfindfile <name>\033[0m    - Find files matching pattern"
    echo -e "  \033[32mfinddir <name>\033[0m     - Find directories matching pattern"
    echo -e "  \033[32mpsgrep <pattern>\033[0m   - Search running processes\n"
    
    echo -e "\033[1;33m🌳 Git Commands:\033[0m"
    echo -e "  \033[32mgst\033[0m                - Colorized git status"
    echo -e "  \033[32mgit-sync\033[0m           - Sync current branch with remote"
    echo -e "  \033[32mgit-clean-branches\033[0m - Clean up merged branches\n"
    
    echo -e "\033[1;33m📁 File Operations:\033[0m"
    echo -e "  \033[32mltree\033[0m              - Tree-like directory listing"
    echo -e "  \033[32mmkcd <dir>\033[0m         - Create directory and cd into it\n"
    
    echo -e "\033[1;33m📦 Poetry Commands:\033[0m"
    echo -e "  \033[32mpi\033[0m                 - Install dependencies (poetry install)\n"
}