---
work_package_id: WP03
title: Decision-ledger resolves meta.json via PRIMARY, ending the husk split-brain (#4966)
dependencies: []
requirement_refs:
- C-003
- FR-003
- FR-005
- NFR-003
planning_base_branch: fix/coord-read-fail-closed
merge_target_branch: fix/coord-read-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/coord-read-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/coord-read-fail-closed unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-read-fail-closed-01M38VVH
base_commit: ece5c77723149d8e3cb3489bc6bc03891262a5a4
created_at: '2026-09-24T05:52:19.842074+00:00'
subtasks:
- T009
- T010
- T011
history:
- event: created
  at: '2026-09-24T05:45:24Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/integration/test_accept_matrix_coord_partition.py
execution_mode: code_change
owned_files:
- src/specify_cli/decisions/service.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- tests/specify_cli/decisions/test_service_idempotency.py
- tests/specify_cli/cli/commands/test_decision_single_authority.py
- tests/integration/test_accept_matrix_coord_partition.py
role: implementer
tags: []
tracker_refs:
- '#4966'
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro` before anything else.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objective
End the decision-ledger husk split-brain: on a coord mission whose coord worktree is a **materialised status-only husk**, `decisions/service.py` resolves `meta.json` through that husk (which lacks it) → `MISSION_NOT_FOUND`, deferred decisions never reach the PRIMARY index, and `accept` is permanently blocked on the spec.md clarification marker. `meta.json` is a **PRIMARY-partition** artifact; the fix is to resolve it via `PRIMARY_METADATA` so the service agrees with the ledger `accept` already reads. This is independent of WP01 (the state is MATERIALIZED, not UNMATERIALIZED). **Read `contracts/reader-partition-contract.md` first.**

## Key context (verified on main)
- `decisions/service.py::_mission_dir` (~203-216): `return placement_seam(repo_root, mission_slug).read_dir(STATUS_STATE)` — a COORD kind → the status-only husk. `_resolve_mission_id` (~151-200) reads `meta.json` from that dir → `MISSION_NOT_FOUND`.
- **Wrong docstring (~157-167)**: claims a materialised coord worktree carries `meta.json`. It does not — `meta.json` is `PRIMARY_METADATA`, "only ever lives on the PRIMARY checkout" (`resolution.py:886`, `artifacts.py:169`); the husk holds `status.events.jsonl`/`status.json` "and nothing else" (`coherence.py:168`).
- Reference (unchanged): `acceptance/__init__.py::_has_blocking_clarification_marker` (~666) reads the ledger via `load_index(file_path.parent)` = the PRIMARY spec dir. The service must resolve to the SAME partition.

## Subtasks

### T009 — Red-first `[P]`
In `tests/specify_cli/decisions/test_service_idempotency.py` (and/or `test_decision_single_authority.py`), build a coord mission with a materialised status-only husk (coord worktree present, no `meta.json`/`decisions/` there) and assert `_resolve_mission_id` / `decision open` **resolves** (finds `meta.json` on PRIMARY). Confirm it FAILS pre-fix (`MISSION_NOT_FOUND`). Paste the failure.

### T010 — Resolve meta.json via PRIMARY + fix docstring `[P]`
Change `_mission_dir` / `_resolve_mission_id` to locate `meta.json` via a **PRIMARY_METADATA** resolution (it short-circuits to the PRIMARY checkout, never the coord husk). Keep any legitimately-coord reads (status) as-is. Correct the `:157-167` docstring to state the husk does NOT carry `meta.json` and that `meta.json` resolves to PRIMARY. Do not change `acceptance/__init__.py`.

### T011 — Integration: decision + accept agree `[P]`
Add `tests/integration/test_accept_matrix_coord_partition.py`: on a materialised-husk coord mission, a deferred→resolved decision reaches the PRIMARY index that `_has_blocking_clarification_marker` reads, and `accept` proceeds (no permanent block, no split-brain). Add a non-coord/flat regression (decision flow unchanged). Run `tests/specify_cli/decisions/` + the new integration test; paste counts.

## Branch Strategy
Base + target `fix/coord-read-fail-closed`; worktree per `lanes.json`.

## Definition of Done
- `decision open` resolves on a materialised husk (no MISSION_NOT_FOUND); `accept` proceeds; decision service + accept read the same PRIMARY ledger (FR-003, NFR-003, red-first green).
- Docstring corrected (no false meta.json-in-husk claim). Non-coord flows unchanged.
- `ruff`/`mypy` clean on owned files.

## Reviewer guidance
Confirm `meta.json` is resolved via PRIMARY_METADATA (grep: no `read_dir(STATUS_STATE)` feeding a meta.json read). Confirm agreement with `acceptance/__init__.py`'s `load_index(file_path.parent)`. This is the #4966 that blocked THIS mission's own `decision open` (tracer-tooling-friction.md) — verify the repro reflects that.
