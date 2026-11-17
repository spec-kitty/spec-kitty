---
work_package_id: WP01
title: Shared seams and retarget verdicts
dependencies: []
requirement_refs:
- FR-002
- FR-008
- FR-011
- NFR-004
- C-001
- C-002
- C-005
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-11-17T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/meta_write.py
- tests/consolidation/test_meta_write.py
- tests/consolidation/test_retarget_verdict.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/meta_write.py
- src/specify_cli/consolidation/mission_number/bake.py
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/coordination/status_transition.py
- tests/consolidation/test_meta_write.py
- tests/consolidation/test_retarget_verdict.py
- tests/consolidation/test_unwritable_recorded_target_verdict.py
- tests/architectural/_load_meta_census.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared seams and retarget verdicts

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission consolidate-retarget-01M7M5JA`). If this WP came back from review, the feedback is your TODO list; record progress with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

This is the foundation for `spec-kitty consolidate --target <b> --retarget` (issue #7692). The WP does three things:

1. **Campsite (behaviour-preserving, first).**
   - Move the meta-write mechanics the mission-number bake owns into a reusable module, so the retarget phase (WP03) reuses them instead of copying them.
   - Fold the duplicated `refuse_protected_target_override(...) or refuse_unwritable_recorded_target(...)` chain into one pure verdict.
2. **Retarget verdicts.** Add the pure refusal for a retarget whose record cannot be written on the new target, plus the two new error codes.
3. **Re-pointable #5385 probe.** The `done`-bookkeeping policy probe can judge a destination other than the one `meta.json` names today.

Done when:
- every existing test that exercises the bake and the #5783 verdict is green, unchanged except where noted;
- the new unit tests pin every branch of the new verdicts;
- ruff, ruff format and mypy are clean on the touched files, and every function has complexity ≤ 15.

## Context & Constraints

- Read first: `kitty-specs/consolidate-retarget-01M7M5JA/spec.md` (FR-002, FR-008, FR-011), `plan.md` (D1, D2, D4), `research.md` (squad findings R1, R2, R4, A5), and `contracts/cli-retarget.md`.
- Charter: single canonical authority, and the campsite standing order (#2). Read `.kittify/charter/charter.md`. Load action doctrine with `spec-kitty charter context --action implement`.
- C-001: the #6464 semantics are unchanged. C-002: a plain `--target` keeps `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`.
- **Share mechanics, never policy.** The bake is fail-open: it surfaces an unbaked number and returns False. The retarget (WP03) is fail-closed. Do not merge their policies.
- Do not change the meta merge driver (`consolidation/drivers.py`).

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:
`spec-kitty agent action implement WP01 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T001 – Extract the shared meta-write mechanics into `consolidation/meta_write.py`

- **Purpose**: one home for the "write `meta.json` under the Mission write lock, keep the before and written bytes, commit it on a branch, undo it by CAS" mechanics, used by the bake today and by the retarget phase in WP03 (squad R1/R2).
- **Steps**:
  1. Create `src/specify_cli/consolidation/meta_write.py` with:
     - `primary_checkout_refusal(main_repo: Path, rel_meta: Path, target_branch: str) -> str | None`: the body of `mission_number/bake.py::_primary_checkout_refusal`, moved verbatim. The message wording stays as it is ("merge target").
     - `locked_update_meta_capturing(feature_dir: Path, mutate: Callable[[dict[str, Any]], bool], *, repo_root: Path | None) -> tuple[bytes, bytes] | None`: generalise `_locked_assign_mission_number`. `mutate` returns True when it changed the dict. Keep the `observe_writes` / `stop_observing_writes` capture and `locked_update_meta(..., validate=False)`. Return `(before, written)`, or None when `mutate` returned False.
     - `undo_meta_write(meta_path: Path, original: bytes, written: bytes, repo_root: Path) -> str | None`: the body of `_undo_primary_bake`.
     - `commit_meta_on_branch(main_repo: Path, branch: str, mission_slug: str, mutate, *, message: str) -> MetaBranchWrite`: extracted from `_write_mission_number_to_branch`. It runs the scratch detached worktree, then `compose_meta_json_path`, the `path_is_under_worktrees` guards, the locked write, `git -c commit.gpgsign=false commit --only -m <message> -- <rel_meta>`, `advance_branch_ref(..., context=mission_residue_context(...))` with the existing `RefAdvanceDirtyWorktreeError` text fold, and `remove_scratch_worktree` in `finally`. Return a small frozen dataclass whose outcome is one of: `written(new_sha)`, `no_meta_on_branch`, `unchanged` (mutate returned False), `refused(reason)`. Keep the existing warnings in the bake's caller, not in the helper.
  2. Make `mission_number/bake.py` call the helpers.
     - Keep the module-level names `_primary_checkout_refusal`, `_locked_assign_mission_number` and `_undo_primary_bake` bound, because `tests/specify_cli/test_remaining_meta_writers.py` patches `bake._primary_checkout_refusal`. Either wrap the shared ones with thin aliases (`_primary_checkout_refusal = primary_checkout_refusal`), or keep tiny wrappers.
     - The bake must call `_primary_checkout_refusal` through its module global so the patch still takes effect.
     - `_write_mission_number_to_branch` uses `commit_meta_on_branch` and maps the outcomes onto its existing return values and log lines. The `no_meta_on_branch` outcome falls through to `_bake_mission_number_on_primary_tree` exactly as today.
  3. **Do not change behaviour.** Every log message, return value and refusal string stays the same.
