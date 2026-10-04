---
work_package_id: WP02
title: Upgrade outcome owns kind, reasons and rendering
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-013
- FR-014
- FR-017
- FR-018
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-4925-upgrade-outcome-single-rendering
merge_target_branch: issue-4925-upgrade-outcome-single-rendering
branch_strategy: Planning artifacts for this mission were generated on issue-4925-upgrade-outcome-single-rendering. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4925-upgrade-outcome-single-rendering unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-outcome-single-rendering-01M444Q6
base_commit: ab9860a633307393f1b5e24d16c92c1cc0af2f78
created_at: '2026-10-04T19:33:50.446419+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Functional change
history:
- at: '2026-10-04T19:11:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_upgrade_outcome_regression_4925.py
- tests/upgrade/test_upgrade_outcome_kind.py
- tests/upgrade/test_upgrade_outcome_rendering.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/upgrade/test_upgrade_char_net.py
- tests/upgrade/test_worktree_stamp_guard.py
- tests/specify_cli/cli/commands/test_upgrade_command.py
- src/specify_cli/upgrade/outcome.py
- src/specify_cli/upgrade/finalize.py
- src/specify_cli/cli/commands/upgrade.py
- tests/upgrade/test_upgrade_outcome_regression_4925.py
- tests/upgrade/test_upgrade_outcome_kind.py
- tests/upgrade/test_upgrade_outcome_rendering.py
- tests/upgrade/test_finalizer.py
- tests/upgrade/test_upgrade_integration.py
- tests/specify_cli/tool_surface/test_drift_policy.py
- tests/specify_cli/tool_surface/test_surface_repair_wiring.py
- tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py
- docs/api/cli-commands.md
- src/specify_cli/_completion_manifest.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Upgrade outcome owns kind, reasons and rendering

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Fix GitHub issue 4925 structurally (spec FR-001 to FR-011, FR-013, FR-014, FR-017, FR-018; NFR-001 to NFR-004).

Today, on an up-to-date project with one hand-edited managed file, `spec-kitty upgrade --yes` prints `Project is already up to date!` and exits 1 with no reason, while `--json` reports `status: failed` and the drift error. The exit code already comes from one place (`UpgradeOutcome.derive_exit_code`); the error list and the closing line do not.

Done when the contract in `contracts/upgrade-outcome-contract.md` holds for every row, on both the migrations path and the no-migrations path, in text and JSON, and:

- `UpgradeOutcome` owns `kind`, `reasons`, `errors()`, `warnings()`, `status` and `closing_line()`; `surface_drift_failed` is gone.
- `src/specify_cli/cli/commands/upgrade.py` contains no closing-line text and builds no error list of its own.
- The message `drift in 0 file(s)` cannot be produced.
- A non-zero exit always prints at least one reason.

## Context & Constraints

- Read first: `.kittify/charter/charter.md` (Standing Orders 2, 4, 5), then this mission's `spec.md`, `plan.md`, `data-model.md` and `contracts/upgrade-outcome-contract.md` under `kitty-specs/upgrade-outcome-single-rendering-01M444Q6/`.
- Load doctrine with `spec-kitty charter context --action implement`.
- **Read-only**: `src/specify_cli/upgrade/runner.py` and `src/specify_cli/upgrade/assessment.py` (a sibling mission and an open pull request own them). `worktree_failures` stays `list[str]`.
- Do not change the planner / compatibility exit paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, agent-check flags).
- Do not edit the mission's tracer files under `traces/`; report friction and decisions in your hand-back and the orchestrator records them.
- Use CodeGraph first: `codegraph explore "<symbols>"`.
- In a lane worktree there is no `.venv`: run `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest ...`, and drive the CLI in-process (`CliRunner`), never the global `spec-kitty` binary. Never a bare `uv run`.
- Tests: run only the files named in this prompt. No whole directories, no `make test-fast`, no full `tests/architectural/`.
- New code passes `ruff check`, `ruff format --check --force-exclude <files>` and `mypy --strict` with no new suppressions. Complexity ≤ 15 per function. Repeated literals (3+) become constants.
- No machine-local paths or personal data in code, tests or commit messages.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path that `spec-kitty implement` returns.

- Depends on WP01 (the legacy surface-repair branch is already removed). If WP01 reported that the branch had to stay, route it through `SurfaceRepairReport` too.
- Unresolved drift keeps a non-zero exit (spec C-002). Do not change that.
- JSON: add keys, never remove or rename (NFR-002).

## Subtasks & Detailed Guidance

### Subtask T004 – Red-first regression repro (first commit, must be RED)

