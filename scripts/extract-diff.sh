#!/bin/bash
# Extract git diff with line numbers for AI code review

set -euo pipefail

# Configuration
BASE_BRANCH="${BASE_BRANCH:-main}"
OUTPUT_FILE="${1:-/tmp/pr-diff.txt}"

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}[INFO]${NC} Extracting diff from $BASE_BRANCH..."

# Create a detailed diff with full context
{
    echo "# Pull Request Diff"
    echo "Base: $BASE_BRANCH"
    echo "Head: $(git rev-parse --abbrev-ref HEAD)"
    echo "Generated: $(date)"
    echo ""
    
    # Get list of changed files
    echo "## Changed Files"
    git diff --name-status "$BASE_BRANCH...HEAD" | while read -r status file; do
        case $status in
            A) echo "- Added: $file" ;;
            M) echo "- Modified: $file" ;;
            D) echo "- Deleted: $file" ;;
            R*) echo "- Renamed: $file" ;;
        esac
    done
    echo ""
    
    # Get the actual diff with line numbers
    echo "## Detailed Changes"
    echo '```diff'
    git diff "$BASE_BRANCH...HEAD" --unified=5
    echo '```'
    
} > "$OUTPUT_FILE"

echo -e "${GREEN}[SUCCESS]${NC} Diff extracted to: $OUTPUT_FILE"

# Also output some stats
LINES_ADDED=$(git diff "$BASE_BRANCH...HEAD" --numstat | awk '{s+=$1} END {print s}')
LINES_REMOVED=$(git diff "$BASE_BRANCH...HEAD" --numstat | awk '{s+=$2} END {print s}')
FILES_CHANGED=$(git diff "$BASE_BRANCH...HEAD" --name-only | wc -l)

echo -e "${BLUE}[INFO]${NC} Statistics:"
echo "  - Files changed: $FILES_CHANGED"
echo "  - Lines added: ${LINES_ADDED:-0}"
echo "  - Lines removed: ${LINES_REMOVED:-0}"