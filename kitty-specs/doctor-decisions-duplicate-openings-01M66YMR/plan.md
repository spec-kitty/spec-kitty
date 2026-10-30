# Implementation Plan: doctor decisions reports tolerated duplicate openings

**Branch**: `issue-6764-doctor-decisions-duplicate-openings` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/doctor-decisions-duplicate-openings-01M66YMR/spec.md`

## Summary

`doctor decisions` (read-only diagnose) must report, as an informational finding, every
decision whose event log holds several `DecisionPointOpened` rows that the canonical fold
already accepts (#4848). The finding is a `duplicate_openings_tolerated: list[str]` field
on `DecisionsReconciliationReport`, printed as a human line and emitted as one additive
`--json` key. It never changes `clean`, the exit code, or `--repair` behaviour, and it is
computed from the same per-decision event groups the diagnose path already reads, using
one exported helper beside the fold so the report cannot drift from what the fold accepts.

## Technical Context

**Language/Version**: Python 3.11 (repo standard; `uv`-managed)
**Primary Dependencies**: Typer (CLI), pydantic (models), `spec_kitty_events.decisionpoint`
(event contract). No new dependency.
**Storage**: Files only — `kitty-specs/<mission>/status.events.jsonl` (event log, COORD
partition) and `decisions/index.json` (ledger, PRIMARY partition). Both read-only here.
**Testing**: pytest. Red-first: a failing test through the real `doctor decisions --json`
CLI (`typer.testing.CliRunner`, the pattern already used in
`tests/decisions/test_decisions_reconciler.py`).
**Target Platform**: CLI (Linux/macOS/Windows shell).
**Project Type**: Single project (`src/specify_cli/`, `tests/`).
**Performance Goals**: no measurable change — the finding rides the existing per-decision
loop; `status.events.jsonl` is read once (NFR-001).
**Constraints**: read-only diagnose; additive JSON keys only; no behaviour change to
`--repair` (C-001, C-002, NFR-002).
**Scale/Scope**: one report field, one fold helper, one human emit, one JSON key, one doc
section, three to five tests. Roughly 60 lines of production change.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict | Evidence |
| --- | --- | --- |
| Single canonical authority | PASS | The duplicate predicate lives once, in `index_fold`, beside the fold that applies it (spec FR-005). No second reducer. |
| Architectural alignment | PASS | No new module, no new boundary; the doctor already imports `index_fold` (`_index_fold.fold_events`). |
| ATDD-first (C-011) | PASS | Red-first test drives the real `doctor decisions --json` CLI before the fix exists; every FR has an acceptance scenario. |
| Smallest viable diff / locality (DIRECTIVE_024, `change-apply-smallest-viable-diff`) | PASS | Five touched files, all on the existing call path. |
| Terminology adherence | PASS | "informational finding", "decision", "opening" are the terms the issue and #4919 already use; the JSON key reproduces the issue's own proposal. |
| No full heavy suites in mission | PASS | Only the decisions test modules and the docs-freshness check locally; CI owns the heavy gates. |
| Pre-existing failure reporting | PASS | No new red expected; any unattributable red gets an issue and a `## Deferred` line. |
| Model routing | PASS | Implementation on the cheaper tier, review on the stronger tier (single-agent batch: I implement, then run an independent review pass). |

No violations — Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctor-decisions-duplicate-openings-01M66YMR/
├── plan.md              # This file
├── research.md          # Phase 0 output (D-1..D-6)
├── spec.md              # Mission specification
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── tasks/               # Work-package files
```

No `data-model.md`, `quickstart.md` or `contracts/` for this mission: the change adds no
ordinary entity, no new user entry point and no new interface contract. The one contract
it touches — the `doctor decisions --json` document — is documented in
`docs/api/cli-commands.md`, which is the existing contract home and is updated there
(C-002). Recording that decision here rather than minting empty artifacts.

### Source Code (repository root)

```
src/specify_cli/
├── decisions/
│   └── index_fold.py                    # + tolerated-duplicate helper (beside the fold)
└── cli/commands/
    └── _decisions_doctor.py             # + report field, collector call, human emit, JSON key

tests/decisions/
└── test_decisions_reconciler.py         # red-first tests beside the #4848 test

docs/
├── api/cli-commands.md                  # `doctor decisions` section: document the finding
└── changelog/CHANGELOG.md               # [Unreleased] entry (#6764)
```

**Structure Decision**: Single project, following the existing `decisions/` +
`cli/commands/` split. The predicate goes in `decisions/index_fold.py` (the fold's home);
the reporting goes in `cli/commands/_decisions_doctor.py` (the doctor's home). That keeps
the read rule and its single consumer in their existing homes rather than creating a new
module for ~15 lines.

## Design decisions

### D1 — One helper, exported from `index_fold`

```python
def tolerated_duplicate_openings(events: Iterable[Mapping[str, Any]]) -> int:
    """How many DecisionPointOpened rows *events* holds beyond the one folded."""
