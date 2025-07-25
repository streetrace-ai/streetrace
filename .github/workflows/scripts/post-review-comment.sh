#!/bin/bash

# post-review-comment.sh
# Posts AI code review results as GitHub PR comments
# Designed for GitHub Actions environment

set -euo pipefail

# Required environment variables
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
PR_NUMBER="${PR_NUMBER:-}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-}"

# Optional environment variables
PR_TITLE="${PR_TITLE:-}"
PR_AUTHOR="${PR_AUTHOR:-}"
BASE_BRANCH="${BASE_BRANCH:-main}"
HEAD_BRANCH="${HEAD_BRANCH:-}"

# Configuration
COMMENT_PREFIX="🤖 **AI Code Review**"
MAX_COMMENT_LENGTH=65000  # GitHub comment limit is ~65k characters

# Function to print usage
usage() {
    cat << EOF
Usage: $0 <review_file>

Posts AI code review results as GitHub PR comments.

Arguments:
    review_file    Path to file containing the AI review results

Environment Variables (required):
    GITHUB_TOKEN   GitHub token with pull request write permissions
    PR_NUMBER      Pull request number
    GITHUB_REPOSITORY  Repository in format owner/repo

Environment Variables (optional):
    PR_TITLE       Pull request title
    PR_AUTHOR      Pull request author
    BASE_BRANCH    Base branch name
    HEAD_BRANCH    Head branch name

Examples:
    $0 /tmp/review-results.txt
    GITHUB_TOKEN=\${{secrets.GITHUB_TOKEN}} PR_NUMBER=123 $0 review.txt
EOF
}

# Function to validate environment
validate_environment() {
    local missing_vars=()
    
    if [ -z "$GITHUB_TOKEN" ]; then
        missing_vars+=("GITHUB_TOKEN")
    fi
    
    if [ -z "$PR_NUMBER" ]; then
        missing_vars+=("PR_NUMBER")
    fi
    
    if [ -z "$GITHUB_REPOSITORY" ]; then
        missing_vars+=("GITHUB_REPOSITORY")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "Error: Missing required environment variables: ${missing_vars[*]}" >&2
        echo "" >&2
        usage
        exit 1
    fi
    
    # Validate GitHub CLI is available
    if ! command -v gh &> /dev/null; then
        echo "Error: GitHub CLI (gh) is not installed or not in PATH" >&2
        echo "Please install GitHub CLI: https://cli.github.com/" >&2
        exit 1
    fi
}

# Function to check if review file exists and is readable
validate_review_file() {
    local review_file="$1"
    
    if [ ! -f "$review_file" ]; then
        echo "Error: Review file '$review_file' does not exist" >&2
        exit 1
    fi
    
    if [ ! -r "$review_file" ]; then
        echo "Error: Review file '$review_file' is not readable" >&2
        exit 1
    fi
    
    if [ ! -s "$review_file" ]; then
        echo "Warning: Review file '$review_file' is empty" >&2
        return 1
    fi
    
    return 0
}

