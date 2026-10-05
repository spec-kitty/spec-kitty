---
work_package_id: WP03
title: Gate re-check and honest verified banner
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-004
- C-001
planning_base_branch: issue-5668-approved-claim-bound
merge_target_branch: issue-5668-approved-claim-bound
branch_strategy: Planning artifacts for this mission were generated on issue-5668-approved-claim-bound. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5668-approved-claim-bound unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-claim-bound-01M444QR
base_commit: 1571015860025be91d106c4f550b3c6b6b1a6246
created_at: '2026-10-04T21:47:08.202822+00:00'
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 3 - Completing the fix
history:
- at: '2026-10-04T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/terminus/test_post_approval_gate_recheck.py
- tests/consolidation/test_approved_bound_residuals.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/phase_gate.py
- tests/terminus/test_post_approval_gate_recheck.py
- tests/consolidation/test_approved_bound_residuals.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Gate re-check and honest verified banner

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `implementer`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task.** Check the `review_ref` field in the event log (`.venv/bin/spec-kitty agent tasks status --mission approved-claim-bound-01M444QR`). If this work package was returned from review, every feedback item is part of your work.

---

## Objectives & Success Criteria

"Reconciliation verified" is printed only when every lane tip is still within its approved bound when the gate runs.

- A commit added to an approved lane after the claim-time check and before the lane is merged is refused at the gate with `LANE_MOVED_AFTER_APPROVAL`; the banner is not printed; the run is rolled back through the existing rollback authority and the target is at its pre-run tip.
- No new restore path: `tests/consolidation/test_single_rollback_authority.py` passes unchanged.
- The one known hole, content inside a merge commit, is pinned as a strict expected failure.

Implementation command: `.venv/bin/spec-kitty agent action implement WP03 --agent implementer --mission approved-claim-bound-01M444QR`

## What WP02 delivered (read before the subtasks)

WP02 is approved. These exist on your lane's base; call them, do not redefine or edit them:

- `consolidation/approved_bound.py`: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `BoundRefusalCode`, `BoundRefusal.render()`, `approval_stamp(events, wp_id)`, `check_lane(...)`, `commits_beyond`, `content_commits`. The printed recovery command is `spec-kitty agent tasks move-task <WP> --to in_progress --mission <mission>`.
- `consolidation/reconciliation.py`: `approved_bound_refusal(repo_root, feature_dir, lanes_manifest, *, coord_base_ref, excluded_canceled_wp_ids=(), excluded_window_base=None, event_log=None) -> str | None` and `lane_tips_moved_refusal(repo_root, lanes_manifest, *, validated_tips, anchor_shas, planning_prefix, approved_wp_ids=None) -> str | None`. The claim carries `ApprovedWpCommitSet.bound_lane_tips`.
- Run state (`run_state.py`, set in `phase_claim._capture_reconciliation_claim`): `validated_lane_tips: dict[str, str]`, `bound_anchor_shas: tuple[str, ...]`.
- `tests/terminus/post_approval_support.py` (frozen: import it, do not edit it): `build_post_approval_mission(tmp_path, "lanes" | "coord")` returning a two-lane `CoordMission`, `add_post_approval_commit(mission, lane=...)`, `strip_approval_stamps(mission, wp_id)`, `rework_and_reapprove(mission, wp_id)`, `lane_worktree`. Test helpers that re-record approvals at the current lane tips: `restamp_approvals_at_lane_tips` (`tests/terminus/conftest.py`), `tests/consolidation/approval_stamps.py`.
- `tests/architectural/test_no_dead_symbols.py` is red on the base for five names that have no `src/` caller yet: `APPROVED_REVIEWED`, `ATTEST_APPROVED_FLAG`, `approval_stamp` (WP04 imports them), `lane_tips_moved_refusal` (WP03), `approved_bound_refusal` (WP05). Your work package clears its own names; the others stay red on your lane until the lanes are consolidated. Do not add an allowlist entry.
- Running mypy on one file alone reports a spurious `no-any-return` because of the repository's `follow_imports = "skip"` override; run `.venv/bin/mypy --strict src/specify_cli/consolidation` (the package) instead.

- **For this work package**: pass `approved_wp_ids` to `lane_tips_moved_refusal` (lane branch to the approved work packages of that lane). Without it the text and the printed recovery command name the first manifest work package of the lane, which can be a canceled one. Take the approved membership from the claim or the snapshot the run already holds; do not re-derive it from events.

## Context & Constraints

Read first, in this order:

1. `.kittify/charter/charter.md` (binding) and `spec-kitty charter context --action implement --json`.
2. `kitty-specs/approved-claim-bound-01M444QR/spec.md`, `plan.md` (sections D-1 to D-6), `research.md`, `data-model.md`, `contracts/consolidate-refusals.md`.
3. `kitty-specs/approved-claim-bound-01M444QR/research/code-grounding.md` for file and line references. Line numbers were taken at `9adc68803f`; re-locate by symbol name (`codegraph explore "<symbol>"`).

Rules that bind every work package of this mission:

- **CLI binary**: always `.venv/bin/spec-kitty` and `.venv/bin/python -m pytest`. The bare `spec-kitty` on PATH is a stale install. Never `uv run`.
- **No heavy suites**: never `make test-full`, never a bare `tests/architectural/` run. Run the files named in this prompt.
- **Test economy**: each new test must pin one distinct behaviour. No test per helper, no duplicate of an existing pin. Prefer extending a parametrized test over adding a sibling.
- **Quality**: `ruff check` and `mypy --strict` clean on changed files, complexity <= 15, no new `# noqa` or `# type: ignore`. Format check: `uv run --frozen ruff format --check --force-exclude <changed files>`.
- **Status imports**: import status symbols only through the `specify_cli.status` facade. Git reads go through `consolidation/git_probes.py`; do not shell out to git directly from new consolidation code.
- **Byte-identity**: no existing refusal code or text changes. New texts are additions.
- **No fail-open**: an absent approval stamp is never replaced by the lane tip, in product code or by a test switch (spec C-003).
- **Terminology**: Mission and work package; `--mission`, never `--feature`.
- **Commits**: conventional messages; every commit ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model or tool identifiers in commit messages.
- **Tracers**: do not edit `kitty-specs/approved-claim-bound-01M444QR/tracers/*.md` in a lane worktree (parallel lanes would conflict). Put tooling friction and unplanned design decisions in this prompt's Activity Log and in your hand-back report; the orchestrator records them.

## Branch Strategy

- **Strategy**: see `branch_strategy` in the frontmatter (written by `finalize-tasks`)
- **Planning base branch**: issue-5668-approved-claim-bound
- **Merge target branch**: issue-5668-approved-claim-bound

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path `spec-kitty agent action implement` resolves, do not construct it.

## Subtasks & Detailed Guidance

### Subtask T012 – Red test: a commit injected during the run

- **Purpose**: prove the claim-time check alone is not enough (spec US1 scenario 5), through a real `consolidate` run.
- **Steps**:
  1. Create `tests/terminus/test_post_approval_gate_recheck.py`. Reuse `tests/terminus/post_approval_support.py` (WP02) for the mission.
  2. Inject the commit after the claim was captured and before the lane is merged. Choose the least invasive real mechanism and document it in the module docstring. Two workable options:
     - in-process: invoke the consolidate command with typer's `CliRunner` and wrap the first lane-merging phase function (find it from `executor._run_lane_based_consolidation_locked`; at grounding time the lane merge is in `consolidation/phase_advance.py`) so that it commits on the lane branch and then delegates to the real function;
     - subprocess: a `git` wrapper on `PATH` that pauses the run at a named git command, as the reproducer library in issue 5668 does (`install_wrapper`, `run_sk_paused`).
     Prefer the in-process wrapper: it names the phase boundary and is deterministic.
  3. Assert: non-zero exit, `LANE_MOVED_AFTER_APPROVAL` and the injected commit's short SHA in the output, no "Reconciliation verified" line, target tip equal to its pre-run tip, mission branch and (coordination topology) coordination branch at their pre-run tips.
  4. Positive control on the same fixture: the same wrapper injecting nothing lets the run pass and print the banner.
  5. Parametrize over both strategies and **both topologies**: on a LANES mission the claim base is the mission branch itself, which is the case most easily missed.
  5a. The injection must happen **before** the lane is merged, so the late commit really lands on the mission branch: before the rollback assertion, assert from the run's output or from a recorded ref that the injected SHA became an ancestor of the mission branch during the run (for example capture `git merge-base --is-ancestor` inside the wrapper after the real phase function returns). A commit injected after the lane merge proves nothing.
  6. Run it: it must be red (the run passes and prints the banner, or fails with a different verdict). Commit it alone: `test(consolidation): reproduce a lane commit added during consolidate`.
- **Files**: `tests/terminus/test_post_approval_gate_recheck.py`.

### Subtask T013 – Re-run the lane check at the gate