- **Purpose**: charter ATDD rule and ADR `2026-07-17-1`: the defect is witnessed through the pre-existing entry point before the fix.
- **Steps**:
  1. Create `tests/upgrade/test_upgrade_outcome_regression_4925.py`, marked `@pytest.mark.regression`, driving the real `upgrade` command with `CliRunner` on a no-migrations project whose prepared repairs report one `consent_required` disposition. Look at `tests/specify_cli/tool_surface/test_drift_policy.py` (text-mode test near line 553 and its JSON twin) and `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py` for how existing tests build a drifted project; reuse their fixture approach, do not invent a mock of the outcome.
  2. Assert, in text mode: exit code non-zero; output contains `Unresolved tool-surface drift in 1 file(s)`; output does **not** contain `already up to date`.
  3. Add a second test for the `drift in 0 file(s)` misreport: a repair result that is not applied, with no drifted file, in JSON mode: assert no entry in `errors` contains `in 0 file(s)` and `errors` is non-empty.
  4. Capture note: `test_upgrade_command_skill_drift.py` says the human renderer's drift lines "do not reach the CliRunner capture". Check whether that is a real harness limit (the module-level rich `console`) or just the bug. If the console is not captured by `CliRunner`, patch the module `console` with a recording `Console(file=io.StringIO())` in a fixture and assert on that.
  5. Run it, confirm both tests fail for the right reason, paste the failure lines into the commit body, and commit alone: `test(upgrade): reproduce the silent non-zero exit on a no-migrations run with drift`.
- **Files**: `tests/upgrade/test_upgrade_outcome_regression_4925.py` (new).

### Subtask T005 – Outcome model

- **Purpose**: one object that knows what happened (FR-001, FR-002, FR-008, FR-009, FR-010, FR-018).
- **Steps** (all in `src/specify_cli/upgrade/outcome.py`, following `data-model.md`):
  1. `UpgradeOutcomeKind(StrEnum)`: `APPLIED="applied"`, `NO_OP="no_op"`, `DRIFT_UNRESOLVED="drift_unresolved"`, `FAILED="failed"`.
  2. `UpgradeFailureReason(StrEnum)`: `MIGRATION_FAILED`, `ACTIVATION_ERROR`, `WORKTREE_FAILURE`, `SURFACE_REPAIR_FAILED`, `PREVIEW_INCOMPLETE`, `SURFACE_DRIFT` (values are the lower-case names).
  3. Frozen dataclass `SurfaceRepairReport(drifted_paths: tuple[Path, ...] = (), failed: bool = False, preview_incomplete: bool = False, failure_messages: tuple[str, ...] = ())`.
  4. `UpgradeOutcome`: remove `surface_drift_failed`; add `had_migrations: bool = False`, `drifted_paths: list[Path]`, `surface_repair_failed: bool = False`, `preview_incomplete: bool = False`, `surface_repair_messages: list[str]`. Add a method `record_surface_repair(report: SurfaceRepairReport) -> None`.
  5. `reasons` property (ordered as in `data-model.md`), `kind` property (any reason other than `SURFACE_DRIFT` → `FAILED`; only drift → `DRIFT_UNRESOLVED`; none → `APPLIED` if `had_migrations` else `NO_OP`), `effective_success` = `not self.reasons`.
  6. `errors() -> list[str]`: ordered and de-duplicated: `result.errors`, `activation_errors`, `worktree_failures`, `surface_repair_messages`, then the drift message iff `drifted_paths`. Move the drift wording here as a module constant; the count is `len(drifted_paths)`. The message points at `spec-kitty doctor tool-surfaces` and must not mention `--fix`. If `SURFACE_REPAIR_FAILED` or `PREVIEW_INCOMPLETE` holds and nothing in the list explains it, append a generic line so invariant 3 holds (a non-zero exit always has an error).
  7. `warnings() -> list[str]`: `result.warnings` plus `repair.message` when `repair.failed` and a message exists. First check whether the mission-state gate already prints that message itself (`_teamspace_mission_state_gate`); if it does, include only the isolation-boundary message set in `finalize.py` to avoid printing twice.
  8. `status` property: `success` for applied, `up_to_date` for no-op, `failed` otherwise.
  9. `closing_line() -> str`: per the contract table, with the dry-run variant for a completed dry run on the migrations path. Plain text, no rich markup. Closing-line texts are module constants here and nowhere else.
  10. `derive_exit_code()`: `0 if self.kind in (APPLIED, NO_OP) else 1`. Still the only site.
  11. Update the module docstring; declare nothing in `__all__` unless the module already does.
