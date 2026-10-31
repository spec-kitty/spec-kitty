---
work_package_id: WP01
title: Project the whole late coordination window
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6791-late-teardown-verdict-projection
merge_target_branch: issue-6791-late-teardown-verdict-projection
branch_strategy: Planning artifacts for this mission were generated on issue-6791-late-teardown-verdict-projection. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6791-late-teardown-verdict-projection unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-late-teardown-verdict-projection-01M67J85
base_commit: 4ee2407ba8f5757252b763457c43ca3f32f17244
created_at: '2026-10-30T23:32:22.453767+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Core fix
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_issue_6791_late_verdict_projection.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/bookkeeping_projection.py
- src/specify_cli/consolidation/phase_teardown.py
- tests/consolidation/test_issue_6791_late_verdict_projection.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Project the whole late coordination window

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Load the PM profile first: `spec-kitty agent profile show python-pedro`, then
`spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting. If a
review returned this WP, every feedback item is an implementation TODO and must be addressed
before the WP is complete.

---

## Objectives & Success Criteria

Make `spec-kitty consolidate --mission <slug> --resume --yes` (after a
`COORD_TEARDOWN_KEPT_ONLY_COPY` refusal) project **every** attributable coordination commit in the
late window `pre_mutation_coord_sha..coordination-tip` onto the target, or refuse before deleting
the coordination branch.

Done when:

- The #6791 reproduction is green: after a refusal, an artifacts commit and a real
  `agent issue-verdict` commit both land, and the target's `issue-matrix.json` carries the recorded
  terminal verdict while the coordination branch is gone.
- Every coordination record changed in the late window is byte-identical on the target after a
  successful resume; otherwise the resume exits non-zero, names the path, and leaves the branch,
  worktree and coordination marker intact.
- A projection never loses or downgrades a judgement the target already holds, and never expresses
  a deletion.
- The mid-merge projection (`project_post_checkpoint_commits_to_target` /
  `_post_checkpoint_mission_paths` default behaviour) is unchanged.

## Context & Constraints

Read first (all absolute or repo-relative):

- `kitty-specs/late-teardown-verdict-projection-01M67J85/spec.md` — FR/NFR/C/SC and the three user
  stories.
- `kitty-specs/late-teardown-verdict-projection-01M67J85/research.md` — the real-CLI reproduction and
  decisions D1–D5.
- `src/specify_cli/consolidation/phase_teardown.py` — `_land_late_coordination_commits` (the #5570
  late projection), `_teardown_coordination_triple` (call order: late projection → status fold →
  worktree teardown → compare-and-swap branch delete → marker flatten).
- `src/specify_cli/consolidation/bookkeeping_projection.py` — `_post_checkpoint_mission_paths`
  (the `excluded_kinds = {ISSUE_MATRIX, ACCEPTANCE_MATRIX}` set that drops the verdict commit) and
  `project_post_checkpoint_commits_to_target` (whose `projected_paths` feed the reconciliation
  squash proof — do not change its default path set).
- `src/specify_cli/coordination/coherence.py::is_coordination_kind_file` — the one classifier for
  "is this a COORD-partition record".
- `tests/consolidation/test_teardown_refusal_resume.py` — the #5965 refusal/resume fixture family to
  model the new test on (`build_coord_mission`, `run_terminus`, `_declare_subtask_rosters`).

Constraints that matter:

- **C-001**: the mid-merge projection must stay byte-identical. Any widening of the shared window
  selector must be opt-in (default off).
- **NFR-003**: the projection commits through the existing `commit_merge_bookkeeping` seam
  (`_commit_projection_and_carry`); no new writer, no direct `git commit`.
- **NFR-002**: fail closed. An unreadable git diff, an unparsable coordination matrix, or an
  unmatched path raises *before* the branch delete. Never read an error as "nothing to project".
- **NFR-001**: bounded work, `O(paths changed in the window)`.
- **C-002**: no `mission_runtime` / placement-seam changes; this is a projection-window fix.

## Branch Strategy

- **Strategy**: workspace-per-work-package on a coordination-topology mission; the WP executes in
  its computed lane worktree and merges back into the mission branch.
- **Planning base branch**: `issue-6791-late-teardown-verdict-projection`
- **Merge target branch**: `issue-6791-late-teardown-verdict-projection`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### T001 – Write the red-first reproduction and prove it fails

- **Purpose**: Prove the defect through the pre-existing production entry point before touching
  production code (DIRECTIVE_034).
- **Steps**:
  1. Create `tests/consolidation/test_issue_6791_late_verdict_projection.py`, modelled on
     `tests/consolidation/test_teardown_refusal_resume.py` (reuse `build_coord_mission`,
     `run_terminus`, `_declare_subtask_rosters`; `pytestmark = [integration, git_repo, regression]`).
  2. Fixture: coord mission with `WP01`/`WP02`, an `issue-matrix.json` carrying one `in-mission`
     row seeded on both surfaces (build it with
     `specify_cli.tasks.issue_matrix.build_issue_matrix_document` /
     `IssueMatrixEntry`, so the document is the real shape), then `move-task WP02 --to planned
     --review-feedback-file …` and `--to canceled` with `--no-auto-commit` so the review-cycle file
     stays untracked, then `consolidate --yes` → assert exit
     `COORD_TEARDOWN_KEPT_ONLY_COPY_EXIT_CODE` (76).
  3. Commit the review-cycle artifact inside the coordination worktree (**commit A**), then run the
     **real** `agent issue-verdict --mission <slug> --issue '#6791' --verdict fixed --actor tester`
     from the primary checkout (**commit B**) and assert its stdout reports `committed` with
     `surface=kitty/mission-<slug>`.
  4. `consolidate --resume --yes` → assert exit 0, the coordination branch is gone, and
     `git show <target>:kitty-specs/<slug>/issue-matrix.json` carries `"verdict": "fixed"` with the
     evidence ref — **plus** the artifacts file present at the target.
  5. Run it against the unfixed code and record the failure output (this is the red-first proof
     quoted in the PR body). Suggested command:
     `uv run pytest tests/consolidation/test_issue_6791_late_verdict_projection.py -x -q`.
- **Files**: `tests/consolidation/test_issue_6791_late_verdict_projection.py` (new)
- **Parallel?**: No — this must land first.
- **Notes**: Do not hand-write the verdict commit; the point is that the production writer route is
  what the resume must carry. Keep the fixture close to the issue's own steps.

### T002 – Opt-in gate-matrix widening of the late-window selector

- **Purpose**: Let the late window see gate-matrix paths without changing the mid-merge path set.
- **Steps**: Add `include_gate_matrices: bool = False` to `_post_checkpoint_mission_paths`; when
  True, drop `ISSUE_MATRIX` / `ACCEPTANCE_MATRIX` from `excluded_kinds` and update the docstring to
  state *why* the exclusion is window-scoped (mid-merge placeholder vs post-teardown window — D1).
  All existing callers keep the default.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py`
