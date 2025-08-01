# PR #60 Implementation Plan: Holistic Diff-Based Code Review

## **What Has Been Implemented in This PR**

This PR implements a **comprehensive, production-ready automated code review system** that integrates StreetRace with GitHub Actions. The current implementation uses a **per-file review architecture** where each changed file is reviewed individually with full context.

### **Complete Implementation Summary**

#### **1. GitHub Actions Workflow Integration**
- **File**: `.github/workflows/code-review.yml`
- **Purpose**: Main orchestrator triggering on PR creation
- **Features**:
  - Runs on `ubuntu-latest` with Python 3.12 and Poetry setup
  - Triggers only on PR `opened` events (skips dependabot PRs)
  - Comprehensive environment variables (API keys, PR metadata)
  - Uses `openai/gpt-4o` as default model
  - Generates both JSON reviews and SARIF security reports
  - Creates GitHub job summaries with review statistics
  - Archives all results as workflow artifacts

#### **2. Core Review Scripts** (`.github/workflows/scripts/`)
- **`code_review.py`** - Main orchestrator and entry point
  - Environment setup and prerequisite validation
  - Git repository state checking
  - Orchestrates the per-file review process
  - Manages output file paths and GitHub environment variables

- **`per_file_code_review.py`** - Core review engine (579 lines)
  - `FileReviewer` class: Handles individual file reviews with old/new content comparison
  - `PerFileCodeReviewer` class: Main orchestrator for complete review process
  - File prioritization (security-critical files first)
  - Line-numbered content processing for accurate issue reporting
  - Individual JSON output per file with aggregation
  - Comprehensive error handling and timeout management

- **`per_file_sarif_generator.py`** - Security report generator
  - Converts review JSON to GitHub-compatible SARIF format
  - Maps custom severity levels to SARIF standards
  - Generates unique rule IDs and fingerprints for deduplication
  - Filters out internal "Review Failed" issues

- **`generate_summary.py`** - GitHub job summary generator
  - Creates human-readable summaries for GitHub Actions UI
  - Markdown-formatted statistics and issue counts

- **`utils.py`** - Shared utilities
  - Colored terminal output for debugging
  - Language detection mappings for file types
  - JSON cleanup patterns for file management

#### **3. StreetRace Code Reviewer Agent** (`src/streetrace/agents/code_reviewer/`)
- **`agent.py`** - Specialized StreetRace agent implementation
  - Reviews ALL file types without filtering (Python, shell, YAML, JSON, Markdown, Docker, etc.)
  - Security-first approach with explicit vulnerability patterns
  - Structured JSON output via enhanced `write_json` tool
  - File-specific review expertise
  - Mandatory immediate execution (no planning phase)
- **Supporting files**: `__init__.py`, comprehensive `README.md`

#### **4. Review Infrastructure**
- **Template**: `.github/workflows/templates/per-file-review-prompt.md`
  - Standardized prompt template for individual file reviews
  - Security vulnerability examples with code patterns
  - Exact JSON output format specification
  - Line numbering instructions for accurate issue reporting

- **Enhanced Tools**: 
  - `write_json` tool with validation (`src/streetrace/tools/definitions/write_json.py`)
  - Integration into `fs_tool.py` for agent access

### **Current Workflow Process**
1. **PR Trigger**: GitHub Actions starts on PR opened
2. **Environment Setup**: Install Poetry, StreetRace, configure APIs
3. **File Discovery**: Git diff analysis to find changed files vs main branch
4. **File Prioritization**: Security files → Tests → Core code → Config files
5. **Per-File Review Loop**:
   - Extract old/new content with line numbers
   - Generate file-specific prompt using template
   - Execute StreetRace Code Reviewer Agent
   - Agent uses `write_json` tool for structured output
   - Parse and validate JSON results
6. **Aggregation**: Combine individual file reviews into final JSON
7. **SARIF Generation**: Convert to GitHub security format
8. **Report Generation**: Create job summary and upload artifacts
9. **Security Integration**: Upload SARIF to GitHub Code Scanning

### **Key Features of Current Implementation**
- **Comprehensive Coverage**: Reviews all file types (not just programming languages)
- **Security-First**: Explicit patterns for SQL injection, command injection, hardcoded secrets, path traversal
- **No Token Limits**: Per-file approach avoids context window issues
- **Production Ready**: Complete error handling, timeouts, cleanup, debugging support
- **GitHub Integration**: SARIF reports, job summaries, artifact archival, Security tab integration
- **Scalability**: Can handle hundreds of files without truncation

