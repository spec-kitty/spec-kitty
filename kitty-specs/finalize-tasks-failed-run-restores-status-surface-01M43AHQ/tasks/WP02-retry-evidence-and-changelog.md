---
work_package_id: WP02
title: Retry evidence and changelog
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
planning_base_branch: kitty/fix-5641-finalize-tasks-atomic-status
merge_target_branch: kitty/fix-5641-finalize-tasks-atomic-status
branch_strategy: Planning artifacts for this mission were generated on kitty/fix-5641-finalize-tasks-atomic-status. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/fix-5641-finalize-tasks-atomic-status unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - Evidence and docs
history:
- at: '2026-10-04T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: docs/changelog/
create_intent:
- kitty-specs/finalize-tasks-failed-run-restores-status-surface-01M43AHQ/research/retry-evidence.md
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
- kitty-specs/finalize-tasks-failed-run-restores-status-surface-01M43AHQ/research/retry-evidence.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Retry evidence and changelog

## Objectives & Success Criteria

- `research/retry-evidence.md` records, for `coord` and `lanes`, what a second finalize-tasks does after a failed one, before the fix (on `skupstream/main`) and after it (on this branch): seed commits in history and `planned` events in the log (SC-003).
- A `### Fixed` entry under Unreleased in `docs/changelog/CHANGELOG.md` in house style: bold impact-first lead sentence with the ref, then Before / After in plain language.

## Context & Constraints

- The evidence comes from a recorded run, not a new test (test economy, C-004), unless the retry is still wrong after WP01. In that case, stop and report.
- Write Mission, never feature.

## Subtasks & Detailed Guidance

### Subtask T006 – retry evidence
- Run the exploration harness against the base (`PYTHONPATH` pointing at a base worktree) and against this branch, and record the counts.

### Subtask T007 – changelog
- Add the entry, then run `python -m scripts.docs.check_changelog_style` and `python -m scripts.docs.check_spelling`.

## Review Guidance

- The counts in the evidence match a re-run.

## Activity Log
