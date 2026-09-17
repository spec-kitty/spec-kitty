---
work_package_id: WP01
title: 'F-51: source-aware move-task --to planned refusal message'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-3937-blocked-planned-refusal-message
merge_target_branch: issue-3937-blocked-planned-refusal-message
branch_strategy: Planning artifacts for this mission were generated on issue-3937-blocked-planned-refusal-message. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3937-blocked-planned-refusal-message unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-blocked-planned-refusal-message-01M2Q4E0
base_commit: fefda36ee40295aa1d75e3167a490e27e30af499
created_at: '2026-09-17T08:35:56.043988+00:00'
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#3937'
---

# WP01: F-51 — source-aware `move-task --to planned` refusal

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` (alias for `spk-doctrine-profile-load`) BEFORE reading the rest of this prompt.

- Profile: `python-pedro`
- Role: `implementer`
- Agent/tool: `claude`

Load the resolver-backed profile + action context, apply its initialization, directives, tactics, and the reviewer-handoff boundary. If structured governance is empty, disclose it and read the binding charter/profile sources explicitly — do not invent activation.

## Objective

Make the refusal emitted by `_guard_planned_rollback` **source-aware** so an
operator trying `move-task <WP> --to planned` gets the *real* recovery path for
the work package's current lane, instead of the misleading "requires review
feedback" that is printed today for every source lane. This closes finding F-51
of issue #3937 (P0/MVP).

**Message-enrichment ONLY.** The guard's allow/deny logic is not changed. Every
`--to planned` move without a valid, non-empty review-feedback file is still
refused — for all source lanes, with and without `--force`. The source lane is
read only to *shape the message*, never to decide *whether* to refuse.

## Root cause (verified on `main` @ ee8e7885ed)

`src/specify_cli/cli/commands/agent/tasks_transition_core.py` —
`_guard_planned_rollback` (~line 561), guard-chain index 6 of `_GUARDS`
(~line 675), runs entirely **before** `build_transition_plan` / the state
machine (`decide_transition`, ~line 800). Its missing-feedback branch emits a
**byte-identical, source-agnostic** message for every source lane and ignores
`--force` (it reads neither `req.old_lane` nor `req.force`). So a `blocked` work
package — whose honest recovery is the one-hop `blocked → in_progress`
(`BlockedState.allowed_targets == {in_progress, canceled}`) — is told to
fabricate a review file.

**Why the guard must stay structurally force-proof:** its "cannot be bypassed
with --force" promise holds *only* because it refuses before the state machine
and never consults the source to decide. If a source lane ever falls through to
`build_transition_plan`, the FSM's force-override (`wp_state.py:177-181`)
accepts the move — and for `done`, backward auto-force-promotion (FR-015,
`tasks_transition_core.py:325-349`; `_is_backward_transition`/`_FORWARD_ORDER`
in `tasks_finalize_validation.py:44-67`) supplies `force=true` **flaglessly**,
resurrecting a merged work package to `planned` with a reason nobody wrote. The
prior attempt (WP02 of `blocked-wp-unblock-path-01M29093`) was cut for exactly
this: it turned the guard into a source-scoped early-return keyed on
`is_run_affecting`. **Do not do that.**

## Design (locked — see `plan.md`, `contracts/planned-rollback-message.md`)

Inside the existing missing-feedback branch, compute:

```
reachable = Lane.PLANNED in wp_state_for(resolve_lane_alias(req.old_lane)).allowed_targets()
```

- `reachable` is **true** (`in_review`, `in_progress`, `approved`, `genesis`):
  return the **existing** review-feedback `RefuseExit1(...)` message verbatim
  (keep the substrings `requires review feedback` and
  `cannot be bypassed with --force`).
- `reachable` is **false** (`blocked`, `canceled`, `done`, `uninitialized`):
  return a `RefuseExit1(...)` that (a) does NOT mention review feedback,
  (b) states `planned` is not reachable from the source lane, (c) names the
  source lane's legal targets from `allowed_targets()` (or says the lane is
  terminal when the set is empty), and (d) for `blocked` names `--to in_progress`
  as the resume path (and may name `--to canceled`).

Both arms end in `return RefuseExit1(...)`. Do **not** add an early `return None`.
Do **not** touch the four feedback-field checks. Do **not** reorder `_GUARDS`.
`wp_state_for`, `Lane`, and `resolve_lane_alias` are already imported/available
in this module (see existing use at ~line 230 and ~line 463).

## Subtasks

### T001 — RED-first regression matrix (write and prove RED before touching the guard)

Extend `tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py`
(reuse the existing `_base_request(**overrides)` factory and `decide_transition`
/ `RefuseExit1`). Add a matrix driving `decide_transition` with
`target_lane="planned"`, `feedback_provided=False`, over source lanes
`{done, canceled, genesis, blocked, in_review}` × `force ∈ {False, True}`.

Assertions (observable outcome, not just substrings):

- Every row → `isinstance(outcome, RefuseExit1)` (the move is refused; lane
  unchanged — the pure core returns a refusal, no emit).
- **blocked** rows: message contains `--to in_progress` and does **not** contain
  `requires review feedback`.
- **canceled / done** rows: message does **not** contain `requires review
  feedback`; message indicates `planned` is not reachable / terminal.
- **genesis / in_review** rows: message contains `requires review feedback`
  (Arm A preserved).
- **done, flagless** (`force=False`) — the FR-015 tripwire: assert the outcome
  is a refusal AND that **no** emit/force-rewind is produced by the pure core
  (there is no `Emit` result and no `force=true` transition). This is the row
  the prior attempt's test never had.
- **Positive control**: `old_lane="in_review"`, valid non-empty feedback file →
  the guard passes (the result is an `Emit`/success to `planned`, exit 0
  semantics). Mirror the existing `test_planned_with_valid_feedback_is_planned_rollback`.
- **Fabricated feedback on blocked**: `old_lane="blocked"` with a non-empty
  feedback file → still refused? NOTE: with valid feedback the guard passes to
  the FSM which rejects `blocked → planned`; assert the observable end state is
  a refusal (no successful move to `planned`). If the pure-core layer cannot
  see the FSM rejection, drive this one case through the CLI/decision path that
  does (see `test_tasks_cli_contract_coord.py` for the pattern) — the invariant
  to pin is "a review artifact cannot launder an illegal `blocked → planned`".

Run the new tests and CONFIRM they FAIL against the current guard (the
blocked/canceled/done message assertions and the no-review-feedback assertions
red). Record the RED output.

### T002 — Implement the source-aware message

Edit `_guard_planned_rollback` in
`src/specify_cli/cli/commands/agent/tasks_transition_core.py` per the Design
above. Keep the four feedback checks and the `_GUARDS` tuple byte-unchanged.
Keep `_guard_planned_rollback`'s cyclomatic complexity ≤ 15 (extract a small
pure helper for the message if needed, e.g. `_planned_rollback_message(old_lane)`
returning the string — the helper must return a string, never drive
proceed/refuse). Hoist any literal used ≥ 3 times to a module constant.

### T003 — Prove green + blast radius + gates

- The full T001 matrix passes.
- Blast-radius set (record commands + counts in the PR):
  `PWHEADLESS=1 .venv/bin/python -m pytest
  tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
  tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py
  tests/specify_cli/cli/commands/agent/test_tasks_backward_emit.py
  tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py -q`
- Shared baseline: `make test-fast`.
- Terminology guard (user-facing message touched):
  `PYTHONPATH=src .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
