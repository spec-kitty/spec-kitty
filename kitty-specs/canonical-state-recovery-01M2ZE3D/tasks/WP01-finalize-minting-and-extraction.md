---
work_package_id: WP01
title: '#4758 finalize minting + pure-core extraction + wedge predicate'
dependencies: []
requirement_refs:
- FR-001
- NFR-004
- C-001
- C-003
planning_base_branch: fix/canonical-state-recovery
merge_target_branch: fix/canonical-state-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/canonical-state-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/canonical-state-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-canonical-state-recovery-01M2ZE3D
base_commit: d5b8e9ea985b8c9e22fa305705c5c7e6f11e7c2b
created_at: '2026-09-20T13:05:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-09-20T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/compute_and_persist.py
- tests/cli/test_tasks_finalize_lanes_minting.py
- tests/status/test_compute_and_persist_core.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/lanes/compute_and_persist.py
- src/specify_cli/lanes/persistence.py
- tests/cli/test_tasks_finalize_lanes_minting.py
- tests/status/test_compute_and_persist_core.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4758'
---

# Work Package Prompt: WP01 – #4758 finalize minting + pure-core extraction + wedge predicate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Close #4758's *minting* root: the legacy `agent tasks finalize-tasks` must never leave a mission with `genesis→planned` events seeded but no `lanes.json`. Extract the pure lane-compute core so the WP03 recovery action can reuse it without a layer inversion, and introduce the narrow "wedge predicate" shared by the finalize refusal and WP03's detector.

**Done when:**
- `agent tasks finalize-tasks` either writes `lanes.json` alongside the event-log bootstrap, or refuses to half-finalize and names the canonical `agent mission finalize-tasks` — it never seeds events without lanes (FR-001, SC-001).
- A pure `compute_and_write_lanes(...)` lives in `src/specify_cli/lanes/compute_and_persist.py`, takes `planning_commit_sha` and `mission_id` as **already-resolved** inputs, and imports **no** `typer`/console/JSON/`policy` (layer purity, C-001). `mission_finalize._compute_and_write_lanes` becomes a thin CLI wrapper (resolve sha via the still-local `_preserve_or_capture_planning_commit_sha`, call the core, then `_report_planning_sha_decision`/`_report_parallelization_risk`). Finalize behavior is byte-identical for the healthy path.
- One named wedge predicate `(_execution_has_begun AND lanes.json absent)` is the single definition used by the finalize refusal (`mission_finalize.py:2210-2230`) and (imported by) WP03; the finalize refusal and `MissingLanesError` (`persistence.py:115`) messages name the repair command `spec-kitty doctor mission-state --fix --mission <slug>` (FR-006 for these two sites).
- Rebuild is deterministic: same event log → byte-identical `lanes.json` (NFR-004).

## Context & Constraints

- Grounded sites (verify via Read; grep may mangle identifiers here): `tasks_finalize.py:271` (`bootstrap_canonical_state`, no lanes write); `mission_finalize.py:2302-2383` (`_compute_and_write_lanes` current body), `:2829` (only production caller), `:2169` (`_preserve_or_capture_planning_commit_sha` — STAYS local), `:2039` (`_execution_has_begun`), `:2210-2230` (refusal); `lanes/compute.py` (pure — the layer bar to keep), `lanes/persistence.py:111` (`require_lanes_json`), `:83-119` (`write_lanes_json`); `ownership/validation.py:384` (`validate_glob_matches`).
- Do **NOT** touch `status/models.py` or the upstream `spec_kitty_events.diary` fold.
- Preserve #3311's guard: recovery/refinalize must never rewrite existing lanes — this WP only fixes the *absent* case.
- ATDD red-first (C-003); ruff + mypy clean, zero new suppressions; complexity ≤15; new helpers stay out of `__all__` unless consumed cross-module.

## Subtasks

### T001 — Red: minting bug
Add `tests/cli/test_tasks_finalize_lanes_minting.py` (`pytestmark = pytest.mark.regression`, pinned #4758): seed a fresh mission, run the `agent tasks finalize-tasks` entry point, assert `lanes.json` is absent (the bug). Confirm RED intent by asserting the *desired* post-state (lanes present or an honest refusal). RED on current tree.

### T002 — Extract the pure core
Create `lanes/compute_and_persist.py::compute_and_write_lanes(...)` per the architect boundary (glob re-validation + `compute_lanes` + `write_lanes_json`; inputs already resolved; no console/JSON/policy). Refit `mission_finalize._compute_and_write_lanes` as the CLI wrapper calling it. Unit-test the core in `tests/status/test_compute_and_persist_core.py` (determinism NFR-004).

### T003 — Legacy finalize co-locates lanes
Make `agent tasks finalize-tasks` (`tasks_finalize.py`) write `lanes.json` via the pure core after the event-log bootstrap (or refuse-and-delegate if any consumer depends on events-only — check `tests/cli/`). Turns T001 green.

### T004 — Wedge predicate + honest messages
Add the single named wedge predicate; route the finalize refusal through it; make the refusal and `MissingLanesError` messages name `doctor mission-state --fix --mission <slug>`.

### T005 — Green + core unit tests
T001 passes; add idempotence/determinism unit tests for the core.

### T006 — Blast radius
Run `tests/cli/` finalize coverage + `tests/status/` lane-compute (narrow, file-scoped). Record commands + passed/failed counts in `traces/test-evidence.md`.
