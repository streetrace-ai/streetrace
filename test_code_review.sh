#!/bin/bash
set -e

echo "🧪 Testing Holistic Diff-Based Code Review Implementation"
echo "======================================================"

# Set up environment variables similar to GitHub Actions
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export GOOGLE_AI_API_KEY="${GOOGLE_AI_API_KEY:-}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-dummy_token}"
export PR_NUMBER="67"
export PR_TITLE="feat: #60: Implement holistic diff-based code review"
export PR_AUTHOR="test_user"
export BASE_BRANCH="main"
export HEAD_BRANCH="feature/60-holistic-diff-review"
export STREETRACE_MODEL="openai/gpt-4o"

# Create a mock GitHub environment file
export GITHUB_ENV="/tmp/github_env_test"
echo "" > "$GITHUB_ENV"

echo "📋 Environment Setup:"
echo "  - Model: $STREETRACE_MODEL"
echo "  - Base Branch: $BASE_BRANCH"
echo "  - Head Branch: $HEAD_BRANCH"
echo "  - GitHub Env File: $GITHUB_ENV"
echo ""

# Check if we have API keys
if [[ -z "$OPENAI_API_KEY" && -z "$ANTHROPIC_API_KEY" ]]; then
    echo "⚠️  No API keys found. This test will likely fail at the LLM call."
    echo "   Set OPENAI_API_KEY or ANTHROPIC_API_KEY to test with real models."
    echo ""
fi

# Test 1: Check that our scripts exist
echo "🔍 Test 1: Checking script files exist..."
SCRIPTS_DIR=".github/workflows/scripts"

if [[ ! -f "$SCRIPTS_DIR/code_review.py" ]]; then
    echo "❌ Missing: $SCRIPTS_DIR/code_review.py"
    exit 1
fi

if [[ ! -f "$SCRIPTS_DIR/simple_diff_review.py" ]]; then
    echo "❌ Missing: $SCRIPTS_DIR/simple_diff_review.py"
    exit 1
fi

if [[ ! -f "$SCRIPTS_DIR/sarif_generator.py" ]]; then
    echo "❌ Missing: $SCRIPTS_DIR/sarif_generator.py"
    exit 1
fi

echo "✅ All required scripts found"
echo ""

# Test 2: Check Python syntax
echo "🔍 Test 2: Checking Python syntax..."
python3 -m py_compile "$SCRIPTS_DIR/code_review.py"
python3 -m py_compile "$SCRIPTS_DIR/simple_diff_review.py" 
python3 -m py_compile "$SCRIPTS_DIR/sarif_generator.py"
echo "✅ Python syntax validation passed"
echo ""

# Test 3: Test help messages
echo "🔍 Test 3: Testing help messages..."
echo "--- code_review.py --help ---"
python3 "$SCRIPTS_DIR/code_review.py" --help
echo ""

echo "--- simple_diff_review.py --help ---"
python3 "$SCRIPTS_DIR/simple_diff_review.py" --help
echo ""

echo "--- sarif_generator.py --help ---"
python3 "$SCRIPTS_DIR/sarif_generator.py" 2>&1 || true
echo ""

# Test 4: Check if git diff works
echo "🔍 Test 4: Testing git diff generation..."
if git diff main...HEAD > /dev/null 2>&1; then
    echo "✅ Git diff command works"
    DIFF_SIZE=$(git diff main...HEAD | wc -l)
    echo "   Diff size: $DIFF_SIZE lines"
else
    echo "⚠️  Git diff command failed (this might be expected in some environments)"
fi
echo ""

# Test 5: Dry run of the main script (will fail at LLM call but should get there)
echo "🔍 Test 5: Dry run of code review script..."
echo "This will likely fail at the LLM call, but we can check the setup..."
echo ""

# Run with timeout to avoid hanging
timeout 30s python3 "$SCRIPTS_DIR/code_review.py" 2>&1 || {
    EXIT_CODE=$?
    if [[ $EXIT_CODE -eq 124 ]]; then
        echo "⏰ Timeout reached (expected - would hang at LLM call)"
    else
        echo "🔄 Script exited with code $EXIT_CODE"
        echo "   This might be expected if no API keys are provided"
    fi
}
echo ""

# Test 6: Check environment file was created/modified
echo "🔍 Test 6: Checking GitHub environment file..."
if [[ -f "$GITHUB_ENV" ]]; then
    echo "✅ GitHub environment file exists"
    if [[ -s "$GITHUB_ENV" ]]; then
        echo "📄 Contents:"
        cat "$GITHUB_ENV"
    else
        echo "📄 File is empty (expected for failed run)"
    fi
else
    echo "❌ GitHub environment file not found"
fi
echo ""

# Test 7: Validate JSON structure with a mock file
echo "🔍 Test 7: Testing SARIF generator with mock data..."
MOCK_JSON="/tmp/mock_review.json"
cat > "$MOCK_JSON" << 'EOF'
{
  "summary": "Test review of holistic diff-based implementation",
  "issues": [
    {
      "severity": "warning",
      "line": 42,
      "title": "Test Issue",
      "message": "This is a test issue to validate SARIF generation",
      "category": "quality",
      "code_snippet": "test code snippet",
      "file": "test_file.py"
    }
  ],
  "positive_feedback": ["Good test structure"],
  "metadata": {
    "review_focus": "holistic diff analysis",
    "review_type": "diff_based"
  },
  "statistics": {
    "total_issues": 1,
    "errors": 0,
    "warnings": 1,
    "notices": 0,
    "total_review_time_ms": 5000
  }
}
EOF

MOCK_SARIF="/tmp/mock_review.sarif"
python3 "$SCRIPTS_DIR/sarif_generator.py" "$MOCK_JSON" "$MOCK_SARIF"

if [[ -f "$MOCK_SARIF" ]]; then
    echo "✅ SARIF file generated successfully"
    echo "📄 SARIF file size: $(wc -c < "$MOCK_SARIF") bytes"
    
    # Validate it's valid JSON
    if python3 -m json.tool "$MOCK_SARIF" > /dev/null 2>&1; then
        echo "✅ SARIF file is valid JSON"
    else
        echo "❌ SARIF file is not valid JSON"
        exit 1
    fi
else
    echo "❌ SARIF file was not generated"
    exit 1
fi
echo ""

# Cleanup
rm -f "$MOCK_JSON" "$MOCK_SARIF" "$GITHUB_ENV"

echo "🎉 Test Summary"
echo "==============="
echo "✅ All script files exist and have valid Python syntax"
echo "✅ Help messages work correctly"
echo "✅ SARIF generation works with mock data"
echo "⚠️  Full end-to-end test requires API keys and real git diff"
echo ""
echo "🚀 Ready for GitHub Actions testing!"
echo "   To test with real models, set OPENAI_API_KEY or ANTHROPIC_API_KEY"