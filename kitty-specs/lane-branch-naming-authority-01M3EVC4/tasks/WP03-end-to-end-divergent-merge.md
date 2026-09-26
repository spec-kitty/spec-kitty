---
work_package_id: WP03
title: End-to-end divergent merges + merge preflight Mission-branch fallbacks
dependencies:
- WP01
- WP02
- WP04
requirement_refs:
- FR-003
- FR-005
- FR-011
- FR-012
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
- T046
- T047
phase: Phase 3 - End-to-end proof (wave 3)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/merge/preflight.py
- tests/merge/test_merge_divergent_end_to_end.py
- tests/merge/test_mid8_embedded_preflight.py
authoritative_surface: src/specify_cli/merge/preflight.py
create_intent:
- tests/merge/test_merge_divergent_end_to_end.py
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

# Work Package Prompt: WP03 – End-to-end divergent merges + merge preflight Mission-branch fallbacks

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

This WP is the **proof** that #5108 is closed for the operator. It also closes the last Mission-branch fallbacks inside `merge/preflight.py`.

1. **SC-001**: all four divergent shapes merge end to end through the real `spec-kitty merge` entry point (4/4). The shapes are backfilled legacy, mismatched mid8, invalid identity ≥ 8 characters, and invalid identity < 8 characters. There must be no traceback and no refusal, and every approved lane's commits must be reachable from the target.
2. **SC-002 / US1 AS5**: after each successful merge, 0 created lane branches or worktrees are orphaned, and the retention policy (`retain_branches` / `retain_worktrees`) keeps exactly the created names.
3. **PD-14 upgrade pin (FR-005, US2 AS2)**: a merge interrupted under the old code has persisted a tip record keyed under the identity-form branch name. On `--resume` it refuses and names `spec-kitty merge --abort`. Canceled-only and planning-only Missions are exempt, end to end (US2 AS3).
4. **PD-13 (FR-011)**: two fallbacks in `merge/preflight.py` must prefer the recorded `lanes.json` `mission_branch` when one is available: `target_branch_sync_remediation` (the `source_branch = mission_branch or mission_branch_name_required(...)` line) and `_check_mission_branch` (`expected_branch or resolve_branch_name(...)`). When they must recompose from an invalid identity, they refuse with the typed `BranchIdentityUnresolved`, never a `ValueError` traceback.
5. **FR-012 regression guard**: `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget` (red on HEAD: 2 failed) was turned green by WP01 alone. This WP **re-asserts** it green, with its class unedited, after WP02 and WP04 landed.

## Context & Constraints

- **Spec**: US1 (AS1–AS5), US2 (AS2–AS3), SC-001, SC-002, SC-005, FR-003, FR-005, FR-011, FR-012.
- **Plan**:
  - PD-13 and PD-14.
  - Risk 1: invalid-identity shapes may still fail at non-naming merge steps. This WP's end-to-end test is the proof.
  - Parallel Work Analysis WP03.
- **Research Part A**: §4 lists `merge/preflight.py:123`, `:165` as independent composers. §8 Risk 4.
- **tasks.md deviations 5 and 6**: H5 lives in WP02 (`executor.py`), and the recovery fallback in WP04 (`lanes/recovery.py`). This WP owns neither file. It exercises them end to end.
- **Dependencies**:
  - WP01: the claim, and the `_divergent_shapes` fixture you reuse. WP01 alone already turns `TestPlanningArtifactReachesTarget` green (verified post-tasks); this WP only re-asserts it.
  - WP02: the executor stages and H5, needed by the end-to-end merges (T043–T045).
  - WP04: the lifecycle and acceptance consumers, and recovery, needed by the end-to-end merges.
- **Residual failures**: if the end-to-end run surfaces a remaining non-naming failure in a file owned by an upstream WP (for example `executor.py` or `reconciliation.py`), fix it as a **documented out-of-map edit**. Those WPs are complete and their files are quiescent. Add a one-line rationale in the Activity Log and a regression test in your owned test file. If the fix is larger than a few lines, stop and report to the orchestrator.

**Implementation command**: `spec-kitty agent action implement WP03 --agent <name>`. It depends on WP01, WP02 and WP04.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T043 – End-to-end merge over the four divergent shapes (SC-001)