- **Files**: `src/specify_cli/upgrade/outcome.py`.

### Subtask T006 – Unit matrix for the outcome

- **Purpose**: pin the truth table without the CLI (fast, exhaustive).
- **Steps**: `tests/upgrade/test_upgrade_outcome_kind.py`, parametrised over every combination of the five failure inputs × `had_migrations` × `dry_run` that is meaningful. Assert `kind`, `reasons`, `status`, `exit_code`, `closing_line()` and the five invariants in `data-model.md` (notably: drift message present iff `drifted_paths`, count equal; `errors()` non-empty whenever exit is non-zero; a failed mission-state `repair` adds no reason). Include the precedence case (repair failure + two drifted files → `failed`, both messages, count 2).
- **Files**: `tests/upgrade/test_upgrade_outcome_kind.py` (new).

### Subtask T007 – Finalizer and surface-repair step return a report

- **Purpose**: replace the boolean that carried three meanings.
- **Steps**:
  1. `src/specify_cli/upgrade/finalize.py`: `run_surface_repair: Callable[[], SurfaceRepairReport]`; replace `outcome.surface_drift_failed = bool(run_surface_repair())` with `outcome.record_surface_repair(run_surface_repair())`. Update the docstring.
  2. `_finalizer_step_surface_repair` in `cli/commands/upgrade.py` returns a `SurfaceRepairReport`:
     - failed migration result → empty report;
     - dry run → `preview_incomplete=incomplete`, with the notice carried in `failure_messages` when incomplete. Stop appending the notice to `result.errors` and stop printing it in the step when incomplete, so it is printed once, by the renderer. A complete preview's notice is still printed by the step as today;
     - prepared path → `drifted_paths` from `consent_required` dispositions (as today), `failed` when any result outcome is not `applied`/`skipped`. Keep extending `result.errors` with error diagnostics. For each non-applied result that has **no** error diagnostic, add to `failure_messages`: `Tool-surface repair for <owner> was not applied (<outcome>); re-run 'spec-kitty upgrade'.` (look at the result object for the owner identifier).
  3. Keep `ctx.surface_repair_summary` populated: the JSON `surface_repair` payload still reads it.
  4. Set `had_migrations` where the two `UpgradeOutcome(...)` instances are constructed (`bool(migrations_needed)`).
  5. Update `tests/upgrade/test_finalizer.py` for the new callable type; its exit-code case that used `surface_drift_failed` becomes two cases (drift, repair failure) and asserts kind as well.
- **Files**: `src/specify_cli/upgrade/finalize.py`, `src/specify_cli/cli/commands/upgrade.py`, `tests/upgrade/test_finalizer.py`.

### Subtask T008 – Presentation reads the outcome

- **Purpose**: FR-003, FR-004, FR-005, FR-017. This is where T004 goes green.
- **Steps** (in `src/specify_cli/cli/commands/upgrade.py`):
  1. Delete `_combined_errors` and `_surface_drift_error`. Both JSON builders use `outcome.status`, `outcome.effective_success`, `outcome.errors()`, `outcome.warnings()` and add `"outcome": outcome.kind.value` and `"failure_reasons": [r.value for r in outcome.reasons]`. Remove their `surface_repair_summary` use for errors; they still take it for the `surface_repair` payload.
  2. Text: one tail renderer for both paths, e.g. `_render_outcome_tail(outcome, *, manual_review_paths, auto_commit_paths, left_uncommitted)`: warnings section, errors section from `outcome.errors()`, manual-review section, blank line, then `outcome.closing_line()` styled by kind (green for applied / no-op, yellow for a completed dry run, red for drift-unresolved and failed), then the auto-commit / left-uncommitted line only on a success kind. `_display_no_migrations_results` is removed; `_display_upgrade_results` keeps only its migrations-only prefix (dry-run panel, applied / skipped sections) and loses its `effective_success=` and `errors=` parameters.
  3. On the no-migrations success path the visible output must stay as it is today (`Project is already up to date!`, then warnings, then the commit line): existing tests pin this (`tests/upgrade/test_upgrade_integration.py` near lines 146 and 167). If the unified renderer would reorder lines for the no-op kind, keep the existing order for that kind and note it.
  4. Keep the single `raise typer.Exit(outcome.exit_code)` exactly where it is.
  5. Keep each function at complexity ≤ 15; extract small helpers rather than nesting.
- **Files**: `src/specify_cli/cli/commands/upgrade.py`.

### Subtask T009 – CLI matrix (FR-011, NFR-001)

