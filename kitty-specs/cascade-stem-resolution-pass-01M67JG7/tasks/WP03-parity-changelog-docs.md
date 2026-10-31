---
work_package_id: WP03
title: Behaviour parity, changelog and docs (#6777)
dependencies:
- WP01
- WP02
requirement_refs:
- FR-003
- FR-007
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-6777-cascade-stem-resolution-pass
merge_target_branch: issue-6777-cascade-stem-resolution-pass
branch_strategy: Planning artifacts for this mission were generated on issue-6777-cascade-stem-resolution-pass. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6777-cascade-stem-resolution-pass unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cascade-stem-resolution-pass-01M67JG7
base_commit: 6bbbb6b7b4dc0b8b3767d0d5992d704cc1e03b43
created_at: '2026-10-31T00:54:31.761072+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 3 - Parity and record
history: []
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/testing/testing-flakiness.md
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Behaviour parity, changelog and docs

## Objective

Prove the speedup changed no stored behaviour, then record the operator-visible cost
change where operators and maintainers will look.

## Context

* `tests/charter/activation/test_stored_spelling_6527.py` — the case's own stored-list
  assertions are the same-fixture positive control.
* `docs/changelog/CHANGELOG.md` — `[Unreleased]`, bold impact-first lead with `(#6777)`,
  before/after, under 1,200 characters (root `CHANGELOG.md` is a symlink to it).
* Docs surface describing the cascade command, if it states a cost.

## Definition of Done

* T008 the whole module passes under the default 240 s timeout, `--durations` recorded.
* T009 `tests/charter/activation/` neighbours stay green.
* T010 changelog entry present and within budget.
* T011 docs freshness verified for whatever the diff touches.
