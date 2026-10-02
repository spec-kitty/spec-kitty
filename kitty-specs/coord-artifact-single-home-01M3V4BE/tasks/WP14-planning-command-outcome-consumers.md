---
work_package_id: WP14
title: Planning-command and retrospect consumers render per-surface outcomes
dependencies:
- WP05
requirement_refs:
- FR-003
- FR-007
- FR-016
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:52:10.320738+00:00'
subtasks:
- T003
- T074
- T075
- T076
- T077
- T078
phase: Phase 5 - Command consumers
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_setup_plan.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py
- tests/orchestrator_api/test_commit_outcome_rendering.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/git/report_transaction.py
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/cli/commands/retrospect.py
- src/specify_cli/cli/commands/agent_retrospect.py
- tests/git/test_report_transaction.py
- tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py
- tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py
- tests/orchestrator_api/test_commit_outcome_rendering.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Planning-command and retrospect consumers render per-surface outcomes

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Several commands either read only the caller-surface fields of `CommitRouterResult` or discard the result outright, so a skipped or refused surface goes unnoticed (#5513, #5501). This WP migrates the remaining planning-command consumers and `retrospect` onto WP05's shared commit-outcome contract. It also moves retrospect's event appends onto the write-location accessor (FR-003).

Done means:
- R11, retrospect half, is green: `retrospect` reports each surface's outcome, so a skipped coordination surface is visible.
- **setup-plan**: the `_commit_to_branch` consumer (`mission_setup_plan.py` ≈L237) renders through `render_commit_outcome` and adds JSON `surfaces`. The two discarded-result sites (≈L892 gap analysis, ≈L951 generator config) print a warning when a surface is neither `committed` nor `unchanged`.
- **record-analysis** (`mission_record_analysis.py` ≈L374, inside `record_analysis` itself; extract that block first — see Binding corrections), the **orchestrator API** (`orchestrator_api/commands.py` ≈L3018) and the **report transaction** (`git/report_transaction.py` ≈L199) all render through the shared pair. JSON stays additive.
- **retrospect**: `_canonical_events_path` (≈L109) splits reads (keep the read resolver) from appends (`write_dir(STATUS_STATE)`), and `agent_retrospect._canonical_events_dir` (≈L198) does the same. The commit at ≈L315 renders per-surface outcomes.
- Non-coordination Missions keep identical output (C-008), and JSON is additive only.

## Context & Constraints

- **Spec**: FR-003 (retrospect and agent-retrospect event appends are a writer family), FR-007 (every consumer renders through the shared renderer), FR-016 (R11), SC-003, US3.9.
- **Plan**: IC-07 (consumer table; research D8 rows setup-plan, record-analysis, report transaction, orchestrator API, retrospect) and IC-04 (retrospect row: "split: reads keep the resolver, appends use `write_dir`").
- **Research**: D8 (rule: discarded-result sites render a warning only when a surface is not `committed`/`unchanged`; exit non-zero iff a surface is refused or errored), D1 (accessor), R11.
- **Contract**: `contracts/commit-outcome.md` ("retrospect, setup-plan, record-analysis: add `surfaces` to their existing commit payloads").
- **Dependencies**:
  - WP05 provides `commit_outcome.py` and `CommitRouterResult.surfaces`;
  - WP04 provides `PlacementSeam.write_dir` (transitively, through WP05);
  - Your own T003 (moved from WP01) extracts `record_report_transaction`'s commit call into one helper. Edit that helper, not the main body.
- **Leave alone**:
  - `record_analysis` (`mission_record_analysis.py` ≈L225, C901 13): extract the suppress-and-commit block (L355-391) into a private helper first, then render there (Binding corrections);
  - `setup_plan` (C901 11) must stay at or below 15.
- **Charter**: load `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`), review = opus.
- **Terminology**: say Mission, never feature, and name the sense of "primary".
- **C-006**: targeted tests only.
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP14` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`).
- Start with `spec-kitty agent action implement WP14 --agent claude`. Use the resolved workspace path.
- **Lane-relevant sharing (updated by the post-tasks squad, P-m7)**: the `record_report_transaction` extraction moved here from WP01 as this WP's tidy-first first commit, so WP01 no longer owns these files. This WP runs in **its own lane**, based on WP05's tip (lane A), which already contains WP01's router and anchor-resolver extractions.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T003 – Extract helpers from `record_report_transaction` (git/report_transaction.py:130, C901 15)

