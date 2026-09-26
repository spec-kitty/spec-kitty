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
5. **FR-012**: `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget` (red on HEAD: 2 failed) goes **green without editing its fixture**.

## Context & Constraints

- **Spec**: US1 (AS1–AS5), US2 (AS2–AS3), SC-001, SC-002, SC-005, FR-003, FR-005, FR-011, FR-012.
- **Plan**:
  - PD-13 and PD-14.
  - Risk 1: invalid-identity shapes may still fail at non-naming merge steps. This WP's end-to-end test is the proof.
  - Parallel Work Analysis WP03.
- **Research Part A**: §4 lists `merge/preflight.py:123`, `:165` as independent composers. §8 Risk 4.
- **tasks.md deviations 5 and 6**: H5 lives in WP02 (`executor.py`), and the recovery fallback in WP04 (`lanes/recovery.py`). This WP owns neither file. It exercises them end to end.
- **Dependencies**:
  - WP01: the claim, and the `_divergent_shapes` fixture you reuse.
  - WP02: the executor stages and H5.
  - WP04: the lifecycle and acceptance consumers, and recovery.
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
- **Red-first**:
  - Run this test on the **merge-base of this mission**, before WP01, WP02 and WP04, for example via `git stash` or by running against `upstream` with `PYTHONPATH`, per CLAUDE.md "baseline-red gotcha".
  - Record that it is red (refused or crashing) there.
  - If that is impractical inside the lane worktree, record the WP01 claim-level red run as the proxy and state it explicitly.

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

- Run `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget`. It **must** be green. `git diff <mission base> -- tests/integration/test_merge_lane_planning_data_loss.py` must show no change inside that class (WP02 may have edited another class).
- If it is still red:
  - Diagnose it to the root cause (DIRECTIVE_052).
  - If the cause lies in `reconciliation.py` or `executor.py`, apply the out-of-map rule from Context & Constraints.
  - Never edit the class.
- Run the Test Strategy commands and record the exact commands plus counts. Classify any baseline reds per CLAUDE.md.

## Test Strategy

- **Red-first**: T043/T045/T046 tests are demonstrated red on the pre-mission code, or via the documented proxy.
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
