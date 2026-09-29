---
work_package_id: WP02
title: Single snapshot + CAS rollback authority (core)
dependencies: []
requirement_refs:
- C-007
- FR-003
- FR-007
- FR-010
- FR-011
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-5338-consolidation-claim-rollback-integrity
merge_target_branch: issue-5338-consolidation-claim-rollback-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-5338-consolidation-claim-rollback-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5338-consolidation-claim-rollback-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidation-claim-rollback-integrity-01M3PD1T
base_commit: 28d6b38d0d32d97409d23ad7f4be3ddb2db28a23
created_at: '2026-09-29T13:21:42.417458+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - Foundation
history:
- at: '2026-09-29T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/rollback.py
- tests/consolidation/test_rollback_authority.py
- tests/consolidation/test_state_snapshot_fields.py
- tests/git/test_restore_branch_ref_resync.py
- tests/terminus/lanes_fixture.py
- tests/terminus/test_lanes_fixture_smoke.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/git/ref_advance.py
- tests/architectural/test_destructive_op_routing.py
- tests/consolidation/test_rollback_authority.py
- tests/consolidation/test_state_snapshot_fields.py
- tests/git/test_restore_branch_ref_resync.py
- tests/terminus/lanes_fixture.py
- tests/terminus/test_lanes_fixture_smoke.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Single snapshot + CAS rollback authority (core)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE: no heavy full suites during the mission

