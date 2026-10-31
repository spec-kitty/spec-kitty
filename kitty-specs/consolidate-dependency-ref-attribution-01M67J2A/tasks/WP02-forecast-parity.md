---
work_package_id: WP02
title: '`--dependency-ref`, run-state persistence and the dry-run forecast'
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-004
- SC-002
planning_base_branch: issue-6771-consolidate-dependency-ref-attribution
merge_target_branch: issue-6771-consolidate-dependency-ref-attribution
branch_strategy: Planning artifacts for this mission were generated on issue-6771-consolidate-dependency-ref-attribution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6771-consolidate-dependency-ref-attribution unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-dependency-ref-attribution-01M67J2A
base_commit: 4b9ac2575bb2f21d2245543bf0eb304d53e0dab7
created_at: '2026-10-31T00:18:58.155740+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Operator surface and forecast parity
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/forecast.py
create_intent:
- tests/consolidation/test_dependency_ref_forecast.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/consolidation/forecast.py
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/state.py
- src/specify_cli/consolidation/phase_claim.py
- src/specify_cli/consolidation/phase_gate.py
- tests/consolidation/test_dependency_ref_forecast.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6771'
---

# Work Package Prompt: WP02 – `--dependency-ref`, run-state persistence and the dry-run forecast

## Goal

The operator declares the dependency ref once, on the command line. The forecast and the real
run then reach the same verdict and the same exit code. `--resume` keeps the declaration.

## Red first (T006)

`tests/consolidation/test_dependency_ref_forecast.py` (fails before the fix):

- `--dry-run` on a mission whose lane merged an undeclared external branch exits **1**, names
  the un-attributable commits, and points at `--dependency-ref`; `--json` carries the same
  `error` text plus an `error_code`.
- The same mission with `--dependency-ref <ref>` on the forecast exits 0.
- A declared ref that does not resolve exits 1 on the forecast as well.

Use the real-CLI harness (`tests/terminus/conftest.py::run_terminus`) for one of these and the
forecast function directly (`run_dry_run_forecast`) for the cheaper cases; keep the suite under
about 60 seconds.

## Implementation (T007–T010)

- `ConsolidateOptions.dependency_refs: list[str] | None` and
  `--dependency-ref` (repeatable) on `consolidate`, help text naming what qualifies (a ref the
  mission branch reaches, with no commit of any mission spine in it).
- `_MergeRunState.dependency_refs: tuple[str, ...] = ()`, populated where the run state is
  built; `ConsolidationState.dependency_refs: list[str]` persisted through the existing
  `to_dict`/`from_dict` seam with the fail-closed `_str_list_or_empty` loader, so a `--resume`
  (and the gate's defensive rebuild) sees the same declaration.
- `phase_claim.build_approved_wp_set(...)` and `phase_gate._reconciliation_claim_for_gate`'s
  rebuild pass `external_dependency_refs=run.dependency_refs`.
- `run_dry_run_forecast(..., dependency_refs=...)`: after the integration-conflict preview and
  before the payload, resolve the status surface, `build_approved_wp_set(...)` with the
  declared refs (a claim refusal is emitted with `_emit_dry_run_error` and `typer.Exit(1)`),
  then run the shared window scan over the refs the landing would introduce (the mission branch
  and the target). Any un-attributable commit → `_emit_dry_run_error` naming up to a handful of
  commits, the count, and the `--dependency-ref` recovery, with a stable `error_code`, and
  `typer.Exit(1)`. A run with nothing to flag prints the payload and exits 0 exactly as today.

## Definition of done

- New tests pass; `tests/consolidation/test_forecast_seam.py`,
  `tests/consolidation/test_consolidate_options.py`, and the terminus dry-run tests stay green;
  `ruff` clean; no change to the payload shape beyond what the change requires.