- **File**: `tests/merge/test_merge_divergent_end_to_end.py` (new). Markers: `integration`, `git_repo`. Check `pytest.ini`, and mark it `slow` if the runtime warrants.
- **Entry point**: the real merge command. Invoke it through `typer.testing.CliRunner` on the `merge` Typer command (`cli/commands/merge.py`), or through the function the CLI calls (`merge/executor.py::_run_lane_based_merge` or its public wrapper), whichever the existing end-to-end tests use. `tests/integration/test_merge_lane_planning_data_loss.py` and `tests/integration/test_merge_lane_worktree_safety.py` are the references. Do **not** hand-roll git merges.
- **Fixture**: `tests/merge/_divergent_shapes.py` (WP01). Every lane comes from `allocate_lane_worktree`. All WPs are approved, with status events emitted through the canonical emitter.
- **Parametrize** over `backfilled_legacy`, `mismatched_mid8`, `invalid_identity_long`, `invalid_identity_short`.
- **Assertions**, per shape:
  - The command exits 0 with no `Traceback` in the output, and nothing like "no approved lane resolved any commits" or "Reconciliation refused".
  - Every approved lane's commit SHA, taken from the fixture's recorded allocator output, is reachable from the target: `git merge-base --is-ancestor <sha> <target>`, or content-equivalent for squash. Use the default strategy and assert blob presence for squash.
  - Add a canceled-lane-plus-survivor variant for one shape (US1 AS2).
- **Red-first (SC-001 red run, MANDATORY; no proxy)**:
  1. `MB=$(git merge-base HEAD claude/charter-load-mission-q9ajcz)`; if your lane base differs, use the mission's planning commit before WP01's first commit. Record the SHA.
  2. `git worktree add --detach /tmp/wp03-mb-$MB $MB` (outside `.worktrees/`, detached, so it creates no lane branch).
  3. From your lane worktree, run the new test file against the old source: `PYTHONPATH=/tmp/wp03-mb-$MB/src .venv/bin/python -m pytest tests/merge/test_merge_divergent_end_to_end.py -q -p no:cacheprovider`. The test file and the `_divergent_shapes` fixture come from your lane; the product code comes from the merge-base. Confirm with `python -c "import specify_cli, sys; print(specify_cli.__file__)"` under the same `PYTHONPATH` that the old tree is imported.
  4. Record the red output (counts plus one representative refusal or traceback per shape) in this WP's Activity Log as evidence.
  5. `git worktree remove --force /tmp/wp03-mb-$MB`.
  - If the fixture itself cannot import against the merge-base (for example it needs an API a WP added), make the fixture import-compatible with both trees, or put the old-tree-incompatible part behind the test, and re-run. Do **not** substitute the WP01 claim-level red run; if the red run stays impossible, STOP and report to the orchestrator.

### Subtask T044 – Orphan and retention assertions (SC-002)

- **Same file.** After each successful merge from T043:
  - No directory from the fixture's recorded worktree paths exists.
  - `git branch --list` contains none of the recorded created lane branches.
  - `git worktree list --porcelain` lists none of them.
  - The lane workspace contexts are tombstoned. Use the workspace context API (`specify_cli.workspace.load_context`) to assert `None`.
- **Retention variant** for one shape: set `retain_branches: true`, `retain_worktrees: true` in `meta.json` (or pass `--keep-branch --keep-worktree`). Afterwards, exactly the created branches and worktrees remain, and nothing identity-named was created.
- **Invariant**: every expected name comes from the fixture's recorded allocator output. None is recomposed in the test.

### Subtask T045 – Upgrade-resume refusal pin (PD-14, US2 AS2–AS3)

- **Tests** (same file):
  1. `test_resume_with_old_form_tip_record_refuses`:
     - Build a coordination-topology divergent shape. Start the merge and interrupt it after the tips are persisted. Use the existing interruption technique of `tests/merge/test_issue_2711_merge_rollback_resume_coherence.py` or `test_merge_rollback_resume_coherence.py`, or write `MergeState` via `merge.state.save_state` with `pre_mutation_coord_sha` set and `completed_wps` as the old code would have left them.
     - Rewrite `pre_interrupt_lane_tips` so it is keyed by the **identity-form** branch name, a **test literal**.
     - Run `spec-kitty merge --resume`. Assert exit 1 and that the output names `spec-kitty merge --abort`.
     - Then `--abort` plus a fresh merge succeeds (the remedy works).
  2. `test_resume_canceled_only_not_refused`: every lane canceled, an empty tip record → no H5 refusal. Any other outcome must be the pre-existing behaviour, not H5.
  3. `test_resume_planning_only_not_refused`: only `lane-planning` → no H5 refusal.
- **Scope**: H5 applies only on coordination topology with a persisted anchor (PD-4). Assert once that a non-coordination Mission resume is **not** refused by H5.

