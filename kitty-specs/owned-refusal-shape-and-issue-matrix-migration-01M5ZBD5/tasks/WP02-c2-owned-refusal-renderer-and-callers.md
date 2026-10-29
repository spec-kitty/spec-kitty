---
work_package_id: WP02
title: One C2 owned refusal through the shared renderer
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-014
- C-001
- C-002
- C-004
- NFR-002
- NFR-003
- C-005
- C-006
planning_base_branch: issue-6354-owned-issue-verdict-cleanup
merge_target_branch: issue-6354-owned-issue-verdict-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-6354-owned-issue-verdict-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6354-owned-issue-verdict-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
base_commit: a9ec5fd69ec86a127d8855e2e1f1aebc79d34a23
created_at: '2026-10-27T20:08:33.773186+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Refusal shape
history:
- at: '2026-10-27T19:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- docs/adr/4.x/2026-10-27-1-owned-refusals-use-the-c2-error-contract.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_owned_checkout.py
- src/specify_cli/cli/commands/agent/acceptance_verdict.py
- src/specify_cli/cli/commands/agent/context.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/cli/commands/agent/tasks_status_cmd.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/next_cmd.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/spec_commit_cmd.py
- src/specify_cli/cli/commands/research.py
- src/specify_cli/cli/commands/charter/generate.py
- src/specify_cli/cli/commands/decision.py
- docs/adr/4.x/2026-10-27-1-owned-refusals-use-the-c2-error-contract.md
- tests/specify_cli/cli/commands/test_owned_checkout_helper.py
- tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py
- tests/specify_cli/cli/commands/agent/test_task_command_owned_conversion.py
- tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py
- tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py
- tests/specify_cli/cli/commands/test_next_owned_fact.py
- tests/specify_cli/cli/commands/test_accept_decomposition.py
- tests/specify_cli/cli/commands/test_decision_owned_checkout.py
- tests/specify_cli/invocation/cli/test_op_owned_checkout.py
- tests/integration/test_owned_issue_verdict_authority_6320.py
- tests/integration/test_p0_repro_6320_owned_issue_verdict.py
- tests/integration/test_p0_repro_6023_owned_acceptance_verdict.py
- tests/integration/test_owned_lifecycle_acceptance_*.py
- tests/integration/test_owned_analysis_recording.py
- tests/integration/test_owned_charter_generation.py
- tests/integration/test_owned_map_requirements.py
- tests/integration/test_owned_checkout_mark_status.py
- tests/integration/test_owned_decision_runtime_lock.py
- tests/integration/test_explicit_checkout_commands.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One C2 owned refusal through the shared renderer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

Issue #6353, operator ruling 2026-10-27 (Decision Moments in
`kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/decisions/`). Every
owned-checkout refusal rendered by the shared renderer prints, in `--json` mode, on
stdout, exit 1:

```json
{"ok": false, "error": {"code": "<registered owned code>", "message": "<text>"}}
```

plus an optional top-level `context` object (command-specific facts) and an optional
top-level `spec_kitty_version` (commands that stamp every payload). Nothing else at the
top level: no `error_code`, `success`, `result`, `status`, `code`, `message`.

Done when:
- FR-004 / FR-005: every renderer caller emits the C2 core, no top-level `error_code`.
- FR-007: `context` carries mark-status's nothing-applied facts, spec-commit's `committed: false`, setup-plan's `phase_complete: false`.
- FR-008: setup-plan, finalize-tasks, check-prerequisites and record-analysis carry `spec_kitty_version` top-level on their owned refusal.
- FR-009: the `agent decision` verbs' owned refusal is on stdout (their non-owned errors stay on stderr).
- FR-010: human mode unchanged (`Error: [<CODE>] <message>` on stderr, exit 1).
- FR-011: success payloads and non-owned error payloads unchanged.
- FR-014: ADR written; it supersedes the contract line quoted in T008.
- C-001: the unregistered-code fail-closed check stays. C-002: `test_owned_checkout_single_authority.py` stays green with its empty allowlist.

The contract and per-command `context` table are in
`kitty-specs/owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5/contracts/owned-refusal-envelope.md`
and `data-model.md`. Read them first.

## Context & Constraints

