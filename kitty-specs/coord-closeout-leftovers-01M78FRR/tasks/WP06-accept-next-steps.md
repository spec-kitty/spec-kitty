---
work_package_id: WP06
title: Topology-aware accept Next steps (#7599)
dependencies: []
requirement_refs:
- FR-010
- SC-003
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
phase: Phase 2 - Closeout fixes
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/specify_cli/test_acceptance_next_steps.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/acceptance/__init__.py
- tests/specify_cli/test_acceptance_next_steps.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Topology-aware accept "Next steps" (#7599)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before reading further.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `add-history`.

---

## Objectives & Success Criteria

FR-010 (and fold Decision `01M78G64M6W660HXKA75Y206NT`: key the text on "lanes still to
consolidate", flat lanes too).

Done when:
- Local-mode accept on the integration (target) branch of a coordination Mission (`lanes_with_coord`, `coord`, or a recorded `coordination_branch`) prints a "Next steps" naming the branch the record was committed to (the Mission/coordination branch from `meta.json`) and `spec-kitty consolidate --mission <handle>`; never "No merge needed".
- The same for a flat `lanes` Mission that still has lanes to consolidate.
- A Mission with nothing to consolidate keeps "Acceptance recorded directly on `<branch>`. No merge needed." byte-identical.
- The `pr` and `checklist` arms are unchanged.

## Context & Constraints

- `_build_acceptance_instructions`, `src/specify_cli/acceptance/__init__.py:2030-2109`; the local integration-branch arm `:2071-2073` never reads `lands_by_consolidation` (the `pr` arm does, `:2053-2060`, #6450). Caller `perform_acceptance` (`:2217-2233`) passes `branch = summary.branch or summary.feature`, `is_integration_branch`, `landed_by_consolidate`, `lands_by_consolidation` (`_lands_by_consolidation`, `:2159-2175`). Printed by `cli/commands/accept.py:741-744`.
- "Lanes still to consolidate": a predicate from data already on the summary/result (`AcceptanceSummary.lanes`, `merge_pending_wps` on the result, or `lanes.json` code lanes). Prefer one small helper `_has_lanes_to_consolidate(summary, ...)`; do not add new git reads here.
- Name the record branch from `meta.json` (`coordination_branch` or `mission_branch`), not `branch` (the checkout's branch). PR #7567 commits the record through `commit_for_mission` on the Mission branch.
- **R3 / C-004**: sub-epic C (#7546) may edit this file for the accept path-convention message. Touch only `_build_acceptance_instructions` and the arguments `perform_acceptance` passes to it.
- Existing tests: `tests/specify_cli/test_acceptance_regressions.py:1150-1183` (pr coordination arm + flat control), `tests/acceptance/test_pr_mode_lane_cleanup.py:128-141` (direct calls). No test asserts "No merge needed" today.

## Branch Strategy

Planning base / merge target: `fix/7598-coord-closeout-leftovers`.

```bash
spec-kitty agent action implement WP06 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T022 – Red: local-mode Next steps

- **Steps**:
  1. `tests/specify_cli/test_acceptance_next_steps.py`: direct calls of `_build_acceptance_instructions` (as `test_pr_mode_lane_cleanup.py` does) for: local + integration + coordination Mission; local + integration + flat lanes with lanes to consolidate; local + integration + nothing to consolidate (control); pr + coordination (unchanged).
  2. One end-to-end cell through `spec-kitty accept --mode local` on a coordination Mission fixture if a cheap one exists in `tests/specify_cli/test_acceptance_regressions.py` (reuse its fixture; else skip the e2e and say so in the WP history).
  3. Red: the coordination and flat-lanes cells fail ("No merge needed"). Commit `test(accept): local Next steps point a Mission with lanes to consolidate (#7599, red)`.

### Subtask T023 – Topology-aware local arm

- **Steps**: add the consolidation branch to the local arm, mirroring the pr wording: "Acceptance recorded on `<record branch>`. This Mission lands through `spec-kitty consolidate --mission <handle>`; run it next." Pass the record branch and the lanes-to-consolidate fact from `perform_acceptance`. Keep complexity ≤ 15 (extract a `_local_mode_lines(...)` helper if needed).

### Subtask T024 – Controls stay byte-identical

- **Steps**: assert the nothing-to-consolidate local text and the pr/checklist texts are unchanged against their current strings; run the existing acceptance suites.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/specify_cli/test_acceptance_next_steps.py tests/specify_cli/test_acceptance_regressions.py tests/acceptance/test_pr_mode_lane_cleanup.py
.venv/bin/python -m pytest -q --dist loadfile -n 8 tests/specify_cli/acceptance tests/acceptance
ruff / format --force-exclude / mypy on changed files
```

## Review Guidance

- "No merge needed" appears only when nothing remains to consolidate; the named branch is where the record actually went.

## Progress & Status

Event log only.
