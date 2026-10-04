# Implementation Plan: Upgrade reports one outcome

**Branch**: `issue-4925-upgrade-outcome-single-rendering` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-outcome-single-rendering-01M444Q6/spec.md`

## Summary

`UpgradeOutcome` (`src/specify_cli/upgrade/outcome.py`) already decides the exit code once. It does not own the reasons or the closing line, so each renderer in `src/specify_cli/cli/commands/upgrade.py` picks its own subset and the no-migrations text renderer prints a success line on a failing run (GitHub issue 4925).

The plan extends that one object. It gains a typed kind (applied / no-op / drift-unresolved / failed), typed reasons that replace the overloaded `surface_drift_failed` boolean, and the ordered error list. The exit code, the JSON `status` / `success` / `errors` and the text closing line are all read from it. One text renderer replaces the two that exist today for the tail of the run, so the no-migrations path cannot diverge again. An AST gate keeps presentation code from building its own error list or closing line.

## Engineering Alignment

- **Branch contract**: current branch `issue-4925-upgrade-outcome-single-rendering`; planning base and merge target are the same branch (`branch_matches_target: true`); the work is published as a draft pull request from this branch to `main` on the upstream repository, and the operator merges.
- **Invariant**: for every run that reaches the finalizer, `kind`, `exit_code`, JSON `status` and the closing line are functions of the same `UpgradeOutcome`.
- **Unresolved drift exits non-zero** (spec C-002). The operator may still rule otherwise; the kind makes that a one-line mapping change.
- Planning questions were answered by the pre-spec grounding squad; no interview was run, at the operator's instruction.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing; no dependency added, upgraded or removed)
**Storage**: N/A
**Testing**: pytest; `typer.testing.CliRunner` through the real `upgrade` command; one AST gate under `tests/architectural/`; mypy strict; ruff
**Target Platform**: Linux, macOS, Windows (the defect was reported on Windows and macOS and reproduces on Linux)
**Project Type**: single (CLI)
**Performance Goals**: no added subprocess or filesystem work on the upgrade path; the change is pure in-memory derivation
**Constraints**: do not modify `src/specify_cli/upgrade/runner.py` (sibling mission for issue 5457 owns it); `worktree_failures` stays `list[str]`; no JSON key removed or renamed; planner / compatibility exit paths untouched; complexity ≤ 15 per function
**Scale/Scope**: 3 source files (`upgrade/outcome.py`, `upgrade/finalize.py`, `cli/commands/upgrade.py`), the generated CLI reference and completion manifest that mirror the help text, about 8 test files, 1 new gate, 1 ADR, changelog

## Charter Check

| Gate | Verdict |
|------|---------|
| Single canonical authority (DIRECTIVE_044) | Pass. Extends the existing authority; removes the parallel one in the renderers. No second outcome type. |
| Architectural alignment (DIRECTIVE_001) | Pass. Dependency direction `cli.commands -> upgrade` is kept; `outcome.py` gains no import from `cli`. |
| ATDD / red-first (C-011, DIRECTIVE_041) | Planned. The regression repro through the CLI entry point is the first commit of the first functional work package. |
| Architectural gate discipline (DIRECTIVE_043) | Planned. The gate starts with an empty allowlist and carries a self-mutation test. |
| Tidy-first (DIRECTIVE_025) | Planned. The legacy surface-repair branch is settled in a separate, behaviour-preserving step before the functional change. |
| User customization preservation | Pass. No mutating behaviour changes; drifted files are still preserved. The message must not recommend the overwriting option. |
| No full heavy suites in mission work | Pass. Targeted files and the one named gate only. |
| Terminology canon | Pass. No `feature` wording introduced. |

No violations; Complexity Tracking is empty.

## Design

### The outcome (see [data-model.md](data-model.md))

`UpgradeOutcome` gains:

- `had_migrations: bool` — whether the run was on the migrations path.
- `drifted_paths: list[Path]` — managed files left alone because overwriting needs consent.
- `surface_repair_failed: bool` — a repair could not be applied.
- `preview_incomplete: bool` — a dry-run preview could not be completed.
- `warnings()` — `result.warnings` plus the mission-state repair message when `repair.failed` (FR-018; exit code unchanged). The implementer checks the gate does not already print that message, to avoid a double print.
- `reasons` (property) — the ordered tuple of `UpgradeFailureReason` values that hold.
- `kind` (property) — `UpgradeOutcomeKind`.
- `errors()` — the ordered, de-duplicated error list (the logic of today's `_combined_errors`, plus the drift message when `drifted_paths` is non-empty).
- `status` (property) — the JSON status word: `success` (applied), `up_to_date` (no-op), `failed` otherwise. Existing vocabulary, unchanged.
- `closing_line()` — the plain-text closing line for the kind.

`surface_drift_failed` is removed. `effective_success` becomes `not self.reasons`, and `derive_exit_code()` keeps its single-site role.

The finalizer's `run_surface_repair` callable changes its return type from `bool` to a small frozen `SurfaceRepairReport(drifted_paths, failed, preview_incomplete, failure_messages)` defined in `outcome.py`; `finalize_upgrade` copies it onto the outcome. This replaces the boolean that carried three meanings.

### Kind derivation

| Condition | Kind |
|-----------|------|
| any reason other than `SURFACE_DRIFT` | `failed` |
| only `SURFACE_DRIFT` | `drift_unresolved` |
| no reasons, `had_migrations` | `applied` |
| no reasons, not `had_migrations` | `no_op` |

`preview_incomplete` is a failure reason, so an incomplete dry-run preview is `failed` on both paths. A completed dry run keeps its own closing wording (`Dry run complete — no changes applied.`) through `closing_line()`, selected by `result.dry_run`; it is a presentation variant of applied / no-op, not a fifth kind.

### Presentation (see [contracts/upgrade-outcome-contract.md](contracts/upgrade-outcome-contract.md))

- JSON: both payload builders read `outcome.status`, `outcome.effective_success` and `outcome.errors()`. They add two keys, `outcome` (the kind) and `failure_reasons` (list of reason names). Nothing is removed or renamed.
- Text: one function renders the tail for both paths: warnings, the errors section from `outcome.errors()`, manual-review paths, then the closing line from `outcome.closing_line()` styled by kind. `_display_no_migrations_results` and the tail of `_display_upgrade_results` are folded into it. The sections that only the migrations path has (migrations applied / skipped, dry-run panel) stay in a migrations-only prefix that prints no closing line.
- The drift message keeps its current text (`Unresolved tool-surface drift in N file(s); run 'spec-kitty doctor tool-surfaces' to review.`) and is produced only when N ≥ 1. A repair failure is reported by the repair's error diagnostics; for a result that is neither applied nor skipped and carries no error diagnostic, the surface-repair step synthesises `Tool-surface repair for <owner> was not applied (<outcome>); re-run 'spec-kitty upgrade'.` so a non-zero exit always has a printed reason. On an incomplete dry-run preview the step no longer prints the notice itself; it is printed once, from `outcome.errors()`.

### Closing lines

| Kind | Closing line |
|------|--------------|
| applied | `Upgrade complete! <from> -> <to>` (unchanged) |
| no-op | `Project is already up to date!` (unchanged) |
| drift-unresolved | `Upgrade finished with unresolved tool-surface drift.` |
| failed | `Upgrade failed.` (unchanged) |

Drift on the migrations path prints `Upgrade failed.` today. It changes to the drift line: migrations did apply, and the line now says what is actually outstanding. Tests that pin `Upgrade failed.` for the drift-only case are re-pinned as part of FR-013.

### Legacy surface-repair branch (FR-016)

`_run_upgrade_surface_repair` is reached from `_finalizer_step_surface_repair` only when `ctx.prepared_repairs is None` on a real, successful run. `_prepare_finalizer_repairs` either sets `prepared_repairs` or returns errors, and returned errors become `activation_errors`, which skips the surface-repair step. The tidy-first work package confirms this with a test that asserts the branch is not entered on any reachable path, then removes the branch, `_surface_drift_exit_required` and the helper, and repoints the tests that patch it (`tests/compat/test_dry_run_parity.py`, `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py`). `render_surface_summary_lines` stays: `init` uses it. If the reachability check fails, the branch is kept and routed through `SurfaceRepairReport` instead.

### Gate (FR-012)

`tests/architectural/test_upgrade_outcome_single_rendering.py` parses `src/specify_cli/cli/commands/upgrade.py` and asserts:

1. the closing-line literals (`already up to date`, `Upgrade complete`, `Upgrade failed`, `Dry run complete`, `unresolved tool-surface drift`) appear in no string constant of that module — they live in `upgrade/outcome.py` only;
2. no function in the module reads `activation_errors`, `worktree_failures` or `drifted_paths` off an outcome to build an error list, and no renderer or payload builder has an `errors`, `effective_success` or `surface_repair_summary` parameter used for error assembly — only `outcome.errors()` is called;
3. `derive_exit_code` has exactly one caller in `src/`, and its body depends on `kind` only.

Empty allowlist. A self-mutation test feeds the checker a synthetic module containing each violation and asserts it fails; a floor assertion requires the checker to have visited the real renderer functions.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-outcome-single-rendering-01M444Q6/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/upgrade-outcome-contract.md
└── tasks.md            # created by /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── outcome.py           # kind, reasons, SurfaceRepairReport, errors(), status, closing_line()
└── finalize.py          # run_surface_repair returns SurfaceRepairReport

src/specify_cli/cli/commands/
└── upgrade.py           # one tail renderer; JSON builders read the outcome; legacy branch removed

tests/upgrade/
├── test_upgrade_outcome_kind.py          # new: unit matrix on the outcome
├── test_upgrade_outcome_rendering.py     # new: CLI matrix kind × text/JSON × path
├── test_finalizer.py                     # updated for SurfaceRepairReport
└── test_upgrade_integration.py           # strengthened
tests/specify_cli/tool_surface/
├── test_drift_policy.py                  # text-mode message assertions
└── test_surface_repair_wiring.py         # text-mode message assertions
tests/specify_cli/cli/commands/
└── test_upgrade_command_skill_drift.py   # text-mode message assertions; docstring corrected
tests/architectural/
└── test_upgrade_outcome_single_rendering.py   # new gate

docs/adr/4.x/2026-10-04-2-upgrade-reports-one-outcome.md
docs/changelog/CHANGELOG.md
```

