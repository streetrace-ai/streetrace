#!/bin/bash

# validate-config.sh
# Validates configuration and environment for GitHub Actions code review workflow
# Ensures all prerequisites are met before running AI code review

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MIN_POETRY_VERSION="1.0.0"
MIN_PYTHON_VERSION="3.8"
MIN_GIT_VERSION="2.20"

# Function to print colored output
print_status() {
    local status="$1"
    local message="$2"
    
    case "$status" in
        "SUCCESS")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}✗${NC} $message"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
    esac
}

# Function to compare versions
version_compare() {
    local version1="$1"
    local version2="$2"
    
    # Convert versions to comparable format
    local v1=$(echo "$version1" | sed 's/[^0-9.]*//g')
    local v2=$(echo "$version2" | sed 's/[^0-9.]*//g')
    
    # Use sort -V for version comparison
    if printf '%s\n%s\n' "$v1" "$v2" | sort -V -C; then
        return 0  # v1 >= v2
    else
        return 1  # v1 < v2
    fi
}

# Function to validate git repository
validate_git_repo() {
    print_status "INFO" "Validating git repository..."
    
    if ! command -v git &> /dev/null; then
        print_status "ERROR" "Git is not installed"
        return 1
    fi
    
    local git_version=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if ! version_compare "$git_version" "$MIN_GIT_VERSION"; then
        print_status "WARNING" "Git version $git_version is older than recommended $MIN_GIT_VERSION"
    else
        print_status "SUCCESS" "Git version $git_version is sufficient"
    fi
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_status "ERROR" "Not in a git repository"
        return 1
    fi
    
    print_status "SUCCESS" "Git repository validated"
    return 0
}

# Function to validate Python environment
validate_python() {
    print_status "INFO" "Validating Python environment..."
    
    if ! command -v python3 &> /dev/null; then
        print_status "ERROR" "Python 3 is not installed"
        return 1
    fi
    
    local python_version=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
    if ! version_compare "$python_version" "$MIN_PYTHON_VERSION"; then
        print_status "ERROR" "Python version $python_version is too old (minimum: $MIN_PYTHON_VERSION)"
        return 1
    fi
    
    print_status "SUCCESS" "Python version $python_version is sufficient"
    return 0
}

