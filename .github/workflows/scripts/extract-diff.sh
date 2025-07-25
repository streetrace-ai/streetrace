#!/bin/bash

# extract-diff.sh
# Extracts git diff for code review processing
# This script generates a formatted diff suitable for AI code review

set -euo pipefail

# Default values
BASE_BRANCH="main"
TARGET_BRANCH="HEAD"
OUTPUT_FORMAT="unified"
MAX_DIFF_SIZE=100000  # 100KB limit to prevent excessive token usage
INCLUDE_STATS=true
FILTER_PATTERNS=""
STAGED_CHANGES=false

# Function to print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Extract git diff for code review processing

Options:
    -b, --base BRANCH       Base branch for comparison (default: main)
    -t, --target BRANCH     Target branch for comparison (default: HEAD)
    --staged               Compare staged changes against HEAD
    -f, --format FORMAT     Output format: unified, patch, or stats (default: unified)
    -s, --max-size SIZE     Maximum diff size in bytes (default: 100000)
    --no-stats             Don't include diff statistics
    --filter PATTERNS      Comma-separated file patterns to include (e.g., "*.py,*.js")
    --exclude PATTERNS     Comma-separated file patterns to exclude (e.g., "*.md,*.txt")
    -h, --help             Show this help message

Examples:
    $0                                    # Compare main..HEAD
    $0 -b origin/main -t HEAD            # Compare origin/main..HEAD
    $0 --filter "*.py,*.js" --no-stats   # Only Python and JavaScript files
    $0 --exclude "*.md,*.txt"            # Exclude documentation files
EOF
}

# Function to check if git repository exists
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "Error: Not a git repository" >&2
        exit 1
    fi
}

# Function to validate branch exists
validate_branch() {
    local branch="$1"
    if ! git rev-parse --verify "$branch" > /dev/null 2>&1; then
        echo "Error: Branch '$branch' does not exist" >&2
        exit 1
    fi
}

