---
work_package_id: WP01
title: Seam raise contract + CoordinationWorktreeUnmaterialized sibling + ADR
dependencies: []
requirement_refs:
- C-001
- C-002
- C-005
- FR-001
- NFR-002
planning_base_branch: fix/coord-read-fail-closed
merge_target_branch: fix/coord-read-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/coord-read-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/coord-read-fail-closed unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-read-fail-closed-01M38VVH
base_commit: c87e78ca5790c954024266ab13ce43d46f1016a6
created_at: '2026-09-24T05:51:32.461706+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- event: created
  at: '2026-09-24T05:45:24Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md
- tests/mission_runtime/test_coord_read_seam.py
execution_mode: code_change
owned_files:
- src/mission_runtime/resolution.py
- src/specify_cli/coordination/surface_resolver.py
- tests/mission_runtime/test_coord_read_seam.py
- tests/mission_runtime/test_resolution_typed_errors.py
- docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md
role: implementer
tags: []
tracker_refs:
- '#4959'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your profile: `/ad-hoc-profile-load python-pedro`. It governs your implementation style, boundaries, and quality standards.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objective

Make the placement read seam **fail closed** on an unmaterialised coordination surface. Today `_classify_artifact_surface` returns empty-PRIMARY for `CoordState.UNMATERIALIZED` (coord branch declared in git but its worktree absent — the fresh-clone / CI / removed-worktree case); readers then act on empty as if it were the real document. This WP makes the seam **raise** a typed error there instead, so both surfaces and every future reader inherit fail-closed. **Read `research.md` + `contracts/seam-fail-closed-contract.md` + `data-model.md` first.**

## Key context (verified on main d6533ea419)

- `src/mission_runtime/resolution.py::_classify_artifact_surface` (~1904-1967): tail raises `CoordinationBranchDeleted` on `CoordState.DELETED` (~1949), returns COORD on `MATERIALIZED` (~1958), and `return TopologySurface.PRIMARY, None` (~1967) for `EMPTY`/`UNMATERIALIZED`/`NONE`. Return type `tuple[TopologySurface, Path | None]`.
- PRIMARY-partition kinds short-circuit to PRIMARY **before any probe** (`declared_read_surface`, ~1928-1929) → they can never raise. The change is invisible to them.
- `CoordState` (`src/specify_cli/missions/_read_path_resolver.py:256-281`): `UNMATERIALIZED` = coord root absent AND branch present in git; `DELETED` = absent AND branch gone; `EMPTY` = coord root present, mission dir absent; `NONE` = no coord topology.
- `src/specify_cli/coordination/surface_resolver.py`: `CoordinationBranchDeleted(StatusReadPathNotFound)` (~180-273) with `error_code`/`next_step`/`for_mission`. This is the model for the new sibling. **`_coord_branch_exists` (~444) is the #4979/#4950 surface — do NOT touch it (C-002).**

## Subtasks

### T001 — Red-first: UNMATERIALIZED returns empty-PRIMARY (should raise)
In `tests/mission_runtime/test_coord_read_seam.py` (new), construct a coord-topology mission with `CoordState.UNMATERIALIZED` (coord branch declared, worktree absent) and assert a coord-partition `read_dir(STATUS_STATE)` **raises** `CoordinationWorktreeUnmaterialized`. Confirm it FAILS pre-fix (returns an empty-PRIMARY path). Paste the failure.

### T002 — Add the sibling exception (additive)
In `surface_resolver.py`, add `class CoordinationWorktreeUnmaterialized(StatusReadPathNotFound)` next to `CoordinationBranchDeleted`: its own `error_code` (e.g. `COORDINATION_WORKTREE_UNMATERIALIZED`) and a truthful `next_step` pointing at **materialising** the coord worktree (NOT flatten — the branch exists). Provide a `for_mission(...)` factory mirroring the sibling. **Only ADD; do not modify `_coord_branch_exists` or any existing function (C-002).**

### T003 — Seam raises on UNMATERIALIZED
In `_classify_artifact_surface`, split the `EMPTY`/`UNMATERIALIZED`/`NONE` fall-through: on `UNMATERIALIZED` for a coord-partition kind, raise `CoordinationWorktreeUnmaterialized.for_mission(...)`. Keep `DELETED`→`CoordinationBranchDeleted`, `MATERIALIZED`→COORD, and `EMPTY`/`NONE`→PRIMARY unchanged. Add a comment naming #4959 + the operator decision `DM-01M38VWD`.

### T004 — Regression pins
Extend `tests/mission_runtime/test_resolution_typed_errors.py`: DELETED still raises `CoordinationBranchDeleted`; a PRIMARY-partition kind (e.g. `PRIMARY_METADATA`) on the same UNMATERIALIZED mission does **not** raise; `EMPTY`/`NONE` still return PRIMARY. Run and paste counts.

### T005 — ADR
`docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md`, status **Accepted**: context (empty-PRIMARY substitution → destructive reads), decision (seam raises on UNMATERIALIZED; new sibling; scoped to coord-partition reads; EMPTY/NONE deferred), consequences (coord readers now fail loud; sanctioned degraders keep degrading). Frontmatter `description` 50–180 chars, unique/non-boilerplate; MD060 spaced pipes. Do NOT regen docs indexes (WP05 owns that).

## Branch Strategy
Planning base + merge target `fix/coord-read-fail-closed`; execution worktree per `lanes.json`. Do not hand-create branches.

## Definition of Done
- UNMATERIALIZED coord read raises the new sibling (red-first green); DELETED/MATERIALIZED/EMPTY/NONE + PRIMARY kinds unchanged (FR-001, C-005, NFR-002).
- New exception additive in `surface_resolver.py`; `_coord_branch_exists` untouched (C-002).
- ADR present + gate-clean. `ruff`/`mypy` clean on changed files.

## Reviewer guidance
Confirm `_coord_branch_exists` is byte-unchanged. Confirm PRIMARY kinds still short-circuit (no new raise). Re-run the red-first swap.
