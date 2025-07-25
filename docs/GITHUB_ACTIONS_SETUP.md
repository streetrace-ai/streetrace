# GitHub Actions Code Review Setup

This guide explains how to set up the AI-powered code review workflow for your GitHub repository using StreetRace.

## Overview

The GitHub Actions integration provides automated code review for pull requests using AI models. When a PR is opened or updated, the workflow:

1. Extracts the code changes
2. Analyzes them using AI (Anthropic Claude, OpenAI GPT, or Google Gemini)
3. Posts structured feedback as PR comments
4. Handles large diffs and error cases gracefully

## Prerequisites

- GitHub repository with Actions enabled
- StreetRace installed (handled automatically by the workflow)
- AI provider API key (Anthropic, OpenAI, or Google AI)
- Repository administrator access to configure secrets

## Setup Instructions

### 1. Copy Workflow Files

The GitHub Actions workflow has been implemented in this repository. The key files are:

- `.github/workflows/code-review.yml` - Main workflow definition
- `.github/workflows/scripts/extract-diff.sh` - Extracts git diffs  
- `.github/workflows/scripts/post-review-comment.sh` - Posts review comments
- `.github/workflows/scripts/code-review.sh` - Main review orchestration
- `.github/templates/code-review-prompt.md` - AI review prompt template

### 2. Configure Repository Secrets

Go to your repository's **Settings → Secrets and variables → Actions** and add:

#### Required Secrets

At least one AI provider API key:

- `ANTHROPIC_API_KEY` - For Claude models (recommended)
- `OPENAI_API_KEY` - For GPT models  
- `GOOGLE_AI_API_KEY` - For Gemini models

#### Optional Secrets

- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

### 3. API Key Setup

#### Anthropic Claude (Recommended)
```bash
# Get API key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-api03-...
```

#### OpenAI GPT
```bash
# Get API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...
```

#### Google AI
```bash
# Get API key from: https://aistudio.google.com/app/apikey
GOOGLE_AI_API_KEY=...
```

### 4. Workflow Configuration

The workflow automatically:

- Triggers on PR open/synchronize events
- Skips documentation-only changes
- Excludes dependabot PRs
- Handles diff size limits (100KB max)
- Posts or updates review comments

### 5. Custom Configuration (Optional)

Modify `.streetrace/github-review-config.yaml` to customize:

- File inclusion/exclusion patterns
- Review focus areas (security, performance, etc.)
- AI model preferences
- Comment behavior
- Size limits and thresholds

## Usage

### Automatic Reviews

Once configured, the workflow runs automatically on:
- New pull requests
- Pull request updates (pushes to PR branch)

### Manual Testing

Test the workflow locally:

```bash
# Test diff extraction  
./.github/workflows/scripts/extract-diff.sh --staged

# Test with code review script
./.github/workflows/scripts/code-review.sh
```

## Workflow Behavior

### Normal Operation

1. **Trigger**: PR opened/updated
2. **Extract**: Get code changes using git diff
3. **Filter**: Apply file pattern filters
4. **Validate**: Check diff size limits
5. **Review**: Send to AI model for analysis
6. **Comment**: Post structured feedback

### Large Diff Handling

For diffs > 100KB:
- Skips AI review to avoid excessive token usage
- Posts informational comment with alternatives
- Suggests breaking PR into smaller changes

### Error Handling

- API failures: Graceful error messages
- Missing configuration: Clear validation errors
- Network issues: Retry logic with backoff

## Comment Format

AI reviews are posted as structured comments with:

- **Summary**: Overview of changes
- **Critical Issues**: Security vulnerabilities, breaking changes
- **High Priority**: Performance problems, major quality issues
- **Medium Priority**: Code improvements, style issues  
- **Low Priority**: Minor optimizations, documentation
- **Positive Feedback**: Well-implemented features
- **Recommendations**: Overall assessment and next steps

## Troubleshooting

### Common Issues

#### Workflow Not Triggering
```yaml
# Check .github/workflows/code-review.yml triggers:
on:
  pull_request:
    types: [opened, synchronize]
```

