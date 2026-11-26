---
work_package_id: WP07
title: Approved-lane stale remedy, siblings and halt reason
dependencies:
- WP01
- WP08
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
- T036
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_approved_lane_stale_remedy.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/stale_check.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/consolidation/phase_advance.py
- tests/lanes/test_stale_remediation_cli_command.py
- tests/lanes/test_approved_lane_stale_remedy.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Approved-lane stale remedy, siblings and halt reason

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

When consolidate refuses an approved code lane as stale, the refusal must:

1. name **exactly** the sibling lane(s) whose approved content conflicts with this lane (FR-002), never a lane that does not overlap;
2. say why the in-run auto-rebase did not refresh the lane, with the exact conflicted paths (FR-003): `conflict`, `no_lane_checkout` or `merge_in_progress`;
3. print the runnable re-review route of `contracts/stale-remedy.md` (FR-001): send back, `implement --incorporate <sibling>`, resolve and commit, `for_review`, independent review and approval, `consolidate`;
4. never print a command that refuses an approved work package, and never print `git merge` or `cd .worktrees` (the #7285 A-10 rule, kept by operator ruling DM-01M7WX8AX56E23AXBZRWGNX4EM, option b).

Every other caller (a planning lane, a lane with no approved WP, the lifecycle sync point, any caller that passes no `approved_wp_ids`) gets today's text byte-for-byte (US1 AS3).

Also: `phase_advance` records the run's own auto-rebase move in `ConsolidationState.lane_rebase_moves` on **every** auto-rebase merge, not only when the lane later consolidated (R-03; consumed by WP03's rollback).

Done means: T032 red tests green, the existing A-10 tests still green unchanged, each printed command runs on the two-lane conflicting fixture (T036), quality gates clean.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`; `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (US1, FR-001..FR-003), `plan.md` (IC-04), `research.md` (R-01, R-02, R-03), `data-model.md` (`StaleCheckResult`, `SiblingLane`), `contracts/stale-remedy.md` (the exact ordered text), `tasks.md`.
- Squad evidence: `squads/01-pre-spec-and-post-specify.md`; architect F1/F12/F15 and reviewer findings on FR-001/FR-002/FR-003.
- **Integrity invariants** (bind this WP even though it changes no verdict):
  - C-001: the remedy never suggests attributing a resolution without review. It names re-review.
  - C-002: no new flag, attestation or override is introduced; the remedy only prints existing lifecycle commands plus WP08's `--incorporate`.
  - C-004: the route names an *independent* review approval; do not print `--force` on the approval step.
  - C-006 single authority: reuse `approved_bound.move_back_command` (`src/specify_cli/consolidation/approved_bound.py:95-97`) for the send-back line. One remedy renderer: `stale_check._stale_remediation`. The orchestrator-api (WP09) reaches the same renderer through `consolidate_lane_into_mission`; do not add a second wording there.
  - Fail closed: a probe failure while naming siblings or conflicted paths must never shrink the answer silently. When a probe fails, name every candidate lane / every overlapping path and say the list could not be narrowed.