- **Purpose**: pin closing line, JSON status, reported kind and exit code together, through the command.
- **Steps**: `tests/upgrade/test_upgrade_outcome_rendering.py`, parametrised: kind ∈ {applied, no_op, drift_unresolved, failed} × path ∈ {migrations, no-migrations} (where the kind exists on that path) × mode ∈ {text, json}, plus: completed dry run (both paths), incomplete dry-run preview (both paths; assert the notice appears exactly once in text and no success line), the run without `--yes`, activation error, worktree stamp failure and `SafeCommitRecoveryFailed` on the no-migrations path. For each row assert exit code, the closing line (text) or `status` / `success` / `outcome` (JSON), that text contains every string in the JSON `errors` of the same state, and that `already up to date` / `Upgrade complete` are absent whenever the exit is non-zero. Drive through `CliRunner` on the real `upgrade` command with the narrowest stubs (prepared repairs, migrations list); do not construct the outcome by hand in this file.
- **Files**: `tests/upgrade/test_upgrade_outcome_rendering.py` (new).

### Subtask T010 – Strengthen the tests that only pinned the exit code (FR-013)

- **Steps**:
  - `tests/specify_cli/tool_surface/test_drift_policy.py` (text-mode case near line 553): also assert the drift message and the absence of a success line.
  - `tests/specify_cli/tool_surface/test_surface_repair_wiring.py` (near line 124): same.
  - `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py` (near lines 80–128): assert the human output's drift line; correct the docstring that records the missing message as a capture limit.
  - `tests/upgrade/test_upgrade_integration.py` (near line 204): replace the comment that accepts "no failure banner" with an assertion on the closing line.
  - Where a test pins `Upgrade failed.` for a drift-only run on the migrations path, re-pin to `Upgrade finished with unresolved tool-surface drift.` and say so in the commit body.
- Do not delete or loosen any existing assertion. After the fix, drop the `regression` marker from the T004 file's tests if they now duplicate matrix rows: keep them as focused tests named for the behaviour (ADR `2026-07-17-1`: a transitional repro is not left marked `regression`).

### Subtask T011 – Help text and its generated mirrors (FR-014)

- **Steps**: the `upgrade` docstring says any `--dry-run` exits 0 (near line 1664). Correct it: a completed preview exits 0; an incomplete preview exits 1. Find how `docs/api/cli-commands.md` and `src/specify_cli/_completion_manifest.json` are generated (search `scripts/` and the Makefile for the generator; do not hand-edit if a generator exists) and regenerate them so they match. If regeneration changes unrelated entries, stop and report instead of committing the noise.
- **Files**: `src/specify_cli/cli/commands/upgrade.py`, `docs/api/cli-commands.md`, `src/specify_cli/_completion_manifest.json`.

## Commit sequence

1. T004 (red). 2. T005 + T006 (model + unit matrix; if removing `surface_drift_failed` would break `upgrade.py` at this commit, land T005–T008 as one commit instead of leaving a broken intermediate). 3. T007 + T008 (finalizer + presentation; T004 green). 4. T009. 5. T010. 6. T011.

Every commit after the first must pass the test command below.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/upgrade/test_upgrade_outcome_regression_4925.py tests/upgrade/test_upgrade_outcome_kind.py \
  tests/upgrade/test_upgrade_outcome_rendering.py tests/upgrade/test_finalizer.py \
  tests/upgrade/test_upgrade_integration.py tests/upgrade/test_upgrade_auto_commit_unit.py \
  tests/upgrade/test_upgrade_char_net.py tests/upgrade/test_worktree_stamp_guard.py \
  tests/upgrade/test_legacy_surface_repair_unreachable.py \
  tests/specify_cli/tool_surface/test_drift_policy.py tests/specify_cli/tool_surface/test_surface_repair_wiring.py \
  tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py tests/compat/test_dry_run_parity.py \
  tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py \
  tests/specify_cli/skills/test_crlf_skill_render_4998.py
