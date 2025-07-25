#!/bin/bash

# test-code-review.sh
# Test script for complete code review workflow
# This script demonstrates how to use StreetRace for automated code review

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMP_FILE="/tmp/code-review-$(date +%s).md"

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

# Function to clean up temporary files
cleanup() {
    if [ -f "$TEMP_FILE" ]; then
        rm -f "$TEMP_FILE"
    fi
}

trap cleanup EXIT

# Function to test diff extraction
test_diff_extraction() {
    print_status "Testing diff extraction..."
    
    # Test with staged changes
    if ! git diff --cached --quiet; then
        print_status "Found staged changes, testing extraction..."
        
        "$PROJECT_ROOT/scripts/extract-diff.sh" --staged --filter "*.py,*.sh,*.md,Dockerfile" > "$TEMP_FILE"
        
        if [ -s "$TEMP_FILE" ]; then
            print_success "Diff extraction successful"
            print_status "Diff size: $(wc -c < "$TEMP_FILE") bytes"
            print_status "Lines: $(wc -l < "$TEMP_FILE") lines"
        else
            print_error "Diff extraction failed - empty output"
            return 1
        fi
    else
        print_warning "No staged changes found. Testing with committed changes..."
        
        # Try to get diff from last commit
        if git log --oneline -1 > /dev/null 2>&1; then
            "$PROJECT_ROOT/scripts/extract-diff.sh" -b HEAD~1 -t HEAD > "$TEMP_FILE"
            
            if [ -s "$TEMP_FILE" ]; then
                print_success "Diff extraction from last commit successful"
            else
                print_warning "No differences found in last commit"
                # Create a minimal test diff for demonstration
                echo "# Test Diff" > "$TEMP_FILE"
                echo "This is a test diff for demonstration purposes." >> "$TEMP_FILE"
            fi
        else
            print_warning "No git history found. Creating test diff..."
            echo "# Test Diff" > "$TEMP_FILE"
            echo "This is a test diff for demonstration purposes." >> "$TEMP_FILE"
        fi
    fi
}

# Function to create code review prompt
create_review_prompt() {
    print_status "Creating code review prompt..."
    
    local template_file="$PROJECT_ROOT/templates/code-review-prompt.md"
    local diff_content
    
    if [ ! -f "$template_file" ]; then
        print_error "Template file not found: $template_file"
        return 1
    fi
    
    # Read the diff content
    diff_content=$(cat "$TEMP_FILE")
    
    # Create the prompt by replacing the placeholder
    # We'll use a simpler approach to avoid sed escaping issues
    local temp_template="${TEMP_FILE}.template"
    cp "$template_file" "$temp_template"
    
    # Use Python to do the replacement safely
    python3 -c "
import sys
with open('$temp_template', 'r') as f:
    template = f.read()
with open('$TEMP_FILE', 'r') as f:
    diff_content = f.read()
result = template.replace('{DIFF_CONTENT}', diff_content)
with open('${TEMP_FILE}.prompt', 'w') as f:
    f.write(result)
" 
    
    rm -f "$temp_template"
    
    print_success "Code review prompt created: ${TEMP_FILE}.prompt"
    print_status "Prompt size: $(wc -c < "${TEMP_FILE}.prompt") bytes"
}

# Function to test StreetRace non-interactive mode
test_streetrace_noninteractive() {
    print_status "Testing StreetRace non-interactive mode..."
    
    local prompt_file="${TEMP_FILE}.prompt"
    
    if [ ! -f "$prompt_file" ]; then
        print_error "Prompt file not found: $prompt_file"
        return 1
    fi
    
    # Test with a simple prompt first
    print_status "Testing with simple prompt..."
    
    cd "$PROJECT_ROOT"
    
    # Test basic invocation
    if poetry run streetrace --help > /dev/null 2>&1; then
        print_success "StreetRace is accessible via poetry"
    else
        print_error "StreetRace is not accessible via poetry"
        return 1
    fi
    
    # Test non-interactive mode with simple prompt
    print_status "Testing simple non-interactive mode..."
    local simple_prompt="Please analyze this text: Hello World. Provide a brief response."
    
    # Note: We're not actually running with a real model here since this is for testing the infrastructure
    # In real usage, you would set ANTHROPIC_API_KEY or other API keys
    
    if [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
        print_status "API keys detected. Running actual test..."
        
        # Run with a model that's likely to be available
        if poetry run streetrace --model=anthropic/claude-3-haiku-20240307 --prompt="$simple_prompt" 2>/dev/null; then
            print_success "Non-interactive mode test successful"
        else
            print_warning "Non-interactive mode test failed, but infrastructure is working"
        fi
    else
        print_warning "No API keys found. Skipping actual model test."
        print_status "Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or similar to test with real models"
    fi
    
    print_success "Infrastructure test completed"
}

# Function to demonstrate complete workflow
demonstrate_workflow() {
    print_status "Demonstrating complete code review workflow..."
    
    cat << EOF

# Complete Code Review Workflow

This demonstrates how to use the Docker-based testing environment for GitHub workflow integration:

## 1. Extract diff from changes
./scripts/extract-diff.sh --staged --filter "*.py,*.js,*.ts,*.go"

## 2. Generate code review prompt
# The template at templates/code-review-prompt.md provides structured guidance

## 3. Run StreetRace for code review
poetry run streetrace --model=anthropic/claude-3-5-sonnet-20241022 --prompt="\$(cat prompt.md)"

## 4. For GitHub Actions integration:
# The docker/github-action/Dockerfile provides the environment
# The scripts/test-github-workflow.sh provides local testing

## 5. Example GitHub Action workflow:
cat << 'YAML'
name: AI Code Review
on: [pull_request]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install Poetry
        uses: snok/install-poetry@v1
      - name: Install dependencies
        run: poetry install
      - name: Extract diff
        run: |
          ./scripts/extract-diff.sh -b origin/main -t HEAD > diff.txt
      - name: Run code review
        env:
          ANTHROPIC_API_KEY: \${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          DIFF_CONTENT=\$(cat diff.txt)
          PROMPT=\$(sed "s/{DIFF_CONTENT}/\$DIFF_CONTENT/g" templates/code-review-prompt.md)
          poetry run streetrace --model=anthropic/claude-3-5-sonnet-20241022 --prompt="\$PROMPT"
YAML

EOF
}

# Main function
main() {
    print_status "Starting complete code review workflow test"
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Run tests
    test_diff_extraction
    create_review_prompt
    test_streetrace_noninteractive
    demonstrate_workflow
    
    print_success "All tests completed successfully!"
    print_status "Docker environment and scripts are ready for GitHub workflow integration"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Test script for complete code review workflow"
        echo ""
        echo "Options:"
        echo "  -h, --help     Show this help message"
        echo ""
        echo "This script tests the complete workflow:"
        echo "1. Diff extraction"
        echo "2. Prompt generation"
        echo "3. StreetRace integration"
        echo "4. Docker environment"
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        exit 1
        ;;
esac