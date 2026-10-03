---
work_package_id: WP02
title: Resume refreshes a coordination worktree that only lags its HEAD (#5571)
dependencies: []
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-004
- SC-001
- SC-002
planning_base_branch: kitty/rc5-consolidate-regressions
merge_target_branch: kitty/rc5-consolidate-regressions
branch_strategy: Planning artifacts for this mission were generated on kitty/rc5-consolidate-regressions. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/rc5-consolidate-regressions unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rc5-consolidate-regressions-01M4189Z
base_commit: c2f3b261055b5d2165f29a5b66022e98fed49b31
created_at: '2026-10-03T16:27:27.215904+00:00'
subtasks:
- T006
- T007
- T008
- T009
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/terminus/test_repro_5571.py
- tests/consolidation/test_resume_coord_lag.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/consolidation/preflight.py
- src/specify_cli/consolidation/executor.py
- tests/terminus/test_repro_5571.py
- tests/consolidation/test_resume_coord_lag.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Resume refreshes a coordination worktree that only lags its HEAD (#5571)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP02 --agent claude`

## Objective

When `consolidate` was interrupted after advancing the mission branch and before refreshing the
coordination worktree, `consolidate --resume` must recognise the pure behind-own-HEAD lag,
refresh the coordination worktree in place and complete with every approved lane's content on
the target. If the dirt is not a pure lag, it refuses non-zero and never advises committing the
staged deletions.

## Context

Read `research.md` (#5571) and `plan.md` (IC-02).

- Guard: `_pre_mutation_safety_preflight` (`consolidation/executor.py` ~3278; coord guard
  ~3368-3369 `assert_worktree_clean(coord_worktree, …)`) → `MERGE_UNSAFE_WORKTREE_DIRTY` with the
  generic remedy at `git/destructive_guard.py:206`.
- Primary-only handling: advice in `_report_pre_mutation_refusal` (~3784-3797),
  `_recover_behind_head_primary_on_resume` (~3819-3880, gate ~3848, called ~3944).
- Classifier: `classify_resume_dirty_remedy` (`consolidation/preflight.py:778-838`),
  `is_pure_behind_head_lag` (~840+). For the coordination worktree the base is
  `state.pre_mutation_coord_sha`.
- **Parametrise, do not copy** (brownfield fold): generalise recovery/advice by checkout path +
  base SHA. Keep recovery resume-only and provably pure (#4933 gating). Leave the ancestry-only
  "already integrated" skip (`consolidation/git_probes.py:44-65`) unchanged.
- Executor.py is shared with WP03 (`_delete_mission_branch`) and WP04 (marker writer/heal
  caller): touch only the preflight/resume functions named here.
- Why the old test went green: `tests/terminus/test_repro_4982.py:82` merges inside the coord
  worktree, which leaves it clean. Model the state from `tests/terminus/test_repro_4997.py:51-110`
  (`_interrupt_behind_own_head`) instead.

> Post-tasks squad: `git/destructive_guard.py` (generic remedy at :206) is NOT owned; replace the advice only in the executor's refusal report (`_report_pre_mutation_refusal`, ~3745).

### Subtask T006: Red-first entry-point test (separate commit)

- **Steps**: in `tests/terminus/test_repro_5571.py`, build a coordination-topology mission with
  three approved WPs on lanes a/b/c (`build_coord_mission` or equivalent). Run a real
  `consolidate` until the interrupted shape: advance the mission/coord branch with
  `git update-ref <ref> <merge-sha> <old>` built in a temporary detached worktree, persist state
  as the real attempt does, and leave the coordination worktree unreset (its files show staged
  deletions). Then run `consolidate --resume` through the CLI.
  - Assert (ideal): exit 0, every lane's file on the target, all WPs `done`.
  - Second case: add a genuine edit in the coordination worktree → non-zero, output does not
    contain "Commit, stash, or revert" / any advice to commit; contains the "Do NOT stage or
    record" guidance.
- **Validation**: RED on base; commit alone (`test(WP02): red-first #5571`).

### Subtask T007: Generalise the classifier/advice to a checkout parameter

- **Steps**: make the behind-own-HEAD advice path in `_report_pre_mutation_refusal` apply to the
  coordination-worktree refusal (carry the worktree path / distinguish it), computing the remedy
  with `classify_resume_dirty_remedy(coord_worktree, …)` against `pre_mutation_coord_sha`.
- **Validation**: unit tests in `tests/consolidation/test_resume_coord_lag.py`.

### Subtask T008: In-place refresh of a pure coordination lag on resume

- **Steps**: generalise `_recover_behind_head_primary_on_resume` to take the checkout and base
  SHA; on `--resume` only, when the lag is provably pure, `reset --hard HEAD` the coordination
  worktree and retry the preflight once. Any non-pure state still refuses.
- **Validation**: T006 green; complexity ≤ 15 (extract helpers + focused tests).

### Subtask T009: Regression sweep of resume tests

- **Steps**: run `tests/terminus/test_repro_4982.py`, `test_repro_4997.py`,
  `test_resume_phantom_only.py`, `tests/consolidation/` resume tests. Fix only genuine regressions.

## Definition of Done

- T006 red on base, green on tip; genuine-dirt case refuses without commit advice.
- Root-checkout (#4997) behaviour unchanged.
- Lint/format/mypy clean on touched files; subtasks marked done via `mark-status`.

## Risks

- Misclassifying genuine user edits as lag → data loss. Keep `is_pure_behind_head_lag` strict,
  including the untracked-obstruction check.

## Reviewer Guidance

- Verify the recovery only fires on `--resume` and only for a pure lag.
- Verify no second, coordination-only copy of the recovery logic.