ruff check <changed files> && ruff format --check --force-exclude <changed files>
mypy --strict src/specify_cli/upgrade/outcome.py src/specify_cli/upgrade/finalize.py src/specify_cli/cli/commands/upgrade.py
```

Also `grep -rn "surface_drift_failed\|_combined_errors\|_display_no_migrations_results" src tests` must return nothing.

## Risks & Mitigations

- **Hidden consumers of `surface_drift_failed`**: the grep above; fix every call site in the same commit.
- **Double printing**: the dry-run notice and the mission-state repair message each have one printer after this WP; the matrix asserts "exactly once" for the notice.
- **Ordering of `errors`**: `test_drift_policy.py` pins the drift message at `errors[0]` for a drift-only run; the order in T005 keeps that true.
- **Generated docs**: regenerate, do not hand-edit.

## Review Guidance

- Red→green: T004's commit is first and its tests fail on that commit for the stated reason; they pass on the final commit.
- No closing-line literal and no error-list assembly remains in `cli/commands/upgrade.py`.
- The no-op and applied success outputs are byte-identical to before (FR-006, FR-007, NFR-003).
- No JSON key removed or renamed; `outcome` and `failure_reasons` added on both payloads.
- `src/specify_cli/upgrade/runner.py` and `assessment.py` untouched.
- Fakeability check: delete the `errors()` call in the tail renderer and confirm the matrix goes red.

## Amendments from the post-tasks review (binding; these override the text above where they differ)

1. **More files are yours.** `tests/specify_cli/cli/commands/test_upgrade_command.py` (near lines 982–1031) calls `_display_upgrade_results(..., effective_success=, errors=)` and asserts `Upgrade failed.` / `Dry run complete` from it: repoint it at the new tail renderer and keep its assertions. `tests/upgrade/test_worktree_stamp_guard.py` and `tests/upgrade/test_upgrade_char_net.py` mention removed names in docstrings/comments: update the wording. Add all three, plus `tests/upgrade/test_yes_consent_exit_honesty.py` and `tests/regressions/test_issue_4888_safe_commit_index_preservation.py` (both construct an outcome), to the test command.
2. **Commit-recovery failure gets its own reason (same defect class).** `_finalizer_step_commit_churn` sets `outcome.result.success = False` on `SafeCommitRecoveryFailed`, which under the data model would be reported as `migration_failed` on a run with no migrations. Add `UpgradeFailureReason.COMMIT_RECOVERY_FAILED` and an outcome flag `commit_recovery_failed: bool`; the step sets the flag and still appends the rendered error to `result.errors`, and no longer flips `result.success`. Order in `reasons`: after `worktree_failure`. Assert it in the T006 and T009 rows. Check `tests/regressions/test_issue_4888_safe_commit_index_preservation.py` still holds (exit non-zero, message names the stash).
3. **Text format per kind, stated once.** Success kinds keep today's formats exactly: no-op prints the closing line first, then inline `Warning:` lines, then the commit line; applied prints the sectioned lists, then the closing line. Non-success kinds (drift-unresolved, failed) use one format on both paths: warnings, then the `Errors:` section from `outcome.errors()`, manual-review section, blank line, then the closing line last. This resolves the conflict between T008 steps 2 and 3.
4. **Characterise before changing.** In the T004 commit, also add golden-output characterisation tests (full captured text, not a substring) for: no-op with one warning; applied; applied dry run. They pass before and after the change and make "unchanged success output" checkable. They are not marked `regression`.
5. **Docstrings count.** The closing-line fragments also appear in the `_display_upgrade_results` docstring (near lines 1981–1982). Reword it so no closing-line fragment remains anywhere in `cli/commands/upgrade.py`, docstrings and comments in string form included: WP03's gate scans string constants.
6. **Status word comes from the outcome.** Both JSON builders set `"status": outcome.status`; no `"up_to_date" if ... else "failed"` expression remains. `upgrade()` may still append to `result.warnings` before rendering (the commit warning); presentation functions read `outcome.warnings()` / `outcome.errors()` only, never `.result.errors` / `.result.warnings` directly.
7. **T011 generators.** The CLI reference is built by `scripts/docs/build_cli_reference.py` (flags `--output`, `--mode`, `--force`, `--repo-root`); its default runner shells out through `uv run`, which this repo forbids in mission work. Do not run it from the lane. Regenerate the completion manifest with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m specify_cli.completion --regenerate` and commit it. For `docs/api/cli-commands.md`, make the minimal hand edit that mirrors the corrected help sentence, then run `tests/architectural/test_docs_cli_reference_parity.py` and `tests/architectural/test_completion_manifest_freshness.py`; if parity fails, report it in your hand-back so the orchestrator regenerates at the repository root.
8. **Acceptance grep** (`surface_drift_failed|_combined_errors|_display_no_migrations_results` over `src tests`) must return nothing, with the files in item 1 now in your ownership.
9. **Contract numbering.** `contracts/upgrade-outcome-contract.md` rules read 5, 7, 8, 6; rule 6 means "changes no column of the table" and rule 8 adds that the failure is listed in `warnings`. Treat them as consistent: a failed mission-state repair adds a warning and changes nothing else.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:11:03Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
