---
work_package_id: WP03
title: Canonical-state recovery — lanes rebuilder in doctor mission-state --fix
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-006
- NFR-001
- NFR-002
- NFR-004
- C-002
- C-003
planning_base_branch: fix/canonical-state-recovery
merge_target_branch: fix/canonical-state-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/canonical-state-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/canonical-state-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-canonical-state-recovery-01M2ZE3D
base_commit: d5b8e9ea985b8c9e22fa305705c5c7e6f11e7c2b
created_at: '2026-09-20T13:05:00+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 2 - Recovery
history:
- at: '2026-09-20T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/unit/migration/test_mission_state_lanes_rebuild.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/migration/mission_state.py
- src/specify_cli/cli/commands/_mission_state_doctor.py
- tests/unit/migration/test_mission_state_lanes_rebuild.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4758'
---

# Work Package Prompt: WP03 – Canonical-state recovery (lanes rebuilder)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Add the **one documented recovery action** the wedge needs, homed in `doctor mission-state --fix` (NOT `agent mission repair` — its `shas is None` early return short-circuits the non-coordinated topologies where the wedge lives). When the shared wedge predicate holds (execution began AND `lanes.json` absent), rebuild `lanes.json` from the canonical event log using WP01's pure `compute_and_write_lanes` core.

**Done when:**
- `spec-kitty doctor mission-state --fix --mission <slug>` on a wedged mission rebuilds `lanes.json` from the event log and the mission becomes advanceable (approval/implement no longer refuse) (FR-003, NFR-001, SC-002).
- Rebuild fires **only** when the wedge predicate holds; a mission with `lanes.json` present is untouched (preserve #3311) and a healthy mission repair is a no-op (NFR-004 idempotence).
- Every canonical-state refusal that points here is honest — detect≡cure parity (NFR-002).
- The action reuses WP01's pure core and the shared wedge predicate — no fourth authority (C-002, C-001).

## Context & Constraints

- Grounded sites (verify via Read): `migration/mission_state.py:685` (`repair_repo(..., mission=...)` — already `--mission`-scoped), `:501-532` (`_anchor_repair_root → resolve_canonical_root`, primary-anchored, no coord gate), `:336-356` (`MissionRepairResult` dataclass — add a rebuild action to its report), the existing JSON-shape canonicalization in `repair_repo` (**do not disturb**); `cli/commands/_mission_state_doctor.py` (the `doctor mission-state` front). Import WP01's `lanes/compute_and_persist.py::compute_and_write_lanes` and the wedge predicate.
- Supply `planning_commit_sha` (recorded sha if recoverable, else None) and `mission_id` (from `meta.json`) as resolved inputs to the pure core.
- Do NOT touch `status/models.py`. Do NOT re-run tests broadly in-worktree — narrow file-scoped runs only.
- ATDD red-first (C-003); ruff/mypy clean; complexity ≤15; new branch independently tested (R5 — don't entangle with the existing shape canonicalization).

## Subtasks

### T011 — Red: recovery absent
Add `tests/unit/migration/test_mission_state_lanes_rebuild.py` (`pytest.mark.regression`, pinned #4758): seed a wedged mission (events past `planned`, no `lanes.json`), run `repair_repo(..., mission=slug, fix=True)`, assert `lanes.json` is NOT rebuilt today. RED against the desired rebuild.

### T012 — Add the rebuild action (fail-closed on corrupt input)
In `repair_repo`/`run_mission_state`, when the shared wedge predicate holds, call `compute_and_write_lanes(...)` to rebuild; record the action in `MissionRepairResult` (mirroring the existing meta-actions reporting). Wire the `_mission_state_doctor.py` front to surface it. Never rewrite existing lanes. **A corrupt/partial event log must fail closed with a clear diagnostic — never a partial rebuild that masks corruption** (NFR-003, spec Edge Case). Add a red-then-green test feeding a truncated/corrupt `status.events.jsonl` and asserting the action refuses with a diagnostic rather than writing a partial `lanes.json`.

### T013 — Green e2e + NFRs
Reproduce the #4758 wedge (via WP01/WP02 fixtures), run `doctor mission-state --fix --mission X`, then advance the WP to approval end-to-end (NFR-001). Assert idempotence (rerun on the now-healthy mission = 0 changes, NFR-004). **NFR-002 parity: enumerate every canonical-state condition the doctor/gate DETECTS and assert each has a clearing repair — a table with 0 detect-without-cure rows, not a single weak assertion.**

### T014 — Blast radius
Run `tests/unit/migration/` + `tests/cli/` doctor mission-state (narrow, file-scoped); record counts in `traces/test-evidence.md`.
