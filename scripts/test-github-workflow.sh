#!/bin/bash

# test-github-workflow.sh
# Simulate GitHub Actions workflow locally for testing

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

# Main function
main() {
    echo "🧪 Testing GitHub Actions Workflow Locally"
    echo "=========================================="
    
    cd "$PROJECT_ROOT"
    
    # Clean up any previous test runs
    rm -rf /tmp/*review*.txt code-reviews/*.md 2>/dev/null || true
    
    # Load environment
    if [ -f .env ]; then
        print_status "Loading .env file"
        set -a
        source .env
        set +a
    fi
    
    # Simulate GitHub Actions environment variables
    export PR_NUMBER="999"
    export PR_TITLE="Test PR: Code Review Integration"
    export PR_AUTHOR="test-user"
    export BASE_BRANCH="main"
    export HEAD_BRANCH="feature/test-branch"
    export GITHUB_REPOSITORY="test-org/test-repo"
    
    print_status "Simulated PR Environment:"
    echo "  PR #${PR_NUMBER}: ${PR_TITLE}"
    echo "  Author: ${PR_AUTHOR}"
    echo "  Base: ${BASE_BRANCH} <- Head: ${HEAD_BRANCH}"
    echo ""
    
    # Step 1: Run Code Review
    print_status "Step 1: Running Code Review"
    echo "----------------------------"
    
    if ./.github/workflows/scripts/code-review.sh; then
        print_success "Code review completed"
    else
        print_error "Code review failed"
        exit 1
    fi
    
    # Step 2: Find the generated report
    print_status "Step 2: Finding Review Report"
    echo "------------------------------"
    
    LATEST_REPORT=$(ls -t code-reviews/*.md 2>/dev/null | head -n1)
    
    if [ -n "$LATEST_REPORT" ] && [ -f "$LATEST_REPORT" ]; then
        print_success "Found review report: $LATEST_REPORT"
        cp "$LATEST_REPORT" /tmp/ai-review-result.txt
        
        echo ""
        print_status "Report Preview:"
        head -n 20 "$LATEST_REPORT"
        echo "..."
        echo ""
    else
        print_error "No review report found in code-reviews/"
        exit 1
    fi
    
    # Step 3: Test Post Review Comment
    print_status "Step 3: Testing Post Review Comment"
    echo "------------------------------------"
    
    if [ -f "/tmp/ai-review-result.txt" ] && [ -s "/tmp/ai-review-result.txt" ]; then
        print_status "Would post review to PR #${PR_NUMBER}"
        print_status "Review content size: $(wc -c < /tmp/ai-review-result.txt) bytes"
        
        # Simulate the post (don't actually post to GitHub)
        echo ""
        print_warning "Simulating GitHub comment post (not actually posting)"
        echo "Would execute: ./.github/workflows/scripts/post-review-comment.sh /tmp/ai-review-result.txt"
    else
        print_error "No review generated"
        exit 1
    fi
    
    # Step 4: Archive simulation
    print_status "Step 4: Simulating Archive"
    echo "--------------------------"
    
    print_status "Would archive:"
    ls -la /tmp/*review*.txt 2>/dev/null || echo "  No temp review files"
    ls -la code-reviews/*.md 2>/dev/null || echo "  No review reports"
    
    echo ""
    print_success "GitHub Actions workflow test completed successfully!"
    print_status "Review report saved at: $LATEST_REPORT"
}

# Help function
show_help() {
    cat << EOF
Test GitHub Actions Workflow Locally

Usage: $0 [OPTIONS]

This script simulates the GitHub Actions workflow environment locally
to test the code review integration without actually running in GitHub.

Options:
  -h, --help    Show this help message

The script will:
1. Run the code review workflow
2. Find and validate the generated report
3. Simulate posting to GitHub (without actually posting)
4. Show what would be archived

Environment Variables:
  Uses the same environment variables as the actual workflow
  (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
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