# Function to validate Poetry
validate_poetry() {
    print_status "INFO" "Validating Poetry..."
    
    if ! command -v poetry &> /dev/null; then
        print_status "ERROR" "Poetry is not installed"
        print_status "INFO" "Install Poetry: https://python-poetry.org/docs/#installation"
        return 1
    fi
    
    local poetry_version=$(poetry --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    if ! version_compare "$poetry_version" "$MIN_POETRY_VERSION"; then
        print_status "WARNING" "Poetry version $poetry_version is older than recommended $MIN_POETRY_VERSION"
    else
        print_status "SUCCESS" "Poetry version $poetry_version is sufficient"
    fi
    
    # Check if pyproject.toml exists
    if [ ! -f "pyproject.toml" ]; then
        print_status "ERROR" "pyproject.toml not found in current directory"
        return 1
    fi
    
    print_status "SUCCESS" "Poetry configuration validated"
    return 0
}

# Function to validate StreetRace installation
validate_streetrace() {
    print_status "INFO" "Validating StreetRace installation..."
    
    # Check if we're in poetry environment or can access streetrace
    if poetry run streetrace --version &> /dev/null; then
        local streetrace_version=$(poetry run streetrace --version 2>/dev/null || echo "unknown")
        print_status "SUCCESS" "StreetRace is installed (version: $streetrace_version)"
        return 0
    elif command -v streetrace &> /dev/null; then
        local streetrace_version=$(streetrace --version 2>/dev/null || echo "unknown")
        print_status "SUCCESS" "StreetRace is installed globally (version: $streetrace_version)"
        return 0
    else
        print_status "ERROR" "StreetRace is not installed or not accessible"
        print_status "INFO" "Run 'poetry install' to install StreetRace"
        return 1
    fi
}

# Function to validate GitHub CLI
validate_github_cli() {
    print_status "INFO" "Validating GitHub CLI..."
    
    if ! command -v gh &> /dev/null; then
        print_status "WARNING" "GitHub CLI (gh) is not installed"
        print_status "INFO" "GitHub CLI is required for posting comments. Install: https://cli.github.com/"
        return 1
    fi
    
    local gh_version=$(gh --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    print_status "SUCCESS" "GitHub CLI version $gh_version is available"
    return 0
}

# Function to validate API keys
validate_api_keys() {
    print_status "INFO" "Validating AI provider API keys..."
    
    local api_keys_found=0
    
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        print_status "SUCCESS" "Anthropic API key is configured"
        api_keys_found=$((api_keys_found + 1))
    fi
    
    if [ -n "${OPENAI_API_KEY:-}" ]; then
        print_status "SUCCESS" "OpenAI API key is configured"
        api_keys_found=$((api_keys_found + 1))
    fi
    
    if [ -n "${GOOGLE_AI_API_KEY:-}" ]; then
        print_status "SUCCESS" "Google AI API key is configured"
        api_keys_found=$((api_keys_found + 1))
    fi
    
    if [ "$api_keys_found" -eq 0 ]; then
        print_status "ERROR" "No AI provider API keys found"
        print_status "INFO" "Set at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_AI_API_KEY"
        return 1
    fi
    
    print_status "SUCCESS" "Found $api_keys_found AI provider API key(s)"
    return 0
}

# Function to validate GitHub token
validate_github_token() {
    print_status "INFO" "Validating GitHub token..."
    
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        print_status "ERROR" "GITHUB_TOKEN environment variable is not set"
        return 1
    fi
    
    # Test token validity (in GitHub Actions context)
    if [ -n "${GITHUB_REPOSITORY:-}" ]; then
        if gh auth status >/dev/null 2>&1 || echo "$GITHUB_TOKEN" | gh auth login --with-token >/dev/null 2>&1; then
            print_status "SUCCESS" "GitHub token is valid and authenticated"
        else
            print_status "ERROR" "GitHub token authentication failed"
            return 1
        fi
    else
        print_status "SUCCESS" "GitHub token is configured (validation skipped outside GitHub Actions)"
    fi
    
    return 0
}

# Function to validate required scripts
validate_scripts() {
    print_status "INFO" "Validating required scripts..."
    
    local required_scripts=(
        "scripts/github-diff-extractor.sh"
        "scripts/post-review-comment.sh"
    )
    
    local missing_scripts=()
    
    for script in "${required_scripts[@]}"; do
        if [ ! -f "$script" ]; then
            missing_scripts+=("$script")
        elif [ ! -x "$script" ]; then
            print_status "WARNING" "$script exists but is not executable"
            chmod +x "$script" 2>/dev/null || true
        fi
    done
    
    if [ ${#missing_scripts[@]} -gt 0 ]; then
        print_status "ERROR" "Missing required scripts: ${missing_scripts[*]}"
        return 1
    fi
    
    print_status "SUCCESS" "All required scripts are available"
    return 0
}

# Function to validate templates
validate_templates() {
    print_status "INFO" "Validating review templates..."
    
    local required_templates=(
        "templates/github-review-prompt.md"
    )
    
    local missing_templates=()
    
    for template in "${required_templates[@]}"; do
        if [ ! -f "$template" ]; then
            missing_templates+=("$template")
        fi
    done
    
    if [ ${#missing_templates[@]} -gt 0 ]; then
        print_status "ERROR" "Missing required templates: ${missing_templates[*]}"
        return 1
    fi
    
    print_status "SUCCESS" "All required templates are available"
    return 0
}

# Function to validate GitHub Actions environment
validate_github_actions_env() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        print_status "INFO" "Running in GitHub Actions environment"
        
        local required_github_vars=(
            "GITHUB_REPOSITORY"
            "GITHUB_SHA"
        )
        
        local missing_vars=()
        
        for var in "${required_github_vars[@]}"; do
            if [ -z "${!var:-}" ]; then
                missing_vars+=("$var")
            fi
        done
        
        if [ ${#missing_vars[@]} -gt 0 ]; then
            print_status "ERROR" "Missing GitHub Actions variables: ${missing_vars[*]}"
            return 1
        fi
        
        print_status "SUCCESS" "GitHub Actions environment validated"
    else
        print_status "INFO" "Not running in GitHub Actions (local environment)"
    fi
    
    return 0
}

# Main validation function
main() {
    echo "🔍 StreetRace GitHub Actions Code Review - Configuration Validation"
    echo "=================================================================="
    echo ""
    
    local validation_errors=0
    
    # Run all validations
    validate_git_repo || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_python || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_poetry || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_streetrace || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_github_cli || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_api_keys || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_github_token || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_scripts || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_templates || validation_errors=$((validation_errors + 1))
    echo ""
    
    validate_github_actions_env || validation_errors=$((validation_errors + 1))
    echo ""
    
    # Summary
    echo "=================================================================="
    if [ "$validation_errors" -eq 0 ]; then
        print_status "SUCCESS" "All validations passed! Ready for AI code review."
        exit 0
    else
        print_status "ERROR" "Validation failed with $validation_errors error(s). Please fix the issues above."
        exit 1
    fi
}

# Execute main function
main "$@"