- **Parallel?**: Yes (separate function from T004).
- **Notes**: `project_post_checkpoint_commits_to_target` must keep calling with the default; its
  output feeds `projected_content_matches_target`.

### T003 – `project_late_gate_matrix_commits`

- **Purpose**: Bring a post-checkpoint gate-matrix commit forward onto the target checkout.
- **Steps**: New function in `bookkeeping_projection.py`:
  `project_late_gate_matrix_commits(*, main_repo, mission_slug, coord_ref, checkpoint_sha) -> tuple[Path, ...]`.
  For each gate-matrix path changed in `checkpoint_sha..coord_ref` (scoped to
  `kitty-specs/<slug>/`, resolved through
  `_assert_status_path_within_target_surface` so a bad slug can never escape the mission dir):
  read the coordination blob; skip when it equals the target's current bytes; call the T004 guard;
  otherwise write it into the target checkout and record the path. Forward-only: a missing
  coordination blob (a deleted matrix) is a refusal, never a delete.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py`
- **Parallel?**: No — needs T002.
- **Notes**: Export it in `__all__` alongside the other projection seams.

### T004 – Established-judgement guard and forward-only refusal

- **Purpose**: Lifting the exclusion must not trade one data-loss mode for another.
- **Steps**:
  1. Define a `LateProjectionRefused(Exception)` carrying a message that names the path and the
     reason.
  2. Define the *established judgement* map per gate-matrix kind, derived from the canonical sets —
     never a second hardcoded list:
     - `issue-matrix.json`: row → `verdict` is terminal (i.e. a member of
       `IssueMatrixVerdict` other than `in-mission`; `unknown` is not a member and is non-terminal).
     - `acceptance-matrix.json`: criterion → `pass_fail == "pass"`;
       negative invariant → `result` in `acceptance.matrix.TERMINAL_INVARIANT_RESULTS`.
  3. Refuse when projecting would remove a key the target has, or turn an established
     judgement into a non-established one. Refuse when the candidate document is unparsable.
     A target file that is absent or unparsable holds no established judgement (project).
  4. Document the symmetric rule in the docstring: forward-only, no evidence loss.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py`
