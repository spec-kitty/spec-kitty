---
work_package_id: WP02
title: Durable auto-rebase record
dependencies: []
requirement_refs:
- FR-005
- NFR-002
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Foundations
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/auto_rebase_record.py
- tests/lanes/test_auto_rebase_record.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/lanes/auto_rebase_record.py
- src/specify_cli/consolidation/lane_cleanup.py
- tests/lanes/test_auto_rebase_record.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 - Durable auto-rebase record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission approved-lane-resolution-route-01M7WW0Z`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: as you address each item, record it with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Every merge that the stale-lane auto-rebase makes on a lane must leave a durable, tool-written record:

```
refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha>   ->   <merge-sha>
```

`lanes/auto_rebase.attempt_auto_rebase` (`src/specify_cli/lanes/auto_rebase.py:991-1119`) is the single writer. It serves all three auto-rebase callers:

- consolidate, via `lanes/consolidation._try_auto_rebase_if_stale` (`lanes/consolidation.py:228-247`), called from `consolidate_lane_into_mission` (`:265`);
- `orchestrator-api consolidate-mission`, through the same `consolidate_lane_into_mission`;
- the implement sync point, `lanes/lifecycle_sync.sync_lane_after_coordination_commit` (`lifecycle_sync.py:169-176`).

The record has exactly two readers later in the Mission:

- WP05 (FR-004): a merge is tool-made, and so exempt from the claim-time `RESOLUTION_MERGE_UNREVIEWED` refusal, exactly when this ref exists and resolves to that SHA;
- WP03 (FR-009): the rollback deletes the ref after it undoes the lane move.

The reconciliation gate NEVER reads it (C-002, C-003): a forged ref can only change which message the operator sees; the gate still refuses unreviewed own content.

Done when:

- a clean auto-rebase merge and an auto-resolved one both write the ref with the exact merge SHA;
- a write failure halts the auto-rebase and leaves no unrecorded tool merge on the lane;
- lane cleanup removes every ref under the lane's prefix when it removes the lane branch, and only then;
- `is_recorded` is true only for that exact SHA under that lane, and raises on a git failure;
- ruff, `ruff format --check --force-exclude` and mypy are clean on every changed file; complexity <= 15 everywhere; no suppressions.

## Context & Constraints

- Read first: `spec.md` (US3 AS3-AS5, FR-005, NFR-002, Edge Cases "Records from earlier releases"), `plan.md` (IC-02), `research.md` (R-03), `data-model.md` ("Auto-rebase record"), `contracts/auto-rebase-record.md`.
- Charter: `.kittify/charter/charter.md`; `spec-kitty charter context --action implement`.
- Integrity invariants:
  - **C-002**: the record never lifts a verdict. Nothing in this WP may be read by `reconciliation_*` or `MergeOutcomeVerifier`.
  - **C-003**: the #7307 post-approval merge rule is unchanged.
  - **C-006**: one writer (`attempt_auto_rebase`), one ref-write authority. Every `refs/spec-kitty/**` write goes through `specify_cli.git.ref_advance.write_bookkeeping_ref` / `delete_bookkeeping_ref` (`git/ref_advance.py:1082-1110`). `tests/architectural/test_merge_pipeline_ratchets.py::test_no_raw_update_ref_outside_ref_advance_helper` fails on any `"update-ref"` literal outside that module.
  - **Fail closed** (NFR-002): a failure to write the record halts the auto-rebase; a failure to READ the record raises (never "not recorded" by accident, never "recorded" by accident).
- **Threat model** (R-03): deliberate local edits to refs are out of model, as for the event log. The SHA-keyed ref is not forgeable by a commit message or by a parent shape: a hand merge whose message imitates `auto-rebase(lane=...)` and a hand merge of the Mission branch into the lane (the same parents a tool merge has, `lane_cleanup.own_auto_rebase_move`, `lane_cleanup.py:217-236`) are both NOT recorded.
- **Layering**: like `lanes/lane_tip.py` (`:13-16`), the new module must never import `specify_cli.consolidation.*`. It imports only `specify_cli.git.ref_advance` and the standard library.
- **Tasks.md wording vs code**: tasks.md says "through the kernel git helpers". `src/kernel/git/` has no ref-write helper; the canonical `refs/spec-kitty/**` writer is `specify_cli.git.ref_advance` (`BOOKKEEPING_REF_PREFIX`, `:1046`), which `lane_tip.py` already uses. Use that. Tasks.md also writes `is_recorded(sha)` / `delete(sha)`: the ref embeds the lane branch, so both functions take the lane branch too.
- Terminology: Mission; lane consolidation; "incorporate"; never "sync" in new text (existing identifiers such as `lifecycle_sync` stay).

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/approved-lane-resolution-route`
- **Merge target branch**: `fix/approved-lane-resolution-route`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command:
`spec-kitty agent action implement WP02 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T006 - Red tests for the record contract

- **Purpose**: pin `contracts/auto-rebase-record.md` before writing any production code.
- **File**: `tests/lanes/test_auto_rebase_record.py` (new), `pytestmark = pytest.mark.git_repo`.
- **Fixtures**: build real repositories the way `tests/lanes/test_auto_rebase_additive.py:37-77` does (`_init_repo`, `_make_lane`, `_make_lane_worktree`). Do not import that module's private helpers; copy the minimal shape. Two shapes:
  - **clean**: the Mission branch and the lane edit different files, so `git merge --no-ff --no-commit` exits 0 (`attempt_auto_rebase`, `auto_rebase.py:1045-1077`);
  - **auto-resolved**: both add a dependency to `pyproject.toml` (the additive classifier rule exercised by `test_auto_rebase_additive.py:188`), so the merge conflicts and `_finalize_auto_rebase` commits (`auto_rebase.py:908-988`).
- **Tests (write them all first; each is red today because no ref is written)**:
  1. `test_clean_auto_rebase_records_the_merge`: after `attempt_auto_rebase(...)` succeeds, the lane HEAD is a merge whose parents are `[lane tip before, mission tip before]`, and `git rev-parse refs/spec-kitty/auto-rebase/<lane-branch>/<head>` prints `<head>`.
  2. `test_auto_resolved_auto_rebase_records_the_merge`: same assertions for the conflict shape.
  3. `test_report_names_the_merge_sha`: `report.merge_sha == <lane head>` on both shapes; `None` on a halted attempt.
  4. `test_halted_auto_rebase_records_nothing` (**control: green at HEAD**, no ref is ever written today; it must stay green): a Manual conflict (two different edits of the same line in a `.py` file) halts; no ref exists under the lane prefix.
  5. `test_already_up_to_date_records_nothing` (**control: green at HEAD**, it must stay green): the lane already contains the Mission tip; no merge commit, no ref.
  6. `test_record_write_failure_halts_and_leaves_no_unrecorded_merge`: monkeypatch `auto_rebase_record.record` to return `False`; the report has `succeeded is False`, a `halt_reason` that names the record, the lane HEAD equals the pre-merge tip, no ref exists under the record prefix, and `refs/spec-kitty/lane-tip/<lane-branch>` equals the pre-merge tip. Run it on both shapes; for the clean shape, simulate the POSIX post-commit recorder hook by writing the lane-tip ref to the merge before the record step (or install the recorder hook in the fixture), so the test proves the undo re-records the tip rather than passing because nothing advanced it.
  7. `test_is_recorded_only_for_the_exact_sha_and_lane`: true for the recorded merge on its lane; false for the same SHA under another lane's branch name; false for a different SHA.
  8. `test_forged_message_merge_is_not_recorded` and `test_hand_merge_of_the_mission_branch_is_not_recorded`: make the two hand merges by plain `git merge` in the lane worktree (one with `-m "auto-rebase(lane=lane-a): 0 conflicts resolved by classifier rules []"`); `is_recorded` is false for both.
  9. `test_is_recorded_raises_on_git_failure`: call it with a non-repository directory; it raises `AutoRebaseRecordError` (a new exception in the module), never returns False.
  10. Cleanup tests are in T009.
- **Validation**: run the file; every test except the controls 4 and 5 fails on HEAD (`ImportError` for the new module counts only for tests 7-9; tests 1-3 and 6 must fail on their assertions, so write them against `attempt_auto_rebase` and read refs with plain `git`, not through the new module). Tests 4 and 5 pass at HEAD: record them as controls, not as red. Record the red run: `spec-kitty agent tasks add-history WP02 --note "T006 red: ..."`.
- **Edge cases to include**:
  - a lane branch name with slashes (`kitty/mission-x-01ABCDEF-lane-a`) produces a valid nested ref;
  - two auto-rebases of the same lane in one test (lane goes stale twice) produce two refs, both readable.
- **Why each is red today**: `attempt_auto_rebase` writes no ref anywhere (the only ref it moves is the lane-tip ref in `_finalize_auto_rebase`, `auto_rebase.py:981-984`), `AutoRebaseReport` has no `merge_sha` field (`:127-147`), and a record failure cannot happen because no record exists.
- **Assertion helpers** (keep them in the test module):
  - `_refs_under(repo, prefix) -> list[str]` via `git for-each-ref --format=%(refname)`;
  - `_parents(repo, sha) -> list[str]` via `git rev-list --parents -n1`;
  - read refs with plain git in tests 1-6, so those tests do not depend on the module under test.
- **Environment**: the auto-resolved shape may need `uv` for a `uv.lock` rule; choose the pyproject additive rule only, which needs no external tool. Set `user.name`/`user.email` in the fixture (the writer's `_git_user_env_ready`, `auto_rebase.py:683-689`, does it too, but the fixture's own commits need it first).
- **Files**: `tests/lanes/test_auto_rebase_record.py`.
- **Parallel?**: no; it defines the contract.

### Subtask T007 - New module `lanes/auto_rebase_record.py`

- **Purpose**: the one module that names, writes, reads and deletes the record.
- **File**: `src/specify_cli/lanes/auto_rebase_record.py` (new).
- **API** (all take `repo_root: Path` first):
  ```python
  AUTO_REBASE_REF_PREFIX = "refs/spec-kitty/auto-rebase/"

  class AutoRebaseRecordError(Exception): ...          # a read could not be answered

  def record_ref(lane_branch: str, merge_sha: str) -> str
  def record(repo_root: Path, lane_branch: str, merge_sha: str) -> bool
  def is_recorded(repo_root: Path, lane_branch: str, sha: str) -> bool
  def recorded_merges(repo_root: Path, lane_branch: str) -> frozenset[str]
  def delete(repo_root: Path, lane_branch: str, merge_sha: str) -> bool
  def delete_for_lane(repo_root: Path, lane_branch: str) -> tuple[str, ...]   # refs that could not be deleted
  ```
- **Steps**:
  1. `record`: `write_bookkeeping_ref(repo_root, record_ref(...), merge_sha, create_only=True)` (`git/ref_advance.py:1082-1097`). If it returns False because the ref already exists with the SAME value (a retried call), treat it as success: re-read with `is_recorded`. Any other False is a failure.
  2. `is_recorded`: `git rev-parse --verify --quiet <ref>`; exit 0 and stdout == `sha` -> True; exit 1 with empty output -> False; any other outcome (OSError, a different exit) -> `AutoRebaseRecordError`. Mirror `lane_tip.read_tip` (`lane_tip.py:139-152`) but do NOT collapse errors into "absent".
  3. `recorded_merges`: one `git for-each-ref --format=%(refname) <prefix><lane-branch>/` call; strip the prefix; raise `AutoRebaseRecordError` on failure, like `lane_tip.recorded_tip_branches` (`lane_tip.py:155-180`). WP05 uses this to read a lane's records in one process (NFR-001).
  4. `delete` and `delete_for_lane`: `delete_bookkeeping_ref` per ref (`git/ref_advance.py:1100-1110`). `delete_for_lane` lists with `recorded_merges` and returns the refs whose delete failed (empty tuple when all went).
  5. Validate inputs: an empty branch or a SHA that is not 40 hex characters raises `ValueError` before any git call. (`write_bookkeeping_ref` already refuses refs outside `refs/spec-kitty/`.)
- **Notes**:
  - no import from `specify_cli.consolidation` (layering, see Context);
  - for-each-ref output is ref names, not paths, so splitting on `"\n"` does not trip `tests/architectural/test_git_path_listing_owner.py` (it flags NUL and `" -> "` splits only); run that gate anyway;
  - module docstring: state the contract in five lines (writer, two readers, never the gate, deletion points) and cite FR-005 / R-03.
- **Validation**: T006 tests 7-9 green; `uv run --frozen mypy src/specify_cli/lanes/auto_rebase_record.py` clean.
- **Edge cases**:
  - `record` called twice for the same SHA: idempotent success;
  - `delete` of an absent ref: success (`git update-ref -d` on a missing ref is a no-op, `ref_advance.py:1103-1104`);
  - `recorded_merges` on a lane with no refs: empty frozenset from a successful listing (distinct from an error).
- **Parallel?**: yes with T009's test writing; T008 and T009 need it.

### Subtask T008 - Write the record in `attempt_auto_rebase`; halt on a write failure

- **Purpose**: the single writer records every merge commit it creates, clean or auto-resolved, before it returns.
- **Steps**:
  1. In `attempt_auto_rebase` (`auto_rebase.py:991`), read two tips BEFORE the merge command at `:1043`:
     - `before`: the lane worktree's `HEAD` (`git rev-parse HEAD` in `worktree_path`);
     - `mission_before`: `git rev-parse <mission_branch>`.
     A failure to read either halts with `attempted=True, succeeded=False` and a `halt_reason` naming the read; no merge is attempted.
  2. Add `merge_sha: str | None = None` as the LAST field of `AutoRebaseReport` (`auto_rebase.py:127-147`). The frozen dataclass and its `__post_init__` invariants (halt_reason iff not succeeded) are unchanged. Keep it additive. No other WP reads this field today (WP07 takes the move from `lane_cleanup.own_auto_rebase_move`, WP05 and WP03 read the durable ref); it is report data, pinned by test 3. Do not add a consumer here.
  3. Extract one helper, for example `_record_tool_merge(context, worktree_path, repo_root, lane_id, branch, before, mission_before, classifications) -> AutoRebaseReport | str`:
     - read the new `HEAD`; if it equals `before` (nothing committed, "Already up to date"), return without recording;
     - check the parents are exactly `[before, mission_before]` (`git rev-list --parents -n1 HEAD`, the shape `lane_cleanup.own_auto_rebase_move` checks, `lane_cleanup.py:229-236`). Any other shape is a bug in the writer: halt;
     - `auto_rebase_record.record(repo_root, branch, head)`; on True return the SHA;
     - on False: undo the merge with `git.destructive_guard.guarded_reset_hard(worktree_path, before, context=context, env=_make_merge_env())` (`destructive_guard.py:405-419`), then re-record the lane work tip with `lanes.lane_tip.record_tip(repo_root, branch)` (`lane_tip.py:66`; it reads the branch head, now `before`): when the POSIX lane-tip recorder hook is installed, the merge commit already advanced `refs/spec-kitty/lane-tip/<branch>` through `post-commit`, and without this call the tip ref would keep naming the undone merge. Then return a failure report whose `halt_reason` is `auto-rebase record could not be written for merge <sha12>; the merge was undone`. If the reset itself is refused (`DestructiveOpRefused`) or fails, the `halt_reason` says the merge `<sha12>` was left on the lane unrecorded and that consolidate will judge it as a hand merge (it then refuses by name if it carries content of its own, which is the fail-closed direction).
  4. Call the helper in BOTH success paths:
     - the clean path, after `conclude_in_progress_op` succeeds (`auto_rebase.py:1063-1070`) and only when `_merge_head_exists` was true;
     - `_finalize_auto_rebase`, after the commit (`:967-979`) and BEFORE `record_tip(repo_root, branch)` (`:984`), so a halted record never advances the lane-tip ref to an undone merge.
  5. Pass `merge_sha=<sha>` into the success `AutoRebaseReport`.
- **Complexity**: `attempt_auto_rebase` and `_finalize_auto_rebase` are already long. Keep each <= 15 by putting the read/verify/record/undo sequence in the helper, and the two pre-merge reads in a second small helper. Check with `uv run --frozen ruff check --select C901`.
- **Red-first**: T006 tests 1-6 go green here; record "T008 green" with counts.
- **Edge cases**:
  - the clean path's merge was concluded but the lane worktree is sparse (`_reapply_sparse_checkout`, `:1055-1060`): the record step runs after the sparse re-apply, so a sparse failure still halts before any record (no record for a merge that is then aborted);
  - `lifecycle_sync` raises `LaneAutoRebaseSyncError` on a failed report (`lifecycle_sync.py:177-186`); a record failure surfaces there with the new `halt_reason` text, with no change to `lifecycle_sync.py` (not owned);
  - an octopus is impossible here (one `git merge <mission_branch>`), so the two-parent check is exact.
- **Validation**:
  - `tests/lanes/test_auto_rebase_additive.py`, `test_auto_rebase_managed_artifact_recognition.py`, `test_auto_rebase_target_owned.py`, `tests/lanes/test_lane_tip_record_points.py` (`test_auto_rebase_commit_records_tip_despite_foreign_hook`, `:172`) and `tests/integration/test_lane_lifecycle_sync.py` stay green;
  - the lane-tip ref still equals the merge on success (record_tip unchanged).
- **Files**: `src/specify_cli/lanes/auto_rebase.py`.
- **Parallel?**: no.

### Subtask T009 - Delete the lane's records in lane cleanup

- **Purpose**: refs under `refs/spec-kitty/` keep their commits alive (they are "keeping refs" for the landed-removal guard, `git/destructive_guard.py:865-866`), so a removed lane must not leave its auto-rebase records behind.
- **Steps**:
  1. `lane_cleanup.MainTodayRemover._delete_branch` (`consolidation/lane_cleanup.py:427-443`): right after `lane_tip.clear_tip(self._repo_root, branch)` (`:442`), call `auto_rebase_record.delete_for_lane(self._repo_root, branch)`.
  2. `lane_cleanup.GuardedLaneRemover.remove` (`:525-565`): inside `if result.branch_deleted:` (`:560-563`), after `clear_tip`, the same call.
  3. Never delete records when the branch was NOT deleted:
     - a missing branch keeps its lane-tip ref by FR-034 (`:432-434`) and keeps its records the same way;
     - a refused delete (`DestructiveOpRefused`, a git refusal, a branch still present, `:435-441`) keeps them;
     - a retained branch (`LaneRetention.delete_branch=False`, `_legs_to_run`, `:262-274`) keeps them.
  4. A record delete failure does not turn a REMOVED lane into a kept one (the branch is already gone; the refs only keep a tool merge reachable). Match the `clear_tip` posture: best effort, but log the refs that remained at debug level so it is diagnosable. Do not swallow `BookkeepingRefError` (a namespace bug must surface).
- **Tests** (in `tests/lanes/test_auto_rebase_record.py`; real repos; process probe injected like `tests/consolidation/test_lane_cleanup_auto_rebase_6736.py:68-71`):
  1. `test_cleanup_removes_the_lane_s_records`: record two merges on lane-a and one on lane-b; `MainTodayRemover.remove` on lane-a deletes both lane-a refs and leaves lane-b's.
  2. `test_guarded_cleanup_removes_the_lane_s_records`: same through `GuardedLaneRemover` with a `LocalTargetAtPass` landing proof (see `test_lane_cleanup_auto_rebase_6736.py:100-115` for `_land` / `_item`).
  3. `test_a_kept_lane_keeps_its_records`: make the delete refuse (a unique commit on the lane, `BRANCH_HAS_UNIQUE_COMMITS`); the refs stay.
  4. `test_a_missing_branch_keeps_its_records`: delete the branch by hand first; cleanup reports REMOVED and the refs stay (FR-034 parity).
- **Why at lane cleanup and not when the WP reaches `done`**: the terminal-transition hook `lanes/claim_base.on_wp_terminal` clears per-WP refs (`claim_base.py:160-180`), but the auto-rebase merge stays on the lane branch until cleanup removes it, and FR-004 must still recognise it on a `--resume` between those two moments. The record's lifetime is the lane branch's lifetime (or the rollback that undoes the merge, WP03).
- **Not this WP**: the rollback-time delete of a single record (`delete(repo_root, branch, sha)`) is called by WP03 from `consolidation/rollback.py`; do not touch `rollback.py` here.
- **Edge cases**: the order matters. Delete the records AFTER the branch delete: during the delete, the records still keep the tool merge reachable, which is what the guard's "no commit only this branch reaches" proof should see.
- **Validation**: the four tests green; `tests/consolidation/test_lane_cleanup_auto_rebase_6736.py`, `test_lane_cleanup_module.py`, `test_lane_cleanup_kept_report.py` and `test_lane_remover_guard_binding.py` unchanged and green; `tests/architectural/test_destructive_op_routing.py` green (the lane remover still binds `guarded_landed_removal` and carries no `--force`, `:776-783`).
- **Files**: `src/specify_cli/consolidation/lane_cleanup.py`, `tests/lanes/test_auto_rebase_record.py`.
- **Parallel?**: yes, after T007.

## Test Strategy

Red first (T006), then T007, T008, T009. Commands (targeted files only):

```bash
uv run --frozen pytest -q tests/lanes/test_auto_rebase_record.py
uv run --frozen pytest -q tests/lanes/test_auto_rebase_additive.py tests/lanes/test_auto_rebase_managed_artifact_recognition.py \
  tests/lanes/test_auto_rebase_target_owned.py tests/lanes/test_lane_tip_record_points.py tests/lanes/test_lane_tip.py \
  tests/integration/test_lane_lifecycle_sync.py
uv run --frozen pytest -q tests/consolidation/test_lane_cleanup_auto_rebase_6736.py tests/consolidation/test_lane_cleanup_module.py \
  tests/consolidation/test_lane_cleanup_kept_report.py tests/consolidation/test_lane_remover_guard_binding.py
uv run --frozen pytest -q tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py
make test-fast
```

No full heavy suites and no bare `tests/architectural/`.

Quality gates:

```bash
uv run --frozen ruff check src/specify_cli/lanes/auto_rebase.py src/specify_cli/lanes/auto_rebase_record.py src/specify_cli/consolidation/lane_cleanup.py tests/lanes/test_auto_rebase_record.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/lanes/auto_rebase.py src/specify_cli/lanes/auto_rebase_record.py src/specify_cli/consolidation/lane_cleanup.py tests/lanes/test_auto_rebase_record.py
uv run --frozen mypy src/specify_cli/lanes/auto_rebase.py src/specify_cli/lanes/auto_rebase_record.py src/specify_cli/consolidation/lane_cleanup.py
```

Complexity <= 15; no `# noqa`, no `# type: ignore`. Record commands and counts in WP history.

**Tracer notes**: this code WP cannot own `kitty-specs/` paths. Record notes with `spec-kitty agent tasks add-history WP02 --note "trace(<tooling-friction|approach|design-decisions>): ..."`. Expected design-decision entries: why a durable ref and not `lane_rebase_moves` (R-03), the undo-on-record-failure choice, the `lane_branch` parameter on `is_recorded`/`delete`, and the deletion points.

## Risks & Mitigations

- **Undoing a committed merge is destructive.** Mitigation: only through `guarded_reset_hard` with the attempt's own abort context (`_abort_context`, `auto_rebase.py:168-181`), and only back to the tip read seconds earlier; a refusal leaves the merge and says so (FR-004 then judges it, fail closed).
- **Raw `update-ref`.** The AC-B3 ratchet fails on any `"update-ref"` literal outside `git/ref_advance.py`. Mitigation: only `write_bookkeeping_ref` / `delete_bookkeeping_ref`.
- **Records keep commits reachable.** A forgotten record pins a merge forever. Mitigation: deletion at cleanup (T009) and at rollback (WP03).
- **Older releases' merges have no record.** By design (spec Edge Cases): FR-004 treats them as hand merges and refuses only when they carry content of their own. Do not add any backfill.
- **Writer drift.** Another code path could create lane merges without recording. Mitigation: this WP makes `attempt_auto_rebase` the only writer; `implement --incorporate` (WP08) deliberately does NOT record, because its merge is reviewed content.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`, FR-005 findings):

- The discriminator is the SHA-keyed ref, never the commit message or the parent shape. Both negative controls (forged message; hand merge of the Mission branch with the tool's parent shape) must be present and must be false.
- The record is written on clean AND auto-resolved merges, and on every caller (the writer is `attempt_auto_rebase`; check no caller bypasses it).
- A write failure leaves no unrecorded tool merge (test 6 asserts the lane tip, not only the report).
- `is_recorded` raises on a git failure; grep the module for any `except` that returns False.
- The reconciliation GATE never reads the record (C-002): `grep -n auto_rebase_record src/specify_cli/consolidation/reconciliation_verifier.py src/specify_cli/consolidation/reconciliation_closed_world.py` is empty. Do not widen this check to `reconciliation*.py`: WP05 legitimately calls `is_recorded` from `reconciliation_bound.py`, which is the claim-time bound, not the gate.
- Confirm mypy ran and passed in addition to pytest.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`), never in this prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