- `stale_check.py` stays pure and status-free (its module docstring and the A-10 docstring at `stale_check.py:157-177`). All approval knowledge arrives as arguments.
- `lanes/consolidation.py` is pinned by `tests/architectural/test_merge_pipeline_ratchets.py` (AC-F1: every `subprocess.run` carries `env=`, no bare `os.environ`). Use kernel git helpers (`kernel.git.listing.merge_tree`, `log_paths`), not a new `subprocess.run`.
- Recorded leeway (tasks.md): WP01 adds one read-only accessor `registered_merge_driver_specs()` next to `merge_driver_attribute_lines()` (`lanes/consolidation.py:533`). WP01 is a dependency of this WP, so the accessor is in your base: do not remove or rename it; keep your edits away from the `_MERGE_DRIVERS` block (`:71-151`) and do not place the new sibling helper next to `merge_driver_attribute_lines()`.
- **The one public sibling helper (fixed here; WP09 calls it too)**:
  ```python
  # src/specify_cli/lanes/stale_check.py
  @dataclass(frozen=True)
  class SiblingCandidate:
      lane_id: str
      branch: str
      tip: str  # the pre-run tip to measure from

  # src/specify_cli/lanes/consolidation.py
  def sibling_candidates_before(
      lanes_manifest: LanesManifest,
      lane_id: str,
      *,
      integrated_lane_ids: Collection[str],
      pre_run_tips: Mapping[str, str],
  ) -> tuple[SiblingCandidate, ...]:
      """Code lanes that precede *lane_id* in manifest order, are in *integrated_lane_ids*, and have a tip in *pre_run_tips* (keyed by lane branch)."""
  ```
  Pure (no git, no status read): order and filter only. Both callers call it and pass the result as `sibling_candidates=` to `consolidate_lane_into_mission`: `phase_advance._phase_merge_lanes` (T035, with the run's pre-run tips) and `orchestrator_api/consolidation.py` (WP09, with its `lane_tips`). The narrowing of candidates to real siblings (a git read per candidate) is private to `lanes/consolidation.py` (`_narrow_siblings`, T034 step 4); nobody else re-implements it.
- **The one public renderer**: `stale_check.render_stale_remediation(result: StaleCheckResult, lane: ExecutionLane, lane_branch: str, mission_branch: str, *, mission_slug: str | None = None, approved_wp_ids: frozenset[str] | None = None, done_wp_ids: frozenset[str] = frozenset()) -> str`. `_stale_remediation` (`stale_check.py:150`) delegates to it with `approved_wp_ids=None` (today's text). `check_lane_staleness` (`:39-46`) keeps its current signature and output; it takes no approval keyword.
- Terminology: Mission, consolidate / lane consolidation, "incorporate". Never "feature", never "sync" in new prose (existing identifiers such as `lifecycle_sync` stay).

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP07 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Current code at HEAD (read before editing)

- `src/specify_cli/lanes/stale_check.py`
  - `StaleCheckResult` (`:30-36`): `is_stale`, `stale_files`, `remediation`. Note the field is `stale_files`, not `overlapping_files` as `data-model.md` says. Keep `stale_files`; do not rename (callers: `lanes/consolidation.py:342`, orchestrator-api).
  - `check_lane_staleness` (`:39-93`) computes `overlap` and calls `_stale_remediation` (`:92`).
  - `_mission_side_changes` (`:96-111`) returns **paths only** (`log_paths(..., remerge_merges=True)`).
  - `_reentry_command` (`:144-147`) and `_stale_remediation` (`:150-197`): the planning-lane branch (`:178-189`) and the code-lane A-10 text (`:190-197`).
- `src/specify_cli/lanes/consolidation.py`
  - `_try_auto_rebase_if_stale` (`:228-247`): returns `stale` unchanged when the worktree is missing (`:239-240`, the `no_lane_checkout` case) and **discards the `AutoRebaseReport`** when it did not succeed (`:244-247`).
  - `consolidate_lane_into_mission` (`:265-360`): stale check at `:328`, the refusal text at `:342`.
- `src/specify_cli/lanes/auto_rebase.py` (owned by WP02, read only here)
  - `AutoRebaseReport` (`:127-150`): `attempted`, `succeeded`, `classifications`, `halt_reason`.
  - `_abort_with_failure` (`:774-801`): when the guarded abort refuses, the merge is **left in progress** (`:789`).
  - `attempt_auto_rebase` (`:991`): classification stops at the **first** `Manual` file, so `classifications` never lists every conflicted path.
- `src/specify_cli/consolidation/phase_advance.py`
  - `_record_own_auto_rebase` (`:198-210`) and `_phase_merge_lanes` (`:371-432`): `lane_before`/`mission_before` read at `:418`, `consolidate_lane_into_mission` at `:419`, and the move recorded **only** on `lane_result.success` (`:420-421`).
- `src/specify_cli/consolidation/lane_cleanup.py::own_auto_rebase_move` (`:217-236`): exact-shape check `parents == [before, mission_before]`.
- `src/specify_cli/consolidation/run_state.py`: `approved_wp_set` (`:299`), `claim_inputs` (`:303`), `validated_lane_tips` (`:344`). `ApprovedWpCommitSet.approved` keys are the claimed WP ids (`reconciliation_claim_types.py:151`).
- Second caller: `src/specify_cli/orchestrator_api/consolidation.py:793` (WP09 passes the new keywords; your signature must keep its current positional call working).

## Subtasks & Detailed Guidance

### Subtask T032 – Red tests first

- **Purpose**: pin the approved-lane remedy, exact sibling naming, the halt reasons, and the unchanged non-approved text before any production edit. Every test here must fail at HEAD for the stated reason.
- **Files**: `tests/lanes/test_approved_lane_stale_remedy.py` (new), `tests/lanes/test_stale_remediation_cli_command.py` (add tests; do not weaken the four existing ones at `:76-118`).
- **Fixture**: reuse the shape of `_stale_repo` in `test_stale_remediation_cli_command.py:47-73` (a coordination branch, one lane worktree under `.worktrees/`, real git). Extend it in your new file to three lanes:
  - lane-a and lane-b each edit adjacent lines of `src/shared.txt` so `git merge-tree --write-tree lane-b <mission>` exits 1 after lane-a is merged into the Mission branch. Assert that precondition with `kernel.git.listing.merge_tree(...)` (`conflicted` non-empty) inside the fixture, so the test cannot pass on a non-conflicting setup.
  - lane-c edits `src/other.txt` only (the exact-set negative control).
  - one path both lane-a and lane-b touch that merges cleanly (`src/clean.txt`, edits far apart): it is overlapping but must NOT appear in `conflicted_paths`.
- **Tests to write (all red today)**:
  1. `test_approved_lane_remedy_names_sibling_and_route`: call `lanes.consolidation.consolidate_lane_into_mission(repo, slug, "lane-b", manifest, approved_wp_ids=frozenset({"WP02"}), sibling_candidates=sibling_candidates_before(manifest, "lane-b", integrated_lane_ids={"lane-a"}, pre_run_tips={<lane-a branch>: <lane-a tip>}))` (this exact function; the lane-b worktree exists, so the auto-rebase runs and halts on the conflict) and assert on `result.stale_check.remediation`, in order, each line of `contracts/stale-remedy.md`: the stale line naming `lane-a` only; the halt line; the "conflict resolution on an approved lane is new content" line; `spec-kitty agent tasks move-task WP02 --to in_progress --mission <slug>`; `spec-kitty agent action implement WP02 --mission <slug> --incorporate lane-a`; the resolve-and-commit line; `move-task WP02 --to for_review`; the independent-review line; `spec-kitty consolidate --mission <slug>`. Red because the parameters do not exist.
  2. `test_approved_lane_remedy_has_no_raw_git_and_no_bare_implement`: assert `"git merge" not in`, `"cd .worktrees" not in`, and that every `agent action implement` occurrence carries `--incorporate` (A-10 kept under option b).
  3. `test_sibling_set_is_exact`: lane-c is never named; lane-a is named once even when it touched two overlapping paths.
  4. `test_conflicted_paths_are_exact`: `result.conflicted_paths == ("src/shared.txt",)`; `src/clean.txt` is in `stale_files` but not in `conflicted_paths`.
  5. `test_halt_reason_no_lane_checkout`: remove the lane-b worktree; `halt_reason == "no_lane_checkout"`; the remedy says the command below recreates the checkout.
  6. `test_halt_reason_merge_in_progress`: start `git merge` in the lane-b checkout and leave it conflicted before consolidating (the state WP08's `--incorporate` leaves on a conflict); `halt_reason == "merge_in_progress"`; the remedy names the checkout and says to finish or abort it first; and `attempt_auto_rebase` was NOT called (spy on it).
  6b. `test_operator_half_resolved_merge_survives_consolidate`: as test 6, but the operator has already written half-resolved bytes into the conflicted file (not committed). Run `consolidate_lane_into_mission` (and, end to end, `consolidate --mission <slug> --yes` through `run_terminus`); assert afterwards that the file's bytes in the lane checkout are exactly the operator's half-resolved bytes, `MERGE_HEAD` still exists, and the index still lists the path as unmerged. Red at HEAD: `attempt_auto_rebase` runs `git merge`, lists the operator's unmerged file and goes to `_abort_with_failure` (`auto_rebase.py:774-801`), whose guarded abort may discard the resolution.
  6c. `test_halt_reason_merge_in_progress_when_the_guarded_abort_refuses` (the real cause of FR-003's third reason, if feasible): no merge in progress before the run; an uncommitted operator edit in the lane checkout that is not part of the merge makes `guarded_merge_abort` refuse inside `_abort_with_failure` (`auto_rebase.py:783-789`), so the merge is left in progress; assert `halt_reason == "merge_in_progress"`. If a preflight refuses the dirty checkout before the auto-rebase runs, so this state cannot be reached through `consolidate_lane_into_mission`, do not fake it: record in history why it is not feasible (the exact refusal that fires first) and keep test 6 as the proof.
  7. `test_done_wp_send_back_adds_force`: with `done_wp_ids={"WP02"}` the send-back line ends with `--force --note "<why>"` (spec Edge Cases, contract line 4).
  8. In `test_stale_remediation_cli_command.py`: `test_non_approved_callers_keep_the_a10_text` (a **ratchet**, not a red test: it pins today's text byte for byte and is red only because it calls the new `render_stale_remediation` keyword; label it a ratchet in the red record): same fixture as `_stale_repo`, called with `approved_wp_ids=None` and with `approved_wp_ids=frozenset()` and with a planning lane; assert the remediation string equals today's text exactly (compute the expected string from `_reentry_command` and the literal in `stale_check.py:191-197`). This pins US1 AS3.
- **Edge cases**: a lane with two WPs where only one is approved (route uses the approved one; the placeholder logic of `_reentry_command` must not leak `<WP>` into `--incorporate` lines); a sibling with no recorded approval stamp (name the lane anyway; `--incorporate` refuses it with its own message, WP08).
- **Validation**: run the file, confirm every new test fails (for "unexpected keyword", a missing field, or, for 6b, the lost bytes), record the red output in the WP history (`spec-kitty agent tasks add-history WP07 --note "T032 red: ..."`), with test 8 recorded as a ratchet and 6c either red or "not feasible because ...".

### Subtask T033 – `StaleCheckResult` fields and the approved-lane branch of the pure renderer

- **Purpose**: carry the new facts and render the route, keeping `stale_check` pure.
- **Steps**:
  1. Add to `StaleCheckResult` (append with defaults so existing constructions keep working): `halt_reason: HaltReason | None = None`, `halt_detail: str | None = None` (raw `AutoRebaseReport.halt_reason`, shown only when the reason is not one of the three named cases), `conflicted_paths: tuple[str, ...] = ()`, `sibling_lanes: tuple[SiblingLane, ...] = ()`.
  2. Add `@dataclass(frozen=True) class SiblingLane` with `lane_id`, `branch`, `approval_stamp_sha: str | None`, `paths: tuple[str, ...]` (data-model). `approval_stamp_sha` is display-only; `--incorporate` resolves the stamp itself (WP08), so `None` is acceptable when phase_advance cannot cheaply know it.
  3. `HaltReason = Literal["conflict", "no_lane_checkout", "merge_in_progress", "other"]`. `"other"` is a recorded deviation from data-model.md (which lists three values): `attempt_auto_rebase` has further halts (status-deletion refusal `auto_rebase.py:1019-1030`, sparse cleanup failure, a merge that failed without conflicts). Rendering them as "conflict" would mislead. Record this in the WP history as a design note and print the raw `halt_detail` for `"other"`.
  4. Split `_stale_remediation` into helpers (keep each ≤ 15 complexity): `_planning_lane_remedy` (today's `:178-189`, byte-identical), `_code_lane_remedy` (today's `:190-197`, byte-identical), and `_approved_lane_remedy(result, lane, mission_slug, approved, done)` that builds the ordered lines of `contracts/stale-remedy.md`.
  5. Select the approved branch only when all hold: `approved_wp_ids` is not `None`; `not is_planning_lane(lane)`; `set(lane.wp_ids) & approved_wp_ids` is non-empty. Otherwise return the existing text unchanged.
  6. Send-back line: one per approved WP of the lane, from `move_back_command(wp_id, slug)`. Import it inside the helper (function-local) or at module top after checking `python -c "import specify_cli.lanes.stale_check"` does not create an import cycle (`approved_bound` imports `consolidation.git_probes`, which imports `rich` and `coordination`; `lanes/consolidation.py` already imports `consolidation.git_probes`, so the edge exists, but keep `stale_check` light: prefer the function-local import and say why in a one-line comment).
  7. `--incorporate` line: one per sibling, in the sibling order phase_advance passes (lane consolidation order). No sibling known (empty tuple) → print `--incorporate <sibling lane>` placeholder plus "(the sibling could not be determined; see `spec-kitty agent tasks status`)". Never fall back to the bare A-10 command.
  8. `check_lane_staleness` keeps its exact signature and output (no new keyword). Add the public pure renderer `render_stale_remediation(...)` (signature in Context) and make `_stale_remediation` delegate to it with `approved_wp_ids=None`. Add `SiblingCandidate` (Context) next to `SiblingLane`.
- **Files**: `src/specify_cli/lanes/stale_check.py`.
- **Notes**: keep the module docstring accurate: add one paragraph saying the approved-lane remedy exists, why (#5604, #7754, #7755), and that A-10 still holds.

### Subtask T034 – `lanes/consolidation.py`: keep the report, accept approval facts, name siblings and halt reasons

- **Purpose**: the data that the renderer needs is computed here, once, for both callers (CLI phase_advance and orchestrator-api).
- **Steps**:
  1. `_try_auto_rebase_if_stale` (`:228-247`) returns `tuple[StaleCheckResult, AutoRebaseReport | None, HaltReason | None]` (or a small frozen dataclass). Cases, in this order:
     - worktree missing → `(stale, None, "no_lane_checkout")`;
     - **an operation already in progress in the lane checkout** → probe `MERGE_HEAD`, `REBASE_HEAD` and `CHERRY_PICK_HEAD` BEFORE calling `attempt_auto_rebase` (`git rev-parse -q --verify <name>` in the lane checkout through `kernel.git.run_git(..., check=False)`); when any exists, do NOT call `attempt_auto_rebase` and return `(stale, None, "merge_in_progress")`. Calling it would run `git merge` on top of the operator's unfinished `--incorporate` merge and reach `_abort_with_failure`, whose guarded abort may discard the operator's half-resolved bytes (T032 test 6b). A probe failure (git cannot run) → treat as in progress (skip the attempt; fail toward not touching the checkout);
     - report succeeded → recheck as today, halt `None`;
     - report failed → `halt = "merge_in_progress"` when `MERGE_HEAD` exists in the lane checkout after the attempt (the guarded abort refused and left the merge, `auto_rebase.py:783-789`; probe as above; do not parse the halt text), else `"conflict"` when any classification is `Manual`, else `"other"`.
  2. Add keyword-only parameters to `consolidate_lane_into_mission`: `approved_wp_ids: frozenset[str] | None = None`, `done_wp_ids: frozenset[str] = frozenset()`, `sibling_candidates: Sequence[SiblingCandidate] = ()` (from `sibling_candidates_before`, Context). Add the public `sibling_candidates_before(...)` here (Context signature), away from `merge_driver_attribute_lines()`, with direct unit tests (order, filter by `integrated_lane_ids`, skip a lane with no tip, never the current lane, planning lanes excluded). The positional call at `orchestrator_api/consolidation.py:793` must keep working unchanged.
  3. Compute conflicted paths only when `halt == "conflict"`: `kernel.git.listing.merge_tree(repo_root, branch, mission_branch).conflicted`, minus `is_target_owned_path` paths and minus paths with an `Auto` classification in the report. Rationale: classification stops at the first `Manual` file, so the report alone under-reports. Probe failure (`GitCommandError`) → fall back to `stale.stale_files` and set a flag so the remedy says "conflicted paths could not be computed exactly; listing every overlapping path" (fail toward over-reporting, never silence).
  4. Compute siblings in a private `_narrow_siblings(repo_root, lane_branch, overlap, candidates) -> tuple[SiblingLane, ...]`: for each `SiblingCandidate` other than this lane, `log_paths(repo_root, f"{lane_branch}..{candidate.tip}", pathspecs=overlap)`; non-empty → `SiblingLane(lane_id, branch, None, paths)`. One process per candidate (NFR-001 spirit; candidates are only lanes consolidated before this one). A failed probe → include the candidate (fail toward over-inclusion is noisy but safe for a remedy; the three-lane exact-set test runs on a healthy repo).
  5. Re-render the remediation with the new facts (`dataclasses.replace(stale, ...)` then `render_stale_remediation(..., approved_wp_ids=..., done_wp_ids=...)`), so the refusal text at `:342` carries the route. Keep the `errors=[...]` prefix `Lane {lane_id} is stale: overlapping files ...` unchanged for log compatibility.
  6. Keep `LaneConsolidationResult.stale_check` populated (`:342-344`) with the enriched result.
- **Files**: `src/specify_cli/lanes/consolidation.py` (owned), reads `auto_rebase.py` types only.
- **Validation**: `tests/architectural/test_merge_pipeline_ratchets.py` stays green (no new bare `subprocess.run`).

### Subtask T035 – `phase_advance.py`: approval facts, sibling candidates, record every auto-rebase move

- **Purpose**: the run knows the claim, lane order and pre-run tips; pass them in, and record the auto-rebase move whatever happens next.
- **Steps**:
  1. In `_phase_merge_lanes` (`:371-432`) build once before the loop: `approved = frozenset(run.approved_wp_set.approved) if run.approved_wp_set else None`; `done = frozenset(run.state.completed_wps)`.
  2. Sibling candidates: keep a running set `integrated` of lane ids (consolidated earlier in this loop, or skipped as already integrated at `:410-414`), and a tip map `{**run.validated_lane_tips, **run.state.pre_mutation_refs}` restricted to lane branches (the pre-run tip the claim validated wins). Per lane, call `sibling_candidates_before(lanes_manifest, lane.lane_id, integrated_lane_ids=integrated, pre_run_tips=tips)`; do not re-implement the order/filter here.
  3. Pass `approved_wp_ids=approved, done_wp_ids=done, sibling_candidates=<that result>` to `consolidate_lane_into_mission`.
  4. Move `_record_own_auto_rebase(run, _lane_branch, before=lane_before, mission_before=mission_before)` **before** the `if lane_result.success:` branch so it runs on every outcome (R-03; `own_auto_rebase_move` already returns `None` unless the exact auto-rebase shape is present, so a failed attempt with no merge records nothing). This is what WP03 consumes.
  5. Optional `approval_stamp_sha`: phase_advance must not add a new status read (it is in the scan scope of `tests/architectural/test_coord_read_residuals_closeout.py:258-272`; a `read_events` there must stay coord-aware). Leave `approval_stamp_sha=None` unless a value is already on `run`; do not read the event log here. Record the decision in the WP history.
- **Tests (in `test_approved_lane_stale_remedy.py`)**:
  - `test_auto_rebase_move_recorded_when_lane_stays_stale`: a phase-level test where the auto-rebase merge succeeded but the lane is still stale (or `consolidate_lane_into_mission` returns `success=False` after the merge); assert `run.state.lane_rebase_moves[branch] == [before, after]`. Red today because recording is gated on `success`.
  - `test_phase_passes_approved_ids_and_siblings`: monkeypatch `consolidate_lane_into_mission` in `phase_advance`'s namespace to capture kwargs; assert `approved_wp_ids` equals the claim keys and `sibling_candidates` lists only earlier, integrated lanes in order, and that `phase_advance` obtained them through `sibling_candidates_before` (spy).
- **Edge cases**: `run.approved_wp_set is None` (hand-built runs in older tests) → pass `None`, so the text is unchanged; resume where earlier lanes were skipped as integrated → they still count as candidates.

### Subtask T036 – Execute each printed command on a two-lane conflicting fixture

- **Purpose**: FR-001's "no-op passable: no" clause. A prose-only remedy, or one that prints a command refused for an approved WP, must fail this test.
- **Depends on**: WP08 (`--incorporate`) being merged into your lane (it is a declared dependency; `implement` merges it).
- **Steps**:
  1. Build a coordination Mission with two approved lanes editing adjacent hunks of one file, using the in-process production shell like `tests/terminus/post_approval_support.py:109-151` (`allocate_lane_worktree`, `tests.terminus.mixed_lane_support.transition`, `tests.terminus.canceled_dependency_support._commit_in` / `_approve`). Do not import WP12's support module (it does not exist yet).
  2. Run `consolidate --mission <slug> --yes` through `tests.terminus.conftest.run_terminus`; assert exit 1 and the stale refusal names `lane-a`, `src/pkg/shared.py` and the route.
  3. Parse the printed command lines (lines starting with `spec-kitty `) and run them in order through `run_terminus` (drop the leading `spec-kitty`). Between `--incorporate` and `for_review` perform the human act: write the resolved file in the lane checkout the command printed and `git commit`.
  4. Assert: the send-back exits 0; `implement --incorporate` exits 0 and leaves a merge (or a conflict to resolve, per WP08's chosen exit behaviour); `for_review` exits 0; none of the outputs contains "approved" refusal wording (for example `cannot claim`, `is already in lane: approved`, `--force`) for the approved WP. The review and the final consolidate belong to WP12; stop after `for_review` here.
- **Notes**: mark `pytest.mark.integration`, `pytest.mark.git_repo`. Use `monkeypatch.delenv` for `SPEC_KITTY_NO_NAG`, `SPEC_KITTY_NON_INTERACTIVE` if the CLI behaves differently under them (CLAUDE.md gotcha 5).

## Binding DoD item: incorporate merge-attribute guard (WP08 review item 3, moved here as recorded leeway)

Accepted by the reviewer on 2026-11-20. It is a blocking check in WP07's review and in the final aggregate review.
- WP07's lane contains both WP01's guard and WP08's `src/specify_cli/lanes/incorporate.py`. Edit `incorporate.py` as recorded leeway, with a one-line rationale in history.
- Before `--incorporate` merges, call WP01's `assert_registered_merge_behaviour(repo, <paths changed among HEAD, the sibling stamp and their merge-base>, attributes_source=<pre-run target tip>)` through the SAME shared pinned-config helper WP01 cycle 2 adds (merge.renormalize / filter / directoryRenames pinning or refusal). Do not add a second check.
- On `GitProbeError`, refuse with a new named code, `INCORPORATE_MERGE_ATTRIBUTES_REFUSED`, before any merge. Exit 1, like the other refusals.
- Red first: a real-git test where the lane commits `*.py merge=union` and the sibling stamp conflicts on a `.py` file. Today the merge exits 0 with content neither side wrote. After the fix it refuses with the new code, and nothing is merged.

## Binding scope ruling (operator, 2026-11-25, DM-01M88RZDBP57ZTYJHC5NP0ZH4R). It supersedes every conflicting step above.

Main's #7754/#7755 fix landed under this Mission and is now in WP07's base. It is the single authority for naming siblings and for the remedy text:
- `lanes/stale_check.py`: `SiblingLane(lane_id, branch)`, `find_sibling_lanes`, `refine_stale_result`, `_reopen_step`, `_cause_sentence`, `_refresh_step`, `_stale_remediation`, and `StaleCheckResult.auto_rebase_halt` / `.sibling_lanes`.
- `lanes/consolidation.py`: `_explain_stale`. Both callers reach it through `consolidate_lane_into_mission`: `phase_advance` and `orchestrator_api/consolidation.py:794`.

Do NOT add any of the following:
- `SiblingCandidate`, `sibling_candidates_before`, `_narrow_siblings` or `render_stale_remediation`;
- a second `SiblingLane`;
- new `StaleCheckResult` fields that duplicate the halt reason or the siblings;
- new sibling keyword parameters on `consolidate_lane_into_mission`.

If you truly need more data on main's `SiblingLane`, append optional fields with defaults and record why in history.

WP07 changes only three things:

1. **Refresh step** (restores ruling (b) and A-10). In `_refresh_step`, when siblings are known, replace `git merge <sibling branch>` with one line per sibling: `spec-kitty agent action implement <WP> --mission <slug> --incorporate <sibling lane_id>`. That is WP08's command; it merges at the sibling's approval stamp. Then come, in order:
   - resolve and commit in the checkout that command names;
   - `spec-kitty agent tasks move-task <WP> --to for_review --mission <slug>`;
   - independent review and approval;
   - `spec-kitty consolidate --mission <slug>`.

   Keep these unchanged:
   - main's reopen step, exactly (`move-task <WP> --to planned --review-feedback-file <file>`, plus the re-review cost sentence);
   - main's cause sentence and halt reason;
   - without siblings, main's auto-rebase wording;
   - the planning-lane wording.

   No printed line may contain `git merge` (except a `git merge --abort` back-out) or `cd .worktrees`. The `--to in_progress` send-back line of `contracts/stale-remedy.md` is superseded by main's reopen step; WP13 updates the contract. Red first: change main's tests that assert `git merge <branch>` so they assert the new lines, and record the red run.
2. **FR-009: record every auto-rebase move made during consolidation** with WP02's `auto_rebase_record`, so WP03 can undo it. Verify that the `phase_advance` path, including main's `_explain_stale` route, records each move. Fill only the gaps; never add a second record.
3. **Merge-attribute guard on `--incorporate`**: the binding DoD section above. It now also covers the window-merge probe that WP08 cycle 3 added in `incorporate.py`.
   - Wrap its `merge_own_changed_paths` with WP01's guard and pinned env (`merge_probe_env`).
   - `attributes_source` is the Mission branch tip, read once at the start of `--incorporate`.
   - A guard refusal or a probe error refuses with `INCORPORATE_MERGE_ATTRIBUTES_REFUSED` (fail closed).
   - Red first: a committed `merge=union` on a path that a canceled-window merge touches.

Use WP08's public `wp_attribution.wp_windows` / `window_stamps` and WP01's public helpers. Never import a private helper across modules. Where a step above conflicts with this section, this section wins; record each superseded step in WP history.

## Binding addition: fix the reopen route on protected coordination targets (operator ruling 2026-11-25, DM-01M89KDT5DZQ4DX6ZFX54HY3J3; #7861)

Option (b). Keep main's #7754 reopen text exactly as it is: `spec-kitty agent tasks move-task <WP> --to planned --review-feedback-file <file> --mission <m>`. Fix the CLI so the command works on a coordination Mission (`lanes_with_coord`) whose target is a protected `main`.

1. The verdict-evidence commit made by `move-task --to planned --review-feedback-file` must land on the allowed branch, which is the coordination branch, and never on the protected target. Route it through the existing placement/commit seam (`commit_for_mission`, the coordination partition). Do not add a second commit path, and do not set any env-var bypass.
2. After that reopen, `spec-kitty agent action implement <WP> --mission <m> --agent <agent>` must find the review-feedback artifact on the surface it reads, and must re-enter the lane.
3. Red first, on the two real-git fixtures that reproduced the bug: WP08's `build_route` fixture and T036's fixture. Record each red run.
   - Then T036 must run main's exact reopen line end to end through the CLI, with no move-back substitute, and the Mission must land.
4. Fold the `--agent <agent>` token into main's no-sibling re-entry line as well (`_reentry_command`). Every printed `implement` line must run as printed. Pin it with a test.
5. Ownership:
   - Edits to the move-task / review-feedback / commit-routing files are recorded leeway for this WP. Give a one-line rationale per file in WP history and keep each change minimal.
   - If the fix needs a change to the placement seam's routing rules themselves (not just calling them correctly), stop and report before editing.
6. Fail closed. When the coordination surface cannot be resolved, refuse with the existing named error. Never fall back to the protected target.
7. This fixes #7861, which closes with this Mission's PR.

## Test Strategy

Red first (NFR-004). Commands (targeted files only, no directory sweeps):

```bash
uv run --frozen pytest -q tests/lanes/test_approved_lane_stale_remedy.py tests/lanes/test_stale_remediation_cli_command.py
uv run --frozen pytest -q tests/lanes/test_stale_check.py tests/lanes/test_stale_check_contained_change.py tests/lanes/test_stale_check_target_owned.py
uv run --frozen pytest -q tests/lanes/test_auto_rebase_additive.py tests/lanes/test_auto_rebase_target_owned.py tests/lanes/test_auto_rebase_managed_artifact_recognition.py
uv run --frozen pytest -q tests/consolidation/ -k "phase_advance or merge_lanes or rebase_move or lane_cleanup"
uv run --frozen pytest -q tests/orchestrator_api/ -k "consolidat"
uv run --frozen pytest -q tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_commit_scope_owner.py tests/architectural/test_coord_read_residuals_closeout.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py
make test-fast
```

Find other tests that exercise the changed modules with `grep -rl "stale_check\|consolidate_lane_into_mission\|_record_own_auto_rebase" tests/ --include="*.py"` and run those files too. Do not run `make test-full` or bare `tests/architectural/`.

Quality gates (zero findings, no new `# noqa` / `# type: ignore`, complexity ≤ 15 per function):

```bash
uv run --frozen ruff check src/specify_cli/lanes/stale_check.py src/specify_cli/lanes/consolidation.py src/specify_cli/consolidation/phase_advance.py tests/lanes/test_approved_lane_stale_remedy.py tests/lanes/test_stale_remediation_cli_command.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/lanes/stale_check.py src/specify_cli/lanes/consolidation.py src/specify_cli/consolidation/phase_advance.py tests/lanes/test_approved_lane_stale_remedy.py tests/lanes/test_stale_remediation_cli_command.py
uv run --frozen mypy src/specify_cli/lanes/stale_check.py src/specify_cli/lanes/consolidation.py src/specify_cli/consolidation/phase_advance.py
```

## Tracer notes

Code WPs cannot own `kitty-specs/` paths. Record friction, approach and design notes for `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md` with `spec-kitty agent tasks add-history WP07 --note "<trace: design-decisions> ..."`. Expected design notes: the `"other"` halt reason; conflicted paths from `merge_tree` rather than from classifications; `approval_stamp_sha` left `None` in phase_advance and why; fail-toward-over-reporting on probe errors.

## Risks & Mitigations

- **Byte-identity regression for non-approved callers.** Mitigation: T032 test 8 compares the full string; refactor by extraction only.
- **Import cycle `lanes.stale_check` → `consolidation.approved_bound`.** Mitigation: function-local import; verify with a bare `python -c` import.
- **`merge_tree` follows clone-local merge attributes (FR-010).** Acceptable here: the conflicted-path list is remedy text, not a verdict. Do not reuse it for any verdict.
- **Sibling over-inclusion on probe failure.** Safe for a remedy; the exact-set test runs on a healthy repo. Say so in the remedy line.
- **WP09 depends on your signature.** Keep the new parameters keyword-only with defaults, and document them in the docstring. WP09 calls `sibling_candidates_before` exactly as named in Context; do not rename it or make it private.
- **Destroying an operator's in-progress resolution.** Mitigation: the `MERGE_HEAD`/`REBASE_HEAD`/`CHERRY_PICK_HEAD` probe runs BEFORE `attempt_auto_rebase`; T032 test 6b proves the half-resolved bytes survive.
- **WP03 depends on T035.** Recording on every outcome must not record a foreign move: `own_auto_rebase_move` keeps the exact-shape check; do not loosen it.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`):

- **Zero-command pass (FR-001/US1-2).** The test must assert each command is present and must execute them (T036). A remedy that prints prose only must fail.
- **Over-inclusive answers (FR-002/FR-003).** Check the three-lane control: lane-c is not named; `src/clean.txt` (overlapping, merges cleanly) is not in `conflicted_paths`.
- **A-10 kept.** No `git merge`, no `cd .worktrees`, no bare `agent action implement <WP>` without `--incorporate` for an approved code lane; the four existing A-10 tests are unchanged.
- **Non-approved callers unchanged** (US1 AS3): byte comparison, not substring.
- **`done` WPs** get `--force --note` on the send-back line.
- **Recording on every merge** (R-03): the test proves recording when the lane stayed stale; the exact-shape check is untouched.
- **In-progress operations are never touched**: the in-progress probe precedes `attempt_auto_rebase`; test 6b asserts the operator's bytes, `MERGE_HEAD` and the unmerged index entry survive a consolidate. Test 6c is present, or history records why it is not feasible.
- **One sibling helper**: `sibling_candidates_before` is public, called by `phase_advance`; no second order/filter implementation exists. Test 8 is recorded as a ratchet.
- Confirm the implementer ran ruff, `ruff format --check --force-exclude` and mypy on every changed file, and that complexity of `_stale_remediation` helpers and `_phase_merge_lanes` is ≤ 15.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP07 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP07 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