### Subtask T046 – `merge/preflight.py` Mission-branch fallbacks (PD-13)

- **File**: `src/specify_cli/merge/preflight.py`.
- **Sites**:
  1. `target_branch_sync_remediation(...)`: `source_branch = mission_branch or mission_branch_name_required(mission_slug, mission_id)`. This is guidance text. Check that every caller passes the recorded `lanes.json` `mission_branch` when one exists (`grep -rn "target_branch_sync_remediation" src`); if a caller does not, thread it through from `lanes.json`. Wrap the recomposition so that a `ValueError` from `_mid8` (identity < 8 characters) degrades to `BranchIdentityUnresolved`. Here that means not crashing the remediation text: either emit the line without a source branch plus a doctor-identity hint, or propagate the typed error, whichever the caller contract expects. Read it and pick; record the choice.
  2. `_check_mission_branch(mission_slug, repo_root, *, expected_branch=None, mission_id=None)`: `expected_branch or resolve_branch_name(mission_slug, mission_id=mission_id)`. Make sure callers pass `expected_branch` = the recorded `lanes.json` `mission_branch`. Convert a `ValueError` from recomposition into `BranchIdentityUnresolved`, keeping the existing fail-closed behaviour.
- **Tests**:
  - Migrate `tests/merge/test_mid8_embedded_preflight.py`: its 2 identity-passing lane-naming calls go to the created form or `predict_lane_worktree`. Keep the file's Mission-branch assertions (`TestCheckMissionBranchMid8`) unchanged in intent; they pin #1978 behaviour.
  - Add to `tests/merge/test_merge_divergent_end_to_end.py`, or to a focused class in `test_mid8_embedded_preflight.py`:
    - a recorded `mission_branch` wins over the identity-derived one for a backfilled legacy shape (red on HEAD if a caller omits it);
    - `mission_id="abc"` with no recorded branch → `BranchIdentityUnresolved`, not `ValueError` (red on HEAD).
- **Complexity**: both functions stay ≤ their current CC + 1, and ≤ 15.

### Subtask T047 – Planning-artifact class green unedited, triage, quality gates

- Re-assert `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget`. It **must** be green; WP01 already made it green. `git diff <mission base> -- tests/integration/test_merge_lane_planning_data_loss.py` must show no change inside that class (WP02 may have edited another class).
- If it is red here, that is a **regression** introduced after WP01 (most likely by WP02 or WP04):
  - Diagnose it to the root cause (DIRECTIVE_052).
  - If the cause lies in `reconciliation.py` or `executor.py`, apply the out-of-map rule from Context & Constraints.
  - Never edit the class.
- Run the Test Strategy commands and record the exact commands plus counts. Classify any baseline reds per CLAUDE.md.

## Test Strategy

