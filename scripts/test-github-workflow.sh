#!/bin/bash

# test-github-workflow.sh
# Local testing script for GitHub workflow integration
# This script builds and runs the Docker environment to test StreetRace
# in a GitHub Actions-like environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_IMAGE_NAME="streetrace-github-action"
CONTAINER_NAME="streetrace-test-$(date +%s)"
WORKSPACE_DIR="$(pwd)"

# Function to print colored output
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

# Function to clean up containers
cleanup() {
    print_status "Cleaning up containers..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

# Set up cleanup trap
trap cleanup EXIT

# Function to build Docker image
build_image() {
    print_status "Building Docker image: $DOCKER_IMAGE_NAME"
    docker build -t "$DOCKER_IMAGE_NAME" -f docker/github-action/Dockerfile .
    print_success "Docker image built successfully"
}

# Function to run tests
run_test() {
    local test_name="$1"
    local command="$2"
    
    print_status "Running test: $test_name"
    
    # Run the container with volume mounts and environment variables
    docker run --rm \
        --name "$CONTAINER_NAME" \
        -v "$WORKSPACE_DIR:/github/workspace" \
        -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
        -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
        -e GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
        -e GITHUB_ACTIONS=true \
        -e CI=true \
        -w /github/workspace \
        "$DOCKER_IMAGE_NAME" \
        bash -c "$command"
    
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        print_success "Test '$test_name' passed"
    else
        print_error "Test '$test_name' failed with exit code $exit_code"
        return $exit_code
    fi
}

# Main function
main() {
    print_status "Starting GitHub workflow integration testing"
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if we're in the project root
    if [ ! -f "pyproject.toml" ]; then
        print_error "This script must be run from the project root directory"
        exit 1
    fi
    
    # Build the Docker image
    build_image
    
    # Run basic tests
    print_status "Running basic functionality tests"
    
    # Test 1: Check if StreetRace can be invoked
    run_test "Basic invocation" "poetry install --only=main && poetry run streetrace --help"
    
    # Test 2: Test non-interactive mode with simple prompt
    run_test "Non-interactive mode" "poetry install --only=main && poetry run streetrace --model=test --prompt='Hello, this is a test prompt'"
    
    # Test 3: Test git diff extraction
    if [ -f "scripts/extract-diff.sh" ]; then
        run_test "Git diff extraction" "bash scripts/extract-diff.sh --help"
    else
        print_warning "scripts/extract-diff.sh not found, skipping git diff test"
    fi
    
    # Test 4: Test with environment variables
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        run_test "Environment variables" "env | grep -E '(ANTHROPIC|OPENAI|GOOGLE)_API_KEY' | wc -l"
    else
        print_warning "No API keys found in environment, skipping API key test"
    fi
    
    print_success "All tests completed successfully!"
    print_status "Docker environment is ready for GitHub workflow integration testing"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Local testing script for GitHub workflow integration"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --build-only   Only build the Docker image, don't run tests"
    echo ""
    echo "Environment Variables:"
    echo "  ANTHROPIC_API_KEY  - API key for Anthropic Claude"
    echo "  OPENAI_API_KEY     - API key for OpenAI"
    echo "  GOOGLE_API_KEY     - API key for Google AI"
    echo ""
    echo "Examples:"
    echo "  $0                 # Run all tests"
    echo "  $0 --build-only    # Only build Docker image"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    --build-only)
        build_image
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