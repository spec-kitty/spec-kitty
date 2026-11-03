---
work_package_id: "WP02"
title: "Operator surface and regression sweep"
dependencies:
  - "WP01"
planning_base_branch: "main"
merge_target_branch: "main"
branch_strategy: "Planning artifacts were generated on the issue branch; completed changes must merge back into main."
owned_files:
  - "docs/changelog/unreleased"
requirement_refs:
  - FR-006
  - FR-007
  - FR-009
subtasks:
  - "T006"
  - "T007"
  - "T008"
  - "T009"
phase: "Phase 2 - Operator surface"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2026-11-02T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP02 – Operator surface and regression sweep

## Objective

Make the first-run refusal read correctly, give the change its changelog fragment, correct any doc
that claims a resume-only guarantee, and prove the `--resume` protection was not weakened.

## Subtasks

### T006 — Refusal routing

The first-run refusal must go through `_late_projection_refusal` (per-kind remedies from #6791:
deletion-cannot-be-expressed, evidence-would-be-lost, unreadable gate document, record-not-landed).
Add a test that the first-run refusal text names the coordination branch, the target ref, the kept
marker/worktree and `spec-kitty consolidate --resume`.

### T007 — Regression sweep

Run and record:

- `uv run pytest tests/consolidation/test_late_teardown_projection.py -q` (the #6857 resume suite;
  no test edited)
- `uv run pytest tests/coordination/test_projection_teardown.py -q`
- `uv run pytest tests/consolidation/test_teardown_refusal_resume.py tests/terminus/test_coord_teardown_cas_branch_delete.py -q`

### T008 — Changelog fragment

`docs/changelog/unreleased/<pr>.fixed.md`, fragment style: bold impact-first lead with the issue
refs, then before/after, under 1,200 characters. Never edit `docs/changelog/CHANGELOG.md`.
Validate with `uv run --frozen python -m scripts.docs.check_changelog_style`.

### T009 — Docs

If a doc page or an ADR states that the late-window projection is a `--resume`-only guarantee,
correct it. Otherwise record the check in the PR body (no page to change).

## Definition of Done

- Fragment present and accepted by the style check.
- The three suites above green, no assertion weakened.
