---
work_package_id: WP04
title: 'Caller blast-radius: coord readers fail loud at a sane boundary'
dependencies:
- WP01
requirement_refs:
- FR-004
- NFR-002
planning_base_branch: fix/coord-read-fail-closed
merge_target_branch: fix/coord-read-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/coord-read-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/coord-read-fail-closed unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
history:
- event: created
  at: '2026-09-24T05:45:24Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: tests/mission_runtime/
create_intent:
- tests/mission_runtime/test_coord_read_seam_callers.py
execution_mode: code_change
owned_files:
- tests/mission_runtime/test_coord_read_seam_callers.py
- src/specify_cli/decisions/emit.py
- src/specify_cli/agent_utils/status.py
- src/specify_cli/lanes/recovery.py
- src/specify_cli/agent_tasks_ports.py
role: implementer
tags: []
tracker_refs:
- '#4959'
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro` before anything else.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objective
With WP01 making the seam raise on UNMATERIALIZED, the ~25 no-catch coord `STATUS_STATE` readers now **propagate** the raise — the *desired* fail-loud, but each must land at a **sane boundary** (a clear operator-facing error, not a raw traceback). This WP verifies that with regression tests and wraps the raw-traceback cases at their CLI edge. It also pins that sanctioned read-only degraders keep degrading and already-safe catchers are unchanged (NFR-002). **Read `research.md` §blast-radius + `contracts/seam-fail-closed-contract.md` first.**

## Key context (from the Phase-0 audit)
- **Already-safe (verify unchanged, do NOT edit):** `status/aggregate.py:357`, `agent/status.py:180/219`, `merge/executor.py:2543`, `mission_finalize.py:2090/2626`, `retrospective/generator.py:281`, `worktree_topology.py:182`, `_review_cycle_reconcile_doctor.py:276`.
- **Sanctioned read-only degraders (verify still degrade, do NOT edit):** `mission_runtime/read_dir_degrade.py`, `review/cycle.py:294`.
- **No-catch readers to verify + wrap if they'd emit a raw traceback** (this WP's edit set): `decisions/emit.py:88`, `agent_utils/status.py:103`, `lanes/recovery.py:615`, `agent_tasks_ports.py:339`. (Others — `workspace/context.py`, `acceptance/__init__.py:964`, `tasks_*` — are verified read-only in T013; only edit one if it emits a raw traceback, and record a one-line out-of-map rationale rather than expanding owned_files broadly.)

## Subtasks

### T012 — Degrader + already-safe regression
`tests/mission_runtime/test_coord_read_seam_callers.py` (new): assert the sanctioned read-only degraders still degrade under UNMATERIALIZED (their `except StatusReadPathNotFound` absorbs the new sibling); assert a representative already-safe catcher path is unchanged. Confirms NFR-002.

### T013 — Verify fail-loud at a sane boundary + wrap raw tracebacks
For each named no-catch reader (`decisions/emit.py`, `agent_utils/status.py`, `lanes/recovery.py`, `agent_tasks_ports.py`): drive it on an UNMATERIALIZED coord mission and confirm the failure surfaces as a **sane, operator-facing error** (the sibling's `next_step`, or a wrapped CLI error) — not a raw traceback. Where a raw traceback would leak, wrap the read at the boundary to present `CoordinationWorktreeUnmaterialized.next_step`. Keep edits minimal (fail-loud is the goal; only add a message wrap).

### T014 — Regression coverage
Add cases proving: each named reader fails loud sanely; a non-coord (SINGLE_BRANCH/LANES/flat) mission produces NO new raise for the same readers. Run `tests/mission_runtime/` + the touched modules' tests; paste counts.

## Branch Strategy
Base + target `fix/coord-read-fail-closed`; worktree per `lanes.json`.

## Definition of Done
- Named no-catch readers fail loud at a sane boundary (FR-004); sanctioned degraders + already-safe catchers unchanged; non-coord no new raise (NFR-002).
- Any caller edit is a minimal message-wrap with a one-line rationale; no broad refactor.
- `ruff`/`mypy` clean on owned files.

## Reviewer guidance
Confirm the wraps present a sane message (not a traceback) and don't swallow the error into a silent success. Confirm the sanctioned degraders were NOT changed. Confirm non-coord paths are untouched.
