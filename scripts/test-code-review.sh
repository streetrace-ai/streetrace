#!/bin/bash
# Test the GitHub code review workflow locally

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

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Help function
show_help() {
    cat << EOF
Test GitHub Code Review Locally

Usage: $0 [OPTIONS]

This script tests the AI code review process locally, including:
1. Running the code review
2. Parsing the structured output
3. Showing what GitHub annotations would be generated

Options:
  -h, --help           Show this help message
  -m, --model MODEL    Specify the AI model to use (default: from env or openai/gpt-4o-mini)
  --skip-review        Skip running the review, use existing files
  --json-file FILE     Path to existing JSON review file (implies --skip-review)

Examples:
  $0                                          # Run full test with default model
  $0 --model anthropic/claude-3-5-sonnet     # Use specific model
  $0 --skip-review                           # Test parsing only
  $0 --json-file code-reviews/test.json      # Test specific JSON file

Prerequisites:
- Must be run from within the StreetRace project directory
- Must have poetry installed with project dependencies
- Must have an AI API key configured
EOF
}

# Default values
MODEL="${STREETRACE_MODEL:-openai/gpt-4o-mini}"
SKIP_REVIEW=false
JSON_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        --skip-review)
            SKIP_REVIEW=true
            shift
            ;;
        --json-file)
            JSON_FILE="$2"
            SKIP_REVIEW=true
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main test function
main() {
    echo "🧪 Testing GitHub Code Review Locally"
    echo "===================================="
    
    cd "$PROJECT_ROOT"
    
    # Step 1: Run the code review (unless skipping)
    if [ "$SKIP_REVIEW" = false ]; then
        print_status "Running code review with model: $MODEL"
        
        # Export model for the review script
        export STREETRACE_MODEL="$MODEL"
        
        # Run the review
        if ! python3 "$PROJECT_ROOT/.github/workflows/scripts/code_review.py"; then
            print_error "Code review failed"
            exit 1
        fi
        
        # Find the most recent JSON file
        JSON_FILE=$(ls -t code-reviews/*_structured.json 2>/dev/null | head -n1)
        
        if [ -z "$JSON_FILE" ] || [ ! -f "$JSON_FILE" ]; then
            print_error "No structured JSON review file found"
            exit 1
        fi
    else
        # Validate provided JSON file
        if [ -z "$JSON_FILE" ] || [ ! -f "$JSON_FILE" ]; then
            # Try to find the most recent one
            JSON_FILE=$(ls -t code-reviews/*_structured.json 2>/dev/null | head -n1)
            
            if [ -z "$JSON_FILE" ] || [ ! -f "$JSON_FILE" ]; then
                print_error "No JSON file specified and no recent reviews found"
                exit 1
            fi
        fi
    fi
    
    print_success "Using review file: $JSON_FILE"
    
    # Step 2: Parse and display the review
    print_status "Parsing structured review..."
    
    # Show JSON summary
    echo ""
    echo "📊 Review Statistics:"
    python3 -c "
import json
with open('$JSON_FILE') as f:
    data = json.load(f)
    stats = data.get('statistics', {})
    print(f\"  - Total issues: {stats.get('total_issues', 0)}\")
    print(f\"  - Errors: {stats.get('errors', 0)}\")
    print(f\"  - Warnings: {stats.get('warnings', 0)}\")
    print(f\"  - Notices: {stats.get('notices', 0)}\")
"
    
    # Step 3: Generate GitHub annotations (dry run)
    print_status "Testing GitHub annotations generation..."
    echo ""
    echo "📝 GitHub Annotations that would be generated:"
    echo "=============================================="
    
    # Run the parser in test mode (just show annotations)
    python3 "$PROJECT_ROOT/.github/workflows/scripts/parse-review-annotations.py" "$JSON_FILE" --annotations-only
    
    # Step 4: Show the summary
    echo ""
    echo "📄 Job Summary:"
    echo "==============="
    
    # Generate and display the summary
    python3 "$PROJECT_ROOT/.github/workflows/scripts/parse-review-annotations.py" "$JSON_FILE" \
        --summary-file /tmp/test-summary.md
    
    if [ -f /tmp/test-summary.md ]; then
        cat /tmp/test-summary.md
        rm -f /tmp/test-summary.md
    fi
    
    echo ""
    print_success "Test completed successfully!"
    
    # Show next steps
    echo ""
    echo "ℹ️  Next Steps:"
    echo "  1. Review the annotations above - they will appear inline in the PR"
    echo "  2. Check the generated markdown report: $(ls -t code-reviews/*.md | head -n1)"
    echo "  3. The JSON file contains all structured data: $JSON_FILE"
    
    # Check if there are errors
    ERROR_COUNT=$(python3 -c "
import json
with open('$JSON_FILE') as f:
    data = json.load(f)
    errors = sum(1 for issue in data.get('issues', []) if issue.get('severity') == 'error')
    print(errors)
")
    
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo ""
        print_warning "The review found $ERROR_COUNT error(s) that would block the PR"
    fi
}

# Run main function
main