- Lint/type/format: `ruff check src/specify_cli/cli/commands/agent/tasks_transition_core.py`,
  `mypy` on the changed module, `ruff format --check .` (or `ruff format` the
  changed files).

## Branch Strategy

Planning artifacts were generated on `issue-3937-blocked-planned-refusal-message`.
This WP branches from the mission base during `/spec-kitty.implement` (its lane
worktree is resolved from `lanes.json`); completed changes merge back into
`issue-3937-blocked-planned-refusal-message`, which lands via a PR to `main`.
The execution worktree is allocated per computed lane — do not hand-construct
the path.

## Definition of Done

- FR-001..FR-004 satisfied; the reachability × force matrix (NFR-001) is green
  and was RED-first.
- NFR-002: flagless `done → planned` emits no forced-rewind event.
- NFR-003: `wp_state.py` and `fsm_parity_baseline.jsonl` unchanged (0 rows).
- NFR-004: the existing review-family pin (`test_tasks_transition_core.py`
  ~line 473-474) stays green.
- `_guard_planned_rollback` stays unconditional; `_GUARDS` order unchanged; no
  new early-return; complexity ≤ 15; no suppressions; `ruff`/`mypy`/`ruff
  format` clean.

## Reviewer guidance

- Verify the guard has **no** source-scoped early `return None` and that every
  `--to planned` + missing-feedback branch returns `RefuseExit1`.
- Verify the matrix actually exercises `--force` and uses `done`/`canceled`/
  `genesis` as sources (the prior attempt's test did neither).
- Verify the `done`-flagless no-rewind-event assertion is present and meaningful.
- Confirm no `wp_state.py` / `fsm_parity_baseline.jsonl` diff.
