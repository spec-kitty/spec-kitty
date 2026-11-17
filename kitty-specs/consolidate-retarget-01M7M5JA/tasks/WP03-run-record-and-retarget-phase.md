---
work_package_id: WP03
title: Run record, entry preflight and the retarget phase
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-011
- FR-012
- NFR-001
- NFR-002
- C-003
- C-005
- NFR-004
- C-006
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T012
- T013
- T014
- T015
- T016
- T017
phase: Phase 2 - Core
history:
- at: '2026-11-17T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_retarget_record.py
- tests/consolidation/test_retarget_entry_preflight.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/entry_preflight.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/consolidation/resolve.py
- src/specify_cli/consolidation/phase_advance.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/run_state.py
- tests/consolidation/test_executor_rollback_wiring.py
- src/specify_cli/consolidation/status_surface.py
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/mission_metadata.py
- tests/consolidation/test_retarget_record.py
- tests/consolidation/test_retarget_entry_preflight.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_executor_phase_boundary.py
- tests/consolidation/test_state_snapshot_fields.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Run record, entry preflight and the retarget phase

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission consolidate-retarget-01M7M5JA`). If this WP returned from review, the feedback is your TODO list.

---

## Objectives & Success Criteria

This is the core of #7692. After this WP, `_run_lane_based_consolidation(..., target_override=<b>, retarget=True, retarget_reason=...)` does the following:

1. **Entry preflight.** It judges the retarget against `<b>`: #6464, `RETARGET_RECORD_UNWRITABLE`, and the #5385 probe re-pointed at `<b>`. It does this pre-lock, before anything moves, and refuses with the verdict's own code.
2. **Run record.** It records `state.retarget = {"from", "to", "actor", "at", "reason", "committed": False}` in a fresh run record, before the claim.
3. **Claim.** The claim's status surface follows `<b>`, not the old target (squad A2).
4. **First mutation.** As the first mutation inside the one rollback door, it commits the rewritten record (`target_branch = <b>` plus a `retarget_history` entry):
   - on the Mission branch, when its tree carries `meta.json` (the meta driver's two-way landing takes `target_branch` from that side; squad A1, witnessed by the spike);
   - on `<b>` in the root checkout.

   It records both moves (`_records_post_mutation_tips`, and the `advance_branch_ref` intents) and then persists `committed=True`.
5. **Downstream.** Every later write resolves `<b>` from the record: the landing, `done`, the flatten, the bake, the projections and the retrospective.
6. **Rollback.** On failure, the one rollback authority restores `<b>` and the Mission branch, which undoes the record. The re-baseline keeps `state.retarget` with `committed=False`.
7. **Resume.** `--resume` honours a persisted retarget and never commits it twice. `--resume --target X --retarget` with an X other than the persisted `to` refuses with `RETARGET_RESUME_MISMATCH`.

A plain `--target` (no `retarget`) behaves byte-identically to today.

## Context & Constraints

- Read first: `spec.md` (FR-003, FR-004, FR-006, FR-007, FR-008, FR-011, FR-012, NFR-002, C-003, C-005), `plan.md` D2–D7, `research.md` (squad A1–A6, R2, R5), and `data-model.md`.
- Read ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (the one rollback authority, the re-baseline, `UNEXPLAINED_BRANCH_MOVE`). WP05 writes its amendment; do not edit the ADR here.
- WP01 provides: `consolidation/meta_write.py` (`locked_update_meta_capturing`, `undo_meta_write`, `primary_checkout_refusal`, `commit_meta_on_branch`); `preflight.target_override_verdict`, `retarget_record_refusal` and the codes; `refuse_protected_status_target(retarget_to=...)`.
- C-003: no second restore path. `tests/consolidation/test_single_rollback_authority.py` forbids `restore_branch_ref` outside `rollback.py` in the executor family.
- C-005: do NOT thread `<b>` through each bookkeeping write. The record is the authority.

## Branch Strategy

- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

Worktrees are allocated per lane from `lanes.json`.
`spec-kitty agent action implement WP03 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T008 – Entry preflight: the retarget arm, re-pointed #5385, resume awareness