- research.md §1.2-§1.4: grounding, full caller inventory (rows 1-21, 24, 25) and the list of stale tests.
- Plan IC-02 and the confirmed Engineering Alignment (renderer by construction; redundant `result:"error"` / `success:false` dropped, not moved).
- The core comes from `specify_cli.cli.json_contract.json_error`, the single C2 authority. Do not re-spell `{"ok": False, "error": {...}}` anywhere.
- **Out of scope here (WP04):** `agent mission create` (`mission_create.py`) and the move-task owned catch-all (`tasks_move_task.py:1726-1740`). Leave both files untouched.
- **Out-of-map edit (recorded leeway):** `src/specify_cli/cli/commands/agent/issue_verdict.py` belongs to WP01. Its `resolve_owned_or_refuse(..., envelope=success_false_envelope)` call (~line 379-387) must drop `envelope=` here or the module will not import. Make exactly that edit plus the import cleanup and record it with `spec-kitty agent tasks add-history WP02 --note "out-of-map: issue_verdict.py renderer call (signature change)"`. WP01 is approved before WP02 starts, so the edit cannot collide.
- `dispatch.py`, `invocations_cmd.py` and `profile_invocation.py` need no edit: their refusal goes through `resolve_owned_op_record_root` inside `_owned_checkout.py`.
- ATDD: T006 is committed red before T007.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6354-owned-issue-verdict-cleanup`
- **Merge target branch**: `issue-6354-owned-issue-verdict-cleanup`

```bash
spec-kitty agent action implement WP02 --agent claude --mission owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
```

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first tests

- **Renderer unit tests** in `tests/specify_cli/cli/commands/test_owned_checkout_helper.py`
  (add, do not yet delete the old ones; T012 re-pins them):
  1. `test_owned_refusal_payload_is_strict_c2`: `owned_refusal_payload("OWNED_CHECKOUT_IS_REPOSITORY_ROOT", "m") == {"ok": False, "error": {"code": "OWNED_CHECKOUT_IS_REPOSITORY_ROOT", "message": "m"}}`.
  2. `test_owned_refusal_payload_adds_context_only_when_given`: with `context={"committed": False}` the payload gains exactly `"context": {"committed": False}`; with `context=None` there is no `context` key.
  3. `test_owned_refusal_payload_stamps_version_only_when_asked`: `stamp_version=True` adds `spec_kitty_version == cli_version()`; default adds nothing.
  4. `test_emit_owned_refusal_json_prints_c2_and_exits_one` (capsys): no top-level `error_code`; exit code 1.
  5. `test_emit_owned_refusal_human_mode_unchanged`: stderr is exactly `Error: [<code>] <message>` (positive control for FR-010).
  6. Keep the existing unregistered-code test (C-001).
- **Integration**: in `tests/integration/test_owned_issue_verdict_authority_6320.py`, extend
  `test_owned_fact_resolving_no_mission_still_refuses` (or add a sibling in the same module,
  same fixture) asserting `json.loads(res.output) == {"ok": False, "error": {"code": "MISSION_CONTEXT_UNRESOLVED", "message": ANY_NON_EMPTY_STR}}`
  and the existing no-write assertions (NFR-004). Keep the positive test in that module
  (owned verdict records) as the same-fixture control.
- Commit red: `test(owned-checkout): red C2 owned refusal shape (#6353)`.

### Subtask T007 – Renderer core (`_owned_checkout.py`)

1. Add the single builder:

   ```python
   def owned_refusal_payload(
       code: str,
       message: str,
       *,
       context: Mapping[str, object] | None = None,
       stamp_version: bool = False,
   ) -> dict[str, object]:
       """The ONE owned-refusal JSON payload: C2 core + optional ``context`` + optional version stamp."""
       payload = json_error(code, message)
       if context is not None:
           payload["context"] = dict(context)
       if stamp_version:
           payload["spec_kitty_version"] = cli_version()
       return payload
   ```

   Import `cli_version` from `specify_cli.version_utils` lazily inside the function if a
   top-level import would break the module's cold-import boundary (see the module
   docstring, "Cold-import boundary"); check `python -X importtime` is not needed;
   just keep it lazy to be safe. Non-validating by design: WP04's move-task catch-all uses it
   for arbitrary `ActionContextError` codes.
2. `emit_owned_refusal(exc, *, json_output, context=None, stamp_version=False) -> NoReturn`:
   registry check first (unchanged), then `owned_refusal_payload(exc.code, str(exc), context=..., stamp_version=...)`;
   JSON → `print(json.dumps(payload, indent=2))` (stdout, unchanged indentation), human →
   unchanged stderr line; `raise typer.Exit(1)`. Delete `_ERROR_CODE_KEY` and the force-add.
