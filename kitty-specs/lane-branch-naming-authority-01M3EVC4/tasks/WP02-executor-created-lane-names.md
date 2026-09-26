---
work_package_id: WP02
title: Executor stages use the created lane name; resume guard armed
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-006
- FR-012
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
- T036
phase: Phase 2 - Merge executor stages (wave 2)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/merge/executor.py
- tests/merge/test_executor_lane_naming.py
- tests/merge/test_executor_terminus_integrity.py
- tests/integration/test_merge_lane_planning_data_loss.py
authoritative_surface: src/specify_cli/merge/executor.py
create_intent:
- tests/merge/test_executor_lane_naming.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP02 – Executor stages use the created lane name; resume guard armed

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`merge/executor.py` names lanes in several places. Four of them pass a Mission identity, and the rest mix `run.mission_slug` with `run.lanes_manifest.mission_slug`. This WP gives every executor stage **one** source of the created lane branch and worktree, and arms the resume guard:

1. **Helpers** (PD-2), each with focused tests:
   - `_created_lane_branch(lanes_manifest, lane_id) -> str`, keyed on `lanes_manifest.mission_slug`, keeping `planning_base_branch=lanes_manifest.target_branch`.
   - `_created_lane_worktree(main_repo, mission_slug, lane_id) -> Path`, via `predict_lane_worktree`.
2. **FR-004.** `_capture_pre_interrupt_lane_tips` keys every non-canceled, non-planning lane's tip by its **created** branch, and skips lanes whose WPs are all in `run.excluded_canceled_wp_ids` (US2 AS1).
3. **FR-005 (H5, PD-4).** `_enforce_resume_anchor_integrity` refuses a resume when any non-planning, not-fully-canceled lane has no tip under its created branch name. It names `spec-kitty merge --abort` followed by a fresh merge. It applies only when `coord_topology and state.pre_mutation_coord_sha` (where tips are captured and persisted). Canceled-only and planning-only manifests are exempt (US2 AS2–AS3, SC-005).
4. **FR-006.** `_pre_mutation_safety_preflight` inspects **created** worktrees, so a dirty divergent-shape lane worktree refuses the merge (US1 AS4).
5. **FR-006.** Cleanup is first tidied (behaviour-preserving extraction), then removes the created worktrees and branches, and honours retention (US1 AS5, SC-002).
6. The `_phase_merge_lanes` lane-branch compose goes through the helper, behaviour-preserving.

## Context & Constraints

- **Spec**:
  - US1 AS4–AS5 and US2 AS1–AS3.
  - FR-004, FR-005 (coordination-scoped, amended per ADJ-2), FR-006 and FR-012.
  - SC-002 and SC-005.
- **Plan**:
  - PD-2 (manifest slug), PD-4 (H5 scope), PD-14 (upgrade resume → refusal, pinned in WP03).
  - Complexity Tracking: `_phase_cleanup_worktrees_and_branches` goes from CC10 to about 4 via extraction; `_enforce_resume_anchor_integrity` goes from CC5 to about 6.
- **Research Part A**:
  - §3 "FR-004" (`_capture_pre_interrupt_lane_tips`, CC4).
  - §3 "FR-005" (H5 details).
  - §3 "FR-006" table rows `executor.py:2966` preflight, `:2756` cleanup, `:2782`, `:2794`, `:654`.
  - §6 tidy-first extractions.
- **tasks.md deviation 5**: H5 is here (single owner of `executor.py`). **Deviation 2**: `worktree_path` / `worktree_dir_name` require `mission_id` at HEAD, so route through `predict_lane_worktree` (no identity parameter) and leave WP07 nothing to edit in this file.
- **FR-012 constraint**: in `tests/integration/test_merge_lane_planning_data_loss.py` you may migrate `TestRetentionConstraintSurvivesCleanup` (its `worktree_path(..., mission_id=_RETENTION_MISSION_ID, ...)` calls, ≈L1518, L1631, L1729). You must **not edit `TestPlanningArtifactReachesTarget`**; it has to go green with its fixture unedited (WP03 asserts that).
- **Reuse** WP01's `tests/merge/_divergent_shapes.py` fixture (real allocator). Do not fork it. If you need a knob it lacks (for example `with_planning_lane`), add it as a small documented out-of-map edit, or ask for it.