- **Moved here from WP01 (post-tasks squad P-m7)**: this is this WP's **tidy-first FIRST commit**. It is a behaviour-preserving extraction with its own focused tests and no assertion edits, committed BEFORE the red-first test. Moving it lets this WP take its own lane after WP05 instead of serializing in lane A. Re-measure C901 for the target function(s) first (`ruff check --select C901 <file>`) and record before/after in the activity log.

- **Purpose**: WP14 renders this transaction's commit outcome per surface. The `commit_for_mission(...)` call at ≈L199 and the reads of `outcome.status` / hash / diagnostic that follow should sit in one helper.
- **Steps**:
  1. Read the function. It records the analysis report, verifies the working tree did not change concurrently (the `_working(...) != working or collect_material_inputs(...) != inputs` guard before the commit), commits, and builds a result dict.
  2. Extract:
     - `_guard_unchanged_inputs(...)`: the concurrency re-check that raises `ValueError("Repository changed before report commit; ...")`.
     - `_commit_report(...)`: the `commit_for_mission(...)` call plus the interpretation of `outcome` into the returned dict fields. **WP14 swaps rendering here.**
     - Optionally, the write/restore preamble if it is the remaining complexity source. Keep the docstring rule "never reset or restore concurrent operator state" intact.
  3. The keyword-only signature and the returned `dict[str, object]` keys are unchanged.
- **Files**: `src/specify_cli/git/report_transaction.py`; tests in `tests/git/test_report_transaction.py`.
- **Validation**:
  - `tests/git/test_report_transaction.py` and `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py` stay green with no edits.
  - The new helper tests cover each `outcome.status` arm and the `ValueError` guard.
- **Edge cases**: the function must still never reset or restore operator state on failure paths. Keep the exact order of the `wrote` flag handling.

### Subtask T074 – Red-first: retrospect and setup-plan mask a skipped surface; retrospect appends on the coordination surface

- **Purpose**: Witness the masking and the misplaced append through the pre-existing CLI entry points, before fixing them. Commit the tests alone.
- **Steps**:
  1. **R11, retrospect half.** In `tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py`, add `test_retrospect_reports_each_surface`.
     - Build a coordination-routed Mission with WP02's factory (`tests._factories.coord_mission`).
     - Run the retrospect command path that auto-commits (`_maybe_auto_commit`, L294-344 in `retrospect.py`, is reached from the retrospect create/record commands; use the CLI).
     - Make one surface's group commit and the other's be skipped or refused. For example, hold the status lock so the coordination group is refused with `STATUS_LOCK_HELD` while the PRIMARY retrospective record commits.
     - Assert that the output names the coordination surface's fate.

     At the base it is masked: `_merge_group_results` returns only the caller-surface fields.
  2. **setup-plan.** In `tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py` (new), add `test_setup_plan_reports_skipped_surface`. Drive `spec-kitty agent mission setup-plan --json` against a fixture where a commit request touches two surfaces, then assert that `surfaces` is in the JSON and that the skipped surface is rendered.
  3. **Retrospect append location.** Add `test_retrospect_append_on_prefix_mission_lands_on_coordination_surface`:
     - use WP02's pre-fix builder (`make_prefix_coord_mission`, worktree EMPTY);
     - run a retrospect event append through the CLI;
     - assert the event lands in the coordination worktree's log, seeded once, with the root-checkout log restored.

     At the base it lands in the root checkout (`resolve_status_surface` → EMPTY → root fallback).
- **Files**: the two test files above.
- **Validation**: all three are red on the WP base. Paste the red output into the activity log.
- **Edge cases**:
  - Retrospect auto-commit only runs when `get_auto_commit_default(repo_root)` is true. Enable it in the fixture.
  - Find the exact CLI that appends retrospect events with `grep -n "_canonical_events_path\|_canonical_events_dir" src/specify_cli/cli/commands/retrospect.py src/specify_cli/cli/commands/agent_retrospect.py`.
