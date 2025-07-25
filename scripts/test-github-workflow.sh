#!/bin/bash
# Test the GitHub workflow integration end-to-end

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
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

print_annotation() {
    echo -e "${MAGENTA}[ANNOTATION]${NC} $1"
}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Create a sample JSON review for testing
create_sample_review() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local json_file="$PROJECT_ROOT/code-reviews/${timestamp}_structured.json"
    local markdown_file="$PROJECT_ROOT/code-reviews/${timestamp}.md"
    
    mkdir -p "$PROJECT_ROOT/code-reviews"
    
    # Create sample JSON review
    cat > "$json_file" << 'EOF'
{
  "summary": "This PR adds the ESLint-style inline annotation feature for GitHub code reviews. The implementation includes structured JSON output parsing and GitHub annotation generation.",
  "statistics": {
    "files_changed": 5,
    "additions": 450,
    "deletions": 120,
    "total_issues": 6,
    "errors": 1,
    "warnings": 3,
    "notices": 2
  },
  "issues": [
    {
      "severity": "error",
      "file": ".github/workflows/scripts/parse-review-annotations.py",
      "line": 45,
      "end_line": 48,
      "title": "Missing Error Handling",
      "message": "The file path is not validated before use. Add validation to ensure the path exists and is within the repository: if not os.path.exists(file_path) or not os.path.abspath(file_path).startswith(os.getcwd())",
      "category": "security"
    },
    {
      "severity": "warning",
      "file": ".github/workflows/scripts/code-review.sh",
      "line": 112,
      "title": "Hardcoded Timeout Value",
      "message": "Consider making the timeout configurable via environment variable instead of hardcoding 300 seconds",
      "category": "quality"
    },
    {
      "severity": "warning",
      "file": ".github/workflows/code-review.yml",
      "line": 73,
      "title": "Missing Error Context",
      "message": "When the Python script fails, it should provide more context about which step failed",
      "category": "quality"
    },
    {
      "severity": "warning",
      "file": "templates/code-review-prompt.md",
      "line": 28,
      "title": "Incomplete Documentation",
      "message": "Add examples for each severity level to help the AI understand the classification better",
      "category": "quality"
    },
    {
      "severity": "notice",
      "file": "scripts/test-code-review.sh",
      "line": 156,
      "title": "Consider Parallel Execution",
      "message": "The JSON parsing and annotation generation could be run in parallel to improve performance",
      "category": "performance"
    },
    {
      "severity": "notice",
      "file": "scripts/extract-diff.sh",
      "line": 41,
      "title": "Add Progress Indicator",
      "message": "For large diffs, consider adding a progress indicator to show the extraction is still running",
      "category": "quality"
    }
  ],
  "positive_feedback": [
    {
      "file": ".github/workflows/scripts/parse-review-annotations.py",
      "line": 15,
      "message": "Good use of type hints for better code clarity"
    },
    {
      "file": ".github/workflows/code-review.yml",
      "line": 58,
      "message": "Excellent job setting up multiple API key options for flexibility"
    },
    {
      "file": "scripts/test-code-review.sh",
      "line": 34,
      "message": "Comprehensive help documentation"
    }
  ]
}
EOF

    # Create sample markdown review
    cat > "$markdown_file" << 'EOF'
# Code Review Report

**Date:** $(date)
**Model:** openai/gpt-4o-mini (test)

## Summary

This PR adds the ESLint-style inline annotation feature for GitHub code reviews. The implementation includes structured JSON output parsing and GitHub annotation generation.

## Statistics

- Files changed: 5
- Lines added: 450
- Lines removed: 120
- Total issues: 6
  - 🚨 Errors: 1
  - ⚠️ Warnings: 3
  - ℹ️ Notices: 2

## Critical Issues 🚨

### 1. Missing Error Handling in parse-review-annotations.py
**File:** `.github/workflows/scripts/parse-review-annotations.py` (lines 45-48)
**Issue:** The file path is not validated before use
**Fix:** Add validation to ensure the path exists and is within the repository

## High Priority Issues ⚠️

### 1. Hardcoded Timeout Value
**File:** `.github/workflows/scripts/code-review.sh` (line 112)
**Issue:** Timeout is hardcoded to 300 seconds
**Recommendation:** Make it configurable via environment variable

