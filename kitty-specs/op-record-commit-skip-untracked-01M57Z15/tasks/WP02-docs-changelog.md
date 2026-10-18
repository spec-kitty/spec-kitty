---
work_package_id: WP02
title: Docs and changelog
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- C-003
planning_base_branch: issue-6410-op-record-commit-target
merge_target_branch: issue-6410-op-record-commit-target
branch_strategy: Planning artifacts for this mission were generated on issue-6410-op-record-commit-target. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6410-op-record-commit-target unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - Docs
history:
- at: '2026-10-18T17:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/architecture/trail-model.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Docs and changelog

Load the `scribe-sally` profile first.

## Objectives & Success Criteria

- `docs/architecture/trail-model.md` describes the conditional Op-record commit and the skip. It drops the claim that an uncommitted record will not survive a checkout or reset.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` → Fixed entry. It leads with the impact in bold and cites (#6410), followed by **Before:** / **After:** / **What to do:**.
- The docs checks pass: `uv run python -m scripts.docs.check_docs_freshness --ci`, `pytest tests/architectural/test_no_legacy_terminology.py`, and the changelog style guard.

## Subtasks

- **T006.** Update the trail-model section (around lines 160-180).
- **T007.** Add the changelog entry. For `spec-kitty/doc-kitty`-style repositories, mention that gitignoring `kitty-ops/` is now honored.