- **Fixture premise at the lane base (post-tasks squad R-M4)**: this WP's lane base is WP01–WP05; WP06's create seeding is NOT present. Build the coordination-routed fixture with WP02's `make_coord_mission(..., materialized=True)`, or `make_prefix_coord_mission` for a pre-fix leg. Before invoking the CLI, **assert the precondition** the red depends on: the coordination state is MATERIALIZED, the coordination copy of the record is dirty, and the root copy is clean (or whatever the scenario requires). A red then cannot come from a wrong fixture. Do NOT add a dependency on WP06.

### Subtask T075 – setup-plan renders through the shared pair

- **Purpose**: setup-plan is the most-used planning committer, and today it hides the coordination surface.
- **Steps**:
  1. `_commit_to_branch` (`mission_setup_plan.py` ≈L181; call ≈L237; status checks ≈L248-280). Keep the existing status arms (committed / unchanged / no_op_wrong_surface / error), which carry behaviour, but print the surface lines with `render_commit_outcome(router_result)` instead of a hand-written message. Return or attach `commit_outcome_payload(router_result)` so the JSON envelope of `setup-plan` gains `surfaces`, additively.
  2. The discarded-result sites at ≈L892 (gap analysis) and ≈L951 (generator config) call `commit_for_mission(...)` and ignore the result. Capture it and call a small helper, `_warn_on_incomplete_surfaces(result)`, which prints the rendered lines only when some surface is neither `committed` nor `unchanged` (research D8 rule). Exit codes for these best-effort commits stay unchanged.
  3. Put the helper in `commit_outcome.py` only if WP05 already provides it. Otherwise add it locally and keep it tiny (one shared definition per module).
- **Files**: `src/specify_cli/cli/commands/agent/mission_setup_plan.py`.
- **Validation**:
  - T074's setup-plan test is green;
  - existing setup-plan tests are green (`grep -rl "setup.plan\|mission_setup_plan" tests --include="test_*.py" | grep -v integration`);
  - C901 of `setup_plan` and `_commit_to_branch` stays at or below 15.
- **Edge cases**: in `--json` mode, warnings go to stderr or into the JSON envelope, never onto stdout as text.

### Subtask T076 – record-analysis, orchestrator API and report transaction

- **Purpose**: Close the remaining D8 rows that read or discard the result.
- **Steps**:
  1. **record-analysis.** At `mission_record_analysis.py` ≈L374, in the private helper you extract from `record_analysis` (L355-391), capture the `commit_for_mission(...)` result. Render it through `render_commit_outcome` when a surface is not `committed`/`unchanged`, and add `surfaces` to the command's JSON payload where that payload is built. Do not touch `record_analysis` (≈L225).
  2. **Orchestrator API.** At `orchestrator_api/commands.py` ≈L3018, the call sits inside a `contextlib.suppress(...)` block whose result is discarded. Capture it and add an additive payload field `commit_surfaces` (via `commit_outcome_payload`) to the orchestrator envelope this function returns, plus a warning entry when a surface is not committed/unchanged. Keep the suppression semantics: a commit failure never undoes the write. Check the orchestrator contract tests for envelope-shape pins (`tests/orchestrator_api/`), and add only new keys.
  3. **Report transaction.** At `git/report_transaction.py` ≈L199, in the helper you extracted in T003, read the outcome through the shared pair. The returned dict gains `surfaces`, and its `status`, `commit_hash` and `diagnostic` keep their existing meaning.
- **Files**: the three source files, `tests/git/test_report_transaction.py`, and `tests/orchestrator_api/test_commit_outcome_rendering.py` (new).
- **Validation**:
  - for each consumer, a one-surface-skipped fixture shows the skip in the output or payload;
  - existing tests are green: `tests/git/test_report_transaction.py`, `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`, and the orchestrator tests that cover record-analysis.
- **Edge cases**:
  - The analysis report is PRIMARY (`ANALYSIS_REPORT`), so `surfaces` usually has a single primary entry. The coordination entry only appears when a mixed batch occurs. Write the fixture so both appear, for example by including a status log in the batch through the report transaction's file list if its API allows; otherwise test via a stubbed `CommitRouterResult`, labelled as a unit test.
  - The orchestrator API is an external contract (charter: central CLI-SaaS / orchestrator contract). Additive only.

