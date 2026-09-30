---
title: CI Coverage Gate — Tuning Notes
description: 'Tuning notes for the split CI coverage gate introduced by mission 062 (WP07): how the project-wide and new-code coverage thresholds were calibrated.'
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# CI Coverage Gate — Tuning Notes

> **Superseded.** Tuning notes for the mission-062 coverage gate in the old `ci-quality.yml`. Per-PR coverage is now the diff-cover ≥90% gate in `ci-aggregate.yml`; see [CI gate mechanics](../../development/reference/ci-gate-mechanics.md). Kept as a record. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

## Context

Mission 062 (WP07) introduced a split CI quality gate:

- **Enforced gate**: 90% diff-coverage on critical-path files (status model,
  mission detection, dashboard API handlers)
- **Advisory report**: Full diff-coverage report with no enforced minimum

Configuration: `.github/workflows/ci-quality.yml`

## Tuning Guidance

Monitor the 90% critical-path gate over several CI runs after merging
`feature/agent-profile-implementation-rebased`. Adjust if needed:

### If the gate is too brittle (false failures)

- A file in the critical-path list may have legitimately untestable lines
  (e.g., platform-specific branches, defensive `except` blocks).
- **Fix**: Add `# pragma: no cover` to genuinely untestable lines, or remove
  the file from the critical-path list and add a comment explaining why.
- Do NOT lower the 90% threshold — instead narrow the file list.

### If the gate is too lenient (misses regressions)

- New critical modules may be added without being included in the critical-path
  file list.
- **Fix**: Add new critical files to the `--include` list in `ci-quality.yml`
  when they are introduced.
- Consider a periodic audit (e.g., quarterly) of the critical-path file list.

### Critical-path file list (as of WP07)

See the `diff-cover` step in `.github/workflows/ci-quality.yml` for the
authoritative list. At time of writing it covers:

- `src/specify_cli/status/` — status model
- `src/specify_cli/lanes/branch_naming.py` — branch-based mission-slug detection
- `src/specify_cli/dashboard/handlers/` — dashboard API handlers

### Related

- Mission 062 spec: `kitty-specs/062-fix-doctrine-migration-test-failures/spec.md`
- WP07 implementation: `WP07-targeted-coverage-ci-split.md`
- WP08 architectural review: `kitty-specs/062-fix-doctrine-migration-test-failures/review.md`
