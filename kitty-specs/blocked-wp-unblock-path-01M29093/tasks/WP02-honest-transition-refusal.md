---
work_package_id: WP02
title: 'F-51: honest single-stage transition refusal that names legal targets'
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
planning_base_branch: fix/3937-blocked-wp-unblock
merge_target_branch: fix/3937-blocked-wp-unblock
branch_strategy: Planning artifacts for this mission were generated on fix/3937-blocked-wp-unblock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3937-blocked-wp-unblock unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-blocked-wp-unblock-path-01M29093
base_commit: 7bd851ef08f91899137ece603011e410b9e5ea72
created_at: '2026-09-11T20:09:59.008175+00:00'
subtasks:
- T005
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_transition_core.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_blocked_recovery_refusal.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/status/work_package_lifecycle.py
- tests/status/test_transitions.py
- tests/specify_cli/cli/commands/agent/test_blocked_recovery_refusal.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#3937'
---

# WP02: F-51 — honest single-stage transition refusal

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` (alias for `spk-doctrine-profile-load`) BEFORE reading the rest of this prompt.

- Profile: `python-pedro`
- Role: `implementer`
- Agent/tool: `claude`

Load the resolver-backed profile + action context, apply its initialization, directives, tactics, and the reviewer-handoff boundary. If structured governance is empty, disclose it and read the binding charter/profile sources explicitly.

## Objective

`spec-kitty ... move-task WP## --to planned` on a non-review-family lane (e.g. `blocked`) must be refused as an **illegal transition** that enumerates the legal targets — NOT gated behind a demand for `--review-feedback-file` that forces a fabricated review finding. And the "cannot start implementation" reject must name the legal recovery command. This closes finding F-51 of #3937.

## Root cause (verified)

`src/specify_cli/cli/commands/agent/tasks_transition_core.py`: `_guard_planned_rollback` (~:561-575) keys ONLY on `target == PLANNED` (source-blind) and demands `--review-feedback-file` ("cannot be bypassed with --force", msg ~:571) BEFORE any FSM legality check. FSM legality is only reached later (`transition_pipeline.py:288` / `wp_state.py:176/181`). So a `blocked → planned` request (illegal per `BlockedState.allowed_targets = {in_progress, canceled}`) gets the wrong error first, and only after supplying a fake feedback file does it report "Illegal transition". The illegal-edge message never enumerates the legal targets. Separately, `work_package_lifecycle.py:256` ("WP … is in '{lane}', cannot start implementation") names no recovery.

## Binding guardrails (from the review squad — do NOT violate)
- **NFR-002 / C-006**: Do NOT modify the machine-readable illegal-transition string at `wp_state.py:176/181` — it is asserted verbatim by ~1500 rows of `tests/status/fsm_parity_baseline.jsonl`. Surface `allowed_targets()` enumeration ONLY on the CLI/emit refusal path.
- **C-002**: Fix the ordering by a SOURCE-LANE-SCOPED EARLY-RETURN inside `_guard_planned_rollback`, NOT by reordering the `_GUARDS` tuple (~:675-687) — reordering shifts the persist-signal prefixes at ~:716/:733.

## Subtasks

### T005 — RED-first ATDD (new file `tests/specify_cli/cli/commands/agent/test_blocked_recovery_refusal.py`)
Assert observable STATE / refusal IDENTITY, not message substrings:
- `blocked → planned` with no feedback → refusal is an **illegal-transition** refusal (its identity/type, e.g. the refusal reason/exit path), and the message enumerates the legal targets `{in_progress, canceled}`; it does NOT demand `--review-feedback-file`.
- `blocked → planned` WITH a `--review-feedback-file` supplied → verdict UNCHANGED (still refused as illegal) — a review artifact cannot launder an illegal transition.
- Regression: a review-family rollback (e.g. `in_review → planned`) with NO feedback → the review-feedback requirement STILL applies (unchanged).
- FR-007: attempting to start implementation on a `blocked` WP → the "cannot start implementation" message names the legal recovery command.
- Add/extend targeted rows in `tests/status/test_transitions.py` for the legal-target enumeration on the refusal path (without changing the FSM-core string or fsm_parity fixtures).
- All RED against current code; committed as the FIRST commit of the lane (C-011).

### T006 — Implement source-lane-scoped early-return
- In `_guard_planned_rollback`, early-return `None` (no refusal) when the SOURCE lane (`req.old_lane`, ~:109) is not a review-family lane, so `blocked → planned` falls through to FSM legality. Keep the demand exactly as-is for genuine review-family rollbacks (regression must pass). Do not reorder `_GUARDS`.

### T007 — Enumerate legal targets on the refusal path + name recovery
- On the CLI/emit illegal-transition refusal path, enrich the operator-facing message to enumerate the current state's `allowed_targets()` (sourced from the authoritative per-state object — no second matrix). Do NOT touch `wp_state.py:176/181`.
- In `work_package_lifecycle.py:256`, extend the "cannot start implementation" message to name the legal recovery command for the current lane.

### T008 — Validate
- `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_blocked_recovery_refusal.py tests/status/test_transitions.py tests/agent/test_workflow_feedback_pointer_2x_unit.py tests/agent/test_review_feedback_pointer_2x_unit.py tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py -q`
- Prove `tests/status/fsm_parity_baseline.jsonl` is byte-unchanged (`git diff --exit-code tests/status/fsm_parity_baseline.jsonl`).
- `.venv/bin/mypy --strict` on changed modules + `.venv/bin/ruff check` + `.venv/bin/ruff format --check` — zero new issues, no new suppressions.

## Definition of Done
- FR-004/005/006/007 satisfied; T005 RED-first then GREEN; refusal identity is illegal-transition (not feedback-demand); fake feedback cannot flip the verdict; review-family rollback regression intact; start-impl reject names recovery; `fsm_parity_baseline.jsonl` unchanged; targeted tests + mypy + ruff green.
- No `_GUARDS` reorder (C-002); no FSM-core string change (NFR-002); no recovery driver (C-001).

## Reviewer guidance (reviewer-renata)
- Verify the tests pin the refusal IDENTITY and that supplying feedback does not change it — not a message substring.
- Confirm `git diff` shows zero change to `fsm_parity_baseline.jsonl` and no reordering of `_GUARDS`.
- Confirm the enumeration is sourced from the authoritative `allowed_targets()` (single canonical authority), and red→green holds.