- **Purpose**: FR-002, FR-008, FR-011 and FR-007's mismatch arm, with NFR-001 (refusals move nothing).
- **Steps**:
  1. Thread `retarget: bool` (keyword-only, default False) into `_refuse_protected_status_target_or_continue` and `_refuse_protected_target_override_or_continue` in `entry_preflight.py`. `executor.py:1104` is the caller. The persisted record is NOT a parameter: a helper `_retarget_mode(main_repo, canonical_id, *, retarget, recorded, effective)` loads it inside the preflight, so the executor signature stays small.
  2. Derive a single `retarget_mode` in that helper:
     - True when `retarget` is set and `effective != recorded`;
     - or when a merge record exists whose `state.retarget` has `to == effective` and `from == recorded`. That is a bare `--resume`, or a re-run after a re-baselined failure.
     - Read the persisted record with `load_state(main_repo, canonical_id)` behind a try. An unreadable record keeps today's path; the existing resume code owns that error.
  3. `RETARGET_RESUME_MISMATCH`: if `retarget` is set and a persisted `state.retarget` exists with `to != effective`, refuse (exit 1). The message names both branches; the next step is `--abort` or re-run with `--target <persisted to>`. Use the existing footer (`_protected_refusal_footer`).
  4. The #5385 probe:
     - With `retarget_mode`, call `refuse_protected_status_target(main_repo, slug, lanes_manifest, retarget_to=effective)`. It is re-pointed, never skipped.
     - Without `retarget_mode`, call it exactly as today.
  5. Replace the inline `or` chain with `target_override_verdict(main_repo, slug, recorded_target=..., effective_target=..., retarget=retarget_mode)`. The rendering (`Error: <code>: <message>`, `Next step:`, footer) and the `ActionContextError` handling stay byte-identical.
  6. **Attestations under a retarget (post-tasks squad).** `_record_operator_attestations` (`executor.py:~522`) writes status events BEFORE the rollback door, to `status_surface_ref`. On a coordination-less Mission that is the recorded target, and the status door would refuse it (the root checkout is on `<b>`).
     - When `retarget_mode` is set, any attestation flag is passed (`attest_canceled_superseded`, `attest_approved_reviewed`, `attest_no_implementation`), and `status_surface_ref(main_repo, slug)` equals the recorded target: refuse with `RETARGET_WITH_ATTESTATION_UNSUPPORTED` (exit 1, nothing moved).
     - The next step: record the attestation with a consolidate run onto the recorded target, or retarget first and attest on the next run.
     - Thread the attestation flags in as a single `has_attestations: bool` keyword.
     - A coordination-topology Mission (status on the coordination branch) is unaffected.
     - This boundary is reported to the operator in the PR.
  7. Add an informational line when the retarget is admitted (for example `Retargeting <slug>: <from> -> <to> (recorded with this run).`), printed once.
- **Files**: `src/specify_cli/consolidation/entry_preflight.py`.

### Subtask T012 – `ConsolidationState.retarget` and fresh-run creation

- **Steps**:
  1. In `state.py`, add the field `retarget: dict[str, Any] | None = None` to `ConsolidationState`:
     - serialise it in `to_dict`;
     - in `from_dict`, read it with a default of `None` when absent, and accept only a dict carrying the keys `from`, `to` and `committed` (otherwise `None`, with a logged warning);
     - add accessor helpers `retarget_pending() -> bool` and `retarget_committed() -> bool` if useful.
     - Check `tests/consolidation/test_state_snapshot_fields.py`; if it pins the field set, extend it.
  2. In `resolve.py::_load_or_create_merge_state`, add a keyword `retarget: dict | None = None`. A FRESH record stores it; a resumed record keeps its persisted value. Never overwrite a persisted retarget with `None`.
  3. In `executor.py::_run_lane_based_consolidation`, add `retarget: bool = False, retarget_reason: str | None = None`. The record is created inside `_run_lane_based_consolidation_locked` (`_load_or_create_merge_state` at about :551), so thread the built dict there as a `retarget_record` keyword. Both entry-preflight functions (`_refuse_protected_status_target_or_continue`, which calls `_refuse_protected_target_override_or_continue` at about :469) take the new keywords.
     - When `retarget` is set and `target_override` differs from the recorded target, build the dict: actor from `done_bookkeeping._resolve_merge_actor()`, `at` from the kernel clock, and `reason` defaulting to `f"operator retarget via spec-kitty consolidate --target {b} --retarget"`.
     - On a resume, the persisted dict wins.
     - The actor helper takes the repository: `done_bookkeeping._resolve_merge_actor(main_repo)`.
     - FR-012: equal targets give no dict.
