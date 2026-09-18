---
work_package_id: WP01
title: 'Shared seam: mission population + canonical not-found constant'
dependencies: []
requirement_refs:
- FR-006
- FR-012
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-handle-resolution-consistency-01M2TPWG
base_commit: a09afc5d9c1dfa012f441d51539234487c3d95fd
created_at: '2026-09-18T18:09:32.339666+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/context/
create_intent:
- tests/specify_cli/context/test_mission_selection.py
execution_mode: code_change
owned_files:
- src/specify_cli/context/mission_resolver.py
- tests/specify_cli/context/test_mission_selection.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load`
with profile `python-pedro` (role: implementer). Adopt its identity, boundaries, and
TDD discipline for the entirety of this work package. Do not begin editing until the
profile is loaded.

## Objective

Provide the two shared building blocks the rest of the mission reuses:
1. a **mission population/selection helper** that enumerates existing missions with a
   single, legacy-tolerant rule, and
2. a **canonical not-found message** constant.

This is the FOUNDATION work package — WP02–WP06 import from here. Get the population
rule and the message form exactly right.

## Context (read before coding)

- File to edit: `src/specify_cli/context/mission_resolver.py`. It already holds
  `ResolvedMission` (fields: `mission_id`, `mission_slug`, `feature_dir`, `mid8` — **no
  `friendly_name`**), `FsMissionResolver` / `FakeMissionResolver`, `resolve_mission`,
  `AmbiguousHandleError`, `MissionNotFoundError`, and imports `load_meta`.
- **Population rule (decided by the brownfield squad — do not deviate):** count any
  mission directory bearing `spec.md` **or** `meta.json`. This matches the agent-layer
  `_list_feature_spec_candidates` (`cli/commands/agent/mission_feature_resolution.py:332`)
  so `next` and plan/tasks agree on the count. **Do NOT build purely on
  `FsMissionResolver.all_missions()`** — it silently drops missions whose `meta.json`
  lacks a `mission_id` (`mission_resolver.py:183-186`), which would miscount legacy
  missions. Reuse the existing directory walk; do not add a second independent
  `kitty-specs/` scan (there is a walker gate: `tests/architectural/test_mission_resolver_walker_gate.py`).
- **Name collision:** `discover_missions` already exists in `src/specify_cli/mission.py:809`
  for mission *types*. Name the new helper `list_missions_for_selection`.
- **friendly_name** comes from `meta.json` (`MissionMetadata.friendly_name`); fall back to
  the slug when absent so listings never blank.
- **Canonical message:** reuse the existing form `Mission not found: <handle>` (capital M),
  as `materialize.py:98` already emits and `next_cmd.py`'s `_emit_mission_not_found_error`
  models. Do NOT invent a lowercase variant.

## Subtasks

### T001 — Red: unit tests for the population helper
Create `tests/specify_cli/context/test_mission_selection.py` (needs a `pytestmark` marker —
e.g. `pytestmark = pytest.mark.unit`). Stage a `tmp_path` repo with `kitty-specs/` holding:
(a) two normal missions with `meta.json` carrying `mission_id`; (b) one legacy mission dir
with `meta.json` lacking `mission_id` (or only `spec.md`). Assert (all failing initially):
- `list_missions_for_selection(root)` returns 3 entries (legacy included), each with
  `mission_slug`, `mid8` (None allowed for legacy), `friendly_name` (slug fallback when absent);
- a sole-mission helper returns the one slug when exactly one exists, `None` for 0 or >1;
- a count helper agrees with `len(...)`;
- the canonical message helper/constant formats `Mission not found: zznope`.

### T002 — `list_missions_for_selection(main_repo)`
Enumerate spec/meta-bearing dirs under `<main_repo>/kitty-specs/`, returning a small
dataclass (or typed dict) list per data-model.md. Read `mission_id`/`mid8`/`friendly_name`
best-effort via `load_meta`; tolerate absence. Deterministic ordering by `mission_slug`.

### T003 — sole-mission + count helpers
Add a `sole_mission_for_selection(main_repo) -> str | None` (FR-004 convention: the slug
when exactly one, else None) and expose the count via the listing length. Keep these thin
over T002 so `next` (WP05) and any consumer share one definition.

### T004 — canonical not-found constant
Hoist `MISSION_NOT_FOUND_MESSAGE = "Mission not found: {handle}"` (or a
`mission_not_found_message(handle)` function) as the single source for the fixed commands.
Document that it is intentionally NOT applied to `MissionNotFoundError` (keeps its
`backfill-identity` remediation) or `reconcile` (dossier wording).

### T005 — `__all__`
Add `__all__` enumerating the **full** existing public surface (`ResolvedMission`,
`AmbiguousHandleError`, `MissionNotFoundError`, `FsMissionResolver`, `FakeMissionResolver`,
`resolve_mission`) **plus** the new symbols. Missing any existing symbol trips
`tests/architectural/test_no_dead_symbols.py`.

### T006 — Green + gates
Make T001 pass. `ruff check`, `ruff format`, and `mypy` clean on the file. Keep every new
function ≤ complexity 15.

## Definition of Done
- New helpers + constant present, `__all__` complete, all T001 assertions green.
- `ruff`/`mypy` zero issues; no new dependency.
- Blast radius run: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/context/ -q`
  plus `tests/architectural/test_no_dead_symbols.py tests/architectural/test_mission_resolver_walker_gate.py`.

## Branch Strategy
Planning/base branch: `issue-4631-4682-mission-handle-resolution`. Final merge target:
`issue-4631-4682-mission-handle-resolution`. The execution worktree is the lane computed
for this WP in `lanes.json`; do not hand-create branches.

## Reviewer guidance
Confirm the population rule counts legacy (no-`mission_id`) missions and matches the
plan/tasks count rule; confirm the message is the capital-M form; confirm `__all__` lists
every pre-existing public symbol; confirm no second `kitty-specs/` walk was added.