During implement and **every WP review**, you AND every implementer/reviewer subagent you dispatch must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission or to CI (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission consolidation-claim-rollback-integrity-01M3PD1T` and the Activity Log for a `review_ref`; if present, every feedback item is your TODO list.

---

## Objectives & Success Criteria

Build the **single** consolidation rollback authority (operator decision DM `01M3PD3VP1YTQ4D17HT96JA0T2`: CAS ref restore, not revert) as a self-contained, fully unit-tested component. **No executor wiring in this WP** (WP03 wires it; WP04 uses it for `--abort`).

Done means:
- `restore_branch_ref` can optionally resync every worktree that has the branch checked out, with the same dirty-check-before-move discipline `advance_branch_ref` uses, via ONE shared helper (`_resync_checkouts`), and the destructive-op census gate stays green (allowlist re-keyed with rationale).
- `ConsolidationState` gains `pre_mutation_refs` and `post_mutation_refs` (branch → sha), loading older records without them.
- `consolidation/rollback.py` provides `capture_pre_mutation_snapshot`, `record_post_mutation_tips`, `rollback_to_snapshot` → `RollbackReport`, and `RollbackReport.render()`, honouring `contracts/rollback-authority.md` guarantees 1–5.
- A reusable LANES real-CLI fixture builder exists in `tests/terminus/lanes_fixture.py`.

## Context & Constraints

- Read: `spec.md` (FR-003, FR-007, FR-010, FR-011), `plan.md` IC-03, `research.md` D2–D4 + D8, `data-model.md`, `contracts/rollback-authority.md` (all under `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/`).
- **Census gate** `tests/architectural/test_destructive_op_routing.py` keys its allowlist by `CensusKey(rel, qualname, token_line, op, op_ordinal)`. Today's entry (~:196-206) is `qualname="advance_branch_ref"`, `token_line="reset = _run_git ( worktree , [ , , branch ] , env = env )"`. Moving the `reset --hard` into `_resync_checkouts` changes the qualname → re-key that ONE entry to the new qualname with the same rationale (plus one sentence: "shared by advance_branch_ref and restore_branch_ref(resync_checkouts=True); both dirty-check before the ref moves"). Do not add a second allowlist entry; do not add any raw `reset --hard` anywhere else.
- `restore_branch_ref` docstring (ref_advance.py:~532-536) says callers own resync and "intentionally retain worktree files for diagnosis" — keep that as the DEFAULT (`resync_checkouts=False`) and amend the docstring for the opt-in.
- Layering: `git/ref_advance.py` must not import `coordination` (it takes `is_residue` injected). `consolidation/rollback.py` may import `specify_cli.coordination.coherence.is_toolchain_generated_churn` and pass it.
- **C-001**: do not edit #5359-touched functions (none of this WP's files are #5359-touched except none — `state.py`, `ref_advance.py`, `rollback.py` are free).
- Complexity ≤ 15 per function; mypy strict clean on new code; no suppressions.

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks; see `lanes.json`)
- **Planning base branch**: `issue-5338-consolidation-claim-rollback-integrity`
- **Merge target branch**: `issue-5338-consolidation-claim-rollback-integrity`

Start with `spec-kitty agent action implement WP02 --agent claude --mission consolidation-claim-rollback-integrity-01M3PD1T`; run tests from the lane worktree so the lane's `src` is imported.

## Subtasks & Detailed Guidance

### Subtask T006 – Extract `_resync_checkouts` (behaviour-preserving, own commit)

- **Steps**:
  1. In `src/specify_cli/git/ref_advance.py`, factor the worktree scan + pre-move dirty check + post-move `reset --hard` out of `advance_branch_ref` (~:483-523) into two cooperating private pieces, e.g.:
     - `_checkouts_ready_for(repo_root, branch, new_sha, env, is_residue) -> list[Path]` — lists worktrees with `refs/heads/<branch>` checked out (not detached), computes `_target_tree_paths`, raises `RefAdvanceDirtyWorktreeError` on `_dirty_entries` (BEFORE any ref move);
     - `_resync_checkouts(checkouts, branch, env, *, context: str)` — the `reset --hard <branch>` loop (the one census-allowlisted literal), raising `RefAdvanceError` with the existing #1826 repair hint.
  2. `advance_branch_ref` calls them with identical ordering (ff-check → ready → CAS update-ref → resync). Error messages unchanged.
  3. Re-key the census entry (see Context). Run `tests/architectural/test_destructive_op_routing.py` (NAMED gate) — must pass, including its self-mutation tests.
  4. Run existing ref_advance tests: `grep -rl "advance_branch_ref\|ref_advance" tests/git tests/consolidation tests/lanes | head` and run those files. Commit: `refactor(git): extract checkout readiness/resync from advance_branch_ref (tidy-first)`.

### Subtask T007 – `restore_branch_ref(..., resync_checkouts=False, is_residue=None)`

- **Steps**:
  1. Signature: `restore_branch_ref(repo_root, branch, restored_sha, *, expected_current_sha, resync_checkouts: bool = False, is_residue: Callable[[str], bool] | None = None, env: dict[str, str] | None = None) -> None`.
  2. When `resync_checkouts`: `checkouts = _checkouts_ready_for(repo_root, branch, restored_sha, env, is_residue)` BEFORE the CAS `update-ref` (a dirty checkout raises `RefAdvanceDirtyWorktreeError`, nothing moved); then the existing CAS `update-ref <ref> <restored> <expected_current>`; then `_resync_checkouts(...)`. Non-fast-forward is allowed (this is the rollback counterpart).
  3. Default path byte-identical to today (other callers: `core/mission_creation.py:~553`, `cli/commands/.../mission_create.py:~178`, executor target rollback).
  4. Tests `tests/git/test_restore_branch_ref_resync.py` on real temp repos (live-verified behaviour, research D8 / residual-hunt item 4):
     - branch checked out in the primary checkout AND in a linked worktree, advanced by 2 commits (add `new.txt`, delete `gone.txt`); restore with resync → HEAD == index == worktree == restored sha in both; `new.txt` gone, `gone.txt` back; an untracked `.kittify/` dir survives.
     - dirty tracked change in a checkout → `RefAdvanceDirtyWorktreeError`, ref NOT moved.
     - residue path excluded via `is_residue` → restore proceeds.
     - CAS mismatch (`expected_current_sha` stale) → `RefRestoreError`, ref not moved.
     - default `resync_checkouts=False` → ref moves, checkout untouched (documents the "reverse diff staged" hazard).

### Subtask T008 – State fields + `reconciliation_passed_for_tip`

- **Steps**:
  1. `ConsolidationState` (`state.py:~87-171`): add `pre_mutation_refs: dict[str, str] = field(default_factory=dict)` and `post_mutation_refs: dict[str, str] = field(default_factory=dict)`; include in `to_dict`, load in `from_dict` with `{}` when absent or not a dict of str→str (fail closed to `{}` + treat as "no snapshot"; never truthiness-coerce).
  2. Add a pure module function `reconciliation_passed_for_tip(state: ConsolidationState, current_target_sha: str) -> bool` = `bool(current_target_sha) and state.reconciliation_passed_target_sha == current_target_sha`. (WP03 makes `executor._resume_reconciliation_already_passed` delegate to it — do not edit executor here.)
  3. Tests `tests/consolidation/test_state_snapshot_fields.py`: round-trip; absent keys; malformed values; predicate truth table (empty sha, mismatch, match).

### Subtask T009 – `src/specify_cli/consolidation/rollback.py` (the single authority)

- **API** (keep functions small; ≤ 15 complexity each):
  ```python
  class BranchOutcomeKind(StrEnum): RESTORED, ALREADY_AT_SNAPSHOT, NOT_RESTORED
  @dataclass(frozen=True) class BranchOutcome: branch; kind; snapshot_sha; observed_sha; expected_sha | None; reason: str | None
  @dataclass(frozen=True) class RollbackReport:
      outcomes: tuple[BranchOutcome, ...]; refused_verified_landing: bool; reason: str | None
      @property fully_restored -> bool   # not refused and every outcome RESTORED/ALREADY
      @property advanced_branches -> tuple[str, ...]
      def render(self) -> str            # the ONLY source of rollback text (FR-009)
  def snapshot_branches(repo_root, lanes_manifest, *, coord_ref: str | None) -> dict[str, str]
  def capture_pre_mutation_snapshot(repo_root, state, lanes_manifest, *, coord_ref: str | None) -> dict[str, str]
  def begin_attempt(repo_root, state) -> None
  def record_post_mutation_tips(repo_root, state) -> None
  def rollback_to_snapshot(repo_root, state, *, target_branch: str) -> RollbackReport
  ```
  (Take primitives, not `_MergeRunState`, so `--abort` can call it with only a `ConsolidationState` + manifest; WP03 passes values from `run`.)
- **Anchors (corrected, post-tasks finding 10)**: `executor._resolve_pre_mutation_target_sha` (:~2001) and `_resolve_pre_mutation_coord_sha` (:~2091, also writes `pre_interrupt_lane_tips`) already persist the legacy anchors BEFORE this capture runs; the capture READS them as seeds and is the single writer of `pre_mutation_refs` only (do not claim it writes the legacy fields).
- **Capture** (`capture_pre_mutation_snapshot`):
  - Branches: `lanes_manifest.target_branch`, `lanes_manifest.mission_branch`, `coord_ref` when not None, and EVERY lane's branch in the manifest **including `lane-planning`** — resolve lane branch names the way the executor does (`lane_created_branch` / manifest lane helpers; grep `def lane_created_branch`). Keys are short branch names, deduped (coord topology: mission_branch may equal the coord ref; LANES: `lane-planning`'s branch resolves to the target branch — same key once).
  - SHAs: seed the target from `state.pre_mutation_target_sha` and the coord ref from `state.pre_mutation_coord_sha` when already persisted (resume of an older record); otherwise `git rev-parse --verify` the live tip. Missing lane branches are skipped (not snapshotted) and returned in a separate list for the caller to warn about.
  - If `state.pre_mutation_refs` is already non-empty → return it unchanged (never recapture — FR-003).
  - Persist via `save_state`.
- **Per-attempt restore targets (post-tasks BLOCKER 2)** — `begin_attempt(repo_root, state) -> None`, called at the end of every attempt's claim (fresh AND resume): for each snapshotted branch `b` with live tip `A`, previous-attempt post tip `P0 = state.post_mutation_refs.get(b)` and snapshot `S`: `restore_targets[b] = S if A in {S, P0} else A` (an advance that consolidation itself produced is undone to the snapshot; a change someone else made between attempts — e.g. the operator fixing the carrier lane — is KEPT). Persist `state.restore_targets` and reset `state.post_mutation_refs = {}` for the new attempt. Add `restore_targets: dict[str, str]` to `ConsolidationState` in T008 (same back-compat rules).
- **Post tips** (`record_post_mutation_tips`): for every key in `pre_mutation_refs`, read the live tip; store in `state.post_mutation_refs` (overwrite each call); save.
- **Rollback** (`rollback_to_snapshot`) — order matters:
  1. No snapshot (`pre_mutation_refs` empty) → report with `reason="no pre-mutation snapshot recorded (pre-fix record)"`, `fully_restored=False`, no ref touched.
  2. FR-011 guard: if `reconciliation_passed_for_tip(state, live target sha)` → `refused_verified_landing=True`, touch nothing. If any snapshotted branch no longer resolves → same refusal (reason names the branch).
  3. Per branch, with `R = restore_targets.get(b, snapshot)`, `P = post_mutation_refs.get(b)`, `L = live`:
     - `L == R` → ALREADY_AT_SNAPSHOT (covers branches the run never moved, e.g. lane branches: `consolidate_lane_into_mission` only moves the mission branch);
     - `P is None` (no attempt in flight for it) → UNCHANGED_BY_RUN — never restored, never counts against `fully_restored` (post-tasks BLOCKER 2: otherwise an operator's lane fix after a completed rollback makes `--abort` sticky);
     - `L != P` → NOT_RESTORED (reason `"moved by another actor since this run"`, observed=L, expected=P);
     - else `restore_branch_ref(repo, b, R, expected_current_sha=P, resync_checkouts=True, is_residue=is_toolchain_generated_churn)` → RESTORED(P→R); `RefRestoreError` / `RefAdvanceDirtyWorktreeError` / `RefAdvanceError` → NOT_RESTORED with the error text.
     Add `UNCHANGED_BY_RUN` to `BranchOutcomeKind`.
  4. Only if `fully_restored` (every outcome RESTORED / ALREADY_AT_SNAPSHOT / UNCHANGED_BY_RUN, not refused): clear `mission_number_baked=False`, `completed_wps=[]`, `reconciliation_passed_target_sha=None`, `post_mutation_refs={}`, and `pending_coord_reconcile=None` when the coordination ref was RESTORED; `save_state`. Keep `pre_mutation_refs` and `restore_targets` (a later `--resume`/`--abort` must see them).
  5. Idempotent: a second call → all ALREADY_AT_SNAPSHOT.
- **render()**: e.g.
  ```
  Rollback to the pre-consolidation snapshot:
    restored  kitty/mission-x-01ABCDEF  04431ce → 7449419
    unchanged develop                   (already at 35f6333)
    NOT restored lane-a branch …  observed 1234abc, expected 5678def — moved by another actor since this run
  ```
  and a verified-landing line: "Kept the landing verified by an earlier reconciliation (target at <sha>); nothing was rolled back." Never the words "no refs/worktrees were mutated".

### Subtask T010 – Unit tests for the authority (real temp repos)

- `tests/consolidation/test_rollback_authority.py`, building small real repos with `git` subprocess (no mocks for git): target + mission branch + 2 lane branches; snapshot; advance target & mission branch (commits), record post tips; then:
  - full restore → RESTORED × 2, ALREADY × 2; `fully_restored`; bookkeeping cleared; checkout resynced (primary checkout on target).
  - CAS conflict: after post tips, commit again on the mission branch (another actor) → NOT_RESTORED with reason "moved by another actor" and `expected == state.post_mutation_refs[branch]`, branch SHA unchanged, bookkeeping NOT cleared.
  - operator fix between attempts: full restore, then rewrite a lane branch with plain git, then `begin_attempt` + rollback → the lane is UNCHANGED_BY_RUN / kept at the operator's commit; a later attempt that advances nothing on it never reverts the fix.
  - restore_targets rule truth table (A==S → S; A==P0 → S; otherwise A).
  - no post tip for a branch (no attempt in flight) → UNCHANGED_BY_RUN, unchanged, does not block `fully_restored`.
  - verified-landing: `reconciliation_passed_target_sha` == live target → refused, nothing moved.
  - deleted snapshotted branch → refused, nothing moved.
  - dirty tracked change in the primary checkout → NOT_RESTORED (not moved).
  - pre-fix record (no snapshot) → no-op report.
  - capture: never recaptures when already set; LANES dedupe (planning lane → target key once); missing lane branch skipped.
  - idempotence; `render()` snapshot tests (never contains "no refs/worktrees were mutated").
- NFR-001 (mandatory, analysis U1): one test asserting a 4-lane rollback (4 branches restored with resync) completes < 2 s using `time.monotonic`; record the measured time in the Activity Log. Not a `timing`-marked test — a plain generous bound.

### Subtask T011 – LANES real-CLI fixture builder

- **Steps**:
  1. Create `tests/terminus/lanes_fixture.py` from the live-verified reference `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/research/lanes_fixture_reference.py.txt` (it wraps the coord builder's primitives into `build_lanes_mission`: `meta.json` `"topology": "lanes"` with no `coordination_branch`, `lanes.json` `mission_branch = mission_branch_name(slug, mission_id=...)`, mission branch created at the bootstrap commit, lanes cut from it, no `CoordinationWorkspace.resolve`).
  2. Keep the two verified traps as asserted preconditions/comments: (a) the target must be an UNPROTECTED branch (use `develop`) — with `main` a LANES run crashes after the squash (filed as #5385); (b) WP frontmatter must NOT carry `agent:` (else `_run_birth_cutover` seeds claim events onto the target log after `done`).
  3. Expose the same attribute names `plant_canceled_commit` / `run_terminus` need (the reference keeps `m.coord_branch` = mission branch) so those helpers work unchanged. Import from `tests.terminus.conftest`; do NOT edit `conftest.py` (#5359 edits it). Prefer its PUBLIC helpers; where the reference uses private ones (`_run`, `_git`, `_approve_events`), wrap them in ONE local adapter function at the top of `lanes_fixture.py` so a #5359 rename breaks one place.
  3b. WP05 needs a planning-lane variant (post-tasks finding 6): parameters `with_planning_lane_wp: bool = False`, `planning_depends_on_code: bool = True`, `approve_planning_wp: bool = True` (WP05 passes False so the planning WP stays claimable), and `target_branch: str = "develop"` — do NOT hard-assert the target is not `main` (WP05's protected-`main` claim case needs it; document the #5385 consolidate trap instead).
  4. `tests/terminus/test_lanes_fixture_smoke.py`: build → `resolve_topology` returns LANES; no coordination branch exists; `spec-kitty consolidate --dry-run` (or a plain happy-path consolidate) exits 0. Mark `integration`, `git_repo`.

## Test Strategy

Run (record counts in the Activity Log):
- `PWHEADLESS=1 .venv/bin/python -m pytest tests/git/test_restore_branch_ref_resync.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_state_snapshot_fields.py tests/terminus/test_lanes_fixture_smoke.py -q`
- existing ref_advance/state tests you found in T006/T008 (by file), and `tests/consolidation -m "fast or unit"` fast tier
- NAMED gates: `tests/architectural/test_destructive_op_routing.py`, `tests/architectural/test_merge_pipeline_ratchets.py` (AC-B3 no raw update-ref outside ref_advance), `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_dead_symbols.py` (new public symbols must have callers — WP03/WP04 add them; if the gate flags them now, keep them private-by-convention or add them to `__all__` only when the gate allows; note the resolution)
- `.venv/bin/ruff check` + `ruff format --check` on touched files; `.venv/bin/mypy` on `rollback.py`, `state.py`, `ref_advance.py`.

## Risks & Mitigations

- Census re-key mistakes → run the named gate incl. its self-mutation tests.
- Resync clobbering operator work → dirty check BEFORE the move; `is_residue` only for toolchain churn.
- Two sources of truth for anchors → capture is the single writer; legacy fields are projections.

## Review Guidance

- Reviewer ≠ implementer. Verify the CAS expected value is always a RECORDED post tip (never the live tip) — SC-005's premise.
- Verify guarantees 1–5 of `contracts/rollback-authority.md` each have a test.
- Verify `advance_branch_ref` behaviour unchanged (existing tests green) and exactly one census entry re-keyed.
- HARD RULE respected.

## Activity Log

- 2026-09-29T13:00:00Z – system – Prompt created.