### 2. Missing Error Context
**File:** `.github/workflows/code-review.yml` (line 73)
**Issue:** Error messages lack context
**Recommendation:** Add more descriptive error messages

### 3. Incomplete Documentation
**File:** `templates/code-review-prompt.md` (line 28)
**Issue:** Missing severity level examples
**Recommendation:** Add concrete examples for each level

## Medium Priority Issues ℹ️

### 1. Performance Optimization Opportunity
**File:** `scripts/test-code-review.sh` (line 156)
**Suggestion:** Run JSON parsing and annotation generation in parallel

### 2. UX Enhancement
**File:** `scripts/extract-diff.sh` (line 41)
**Suggestion:** Add progress indicator for large diffs

## Positive Feedback ✅

- Excellent type hints in the Python parser script
- Good flexibility with multiple API key options
- Comprehensive help documentation in test scripts

## Recommendations

1. Address the security issue in the parser script immediately
2. Consider adding integration tests for the annotation format
3. Document the new workflow in the main README
4. Add examples of the annotation output to help users understand the feature
EOF

    echo "$json_file"
}

# Main test function
main() {
    echo "🚀 Testing GitHub Workflow Integration"
    echo "====================================="
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # Step 1: Create sample review files
    print_status "Creating sample review files..."
    JSON_FILE=$(create_sample_review)
    print_success "Created sample review at: $JSON_FILE"
    
    # Step 2: Simulate GitHub Actions environment
    print_status "Simulating GitHub Actions environment..."
    export GITHUB_ACTIONS=true
    export GITHUB_WORKSPACE="$PROJECT_ROOT"
    export GITHUB_STEP_SUMMARY="/tmp/github-step-summary.md"
    
    # Step 3: Test annotation generation
    echo ""
    print_status "Testing annotation generation..."
    echo "The following annotations would appear inline in your PR:"
    echo ""
    
    # Run the parser and show annotations
    python3 "$PROJECT_ROOT/.github/workflows/scripts/parse-review-annotations.py" "$JSON_FILE" --annotations-only | while IFS= read -r line; do
        if [[ "$line" =~ ^:: ]]; then
            print_annotation "$line"
        else
            echo "$line"
        fi
    done
    
    # Step 4: Test summary generation
    echo ""
    print_status "Testing job summary generation..."
    python3 "$PROJECT_ROOT/.github/workflows/scripts/parse-review-annotations.py" "$JSON_FILE" \
        --summary-file "$GITHUB_STEP_SUMMARY"
    
    echo ""
    echo "📄 Generated Job Summary:"
    echo "========================"
    cat "$GITHUB_STEP_SUMMARY"
    
    # Step 5: Show how it looks in GitHub
    echo ""
    echo ""
    print_success "Workflow test completed!"
    echo ""
    echo "📋 How this appears in GitHub:"
    echo "=============================="
    echo ""
    echo "1. ${MAGENTA}Inline Annotations:${NC}"
    echo "   - Error annotations show as ❌ red marks on specific lines"
    echo "   - Warning annotations show as ⚠️ yellow marks"
    echo "   - Notice annotations show as ℹ️ blue marks"
    echo "   - Clicking on them shows the full message"
    echo ""
    echo "2. ${MAGENTA}PR Comment:${NC}"
    echo "   - The markdown report is posted as a comment"
    echo "   - Provides overview and detailed feedback"
    echo ""
    echo "3. ${MAGENTA}Job Summary:${NC}"
    echo "   - Visible in the Actions tab"
    echo "   - Quick overview of the review results"
    echo ""
    echo "4. ${MAGENTA}Status Check:${NC}"
    echo "   - PR blocked if any 'error' severity issues exist"
    echo "   - Shows as ✅ or ❌ in the PR checks section"
    
    # Cleanup
    rm -f "$GITHUB_STEP_SUMMARY"
}

# Show help
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    echo "Test GitHub Workflow Integration"
    echo ""
    echo "Usage: $0"
    echo ""
    echo "This script demonstrates how the ESLint-style annotations"
    echo "will appear in GitHub PRs. It creates sample review data"
    echo "and shows the generated annotations."
    exit 0
fi

# Run main function
main