- **Parallel?**: Yes (independent of T002/T003 functions, same module).
- **Notes**: Import the acceptance constants from `specify_cli.acceptance.matrix` and the verdict
  enum from `specify_cli.cli.commands.review._issue_matrix`, function-locally if the import graph
  would otherwise cycle. No `try/except Exception` around the comparison: an unreadable document is
  a refusal (NFR-002).

### T005 – Whole-window completeness assertion, wired into teardown

- **Purpose**: FR-002/FR-003 — prove the window landed, or refuse with the coordination triple
  intact.
- **Steps**:
  1. Add `assert_late_window_landed(*, main_repo, mission_slug, coord_ref, checkpoint_sha, target_feature_dir)`
     (name it for what it asserts): for every path changed in the window inside
     `kitty-specs/<slug>/` that `is_coordination_kind_file` classifies as a coordination record, the
     target checkout's bytes must equal the coordination tip's. Exclude the status pair by its
     canonical filename constants (`_STATUS_EVENTS_FILENAME`, `_STATUS_FILENAME`) — the union /
     rematerialize stage owns it and runs *after* this one. Raise `LateProjectionRefused` naming
     every unlanded path (cap the list, like the existing stranded-path message).
  2. In `phase_teardown._land_late_coordination_commits`: call `project_late_gate_matrix_commits`
     inside the existing `try`, add its paths to the committed set, commit as today (only when
     something changed), then call `assert_late_window_landed` **after** the commit and **before**
     returning (so the branch delete that follows can never destroy an unlanded record).
  3. Catch `LateProjectionRefused` next to the existing `GitCommandError` handler and re-raise as
     `CoordinationTeardownError` whose message states: what could not be landed, that the branch was
     NOT deleted, that nothing was rolled back, and that the operator should land the file on the
     target themselves (or move it) and re-run `specify consolidate --resume`.
  4. Keep the console line ("Projected the coordination commit(s)…") only when a commit was
     actually made; the assertion always runs when the window is non-empty.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py`,
  `src/specify_cli/consolidation/phase_teardown.py`
- **Parallel?**: No — after T002–T004.
- **Notes**: The delete stays a compare-and-swap at the live tip; do not weaken it. `--keep-branch`
  and retained-worktree shapes never reach the delete, so they can only see the refusal.

### T006 – Guard, refusal and idempotence tests

- **Purpose**: Pin the new behaviour and its guards.
- **Steps** (same test module unless noted; reuse one shared fixture family so positive and
  negative controls cannot drift):
  1. **Preserved judgement**: target holds a terminal verdict the coordination copy would replace
     with `in-mission` → resume refuses non-zero naming the path, branch and worktree survive, and
     the target's terminal verdict is unchanged. Positive control on the same fixture family:
     the T001 reproduction projects and lands.
  2. **Forward-only**: a late commit that deletes a coordination record → refusal, branch kept, the
     record still present on the target.
  3. **Unprojectable record**: a late commit touching a coordination record the projection cannot
     carry (e.g. an acceptance-matrix change whose target copy diverged) → refusal naming the path,
     branch kept. (If T002/T003 make it projectable, assert it lands instead — the test must assert
     the *outcome*, not the mechanism.)
  4. **Idempotence**: after a successful resume, re-running `--resume` is a no-op (no empty commit,
     exit 0).
- **Files**: `tests/consolidation/test_issue_6791_late_verdict_projection.py`
- **Parallel?**: No — after T005.
- **Notes**: Every assertion must be able to fail: for each refusal test, assert the same probe
  observes the thing when present (the positive-control rule from
  `tactic:acceptance-criteria-non-vacuity`).

### T007 – Targeted verification

- **Purpose**: Prove the change compiles, is typed and does not regress the surrounding suites.
- **Steps**:
  ```bash
  uv run pytest tests/consolidation/test_issue_6791_late_verdict_projection.py -q
  uv run pytest tests/consolidation/test_teardown_refusal_resume.py tests/consolidation/test_teardown_keeps_only_copy.py -q
  uv run pytest tests/coordination -q
  uv run ruff check src/specify_cli/consolidation tests/consolidation/test_issue_6791_late_verdict_projection.py
  uv run ruff format --check src/specify_cli/consolidation tests/consolidation/test_issue_6791_late_verdict_projection.py
  uv run mypy src/specify_cli/consolidation/bookkeeping_projection.py src/specify_cli/consolidation/phase_teardown.py
  ```
  Never run a full heavy suite locally (`NO_FULL_HEAVY_SUITES_IN_MISSION`); CI owns that.
- **Files**: n/a
- **Parallel?**: No.
- **Notes**: Record the exact commands and results in the WP's `add-history` note; the PR's
  "Tests run" section quotes them.

## Test Strategy

Red-first (T001) then green (T005). The production entry point is the CLI (`consolidate --resume`),
not a helper; the new seam functions are additionally covered through that path. Any pre-existing
red is reported, never skipped, xfailed or weakened.

## Risks & Mitigations

- **Over-refusal** on shapes this fix does not anticipate: the assertion compares real bytes against
  the coordination tip, so a genuinely landed record never refuses. Run the existing
  `tests/consolidation/` and `tests/coordination/` suites as the regression net.
- **Changing the mid-merge path set** would silently alter the reconciliation squash proof: the
  widening is opt-in (T002) and no existing caller passes it.
- **A second terminal-verdict list** would drift from the gate: derive from `IssueMatrixVerdict`
  (FR-004).

## Review Guidance

Reviewers should verify:

- The mid-merge projection's path set is unchanged (default-off widening; no new keyword passed by
  `project_post_checkpoint_commits_to_target`).
- The refusal path cannot reach the branch delete: read `_land_late_coordination_commits` top to
  bottom and confirm every raise precedes the CAS delete in `_teardown_coordination_triple`.
- The guard's terminal sets come from the canonical authorities.
- The reproduction test drives the real `agent issue-verdict` writer and the real
  `consolidate --resume`, and would fail if the projection were reverted.
- `ruff`/`mypy` ran on the touched modules.

## Progress & Status

- First: `spec-kitty agent action implement WP01 --agent <name> --mission late-teardown-verdict-projection-01M67J85`
- Record progress with `spec-kitty agent tasks add-history WP01 --note "…"` and subtask completion
  with `spec-kitty agent tasks mark-status T001 --status done`.