**Structure Decision**: single project; the change stays inside the `upgrade` package and its CLI adapter. `src/specify_cli/upgrade/runner.py` is read-only for this mission.

## Implementation Concern Map

### IC-01 — Settle the legacy surface-repair branch

- **Purpose**: remove (or prove live) the second surface-repair path before the functional change, so there is one path to make outcome-driven.
- **Relevant requirements**: FR-016
- **Affected surfaces**: `src/specify_cli/cli/commands/upgrade.py` (`_run_upgrade_surface_repair`, `_surface_drift_exit_required`, the fallback in `_finalizer_step_surface_repair`); `tests/compat/test_dry_run_parity.py`; `tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py`; `tests/specify_cli/skills/test_crlf_skill_render_4998.py` if it patches the helper. The post-spec review confirmed the branch unreachable and the six patches inert (`test_dry_run_parity.py:99`; `test_upgrade_provisions_mission_type_activations.py:240, 269, 298, 330, 373`)
- **Sequencing/depends-on**: none
- **Risks**: `_repair_stale_command_manifest` is called only from the legacy helper; confirm the prepared path covers it before deleting, otherwise keep that call.

### IC-02 — Outcome owns kind, reasons and messages

- **Purpose**: make `UpgradeOutcome` the one source for kind, reasons, error list, status word and closing line; replace the overloaded boolean.
- **Relevant requirements**: FR-001, FR-002, FR-008, FR-009, FR-010, FR-018, NFR-004
- **Affected surfaces**: `src/specify_cli/upgrade/outcome.py`, `src/specify_cli/upgrade/finalize.py`, `tests/upgrade/test_finalizer.py`, new `tests/upgrade/test_upgrade_outcome_kind.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `tests/upgrade/test_finalizer.py` and other tests construct outcomes with `surface_drift_failed=`; every constructor call site must move in the same change.

### IC-03 — Presentation reads the outcome

- **Purpose**: one text tail renderer and both JSON builders derive from the outcome; the red-first regression repro for the reported defect goes green here.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-011, FR-013, FR-014, FR-017, NFR-001, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/cli/commands/upgrade.py` (renderers, JSON builders, `_finalizer_step_surface_repair`, `upgrade` docstring); new `tests/upgrade/test_upgrade_outcome_rendering.py`; the strengthened tests listed above
- **Sequencing/depends-on**: IC-02
- **Risks**: text assertions through `CliRunner` need the module `console` captured; one existing test records that drift lines "do not reach the capture" — verify whether that is a real harness limit before relying on it.

### IC-04 — Gate, decision record and changelog

- **Purpose**: keep the class closed and record the contract.
- **Relevant requirements**: FR-012, FR-015, NFR-005
- **Affected surfaces**: `tests/architectural/test_upgrade_outcome_single_rendering.py`, `docs/adr/4.x/`, `docs/changelog/CHANGELOG.md`, docs retrieval index
- **Sequencing/depends-on**: IC-03
- **Risks**: the changelog is a hot file; expect a union-resolve at rebase.
