---
work_package_id: WP05
title: 'next: missing-handle discovery (auto-select / list / nudge)'
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-011
- FR-012
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
subtasks:
- T021
- T022
- T023
- T024
- T025
- T026
- T027
history:
- Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/next_cmd.py
create_intent:
- tests/next/test_next_missing_mission_discovery.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/next_cmd.py
- tests/next/test_next_missing_mission_discovery.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role: implementer) via `/ad-hoc-profile-load` first.

## Objective

Replace `next`'s hard `--mission required` usage error with discovery: exactly one mission →
auto-select and proceed; several → list `slug (mid8) — friendly_name` and exit cleanly (non-
usage); zero → nudge to specify. Keep the nonexistent-but-present handle's clean not-found.

## Context

- `next_cmd.py::_resolve_mission_slug` (`:447-508`): the empty/None branch raises
  `typer.BadParameter("--mission <slug> is required")` (`:455`) — even though `--mission` is
  declared optional at the Typer layer (`:126`). The nonexistent-but-present branch returns
  the raw handle (`:508`) → downstream `MissionNotFoundError` → `_emit_mission_not_found_error`
  (`:518-549`, human + JSON, already `MISSION_NOT_FOUND`-coded). **Keep that not-found path.**
- The caller `next_step` (`:195-217`) already routes resolution exceptions to structured
  emitters and has `json_output` in scope.
- Reuse WP01's `list_missions_for_selection` / `sole_mission_for_selection` for the population
  (legacy-tolerant; do NOT use `all_missions()` directly — it drops legacy missions).
- **Complexity**: do not inline list-building/JSON formatting into `_resolve_mission_slug`
  (would approach the ≤15 ceiling). Have it RETURN the sole slug (1) or RAISE a typed
  missing-handle discovery signal carrying the listing (N) / empty (0); let the caller emit.
- **Charter preflight** runs at `:188` BEFORE resolution at `:196`; verify it does not
  pre-empt the 0-mission nudge (the integration suite monkeypatches a bypass —
  `tests/next/test_next_command_integration.py`). Add a test that does NOT bypass it.
- Assert usage *semantics* (exit code / absence of the required-flag message), not the
  version-fragile literal "Invalid value".

## Subtasks

### T021 — Red tests
Create `tests/next/test_next_missing_mission_discovery.py` (add `pytestmark`; in-process
`CliRunner`). Cases: (a) exactly 1 mission → bare `next` auto-selects it and proceeds (query
mode exit 0); (b) >1 → lists each as `slug (mid8) — friendly_name`, non-zero, no required-flag
usage error, `--json` includes `available_missions`; (c) 0 → no-missions nudge pointing to
specify, non-zero; (d) sole mission is LEGACY (no `mission_id`) → still auto-selected (not
"no missions") + a backfill nudge; (e) regression: `next --mission zznope` (present-but-bad)
still yields the clean `_emit_mission_not_found_error`. (f) FR-009 without preflight bypass.

### T022 — Typed discovery signal
Add a typed exception (e.g. `MissingHandleDiscovery`) carrying `listings` and `sole_slug`.
Replace the `:455` raise: when the handle is empty/None, compute the population via WP01; if
exactly one, return that slug; else raise the signal (listings for N, empty for 0).

### T023 — Population wiring
Use WP01 helpers so the count matches plan/tasks. Carry `mid8`/`friendly_name` (slug fallback)
into the signal for rendering.

### T024 — Caller emits + exits
In `next_step` (`:195-217`), add an except arm for the discovery signal: sole → proceed (set
the slug and continue); N → render list + `raise typer.Exit(<non-zero>)`; 0 → render nudge +
exit. Honor `--json` in every arm (mirror `_emit_mission_not_found_error`'s dual shape;
include `available_missions` for N).

### T025 — Rendering + nudge
Human list: `slug (mid8) — friendly_name`, one per line, capped ~10, plus "re-run with
--mission <handle>". When any listed mission lacks `mission_id`, append "N mission(s) need
`spec-kitty migrate backfill-identity`". JSON: `available_missions: [{mission_slug, mid8,
friendly_name}]`.

### T026 — Regression
Confirm the present-but-nonexistent handle path is unchanged (T021e).

### T027 — Green + gates
All cases pass; `_resolve_mission_slug` stays ≤ complexity 15; `ruff`/`mypy` clean.

## Definition of Done
- Bare `next` never dead-ends on a required-flag usage error; 0/1/N (incl. legacy sole) behave per contract C5.
- Nonexistent-but-present handle keeps its clean not-found.
- Blast radius: `PWHEADLESS=1 .venv/bin/python -m pytest tests/next/ -q`.

## Branch Strategy
Base/merge target `issue-4631-4682-mission-handle-resolution`; lane worktree from `lanes.json`.

## Reviewer guidance
Confirm listing building lives in the seam/caller (not inflating `_resolve_mission_slug`),
the legacy sole-mission case auto-selects, JSON parity holds, and the required-flag test asserts
semantics not the "Invalid value" literal.