3. `resolve_owned_or_refuse(..., json_output, context=None, stamp_version=False, target_override=None)`:
   replace the `envelope` parameter; forward both to `emit_owned_refusal`.
4. `resolve_owned_op_record_root`: call `emit_owned_refusal(exc, json_output=json_output)`.
5. Delete `success_false_envelope`, `json_error_envelope`, `flat_error_envelope`,
   `result_error_envelope`. Remove the now-unused `Callable` import. Add
   `owned_refusal_payload` to any `__all__` the module has (it has none today; do not add one).
6. Rewrite the module docstring's "Envelope rule" paragraph: owned refusals are C2 (see ADR
   `2026-10-27-1`), and `stale_repository_root_copy` stays additive-only on **success** payloads.
   Update the bullet "typed refusal rendering ... and the four envelope builders" to name
   `owned_refusal_payload`.
7. Keep complexity <= 15 and `mypy --strict` clean.

### Subtask T008 – ADR

Create `docs/adr/4.x/2026-10-27-1-owned-refusals-use-the-c2-error-contract.md`. Mirror the
frontmatter/heading style of a recent ADR in `docs/adr/4.x/` (read
`2026-10-26-1-done-judges-every-issue-matrix-row.md` for the house style; include `status`,
date, an `updated:` freshness date as other ADRs do). Content:
- **Context**: six owned-refusal shapes across commands (research §1.3); issue-verdict's refusal lacked its own `code` key (issue #6353); the operator asked for one shape for every command (2026-10-18 triage, 2026-10-27 rulings).
- **Decision**: C2 core from `json_error`; strict (no top-level `error_code`); optional `context`; `spec_kitty_version` stays top-level where stamped; decision verbs' owned refusal on stdout; human mode unchanged; renderer takes no envelope builder (shape fixed by construction); off-renderer paths use `owned_refusal_payload`.
- **Supersedes**: the sentence "`emit_owned_refusal` keeps each command's existing JSON envelope keys. `error_code` is always one of the registered codes." in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/cli-owned-checkout-surface.md`, line 21. Do **not** edit that historical mission file; the ADR records the supersession.
- **Consequences**: consumers that read top-level `error_code` move to `error.code`; orchestrator-api 1.19.0 (WP03); non-owned errors unchanged; see #4664 for the decision verbs' remaining stderr JSON.
- **Alternatives**: command-faithful + `error_code`; fixed `success_false`; C2 + additive `error_code`.

### Subtask T009 – Agent mission family call sites

For each, replace `envelope=...` with the mapped arguments, delete the now-dead local
envelope helper, and keep everything else byte-identical:

| File (approx. line) | Change |
|---|---|
| `agent/issue_verdict.py` (~379-387, **out-of-map**, see Constraints) | drop `envelope=success_false_envelope` and its import |
| `agent/acceptance_verdict.py` (~593-601) | drop `envelope=success_false_envelope` + import |
| `agent/context.py` (~259-268) | `emit_owned_refusal(exc, json_output=json_output)` |
| `agent/context.py::_emit_context_error` (~208-229) | it reused `success_false_envelope` for **non-owned** errors. Inline its dict `{"success": False, "error_code": code, "error": message}` locally so the non-owned shape is byte-identical (FR-011); update its docstring |
| `agent/mission_setup_plan.py` (~1246-1249) | `emit_owned_refusal(exc, json_output=json_output, context={"phase_complete": False}, stamp_version=True)` |
| `agent/mission_finalize.py` (~660, ~794) | `stamp_version=True`; delete `_finalize_refusal_envelope` (~592-601) |
| `agent/mission_check_prerequisites.py` (~678-686, ~768) | `stamp_version=True`; delete `_refusal_envelope` (~610-613) and the `flat_error_envelope` import |
| `agent/mission_record_analysis.py` (~372, ~419-427) | `stamp_version=True` (its other payloads carry the stamp) |

Before editing check-prerequisites, read `src/specify_cli/orchestrator_api/design_phase.py:449-476`.
The orchestrator classifier reads this payload; WP03 adapts it. Do not edit it here,
but note in the history that WP03 depends on this change.

### Subtask T010 – Tasks family call sites

- `agent/tasks.py::_resolve_task_owned` (~688-719): replace the `envelope` parameter with
  `context: Mapping[str, object] | None = None`; forward to `resolve_owned_or_refuse`.
  - move-task (~891) and map-requirements (~1354): drop `envelope=flat_error_envelope`.
  - mark-status (~1020): pass `context=_ms_failure_context()` (nothing applied).
- `agent/tasks_mark_status.py`: split today's `_ms_failure_payload` into
  `_ms_failure_context(*, event_ids=None, applied_wps=None, destination_ref=None, status_events_path=None, status_snapshot_path=None, dirty=None) -> dict[str, object]`
  returning exactly `{state_applied, event_ids, applied_wps, destination_ref, status_events_path, status_snapshot_path, dirty}`
  (same value rules as today), and make the in-command owned failure
  (`_ms_report_owned_failure`, ~653-690) print
  `owned_refusal_payload(error_code, str(error), context=_ms_failure_context(...))`.
  Drop the `result: "error"` key (Engineering Alignment 2). Keep the human line and the
  exit unchanged. Update both docstrings (the "ONE builder" claim now points at
  `_ms_failure_context` + `owned_refusal_payload`). The in-command path keeps accepting
  its fallback code `MARK_STATUS_FAILED` (it never went through the registry check).
- `agent/tasks_status_cmd.py` (~200-209): `emit_owned_refusal(exc, json_output=st.json_output)`.
  This command is C2-adopted for its ordinary errors already; its owned refusal now
  loses only the extra top-level `error_code`.

### Subtask T011 – Top-level call sites

| File (approx. line) | Change |
|---|---|
| `next_cmd.py` (~238-252) | `emit_owned_refusal(exc, json_output=json_output)`; fix the docstring line "`next`'s `{success, error_code, error}` envelope" (~227) |
| `accept.py` (~959-983) | delete `_refusal_envelope`; `emit_owned_refusal(exc, json_output=json_output)`. Accept's other refusals (incl. any in-flight work, see #6715) are **not** owned refusals: leave them |
| `spec_commit_cmd.py` (~151-153, ~519-527) | delete `_refusal_envelope`; `context={"committed": False}`. Also inspect the `except ActionContextError` arm (~540-546) that adds `error_code`: if it renders an **owned** refusal, route it through `emit_owned_refusal(..., context={"committed": False})`; if it is a non-owned failure, leave it unchanged (FR-011) and say which in the history note |
| `charter/generate.py` (~461-469) | drop `envelope=success_false_envelope` + import |
| `research.py` (~216-224) | drop `envelope=` (human only; no `--json`) |
| `agent/workflow.py` (~1109-1119) | `emit_owned_refusal(exc, json_output=False)` |
| `decision.py` repair-runtime-lock (~1099-1107) | drop the lambda envelope |
| `decision.py` verbs (`_resolve_decision_context`, ~229-237) | today `resolve_owned_or_adopt` raises into the verbs' generic `except ActionContextError` → `_handle_action_context_error` (stderr `{error, code}`). Wrap **only** the `resolve_owned_or_adopt(...)` call in `try/except ActionContextError as exc: emit_owned_refusal(exc, json_output=True)` so the owned refusal goes to stdout as C2 (FR-009). These verbs always print JSON, so `json_output=True`. Non-owned resolver errors raised later (e.g. `_resolve_repo_root_and_slug`) keep `_handle_action_context_error` on stderr. Note: `MISSION_CONTEXT_UNRESOLVED` / `MISSION_CONTEXT_CONFLICT` are registered owned codes, so the registry check accepts every code this call raises |

### Subtask T012 – Re-pin stale shape assertions

Judge each failing assertion (charter Standing Order 4: stale → re-pin, never delete a
valid test). Files and spots known from research §1.4:
- `test_owned_checkout_helper.py` (:187, :516, :531-541 force-add test → delete only the force-add assertion and replace it with the C2 strictness assertion; :597-615 builder tests → replace with the T006 payload tests).
- `test_next_owned_fact.py:198` → C2.
- `test_accept_decomposition.py:269-270, :713` → C2 (ordinary accept errors at :245, :256, :328, :634 stay `{"error": ...}`: FR-011 control).
- `agent/test_task_command_owned_conversion.py` :114, :132 (flat builder test → delete with the builder; covered by T006), :342 (`_ms_failure_payload` → `_ms_failure_context` + C2), :443-459 (spec-commit, check-prereq).
- `agent/test_mission_finalize_phases.py:1516` (+ :535, :571 if they pin the refusal).
- `agent/test_mission_setup_plan_phases.py:1200-1202`.
- `test_owned_refusal_format_unified.py` (move-task, check-prereq, mark-status JSON assertions).
- `tests/integration/test_owned_lifecycle_acceptance_next.py:193` (`success is False` → `ok is False`).
- Shape-agnostic `["error_code"]` reads → `["error"]["code"]`:
  `test_owned_lifecycle_acceptance_context.py` (:115, :333-335, :526, :554, :573),
  `test_owned_analysis_recording.py` (:156, :210, :234), `test_owned_charter_generation.py:86`,
  `test_owned_map_requirements.py:116`, `tests/specify_cli/invocation/cli/test_op_owned_checkout.py` (:143, :157, :185, :217),
  `test_explicit_checkout_commands.py` (grep `error_code`), `test_p0_repro_6320_owned_issue_verdict.py:70`
  (tolerant `get("error_code") or get("code")` → read `["error"]["code"]`), `test_p0_repro_6023_owned_acceptance_verdict.py`,
  `test_owned_checkout_mark_status.py`, `test_decision_owned_checkout.py`, `test_owned_decision_runtime_lock.py`.
- Find the rest mechanically: `grep -rn "error_code" tests | grep -i owned` and
  `grep -rln "success_false_envelope\|flat_error_envelope\|json_error_envelope\|result_error_envelope\|_ms_failure_payload\|_finalize_refusal_envelope" tests src`
  must both come back clean of owned-refusal shape pins (the second must return nothing).
  Some hits are **not** owned refusals (e.g. finalize-tasks validation codes, origin-freshness codes, `tests/core/test_checkout_ownership.py` which tests the claim primitive's own `error_code` attribute). Leave those alone.
- If a stale test lives in a file not in `owned_files`, edit it with a recorded out-of-map note (leeway); WP03/WP04 own the orchestrator, mission-create and move-task catch-all tests, so do not touch those.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_owned_checkout_helper.py \
  tests/specify_cli/cli/commands/test_owned_refusal_format_unified.py \
  tests/specify_cli/cli/commands/agent/ tests/specify_cli/cli/commands/test_next_owned_fact.py \
  tests/specify_cli/cli/commands/test_accept_decomposition.py \
  tests/specify_cli/cli/commands/test_decision_owned_checkout.py \
  tests/specify_cli/cli/test_decision_command_shape_consistency.py \
  tests/specify_cli/invocation/cli/test_op_owned_checkout.py -q
uv run --frozen pytest tests/integration/test_owned_*.py tests/integration/test_explicit_checkout_commands.py \
  tests/integration/test_p0_repro_6320_owned_issue_verdict.py tests/integration/test_p0_repro_6023_owned_acceptance_verdict.py -q
uv run --frozen pytest tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <touched files>; uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
```

