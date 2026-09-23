---
work_package_id: WP01
title: Relocate the audit trail + reconcile the state contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- FR-009
- FR-011
- NFR-001
- NFR-002
planning_base_branch: fix/mission-state-audit-trail-durability
merge_target_branch: fix/mission-state-audit-trail-durability
branch_strategy: Planning artifacts for this mission were generated on fix/mission-state-audit-trail-durability. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-state-audit-trail-durability unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-state-audit-trail-durability-01M37PWG
base_commit: 5b666d1fac135d9287c82a6fcb676f326ca3a291
created_at: '2026-09-23T20:51:27.319226+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundations
history:
- timestamp: '2026-09-23T18:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/migration/
create_intent: []
execution_mode: code_change
mission_id: 01M37PWGWRFNZY8X2Y7P7KJJGK
owned_files:
- src/specify_cli/migration/mission_state.py
- src/specify_cli/state/contract.py
- tests/migration/test_mission_state_repair.py
- tests/specify_cli/test_state_contract.py
- tests/specify_cli/test_gitignore_contract.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP01
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: run `/ad-hoc-profile-load implementer-ivan` (or `spec-kitty agent profile show implementer-ivan` + `spec-kitty charter context --action implement --json`) and apply its initialization, boundaries, and directives. State which you applied.

# Work Package Prompt: WP01 — Relocate the audit trail + reconcile the state contract

## Objective

Move the `doctor mission-state --fix` audit trail (per-run manifest, duplicate-key manifest, and quarantine tree) out of git-ignored `.kittify/migrations/mission-state` into a **git-tracked** root `.kittify/mission-state-audit/`, and make the canonical state contract — which *derives* `.gitignore` — agree. Fix the `_assert_git_safe` self-block that only becomes live once the path is tracked. Expose the audit paths on the RepairReport so WP03 can render them. **Do not touch any row-canonicality code** (`AUTHORITATIVE_NON_LANE_EVENT_TYPES`, `is_non_lane_event`, `_is_preserved_non_lane_row`).

## Context & Constraints

- Read `../plan.md`, `../data-model.md`, `../contracts/audit-trail-contract.md`, `../research.md`.
- Two guards, do not conflate (brownfield finding): `_anchor_repair_root` (`mission_state.py:~506-526`) is the repo-boundary guard — leave its behavior intact (NFR-003a). `_assert_git_safe` (`mission_state.py:~2611`, `git status --porcelain -- <paths>`) is the dirty-path refusal — it currently receives `MANIFEST_ROOT` in its checked set at `:716` and `:908`; once the root is tracked, its own prior uncommitted output would make a second `--fix` refuse. Drop `MANIFEST_ROOT`/audit-root from that checked set (NFR-003b, FR-009).
- `.gitignore` is **generated** from `state/contract.py` via `get_runtime_gitignore_entries()`; do NOT hand-edit `.gitignore`. Change the `migration_state_ledger` StateSurface instead. Keep the separate legacy `.kittify/migrations/` entry in place (that is WP04's back-compat check; do not remove it here).

## Subtasks

### T001 — Audit-root constant
Add `MISSION_STATE_AUDIT_ROOT = Path(".kittify/mission-state-audit")` near `MANIFEST_ROOT` (`mission_state.py:77`). Keep `MANIFEST_ROOT` defined only if still referenced by legacy-read paths; otherwise remove it once all writers move.

### T002 — Repoint the three write sites
- Mission-state manifest: `manifest_rel = manifest_path or MISSION_STATE_AUDIT_ROOT / f"{run_id}.json"` (`:713`), write at `:752`.
- Duplicate-key manifest: `:904` (`MISSION_STATE_AUDIT_ROOT / f"{_DUP_KEY_MANIFEST_PREFIX}{run_id}.json"`), write at `:913`. Note this write is conditional (`if file_changes:`) — leave it conditional (contract M-1 applies to the mission-state manifest only).
- Quarantine tree: `quarantine_path = repo_root / MISSION_STATE_AUDIT_ROOT / "quarantine" / run_id / _safe_mission_slug / EVENTS_FILENAME` (`:1712`), write at `:1715`. Conditional on `quarantine_lines`.

### T003 — Drop the audit root from `_assert_git_safe` checked set
At `:716` (`relevant_paths.append(str(MANIFEST_ROOT))`) and `:908` (`[*rel_paths, str(MANIFEST_ROOT)]`), remove the audit-root append so the repair's own output does not trip its dirty-path refusal. Keep the mission-dir paths in the checked set.

### T004 — Repoint `_POLICY_TRACKED`
`mission_state.py:85-89`: change `.kittify/migrations/mission-state/*.json` → `.kittify/mission-state-audit/*.json`.

### T005 — State contract surface + RepairReport fields
- `state/contract.py` `migration_state_ledger` (`:271-287`): `path_pattern=".kittify/mission-state-audit/<run_id>.json"`, `git_class=GitClass.TRACKED` (or `INSIDE_REPO_NOT_IGNORED` if that is the idiom for "tracked, tolerated dirty" — check the enum + `state/doctor.py` handling), and rewrite the notes: the trail is now tracked-and-durable; the accept/merge non-gating is preserved by self-bookkeeping-churn classification (WP02), not by ignoring. Reference #4928 + #2384.
- Add `audit_manifest_path` and `audit_quarantine_path` (nullable) + confirm `quarantined_rows` exists on the `RepairReport`/mission report dataclass so WP03 can render them. (Rendering itself is WP03.)

### T006 — Red-first tests (write failing first)
In `tests/migration/test_mission_state_repair.py`: relocation writes under `.kittify/mission-state-audit/`; `git check-ignore` reports the new manifest/quarantine as NOT ignored; **two consecutive `--fix` runs succeed without `--allow-dirty`** (the self-block regression guard). In `tests/specify_cli/test_state_contract.py` + `test_gitignore_contract.py`: update assertions for the moved surface; confirm `get_runtime_gitignore_entries()` no longer emits the audit root as ignored while the legacy `.kittify/migrations/` entry remains.

## Definition of Done
- All three writers land under `.kittify/mission-state-audit/`; `git check-ignore` clean.
- Two consecutive `--fix` runs succeed without `--allow-dirty`.
- `state/contract.py` surface + derived gitignore + `_POLICY_TRACKED` coherent; legacy ignore untouched.
- `RepairReport` carries the audit paths + count.
- `ruff`/`mypy` clean; the #4897 canonicality suite still green (run `tests/status/test_authoritative_non_lane_registry_4897.py`).

## Reviewer guidance
Verify NO edit to canonicality code. Verify `_anchor_repair_root` behavior unchanged and `_assert_git_safe` no longer receives the audit root. Verify `.gitignore` was not hand-edited (only the contract).
