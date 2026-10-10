---
work_package_id: WP04
title: Owned finalize-tasks branch contract and single-branch lane preview
dependencies:
- WP03
requirement_refs:
- C-001
- C-003
- FR-004
- FR-005
- FR-008
- NFR-002
- SC-001
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
- T018
phase: Phase 4 - Task finalization
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_finalize.py
create_intent:
- tests/integration/test_owned_pr_bound_finalization.py
- tests/integration/test_single_branch_lane_preview.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize_lanes.py
- src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
- src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py
- tests/integration/test_owned_pr_bound_finalization.py
- tests/integration/test_single_branch_lane_preview.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5880'
- '#5892'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP04 – Owned finalize-tasks (#5880 + #5892)

> Kept together per operator instruction — adjacent regions of the same finalize-tasks file family; disjoint files, no overlap.

## Objectives & Success Criteria

- `#5880`: `finalize-tasks` (and `--validate-only`) for a validated PR-bound owned mission consumes `owned.write_branch` for planning/bookkeeping, preserves the canonical landing target in `meta.json`, and does NOT invoke the legacy protected-target recovery triad — no more `PR_BOUND_PLANNING_BRANCH_REQUIRED` (FR-004).
- `#5892`: `finalize-tasks --validate-only` lane preview computes with the stored `single_branch` topology + mission branch, reporting exactly one `lane-planning` lane matching the real finalization output (FR-005, SC-003).
- Legacy refusal path preserved for non-owned missions (FR-008); `ruff` + `mypy --strict` clean (NFR-002).

## Context & Constraints

- Grounding + provenance: `../research.md` (rows #5880, #5892), `../plan.md` IC-04.
- Repair commits to land-and-verify: `#5880` `codex/5880-owned-task-finalization` fix `4c0f5130c` + test `2be94e6fd`; `#5892` `28a262f00` + test `5f5db01fe`. **Adopt-with-rebase** — anchors are verbatim on main but the base drifted in unrelated regions (write-ledger/`_lock_root_of` refactor), so rebase the small edits onto current files rather than a blind cherry-pick. `mission_finalize_lanes.py` base was identical (clean).
- Root cause (origin/main):
  - `#5880`: `mission_finalize.py::_run_finalize_branch_setup` unconditionally calls `_resolve_target_branch` → `_preflight_recovered_pr_bound_contract` → (write) `_persist_branch_contract_for_finalize`; those legacy helpers re-derive the target from ambient branch state and fold via `get_main_repo_root` (`mission_finalize_branch_contract.py`), ignoring `ctx.owned`. `mission_finalize_planning_pin.py::_preflight_refresh_planning_commit` also runs the legacy refresh even when owned.
  - `#5892`: `mission_finalize_bootstrap.py::_emit_validate_only_report` dry-run `compute_lanes` omits `topology=`/`mission_branch=`, defaulting to `MissionTopology.LANES`.
- Model: `mission_finalize_lanes.py::_compute_and_write_lanes` (real path) already does `topology_from_meta(meta, planning_dir)` + `meta.get("mission_branch")` into `compute_lanes` — the preview must copy this.
- Charter: C-001 single resolver / no `core/paths.py`; C-003 ATDD red-first.

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout.

## Subtasks & Detailed Guidance

### Subtask T014 – ATDD #5880: port the owned PR-bound finalization reproduction (RED first)

- **Steps**: Port `tests/integration/test_owned_pr_bound_finalization.py` (from `2be94e6fd`): `test_finalize_uses_owned_planning_and_preserves_landing` (explicit/validate-only/override) asserting exit 0, `primary`/`sibling`/`main`/`meta.json` byte-unchanged, and `lanes.json` with `mission_branch==PLANNING` and `target_branch=="main"`; `test_invalid_owned_claim_refuses_before_writes`; `test_validated_owned_path_never_calls_legacy_recovery` (monkeypatch `_resolve_target_branch`/`_preflight_recovered_pr_bound_contract`/`_persist_branch_contract_for_finalize` to raise). RED on base.

### Subtask T015 – ATDD #5892: port the single-branch lane-preview reproduction (RED first)

- **Steps**: Port `tests/integration/test_single_branch_lane_preview.py` (from `5f5db01fe`): `test_single_branch_preview_matches_real_finalize` (two disjoint WPs; capture the real-run manifest; assert preview `count==1`, `lane_ids==["lane-planning"]`, and mission_branch/target match meta) and `test_existing_and_unstamped_lanes_keep_preview_parity`. RED on base.

### Subtask T016 – #5880 fix: consume owned write branch, skip legacy recovery

- **Steps**: In `mission_finalize.py`, when `ctx.owned is not None`: take `target_branch = ctx.owned.write_branch`; validate any `--target-branch` override against the declared meta target via `_branch_matches_target(...)`, refusing with `OwnedRefusalCode.OWNED_BRANCH_REFUSED` through `emit_owned_refusal`/`_finalize_refusal_envelope`; SKIP both `_preflight_recovered_pr_bound_contract` and `_persist_branch_contract_for_finalize`; add `OwnedRefusalCode` to the `from mission_runtime import …` line. In `mission_finalize_lanes.py::_compute_and_write_lanes`, pass `_resolve_merge_target_branch(planning_dir, target_branch) if owned else target_branch` to `compute_lanes`. In `mission_finalize_planning_pin.py`, gate the `_refresh_branch_contract_error` check behind `if owned is None:`.
- **Files**: `mission_finalize.py`, `mission_finalize_lanes.py`, `mission_finalize_planning_pin.py`.

### Subtask T017 – #5892 fix: single-branch lane preview parity

- **Steps**: In `mission_finalize_bootstrap.py::_emit_validate_only_report`, import `topology_from_meta`, read `mission_branch` from meta, and pass `topology=topology_from_meta(meta or {}, planning_dir)`, `mission_branch=mission_branch`, `target_branch=_resolve_merge_target_branch(planning_dir, target_branch) if owned else target_branch` into the dry-run `compute_lanes`.
- **Files**: `mission_finalize_bootstrap.py`.

### Subtask T018 – Validate green

- **Steps**: Run both new integration files + the finalize/lanes test modules; format-check + ruff + mypy on changed files. Green.

## Definition of Done

- Both repros RED→GREEN; legacy refusal preserved for non-owned; preview == real-run lanes; `meta.json` landing target preserved; lint/type clean.

## Reviewer Guidance

- Confirm the legacy triad is never invoked when `owned` is present and still runs for non-owned missions; confirm the preview uses stored topology + mission branch.
