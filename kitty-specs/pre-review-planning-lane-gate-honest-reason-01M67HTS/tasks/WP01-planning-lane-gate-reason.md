---
work_package_id: WP01
title: The record tells the truth for a planning-lane WP
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6792-planning-lane-gate-honest-reason
merge_target_branch: issue-6792-planning-lane-gate-honest-reason
branch_strategy: Planning artifacts for this mission were generated on issue-6792-planning-lane-gate-honest-reason. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6792-planning-lane-gate-honest-reason unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - The honest reason
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task_gates.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The record tells the truth for a planning-lane WP

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Deliver the mission's whole behavioural change:

1. A **planning-lane WP** (`execution_mode: planning_artifact`, or a WP placed in a lane
   for which `specify_cli.lanes.compute.is_planning_lane` is true) whose changed-file set
   is empty because its workspace **is** the checkout on the target branch records a
   `no_coverage` pre-review verdict whose `reason` names the planning lane and says the
   committed diff was not inspected. **No dispatch, no test subprocess, no block.**
2. A **code-change WP** with an empty changed-file set keeps today's exact wording
   (`no changed files detected for this WP — skipping the gate cheaply`).
3. Nothing else about the gate changes: binding resolution, scope selection, dispatch,
   aggregation, the two hard-stops and the fail-open envelopes are untouched.

Success criteria from `spec.md`: SC-001 (red→green reproduction), SC-002 (existing gate
modules green, unmodified), SC-003 (code-change control keeps the old wording), SC-004
(no dispatch for the planning arm; transition applies).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6792. #2741 (closed) asked for "at minimum record
  'committed-diff not inspected' rather than a misleading `no_coverage`"; the rewritten
  gate kept `no_coverage` but never added that reason for the planning-lane shape.
- Read first: `kitty-specs/pre-review-planning-lane-gate-honest-reason-01M67HTS/plan.md`,
  `research.md` (D-1 … D-7), `spec.md`, `reasons-canvas.md`.
- The single string to replace is at
  `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` — the
  `if not inputs.changed_files:` short-circuit inside
  `_mt_collect_transition_gate_verdicts`. Reproduce first with the real shape, not with a
  patched helper: a `planning_artifact` WP resolves to the repo root, so the merge-base
  diff against the target branch is empty by construction and a clean tree adds no dirty
  paths.
- **Charter constraints**: single canonical authority (ask `is_planning_lane` and
  `WorkProductKind.PLANNING_ARTIFACT`, never compare `"lane-planning"` by hand); locality
  of change (edit beside the string, not in the lane/workspace modules); no gate
  weakening (no skip, xfail, marker or silencing flag); no new dependency, CLI flag,
  config key or env var.
- Terminology: Mission, work package, `planning_artifact`, `lane-planning` are canonical
  values. Do not introduce "feature" for Mission.

## Branch Strategy

- **Strategy**: Feature-branch mission with lanes (`topology: lanes`); all work merges
  into the mission's target branch and a PR carries it to `main`.
- **Planning base branch**: `issue-6792-planning-lane-gate-honest-reason`
- **Merge target branch**: `issue-6792-planning-lane-gate-honest-reason`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Survey the empty-diff arm and the planning-lane authorities

- **Purpose**: Confirm the exact call graph before editing, so the fix lands in one place
  and no second source of truth appears.
- **Steps**:
  1. Read `_mt_collect_transition_gate_verdicts`, `_mt_resolve_transition_gate_inputs`,
     `_mt_pre_review_changed_files` and `_mt_resolve_pre_review_workspace` in
     `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`.
  2. Read `specify_cli.lanes.compute.is_planning_lane` (and its docstring rule about not
     comparing `PLANNING_LANE_ID` by hand), `specify_cli.lanes.persistence.read_lanes_json`
     (raises `CorruptLanesError`), and `specify_cli.ownership.models.WorkProductKind`.
  3. Read `workspace/context._resolve_planning_artifact_arm`,
     `_resolve_planning_lane_arm` and `_resolve_repo_root_lane_arm` to see why lane
     membership alone is not a sufficient signal.
  4. Grep for other producers of "no changed files detected" (there is exactly one) and
     for existing tests that assert the string (there are none).
  5. Record the survey and any campsite finding with
     `spec-kitty agent tracer-append --mission <slug> --category approach --entry "..."`.
- **Files**: the four modules above, read-only.
- **Parallel?**: No — it settles the design the rest depends on.
- **Notes**: If the survey shows the string is produced anywhere else, stop and report
  rather than fixing half the surface.

### Subtask T002 – Failing reproduction through the real entry point

- **Purpose**: Red-first proof at the operator-visible surface (charter, ATDD-First).
- **Steps**:
  1. Create
     `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py`.
     Mark it `pytest.mark.git_repo` like its neighbours in that directory.
  2. Build a **real** git repository fixture: `git init -b <mission target branch>`, an
     initial commit, then a second commit that adds/modifies the planning WP's deliverables
     (so the target branch already contains them, exactly the reported shape). The tree must
     end clean.
  3. Write the mission fixtures the production path needs, in the shapes the neighbouring
     tests already use: `kitty-specs/<mission>/meta.json` (`mission_type: software-dev`,
     `target_branch` = the fixture branch), `tasks/WP09-*.md` frontmatter with
     `execution_mode: planning_artifact`, `lanes.json` placing `WP09` in
     `lane-planning`, and a seeded `in_progress` status event so the WP can move to
     `for_review`.
  4. Drive the production entry point with Typer's `CliRunner`:
     `move-task WP09 --to for_review --mission <slug> --no-auto-commit --json`. Do **not**
     patch `_mt_pre_review_changed_files` — the empty diff must come from git.
  5. Assert: `pre_review_gate.outcome == "no_coverage"`, the reason names the planning lane
     and states the committed diff was not inspected, the reason does **not** contain
     "no changed files detected", `pre_review_gate.blocked` is false, and the transition was
     applied.
  6. Run it and record the RED evidence (the pre-fix reason is the false one) in the WP
     history note and in the PR's tests section later.