#### API Key Not Working
```bash
# Test API key locally:
export ANTHROPIC_API_KEY=your-key
poetry run streetrace --model=anthropic/claude-3-5-sonnet-20241022 --prompt="Hello"
```

#### Permission Errors
```yaml
# Ensure workflow has proper permissions:
permissions:
  contents: read
  pull-requests: write
```

#### Large Diff Skipped
- Break PR into smaller, focused changes
- Run local review: `./.github/workflows/scripts/code-review.sh`
- Increase size limit in configuration (not recommended)

### Debug Mode

Enable debug mode in `.streetrace/github-review-config.yaml`:

```yaml
advanced:
  debug:
    enabled: true
    log_level: "debug"
    save_artifacts: true
```

## Cost Considerations

### Model Costs (Approximate)

- **Claude 3.5 Sonnet**: $3-15 per 1M tokens
- **GPT-4o**: $2.50-10 per 1M tokens  
- **GPT-4o-mini**: $0.15-0.60 per 1M tokens
- **Gemini 1.5**: $1.25-5 per 1M tokens

### Typical Usage

- Small PR (5-10 files): ~2,000-5,000 tokens ($0.01-0.05)
- Medium PR (10-20 files): ~5,000-15,000 tokens ($0.05-0.15)
- Large PR (20+ files): Often skipped due to size limits

### Cost Optimization

1. **Use cheaper models**: GPT-4o-mini for less critical reviews
2. **Filter files**: Exclude documentation, generated code
3. **Size limits**: Prevent excessive token usage
4. **Skip conditions**: Exclude dependabot, draft PRs

## Security Considerations

### API Key Security
- Store keys in GitHub repository secrets
- Never commit keys to code
- Use least-privilege API keys
- Rotate keys regularly

### Review Accuracy
- AI reviews are supplementary to human review
- Critical changes should have manual review
- Use AI feedback as guidance, not absolute truth
- Maintain coding standards and security practices

### Data Privacy
- PR content is sent to AI providers
- Ensure compliance with organization policies
- Consider self-hosted models for sensitive code
- Review AI provider data handling policies

## Integration Examples

### Branch Protection Rules

Require human review in addition to AI review:

```yaml
# In repository settings:
branch_protection_rules:
  main:
    required_reviews: 1
    dismiss_stale_reviews: true
    require_code_owner_reviews: true
```

### Custom Labels

Auto-label PRs based on review results:

```yaml
# In .streetrace/github-review-config.yaml:
integrations:
  github:
    add_labels: true
    label_mapping:
      critical_issues: "needs-security-review"
      performance_issues: "performance"
      quality_issues: "code-quality"
```

### Slack Notifications

Notify team of critical issues:

```yaml
# In .streetrace/github-review-config.yaml:
integrations:
  slack:
    enabled: true
    webhook_url: "your-webhook-url"
    channels:
      critical: "#security-alerts"
```

## Best Practices

### PR Guidelines
- Keep PRs focused and reasonably sized
- Write clear PR descriptions
- Address critical issues before merging
- Use AI feedback to improve code quality

### Team Adoption
- Start with non-critical repositories
- Train team on interpreting AI feedback
- Establish guidelines for addressing issues
- Regular review of AI feedback quality

### Configuration Management
- Version control configuration files
- Test changes in staging environment
- Document custom configurations
- Regular review of filter patterns

## Support and Updates

### Getting Help
- Check workflow logs in Actions tab
- Review validation script output
- Test locally with review scripts
- Consult StreetRace documentation

### Keeping Updated
- Monitor for workflow updates
- Update StreetRace version regularly
- Review AI model improvements
- Adjust configuration as needed

### Contributing
- Report issues with specific examples
- Suggest improvements to prompts
- Share successful configurations
- Contribute bug fixes and enhancements

---

For more information, see:
- [StreetRace Documentation](../README.md)
- [GitHub Workflow Scripts](../.github/workflows/scripts/)
- [Configuration Reference](../.streetrace/github-review-config.yaml)