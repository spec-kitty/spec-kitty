---
work_package_id: WP02
title: Record-anchored rollback authority (#5686)
dependencies: []
requirement_refs:
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-010
- NFR-001
- NFR-004
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T11:37:33.660422+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Authority
history:
- at: '2026-10-05T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/rollback.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/consolidation/state.py
- tests/consolidation/test_rollback_authority.py
- tests/consolidation/test_state_snapshot_fields.py
- tests/consolidation/test_merge_state_unit.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Record-anchored rollback authority (#5686)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show python-pedro`) to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also run `spec-kitty charter context --action implement --json` and apply it.

---

## Objectives & Success Criteria

`consolidation/rollback.py` is the single rollback authority. After this WP, every restore target and every compare-and-swap expectation it uses comes from the persisted record. The authority never adopts a live tip it cannot explain. The design is in `kitty-specs/rollback-anchor-authority-01M45VSA/data-model.md` and is the contract for this WP. Read it fully.

Done when:
- `SPEC_KITTY_RUN_P0_REPRO=1 pytest tests/consolidation/test_rollback_anchor_p0_repro.py::test_second_abort_never_reports_restored_over_an_unrecorded_landing` passes with the test **unchanged**. It was red on the base; record the red run first. Do NOT edit the repro file, which WP01 owns. WP03 removes the marker once both lanes have landed.
- `save_state` is atomic (NFR-001).
- The new fields round-trip and load fail-closed (NFR-004).
- Every behaviour in data-model.md "Derived values" has a focused unit test.

## Context & Constraints

- Spec: FR-003, FR-004, FR-006, FR-007, FR-008, FR-010, NFR-001, NFR-004. Data model: `data-model.md`. Grounding: `research/code-grounding.md` §2 and §7.
- Constraints:
  - C-001: no new restore path. `_restore_one` stays the only `restore_branch_ref` caller.
  - C-002: no destructive recipe text.
  - C-006: `rollback.py` may not be imported by `git/ref_advance.py`. WP03 wires a sink into git plumbing and calls the functions you expose here.
- Keep `__all__` in `rollback.py` accurate. Add every new entry point other modules call.
- Complexity ≤ 15 per function. mypy clean, with no new suppressions.
- WP01 runs in parallel and owns `phase_gate.py` and the gate tests; don't touch them. WP03 (after you) wires `run_state.py`, `executor.py`, `phase_claim.py` and `ref_advance.py`. Expose clean functions for it and do **not** edit those files.

## Branch Strategy

- **Strategy**: lanes. Use the workspace `spec-kitty implement WP02` prints.
- **Planning base / merge target**: `issue-5686-rollback-anchor`

## Subtasks & Detailed Guidance

### Subtask T006 – Atomic record and new fields (`state.py`)

- Make `save_state` write through `kernel.atomic.atomic_write` (keep `indent=2` JSON and the `updated_at` stamp). This is a tidy-first enabler: commit it on its own first, behaviour-preserving, with a test that the file is replaced atomically. For example, assert that no partial file remains if `json.dumps` raises, or that `atomic_write` is the writer. Keep the test meaningful, not a mock echo.
- Add the fields from data-model.md with their defaults:
  - `unsettled_refs: list[str]`
  - `advance_intents: dict[str, list[str]]`
  - `released_refs: dict[str, str]`
  - `release_reasons: dict[str, str]`
- Loaders (fail closed, never raise from `from_dict`):
  - `released_refs` / `release_reasons` → add them to `_REF_MAP_FIELDS`.
  - `advance_intents` → a new `_intent_chains_or_empty`: a dict of str → list[str] with ≥ 2 entries, else `{}`.
  - `unsettled_refs` → a list of str. A malformed value loads as a sentinel meaning "every run-movable branch unsettled". Implement it as a dedicated loader returning `["*"]`, and have the authority treat `"*"` as "all".
  - Document each in the dataclass comments like the neighbouring fields.
- Tests: `tests/consolidation/test_state_snapshot_fields.py` (round trip, absent keys → defaults, malformed → fail-closed values).

### Subtask T007 – `begin_attempt` classification

- Replace `_restore_target(snapshot, previous_post, attempt_start)` with a pure classifier, for example `_classify(previous_target, effective_post, live, unsettled) -> tuple[str, bool]` returning (restore target, unexplained):
  - live ∈ {previous_target, effective_post} → (previous_target, False)
  - not unsettled → (live, False)   # a move made between attempts on a settled branch (ADR A2)
  - else → (previous_target, True)
- `begin_attempt(repo_root, state, *, own_moves: Mapping[str, str] | None = None) -> list[str]` returns the unexplained run-movable branches.
  - `own_moves` maps branch → the tip it had *before* this process's own pre-claim steps (the coord-strand heal, attestations); WP03 passes it. A branch whose live tip differs from `own_moves[b]` was moved by this process. Classify it by its pre-move tip `O`:
    - if `O` was its restore target T, re-anchor (target = live, drop the post), as today;
    - if `O` was the effective post (unreconciled run content), KEEP T and carry the live tip as the post, so that content stays restorable and is never laundered into the restore target (post-tasks squad HIGH);
    - otherwise the branch is unexplained.
  - Lane branches keep the current behaviour. They are report-only, but their restore targets are still set as today.
  - When the list is non-empty: change **nothing** in the record (no restore-target updates, no intent clearing, no unsettled change). Return the list; the caller refuses. It must not raise: the #5686 repro calls `begin_attempt` directly.
  - When the list is empty: set restore targets, carry posts for branches at their effective post, clear all intents, set `unsettled_refs` to every run-movable branch, then save.
- Add a read-only `unexplained_branches(repo_root, state) -> list[tuple[str, str, str]]` (branch, restore target, live) using the same classifier without mutating anything. WP03 calls it before the heal and the attestations.

### Subtask T008 – Intent chains and the effective post

- `note_advance_intent(repo_root, state, branch, old_sha, new_sha) -> None` persists fail closed (it lets `save_state` errors propagate):
  - only for run-movable snapshotted branches; ignore others;
  - if the chain for `branch` exists and its last entry == `old_sha`, append `new_sha`; otherwise start `[old_sha, new_sha]`.
- `_expected_tip(state, branch)` = recorded post, else restore target (default: the snapshot).
- `_effective_post(state, branch, live)`: live if the branch's chain base == `_expected_tip` and live ∈ chain[1:]; else the recorded post.
- `clear_advance_intents(state, branches) -> None` (no save; the caller saves). WP03's recorder uses it per branch.
- Use `_effective_post` in `begin_attempt`, in `unexplained_branches` and in `_rollback_branch`.

### Subtask T009 – `_rollback_branch`, settle/unsettle, release outcome

- In `_rollback_branch`, replace `post = state.post_mutation_refs.get(branch)` with the effective post. An adopted intent restores by CAS with `expected=live`, restore to the restore target.
- Add `BranchOutcomeKind.KEPT_BY_OPERATOR`:
  - It is in `_OK_KINDS` but not RESTORED.
  - Render it as `kept       <b>  (released by operator: <reason>; at <sha>; may contain this consolidation's unverified changes)`.
  - It applies only when the computed outcome would be NOT_RESTORED for an existing run-movable branch and `state.released_refs.get(b) == live`.
  - Never apply it to a branch that would be restored or already at its target.
- Add `release_branch(state, branch, live_sha, reason)` to record a release (no save; WP04 calls it under its own validation), and `run_movable_branches(state)` (public) so WP04 can validate names.
- `begin_attempt` (non-refusing path) also clears `released_refs` / `release_reasons`; a release belongs to one `--abort`. Settle/unsettle expand the malformed-record `"*"` sentinel to the run-movable set.
- Update the module docstring's guarantees list and residual note to the new model.
- After computing the outcomes in `rollback_to_snapshot`:
  - settle (remove from `unsettled_refs`) every branch whose outcome is RESTORED / ALREADY_AT_SNAPSHOT / KEPT_BY_OPERATOR;
  - ensure every NOT_RESTORED run-movable branch is in `unsettled_refs`;
  - save the record even when not fully restored (today it saves only on a full restore; keep the full-restore `_clear_bookkeeping`, and extend it to clear `advance_intents`, `unsettled_refs`, `released_refs` and `release_reasons`).
- Add `settle_branch(repo_root, state, branch)` (saves). WP03 calls it for the target on a reconciliation PASS.
- Report: a RESTORED outcome whose expected value came from an adopted intent should say so (e.g. `restored   main  abc1234 -> def5678 (adopted interrupted advance)`). Add a `BranchOutcome` field for it.

### Subtask T010 – Re-pin tests

- `tests/consolidation/test_rollback_authority.py`:
  - `test_restore_target_truth_table` → re-pin to the new classifier, covering every row of the classification (including `unsettled` × explained/unexplained). Keep the old rows as the cases where the previous target is the snapshot.
  - `test_begin_attempt_drops_the_post_tip_of_a_branch_moved_between_attempts` → re-pin (stale): a foreign commit on an **unsettled** branch is now unexplained (`begin_attempt` returns it, the restore target is unchanged, and `rollback_to_snapshot` reports NOT_RESTORED and keeps the commit). Add a sibling test for the settled case (after a full restore, a between-attempts move is kept as the new restore target), so A2 stays pinned.
  - New tests:
    - intent adoption (chain base == expected → RESTORED via CAS against live);
    - intent with a foreign base (base ≠ expected → NOT adopted, NOT_RESTORED);
    - a chain of two advances with the kill after the first write (live == new₁ → adopted);
    - FR-007, three attempts with the operator commit M kept as the restore target;
    - KEPT_BY_OPERATOR, both applied (NOT_RESTORED branch) and ignored (restorable branch);
    - settle/unsettle bookkeeping;
    - `unexplained_branches` is read-only.
  - Existing tests that call `begin_attempt` then advance then `begin_attempt` again without a rollback in between now see the branch as unsettled. Re-pin only where the new rule legitimately changes the outcome, and record each re-pin with a one-line reason in the activity log.
- Run the #5686 repro with `SPEC_KITTY_RUN_P0_REPRO=1` (green); the marker removal happens in WP03. Add tests for all three `own_moves` cases.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_state_snapshot_fields.py tests/consolidation/test_merge_state_unit.py tests/consolidation/test_executor_rollback_wiring.py tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py -q
uv run --frozen pytest tests/consolidation tests/terminus -q -n auto --dist loadfile
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/state.py
```
Classify every red you see as yours or the base's (CLAUDE.md baseline-red gotcha) by running the same test on the base commit.

## Risks & Mitigations

- `rollback_to_snapshot` now saves on partial restores. Check that `--abort`'s "record kept" flow (`cli/commands/consolidate.py`) still reads correctly. That is read-only for you; WP04 owns the CLI.
- Terminus tests that assert state fields: run `tests/terminus` and fix only what your semantics legitimately change, with a re-pin rationale.

## Review Guidance

- Red-before-green for the #5686 repro.
- Every branch of the classifier and of `_effective_post` is unit-tested, including a positive control on the same fixture.
- No restore-path additions. Complexity ≤ 15.

## Activity Log

- 2026-10-05T12:00:00Z – system – Prompt created.
- 2026-10-05T12:07:18Z – claude – shell_pid=8059 – T006 tidy-first: red pin d264db9b (test_save_state_never_leaves_a_partial_record: FAILED on base, the record was truncated at '"unserializable": '); atomic save_state 64025e82 (green, 84 passed in test_merge_state_unit + test_state_snapshot_fields).
- 2026-10-05T12:07:22Z – claude – shell_pid=8059 – Red run (base 22fb3642): SPEC_KITTY_RUN_P0_REPRO=1 pytest tests/consolidation/test_rollback_anchor_p0_repro.py::test_second_abort_never_reports_restored_over_an_unrecorded_landing -> 1 failed (target outcome already_at_snapshot over the unrecorded landing). Red pins 1947ce6f: test_rollback_authority.py + test_state_snapshot_fields.py -> ImportError (new API absent). Green fe05907c: 130 passed (both files); the #5686 repro passes unchanged with SPEC_KITTY_RUN_P0_REPRO=1 (1 passed).
- 2026-10-05T12:07:25Z – claude – shell_pid=8059 – Re-pins: (1) test_restore_target_truth_table -> _classify table (old rows kept as the previous-target==snapshot settled cases, plus unsettled x explained/unexplained and FR-007 rows), because _restore_target was replaced by the classifier. (2) test_begin_attempt_drops_the_post_tip_of_a_branch_moved_between_attempts -> test_begin_attempt_refuses_to_re_anchor_an_unsettled_branch_moved_between_attempts: a foreign commit on an UNSETTLED branch is now unexplained (FR-004); the settled sibling test_begin_attempt_keeps_a_move_between_attempts_on_a_settled_branch keeps ADR A2 pinned. No other re-pins.
- 2026-10-05T12:07:29Z – claude – shell_pid=8059 – Design notes: (a) own_moves on a SETTLED branch whose pre-move tip is unexplained re-anchors to live (A2) instead of refusing; it refuses only on an unsettled branch (test_own_move_on_a_settled_branch_re_anchors). (b) rollback drops the intent chain of every branch it settles (fail-closed tightening: a spent proof must never adopt a later foreign move to the same SHA). (c) KEPT_BY_OPERATOR applies only to the pre-restore NOT_RESTORED decisions (unrecorded / moved by another actor), never after a restore attempt failed (e.g. dirty checkout), so a release never keeps a restorable landing. (d) UNSETTLED_ALL='*' exported from state.py.
- 2026-10-05T12:07:32Z – claude – shell_pid=8059 – Suites: uv run --frozen pytest tests/consolidation tests/terminus tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py -n auto --dist loadfile -> 1968 passed, 1 skipped, 5 xfailed, 1 failed. The failure, tests/consolidation/test_issue_2786_revert_failure_split_brain.py::test_unrestorable_coordination_branch_keeps_the_marker_and_the_resume_heals, is green on base 22fb3642 and red on this branch, so it is caused by WP02. In pass 2 the coord branch sits at the foreign tip F, which is unsettled and unexplained, so begin_attempt (correctly) refuses and leaves the record unchanged. phase_claim.py ignores the return until WP03 wires the UNEXPLAINED_BRANCH_MOVE refusal, so the run continues and the door restores coord to the snapshot. HANDOFF TO WP03: after the refusal wiring this scenario must refuse (FR-005), and the test needs a re-pin there (refusal + --release-branch flow). Not editable here (not owned; its correct outcome depends on WP03). ruff check + ruff format --check --force-exclude: clean on the 5 changed files. mypy: 3 errors, the same set as base (platformdirs stub missing -> no-any-return at state.py get_state_path/_is_ancestor), none new. ruff C901 (max 15) clean.
