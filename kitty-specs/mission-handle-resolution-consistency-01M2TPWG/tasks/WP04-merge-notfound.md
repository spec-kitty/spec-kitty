---
work_package_id: WP04
title: 'merge: truthful not-found (fresh + resume) with abort tolerance'
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
- T020
history:
- Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/merge/test_merge_missing_mission.py
execution_mode: code_change
owned_files:
- src/specify_cli/merge/resolve.py
- src/specify_cli/cli/commands/merge.py
- tests/merge/test_merge_missing_mission.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role: implementer) via `/ad-hoc-profile-load` first.

## Objective

`merge` (fresh AND `--resume`) must refuse a nonexistent handle with the canonical
`Mission not found: <handle>` instead of the misleading "lanes.json is required … run
task-finalization" (fresh) or "No interrupted merge to resume" (resume). `merge --abort`
must stay tolerant of an unresolvable handle. **Footgun**: do not gate in the shared helper.

## Context

- `merge/resolve.py::_resolve_mission_slug` (`:49-74`) deliberately returns the RAW slug for
  an unresolvable handle (`:71` on `StatusReadPathNotFound`, `:74` fallthrough). The
  `except` comment confirms `--abort` depends on this non-raising behavior. **Keep it.**
- Fresh path: `cli/commands/merge.py:628` resolves via `_resolve_slug_or_exit` (`:246`), then
  the lanes load raises `MissingLanesError` ("lanes.json is required …",
  `lanes/persistence.py:105`) for the phantom dir.
- Resume path: `_dispatch_resume` (`merge.py:384-400`) resolves the raw handle then hits
  `_load_merge_state_for_mission` → None → exits `:393-395` with "No interrupted merge to
  resume" — it never reaches `:628`. So a gate only at `:628` leaves resume wrong.
- Abort path: `_dispatch_abort` (`merge.py:337`) is ALSO a `_resolve_slug_or_exit` caller —
  it must stay ungated (C-003).
- `merge --json` is dry-run-only (`merge.py:669`) — the not-found for a normal merge is a
  human message; do NOT add a new JSON surface (FR-011 scope).

## Subtasks

### T016 — Red tests
Create `tests/merge/test_merge_missing_mission.py` (add `pytestmark`; `tests/merge/test_resolve_seam.py`
is the pattern). With ≥2 real missions, no interrupted merge: (a) `merge --mission zznope`
(fresh) → `Mission not found: zznope`, non-zero, NOT "lanes.json is required"; (b)
`merge --resume --mission zznope` → `Mission not found: zznope`, NOT "No interrupted merge to
resume"; (c) `merge --abort --mission zznope` → tolerant (non-raising) cleanup, NOT a hard
not-found. (a)/(b) fail initially.

### T017 — Gate the fresh path
At `merge.py:628` (fresh flow), after `_resolve_slug_or_exit`, add an `.exists()` check on the
resolved mission dir → emit canonical `Mission not found: <handle>` + non-zero exit, before the
lanes load.

### T018 — Gate the resume path
In `_dispatch_resume` (`merge.py:391`), add the same `.exists()` gate BEFORE the
`_load_merge_state_for_mission` no-state check, so the unknown-handle refusal pre-empts "No
interrupted merge to resume".

### T019 — Preserve abort tolerance
Leave `merge/resolve.py::_resolve_mission_slug` returning the raw slug on a miss, and leave
`_dispatch_abort` (`:337`) ungated. Do NOT put the `.exists()` gate inside the shared
`_resolve_slug_or_exit` helper.

### T020 — Green
T016 passes (all three), especially abort still tolerant. `ruff`/`mypy` clean.

## Definition of Done
- Fresh + resume nonexistent handle → canonical not-found; abort unchanged/tolerant.
- Blast radius: `PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/ -q`.

## Branch Strategy
Base/merge target `issue-4631-4682-mission-handle-resolution`; lane worktree from `lanes.json`.

## Reviewer guidance
Confirm the gate is at the TWO callers (fresh `:628`, resume `:391` before the no-state check),
NOT in `_resolve_slug_or_exit`, and NOT at `_dispatch_abort`. Confirm the abort test proves
tolerance.
