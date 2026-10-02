---
work_package_id: WP13
title: spec-commit names every argument's fate
dependencies:
- WP05
requirement_refs:
- FR-007
- FR-007a
- FR-016
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:52:51.683281+00:00'
subtasks:
- T002
- T069
- T070
- T071
- T072
- T073
phase: Phase 5 - Command consumers
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/spec_commit_cmd.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/spec_commit_cmd.py
- tests/specify_cli/cli/commands/test_spec_commit_cmd.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – spec-commit names every argument's fate

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

Today `spec-kitty spec-commit` reports `success: true` while it silently drops the status log and re-routes decision-ledger files onto the coordination branch (#5501). It reads only the caller-surface fields of `CommitRouterResult` (#5513 masking). After this WP, `spec-commit` names the fate of every argument in both text and JSON output, and never reports success while ignoring one (FR-007a).

Done means:
- R5 is green: for a coordination-routed Mission, `spec-commit` over `spec.md`, the ledger files, a trace and the status log reports:
  - `spec.md` committed on the **target branch**, and each ledger file's fate named on the surface the taxonomy assigns it (`artifact_home_for(MissionArtifactKind.DECISION_LEDGER)`). That is the target branch once WP12 lands; this WP does not depend on WP12, see the lane note;
  - the trace and the status log committed on the **coordination branch**, or refused with a named reason;
  - each fact appears in `surfaces` and in a per-input `arguments[]` list.
- JSON stays additive. Every existing key keeps its meaning, and `success` is `false` exactly when a surface is `refused` or `error`.
- Text output renders through WP05's shared `render_commit_outcome`, with no hand formatting. The exit code follows the shared rule: non-zero iff any surface is refused or errored.
- The `--target-branch` help text no longer promises a "post-commit ff-advance". WP05 retired it under FR-008.

## Context & Constraints

- **Spec**: FR-007 (per-surface outcomes, shared renderer), FR-007a (spec-commit names every argument's fate), FR-016 (R5), SC-003, US3.4.
- **Plan**: IC-07 (the spec-commit consumer, `spec_commit_cmd.py` L70-95 and L214-285), IC-10 (help text, L166-170), IC-01 (this WP's own T002 extracts the helpers from `spec_commit_command`).
- **Research**: D8 (consumer table and exit-code rule), D11 (`_try_advance_ref` retired), D12 (the ledger is now PRIMARY), R5.
- **Contract**: `contracts/commit-outcome.md`. Read the JSON example for spec-commit's `surfaces` and `arguments[]` carefully; it is the target shape.
- **Dependencies**:
  - WP05 provides `commit_outcome.py` (`render_commit_outcome`, `commit_outcome_payload`, the exit-code helper), `CommitRouterResult.surfaces`, owning-surface translation of the root-path status log, and the named refusals;
  - WP12 (separate lane, NOT a dependency) makes the ledger PRIMARY. WP12 owns the "spec-commit commits the ledger on the target branch" assertion. This WP asserts only that the ledger's fate is named on the taxonomy-assigned surface, so R5 holds in either landing order;
  - Your own T002 (moved from WP01) extracts the render branch into a helper. Work inside that helper.
- **Charter**: load `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`), review = opus.
- **Terminology**: say Mission in all user-facing strings. Name the sense of "primary" ("target branch", "coordination branch"); never bare "primary branch" when you mean the PRIMARY partition.
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP13` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`).
- Start with `spec-kitty agent action implement WP13 --agent claude`. Use the resolved workspace.
- **Lane-relevant sharing (updated by the post-tasks squad, P-m7)**: the `spec_commit_command` extraction moved here from WP01 as this WP's tidy-first first commit, so WP01 no longer owns these files. This WP runs in **its own lane**, based on WP05's tip (lane A), which already contains WP01's router and anchor-resolver extractions.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T002 – Extract helpers from `spec_commit_command` (spec_commit_cmd.py:155, C901 15)

- **Moved here from WP01 (post-tasks squad P-m7)**: this is this WP's **tidy-first FIRST commit**. It is a behaviour-preserving extraction with its own focused tests and no assertion edits, committed BEFORE the red-first test. Moving it lets this WP take its own lane after WP05 instead of serializing in lane A. Re-measure C901 for the target function(s) first (`ruff check --select C901 <file>`) and record before/after in the activity log.

- **Purpose**: WP13 replaces the success/failure rendering with the shared per-surface renderer, and adds per-argument fates. Today the rendering is inlined in the command body after the `commit_for_mission` call (≈L214-285, the `if result.status == "committed": payload = _payload(...)` branch chain).
- **Steps**:
  1. Read the whole function (L155 to its end) and `_payload` (≈L70-95).
  2. Extract, in this order, as private module functions:
     - `_resolve_spec_commit_inputs(...)`: argument and path normalisation (mission resolution, absolute-path computation, membership check, owned flag). Returns a small frozen dataclass or a tuple.
     - `_commit_spec_files(...)`: the boundary policy resolve plus the `commit_for_mission(...)` call. Keep the `kind=MissionArtifactKind.SPEC`, `target_branch` and `owned` arguments verbatim.
     - `_render_spec_commit_result(result, *, json_output, ...)`: the whole status branch that builds the payload or text and decides the exit code. **This is the one helper WP13 rewrites.**
  3. `spec_commit_command` becomes: resolve inputs → commit → render. Typer option declarations stay in the signature untouched, help texts included. WP13 changes `--target-branch` help.
  4. Keep exception handling exactly where it was (same exceptions caught, same messages, same exit codes).
- **Files**: `src/specify_cli/cli/commands/spec_commit_cmd.py`; tests in `tests/specify_cli/cli/commands/test_spec_commit_cmd.py` (append a `TestExtractedHelpers` class).
- **Validation**:
  - The existing `test_spec_commit_cmd.py`, `test_issue_2739_spec_commit_protected_primary_guard.py` and `tests/coordination/test_commit_router_fail_loud.py` are unchanged and green.
  - New tests call `_render_spec_commit_result` with a hand-built `CommitRouterResult` for each status (`committed`, `unchanged`, `error`/refused) and assert the identical payload keys and exit codes the CLI produced before.
- **Edge cases**:
  - `--json` and text mode must produce byte-identical output to the base. Capture one CLI output of each before the edit and diff them after.
  - Do not reorder `typer.Option` parameters (the help output order is user-visible).

### Subtask T069 – Red-first R5: `test_spec_commit_names_every_argument_fate`

- **Purpose**: Reproduce #5501 through the pre-existing CLI entry point. Commit the test alone, before any fix.
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_spec_commit_cmd.py`, add `test_spec_commit_names_every_argument_fate`. Build a coordination-routed Mission with WP02's factory (`tests._factories.coord_mission`), topology `coord`.
  2. Prepare these inputs:
     - a dirty `spec.md` (root checkout);
     - a ledger, by opening a decision through the production service so `decisions/DM-<ulid>.md` and `decisions/index.json` exist and are uncommitted in the root checkout;
     - a trace file `traces/approach.md` (dirty);
     - a status-log change dirty on the **coordination** copy, by appending a status event through the production path.
  3. Invoke the CLI through the repo's CLI runner (typer `CliRunner` or the existing helper in this test file):

     ```bash
     spec-kitty spec-commit --mission <slug> -m "spec batch" \
       kitty-specs/<dir>/spec.md kitty-specs/<dir>/decisions/index.json \
       kitty-specs/<dir>/decisions/DM-<ulid>.md kitty-specs/<dir>/traces/approach.md \
       kitty-specs/<dir>/status.events.jsonl --json
     ```
  4. Assert on the JSON:
     - `surfaces` has a primary entry whose `committed` contains `spec.md`, with `branch` = the target branch. Each ledger file is in the `committed` list of the surface given by `artifact_home_for(DECISION_LEDGER)`; compute the expected surface from the taxonomy, never hard-code it;
     - `surfaces` has a coordination entry whose `committed` contains the status log and the trace, with `branch` = the coordination branch;
     - `arguments` lists each of the five inputs exactly once, with its `fate` and `surface`.
  5. Assert on the branches with `git log -1 --name-only` per branch: the target branch tip holds `spec.md` (and the ledger, when the taxonomy says PRIMARY), and the coordination branch tip holds the status log row and the trace.
  6. Add a text-output variant asserting that one line per surface is printed.
- **Files**: `tests/specify_cli/cli/commands/test_spec_commit_cmd.py`.
- **Validation**: the test is red on the WP base. Depending on which predecessors are present, the status log is skipped or the ledger is routed to the coordination branch, and there are no `surfaces`/`arguments` keys. Record the red output.
- **Edge cases**:
  - Use the factory, which gives a real coordination topology with a materialized surface. A `lanes` Mission would make the assertion vacuous.
  - The trace may be passed by its root-checkout path. Traces keep the legacy copy behaviour while the coordination copy is absent (D7); assert the outcome, not the mechanism.
- **Fixture premise at the lane base (post-tasks squad R-M4)**: this WP's lane base is WP01–WP05; WP06's create seeding is NOT present. Build the coordination-routed fixture with WP02's `make_coord_mission(..., materialized=True)`, or `make_prefix_coord_mission` for a pre-fix leg. Before invoking the CLI, **assert the precondition** the red depends on: the coordination state is MATERIALIZED, the coordination copy of the record is dirty, and the root copy is clean (or whatever the scenario requires). A red then cannot come from a wrong fixture. Do NOT add a dependency on WP06.

### Subtask T070 – `_payload` gains `surfaces` and `arguments[]` (additive)

- **Purpose**: The JSON shape names every argument's fate (FR-007a) without breaking existing readers.
- **Steps**:
  1. Extend `_payload` (spec_commit_cmd.py ≈L70-95) with optional `surfaces` and `arguments` parameters. Keep every existing key: `result`, `success`, `committed`, `placement_ref`, `commit_hash`, `error`, `diagnostic`, `reason`, `error_code`.
  2. Build `surfaces` with `commit_outcome_payload(result)` from `specify_cli.coordination.commit_outcome`. Never serialize `SurfaceOutcome` by hand.
  3. Build `arguments` in a new small helper, `_argument_fates(abs_files, result, repo_root) -> list[dict]`. For each input path, as the caller passed it, repo-relative:
     - find its `PathFate` or committed entry across `result.surfaces`, matching on `path` or `owning_path`;
     - emit `{"path", "fate", "surface"}`, with `fate` ∈ `committed | unchanged | skipped | refused`, plus `reason` when the fate is not `committed`.

     Each input appears **exactly once**. An input missing from every surface is a contract violation: emit fate `refused` with reason `PATH_UNROUTABLE` and log it. Never drop an argument silently.
  4. Set `success = not any(s.status in ("refused", "error") for s in result.surfaces)` AND preserve today's error branches. Keep `committed` true when any surface committed.
- **Files**: `src/specify_cli/cli/commands/spec_commit_cmd.py`.
- **Validation**:
  - unit tests for `_argument_fates`: an all-committed batch; a mixed batch with one refused; an unchanged input; an input absent from the result, which becomes `refused` / `PATH_UNROUTABLE`;
  - existing JSON tests in the file stay green, apart from additive keys.
- **Edge cases**:
  - Inputs can be given relative or absolute (`_resolve_commit_inputs`, ≈L103). Normalize both to repo-relative before matching.
  - Owned-checkout paths: match on `owning_path` as well.

### Subtask T071 – Text output and exit code through the shared renderer

- **Purpose**: One renderer everywhere (FR-007; D8 parity), and the exit-code rule.
- **Steps**:
  1. In the render helper you extracted in T002 from the former L214-285 branch, replace the per-status `console.print` formatting for the success and unchanged arms. Print `render_commit_outcome(result)` lines, then one line per non-committed argument.
  2. Exit with the shared exit-code helper from `commit_outcome.py`: non-zero when any surface is `refused` or `error`; `skipped` and `unchanged` exit 0.
  3. Keep the existing actionable refusal for `no_op_wrong_surface` and the `ActionContextError` / `RuntimeError` arms. They now also carry `surfaces` when a result exists.
  4. Keep `spec_commit_command` at or below 15 on C901. T002 brings it to about 10; add logic in helpers, not in the command body.
- **Files**: `src/specify_cli/cli/commands/spec_commit_cmd.py`.
- **Validation**: a text-output assertion in R5; a check that the exit code is 1 when a surface is refused. Measure with `ruff check --select C901 src/specify_cli/cli/commands/spec_commit_cmd.py`.
- **Edge cases**: in `--json` mode, never print the rich text lines to stdout, because that breaks JSON parsing.

### Subtask T072 – `--target-branch` help text (IC-10 spec-commit leg)

- **Purpose**: WP05 deleted `_try_advance_ref` (FR-008). The help text must not promise a fast-forward that no longer happens.
- **Steps**:
  1. Rewrite the `--target-branch` option help (≈L166-170, currently "…used for the post-commit ff-advance (WP09 / FR-010)…"). State the parameter's remaining meaning: the Mission's target branch, passed to the commit router for owned-checkout placement. Confirm the exact current use in `commit_router.py` (≈L283/L290) before writing it.
  2. Do not remove the option. Removing it would break CLI compatibility.
- **Files**: `src/specify_cli/cli/commands/spec_commit_cmd.py`.
- **Validation**: a help-text snapshot test, if one exists (grep `ff-advance` in tests and update it). Also check `grep -rn "ff-advance" src/` to confirm no other user-facing reference remains in this file.
- **Edge cases**: generated agent command copies (`.claude/…`) are not edited; they come from source templates.

### Subtask T073 – Mixed-batch refusal, control and C-008 tests

- **Purpose**: Make FR-007 non-vacuous. A refusal on one surface must be visible, and the clean path stays `unchanged`.
- **Steps**:
  1. `test_spec_commit_reports_refused_coordination_surface`:
     - hold the Mission's status lock in the test (`feature_status_lock` from `specify_cli.status.locking`, with a short timeout fixture) while running spec-commit on a batch with `spec.md` plus the coordination-dirty status log;
     - assert the primary surface is `committed`, the coordination surface is `refused` with reason `STATUS_LOCK_HELD`, `success: false`, and the exit code is non-zero.

     If lock timeouts are slow, use the lock's configurable timeout rather than sleeps.
  2. `test_spec_commit_clean_status_log_reports_unchanged`: a clean coordination copy yields fate `unchanged` with reason `no_op_already_committed`. This is the positive control.
  3. `test_spec_commit_lanes_mission_output_unchanged` (C-008): on a `lanes` Mission, the existing keys and values are identical to today's, and `surfaces` holds a single primary entry.
- **Files**: `tests/specify_cli/cli/commands/test_spec_commit_cmd.py`.
- **Validation**: all green. Each one would fail if the shared renderer were bypassed or if a surface were masked.
- **Edge cases**: also run `tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py`. Its expectations about `committed: false` plus `reason` must still hold.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Stale wording**: every "WP01 extracted …" statement in this prompt is wrong. The `spec_commit_command` extraction is **this WP's own T002**, and the function is at **C901 15 (zero headroom)** on the base. Work inside the helpers *you* extract in T002.
- **`_resolve_commit_inputs` (L103) already exists**: extend or rename it consistently instead of adding a near-duplicate `_resolve_spec_commit_inputs`.
- **`--target-branch`** is also passed to `resolve_owned_or_refuse(target_override=target_branch)` (L200), so the help rewrite must mention the owned-checkout target override.
- **Owned checkout**: there is no partition grouping (router L281), so `surfaces` has a single entry. Mirror this in an owned test.
- Keep stdout clean in `--json` mode (the `console.print` arms are text-only).
- **C3**: the help text states that `success` is `false`, with a non-zero exit, when any surface is refused or errored. Record the reference-doc delta in the activity log for WP22.
- **Pins**: `test_spec_commit_cmd.py` (existing JSON keys); `test_issue_2739_spec_commit_protected_primary_guard.py` (B03, B11, B16); `tests/coordination/test_commit_router_fail_loud.py`.

## Targeted test surface

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/test_spec_commit_cmd.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py -q
uv run --frozen pytest tests/specify_cli/coordination/test_commit_router_partition.py tests/specify_cli/coordination/test_commit_router_partition_authority.py tests/coordination/test_commit_router_fail_loud.py -q
uv run --frozen pytest tests/coordination/test_commit_outcome.py -q
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- `tests/integration/test_owned_lifecycle_acceptance_e2e.py` and `tests/integration/test_explicit_checkout_commands.py` also exercise spec-commit. They are CI-owned; do not run them locally. Mention them in the PR.
- Record the commands and counts in the activity log.
- **Baseline-red gotcha**: classify reds you did not cause as one of: known P0, CI environment, stale install, or stale venv.

## Quality gates

- C901 ≤ 15 for `spec_commit_command` and every helper you add or touch (NFR-004).
- `ruff check` and `ruff format --check` on the changed files; `mypy --strict` on the changed files. No new suppressions (NFR-005).
- ≥ 90% coverage on new and changed lines, with a focused test per new helper (`_argument_fates`) and per branch (NFR-003).
- Repeated reason or fate literals (three or more uses) become module constants, or come from `commit_outcome.py` (Sonar S1192).
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5501 #5513

## Definition of Done

- R5 was red on the WP base and is green on the final commit. The red-first test commit precedes the fix commits.
- JSON is additive: `surfaces` and `arguments[]`, with every input exactly once and `success=false` on a refused or errored surface.
- Text renders through `render_commit_outcome`, and the exit-code rule applies.
- The help text no longer mentions the ff-advance.
- The refused, unchanged and C-008 tests are green. ruff, format and mypy are clean; coverage is at least 90%.

## Risks & Mitigations

- **Breaking JSON consumers** (agents parse `success`). Mitigation: additive keys only. `success=false` happens only on a real refusal, which is the defect being fixed; note it in the PR.
- **An argument that matches no surface** (path-normalisation bugs). Mitigation: the `PATH_UNROUTABLE` fallback is tested, so nothing is ever dropped.
- **Lock-held test flakiness**. Mitigation: use the lock's configurable timeout and never sleep-poll (testing-flakiness policy).

## Review Guidance

- The reviewer (opus, a different agent from the implementer) verifies red→green: R5 was RED on the WP base and is GREEN on the final commit.
- Confirm that no `SurfaceOutcome` is formatted by hand in `spec_commit_cmd.py`.
- Check `arguments[]` completeness in the tests: every input exactly once.
- Confirm existing JSON keys are unchanged in the `lanes` control.
- Confirm C901 of `spec_commit_command` is at or below 15.

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