```

It reuses `_opened_identity()` and `_OPENED_VOLATILE_FIELD`, so the definition of "equal"
is literally the one `_select_opened_event` uses. Returns `0` when the group holds zero or
one opening. It does NOT raise `FoldError` for differing payloads — that is the fold's job,
and the doctor calls it only after `fold_events` succeeded for that decision, so a
differing duplicate is already reported as a malformed fold and never reaches the
informational list (FR-005 / SC-003).

### D2 — Collect in `_fold_diagnostics`, the loop that already runs

`_fold_diagnostics` becomes `_fold_diagnostics(...) -> tuple[list[str], list[dict], list[str]]`
returning `(malformed_ids, status_mismatch, duplicate_ids)`. It appends a decision id when
`fold_events` succeeded AND `tolerated_duplicate_openings(events) > 0`, so a decision is
never both malformed and "tolerated". `_diagnose` threads the third value into the report.
No second read of the log, no second fold pass (NFR-001).

### D3 — Report field that does not gate

`DecisionsReconciliationReport.duplicate_openings_tolerated: list[str] = field(default_factory=list)`.
`clean` is untouched (it is computed from `missing_from_index`, `orphaned_in_index`,
`malformed_folds`, `status_mismatch`, `findings`), so `clean: true` survives a duplicate
log (FR-003). The diagnose path's `raise typer.Exit(0)` is untouched.

### D4 — Human emit and JSON key

- `_emit_duplicate_openings_notice(report)` prints one line, `cyan` ("informational", not
  red), naming the count and the decision ids, and stating that the rows are tolerated and
  the log is left as-is. Called from `_emit_human` AFTER the clean/diverged branch so it
  prints in both cases, next to the existing `_emit_malformed_fold_warning` /
  `_emit_status_mismatch_warning` calls.
- `_emit_json` adds `"duplicate_openings_tolerated": report.duplicate_openings_tolerated`,
  always present (empty list when none) — the #4919 shape (C-002).
- `--repair` re-runs `_diagnose` after the rebuild (existing code), so the post-repair
  report already carries the finding; no repair-path change (FR-006, C-001).

### D5 — Docs

- `docs/api/cli-commands.md`, `## spec-kitty doctor decisions`: add the informational
  finding to the reported-fields description and to the `--json` key list if present.
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: bold impact-first lead with `(#6764)`,
  before/after, what to do.

## Risks

| Risk | Mitigation |
| --- | --- |
| The new key is mistaken for a failure by a script parsing `--json` | It is additive and `clean`/exit code do not change; the human line is explicitly labelled "informational". |
| A future edit loosens the duplicate rule in the fold and the report follows it silently | The report calls the exported helper, so it can only move with the fold — the test that pins differing duplicates to `malformed_folds` (FR-005) fails if the two diverge. |
| Report field creeping into `clean` | Explicit assertion in the red-first test that `clean` is `True` on a duplicate log, plus a comment on the field. |
| Docs freshness red from editing `docs/api/cli-commands.md` | Run `check_docs_freshness --ci` locally before pushing. |

## Implementation Concern Map

### IC-01 — The duplicate predicate (single authority)

- **Purpose**: Make "these openings are the tolerated kind" answerable from outside
  `index_fold` without duplicating its equality rule.
- **Relevant requirements**: FR-005, NFR-001, C-003
- **Affected surfaces**: `src/specify_cli/decisions/index_fold.py` (`__all__`,
  `tolerated_duplicate_openings`)
- **Sequencing/depends-on**: none
- **Risks**: must not raise on differing payloads (the fold owns that refusal); must not
  change `_select_opened_event` behaviour.

### IC-02 — Reporting surfaces (human + JSON, non-gating)

- **Purpose**: Surface IC-01's answer on the diagnose report without changing the verdict,
  the exit code, or `--repair`.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/cli/commands/_decisions_doctor.py`
  (`DecisionsReconciliationReport`, `_fold_diagnostics`, `_diagnose`, `_emit_duplicate_openings_notice`,
  `_emit_human`, `_emit_json`)
- **Sequencing/depends-on**: IC-01
- **Risks**: the field must stay out of `clean`; the human line must not be red.

### IC-03 — Tests and docs

- **Purpose**: Prove the behaviour red-first through the real CLI, pin the non-gating
  properties, and document the finding for operators.
- **Relevant requirements**: SC-001..SC-005, FR-001..FR-006
- **Affected surfaces**: `tests/decisions/test_decisions_reconciler.py`,
  `docs/api/cli-commands.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: none material; keep the new tests in the module that already owns the
  `doctor decisions` contract rather than a new `test_issue_6764*` file (DIRECTIVE_041).