The integration tests are slow (owned fixture). Run them once at the end, after the unit
tier is green. Do not run `make test-full` or a bare `tests/architectural/`.

## Risks & Mitigations

- **Atomic signature change**: an intermediate commit that changes the renderer before all callers would not import. Commit order: T006 (red tests), then one commit for T007 + T009-T011 (renderer + callers), then T012 (re-pins), T008 (ADR) separately.
- **Non-owned regressions**: `context.py::_emit_context_error` and accept's ordinary errors must stay byte-identical; the T012 re-pins keep their existing assertions as controls.
- **Decision verbs**: wrapping only the resolver call is what keeps non-owned errors on stderr.
- **Cold imports**: keep `cli_version` and `json_error` imports at the right scope; `json_contract` is already imported at module top.

## Review Guidance

- `grep -rn "error_code" src/specify_cli/cli/commands/_owned_checkout.py` shows no force-add; the four builders are gone; no caller passes `envelope=`.
- Each command's owned refusal matches the contract table in `data-model.md`; success and non-owned error payloads unchanged.
- The ADR names and supersedes the exact contract line.
- Red-first commit order visible; mypy/ruff/format clean; complexity <= 15.
- Out-of-map edits are recorded in the history.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP02 --to <status>`
- `spec-kitty agent tasks status`