- **Files**: `src/specify_cli/consolidation/meta_write.py` (new, about 180 lines), `src/specify_cli/consolidation/mission_number/bake.py`.
- **Notes**:
  - The C-005 recorded exception (the pathspec'd `commit --only` in a detached scratch worktree) moves with the code; there must still be exactly ONE such site. `tests/architectural/test_commit_scope_owner.py` accepts a pathspec'd `--only` commit, so run it.
  - `tests/architectural/_load_meta_census.py` maps `(file, function) -> count` for `load_meta` calls. Update the entry for `_write_mission_number_to_branch` if the `load_meta` call moves (T006).

### Subtask T002 – Extract the pure `target_override_verdict` in `preflight.py`

- **Purpose**: the `or` chain is duplicated in `entry_preflight.py` (`_refuse_protected_target_override_or_continue`) and `forecast.py`, and split across two functions in `orchestrator_api/consolidation.py`. Give it one owner (squad R4).
- **Steps**:
  1. Add to `src/specify_cli/consolidation/preflight.py`:
     ```python
     def target_override_verdict(main_repo: Path, mission_slug: str, *, recorded_target: str, effective_target: str, retarget: bool = False) -> Refused | None:
     ```
     - With `retarget=False` (T002): `refuse_protected_target_override(...) or refuse_unwritable_recorded_target(...)`, exactly today's order.
     - With `retarget=True` (filled in by T003): `refuse_protected_target_override(...) or retarget_record_refusal(...)`.
  2. Do NOT edit the call sites here: WP03 owns the entry preflight, and WP02 owns the forecast and orchestrator-api. Keep the two existing functions public and unchanged in signature.
- **Files**: `src/specify_cli/consolidation/preflight.py`.

### Subtask T003 – `retarget_record_refusal` and the two codes

- **Purpose**: FR-011. A retarget is refused before anything moves when its record cannot be committed on the new target.
- **Steps**:
  1. Add the module constants `RETARGET_RECORD_UNWRITABLE`, `RETARGET_RESUME_MISMATCH` and `RETARGET_WITH_ATTESTATION_UNSUPPORTED` (each equal to its own name) next to `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`.
  2. Implement:
     ```python
     def retarget_record_refusal(main_repo: Path, mission_slug: str, *, recorded_target: str, effective_target: str) -> Refused | None:
     ```
     - Return `None` when `effective_target == recorded_target` (FR-012: restating is not a retarget).
     - **Where the record lives (operator ruling 2026-11-17: default-topology Missions are IN scope).** The record is written on every branch whose TREE carries `kitty-specs/<slug>/meta.json`, out of:
       - **the Mission branch:** `lanes.json` `mission_branch`. For a default-topology Mission this is its topic branch, which is also the coordination branch after a `lanes_with_coord` settlement, and the write checkout of a default `single_branch` Mission;
       - **`<b>` itself:** an explicit layout whose `<b>` was cut after the Mission existed.

       Probe both with `git cat-file -e <branch>:kitty-specs/<slug>/meta.json`, reading the manifest through the placement seam (`placement_seam(...).read_dir(MissionArtifactKind.LANE_STATE)`, as `forecast.py` does). If NEITHER carries it, refuse `RETARGET_RECORD_UNWRITABLE` and say where the record is: for example, an explicit coord Mission whose record lives only on its old target, on a `<b>` cut before the Mission existed. This is the only shape that genuinely cannot be written, so state that in the message.
     - **When `<b>` carries the record:**
       - `hold = write_checkout_refusal(main_repo, mission_slug, effective_target, operation=...)` (from `coordination.transaction`). If it is not None, refuse with `RETARGET_RECORD_UNWRITABLE`, including `hold.message`.
       - Then `primary_checkout_refusal(main_repo, rel_meta, effective_target)` (T001), with `rel_meta` from `missions._read_path_resolver.compose_meta_json_path(main_repo, mission_slug).relative_to(main_repo)`. If it is not None, refuse with that reason.
     - **When only the Mission branch carries it:** the root checkout is NOT required to hold the record. The landing carries it to `<b>`. The Mission branch must exist and resolve.
     - Return a small result type, or document the probe, so that WP03 can reuse the same "which branches carry the record" decision: export `retarget_record_holders(main_repo, mission_slug, *, mission_branch, effective_target) -> tuple[str, ...]`. Keep one owner of that rule.
     - Message shape: `"Refusing to retarget the mission from '<recorded>' to '<effective>': its record (meta.json) cannot be committed on '<effective>' in this run: <reason>."`
     - `next_step`: name the concrete fix. For example: "check out `<effective>` in the repository root checkout", "commit or discard the edit to `<rel_meta>`", or "a default-topology Mission cannot be retargeted before its landing; consolidate onto its recorded target".
     - `destination_ref=effective_target`.
  3. Fill the `retarget=True` arm of `target_override_verdict`.
- **Files**: `src/specify_cli/consolidation/preflight.py`.
- **Notes**:
  - Read-only and lock-free, like its #5783 sibling.
  - Check how `Refused` is built in `refuse_unwritable_recorded_target` and copy the field set.
  - `RETARGET_RESUME_MISMATCH` and `RETARGET_WITH_ATTESTATION_UNSUPPORTED` are only defined here; WP03 (the entry preflight) raises them.

### Subtask T004 – Re-pointable #5385 probe [P]

- **Purpose**: D2 and squad A5. On a retarget, the `done`-bookkeeping policy probe must judge the NEW target with the workflow mutation policy's own verdict, never be skipped.
- **Steps**:
  1. In `src/specify_cli/coordination/status_transition.py::status_write_refusal`, add a keyword `destination_ref: str | None = None`. When it is given, pass it to `BookkeepingTransaction.preflight_refusal(destination_ref=...)` instead of `identity.destination_ref`. Default behaviour is unchanged.
  2. In `preflight.py::refuse_protected_status_target`, add a keyword `retarget_to: str | None = None`.
     - When it is given and the door's own resolved destination (`identity.destination_ref`) is the Mission's RECORDED target (a coordination-less topology, so the `done` write goes to the target), pass `destination_ref=retarget_to`.
     - When the resolved destination is the coordination branch, leave it alone.
     - Simplest: compute the recorded target via `resolve_merge_target_branch(main_repo, mission_slug, None)[0]` and compare it with the destination `status_write_refusal` would use. You may need a tiny helper in `status_transition.py` that exposes the resolved destination for a request (`status_write_destination(request) -> str | None`), reusing `_resolve_transaction_entry`.
  3. Document in both docstrings: "a retarget re-points the probe at the new target (#7692); the verdict stays the policy's own (C-001)".
- **Files**: `src/specify_cli/coordination/status_transition.py`, `src/specify_cli/consolidation/preflight.py`.

### Subtask T005 – Remedy text names `--retarget`

- **Purpose**: FR-002 and FR-010. A plain `--target` refusal points at the opt-in.
- **Steps**: in `refuse_unwritable_recorded_target`'s `next_step`, add a third remedy after the existing two: `"or, to make '<effective>' the mission's new recorded target in this run, re-run `spec-kitty consolidate --target <effective> --retarget` (CLI only)."` Keep the existing two sentences byte-identical; existing tests assert them.
- **Files**: `src/specify_cli/consolidation/preflight.py`.

### Subtask T006 – Unit tests (red-first) and census update

- **Purpose**: pin every branch.
- **Steps**:
  1. `tests/consolidation/test_meta_write.py` (new). Cover:
     - `locked_update_meta_capturing`: returns before/written; None when `mutate` returns False.
     - `undo_meta_write`: restores when the file is unchanged; returns a note when another writer changed it.
     - `primary_checkout_refusal`: detached, off-target, untracked, dirty, and clean cases. Use a real `git init` in `tmp_path`.
     - `commit_meta_on_branch` on a real repo: the `written` outcome advances the branch with a one-file commit; `no_meta_on_branch`; `unchanged`.
  2. `tests/consolidation/test_retarget_verdict.py` (new). Write it first and watch it fail on missing names. Cover:
     - `target_override_verdict(retarget=False)` equals today's chain on the same inputs: mock the two refusals and assert the order.
     - `retarget=True`: the #6464 refusal wins; otherwise `retarget_record_refusal`.
     - `retarget_record_refusal`: each refusal reason gives `RETARGET_RECORD_UNWRITABLE`; equal targets give None; a clean checkout on `<b>` gives None.
     - `refuse_protected_status_target(retarget_to=...)` passes the new destination for a coordination-less Mission and leaves a coordination destination untouched. Monkeypatch `BookkeepingTransaction.preflight_refusal` to capture its `destination_ref`.
  3. `tests/consolidation/test_unwritable_recorded_target_verdict.py`: add an assertion that `next_step` contains `--retarget`, and that the two pre-existing sentences are still present.
  4. The `load_meta` call at `_load_meta_census.py:239` (`_write_mission_number_to_branch`) moves to `meta_write.commit_meta_on_branch`. Give it a new census key, then run `tests/architectural/test_lifted_root_meta_fail_closed_census.py` and `tests/specify_cli/test_meta_fail_closed_full_census_contract.py`.
  5. `retarget_record_refusal` arms: neither branch carries the record → refused; only the Mission branch carries it (default-topology shape, root checkout on `<b>` with no Mission directory) → None; `<b>` carries it but is dirty → refused.
- **Files**: as listed.

## Test Strategy

Run all of these:
```
.venv/bin/python -m pytest tests/consolidation/test_meta_write.py tests/consolidation/test_retarget_verdict.py tests/consolidation/test_unwritable_recorded_target_verdict.py tests/specify_cli/test_remaining_meta_writers.py -n0 -q
.venv/bin/python -m pytest tests/consolidation -k "bake or mission_number or preflight or target" -n 6 --dist loadfile -q
.venv/bin/python -m pytest tests/coordination -k "status_write_refusal or preflight" -n 6 --dist loadfile -q
.venv/bin/python -m pytest tests/architectural/test_commit_scope_owner.py tests/architectural/test_guard_capability_call_sites.py tests/architectural/test_no_dead_symbols.py <load-meta census gate> -n0 -q
uv run --frozen ruff check <touched files> && uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
```
`test_no_dead_symbols.py`: `target_override_verdict` and `retarget_record_refusal` have no production caller until WP03 (the entry preflight) and WP02 (the forecast and orchestrator-api). If the dead-symbol gate flags them, note it in the WP history; WP03 adds the callers. Do NOT add an allowlist entry.

## Risks & Mitigations

- **Patched names in existing tests.** Keep the bake's module attributes and route calls through them.
- **Hidden behaviour drift in the bake.** Diff the log strings before and after; the existing bake tests are the oracle.
- **The dead-symbol gate** goes red in this lane until WP02. That is acceptable only inside the lane; the integrated branch must be green.

## Review Guidance

- Verify the extraction is behaviour-preserving: no changed strings, return values or order of git calls.
- Verify there is still exactly one `commit --only` site.
- Verify the #5385 probe is re-pointed, never skipped, and its default behaviour is unchanged.
- Confirm mypy and ruff ran on the touched src files.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T001 --status done --mission consolidate-retarget-01M7M5JA`.