### **Output Artifacts Generated**
1. Individual file reviews: `{timestamp}_file_{index:03d}_review.json`
2. Aggregated review: `{timestamp}_per_file_structured.json`
3. SARIF security report: `{timestamp}_per_file_sarif.json`
4. Context files: `{timestamp}_file_{index:03d}_context.md` (debugging)
5. Output logs: `{timestamp}_file_{index:03d}_output.txt` (streaming capture)

**This represents a complete, enterprise-grade automated code review system** that was designed to replace simpler approaches with thorough, file-by-file analysis while maintaining high-quality security detection and full GitHub ecosystem integration.

## **krmrn42's Key Comments:**

1. **Main Review Comment (CHANGES_REQUESTED):**
   > "I think there is no difference in token count consumed if you run `for file in all_changes: streetrace file`, vs `streetrace all_changes`, while the later provides a more holistic review."

2. **Follow-up Clarification:**
   > "We don't need to push all files, only the changes (e.g. git diff format). And then cut the changes to a reasonable length, because if the amount of changes in one PR is large, it's a bad PR. So we are optimizing for bad PRs here :) If the changeset is large, we can log something like 'The diff has been trimmed to fit into the context window, please keep the PRs smaller'."

## **Complete Implementation Plan:**

### **Phase 1: Core Architecture Change (High Priority)**
1. **Replace per-file approach with holistic git diff review**
   - Change from individual file processing to single unified diff
   - Maintain same token efficiency while gaining better context

2. **Implement git diff format processing**
   - Generate unified diff format: `git diff main...HEAD`
   - Parse diff headers, hunks, and change indicators (+/-)
   - Preserve file paths and line numbers for accurate issue reporting

3. **Add intelligent diff trimming for large PRs**
   - Calculate diff size vs context window limits
   - Implement smart truncation that preserves structure
   - Prioritize security-critical files when trimming

4. **Add required warning message**
   - Exact text: *"The diff has been trimmed to fit into the context window, please keep the PRs smaller"*
   - Log when trimming occurs with statistics

### **Phase 2: Component Updates (High Priority)**
5. **Update code review agent**
   - Modify agent to work with unified diff format instead of individual files
   - Update prompt template to handle diff format
   - Ensure security pattern detection works with diff context

6. **Modify workflow scripts**
   - Replace `per_file_code_review.py` logic with diff-based approach
   - Update `code_review.py` orchestrator
   - Simplify file processing pipeline

### **Phase 3: Integration & Testing (Medium Priority)**
7. **Update SARIF generator**
   - Adapt to work with diff-based review output
   - Maintain file path and line number accuracy
   - Preserve security integration

8. **Validate approach**
   - Test that holistic review provides better insights
   - Confirm token efficiency matches per-file approach
   - Verify context window management works correctly

## **Key Benefits of the Change:**
- **Better Context**: See relationships between file changes
- **Simpler Architecture**: Single review call vs complex per-file orchestration
- **Smart Scaling**: Handles both small and large PRs appropriately
- **Quality Focus**: Discourages oversized PRs through trimming warnings

## **Current Architecture Analysis**

The existing implementation is a **comprehensive, production-ready system** with:

### **Major Components Built**
1. **GitHub Actions Workflow** (`.github/workflows/code-review.yml`)
   - Complete CI/CD pipeline with Python/Poetry setup
   - Multi-model support (OpenAI, Anthropic, Google AI)
   - SARIF integration for GitHub Security tab
   - Artifact archival and job summaries

2. **Core Review Scripts** (`.github/workflows/scripts/`)
   - `code_review.py` - Main orchestrator
   - `per_file_code_review.py` - 579-line core engine with FileReviewer class
   - `per_file_sarif_generator.py` - GitHub security integration
   - `generate_summary.py` - Human-readable reporting
   - `utils.py` - Shared utilities and language detection

3. **StreetRace Code Reviewer Agent** (`src/streetrace/agents/code_reviewer/`)
   - Complete specialized agent implementation
   - Security-focused analysis patterns
   - JSON-structured output via enhanced `write_json` tool
   - Support for all file types (not just code)

4. **Supporting Infrastructure**
   - Review prompt template with security vulnerability patterns
   - Enhanced `write_json` tool with validation
   - File prioritization logic (security files first)
   - Line numbering for accurate issue reporting

## **The Fundamental Change Required**

This represents a **fundamental architectural shift** from:
- **Current**: `for file in changed_files: review(file)` 
- **Requested**: `review(git_diff_of_all_changes)`

**The scope of change is significant** - it affects the core review engine, workflow scripts, agent implementation, and output formats, but leverages the existing GitHub Actions infrastructure and StreetRace agent framework.

This represents a **fundamental architectural simplification** that trades the complex per-file infrastructure for a more elegant diff-based approach that provides superior contextual understanding.