---
work_package_id: WP02
title: Doctor flatten remote re-verification guard (#4979)
dependencies:
- WP01
requirement_refs:
- FR-004
- NFR-002
- C-001
planning_base_branch: issue-4979-coord-branch-remote-probe
merge_target_branch: issue-4979-coord-branch-remote-probe
branch_strategy: Planning artifacts for this mission were generated on issue-4979-coord-branch-remote-probe. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4979-coord-branch-remote-probe unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-branch-remote-probe-01M3F6M7
base_commit: 4d083c4012c02c586b81bc7e6f1b9602b6b1546e
created_at: '2026-09-26T17:12:18.715899+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 2 - doctor belt-and-suspenders
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/_coordination_doctor.py
- tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4979'
---

# Work Package Prompt: WP02 — Doctor flatten remote re-verification

## ⚡ Do This First: Load Agent Profile

Load the `implementer-ivan` profile via `/spk-doctrine-profile-load` before parsing the rest.
Read `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`.

- **Profile**: `implementer-ivan` · **Role**: `implementer` · **Agent/tool**: `claude`

## Objectives & Success Criteria

Add an independent last line of defence at the destructive flatten site so a mission whose
coordination branch still exists on any remote is NEVER flattened by `doctor coordination
--fix` — even if a `COORDINATION_WORKTREE_NEVER_CREATED` finding is somehow reached (a future
probe regression, a race). This is belt-and-suspenders behind WP01's source fix.

- **SC (#4979, FR-004):** `_fix_never_created_branches`
  (`src/specify_cli/cli/commands/_coordination_doctor.py:862`) re-verifies each finding's
  coordination branch against the remote (via WP01's shared `remote_branch_lookup` primitive)
  BEFORE calling `flatten_coordination_metadata` (:894). Present-on-remote ⇒ skip the flatten,
  leave `meta.json` unchanged, print an actionable message ("branch exists on <remote>; run
  `git fetch` — not flattened"). Proven RED-first (T007).
- **SC (FR-002 preserved):** a genuinely-absent branch (gone from every remote) still flattens
  exactly as today.
- **SC (C-001):** consume WP01's primitive — do NOT hand-roll a second remote check here.
- New/changed code: complexity ≤ 15, focused tests, ruff + ruff format + mypy clean on touched files.

## Context & Constraints

- After WP01, the doctor CHECK at `:501` (which calls the fixed `_coord_branch_exists`) already
  stops emitting `COORDINATION_WORKTREE_NEVER_CREATED` for a remote-only branch. WP02 guards the
  FIX path independently, so the destructive mutation is unreachable for a remote-present branch
  regardless of the check.
- ATDD red-first: T007 constructs (or stubs) a `COORDINATION_WORKTREE_NEVER_CREATED` finding for
  a mission whose branch is present on a remote and asserts today's `_fix_never_created_branches`
  flattens `meta.json` (RED). Pin `#4979`, `@pytest.mark.regression`.
- Do NOT alter the `_fix_stranded_reverts` / #4920 fast-forward path — this WP touches ONLY the
  never-created flatten path.

## Implementation Sketch

1. **T007 (RED):** fixture with a remote-present coord branch + a synthesized NEVER_CREATED
   finding (carrying `meta_path`); assert flatten happens (RED).
2. **T008:** in `_fix_never_created_branches`, before `flatten_coordination_metadata`, call the
   WP01 primitive on the finding's `coordination_branch`; if `HIT` (or `ERROR`, fail-closed),
   skip + record a skipped-slug message; only `CLEAN_MISS`/`NO_REMOTE` proceed to flatten.
   Mirror the fail-closed posture in `_apply_never_created_fix` (:1222) if it re-derives.
3. **T009:** blast radius + ruff/format/mypy + tracer append.

## Validation

```
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/cli/commands/test_doctor_coordination.py \
  tests/specify_cli/cli/commands/test_coordination_doctor.py \
  tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py -q
.venv/bin/python -m ruff check <touched> && .venv/bin/python -m ruff format --check <touched>
.venv/bin/python -m mypy <touched>
```
Plus `make test-fast`. Append to `tracers/`.
