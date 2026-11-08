---
work_package_id: WP02
title: Retire the 600 s override and pin the slow tier (#6777)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
planning_base_branch: issue-6777-cascade-stem-resolution-pass
merge_target_branch: issue-6777-cascade-stem-resolution-pass
branch_strategy: Planning artifacts for this mission were generated on issue-6777-cascade-stem-resolution-pass. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6777-cascade-stem-resolution-pass unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cascade-stem-resolution-pass-01M67JG7
base_commit: 69f36ede349147c994a919ccfaf81cd6f6834fb6
created_at: '2026-10-31T00:44:49.666287+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Tier decision
history: []
authoritative_surface: tests/charter/activation/
create_intent: []
execution_mode: code_change
owned_files:
- tests/charter/activation/test_stored_spelling_6527.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Retire the timeout override, pin the slow tier

## Objective

Delete the interim `_CASCADE_TIMEOUT_S = 600` per-case `pytest.mark.timeout` marker that
#6776 added, put the `[cascade]` case on the repository's documented `slow` tier, and pin
both decisions with a collected-mark test so neither can regress silently.

## Context

* `tests/charter/activation/test_stored_spelling_6527.py` — `_CASCADE_TIMEOUT_S` and the
  parametrise marks.
* `pytest.ini` — the single 240 s backstop (#3143); `slow` = "test expected to take
  >30 seconds".
* `.github/workflows/module-tests.yml` — shards select `-m "not performance and not
  stress"`, so `slow` stays in CI. No deselect, skip or xfail may be added.

## Definition of Done

* T005 no `timeout` mark on any case; `cascade` carries `slow`.
* T006 the collected-mark guard fails if an override returns or `slow` disappears.
* T007 the selector citation lives in the guard's docstring.