- **Files**: the new test module.
- **Parallel?**: No (single new file).
- **Notes**: If the fixture cannot reach the short-circuit without patching internals,
  report what blocked it instead of weakening the assertion.

### Subtask T003 – Same-fixture code-change control and no-dispatch proof

- **Purpose**: Non-vacuity: the new reason must be reserved, and the cheap skip must still
  cost nothing (tactic `acceptance-criteria-non-vacuity`, half-by-half proof).
- **Steps**:
  1. On the same fixture shape, add a **code-change** WP (frontmatter
     `execution_mode: code_change`, `lanes.json` lane other than `lane-planning`) with an
     empty changed-file set, and assert the incumbent wording is still recorded.
  2. Add a dispatch spy around the gate-dispatch seam that the module already exposes
     (`_mt_dispatch_transition_gates` / `_mt_dispatch_one_gate`) and assert it is never
     called for the planning arm.
  3. Keep both arms on one shared fixture builder so the positive and negative cases cannot
     drift apart.
- **Files**: the new test module.
- **Parallel?**: Yes with T004 once the assertions are fixed.
- **Notes**: The control must fail if the production change is a blanket message rewrite —
  verify by temporarily rewriting the string locally and confirming the control goes red,
  then revert.

### Subtask T004 – Implement the classification and the reason selection

- **Purpose**: The production fix, deliberately tiny.
- **Steps**:
  1. In `tasks_move_task_gates.py`, add a module-level constant for the new reason text
     (one place, referenced by both surfaces through the verdict).
  2. Add `_mt_pre_review_planning_lane_wp(st) -> bool`:
     - read the declared mode from the WP frontmatter with the module's existing
       `extract_scalar` idiom on `st.wp.frontmatter`; `planning_artifact` → true,
       any other non-empty mode → false;
     - only when the frontmatter declares nothing, read `lanes.json` through
       `placement_seam(st.main_repo_root, st.mission_slug, owned=st.owned).read_dir(
       MissionArtifactKind.LANE_STATE)` + `read_lanes_json` + `manifest.lane_for_wp(
       st.task_id)` + `is_planning_lane(lane)`;
     - catch `GuardedReadError` (from `kernel.errors`) and `OSError` and return `False`
       (unknown → today's wording); guard missing state attributes with `getattr`.
  3. Add `_mt_empty_changed_files_reason(st) -> str` returning the new constant for a
     planning-lane WP and the incumbent literal otherwise.
  4. Replace the literal in the `if not inputs.changed_files:` arm with a call to that
     helper, leaving the verdict construction (`_mt_empty_scope_verdict`, `NO_COVERAGE`)
     exactly as it is.
  5. Keep the docstrings current: `_mt_collect_transition_gate_verdicts` documents the
     short-circuit, so extend its docstring with the planning-lane case and cite #6792.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`.
- **Parallel?**: No.
- **Notes**: Do not add a new field to `_TransitionGateInputs` (existing tests construct it
  positionally); do not touch `pre_review_gate.py`.

### Subtask T005 – Target module test run

- **Purpose**: Green evidence at the blast radius the plan named.
- **Steps**: run, from the repo root with the mission's venv:
  - `uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py -q`
  - `uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_escape_hatch.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_baseline_read.py -q`
  - `uv run pytest tests/review -q`
  Record exact counts in the WP history note and the PR body. **Do not** run `make
  test-full` or any whole-repo sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Files**: none.
- **Parallel?**: No.
- **Notes**: A pre-existing red in any of these modules must be classified against
  `origin/main` in a clean worktree and cited, never skipped.

### Subtask T006 – Lint and type checks on the touched files

- **Purpose**: CI parity for the changed Python surface.
- **Steps**: `uv run ruff check` and `uv run ruff format --check` on the two touched files;
  `uv run mypy src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` (note the
  module is quarantined with `follow_imports = "skip"`; do not add suppressions to silence
  a pre-existing diagnostic — report it instead).
- **Files**: the two touched files.
- **Parallel?**: Yes with T005.
- **Notes**: No `# noqa` additions unless a genuine new violation demands a justified one.

## Test Strategy

- New module drives the real `move-task` CLI entry point on a real git repository; no
  mocking of the changed-file computation.
- One shared fixture builder feeds the planning arm and the code-change control arm.
- Dispatch spy proves the cheap skip still dispatches nothing.
- Assertions on the reason are exact-substring, not message-snapshot, so unrelated wording
  churn does not silently pass.

## Risks & Mitigations

- **Mislabeling single_branch code WPs** (their repo-root lane is `lane-planning`): the
  declared `execution_mode` wins; lane membership is only the fallback.
- **Corrupt `lanes.json` turning a skip into a failure**: catch `GuardedReadError`/`OSError`
  and degrade to today's wording.
- **String-duplication drift**: one constant, consumed by the verdict; both the JSON payload
  and the console line render from the same verdict.

## Review Guidance

- Confirm the new reason is reachable **only** from the empty-diff arm.
- Confirm the code-change control arm asserts the incumbent wording verbatim.
- Confirm no test was weakened, skipped or marked to make the suite pass, and that the two
  neighbouring pre-review gate modules are unmodified (`git diff --stat` on `tests/`).
- Confirm the classification imports the canonical seams and contains no `"lane-planning"`
  literal.
- Confirm the cheap skip: no dispatch, no subprocess, transition applied.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
