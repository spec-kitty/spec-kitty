# Implementation Plan: `upgrade --dry-run` names its migration list for what it is

**Branch**: `issue-6234-upgrade-dry-run-would-apply-heading` | **Date**: 2026-11-01 | **Spec**: `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/spec.md`
**Input**: Mission specification from `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/spec.md`
**Research**: `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/research.md`

## Summary

`spec-kitty upgrade --dry-run` prints the `DRY RUN - No changes were made` panel and then an
unconditional green `Migrations applied:` heading with a green `✓` beside every migration the
run would have applied (#6234). The output says nothing was applied and that something was.

The fix is presentational and lives in one place: `_display_upgrade_results` chooses the
heading and the entry marker from `result.dry_run`. A dry run heads its list
`Migrations that would be applied:` in yellow and marks entries with a yellow `→`; a real run
keeps `Migrations applied:` with `✓`, byte for byte. The dry-run characterisation golden
(`_GOLDEN_APPLIED_DRY_RUN`) and the sequenced-verdict CLI assertion are updated **on
purpose**, with the reason in their docstrings; the real-run golden `_GOLDEN_APPLIED` is the
untouched positive control.

## Technical Context

**Language/Version**: Python 3.11 (`src/specify_cli/cli/commands/upgrade.py` — Rich/typer
rendering)
**Primary Dependencies**: `rich` (`console`, `Panel`) and typer, already imported by the
module; no new dependency, no new import
**Storage**: none — the renderer reads `UpgradeResult` in memory; a dry run still writes
nothing
**Testing**: pytest; the existing golden characterisation module drives the real `upgrade`
typer command in-process over a real git-backed fixture and compares the captured text
verbatim; the sequenced-verdict CLI module drives a `--dry-run` run over two real migrations
**Target Platform**: any platform the CLI supports (POSIX + Windows); no platform-specific code
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: no measurable change; one boolean test added to a renderer that
already branches on `result.dry_run` for the panel
**Constraints**: real-run text unchanged; JSON/`--plan-json` unchanged; selection, ordering,
ledger and exit codes unchanged; no test skipped, xfailed or deleted
**Scale/Scope**: 1 source file (2 small edits), 2 test modules, 1 doc paragraph, 1 changelog
fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Note |
|------|--------|------|
| Single canonical authority | Pass | One conditional in the one renderer; no second place decides the words, no new helper that a caller could bypass |
| ATDD-first / red-first (DIRECTIVE_034) | Pass | The red test asserts the corrected dry-run text through the pre-existing CLI entry point and fails on `origin/main` before the fix (see tasks WP01) |
| `change-apply-smallest-viable-diff`, `DIRECTIVE_024` locality | Pass | Two edits inside the function that already owns the panel; no new module, flag, style or JSON key |
| DIRECTIVE_041 (test only real behaviour/invariants) | Pass | The updated goldens pin operator-visible output; no test is added merely to count |
| Complexity ceiling 15 (`C901`) | Pass | `_display_upgrade_results` gains one `if/else` on an existing parameter; well under the ceiling |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Pass | Targeted `tests/upgrade/test_upgrade_outcome_rendering.py` and `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`, plus the changelog/docs lint scripts |
| Terminology Canon / no legacy terms | Pass | "Migrations that would be applied" reuses the canonical term; no legacy noun introduced |
| SPDD / REASONS canvas | N/A (recorded deviation) | The charter scopes canvases to high-risk and multi-WP missions and excludes tiny fixes; this mission is one heading and two goldens, so no `reasons-canvas.md` is authored. The spec's Requirements/Entities sections carry the same intent. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/
├── spec.md              # mission specification
├── research.md          # Phase 0 output (discovery, decisions D1..D6)
├── plan.md              # this file
├── quickstart.md        # Phase 1 output (how to see the fix)
├── issue-matrix.json    # #6234 row, verdict at close-out
├── traces/              # approach.md, design-decisions.md, tooling-friction.md
├── tasks/               # Phase 2 output (/spec-kitty.tasks)
└── tasks.md             # Phase 2 output
```

No `data-model.md`: the mission introduces no entity or data shape (the "entities" in the
spec are rendering concepts). No `contracts/` directory: no interface, endpoint or payload
changes; `meta.json` records `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/specify_cli/cli/commands/upgrade.py        # _display_upgrade_results heading + marker
                                               # _print_predicted_verdicts docstring wording

tests/upgrade/test_upgrade_outcome_rendering.py        # _GOLDEN_APPLIED_DRY_RUN + docstrings
tests/upgrade/test_dry_run_sequenced_verdict_cli.py    # dry-run heading assertion

docs/guides/how-to/installation/upgrade-project.md     # one sentence: what the preview's list says
docs/changelog/unreleased/6234.fixed.md                # changelog fragment (#6234)
```

**Structure Decision**: single project; the change stays inside the file that already renders
the summary, and its tests in the two modules that already pin that output. Nothing moves.

## Phase 0: Research

Complete — see `research.md`. Decisions D1..D6: the defect still reproduces on
`287a226cfe`; one decision site; only two dry-run assertions exist and one of them is the
positive control that must not change; the wording/marker choice; the skipped heading stays;
no behavioural surface moves.

## Phase 1: Design

### One decision site, two renderings

```python
def _display_upgrade_results(result: UpgradeResult) -> None:
    console.print()

    if result.dry_run:
        console.print(Panel("[yellow]DRY RUN[/yellow] - No changes were made", border_style="yellow"))
        applied_header = "[yellow]Migrations that would be applied:[/yellow]"
        applied_prefix = "  [yellow]→[/yellow] "
    else:
        applied_header = "[green]Migrations applied:[/green]"
        applied_prefix = "  [green]✓[/green] "

    _print_upgrade_section(applied_header, result.migrations_applied, applied_prefix)
    _print_upgrade_section("[dim]Migrations skipped (already applied or not needed):[/dim]", ..., "  [dim]○[/dim] ")
    _print_predicted_verdicts(result)
```

Properties this buys:

- **One source of truth.** The two strings are chosen once, from the same `result.dry_run`
  that already gates the panel. No caller can pass a mismatched heading/marker pair.
- **Empty-safe.** `_print_upgrade_section` returns early on an empty list, so a dry run with
  nothing applicable prints no heading at all (the edge case in the spec) — the heading is
  selected, never force-printed.
- **No raise path.** The block adds no I/O, no exit, no formatting arithmetic; the renderer
  still cannot raise (NFR-002).
- **Marker choice.** `→` is the CLI's existing "consequence" arrow (the auto-commit line) and
  is distinct from the success `✓` and the neutral skip `○`; yellow matches the dry-run
  panel, so the whole block reads as preview.

### The goldens become a deliberate oracle

`_GOLDEN_APPLIED_DRY_RUN` changes in exactly two places:

```
-Migrations applied:
-  ✓ 3.2.0a4_fake_migration
+Migrations that would be applied:
+  → 3.2.0a4_fake_migration
```

`_GOLDEN_APPLIED` (real run) is not edited: it is the control proving the fix is
mode-specific. The module docstring of `test_golden_applied_dry_run` and the
`_GOLDEN_APPLIED_DRY_RUN` comment state that this golden now rules on the wording (with
#6234 cited) rather than merely characterising it, because the old text froze the
contradiction.

`tests/upgrade/test_dry_run_sequenced_verdict_cli.py` asserts
`"Migrations applied:" in result.output` on a `--dry-run` run; it becomes
`"Migrations that would be applied:" in result.output`, plus an explicit negative assertion
that the dry run does not print the real-run heading. Its module docstring follows.

### Docs and changelog

- `docs/guides/how-to/installation/upgrade-project.md`: one sentence after the `--dry-run`
  invocation saying the preview's list is headed `Migrations that would be applied:` with `→`
  markers, and that a real run keeps `Migrations applied:`. No sample output block is
  rewritten (the page carries none).
- `docs/changelog/unreleased/6234.fixed.md`: impact-first lead with `(#6234)`, before/after,
  under 1,200 characters, US spelling. A fragment, not an edit to
  `docs/changelog/CHANGELOG.md` (the repository's stated convention).

### What does not change

Selection (`MigrationRegistry.get_applicable` + ledger), execution order
(`order_manifest.txt`), `detect()`/`apply()` bodies, `--json`/`--plan-json` payloads, the
frozen `compat-planner.json` contract, the closing line and exit codes (ADR
`2026-10-04-3`).

## Complexity Tracking

No charter violations. The one recorded deviation — no REASONS canvas — is explained in the
Charter Check table above.

## Implementation Concern Map

### IC-01 — The mode-dependent migration heading

- **Purpose**: Make the dry-run migration list say what it is, from one decision site, without
  touching the real run or any behavioural surface.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005; NFR-001, NFR-002, NFR-003;
  C-001, C-002, C-005
- **Affected surfaces**: `src/specify_cli/cli/commands/upgrade.py`
  (`_display_upgrade_results`, `_print_predicted_verdicts` docstring)
- **Sequencing/depends-on**: none
- **Risks**: Warm the diff, not the surface — the temptation is to "improve" the skipped
  heading too; the issue and D5 in research.md keep that out of scope.

### IC-02 — The goldens and the operator docs become correct on purpose

- **Purpose**: Re-pin every dry-run assertion to the corrected text, with the reason recorded,
  while leaving the real-run golden untouched as the control; tell operators what the preview
  section is called.
- **Relevant requirements**: FR-004; SC-001, SC-002, SC-003, SC-004; C-003, C-004
- **Affected surfaces**: `tests/upgrade/test_upgrade_outcome_rendering.py`,
  `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`,
  `docs/guides/how-to/installation/upgrade-project.md`,
  `docs/changelog/unreleased/6234.fixed.md`
- **Sequencing/depends-on**: IC-01 (the assertions describe IC-01's output)
- **Risks**: Deleting or xfail-ing an assertion would hide the defect instead of correcting
  it; the tasks forbid it and the review checks the diff for removed assertions.
