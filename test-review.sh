#!/bin/bash
# Test script for code review - loads .env for local testing

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Testing Code Review Locally${NC}"
echo "================================"

# Check if .env file exists and load it
if [ -f ".env" ]; then
    echo -e "${BLUE}[INFO]${NC} Loading environment variables from .env"
    set -a  # automatically export all variables
    source .env
    set +a  # stop auto-exporting
else
    echo -e "${YELLOW}[WARNING]${NC} No .env file found. Make sure API keys are set in environment."
fi

# Check for required API key
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo -e "${RED}[ERROR]${NC} No OpenAI API key found. Please set OPENAI_API_KEY"
    echo -e "${BLUE}[INFO]${NC} You can create a .env file with: OPENAI_API_KEY=your_key_here"
    exit 1
fi

# Set default model if not specified
export STREETRACE_MODEL="${STREETRACE_MODEL:-openai/gpt-4o}"

echo -e "${BLUE}[INFO]${NC} Using model: ${STREETRACE_MODEL}"

# Run the code review
echo -e "${BLUE}[INFO]${NC} Running code review..."
python3 ./.github/workflows/scripts/code-review.py

echo -e "${GREEN}[SUCCESS]${NC} Test completed!"