- **Files**: `state.py`, `resolve.py`, `executor.py`.

### Subtask T013 – `_phase_retarget_record` in `phase_advance.py`

- **Purpose**: FR-003, FR-004, NFR-002. This is the first mutation inside the door.
- **Steps**:
  1. Define `_phase_retarget_record(run)` in `phase_advance.py` next to `_phase_merge_lanes`, decorated with `run_state._records_post_mutation_tips`. Follow how the other recorded phases import and apply the decorator.
  2. Return immediately only when `run.state.retarget` is None. Do NOT return early on `committed` (squad: a partial rollback can leave `committed=True` while `<b>` lacks the record). Always run the phase, and let the idempotent mutate return False (`unchanged`) when the copy already names `to` with a matching last history entry. The mutate dedupes the history entry on (`from`, `to`, `at`), so NFR-002 holds on every resume.
  3. Mutate closure: set `target_branch = to`, and append `{"from", "to", "actor", "at", "reason"}` to `retarget_history` through `mission_metadata._append_bounded` (T016). Return True only when something changed.
  4. **Which copies.** Call WP01's `preflight.retarget_record_holders(main_repo, slug, mission_branch=lanes_manifest.mission_branch, effective_target=to)`, the one owner of the rule. It returns the branches whose tree carries the record.
     - Explicit lanes: the Mission branch and `<b>`.
     - Explicit coord: `<b>` only.
     - Default topology, settled `lanes_with_coord` or `single_branch`: the topic (Mission) branch, plus `<b>` when `<b>` already carries it.

     Write each holder, Mission branch first.
  5. **Mission-branch copy** (when it is a holder). Call `meta_write.commit_meta_on_branch(main_repo, lanes_manifest.mission_branch, slug, mutate, message=f"chore({slug}): retarget {from} -> {to}")`.
     - `written`: fine. Its `advance_branch_ref` runs inside `reporting_advance_intents`, so the intent is recorded, and it resyncs any checkout holding the branch. For a default Mission that is the coordination worktree, or the write checkout of a default `single_branch` Mission. This is the same path the mission-number bake takes today.
     - `unchanged`: already retargeted, so skip.
     - `refused` / `no_meta_on_branch`: print the reason and raise `typer.Exit(1)`; the door rolls back.
     - Skip when `mission_branch == to` (planning-artifact-only).
  5b. **`<b>` copy (root checkout)**, only when `<b>` is a holder.
     - Compose `meta_path = compose_meta_json_path(main_repo, slug)` and `rel_meta`.
     - Re-check `primary_checkout_refusal(main_repo, rel_meta, to)`. The world may have moved since the preflight; on a refusal, `typer.Exit(1)`.
     - `captured = locked_update_meta_capturing(meta_path.parent, mutate, repo_root=main_repo)`. If `None`, it is already written.
     - `commit_merge_bookkeeping(repo_root=main_repo, worktree_root=main_repo, mission_slug=slug, message=..., paths=(rel_meta,), destination_ref_override=to)`.
     - On `SafeCommitError` / `RuntimeError`: `undo_meta_write(meta_path, *captured, main_repo)`, print the reason, and raise `typer.Exit(1)`.
  6. Persist `run.state.retarget["committed"] = True` with `save_state(...)` (follow how other phases persist `run.state`). This MUST be the module-level function `phase_advance._persist_retarget_committed(run)`, called through the module global. It is a contract with WP04's kill arm.
  7. Print `Retarget recorded: <from> -> <to>`.
- **Files**: `src/specify_cli/consolidation/phase_advance.py`.
- **Notes**:
  - Order: Mission branch first, then `<b>`. Each move is recorded on its own, and the decorator records both post tips on any exit.
  - Neither copy edits `lanes.json` (D4).
  - Do not touch the meta merge driver.

