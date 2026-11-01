---
title: Linting Cutoff Policy
description: How the CI Quality workflow applies commitlint and markdownlint only to commits and files after the 2026-02-25 cutoff, so legacy history is not retroactively failed.
doc_status: active
updated: '2026-02-25T00:00:00Z'
kind: Reference
---
# Linting Cutoff Policy

## Overview

The CI Quality workflow includes linting checks for commit messages (commitlint) and markdown files (markdownlint). These checks were introduced to maintain code quality going forward, but they run in **informational mode** rather than blocking mode.

## Cutoff Date

**Cutoff Date: 2026-02-25T00:00:00Z**

This date corresponds to when the linting infrastructure was introduced into the codebase.

## Behavior

### Commit Message Linting (commitlint)

- Only commits created **after** the cutoff date are checked
- Commits before the cutoff date are ignored
- Non-compliant commits trigger a PR comment but do not fail the workflow

### Markdown Linting (markdownlint)

- Only markdown files last modified **after** the cutoff date are checked
- Files last modified before the cutoff date are ignored
- Non-compliant files trigger a PR comment but do not fail the workflow

## Workflow Integration

When linting failures are detected on a pull request:

1. The linting steps complete with `continue-on-error: true`
2. A PR comment is posted with:
   - List of non-compliant commits (with commit hash and message)
   - List of non-compliant markdown files
   - A note that these are informational warnings
3. The workflow continues and does not fail due to linting issues

## Non-Blocking Checks

The following checks remain **blocking** (will fail the workflow):
- Unit tests
- Integration tests
- Python linting (ruff)
- Type checking (mypy)
- Security scans (bandit, pip-audit)

The following checks are **informational** (will not fail the workflow):
- Commit message linting (commitlint)
- Markdown style linting (markdownlint)

## Updating the Cutoff Date

If you need to update the cutoff date:

1. Edit `.github/workflows/ci-quality.yml`
2. Find the "Determine commit range and cutoff date" step
3. Update the `CUTOFF_DATE` variable
4. Commit and push the change

```yaml
- name: Determine commit range and cutoff date
  id: commit_range
  run: |
    # Set cutoff date for linting (when linting was introduced)
    CUTOFF_DATE="2026-02-25T00:00:00Z"  # <-- Update this line
    echo "cutoff_date=$CUTOFF_DATE" >> "$GITHUB_OUTPUT"
```

## Rationale

This approach allows the project to:

1. **Avoid blocking existing work**: Historical commits and files are not affected
2. **Encourage best practices**: New commits and files are checked
3. **Provide visibility**: Developers are informed of issues without workflow failures
4. **Maintain flexibility**: The cutoff date can be adjusted as needed
5. **Preserve workflow structure**: The tiered workflow (lint → tests → sonar) remains intact

## Best Practices

While linting failures are informational, developers should still:

1. Follow conventional commit message format for new commits
2. Ensure markdown files follow the project's style guide
3. Address linting issues when convenient
4. Review PR comments for guidance on compliance
