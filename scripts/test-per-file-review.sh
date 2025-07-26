#!/bin/bash

# Test script for per-file code review architecture
# Tests with only 3 files including test_problematic_code.py

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

print_status "Testing per-file code review architecture"
print_status "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# Check if we're in git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Load environment variables from .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    print_status "Loading environment variables from .env"
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Check for API keys
if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" && -z "$GOOGLE_AI_API_KEY" ]]; then
    print_error "No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY"
    exit 1
fi

print_success "Prerequisites OK"

print_status "Running TEST per-file review (limited to 3 files including test_problematic_code.py)..."

# Set environment for per-file review
export STREETRACE_MODEL="openai/gpt-4o"
export REVIEW_STRATEGY="per-file"

# Run the dedicated test script
if python3 .github/workflows/scripts/test_per_file_code_review.py main; then
    print_success "Per-file review test completed successfully!"
    
    # Show the results
    print_status "Checking generated files..."
    
    LATEST_REVIEW=$(ls -t code-reviews/*_test_per_file_structured.json 2>/dev/null | head -1)
    if [[ -n "$LATEST_REVIEW" && -f "$LATEST_REVIEW" ]]; then
        print_success "Found review file: $LATEST_REVIEW"
        
        # Show summary
        echo ""
        echo "=== REVIEW SUMMARY ==="
        python3 -c "
import json
with open('$LATEST_REVIEW') as f:
    data = json.load(f)
print(f\"Files reviewed: {data['statistics']['files_changed']}\")
print(f\"Total issues: {data['statistics']['total_issues']}\")
print(f\"Errors: {data['statistics']['errors']}\")
print(f\"Warnings: {data['statistics']['warnings']}\")
print(f\"Notices: {data['statistics']['notices']}\")
print()
print('Issues found:')
for issue in data['issues']:
    print(f\"  - {issue['file']}:{issue['line']} [{issue['severity']}] {issue['title']}\")
"
    else
        print_warning "No review files found"
    fi
    
    # Show individual review files
    echo ""
    print_status "Individual review files:"
    ls -la code-reviews/*_file_*_review.json 2>/dev/null | tail -3 || echo "No individual review files found"
    
else
    print_error "Per-file review test failed"
    exit 1
fi

print_success "Test completed!"