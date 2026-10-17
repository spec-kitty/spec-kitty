---
work_package_id: WP01
title: Write-target gate owned-awareness
dependencies: []
requirement_refs:
- FR-002
- FR-005
- NFR-001
- NFR-002
planning_base_branch: kitty-base-6320
merge_target_branch: kitty-base-6320
branch_strategy: Planning artifacts for this mission were generated on kitty-base-6320. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty-base-6320 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Gate foundation
history:
- at: '2026-10-17T19:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/mission_runtime/
create_intent:
- tests/mission_runtime/test_write_target_degrade_owned_6320.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/mission_runtime/write_target_degrade.py
- src/specify_cli/coordination/surface_resolver.py
- tests/mission_runtime/test_write_target_degrade_owned_6320.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Write-target gate owned-awareness

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make the fail-closed write-target gate recognize an **owned-only** mission when it is handed a
validated `OwnedCheckout` fact, so `issue-verdict --owned-checkout` (wired in WP02) stops being
refused before it can compute a write dir — while the gate's three unrelated callers stay
byte-identical.

- **FR-002**: `resolve_for_write` + the `mission_runtime` write-target gate recognize the owned mission when given the owned fact.
- **FR-005**: the three unrelated callers of `assert_coord_write_materialized` stay byte-identical.
- **NFR-001**: an `owned` fact that resolves no real mission still refuses fail-closed (no fallback to the repository root).
- **NFR-002**: additive `owned=None` keyword args only; no reverse import edge; layer direction preserved.

## Context & Constraints

Grounding (file:line may drift; verify):
- `src/mission_runtime/write_target_degrade.py`:
  - `resolve_write_target_or_degrade(repo_root, mission_slug, kind, *, degrade_ref, terminus_write=False)` (~L80) — add `owned: OwnedCheckout | None = None`; pass to `resolve_placement_only(..., owned=owned)` (~L148, already owned-capable), `assert_coord_write_materialized(..., owned=owned)` (~L153), and `_mission_meta_exists(..., owned=owned)` (~L146).
  - `_mission_meta_exists(repo_root, mission_slug)` (~L335) — add `owned`; when `owned` is present, read the owned checkout's meta dir instead of `read_primary_meta(repo_root, …)` (~L362). This is the exact `False`→`True` fix for an owned-only mission.
  - `assert_coord_write_materialized(repo_root, mission_slug, kind, resolved)` (~L160) — add `owned`; thread onward to `_delegate_to_write_location_accessor` → `establish_coord_write_location(..., owned=None)` (~L301), which currently hard-codes `owned=None` and must become a passthrough.
- `src/specify_cli/coordination/surface_resolver.py::resolve_for_write(repo_root, mission_slug, kind)` (~L863) — add `owned: OwnedCheckout | None = None`; forward to `resolve_write_target_or_degrade(..., owned=owned)`.

Constraints:
- `assert_coord_write_materialized` has THREE other callers — `decision_log._resolve_default_target`, `bookkeeping_commit._resolve_bookkeeping_commit_target`, `status_transition._resolve_write_target`. The new `owned` param MUST default `None`; those callers pass nothing and MUST resolve byte-identically (FR-005).
- Reuse the `OwnedCheckout` type via the same import path `mission_runtime` already uses internally; do NOT create a new owned-resolution authority (C-001).
- No matrix-format or writer-semantics change (C-002).

## Subtasks

T001 Add `owned` param to `resolve_write_target_or_degrade` and thread it to `resolve_placement_only`, `assert_coord_write_materialized`, and `_mission_meta_exists` (WP01)
T002 Make `_mission_meta_exists` owned-aware: read the owned checkout's meta when `owned` is present, else the primary root as today (WP01)
T003 Add `owned` to `assert_coord_write_materialized` and convert the `establish_coord_write_location(..., owned=None)` hard-code into a passthrough (WP01)
T004 Add `owned` passthrough to `coordination.surface_resolver.resolve_for_write` (WP01)
T005 Red-first unit test: an owned-only mission (owned fact present) no longer raises fail-closed from the gate; the same mission resolved from the primary root still refuses (NFR-001) (WP01)
T006 Unit test proving the three unrelated callers of `assert_coord_write_materialized` resolve byte-identically with the new `owned=None` default (FR-005) (WP01)

## Test strategy

- New file `tests/mission_runtime/test_write_target_degrade_owned_6320.py`.
- T005 is red-first: write the owned-resolves assertion, confirm it fails at the merge-base shape (gate refuses), then implement until green. Keep the negative control (owned fact that resolves no mission still refuses) in the same test module as the same-fixture positive control for FR-005's ratchet.
- T006: assert each of the three callers produces the same resolved target with and without the param present (default path). One focused parametrized test; no shape-pins.
- Declare `pytestmark` per the repo marker convention.

## Definition of Done

- Gate functions + `resolve_for_write` accept and thread `owned`; owned-only mission resolves; fail-closed preserved for an unresolved owned fact.
- Three unrelated callers byte-identical (test-proven).
- `ruff check` + `ruff format --check --force-exclude` + `mypy` clean on touched files (no new suppressions).
- `mark-status` the subtasks done.

## Risks & reviewer guidance

- The `establish_coord_write_location` passthrough is the easy miss — verify it is actually forwarded, not left `None`.
- Reviewer: confirm NFR-001 negative control is non-vacuous (goes red if the owned branch falls through to primary) and FR-005 byte-identity test actually exercises all three callers.
