---
type: reference
updated: 2026-10-04
---

# Contract: consolidate surfaces after the decomposition

## Unchanged external surfaces (C-001, C-006)

| Surface | Contract |
|---|---|
| `spec-kitty consolidate` CLI | Same 19 options (names, flags, help text, defaults); `--help` output byte-identical. |
| Refusal text, exit codes | Unchanged; moved function bodies are byte-identical (four gained annotated locals for mypy only). |
| `ConsolidationState` / `state.json`, `meta.json`, `lanes.json`, status events | Unchanged shapes and write sites. |
| Log records | Same logger objects; the moved mission_number cluster keeps the logger name `specify_cli.consolidation.ordering`. |
| `specify_cli.consolidation` package exports | Same names (`assign_next_mission_number` now sourced from `mission_number.bake`). |
| `specify_cli.consolidation.mission_number` | Still a standard-library-only module exposing `is_assigned_mission_number`. |

## New in-process API (#3457)

`specify_cli.cli.commands.consolidate`:

- `ConsolidateOptions` — frozen dataclass, one field per CLI option, each defaulting to the CLI default (never a `typer.OptionInfo`). Field names and order equal the Typer command's parameters (pinned by `tests/consolidation/test_consolidate_options.py`).
- `run_consolidate(options: ConsolidateOptions) -> None` — the command body. Does not apply `require_main_repo` (same as the former `consolidate.__wrapped__` direct-call path).
- `consolidate(...)` — the Typer command; builds `ConsolidateOptions` from its parsed options and calls `run_consolidate`.

Neither name is in `__all__` (dead-symbol gate: referenced intra-module).

## Internal module boundaries (#2026, #2600)

`consolidation/executor.py` owns orchestration only (entry and lock, locked driver with the single rollback door, `_report_rollback`, attestation recording). Phase helpers live in `run_state`, `coord_strand`, `phase_claim`, `phase_advance`, `phase_bookkeeping`, `phase_gate`, `phase_teardown`, `phase_finalize`, `entry_preflight`, `resume_recovery`; the mission_number bake cluster lives in `mission_number/bake.py`. These are private module paths, not a public API.