- **Purpose**: plan D-3, gate time.
- **Steps**:
  1. In `consolidation/phase_gate.py::_phase_reconcile_before_teardown`, after the `_resume_reconciliation_already_passed` short-circuit and before `MergeOutcomeVerifier(...).verify(...)`, call `reconciliation.lane_tips_moved_refusal(run.main_repo, run.lanes_manifest, validated_tips=run.validated_lane_tips, anchor_shas=run.bound_anchor_shas, planning_prefix=...)`. WP02 defined that function and the two run-state fields; do not add to `reconciliation.py`, `phase_claim.py` or `run_state.py`.
  2. Do **not** call `approved_bound_refusal` here and do not pass a live branch name as an anchor. At gate time every lane was merged into the mission branch with a no-ff merge, so the live mission branch reaches the injected commit, and on a LANES mission the claim base is the mission branch name: a check anchored on live names passes vacuously. The validated tips and anchor SHAs were captured before this run mutated anything.
  3. On a refusal: `run.reconciliation_result = VerifyResult.refused(<text>)`, print `result.recovery_guidance()` exactly as the existing non-PASS branch does, and fall into that branch. Restructure so there is one non-PASS branch, not a copy.
  4. The banner call sites stay as they are: with the re-check in front of `verify()` the banner is reachable only when the lane check passed. Do not change the two banner texts.
  5. A `GitProbeError` from the check becomes a REFUSE, not a traceback: follow how `verify()` reports probe errors.
- **Files**: `src/specify_cli/consolidation/phase_gate.py`.
- **Notes**: lanes that the tool merged with the mission branch during this run carry merge commits; the mission-branch anchor covers them. The already-passed resume path stays exempt: lane branches may be gone there.

### Subtask T014 – Prove the rollback path

- **Purpose**: constraint C-001.
- **Steps**:
  1. Run T012: green.
  2. Run `tests/consolidation/test_single_rollback_authority.py`, `tests/consolidation/test_refuse_restores_target.py`, `tests/terminus/test_rollback_door.py`, `tests/terminus/test_rollback_restores_refs.py`: unchanged and green. The allowed-caller set must not have been edited.
  3. If T012 shows a branch not restored, read `consolidation/rollback.py::rollback_to_snapshot` and the executor's single `try`: the gate's `typer.Exit(1)` must travel through that `try`. Do not add a restore call in `phase_gate.py`.
- **Files**: none expected.

### Subtask T015 – Pin the merge-commit residual

- **Purpose**: the lane check skips merge commits; a merge commit that itself introduces content is not seen. Record it as an honest red.
- **Steps**:
  1. Create `tests/consolidation/test_approved_bound_residuals.py` with one test: approve, then create on the lane a merge commit (from an anchor-reachable parent) whose tree adds a file that neither parent has; assert the ideal behaviour (`LANE_MOVED_AFTER_APPROVAL`).
  2. Mark it `@pytest.mark.xfail(strict=True, raises=AssertionError, reason="content inside a merge commit is not seen by the approved-bound check; tracked as a named residual of mission approved-claim-bound")`.
  3. Module docstring: what the residual is and why it is out of scope (spec, Known residuals).
- **Files**: `tests/consolidation/test_approved_bound_residuals.py`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/terminus/test_post_approval_gate_recheck.py tests/consolidation/test_approved_bound_residuals.py -q
.venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_refuse_restores_target.py tests/terminus/test_rollback_door.py tests/terminus/test_rollback_restores_refs.py tests/consolidation/test_executor_phase_boundary.py -q
.venv/bin/python -m pytest tests/terminus -q -n auto --dist loadfile -p no:cacheprovider
```

## Risks & Mitigations

- **Resume false refusal.** Run the terminus resume tests (`test_resume_*.py`); they must stay green.
- **Second restore path.** The existing `_rollback_target_after_failed_reconciliation` call is a known second path; do not add another and do not remove it here.
- **Phase-boundary pin.** `tests/consolidation/test_executor_phase_boundary.py` pins phase order; the re-check lives inside the existing gate phase, no new phase.

## Review Guidance

- The red test was committed before the fix. With `phase_gate.py` reverted locally, the late file is on the target and the banner prints, in all four cells.
- The test proves the injected commit was merged into the mission branch before the gate ran.
- One non-PASS branch in the gate; no restore call added; the rollback caller pin is unchanged.
- The banner texts are byte-identical.
- The residual test is strict xfail and asserts the ideal behaviour.
- Confirm the implementer ran `ruff check`, the format check and `mypy --strict` on the changed files and that all were clean.
- Reviewer and implementer are different agents. Judge each new test: does it pin a distinct behaviour, and would it fail if the behaviour were removed?

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:45:00Z – system – Prompt created.

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status> --mission approved-claim-bound-01M444QR` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done --mission approved-claim-bound-01M444QR` for subtasks.