# Function to get diff stats
get_diff_stats() {
    local base="$1"
    local target="$2"
    local filter_args=()
    
    if [ -n "$FILTER_PATTERNS" ]; then
        IFS=',' read -ra PATTERNS <<< "$FILTER_PATTERNS"
        for pattern in "${PATTERNS[@]}"; do
            filter_args+=("--" "$pattern")
        done
    fi
    
    if [ "$STAGED_CHANGES" = true ]; then
        if [ ${#filter_args[@]} -gt 0 ]; then
            git diff --cached --stat "${filter_args[@]}"
        else
            git diff --cached --stat
        fi
    else
        if [ ${#filter_args[@]} -gt 0 ]; then
            git diff --stat "$base...$target" "${filter_args[@]}"
        else
            git diff --stat "$base...$target"
        fi
    fi
}

# Function to get file list with changes
get_changed_files() {
    local base="$1"
    local target="$2"
    local filter_args=()
    
    if [ -n "$FILTER_PATTERNS" ]; then
        IFS=',' read -ra PATTERNS <<< "$FILTER_PATTERNS"
        for pattern in "${PATTERNS[@]}"; do
            filter_args+=("--" "$pattern")
        done
    fi
    
    if [ "$STAGED_CHANGES" = true ]; then
        if [ ${#filter_args[@]} -gt 0 ]; then
            git diff --cached --name-only "${filter_args[@]}"
        else
            git diff --cached --name-only
        fi
    else
        if [ ${#filter_args[@]} -gt 0 ]; then
            git diff --name-only "$base...$target" "${filter_args[@]}"
        else
            git diff --name-only "$base...$target"
        fi
    fi
}

# Function to extract unified diff
extract_unified_diff() {
    local base="$1"
    local target="$2"
    local filter_args=()
    local exclude_args=()
    
    # Handle include patterns
    if [ -n "$FILTER_PATTERNS" ]; then
        IFS=',' read -ra PATTERNS <<< "$FILTER_PATTERNS"
        for pattern in "${PATTERNS[@]}"; do
            filter_args+=("--" "$pattern")
        done
    fi
    
    # Generate the diff
    local diff_output
    if [ "$STAGED_CHANGES" = true ]; then
        if [ ${#filter_args[@]} -gt 0 ]; then
            diff_output=$(git diff --cached "${filter_args[@]}")
        else
            diff_output=$(git diff --cached)
        fi
    else
        if [ ${#filter_args[@]} -gt 0 ]; then
            diff_output=$(git diff "$base...$target" "${filter_args[@]}")
        else
            diff_output=$(git diff "$base...$target")
        fi
    fi
    
    # Check diff size
    local diff_size=${#diff_output}
    if [ $diff_size -gt $MAX_DIFF_SIZE ]; then
        echo "Warning: Diff size ($diff_size bytes) exceeds limit ($MAX_DIFF_SIZE bytes)" >&2
        echo "Consider using --filter to include only specific file types" >&2
        # Truncate the diff
        diff_output=$(echo "$diff_output" | head -c $MAX_DIFF_SIZE)
        diff_output="$diff_output\n\n[DIFF TRUNCATED - Original size: $diff_size bytes]"
    fi
    
    echo "$diff_output"
}

# Function to format output for code review
format_for_review() {
    local base="$1"
    local target="$2"
    
    echo "# Code Review Diff"
    echo ""
    echo "**Base:** $base"
    echo "**Target:** $target"
    echo "**Generated:** $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo ""
    
    if [ "$INCLUDE_STATS" = true ]; then
        echo "## Statistics"
        echo "\`\`\`"
        get_diff_stats "$base" "$target"
        echo "\`\`\`"
        echo ""
        
        echo "## Changed Files"
        local changed_files
        changed_files=$(get_changed_files "$base" "$target")
        if [ -n "$changed_files" ]; then
            echo "$changed_files" | sed 's/^/- /'
        else
            echo "No files changed"
            return 0
        fi
        echo ""
    fi
    
    echo "## Diff"
    echo "\`\`\`diff"
    extract_unified_diff "$base" "$target"
    echo "\`\`\`"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--base)
            BASE_BRANCH="$2"
            shift 2
            ;;
        -t|--target)
            TARGET_BRANCH="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -s|--max-size)
            MAX_DIFF_SIZE="$2"
            shift 2
            ;;
        --no-stats)
            INCLUDE_STATS=false
            shift
            ;;
        --staged)
            STAGED_CHANGES=true
            shift
            ;;
        --filter)
            FILTER_PATTERNS="$2"
            shift 2
            ;;
        --exclude)
            # Note: Git doesn't have a direct exclude pattern, so we'll document this limitation
            echo "Warning: --exclude is not implemented yet. Use --filter for include patterns instead." >&2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    check_git_repo
    validate_branch "$BASE_BRANCH"
    validate_branch "$TARGET_BRANCH"
    
    # Check if there are any changes
    local has_changes=false
    if [ "$STAGED_CHANGES" = true ]; then
        if ! git diff --cached --quiet; then
            has_changes=true
        fi
    else
        if ! git diff --quiet "$BASE_BRANCH...$TARGET_BRANCH"; then
            has_changes=true
        fi
    fi
    
    if [ "$has_changes" = true ]; then
        case "$OUTPUT_FORMAT" in
            unified|patch)
                format_for_review "$BASE_BRANCH" "$TARGET_BRANCH"
                ;;
            stats)
                get_diff_stats "$BASE_BRANCH" "$TARGET_BRANCH"
                ;;
            *)
                echo "Error: Unknown format '$OUTPUT_FORMAT'" >&2
                exit 1
                ;;
        esac
    else
        if [ "$STAGED_CHANGES" = true ]; then
            echo "No staged changes found"
        else
            echo "No differences found between $BASE_BRANCH and $TARGET_BRANCH"
        fi
        exit 0
    fi
}

# Run main function
main