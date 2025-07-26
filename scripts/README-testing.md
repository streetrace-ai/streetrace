# AI Code Review Testing Scripts

These scripts allow you to test the AI code review workflow locally before committing and pushing to GitHub.

## Prerequisites

1. **API Key**: Set one of these environment variables:

   **Option A - Environment Variables:**
   ```bash
   export OPENAI_API_KEY="your-key-here"
   # OR
   export ANTHROPIC_API_KEY="your-key-here"  
   # OR
   export GOOGLE_AI_API_KEY="your-key-here"
   ```

   **Option B - .env File (Recommended):**
   Create a `.env` file in the project root:
   ```bash
   # .env file
   OPENAI_API_KEY=your-key-here
   ANTHROPIC_API_KEY=your-other-key
   STREETRACE_MODEL=openai/gpt-4o-mini
   ```
   
   The scripts will automatically load variables from `.env` if it exists.

2. **Dependencies**: Install project dependencies:
   ```bash
   poetry install
   ```

3. **Changes to Review**: Make sure you have changes to review:
   - Staged changes (`git add` some files)
   - Commits on current branch different from `main`
   - Or be on a feature branch with changes

## Testing Scripts

### 1. Full Test (`test-code-review-local.sh`)
Comprehensive test that simulates the complete GitHub Actions workflow:

```bash
./scripts/test-code-review-local.sh
```

**Features:**
- Checks all prerequisites
- Simulates GitHub Actions environment variables
- Runs the complete code review workflow
- Shows detailed results and file locations
- Displays summary like GitHub Actions would

### 2. Quick Test (`test-simple-review.sh`)
Minimal test for quick validation:

```bash
./scripts/test-simple-review.sh
```

**Features:**
- Basic prerequisite checks
- Runs core code review functionality
- Shows generated files
- Fast execution

## What Gets Tested

Both scripts test the same workflow as `.github/workflows/code-review.yml`:

1. **Structured Diff Generation**: Creates JSON representation of changes
2. **AI Code Review**: Runs StreetRace with code reviewer agent
3. **JSON Validation**: Validates AI-generated review JSON
4. **SARIF Generation**: Converts review to GitHub-compatible SARIF format
5. **File Generation**: Creates all output files (JSON, Markdown, SARIF)

## Output Files

The scripts generate files in the `code-reviews/` directory:

- `YYYYMMDD_HHMMSS_structured.json` - Structured diff data
- `YYYYMMDD_HHMMSS.json` - AI review results (JSON format)
- `YYYYMMDD_HHMMSS.md` - AI review report (Markdown format)  
- `YYYYMMDD_HHMMSS_sarif.json` - SARIF format for GitHub integration

## Troubleshooting

### "No changes found to review"
- Make some changes: `echo "# test" >> test.md && git add test.md`
- Or switch to a feature branch with changes
- Or create a test commit

### "No API key found"
- **Option 1**: Set environment variable: `export OPENAI_API_KEY=your-key-here`
- **Option 2**: Create `.env` file in project root:
  ```
  OPENAI_API_KEY=your-key-here
  ```
- The scripts automatically load `.env` files, so this is the easiest approach

### "JSON validation failed"
- This tests our recent fix for write_json tool
- Check the full error message (should now be visible)
- AI should self-correct based on detailed error feedback

### "No SARIF annotations"
- Check if JSON review file was generated successfully
- Verify SARIF file exists and has content
- Review the summary output for debugging info

## Integration with Development

1. **Before Committing**: Run quick test to verify workflow works
2. **Before Pushing**: Run full test to simulate GitHub Actions
3. **Debugging Issues**: Use full test to see detailed output
4. **Validating Fixes**: Test specific issues locally before PR

## Example Usage

```bash
# Make some changes
echo "console.log('test')" > test.js
git add test.js

# Test the review workflow
./scripts/test-simple-review.sh

# Check generated files
ls -la code-reviews/

# Review the markdown report
cat code-reviews/20250726_***.md
```

This allows you to iterate quickly on the AI code review workflow without waiting for GitHub Actions to run.