#!/bin/bash

# test-code-review.sh
# Local development script to test the GitHub code review workflow

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
WORKFLOW_SCRIPT="$PROJECT_ROOT/.github/workflows/scripts/code-review.sh"

# Help function
show_help() {
    cat << EOF
Local Test Script for GitHub Code Review Workflow

Usage: $0 [OPTIONS]

This script tests the GitHub code review workflow locally before pushing to GitHub.

Options:
  -m, --model MODEL    Specify the model to use (default: openai/gpt-4o-mini)
  -e, --env-file FILE  Load environment variables from a specific file
  -h, --help           Show this help message

Examples:
  $0                                    # Run with default model
  $0 -m anthropic/claude-3-5-sonnet    # Use Claude model
  $0 -e .env.test                      # Use test environment file

Environment Variables:
  OPENAI_API_KEY        - API key for OpenAI
  ANTHROPIC_API_KEY     - API key for Anthropic Claude
  GOOGLE_AI_API_KEY     - API key for Google AI
  STREETRACE_MODEL      - Model to use (can be overridden with -m)
EOF
}

# Default values
MODEL=""
ENV_FILE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main function
main() {
    echo "🧪 Testing GitHub Code Review Workflow Locally"
    echo "=============================================="
    
    # Check if workflow script exists
    if [ ! -f "$WORKFLOW_SCRIPT" ]; then
        print_error "Workflow script not found: $WORKFLOW_SCRIPT"
        exit 1
    fi
    
    # Make sure the workflow script is executable
    chmod +x "$WORKFLOW_SCRIPT"
    
    # Load environment file if specified
    if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
        print_status "Loading environment from: $ENV_FILE"
        set -a
        source "$ENV_FILE"
        set +a
    elif [ -f "$PROJECT_ROOT/.env" ]; then
        print_status "Loading default .env file"
        set -a
        source "$PROJECT_ROOT/.env"
        set +a
    fi
    
    # Set model if specified
    if [ -n "$MODEL" ]; then
        export STREETRACE_MODEL="$MODEL"
        print_status "Using model: $MODEL"
    fi
    
    # Show current configuration
    print_status "Configuration:"
    echo "  Project root: $PROJECT_ROOT"
    echo "  Model: ${STREETRACE_MODEL:-openai/gpt-4o-mini}"
    echo "  Current branch: $(git branch --show-current)"
    
    # Check for API keys
    if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GOOGLE_AI_API_KEY:-}" ]; then
        print_warning "No API key found. The workflow script will prompt for one."
    else
        local keys_found=()
        [ -n "${OPENAI_API_KEY:-}" ] && keys_found+=("OpenAI")
        [ -n "${ANTHROPIC_API_KEY:-}" ] && keys_found+=("Anthropic")
        [ -n "${GOOGLE_AI_API_KEY:-}" ] && keys_found+=("Google AI")
        print_success "API keys found: ${keys_found[*]}"
    fi
    
    echo ""
    print_status "Running the code review workflow..."
    echo "===================================="
    echo ""
    
    # Run the workflow script
    cd "$PROJECT_ROOT"
    if "$WORKFLOW_SCRIPT"; then
        echo ""
        print_success "Code review workflow completed successfully!"
    else
        echo ""
        print_error "Code review workflow failed!"
        exit 1
    fi
}

# Run main function
main