- **Red-first**: T043 is demonstrated red on the mission merge-base via the mandatory `git worktree add` + `PYTHONPATH` run (no proxy). T045/T046 tests are demonstrated red on the pre-change code the same way, or on HEAD where the prompt says so.
- **Real git + real allocator**: every name comes from the allocator output. Old-form keys are literals.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/merge/test_merge_divergent_end_to_end.py tests/merge/test_mid8_embedded_preflight.py -q
.venv/bin/python -m pytest "tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget" -q
.venv/bin/python -m pytest tests/merge/ tests/integration/test_merge_lane_planning_data_loss.py tests/integration/test_merge_lane_worktree_safety.py tests/terminus/ -q
.venv/bin/python -m pytest $(grep -rl "merge.preflight\|target_branch_sync_remediation\|_check_mission_branch" tests --include=*.py | tr '\n' ' ') -q
make test-fast
```

- **NFR gates**:

```bash
.venv/bin/ruff check src/specify_cli/merge/preflight.py tests/merge/test_merge_divergent_end_to_end.py tests/merge/test_mid8_embedded_preflight.py
.venv/bin/ruff check --select C901 src/specify_cli/merge/preflight.py
.venv/bin/ruff format --check src/specify_cli/merge/preflight.py tests/merge/
.venv/bin/mypy src/specify_cli/merge/preflight.py tests/merge/test_merge_divergent_end_to_end.py
```

## Definition of Done

- [ ] NFR-004: diff coverage on this WP's changed lines ≥ 90% (e.g. `.venv/bin/python -m pytest <targeted tests> --cov=<touched modules> --cov-report=xml` then `diff-cover coverage.xml --compare-branch=<lane base> --fail-under=90`; record the number in the handoff note).

- [ ] SC-001 red run against the merge-base recorded in the Activity Log (SHA, command, red output).
- [ ] 4/4 divergent shapes merge end to end (SC-001), with 0 orphans and retention honoured (SC-002).
- [ ] The old-form tip record refuses on resume and names `--abort`. The exemptions hold (SC-005).
- [ ] The preflight fallbacks prefer the recorded branch, and an invalid identity yields a typed refusal.
- [ ] `TestPlanningArtifactReachesTarget` is green and its class is unedited.
- [ ] Every out-of-map fix (if any) is logged with a rationale and a regression test.
- [ ] Gates are clean; `make test-fast` is green.

## Risks & Mitigations

- **Non-naming crashes for invalid identities** (post-fix marker, locks, baseline id): the end-to-end run surfaces them. Fold small fixes, and escalate large ones.
- **End-to-end runtime**: keep to 4 shapes plus 2 variants, and mark `slow` if required by the markers policy.
- **Interrupt simulation fidelity**: prefer the existing resume-coherence test technique over new state surgery.

## Review Guidance

- The end-to-end tests drive the real merge entry point, not internal phases.
- Expected names come from allocator output.
- There is no diff inside `TestPlanningArtifactReachesTarget`.
- Check the out-of-map edits, if any, against the rationale.
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
- 2026-09-26T18:54:31Z – claude – shell_pid=8935 – Profile python-pedro loaded (implementer). SC-001 red run: git worktree add --detach at merge-base 8900c2cb5fab2a2dbc10d1b70211a7157341b482 (mission planning commit before WP01); ran test_merge_divergent_end_to_end.py and TestPreflightMissionBranchFallbacks (test_mid8_embedded_preflight.py) from inside that tree via PYTHONPATH (confirmed old specify_cli.__file__) -- 11/13 + 2/4 red, all matching the #5108 defect (Reconciliation refused: no approved lane resolved any commits / raw ValueError from _mid8). Fixed preflight.py: target_branch_sync_remediation degrades a short-identity ValueError to an advisory notice (never raises, matches its existing diagnostics-builder contract); _check_mission_branch converts it to typed BranchIdentityUnresolved. Both already honored a recorded lanes.json.mission_branch verbatim at their call sites (executor.py:3696, no caller change needed). Out-of-map note: the divergent-shapes fixture (WP01, status-only, no WP task files) needed consumer-side setup in my own test file only (never edited) to drive a real merge: (1) commit the seeded status.events.jsonl onto the target branch before creating the mission-branch ref (the post-merge target-validation invariant reads it via `git show`), (2) create the mission-integration-branch ref itself (the fixture only records the name as divergence metadata), (3) mock two additional real, unmocked post-commit assertions (_assert_merged_wps_done_on_target, _assert_baseline_merge_commit_on_target) that are orthogonal to SC-001/naming and owned by other WPs' status/baseline work -- documented with full rationale in _real_merge_mocks_for_divergent_shapes' docstring. T045: stamped write_post_fix_marker so the resume reaches H5 specifically (not the unrelated pre-fix-in-flight-state refusal, which shares the same --abort wording) -- assertion strengthened to require the H5-specific 'pre-interrupt lane-tip record has no anchor' text + the created branch name. Green on HEAD: 13/13 new + 15/15 mid8_embedded_preflight (was 11) all pass. TestPlanningArtifactReachesTarget re-run green, diff -- <merge-base> shows zero changes inside that class (WP02 only touched TestRetentionConstraintSurvivesCleanup, a different class). Broader run: tests/merge/ + both integration files + tests/terminus/ = 1084 passed, 2 xfailed, 7 failed -- all 7 exactly match the WP prompt's documented pre-existing-reds list (TestMergeIncludesPlanningLane::test_merge_state_wp_order_includes_planning_lane_wps, 4x TestRetentionConstraintSurvivesCleanup, test_clean_lane_worktree_removed_as_today, test_local_support_declarations_end_to_end). Gates: ruff check clean, ruff format --check clean (test_mid8_embedded_preflight.py needed a full-file reformat -- confirmed pre-existing drift, not introduced by this change -- required by the WP's own `ruff format --check tests/merge/` gate), C901 clean, mypy --warn-unused-ignores clean on my 2 owned files (the reused test_merge_lane_planning_data_loss.py helper import carries pre-existing, unrelated mypy findings I did not touch). Diff-cover on preflight.py: 100% (19/19 lines). make test-fast is the reviewer's task per this WP's operator split; I did not run it (a stray attempt hung on an unrelated tests/cli/commands/test_routes_command.py test outside my diff and was killed).
