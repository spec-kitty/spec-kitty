---
work_package_id: WP02
title: Reporting fidelity + dry-run parity
dependencies:
- WP01
requirement_refs:
- C-006
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-003
- NFR-004
planning_base_branch: fix/doctor-mission-state-repair-fidelity
merge_target_branch: fix/doctor-mission-state-repair-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/doctor-mission-state-repair-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctor-mission-state-repair-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-mission-state-repair-fidelity-01M2YGV8
base_commit: 06f941ae1ba8bdd59bd673f2411fdcaf1298edae
created_at: '2026-09-20T05:58:02.629113+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Output fidelity
history:
- at: '2026-09-20T05:01:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_mission_state_doctor.py
- tests/cli/commands/test_doctor_mission_state.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Reporting fidelity + dry-run parity

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Make `doctor mission-state --fix` and `--teamspace-dry-run` **honestly report** per-mission outcomes in terminal AND `--json`, so triage needs no gitignored file.

Done when:
- `--fix` terminal names each errored/normalized mission + reason/actions, in addition to the summary counts (FR-005).
- `--fix --json` carries a per-mission record incl. `meta_actions` (FR-006).
- `--teamspace-dry-run` terminal names each affected mission + reason (FR-007); `--json` emits structured `errors[]` shape-equivalent to the repair report (FR-008, parity).
- Complete triage detail is obtainable from one invocation's terminal/`--json` — no gitignored read (FR-009/NFR-003, SC-002/003).
- **Additive only**: no second tree scan (NFR-004); `valid`/`fatal_errors`/`Exit(1)` refusal semantics in `teamspace_dry_run` are UNTOUCHED (C-006, dry-run must still refuse audit-blocking shapes per ADR 2026-05-10-1).

## Context & Constraints

- Depends on WP01's `meta_actions` field. Grounded sites: `cli/commands/_mission_state_doctor.py:290` `_pretty_repair` (count-only), `:333` `_pretty_dry_run` (count-only, `len(report.errors)`), `:351` `if not dry_run_report.valid: raise typer.Exit(1)` (refusal — DO NOT weaken). The per-mission data already exists in `report.missions` / `report.errors`.
- Route output through the canonical console seam (ADR `2026-07-14-1-canonical-cli-console-seam`).
- `__all__` in `_mission_state_doctor.py:36-38` is `["run_mission_state"]` only — new render helpers stay intra-module, NOT added to `__all__` (dead-symbol gate).

## Subtasks

### T008 — Red: `--fix` terminal shows per-mission detail
Failing test: a repair report with an errored mission AND a normalized mission (`meta_actions=["normalized_change_mode"]`) renders each mission's slug + reason/actions in terminal, not just counts.

### T009 — Rewrite `_pretty_repair`
Iterate `report.missions`; for each errored mission print slug + `validation_errors`; for each with non-empty `meta_actions` print slug + actions. Keep the existing summary line + manifest sidecar line.

### T010 — Red: `--teamspace-dry-run` terminal per-mission detail
Failing test: a dry-run report with `errors=[{mission_slug, artifact_path, line, error, message}, ...]` renders each per-mission line, not only the count header.

### T011 — Rewrite `_pretty_dry_run` (additive)
Render each `report.errors` entry (slug/artifact/line/message). Do NOT touch `valid`/`fatal_errors` computation or the `Exit(1)` refusal at `:351`. The header wording may change (e.g. "N validation issues") but stays gated behind `valid=False`→exit 1.

### T012 — JSON parity + no-gitignored-read assertion
Assert `--fix --json` and `--teamspace-dry-run --json` both carry per-mission records; assert the reasons are obtainable from stdout/json without reading `.kittify/migrations/` (NFR-003).

### T013 — Enrich MagicMock characterization builders
Update `_build_repair_report` (`test_doctor_mission_state.py:~247`) and `_build_dry_run_report` (`:~398`) so mocks carry realistic `mission_slug`/`validation_errors`/`meta_actions`/error dicts; ensure `test_fix_mode_pretty_output_shows_summary` (:301) and `test_teamspace_dry_run_exits_1_on_validation_failure` (:465) now assert the per-mission rendering (not just the summary line) and the exit code stays 1.

## Branch Strategy
- Planning base / merge target: `fix/doctor-mission-state-repair-fidelity` (final PR → `main`). Depends on WP01; execution worktree per lane from `lanes.json`.

## Definition of Done
- T008–T013 green; refusal/exit semantics unchanged; no `__all__` additions; ruff/mypy clean; NFR-004 (no extra scan) upheld.

## Reviewer guidance
- Confirm additive-only: `git diff` shows no change to `valid`/`fatal_errors`/`Exit(1)`. Confirm no blocking→warning downgrade. Confirm reasons render for BOTH fix and dry-run in terminal and json.
