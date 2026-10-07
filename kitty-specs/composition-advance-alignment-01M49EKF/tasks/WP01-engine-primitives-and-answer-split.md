---
work_package_id: WP01
title: Engine primitives and the provide_decision_answer split
dependencies: []
requirement_refs:
- FR-005
- FR-011
- SC-003
planning_base_branch: issue-2562-composition-advance-alignment
merge_target_branch: issue-2562-composition-advance-alignment
branch_strategy: Planning artifacts for this mission were generated on issue-2562-composition-advance-alignment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2562-composition-advance-alignment unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Tidy-first engine seam
history:
- at: '2026-10-06T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/_internal_runtime/engine.py
create_intent:
- tests/next/test_engine_commit_primitives.py
- tests/next/test_provide_decision_answer_characterisation.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/runtime/next/_internal_runtime/engine.py
- tests/next/test_engine_commit_primitives.py
- tests/next/test_provide_decision_answer_characterisation.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#2562'
---

# Work Package Prompt: WP01 – Engine primitives and the provide_decision_answer split

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission composition-advance-alignment-01M49EKF`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2562-composition-advance-alignment` (stacked on `issue-2560-runtime-bridge-query-seam`, PR #5834).
- Final merge target: `issue-2562-composition-advance-alignment`.
- Topology `single_branch`: the WP runs in the repository root checkout; there is no lane worktree.

## Shared rules

- **Behaviour-preserving.** This WP changes no observable behaviour. Every existing engine test stays green unchanged.
- **Code quality.** Complexity ≤ 15. No new `noqa` / `type: ignore`. Run `ruff check`, `ruff format --check --force-exclude <changed files>`, and mypy over `src/runtime/next/`; mypy must add no error beyond the 21 on the base.
- **Engine-private names.** Engine-private names stay private (leading underscore). Only `runtime_bridge_engine` may reach them from outside `_internal_runtime/`; that is guarded by `tests/runtime/test_bridge_engine.py`.

## Objective

Give the engine:
- one definition of each run-event recording;
- an abort-only pre-completion guard on its commit path, which WP02 needs;
- no complexity suppression.

## Subtasks

### T001: Characterise `provide_decision_answer` (commit first, green on the base)

New file `tests/next/test_provide_decision_answer_characterisation.py`. Reuse the audit-mission fixture style of `tests/next/test_internal_runtime_engine_coverage.py`: start a run from a temp template, drive it with `next_step`, then answer.

Pin each branch's persisted `decisions` record, `completed_steps`, `blocked_reason`, `pending_decisions`, `inputs`, and the appended event (`DecisionInputAnswered` / `DecisionAuthorityDenied` payload):
- **Input decision:**
  - human answers;
  - answer written to `inputs`;
  - `raci_source` taken from `raci:<issued_step>` when present.
- **LLM delegation:**
  - not delegated → error;
  - empty rationale → error;
  - delegated with `authority_role` / `rationale_linkage`.
- **Audit authority denials:**
  - non-human actor;
  - no `mission_owner_id`;
  - wrong owner.
  - In each case `DecisionAuthorityDenied` is appended with `rationale_linkage: null` and `MissionRuntimeError` is raised.
- **Audit, no significance:** approve completes the step; reject sets `blocked_reason`; an invalid answer raises.
- **Audit, HIGH:** approve/reject are accepted; anything else raises with the "High-band" message.
- **Audit, MEDIUM:**
  - `decide_solo` → `soft_gate:` record with an outcome, and the step completes;
  - `open_stand_up` / `defer` → the pending entry is re-added (equal to the original request) and the outcome is `None`;
  - an approve answer raises with the "Medium-band" message.
- **Unknown decision id:** raises.

Assert exact error-message texts. Commit this file before T002 (the reviewer checks the order).

### T002: Split `provide_decision_answer`

Behaviour-preserving extraction to complexity ≤ 15, then remove `# noqa: C901`. Suggested helpers (squad Q7):
- `_raci_binding(decisions, snapshot, decision_id) -> tuple[str | None, str | None]`.
- `_significance_band(decisions, decision_id) -> str | None`. Today the band is read twice; both reads see the same data.
- `_authorize_audit_answer(...)`: owner checks; appends `DecisionAuthorityDenied` and raises; validates the answer against the band. Returns the authority role.
- `_authorize_llm_answer(inputs, decision_id, actor) -> tuple[str, str]` (role, rationale).
- `_apply_audit_answer(...)`: MEDIUM soft-gate handling via `_record_soft_gate(...)`, plus HIGH / no-band approve/reject. Re-add pending from the ORIGINAL `snapshot.pending_decisions`.

Keep these unchanged:
- the order: snapshot rebuilt with the explicit `MissionRunSnapshot(...)` constructor, written, then `DECISION_INPUT_ANSWERED` appended and emitted;
- the public signature.

T001 must pass unchanged.

### T003: Per-event recording primitives

Extract from `_commit_advance` (each persists through `_append_event`, then calls the emitter):
- `_record_step_completed(run_dir, run_id, step_id, agent_id, result, emitter)`
- `_record_significance(run_dir, payload, emitter)`
- `_record_step_issued(run_dir, run_id, step_id, agent_id, emitter)`
- `_request_decision_input(run_dir, run_id, decision, agent_id, pending, emitter) -> dict[str, Any]`. It adds the `DecisionRequest` and emits only when `decision.decision_id` is not already in `pending`. It returns the (new) pending map.
- `_record_run_completed(run_dir, run_id, mission_key, agent_id, emitter)`

Payloads must be byte-identical to today's: actor via `_actor(agent_id)`, field values unchanged. `_commit_advance` becomes a short dispatcher over these.

### T004: `before_run_completed` guard

Add the keyword-only `before_run_completed: Callable[[], None] | None = None` to `_commit_advance` and `commit_advance`. `commit_advance` keeps the `StaleAdvancePlan` check before anything is written.

On a terminal plan with a completed step (`decision.kind == "terminal" and plan.completed_step_id is not None`), call the guard at the top of `_commit_advance`, before any append or emit (operator ruling 2026-10-07, landing fold; the first implementation called it after the step-completed record). If the guard raises:
- the error propagates;
- nothing is appended or emitted and `state.json` is not written, so a retry starts from the run as it was.

This matches the engine's own legacy strict path, which rolls back byte for byte. `next_step` passes no guard. Document the contract in the docstring.

### T005: Engine unit tests

New file `tests/next/test_engine_commit_primitives.py`:
- **Order:** completed → significance → issued/requested/run-completed → snapshot write. Use a recording emitter plus `run.events.jsonl` order.
- **Dedupe:** `_request_decision_input` emits once and leaves `pending` untouched on a repeat.
- **Guard happy path:** the guard runs before `MissionRunCompleted`.
- **Guard abort:** a raising guard leaves `MissionRunCompleted` absent and `state.json` unchanged, and the error propagates.
- **No-step terminal:** the guard is not called on a terminal re-poll with no completed step.
- **Stale plan:** `commit_advance` raises `StaleAdvancePlan` and writes nothing when `state.json` changed after planning.

## Definition of Done

- The T001 characterisation is committed before T002 and is green before and after.
- `engine.py` has no `noqa: C901`; ruff C901 passes.
- `tests/next/` engine tests and `tests/runtime/test_bridge_engine.py` are green.
- mypy adds no new errors.

## Reviewer guidance

- Diff each primitive's payload construction against the base `_commit_advance` field by field.
- Confirm the MEDIUM re-add reads the original snapshot's pending map.
- Confirm the guard cannot suppress `MissionRunCompleted` without raising.

## Activity Log

- 2026-10-06T21:10:00Z – system – Prompt created.
