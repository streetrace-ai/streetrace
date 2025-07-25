#!/bin/bash

# code-review.sh
# AI code review using StreetRace for GitHub Actions workflow

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load environment variables from .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    print_status "Loading environment variables from .env"
    set -a  # automatically export all variables
    source "$PROJECT_ROOT/.env"
    set +a  # disable automatic export
fi

# Default model - user can override with environment variable
MODEL="${STREETRACE_MODEL:-openai/gpt-4o-mini}"

# Set timeout for GitHub Actions environment (in seconds)
# LiteLLM uses this for HTTP client timeouts
export HTTPX_TIMEOUT="${HTTPX_TIMEOUT:-300}"
export REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-300}"


# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if we're in a git repo
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    
    # Check if StreetRace is available
    if ! poetry run streetrace --help > /dev/null 2>&1; then
        print_error "StreetRace not available via poetry. Run 'poetry install' first."
        exit 1
    fi
    
    # Check for API key (prioritize OpenAI)
    if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GOOGLE_AI_API_KEY:-}" ]; then
        print_error "No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY"
        print_status "You can create a .env file in the project root with: OPENAI_API_KEY=your_key_here"
        exit 1
    fi
    
    print_success "Prerequisites OK"
}

# Check for changes to review
check_for_changes() {
    print_status "Checking for changes to review..."
    
    # Check if we're in the correct branch context
    if ! git diff --quiet main...HEAD 2>/dev/null && [ $(git diff main...HEAD --name-only | wc -l) -gt 0 ]; then
        print_success "Found changes to review"
    elif ! git diff --cached --quiet; then
        print_success "Found staged changes to review"
    elif git log --oneline -1 > /dev/null 2>&1; then
        print_success "Will review recent commits"
    else
        print_error "No changes found to review"
        exit 1
    fi
}

# Run code review
run_review() {
    print_status "Running AI code review with model: $MODEL"
    print_status "This may take a moment..."
    
    cd "$PROJECT_ROOT"
    
    # Create code-reviews directory if it doesn't exist
    mkdir -p "$PROJECT_ROOT/code-reviews"
    
    # Generate timestamp for the report filename
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local report_file="code-reviews/${timestamp}.md"
    
    # Use non-interactive mode with --prompt parameter
    # Reference the github-code-review.md file and instruct to save the report
    local review_prompt="Please conduct a code review following the instructions in @templates/github-code-review.md. Analyze the git diff between the current branch and main branch to identify the changes that need review. After completing the review, save your detailed report to the file: $report_file"
    
    # Capture output to check for timeout errors
    local temp_output="/tmp/streetrace_output.txt"
    
    # Run streetrace with verbose logging to help diagnose timeout issues
    if poetry run streetrace --model="$MODEL" --verbose --prompt="$review_prompt" 2>&1 | tee "$temp_output"; then
        # Check if output contains timeout error even if exit code is 0
        if grep -q "Timed out while waiting for response" "$temp_output" || grep -q "timeout" "$temp_output"; then
            print_error "Code review timed out!"
            rm -f "$temp_output"
            return 1
        fi
        
        print_success "Code review completed!"
        if [ -f "$PROJECT_ROOT/$report_file" ]; then
            print_success "Review report saved to: $report_file"
            rm -f "$temp_output"
        else
            print_warning "Report file not found at: $report_file"
            rm -f "$temp_output"
        fi
        return 0
    else
        print_error "Code review failed!"
        rm -f "$temp_output"
        return 1
    fi
}


# Display results
display_results() {
    # Results are now displayed directly by streetrace
    # This function is kept for compatibility but simplified
    echo ""
    echo "=================================="
    print_status "Review completed successfully"
}

# Main function
main() {
    echo "🔍 AI Code Review"
    echo "=================="
    
    check_prerequisites
    check_for_changes
    run_review
    display_results
    
    print_success "Code review completed!"
}

# Help function
show_help() {
    cat << EOF
AI Code Review for GitHub Actions

Usage: $0 [OPTIONS]

This script performs automated code review using StreetRace:
1. Checks for git changes (staged, branch diff, or recent commits)
2. Runs AI analysis using StreetRace with the github-code-review.md template
3. The AI agent automatically analyzes the git diff
4. Displays and saves the review results

Environment Variables:
  OPENAI_API_KEY        - API key for OpenAI (recommended)
  ANTHROPIC_API_KEY     - API key for Anthropic Claude
  GOOGLE_AI_API_KEY     - API key for Google AI
  STREETRACE_MODEL      - Model to use (default: openai/gpt-4o-mini)

Examples:
  $0                    # Review staged changes or recent commits
  
  # With custom model:
  STREETRACE_MODEL=openai/gpt-4 $0

Options:
  -h, --help           Show this help message

Prerequisites:
- Must be run from within the StreetRace project directory
- Must be in a git repository with changes to review
- Must have poetry installed with project dependencies
- Must have an AI API key configured
EOF
}

# Parse arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac