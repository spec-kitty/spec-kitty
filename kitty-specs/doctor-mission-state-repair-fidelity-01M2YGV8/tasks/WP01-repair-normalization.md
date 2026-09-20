---
work_package_id: WP01
title: Repair normalization + meta_actions + non-fatal reconciliation
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- FR-001
- FR-002
- FR-003
- FR-004
- FR-010
- FR-011
- FR-013
- NFR-002
planning_base_branch: fix/doctor-mission-state-repair-fidelity
merge_target_branch: fix/doctor-mission-state-repair-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/doctor-mission-state-repair-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctor-mission-state-repair-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-mission-state-repair-fidelity-01M2YGV8
base_commit: 2b735504c708d8871b3bb68bb67875e0efe400d4
created_at: '2026-09-20T05:23:11.458780+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Repair correctness
history:
- at: '2026-09-20T05:01:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/unit/migration/test_change_mode_normalization.py
- tests/integration/migration/test_repair_normalizes_change_mode.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission_metadata.py
- src/specify_cli/migration/mission_state.py
- tests/specify_cli/test_mission_metadata_change_mode.py
- tests/unit/migration/test_change_mode_normalization.py
- tests/integration/migration/test_repair_normalizes_change_mode.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Repair normalization + meta_actions + non-fatal reconciliation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Make `spec-kitty doctor mission-state --fix` **repair** a mission whose `meta.json` carries a non-`bulk_edit` `change_mode` (e.g. `regular`) instead of aborting it, and surface the repair through a new `meta_actions` report field.

Done when:
- A mission with `change_mode: regular` is repaired: field removed, counted `updated`, `normalized_change_mode` recorded, exit 0, **no `ValueError`** (FR-001/002/003, SC-001).
- `VALID_CHANGE_MODES = frozenset({"bulk_edit"})` and the `set_change_mode` **write-guard are unchanged** (FR-004/C-001). Do NOT re-widen the vocabulary or introduce `regular` as a term.
- Any non-canonical/malformed value is normalized the same way (FR-011).
- Re-running `--fix` yields zero changes for the normalized mission (NFR-002/SC-005).
- `--audit` and `--fix` agree the field is repairable (FR-010/SC-004) — achieved because `--fix` is no longer fatal; **do NOT edit `audit/shape_registry.py`** (`change_mode` is a known key; editing adds a finding-code + #2720 drift).

## Context & Constraints

- Root-cause & design: `kitty-specs/doctor-mission-state-repair-fidelity-01M2YGV8/research/durable-fix-investigation.md`, `research/research.md`, `data-model.md`, `plan.md`.
- ADRs (aligned, no amendment): `docs/adr/3.x/2026-05-10-1-deterministic-historical-mission-state-repair.md` (invalid→deterministic default; manifest shows what was defaulted; run-twice = no second diff), `docs/adr/3.x/2026-04-14-1-bulk-edit-occurrence-classification-guardrail.md` (`change_mode: bulk_edit` guard; absence = ordinary).
- Grounded sites: `mission_metadata.py:99` (`VALID_CHANGE_MODES`), `:502-506` (`validate_meta` value-check), `:824-826` (write-guard). `migration/mission_state.py`: `_canonicalize_mission_meta` ~1642-1650 raises `ValueError`; meta-actions from `_canonicalize_meta` (~:1610) are consumed only as a write-gate boolean at ~:1499 and **discarded**; `MissionRepairResult` dataclass ~:336-356 (**no `actions`/`meta_actions` field today**); `_mission_seed` ~:2217 (excludes `change_mode` — mission_id idempotency safe).
- Charter: `__all__` convention (new helpers stay intra-module unless consumed cross-module + hash refresh); no new routed `load_meta` read (normalize reads the in-memory dict via `meta.get`); ATDD red-first; ruff/mypy clean.

## Subtasks

### T001 — Red: repair of `change_mode: regular` exits 0 & drops the field
Add a failing test (`tests/integration/migration/test_repair_normalizes_change_mode.py`, pytestmark required) seeding a mission dir whose `meta.json` has `change_mode: "regular"`; assert `repair_repo` reports it `updated` (not `error`), the persisted `meta.json` no longer contains `change_mode`, exit 0, no `ValueError`. Confirm RED on current tree.

### T002 — `_normalize_change_mode` helper in `mission_metadata.py`
Add a small pure helper that, given a meta dict, drops `change_mode` when its value is not `"bulk_edit"` and returns whether it changed (so callers can record it). Keep `VALID_CHANGE_MODES` and `set_change_mode` untouched.

### T003 — `meta_actions` field on `MissionRepairResult` + `to_dict()`
Add `meta_actions: list[str]` (default empty) to `MissionRepairResult` (`migration/mission_state.py:~336`); include it in `to_dict()`. Unit test in `tests/unit/migration/test_change_mode_normalization.py` that a result serializes the field.

### T004 — Wire canonicalizer + conditional action
In `_canonicalize_mission_meta` (~1642), call the normalize helper **before** `validate_meta`; when it changed the field, append `normalized_change_mode` to the mission's `meta_actions` (mirror the conditional `removed_meta_key:*` pattern — only when the field was present). Ensure the write-gate still fires so normalized meta is persisted.

### T005 — Idempotency (red→green)
Test that a second `repair_repo` run reports `missions_updated == 0` and no `meta_actions` for the already-normalized mission (NFR-002). Corroborate the ADR's "run twice = no second diff".

### T006 — Generalize (FR-011)
Parametrize the normalization test over other non-canonical values (unknown string, non-string/malformed) — all normalized to absent identically.

### T007 — Audit/fix agreement (FR-010) — no registry edit
Add a test asserting that on a legacy `change_mode`, `--audit` does not flag it as fatal-and-final while `--fix` errors — after this WP, `--fix` repairs it, so both agree it is repairable. Explicitly assert the fix path did **not** require and did **not** add a `change_mode` entry to `audit/shape_registry.py` (writer-parity `tests/audit/test_shape_registry_writer_parity.py` stays green).

## Branch Strategy
- Planning base / merge target: `fix/doctor-mission-state-repair-fidelity` (final PR → `main`). Execution worktree allocated per computed lane from `lanes.json`.

## Definition of Done
- T001–T007 green; write-guard tests (`test_mission_metadata_change_mode.py:59,105`) still green; ruff/mypy clean; no `shape_registry.py` change; no new `__all__` export unless cross-module (then refresh dead-symbol hashes).

## Reviewer guidance
- Verify normalization is BEFORE `validate_meta`, not a relaxation of it. Verify action recording is conditional (idempotency). Verify no vocabulary widening and no `regular` term introduced. Verify `shape_registry.py` untouched.