# Function to format review content for GitHub comment
format_review_comment() {
    local review_file="$1"
    local review_content
    
    # Read the review content
    review_content=$(cat "$review_file")
    
    # Start building the comment
    local comment_body="$COMMENT_PREFIX

"
    
    # Add PR context if available
    if [ -n "$PR_TITLE" ] || [ -n "$PR_AUTHOR" ] || [ -n "$BASE_BRANCH" ] || [ -n "$HEAD_BRANCH" ]; then
        comment_body+="**Pull Request Context:**
"
        
        if [ -n "$PR_TITLE" ]; then
            comment_body+="- **Title:** $PR_TITLE
"
        fi
        
        if [ -n "$PR_AUTHOR" ]; then
            comment_body+="- **Author:** @$PR_AUTHOR
"
        fi
        
        if [ -n "$BASE_BRANCH" ] && [ -n "$HEAD_BRANCH" ]; then
            comment_body+="- **Branch:** \`$BASE_BRANCH\` ← \`$HEAD_BRANCH\`
"
        fi
        
        comment_body+="
"
    fi
    
    # Add the AI review content
    comment_body+="**Review Results:**

$review_content

---
*This review was generated automatically using StreetRace AI. Please use your judgment when addressing the feedback.*"
    
    # Check comment length
    local comment_length=${#comment_body}
    if [ "$comment_length" -gt "$MAX_COMMENT_LENGTH" ]; then
        echo "Warning: Comment length ($comment_length chars) exceeds GitHub limit ($MAX_COMMENT_LENGTH chars)" >&2
        echo "Truncating comment..." >&2
        
        # Truncate content but preserve footer
        local footer="

---
*This review was generated automatically using StreetRace AI. Please use your judgment when addressing the feedback.*
*Note: Review was truncated due to length limits.*"
        
        local available_length=$((MAX_COMMENT_LENGTH - ${#footer}))
        local truncated_body="${comment_body:0:$available_length}"
        comment_body="${truncated_body}${footer}"
    fi
    
    echo "$comment_body"
}

# Function to check if comment already exists
find_existing_comment() {
    local pr_number="$1"
    
    # Look for existing AI review comments
    gh pr view "$pr_number" \
        --json comments \
        --jq '.comments[] | select(.body | startswith("🤖 **AI Code Review")) | .id' \
        2>/dev/null | head -1 || echo ""
}

# Function to post or update comment
post_comment() {
    local pr_number="$1"
    local comment_body="$2"
    
    # Check if there's an existing AI review comment
    local existing_comment_id
    existing_comment_id=$(find_existing_comment "$pr_number")
    
    if [ -n "$existing_comment_id" ]; then
        echo "Updating existing AI review comment (ID: $existing_comment_id)..." >&2
        
        # Update existing comment
        if echo "$comment_body" | gh api \
            "repos/$GITHUB_REPOSITORY/issues/comments/$existing_comment_id" \
            --method PATCH \
            --field body=@- > /dev/null; then
            echo "Successfully updated AI review comment" >&2
        else
            echo "Error: Failed to update existing comment. Creating new comment..." >&2
            # Fall back to creating new comment
            create_new_comment "$pr_number" "$comment_body"
        fi
    else
        echo "Creating new AI review comment..." >&2
        create_new_comment "$pr_number" "$comment_body"
    fi
}

# Function to create new comment
create_new_comment() {
    local pr_number="$1"
    local comment_body="$2"
    
    if echo "$comment_body" | gh pr comment "$pr_number" --body-file -; then
        echo "Successfully posted AI review comment to PR #$pr_number" >&2
    else
        echo "Error: Failed to post comment to PR #$pr_number" >&2
        exit 1
    fi
}

# Main execution
main() {
    # Check arguments
    if [ $# -ne 1 ]; then
        echo "Error: Exactly one argument (review file) is required" >&2
        echo "" >&2
        usage
        exit 1
    fi
    
    local review_file="$1"
    
    # Show help if requested
    if [ "$review_file" = "-h" ] || [ "$review_file" = "--help" ]; then
        usage
        exit 0
    fi
    
    # Validate environment and inputs
    validate_environment
    
    if ! validate_review_file "$review_file"; then
        echo "Creating placeholder comment for empty review..." >&2
        echo "No significant issues found in the code changes." > /tmp/empty-review.txt
        review_file="/tmp/empty-review.txt"
    fi
    
    # Authenticate with GitHub
    echo "Authenticating with GitHub..." >&2
    if ! gh auth status >/dev/null 2>&1; then
        echo "$GITHUB_TOKEN" | gh auth login --with-token
    fi
    
    # Format and post the comment
    local comment_body
    comment_body=$(format_review_comment "$review_file")
    
    echo "Posting review comment to PR #$PR_NUMBER..." >&2
    post_comment "$PR_NUMBER" "$comment_body"
    
    echo "AI code review comment posted successfully!" >&2
}

# Execute main function
main "$@"