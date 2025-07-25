#!/bin/bash

# github-diff-extractor.sh
# Extracts PR diff for GitHub Actions code review workflow
# Specifically designed for GitHub Actions environment with PR context

set -euo pipefail

# GitHub Actions environment variables
PR_NUMBER="${PR_NUMBER:-}"
BASE_BRANCH="${BASE_BRANCH:-main}"
HEAD_BRANCH="${HEAD_BRANCH:-HEAD}"
GITHUB_SHA="${GITHUB_SHA:-HEAD}"

# Configuration
MAX_DIFF_SIZE=100000  # 100KB limit to prevent excessive token usage
EXCLUDE_PATTERNS="*.md,*.txt,*.json,*.yml,*.yaml,*.lock,*.sum,*.mod"
INCLUDE_PATTERNS="*.py,*.js,*.ts,*.jsx,*.tsx,*.go,*.rs,*.java,*.cpp,*.c,*.h,*.php,*.rb,*.sh"

# Function to check if git repository exists
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "Error: Not a git repository" >&2
        exit 1
    fi
}

# Function to get the base commit for comparison
get_base_commit() {
    # In GitHub Actions, we need to find the merge-base
    if [ -n "$PR_NUMBER" ]; then
        # For PR context, use merge-base between base and head
        git merge-base "origin/$BASE_BRANCH" "$GITHUB_SHA" 2>/dev/null || echo "origin/$BASE_BRANCH"
    else
        echo "origin/$BASE_BRANCH"
    fi
}

# Function to filter diff by file patterns
filter_diff_by_patterns() {
    local diff_content="$1"
    local include_patterns="$2"
    local exclude_patterns="$3"
    
    # Convert comma-separated patterns to grep-compatible format
    if [ -n "$exclude_patterns" ]; then
        local exclude_regex=$(echo "$exclude_patterns" | sed 's/\*/.*/g' | sed 's/,/\\|/g')
        diff_content=$(echo "$diff_content" | grep -v "^diff --git.*\($exclude_regex\)" || echo "$diff_content")
    fi
    
    if [ -n "$include_patterns" ]; then
        local include_regex=$(echo "$include_patterns" | sed 's/\*/.*/g' | sed 's/,/\\|/g')
        diff_content=$(echo "$diff_content" | grep -A999999 "^diff --git.*\($include_regex\)" || echo "$diff_content")
    fi
    
    echo "$diff_content"
}

# Function to generate diff statistics
generate_diff_stats() {
    local base_commit="$1"
    local target_commit="$2"
    
    echo "=== DIFF STATISTICS ==="
    echo "Repository: $(git remote get-url origin 2>/dev/null || echo 'local repository')"
    echo "Base: $base_commit"
    echo "Target: $target_commit"
    
    if [ -n "$PR_NUMBER" ]; then
        echo "PR Number: #$PR_NUMBER"
        echo "Base Branch: $BASE_BRANCH"
        echo "Head Branch: $HEAD_BRANCH"
    fi
    
    echo ""
    
    # File statistics
    echo "Changed files:"
    git diff --name-status "$base_commit..$target_commit" | head -20
    
    local total_files=$(git diff --name-only "$base_commit..$target_commit" | wc -l)
    if [ "$total_files" -gt 20 ]; then
        echo "... and $((total_files - 20)) more files"
    fi
    
    echo ""
    
    # Line statistics
    echo "Diff summary:"
    git diff --stat "$base_commit..$target_commit" | tail -1
    
    echo ""
    echo "=== END STATISTICS ==="
    echo ""
}

# Function to validate diff size
validate_diff_size() {
    local diff_content="$1"
    local size=$(echo "$diff_content" | wc -c)
    
    if [ "$size" -gt "$MAX_DIFF_SIZE" ]; then
        echo "Warning: Diff size ($size bytes) exceeds limit ($MAX_DIFF_SIZE bytes)" >&2
        echo "Consider filtering or splitting the changes for better AI review" >&2
        return 1
    fi
    
    return 0
}

# Main execution
main() {
    # Validate environment
    check_git_repo
    
    # Determine comparison points
    local base_commit=$(get_base_commit)
    local target_commit="$GITHUB_SHA"
    
    echo "Extracting diff: $base_commit..$target_commit" >&2
    
    # Generate diff statistics
    generate_diff_stats "$base_commit" "$target_commit"
    
    # Extract the diff
    local diff_content
    diff_content=$(git diff "$base_commit..$target_commit" 2>/dev/null || {
        echo "Error: Failed to generate diff between $base_commit and $target_commit" >&2
        exit 1
    })
    
    # Handle empty diff
    if [ -z "$diff_content" ]; then
        echo "No changes detected between $base_commit and $target_commit" >&2
        echo ""
        echo "=== NO CHANGES TO REVIEW ==="
        exit 0
    fi
    
    # Filter diff by patterns
    diff_content=$(filter_diff_by_patterns "$diff_content" "$INCLUDE_PATTERNS" "$EXCLUDE_PATTERNS")
    
    # Validate diff size
    if ! validate_diff_size "$diff_content"; then
        echo "Diff size validation failed" >&2
        # Still output the diff, but warn about size
    fi
    
    # Output the filtered diff
    echo "=== CODE CHANGES FOR REVIEW ==="
    echo ""
    echo "$diff_content"
    
    # Footer with metadata
    echo ""
    echo "=== REVIEW CONTEXT ==="
    echo "Generated at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "Commit SHA: $target_commit"
    if [ -n "$PR_NUMBER" ]; then
        echo "GitHub PR: #$PR_NUMBER"
        echo "Comparison: $BASE_BRANCH...$HEAD_BRANCH"
    fi
    echo "Diff size: $(echo "$diff_content" | wc -c) bytes"
    echo "Changed files: $(echo "$diff_content" | grep -c '^diff --git' || echo 0)"
}

# Execute main function
main "$@"