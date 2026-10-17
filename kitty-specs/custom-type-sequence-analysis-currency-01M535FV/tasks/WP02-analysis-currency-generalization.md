---
work_package_id: WP02
title: Analysis-currency gate generalized to any analyze-declaring family
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-003
- C-002
- C-003
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 2 - Runtime currency gate
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_query.py
- tests/runtime/test_analyze_step.py
- tests/runtime/_next_mission_scaffold.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Analysis-currency gate generalized to any analyze-declaring family

## Problem

The stale-analysis → re-`analyze` currency gate is hard-keyed to the literal `software-dev`
family at three runtime sites, so an `analyze`-declaring custom type never gets it:

- `src/runtime/next/runtime_bridge_io.py:1543` — `if mission_family == MISSION_TYPE_SOFTWARE_DEV and step_id == ANALYZE_STEP_ID:` (computes `ANALYSIS_CURRENCY_FACT`).
- `src/runtime/next/runtime_bridge.py:652` — `if board.action == _mapping._STEP_IMPLEMENT and ctx.mission_type == MISSION_TYPE_SOFTWARE_DEV:` (reissues `analyze` on the finalized-board override; decide path).
- `src/runtime/next/runtime_bridge_query.py:144` — same, preview/query path.

## Goal

Generalize all three to key on **the mission's resolved runtime DAG declaring an `analyze` step**.

## Constraints (binding)

- **Key on the DAG step SET, never `action_sequence` membership.** Built-in software-dev's
  `action_sequence` is `specify, plan, tasks, implement, review` — it has NO `analyze` — yet
  software-dev HAS an `analyze` DAG step. Keying on `action_sequence` would silently drop the gate
  for the one family that has it today (an NFR-001 regression). The injected probe
  `analysis_currency_for` (`src/specify_cli/cli/commands/next_cmd.py:97-141`) is already
  family-agnostic and injected unconditionally — do not change the injection wiring.
- **Byte-identical for software-dev / research / documentation / plan.** Verified: only software-dev
  declares an `analyze` step among built-ins. Keep `tests/runtime/test_runtime_seam.py` and
  `test_next_board_authority.py` green with 0 diffs.

## Subtasks

- **T004** — Add `mission_declares_analyze_step(run_dir) -> bool` in `runtime_bridge_cores.py`:
  `ANALYZE_STEP_ID in {s.id for s in <frozen template>.steps}`, loading the frozen template via the
  existing loader (`runtime_bridge_engine._load_frozen_template` / `load_mission_template_file` over
  `run_dir / "mission_template_frozen.yaml"`). `ANALYZE_STEP_ID` is `runtime_bridge_cores.py:106`.
- **T005** — `runtime_bridge_io.py:1543`: drop the family clause → `if step_id == ANALYZE_STEP_ID:`
  (the step is only ever issued when the resolved runtime declares it, so this already encodes the key).
- **T006** — `runtime_bridge.py:652` (decide path): replace `ctx.mission_type == MISSION_TYPE_SOFTWARE_DEV`
  with `mission_declares_analyze_step(ctx.run_dir)` (`ctx.run_dir` is on `DecideNextContext`; the override
  is already gated on `_run_is_untouched(ctx.run_dir)` so the template is frozen).
- **T007** — `runtime_bridge_query.py:144` (preview path): same predicate; thread `run_ref.run_dir`
  into `_build_finalized_override_query_decision` from its caller `_query_dispatch_decision`.
- **T008 [P]** — Add an analyze-declaring non-software-dev custom scaffold in
  `tests/runtime/_next_mission_scaffold.py`; red-first tests in `tests/runtime/test_analyze_step.py`:
  (a) currency fact populated at `analyze` for the custom family + software-dev unchanged + a
  no-analyze family (`research`) absent (FR-003/FR-005); (b) decide-path reissue of `analyze` on a
  stale `analysis-report.md` + a fresh-analysis control that proceeds to implement (FR-004/FR-005);
  (c) preview-path `preview_step == "analyze"` on a stale report + no-analyze control (FR-004).

## Test economy (DIRECTIVE_041 / development-assist-test-cleanup)

One focused test per site, each paired with its no-op/no-analyze control for non-vacuity. Do not
duplicate `test_runtime_seam.py`'s golden-parity assertions; strengthen the existing analyze-step
tests in place where the new family fits rather than cloning whole test bodies. A red-first
demonstration that is not worth keeping goes in the implementer report, not the commit. Provide a
table: test → fold → regression caught → existing coverage.

## Definition of done

- An analyze-declaring custom family refuses `implement` and re-issues `analyze` on a stale/missing
  report, decide and preview alike; software-dev/research/documentation/plan byte-identical.
- `ruff`/`mypy` clean, complexity ≤ 15; NFR-001 golden-parity suites green.