**Implementation command**: `spec-kitty agent action implement WP02 --agent <name>`. It depends on WP01.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves (it bases on WP01's lane).

## Subtasks & Detailed Guidance

### Subtask T030 – Executor created-name helpers; route `_phase_merge_lanes`

- **File**: `src/specify_cli/merge/executor.py`.
- **Steps**:
  1. Add module-private helpers near the other lane helpers:
     ```python
     def _created_lane_branch(lanes_manifest: LanesManifest, lane_id: str) -> str:
         """The lane's CREATED branch (slug + lane id; the Mission identity is not an input, I-1)."""
         return lane_branch_name(lanes_manifest.mission_slug, lane_id, planning_base_branch=lanes_manifest.target_branch)

     def _created_lane_worktree(main_repo: Path, mission_slug: str, lane_id: str) -> Path:
         """The lane's CREATED worktree, from the placement authority (PD-1)."""
         path, _branch = predict_lane_worktree(main_repo, mission_slug, lane_id)
         return path
     ```
     Imports follow the module's existing style; `executor.py` already imports `lane_branch_name` function-locally in several phases. Check that importing `predict_lane_worktree` from `specify_cli.lanes.worktree_allocator` does not create a cycle, and use a function-local import with a rationale if it does. If it still cannot be imported, fall back to `worktree_path(main_repo, mission_slug, mission_id=None, lane_id=lane_id)` inside the helper, and log that WP07 must drop one keyword here (out-of-map for WP07).
  2. `_phase_merge_lanes` (≈L654): replace the local `lane_branch_name(...)` compose with `_created_lane_branch(run.lanes_manifest, lane.lane_id)`. Check equivalence: today it uses `run.mission_slug` and may pass other arguments. Assert `run.mission_slug == run.lanes_manifest.mission_slug` for real runs (PD-2). If a test fixture sets them differently, fix the fixture, not the code.
  3. Unit-test both helpers directly, including `lane-planning` → target branch, and a mismatched-mid8 slug → the created (slug-only) form.
- **Validation**:
  - [ ] The existing `tests/merge/` suites are green.
  - [ ] No behaviour change for modern Missions.

### Subtask T031 – FR-004: tips keyed by the created name

- **Red-first test** (`tests/merge/test_executor_lane_naming.py`, new): build each divergent shape with `_divergent_shapes`, construct the executor run state the way `tests/merge/test_executor_terminus_integrity.py` does, and call `_capture_pre_interrupt_lane_tips(run)`.
  - Assert the returned keys equal the allocator-created branches of every non-planning, non-canceled lane, and that each value equals `git rev-parse` of that branch.
  - **Red on HEAD**: returns `{}` for the divergent shapes, or raises for the short identity.
  - Add a canceled-lane case: a lane whose WPs are all in `run.excluded_canceled_wp_ids` contributes no key, even if its branch exists.
- **Fix** in `_capture_pre_interrupt_lane_tips`:
  - Use `branch = _created_lane_branch(run.lanes_manifest, lane.lane_id)` and drop `mission_id`.
  - Skip fully-canceled lanes (`all(wp in run.excluded_canceled_wp_ids for wp in lane.wp_ids)` with non-empty `wp_ids`). Mirror the predicate already used near L644, and extract it as `_lane_fully_canceled(lane, excluded)` if you use it more than once (T032 does).
  - Update the docstring: "keyed by the lane's created branch (:func:`_created_lane_branch`)". Remove the "mid8 form" claim.
- **Migrate** `tests/merge/test_executor_terminus_integrity.py`. Its helper at ≈L60 builds `lane_branch_name(MISSION_SLUG, lane_id, planning_base_branch=TARGET, mission_id=MISSION_ID)`, and other calls sit at ≈L110 and L121. Move to allocator-built lanes, or to `_created_lane_branch` semantics without the identity. If `MISSION_SLUG` embeds `MISSION_ID`'s mid8, the bytes are identical; still drop the identity. Keep `canonical_mission_id=MISSION_ID` (≈L144) only if T033 keeps that parameter.

### Subtask T032 – FR-005: H5 unanchored-record refusal

- **Red-first tests** (in `tests/merge/test_executor_lane_naming.py`). Drive `_enforce_resume_anchor_integrity(run, coord_topology=True)` with `run.is_resume=True` and `run.state.pre_mutation_coord_sha` set. Cases:
  - `pre_interrupt_lane_tips = {}` with an approved non-planning lane → `typer.Exit(1)`, and the console output names `spec-kitty merge --abort`.
  - A **partial** record (one of two lanes present) → refuse.
  - An **old-form** record keyed under the identity-form branch name, a string literal in the test, never produced by naming code with an identity → refuse (US2 AS2).
  - Canceled-only manifest (all lanes fully canceled) → no refusal (US2 AS3).
  - Planning-only manifest (only `lane-planning`) → no refusal.
  - `coord_topology=False` → no refusal (PD-4).
  - `pre_mutation_coord_sha=None` → H5 not evaluated (the H4 path is unchanged).
  - A complete record keyed by created names → no refusal; H3 CAS runs as before.
  - Red on HEAD: the empty, partial and old-form cases pass silently today.
- **Fix**:
  1. Add `_unanchored_lane_branches(run: _MergeRunState) -> list[str]`: the created branches of non-planning lanes (`is_planning_lane`) that are not fully canceled and whose `_created_lane_branch(...)` key is not in `run.state.pre_interrupt_lane_tips`. Sort deterministically.
  2. In `_enforce_resume_anchor_integrity`, after the H4 block and before the H3 CAS loop, add:
     ```python
     if coord_topology and state.pre_mutation_coord_sha:
         missing = _unanchored_lane_branches(run)
         if missing:
             console.print("\n[red]Error:[/red] cannot resume this merge: the persisted pre-interrupt lane-tip record has no anchor for lane branch(es) " + ", ".join(repr(b) for b in missing) + " (the record is empty, partial, or was written by an older release under a different name). Resuming without an anchor would disarm the resume guard. Run `spec-kitty merge --abort` and start the merge fresh.")
             raise typer.Exit(1)
     ```
     Hoist the remedy phrase "Run `spec-kitty merge --abort` and start the merge fresh." into a module constant: it now appears ≥ 3 times in the function (S1192).
  3. Update the docstring with an **H5** bullet.
- **Complexity**: `_enforce_resume_anchor_integrity` stays ≤ 8.

### Subtask T033 – FR-006: safety preflight inspects created worktrees

- **Red-first**: build a divergent shape, dirty the created lane worktree by writing an untracked file, and call `_pre_mutation_safety_preflight(main_repo, mission_slug, target_branch, lanes_manifest, canonical_mission_id, primary_meta_dir, remove_worktree=True, teardown_coordination=False)`. Assert that `DestructiveOpRefused` (the type raised by `assert_worktree_clean`) is raised. **Red on HEAD**: the identity-form path does not exist, so the dirty worktree is skipped.
  - Also cover `_pre_mutation_safety_preflight_with_recovery` if that is the entry point `_run_lane_based_merge` uses (≈L3360). Test at whichever level is pre-existing and cheapest.
- **Fix**: in the lane loop, `wt_path = _created_lane_worktree(main_repo, lanes_manifest.mission_slug, lane.lane_id)`. Use the manifest slug (PD-2).
- **Retire the identity parameter if unused**. `canonical_mission_id` may now be unused in `_pre_mutation_safety_preflight`. If it is, remove it from the signature and from the callers (≈L3090, `_pre_mutation_safety_preflight_with_recovery` ≈L3360–3384, and the orchestration around ≈L3537–3633), all within `executor.py`. Keep `canonical_mission_id` wherever it serves event fields, marker paths or locks; only its lane-naming use goes. Update the tests that pass it.
- **Complexity**: unchanged (CC6).

### Subtask T034 – Tidy-first: extract the cleanup helpers (no behaviour change)

- **Purpose**: charter campsite / tidy-first. `_phase_cleanup_worktrees_and_branches` is CC10; separate the structure change from the behaviour change.
- **Steps**: extract, **without changing behaviour**:
  - `_remove_lane_worktrees(run)`: the worktree-removal loop and the context tombstone loop, gated by `run.remove_worktree`.
  - `_delete_lane_branches(run)`: the lane-branch deletion loop, gated by `run.delete_branch`.

  `_phase_cleanup_worktrees_and_branches` becomes three calls: `_remove_lane_worktrees`, `_delete_lane_branches`, `_cleanup_mission_branch_and_coordination`. Move the long comments (T005, T012, #4753, FR-005/LC-6, #3131) with their code.
- **Commit this separately** from T035, so the reviewer sees a pure move. Run `tests/merge/` and `tests/integration/test_merge_lane_worktree_safety.py`; they must be green, unchanged.
- **Tests**: add focused tests for each extracted helper, covering both the gated-on and gated-off paths (Sonar coverage for new helpers).

### Subtask T035 – FR-006: cleanup removes the created worktrees and branches

- **Red-first**: merge, or run cleanup directly on a divergent shape with `remove_worktree=True, delete_branch=True`. Assert that afterwards no allocator-created worktree dir exists, no created lane branch exists, and each lane's workspace context is tombstoned (US1 AS5, SC-002). **Red on HEAD**: the worktree loop uses `mission_id=run.baseline_mission_id`, so divergent worktrees are orphaned.
  - Retention: with `remove_worktree=False` / `delete_branch=False` (via `retain_*` or `--keep-*`), the created worktree and branch remain.
- **Fix**:
  - In `_remove_lane_worktrees`, `wt_path = _created_lane_worktree(run.main_repo, run.lanes_manifest.mission_slug, lane.lane_id)`.
  - The tombstone loop uses `_created_lane_worktree(...).name` instead of `worktree_dir_name(run.mission_slug, mission_id=None, …)`. It must be the same string as the one `save_context` wrote, which is the `{slug}-{lane}` form; assert that in a test.
  - `_delete_lane_branches` uses `_created_lane_branch(run.lanes_manifest, lane.lane_id)`.
  - Check whether `run.baseline_mission_id` is still used for non-naming purposes (event fields ≈L1506, L1852, L1863). If so, keep it; it just stops feeding lane naming.
- **After this subtask**, the alias-aware AST scan of `executor.py` must show **0** lane-naming calls that carry a `mission_id` keyword. At most one `mission_id=None` may remain, inside `_created_lane_worktree`, as the documented fallback.

### Subtask T036 – Migrate owned tests, quality gates, blast radius

- `tests/integration/test_merge_lane_planning_data_loss.py`: migrate **only** `TestRetentionConstraintSurvivesCleanup`'s identity-keyed `worktree_path` calls to `predict_lane_worktree`, or to the allocator output of the lanes the fixture created. `git diff` must show **no** change inside `class TestPlanningArtifactReachesTarget`. Observe and record whether that class is green now; WP03 asserts it.
- `tests/merge/test_executor_terminus_integrity.py`: done in T031/T033.
- Run the Test Strategy commands and record the exact commands plus counts.

## Test Strategy

- **Red-first**: T031, T032, T033 and T035 fail on HEAD through the pre-existing executor entry points (`_capture_pre_interrupt_lane_tips`, `_enforce_resume_anchor_integrity`, `_pre_mutation_safety_preflight`, `_phase_cleanup_worktrees_and_branches`). Record the red runs.
- **Real git** plus WP01's real-allocator fixture. Old-form tip keys are **test literals**.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/merge/test_executor_lane_naming.py tests/merge/test_executor_terminus_integrity.py -q
.venv/bin/python -m pytest tests/merge/ -q
.venv/bin/python -m pytest tests/integration/test_merge_lane_worktree_safety.py tests/integration/test_merge_lane_planning_data_loss.py tests/integration/test_merge_primary_checkout_safety.py -q
.venv/bin/python -m pytest $(grep -rl "merge.executor\|merge import executor\|_run_lane_based_merge" tests --include=*.py | tr '\n' ' ') -q
make test-fast
```

- **NFR gates**:

```bash
.venv/bin/ruff check src/specify_cli/merge/executor.py tests/merge/test_executor_lane_naming.py tests/merge/test_executor_terminus_integrity.py
.venv/bin/ruff check --select C901 src/specify_cli/merge/executor.py
.venv/bin/ruff format --check src/specify_cli/merge/executor.py tests/merge/ tests/integration/test_merge_lane_planning_data_loss.py
.venv/bin/mypy src/specify_cli/merge/executor.py tests/merge/test_executor_lane_naming.py
```

- Diff coverage ≥ 90%. Each helper and each H5 arm has a direct test.

## Definition of Done

- [ ] Every executor lane-name use goes through `_created_lane_branch` / `_created_lane_worktree`.
- [ ] Tips are keyed by the created name; canceled lanes are skipped.
- [ ] H5 refuses an empty, partial or old-form record, with every exemption covered.
- [ ] The preflight catches a dirty divergent worktree. Cleanup leaves no orphans, and retention is honoured.
- [ ] The tidy-first extraction was committed separately, with no behaviour change.
- [ ] `TestPlanningArtifactReachesTarget` is untouched.
- [ ] Gates are clean; `tests/merge/` and `make test-fast` are green.

## Risks & Mitigations

- **Non-naming failures for invalid identities** (post-fix marker `_post_fix_marker_path(mission_id)`, locks): plan Risk 1. If a merge stage crashes for the < 8 identity for a non-naming reason, fold the fix here when it is in `executor.py`; otherwise report it. WP03's end-to-end test is the final proof.
- **H5 false refusal on a legitimate resume**: tips are captured once, before `_phase_merge_lanes`. Make sure the lanes H5 checks are exactly the lanes capture keys (the same predicates). Test by capturing and then resuming with the captured record, expecting no refusal.
- **Resumes from older releases** refuse (the intended upgrade behaviour, PD-14). Communicated via the CHANGELOG (WP08).

## Review Guidance

- H5 is scoped to `coord_topology and pre_mutation_coord_sha` and names `--abort`.
- The capture and H5 predicates are the same function(s).
- T034's commit is a pure move.
- No edit inside `TestPlanningArtifactReachesTarget`.
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
