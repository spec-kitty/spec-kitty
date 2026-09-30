---
title: CI Quality Workflow Structure
description: Visual overview of the CI Quality workflow structure, showing how linting checks were converted from blocking to informational, with a solution summary.
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# CI Quality Workflow Structure

> **Superseded.** Describes the February 2026 `ci-quality.yml` layout, before the modular CI from #3995 (the lean CI reinstatement). See [CI gate mechanics](../../development/reference/ci-gate-mechanics.md). Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

This document provides a visual overview of the CI Quality workflow structure, showing how linting checks were converted from blocking to informational warnings.

## Solution Summary

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CI QUALITY WORKFLOW - SOLUTION SUMMARY                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────────┐
│ BEFORE (Problematic)                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ • Linting checks ALL commits/files in history                               │
│ • Linting failures BLOCK the entire workflow                                │
│ • No feedback provided to developers                                        │
│ • Old code violations prevent new work from merging                         │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ AFTER (Solution)                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✅ Cutoff Date: 2026-02-25T00:00:00Z                                        │
│    └─ Only commits/files AFTER this date are checked                        │
│                                                                              │
│ ✅ Non-Blocking Linting                                                     │
│    └─ continue-on-error: true prevents workflow failure                     │
│                                                                              │
│ ✅ PR Comments on Failures                                                  │
│    ├─ Lists non-compliant commits (hash + message)                          │
│    ├─ Lists non-compliant markdown files                                    │
│    └─ Informational note about non-blocking nature                          │
│                                                                              │
│ ✅ Tests Still Fail Workflow                                                │
│    └─ ruff, mypy, bandit, pip_audit, unit-tests, integration-tests          │
│                                                                              │
│ ✅ Tiered Workflow Preserved                                                │
│    └─ lint → unit-tests → [cli, sync, dashboard, integration] → sonar       │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ WORKFLOW DIAGRAM                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐                   ┌──────────────┐                            │
│  │   lint   │ (independent)     │  unit-tests  │ (independent)              │
│  └────┬─────┘                   └──────┬───────┘                            │
│       │                                │                                    │
│       │ (non-blocking)                 ├──→ cli-tests (with coverage) ──┐   │
│       │                                ├──→ sync-tests (with coverage) ─┤   │
│       │                                ├──→ dashboard-tests (coverage) ─┤   │
│       │                                ├──→ integration-smoke (coverage)┤   │
│       │                                │                                │   │
│       │                                └────────────────────────────────┼──→│
│       │                                                                  │   │
│       └──→ PR Comment (if failures)                                     ▼   │
│                                                                  sonarcloud  │
│                                                        (merges all coverage) │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ FILTERING LOGIC                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Cutoff: 2026-02-25T00:00:00Z (Unix timestamp: 1771977600)                  │
│                                                                              │
│  For Each Commit:                                                           │
│    commit_timestamp = git show -s --format=%ct $commit                      │
│    if commit_timestamp > cutoff_timestamp:                                  │
│      ✓ CHECK WITH COMMITLINT                                                │
│    else:                                                                     │
│      ✗ SKIP (before cutoff)                                                 │
│                                                                              │
│  For Each Markdown File:                                                    │
│    last_commit_timestamp = git log -1 --format=%ct $file                    │
│    if last_commit_timestamp > cutoff_timestamp:                             │
│      ✓ CHECK WITH MARKDOWNLINT                                              │
│    else:                                                                     │
│      ✗ SKIP (last modified before cutoff)                                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ PR COMMENT EXAMPLE                                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ## ⚠️ Linting Issues Detected                                              │
│                                                                              │
│  The following linting issues were found in files/commits created after     │
│  the cutoff date (2026-02-25):                                              │
│                                                                              │
│  ### 📝 Commit Message Issues                                               │
│                                                                              │
│  The following commits do not follow the conventional commit format:        │
│                                                                              │
│  ```                                                                         │
│  277d6b1 - Initial plan                                                      │
│  ```                                                                         │
│                                                                              │
│  ### 📄 Markdown Style Issues                                               │
│                                                                              │
│  The following markdown files have style issues:                            │
│                                                                              │
│  ```                                                                         │
│  docs/example.md                                                             │
│  README.md                                                                   │
│  ```                                                                         │
│                                                                              │
│  **Note:** These are informational warnings and do not block the workflow.  │
│  Please address these issues when convenient.                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ DOCUMENTATION                                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  📄 docs/development/linting-cutoff-policy.md                               │
│                                                                              │
│  Includes:                                                                   │
│  • Overview and behavior                                                    │
│  • Cutoff date details and rationale                                        │
│  • Workflow integration explanation                                         │
│  • Instructions for updating cutoff date                                    │
│  • List of blocking vs informational checks                                 │
│  • Best practices for developers                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Linting Cutoff Policy](../../configuration/linting-cutoff-policy.md) - Detailed policy and implementation details
- CI Quality Workflow (`.github/workflows/ci-quality.yml`) - deleted per PROGRAM.md §2 / planning#57; this repo runs no GitHub Actions

## Coverage Collection Strategy

All test jobs now produce coverage reports that are merged in the SonarCloud step:

1. **unit-tests**: Produces `coverage.xml` for unit and contract tests
2. **cli-tests**: Produces `coverage-cli.xml` for CLI tests
3. **sync-tests**: Produces `coverage-sync.xml` for sync tests
4. **integration-smoke**: Produces `coverage-integration.xml` for integration/e2e tests
5. **dashboard-tests**: Produces `coverage-dashboard.xml` for dashboard tests

The **sonarcloud** job:
- Depends on all parallel test jobs: `[unit-tests, cli-tests, sync-tests, integration-smoke, dashboard-tests]`
- Runs with `if: always()` to execute even if some tests fail
- Downloads artifacts from all test jobs (using `continue-on-error: true` for optional jobs)
- Merges all coverage reports before uploading to SonarCloud
- Provides comprehensive code coverage metrics across the entire test suite

This ensures SonarCloud has complete visibility into code coverage from all test suites, not just unit tests.

## Key Benefits

1. **Historical Code Protection**: Old commits and files are not affected by new linting rules
2. **Developer Feedback**: Clear, actionable feedback via PR comments
3. **Non-Blocking**: Linting issues don't prevent merging, encouraging gradual improvement
4. **Maintained Quality**: All tests and critical checks still block the workflow
5. **Flexible**: Cutoff date can be updated as the codebase improves
6. **Comprehensive Coverage**: SonarCloud now receives coverage from all test suites