### Subtask T014 – Executor wiring and the claim's status surface

- **Steps**:
  1. In `executor.py::_run_lane_based_consolidation_locked`, call `_phase_retarget_record(run)` as the FIRST statement inside the `if not _resume_reconciliation_already_passed(run):` branch of the rollback `try`, before `_phase_merge_lanes(run)`. Import it the same way the other phases are imported, so tests can patch `executor._phase_retarget_record`.
  2. **Status surface (squad A2).**
     - `status_surface.py::status_surface_tip` (and `status_surface_ref`) gain `retarget: tuple[str, str] | None = None`. A resolved ref equal to `retarget[0]` is replaced by `retarget[1]`.
     - The live read is `run_state.py::_capture_coord_checkpoint` (`status_surface_tip`, about line 458), which `phase_claim.py` (:331, :497) and `coord_strand.py` (:62) call. It already receives `run`, so pass `(run.state.retarget["from"], run.state.retarget["to"])` there when `run.state.retarget` is set. That one change covers every caller.
     - On a coordination topology (explicit coord or default `lanes_with_coord`) the surface is the coordination branch, and the mapping is a no-op.
     - The old target then never enters `pre_mutation_refs` or `unsettled_refs`; a test asserts this (T017).
     - `claim_inputs.py` (the forecast) reads the same function; it keeps the default (`None`), because the forecast moves nothing.
  3. Thread `retarget` / `persisted_retarget` into the entry-preflight call (T008).
- **Files**: `executor.py`, `phase_claim.py`, `status_surface.py`.

### Subtask T015 – Re-baseline keeps the retarget; abort clears it

- **Steps**:
  1. In `rollback.py::rebaseline_after_full_restore`, set `state.retarget["committed"] = False` when a retarget is present, and keep the record. A bare `--resume` or a re-run then re-applies it and is judged as a retarget (squad A4).
  2. Confirm `--abort` (`cli/commands/consolidate.py::_abort_restore_or_keep_record` → `clear_state`) drops the whole record, so no edit is needed. Add a unit assertion.
- **Files**: `rollback.py`.

### Subtask T016 – `retarget_history` provenance

- **Steps**:
  1. In `mission_metadata.py`:
     - add `retarget_history: list[dict[str, str]]` to `MissionMetaOptional`;
     - add a private `_append_bounded(meta: dict, key: str, entry: dict, *, cap: int = HISTORY_CAP) -> None`, and make `record_acceptance` use it, with behaviour unchanged (squad R3).
     - Export a tiny public `append_retarget_history(meta, entry)` only if `phase_advance` cannot reasonably import a private name. The architectural gates prefer no new public symbol without a caller; this one has one.
  2. Check whether the meta merge driver's coupled groups (`consolidation/drivers.py`) need the new key. Both copies are identical, so the two-way merge is stable either way. Do NOT edit the driver; if a driver test complains, record it and ask.
- **Files**: `src/specify_cli/mission_metadata.py`.

### Subtask T017 – Unit tests and gate updates (red-first)

