#!/bin/bash
# Quick test for AI code review - minimal version
# Usage: ./scripts/test-simple-review.sh

set -e

# Basic setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Testing AI Code Review locally..."

# Check prerequisites
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    echo "❌ Not in StreetRace project root"
    exit 1
fi

# Load environment variables from .env if it exists
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo "📄 Loading environment variables from .env"
    # Export variables from .env file
    set -o allexport
    source "$PROJECT_ROOT/.env"
    set +o allexport
fi

if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" && -z "$GOOGLE_AI_API_KEY" ]]; then
    echo "❌ No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY"
    echo "💡 You can create a .env file in the project root with: OPENAI_API_KEY=your_key_here"
    exit 1
fi

# Set up minimal environment
export GITHUB_ENV=$(mktemp)
export PR_NUMBER="local-test"
export BASE_BRANCH="main"

cd "$PROJECT_ROOT"

# Run the review
echo "🔍 Running code review..."
python3 ./.github/workflows/scripts/code_review.py

# Show results
echo "📊 Results:"
if [[ -f "$GITHUB_ENV" ]]; then
    grep "REVIEW_.*_FILE=" "$GITHUB_ENV" | while read -r line; do
        file_path="${line#*=}"
        if [[ -f "$file_path" ]]; then
            echo "✅ Generated: $file_path"
        else
            echo "❌ Missing: $file_path"
        fi
    done
fi

# Cleanup
rm -f "$GITHUB_ENV"

echo "✅ Test completed!"