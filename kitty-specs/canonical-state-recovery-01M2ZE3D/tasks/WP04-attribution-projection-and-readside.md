---
work_package_id: WP04
title: '#4786 attribution projection + accept read-side + detector + merge guard'
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- C-003
- C-004
planning_base_branch: fix/canonical-state-recovery
merge_target_branch: fix/canonical-state-recovery
branch_strategy: Planning artifacts for this mission were generated on fix/canonical-state-recovery. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/canonical-state-recovery unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-canonical-state-recovery-01M2ZE3D
base_commit: d5b8e9ea985b8c9e22fa305705c5c7e6f11e7c2b
created_at: '2026-09-20T13:05:00+00:00'
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Attribution & read-side
history:
- at: '2026-09-20T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_implementer_attribution_projection.py
- tests/acceptance/test_accept_gate_rejection_cycle.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/reducer.py
- src/specify_cli/status/doctor.py
- src/specify_cli/acceptance/summary_core.py
- src/specify_cli/cli/commands/merge.py
- docs/changelog/CHANGELOG.md
- tests/status/test_implementer_attribution_projection.py
- tests/acceptance/test_accept_gate_rejection_cycle.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4786'
---

# Work Package Prompt: WP04 – #4786 attribution projection + accept read-side + detector + merge guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Fix #4786 at the **read-root**, not the write path. `agent` is a *live-claim* slot that legitimately changes hands (implementer→reviewer) and is correctly released on rollback — leave that alone. The real miss is that nothing owns durable *implementer provenance*; derive it from the immutable event log.

**Done when:**
- A new `_project_implementer_attribution` in `status/reducer.py` (a sibling of `_project_cancellation_provenance`, `reducer.py:67-90`) scans the raw event stream for the prior implementer-role claim and exposes a **derived** attribution slot the fold/release never touches (FR-004, FR-005).
- The accept gate reads that derived slot through **one shared family accessor** (`summary_core.py:86-98`, covering agent/assignee/shell_pid); an ordinary reject→re-review→approve (no `--agent`) reaches `accept` with **no** "missing agent" (FR-005, FR-007, SC-004). A **never-owned** WP still refuses honestly (no fabrication).
- `status/doctor.py:215-240` blanked-slot detector is narrowed to genuine on-disk `agent: ""` and its recommended-action reworded (a released-but-historically-owned WP is no longer a finding) (FR-007).
- `merge.py:259/456` `(mission or "").strip()` is guarded against an unresolved `OptionInfo` default, returning the clean "Use --mission" message (FR-008).
- Every remaining canonical-state refusal message names its repair (FR-006).

## Context & Constraints

- Grounded sites (verify via Read): `status/reducer.py:17` (clear happens UPSTREAM in `spec_kitty_events.diary` — do NOT touch), `:53-64` (`_state_to_snapshot`/`reduce` — the local seam to add the projection), `:67-90` (`_project_cancellation_provenance` — the precedent to mirror); `acceptance/summary_core.py:79` (reads folded `snapshot["agent"]`), `:86-98` (family required; `:87` agent on every lane); `status/doctor.py:215-240` (detect-without-cure); `tasks_move_task.py:2567-2571` (implementer claim `policy_metadata` — the source fact in the log); `merge.py:259,456`.
- Do **NOT** edit `tasks_move_task.py:2891`/`:2970` (the release/suppression — keep #4673 byte-for-byte), and do **NOT** touch `status/models.py` or the upstream `spec_kitty_events.diary` fold. The projection reads the raw event stream; it never mutates a slot.
- Terminology canon (C-004); ATDD red-first (C-003); ruff/mypy clean; complexity ≤15; projection is read-only + idempotent.

## Subtasks

### T015 — Red: rejection-cycle block
Add `tests/acceptance/test_accept_gate_rejection_cycle.py` (`pytest.mark.regression`, pinned #4786): drive a WP claim→for_review→reject→re-review→approve with NO `--agent` on the return legs, then run the `accept` entry point; assert it currently blocks with "missing agent in canonical runtime state". RED against the desired clean accept.

### T016 — Attribution projection
Add `_project_implementer_attribution` to `status/reducer.py` mirroring `_project_cancellation_provenance`; derive the prior implementer-role owner from the raw stream; expose the derived slot in the snapshot. Unit-test in `tests/status/test_implementer_attribution_projection.py` (derives for owned; yields nothing for never-owned; idempotent).

### T017 — Read-side family accessor + honest refusal message
Point `summary_core.py` at the derived slot through one shared accessor for agent/assignee/shell_pid. T015 turns green; add a never-owned case that still refuses honestly. **Also reword the bare `summary_core.py:87` "missing agent in canonical runtime state" refusal to name `spec-kitty doctor mission-state --fix --mission <slug>`** (the never-owned case still refuses, so FR-006/SC-003 require it to name a repair). Assert the never-owned refusal message contains the repair command.

### T018 — Narrow the detector
Narrow `status/doctor.py:215-240` to genuine on-disk `agent: ""`; reword the recommended-action away from "re-record by hand".

### T019 — merge OptionInfo guard
Guard `merge.py:259/456` `(mission or "").strip()` against an `OptionInfo` default; add a focused unit test.

### T020 — Green + honesty
T015 clean via derivation; never-owned still refuses; projection idempotent/read-only.

### T021 — CHANGELOG
Add a `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (impact-first, `(#4758 #4786)`), no version bump (release gate owns that).

### T022 — Blast radius + terminology guard
Run `tests/status/` + `tests/acceptance/` (narrow, file-scoped). Because this WP edits operator-facing prose (refusal messages, CHANGELOG), also run `pytest tests/architectural/test_no_legacy_terminology.py` (C-004). Record counts in `traces/test-evidence.md`.