- **Steps**:
  1. `tests/consolidation/test_retarget_entry_preflight.py`. Cover:
     - a retarget admitted on a clean `<b>` gives no exit;
     - `RETARGET_RECORD_UNWRITABLE` gives exit 1 with the footer;
     - the protected `<b>` gives `PROTECTED_BRANCH_REFUSED`;
     - the re-pointed #5385 probe receives `retarget_to` (monkeypatch);
     - a plain `--target` is byte-identical to today (`TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`);
     - a persisted retarget makes a bare resume a retarget;
     - `RETARGET_RESUME_MISMATCH`.

     Use the lightweight fixtures the existing `tests/consolidation/test_unwritable_recorded_target_verdict.py` / entry-preflight tests use.
  2. `tests/consolidation/test_retarget_record.py`, on a real git repo built with the `tests/terminus` fixtures (`build_lanes_mission`, `build_coord_mission`), calling the phase directly through a minimal `_MergeRunState`. Copy the setup from `tests/consolidation/test_executor_coverage.py`. Cover:
     - lanes: both copies are written (`git show <mission_branch>:kitty-specs/<slug>/meta.json` and `develop:...` name `develop`, with one history entry), and `committed` is persisted;
     - coord: the Mission branch has no `meta.json`, so only `<b>` is written;
     - a second call is a no-op (NFR-002);
     - a refused `<b>` commit undoes the file bytes and raises `Exit(1)`;
     - after `rollback_to_snapshot` the record is restored, and the re-baseline keeps `retarget` with `committed=False`;
     - the claim's status surface on lanes is `develop`, not `main`, and `main` is absent from `pre_mutation_refs` / `unsettled_refs`.
  2b. A `single_branch` commit-to-target Mission (C-006): use `tests/terminus/test_protected_target_preflight.py::_build_commit_to_target_single_branch` as the shape reference. Pin what a retarget does: it lands, or it refuses with a named code. Record which outcome in the WP history and in the test docstring; WP04 and the PR report it to the operator.
  3. `tests/consolidation/test_single_rollback_authority.py`: add `"_phase_retarget_record"` to `_SPAN_PHASES`. The floor rises by one; that is intended and the docstring says why.
  4. `tests/consolidation/test_executor_rollback_wiring.py` (about :309-323, the parametrised recorder-phase list): add `_phase_retarget_record`.
  4b. `tests/consolidation/test_executor_phase_boundary.py`: add `"_phase_retarget_record(run)"` before `"_phase_merge_lanes(run)"` in `expected_order`.
  5. Run the wider consolidation and terminus suites that touch the executor:
     ```
     .venv/bin/python -m pytest tests/consolidation -n 6 --dist loadfile -q
     .venv/bin/python -m pytest tests/terminus/test_rollback_door.py tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_target_override_recorded_target_unwritable.py tests/terminus/test_protected_target_preflight.py tests/terminus/test_repro_4985.py tests/terminus/test_repro_4991.py -n 6 --dist loadfile -q
     ```
- **Files**: as listed.

## Test Strategy

Above, plus:
```
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_commit_scope_owner.py tests/architectural/test_guard_capability_call_sites.py -n0 -q
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy <touched src files>
```
Keep `_run_lane_based_consolidation`'s complexity at or below 15. Extract `_build_retarget_record(...)` rather than growing the function.

## Risks & Mitigations

- **`UNEXPLAINED_BRANCH_MOVE` on the next run.** Every move inside the phase must be recorded: the decorator for the post tips, and `advance_branch_ref` (Mission branch) inside `reporting_advance_intents`. The commit on `<b>` via `commit_merge_bookkeeping` is recorded by the decorator's post-tip capture. Test both with a re-run after a failure.
- **Kill window.** A kill between the commits and `_persist_retarget_committed` resumes as `UNEXPLAINED_BRANCH_MOVE`. This residual is accepted and is documented by WP05 in the ADR amendment.
- **Characterization tests** that kill "before the first lane merge" patch `executor._phase_merge_lanes`. The new phase runs before it but is a no-op without a retarget, so those tests are unaffected. Verify.
- **Lane staleness:** the Mission-branch retarget commit touches `meta.json`. A lane that also touched `meta.json` becomes stale (`stale_check.py:84`) and auto-rebases, and its moved tip then refuses at the gate. Pin in a unit test that the explicit-lanes fixtures do not hit this (lanes there never touch `meta.json`), and note it as a residual otherwise.
- **`test_no_write_side_rederivation.py`** scans `phase_advance.py`: never walk `.path.parent.parent`; use the composed paths.
- **Complexity of `entry_preflight` functions.** Extract a `_retarget_mode(...)` helper.

## Review Guidance

- The rollback authority is the only undo, with no new restore call.
- A plain `--target` is byte-identical.
- Both copies of the record are written on lanes; the coord case writes `<b>` only.
- The status surface fix removes the old target from the snapshot.
- Mypy and ruff were run.
- `_persist_retarget_committed` is a module-level function in `phase_advance` (the WP04 contract), and `executor._phase_retarget_record` is patchable.

## Progress & Status

`spec-kitty agent tasks add-history WP03 --note "..."`; `spec-kitty agent tasks mark-status T0xx --status done --mission consolidate-retarget-01M7M5JA`.
