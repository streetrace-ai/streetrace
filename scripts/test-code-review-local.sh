#!/bin/bash
# Local test script for AI code review workflow
# This simulates the GitHub Actions workflow locally for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

print_status "🧪 Local AI Code Review Test"
print_status "============================="

# Check if we're in the right directory
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    print_error "Not in the StreetRace project root directory"
    exit 1
fi

# Check prerequisites
print_status "Checking prerequisites..."

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    print_error "Poetry is not installed. Please install poetry first."
    exit 1
fi

# Check if we're in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Load environment variables from .env if it exists
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    print_status "Loading environment variables from .env"
    # Export variables from .env file
    set -o allexport
    source "$PROJECT_ROOT/.env"
    set +o allexport
fi

# Check for API keys
if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" && -z "$GOOGLE_AI_API_KEY" ]]; then
    print_error "No API key found. Set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY"
    print_status "You can create a .env file in the project root with: OPENAI_API_KEY=your_key_here"
    exit 1
fi

print_success "Prerequisites OK"

# Simulate the workflow steps
print_status "Installing dependencies (simulating workflow setup)..."

# Install Poetry dependencies
poetry install

print_status "Setting up test environment..."

# Create mock environment variables like GitHub Actions would
export PR_NUMBER="123"
export PR_TITLE="Test PR for local code review"
export PR_AUTHOR="local-test"
export BASE_BRANCH="main"
export HEAD_BRANCH="$(git branch --show-current)"
export GITHUB_REPOSITORY="test/street-race"

# Set up temporary GITHUB_ENV file for environment variable passing
TEMP_ENV_FILE=$(mktemp)
export GITHUB_ENV="$TEMP_ENV_FILE"

print_status "Current branch: $HEAD_BRANCH"
print_status "Base branch: $BASE_BRANCH"

# Check for changes to review
print_status "Checking for changes to review..."

if git diff --quiet main...HEAD && git diff --cached --quiet; then
    print_warning "No changes found to review. Creating some test changes or switch to a feature branch."
    print_status "You can:"
    print_status "  1. Make some changes and stage them with 'git add'"
    print_status "  2. Switch to a feature branch with changes"
    print_status "  3. Create a test commit"
    
    # Ask user what they want to do
    echo
    read -p "Continue anyway with recent commits? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Exiting. Make some changes first."
        rm -f "$TEMP_ENV_FILE"
        exit 0
    fi
fi

print_success "Found changes to review"

# Run the actual code review script
print_status "Running AI code review..."
print_status "This will take a few minutes..."

cd "$PROJECT_ROOT"

# Execute the code review script with error handling
if python3 ./.github/workflows/scripts/code_review.py; then
    print_success "Code review completed successfully!"
else
    print_error "Code review failed"
    rm -f "$TEMP_ENV_FILE"
    exit 1
fi

# Check what files were created
print_status "Checking generated files..."

# Read environment variables that were set by the script
if [[ -f "$GITHUB_ENV" ]]; then
    while IFS= read -r line; do
        if [[ $line == REVIEW_*_FILE=* ]]; then
            export "$line"
            echo "  Exported: $line"
        fi
    done < "$GITHUB_ENV"
fi

# Display results
print_status "📊 Review Results"
print_status "=================="

if [[ -n "$REVIEW_JSON_FILE" && -f "$REVIEW_JSON_FILE" ]]; then
    print_success "✅ JSON review file: $REVIEW_JSON_FILE"
    
    # Show basic stats
    if command -v jq &> /dev/null; then
        echo
        print_status "Quick stats:"
        jq -r '.statistics | to_entries[] | "  \(.key): \(.value)"' "$REVIEW_JSON_FILE" 2>/dev/null || true
    fi
else
    print_warning "❌ No JSON review file generated"
fi

if [[ -n "$REVIEW_MARKDOWN_FILE" && -f "$REVIEW_MARKDOWN_FILE" ]]; then
    print_success "✅ Markdown report: $REVIEW_MARKDOWN_FILE"
else
    print_warning "❌ No Markdown report generated"
fi

if [[ -n "$REVIEW_SARIF_FILE" && -f "$REVIEW_SARIF_FILE" ]]; then
    print_success "✅ SARIF file: $REVIEW_SARIF_FILE"
    
    # Show SARIF stats if possible
    if command -v jq &> /dev/null; then
        echo
        print_status "SARIF results:"
        jq -r '.runs[0].results | length as $count | "  Found \($count) issues"' "$REVIEW_SARIF_FILE" 2>/dev/null || true
    fi
else
    print_warning "❌ No SARIF file generated"
fi

# Generate summary like GitHub Actions would
if [[ -n "$REVIEW_JSON_FILE" && -f "$REVIEW_JSON_FILE" ]]; then
    print_status "📋 Summary (simulating GitHub Actions job summary):"
    print_status "=================================================="
    python3 ./.github/workflows/scripts/generate_summary.py "$REVIEW_JSON_FILE"
fi

# Show file locations
echo
print_status "📁 Generated files are located in:"
print_status "  code-reviews/ directory"

if ls code-reviews/*.json &> /dev/null; then
    print_status "JSON files:"
    ls -la code-reviews/*.json | sed 's/^/    /'
fi

if ls code-reviews/*.md &> /dev/null; then
    print_status "Markdown files:"
    ls -la code-reviews/*.md | sed 's/^/    /'
fi

# Clean up
rm -f "$TEMP_ENV_FILE"

print_success "🎉 Local code review test completed!"
print_status "You can now review the generated files before committing your changes."