### Subtask T077 – retrospect: split read from append; agent-retrospect the same

- **Purpose**: Retrospect and agent-retrospect event appends are an FR-003 writer family. They must write through the write-location accessor, not through a read resolver that substitutes the repository root checkout.
- **Steps**:
  1. `retrospect.py::_canonical_events_path` (≈L109) currently serves both reads and commits through `resolve_status_surface`, with a root fallback. Split it in two:
     - `_canonical_events_read_path(...)` keeps today's behaviour for reads;
     - `_canonical_events_write_path(repo_root, mission_slug)` returns `placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.STATUS_STATE).path / "status.events.jsonl"`.

     Update every append or commit caller to the write variant and every read caller to the read variant (grep the module).
  2. `agent_retrospect.py::_canonical_events_dir` (≈L198): the same split, with a write variant on `write_dir(STATUS_STATE).path`. Keep the `fallback_dir` semantics for reads only.
  3. Write-side errors from `write_dir` (`COORDINATION_BRANCH_DELETED`, remote-only `COORDINATION_WORKTREE_UNMATERIALIZED`, `COORD_SEED_FORK_REFUSED`) surface as the command's actionable error. Never fall back to the repository root checkout on the write path.
  4. `retrospect.py` ≈L315 (`_maybe_auto_commit`): after `commit_for_mission`, render `render_commit_outcome(result)` lines when a surface is not committed/unchanged. Keep the existing protected-target warning helpers (`_refused_on_protected_target`, `_warn_protected_target_refused`), which carry specific remediation text, and add the surface lines.
- **Files**: `src/specify_cli/cli/commands/retrospect.py`, `src/specify_cli/cli/commands/agent_retrospect.py`.
- **Validation**:
  - T074's retrospect tests are green;
  - existing retrospect tests are green (`tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py`, `tests/retrospective/`, `grep -rl "agent_retrospect" tests`);
  - the read path still falls back for a legacy Mission without `meta.json`, as a control.
- **Edge cases**:
  - The ledger reader at `retrospect.py` ≈L281 (`is_coord_residue_churn`) flips with WP12's reclassification. No code change is needed here; WP12 owns its test. Do not change that line.
  - WP20's gate scans `retrospect.py::_canonical_events_path` and `agent_retrospect.py::_canonical_events_dir` by qualname. If you rename them, record the new write-function qualnames in the activity log so WP20 scans the function that now holds the write.

### Subtask T078 – Consumer tests, C-008 controls and JSON additivity

- **Purpose**: Make every migrated consumer's change observable, and prove that non-coordination Missions are untouched.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py`, add one test per consumer (setup-plan, record-analysis, report transaction, retrospect, agent-retrospect append) asserting:
     - text output carries the surface line of a skipped or refused surface;
     - JSON carries `surfaces` (or `commit_surfaces` for the orchestrator) with that surface's fate.
  2. C-008 controls: on a `lanes` Mission and a `single_branch` Mission, each consumer's existing JSON keys and values are byte-identical apart from the new additive key, and the event append path is the repository-root Mission dir (unchanged).
  3. A JSON-additivity test: load a recorded pre-change payload shape (the keys only) and assert that it is a subset of the new payload.
- **Files**: the test files in `owned_files`.
- **Validation**: all green, and coverage of the new helpers is at least 90%.
- **Edge cases**: avoid tautological render tests. Assert the surface name, the fate and the reason that reach the user, not that a function was called (DIRECTIVE_041).

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **`_maybe_auto_commit` lives in `retrospect.py:294`** (commit at L315), not in `mission_record_analysis.py`.
  - The record-analysis commit is **inside `record_analysis`** (`mission_record_analysis.py` L355-391, under `contextlib.suppress`, C901 13).
  - **First** extract that suppress-and-commit block into a private helper (behaviour-preserving, its own commit), then render there. "Leave `record_analysis` alone" is superseded.
