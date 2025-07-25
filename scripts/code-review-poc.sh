#!/bin/bash

# code-review-poc.sh
# Simple proof-of-concept for AI code review using StreetRace
# No Docker needed - just run locally!

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
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMP_DIR="/tmp/streetrace-review-$(date +%s)"
DIFF_FILE="$TEMP_DIR/changes.diff"
PROMPT_FILE="$TEMP_DIR/review-prompt.md"
OUTPUT_FILE="$TEMP_DIR/review-output.md"

# Load environment variables from .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    print_status "Loading environment variables from .env"
    set -a  # automatically export all variables
    source "$PROJECT_ROOT/.env"
    set +a  # disable automatic export
fi

# Default model - user can override with environment variable
MODEL="${STREETRACE_MODEL:-openai/gpt-4o-mini}"

# Cleanup function
cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

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
    if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GOOGLE_API_KEY:-}" ]; then
        print_error "No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY"
        print_status "You can create a .env file in the project root with: OPENAI_API_KEY=your_key_here"
        exit 1
    fi
    
    mkdir -p "$TEMP_DIR"
    print_success "Prerequisites OK"
}

# Extract git diff
extract_changes() {
    print_status "Extracting changes for review..."
    
    # Try staged changes first
    if ! git diff --cached --quiet; then
        print_status "Found staged changes"
        "$PROJECT_ROOT/scripts/extract-diff.sh" --staged --filter "*.py,*.js,*.ts,*.go,*.java,*.rs,*.cpp,*.c,*.h,*.sh,*.md,Dockerfile" > "$DIFF_FILE"
    # Then try changes since main
    elif ! git diff --quiet main...HEAD; then
        print_status "Found changes since main branch"
        "$PROJECT_ROOT/scripts/extract-diff.sh" -b main -t HEAD --filter "*.py,*.js,*.ts,*.go,*.java,*.rs,*.cpp,*.c,*.h,*.sh,*.md,Dockerfile" > "$DIFF_FILE"
    # Finally try last commit
    elif git log --oneline -1 > /dev/null 2>&1; then
        print_status "No uncommitted changes, reviewing last commit"
        "$PROJECT_ROOT/scripts/extract-diff.sh" -b HEAD~1 -t HEAD --filter "*.py,*.js,*.ts,*.go,*.java,*.rs,*.cpp,*.c,*.h,*.sh,*.md,Dockerfile" > "$DIFF_FILE"
    else
        print_error "No changes found to review"
        exit 1
    fi
    
    if [ ! -s "$DIFF_FILE" ]; then
        print_error "No code changes found in diff"
        exit 1
    fi
    
    local diff_size=$(wc -c < "$DIFF_FILE")
    print_success "Extracted diff: $diff_size bytes"
}

# Create review prompt
create_prompt() {
    print_status "Creating review prompt..."
    
    local template_file="$PROJECT_ROOT/templates/code-review-prompt.md"
    
    if [ ! -f "$template_file" ]; then
        print_error "Template file not found: $template_file"
        exit 1
    fi
    
    # Use Python to safely replace the placeholder with the diff content
    python3 -c "
import sys
with open('$template_file', 'r') as f:
    template = f.read()
with open('$DIFF_FILE', 'r') as f:
    diff_content = f.read()
result = template.replace('{DIFF_CONTENT}', diff_content)
with open('$PROMPT_FILE', 'w') as f:
    f.write(result)
"
    
    print_success "Created review prompt"
}

# Run code review
run_review() {
    print_status "Running AI code review with model: $MODEL"
    print_status "This may take a moment..."
    
    cd "$PROJECT_ROOT"
    
    if poetry run streetrace --model="$MODEL" --prompt="$(cat "$PROMPT_FILE")" > "$OUTPUT_FILE" 2>&1; then
        print_success "Code review completed!"
    else
        print_error "Code review failed. Check the output below:"
        cat "$OUTPUT_FILE"
        exit 1
    fi
}

# Display results
display_results() {
    print_status "Code Review Results:"
    echo "=================================="
    cat "$OUTPUT_FILE"
    echo "=================================="
    
    # Save results to project directory
    local results_file="$PROJECT_ROOT/code-review-$(date +%Y%m%d-%H%M%S).md"
    cp "$OUTPUT_FILE" "$results_file"
    print_success "Results saved to: $results_file"
}

# Main function
main() {
    echo "🔍 AI Code Review POC"
    echo "====================="
    
    check_prerequisites
    extract_changes
    create_prompt
    run_review
    display_results
    
    print_success "Code review POC completed!"
}

# Help function
show_help() {
    cat << EOF
AI Code Review POC

Usage: $0 [OPTIONS]

This script demonstrates automated code review using StreetRace:
1. Extracts git diff from staged changes, branch changes, or last commit
2. Creates a structured review prompt
3. Runs AI analysis using StreetRace
4. Displays and saves the review results

Environment Variables:
  OPENAI_API_KEY        - API key for OpenAI (recommended)
  ANTHROPIC_API_KEY     - API key for Anthropic Claude
  GOOGLE_API_KEY        - API key for Google AI
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