- **T074 step 1**: the retrospect helper is `_maybe_auto_commit` (L294-344), not `_auto_commit` around L305-330.
- **Stale wording**: "WP01 extracted `record_report_transaction`" is wrong. That extraction is **this WP's own T003**, and the function is at C901 15 on the base.
- **Orchestrator**: `_do_record_analysis_write` (L2979) commits at L3018 under `contextlib.suppress` and returns the `write_analysis_report` result. Change its return so it also carries the router result. Its caller `record_analysis` (C901 12, L3031) runs it under `_run_write_with_timeout`.
- Existing protected-target warnings (`_refused_on_protected_target`, `_warn_protected_target_refused`) must keep firing, without double-printing.
- **Retrospect read variant**: keep `_canonical_events_path`'s read variant byte-identical, including the `candidate_feature_dir_for_mission` fallback. If the write moves into `_canonical_events_write_path`, record the new qualname for WP20's census.
- **Repro**:
  - retrospect auto-commit is gated by `get_auto_commit_default(repo_root)`;
  - `create` needs a completed Mission (`_check_mission_completed` L170); reuse the builder in `test_retrospect_doctor_surface_4090.py`.
- **C3**: update help text where output changes. Record the reference-doc delta for WP22.

## Targeted test surface

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py tests/orchestrator_api/test_commit_outcome_rendering.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py tests/retrospective/ -q
uv run --frozen pytest tests/git/test_report_transaction.py tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py -q
uv run --frozen pytest $(grep -rl "mission_setup_plan\|setup-plan" tests --include="test_*.py" | grep -v -e integration -e e2e -e architectural) -q
uv run --frozen pytest tests/orchestrator_api/ -q
uv run --frozen pytest tests/coordination/test_commit_outcome.py -q
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record the commands and counts in the activity log.
- **Baseline-red gotcha**: classify reds you did not cause as one of: known P0, CI environment, stale install, or stale venv. Fold only branch-red plus base-green failures.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004): `setup_plan`, `_commit_to_branch`, `_maybe_auto_commit`, the orchestrator function and the retrospect helpers. Extract before you add.
- `ruff check` and `ruff format --check` on the changed files; `mypy --strict` on the changed files. No new suppressions (NFR-005).
- ≥ 90% new and changed-line coverage, with a focused test per new helper or branch (NFR-003).
- Repeated literals used three or more times become constants (S1192).
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5513 #5501

## Definition of Done

- The T074 tests (R11 retrospect half, setup-plan masking, retrospect append location) were red on the WP base and are green on the final commit.
- setup-plan, record-analysis, the orchestrator API, the report transaction and retrospect all render through `render_commit_outcome` / `commit_outcome_payload`, with no hand formatting.
- Retrospect and agent-retrospect appends use `write_dir(STATUS_STATE)`, and reads keep the resolver. Renamed qualnames are recorded for WP20.
- C-008 and JSON-additivity tests are green. ruff, format and mypy are clean; coverage is at least 90%.

## Risks & Mitigations

- **Orchestrator API contract drift.** Mitigation: additive keys only; run `tests/orchestrator_api/`.
- **Retrospect write path now seeds or materializes** on first append for pre-fix Missions, which is a deliberate side effect. Mitigation: the T074 test asserts that the seed happens once and that the root-checkout copy is restored.
- **Discarded-result sites becoming noisy.** Mitigation: warn only when a surface is not committed/unchanged (D8).

## Review Guidance

- The reviewer (opus, a different agent from the implementer) verifies red→green: the T074 tests were RED on the WP base and are GREEN on the final commit.
- Confirm that no consumer reads `result.status` / `commit_hash` alone to decide what the user sees about other surfaces.
- Confirm the retrospect write path cannot reach the repository root checkout for a coordination-routed Mission.
- Confirm that `record_analysis`'s suppress-and-commit block (L355-391) was extracted into a private helper as a separate behaviour-preserving commit **before** rendering was added (~~"record_analysis is untouched"~~ struck in round 5), and that the C901 limits hold.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T14:47:50Z – cursor – shell_pid=1007450 – Cycle 3: removed the formatted retrospect.py ruff-format exclude and emit the write-location refusal as failure_category other.
