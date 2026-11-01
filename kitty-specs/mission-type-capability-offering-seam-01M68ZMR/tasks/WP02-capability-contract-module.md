---
work_package_id: WP02
title: The capability contract module and its wiring
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-003
- C-001
- C-002
- C-004
planning_base_branch: issue-6331-mission-type-capability-offering-seam
merge_target_branch: issue-6331-mission-type-capability-offering-seam
branch_strategy: Planning artifacts for this mission were generated on issue-6331-mission-type-capability-offering-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6331-mission-type-capability-offering-seam unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 2 - Green
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/missions/
create_intent:
- src/charter/offering/missions/capabilities.py
execution_mode: code_change
owned_files:
- src/charter/offering/missions/capabilities.py
- src/charter/offering/api.py
- src/charter/missions.py
- src/charter/activation/mission_type_profiles.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6331'
---

# Work Package Prompt: WP02 – The capability contract module and its wiring

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: claude

---

## Objectives & Success Criteria

Turn WP01's red seam test green by putting the capability contract on the offering seam, without
inverting the layer:

1. `src/charter/offering/missions/capabilities.py` defines the frozen `MissionTypeCapabilities`
   value object, the runtime-checkable `MissionTypeCapabilitySource` protocol, and
   `capabilities_of()`.
2. `src/charter/offering/api.py` publishes exactly those three symbols from that module; `__all__`
   stays sorted and unique.
3. `src/charter/missions.py` re-exports the three from `charter.offering.api` (object identity),
   satisfying the strict facade-coverage gate.
4. `ResolvedMissionType` gains an additive `capabilities` property that returns
   `capabilities_of(self)`.

Success: WP01's test is green; the census/offering gate files that do not need WP03's row are
otherwise undisturbed; `uv run mypy src/charter` shows no new errors; the four built-in families
and their existing tests are untouched behaviourally.

## Context & Constraints

- Contract: `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/contracts/mission-type-capabilities-contract.md`
  (read it in full — it is the acceptance surface).
- Data model: `.../data-model.md`.
- Plan: `.../plan.md` (IC-01, IC-02, and the five design decisions).
- **C-001**: the new offering module must import nothing from `charter.activation`. Only
  `dataclasses` and `typing`.
- **C-002**: no change to capability *semantics*. Do not touch `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`,
  the thunks, `step_ids_declare_wp_iteration`, or any consumer. #6330 and #6327 own those.
- **C-004**: the seam derives from the object's own attributes; never copy the built-in table.
- Precedent to follow (read it, do not invent a shape):
  `tests/charter_offering/test_language_tokens_seam.py` and the `LANGUAGE_TOKENS` seam entry in
  `src/charter/offering/api.py` + `src/charter/languages.py`.

## Branch Strategy

- **Strategy**: Planning base and merge target are `issue-6331-mission-type-capability-offering-seam`.
- **Planning base branch**: `issue-6331-mission-type-capability-offering-seam`
- **Merge target branch**: `issue-6331-mission-type-capability-offering-seam`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Create the contract module

- **Purpose**: Define the consumer-facing contract inside the offering tier, where it can be
  lifted with the seam and cannot reach up into activation.
- **Steps**:
  1. Create `src/charter/offering/missions/capabilities.py` with a module docstring that states:
     this is the mission-type capability contract on the offering seam (#6331); the resolved
     mission type is the single producer of the values; `wp_driven` is advisory where the frozen
     DAG is authoritative (#6330); `code_producing` arrives additively (#6327).
  2. `__all__ = ["MissionTypeCapabilities", "MissionTypeCapabilitySource", "capabilities_of"]`
     (sorted).
  3. `@dataclass(frozen=True) class MissionTypeCapabilities:` with `wp_driven: bool = False` and
     `requires_substantive_spec: bool = False`, each with a short docstring comment stating its
     meaning and the conservative default.
  4. `@runtime_checkable class MissionTypeCapabilitySource(Protocol):` with the two read-only
     properties.
  5. `def capabilities_of(source: MissionTypeCapabilitySource) -> MissionTypeCapabilities:`
     returning `MissionTypeCapabilities(wp_driven=bool(source.wp_driven),
     requires_substantive_spec=bool(source.requires_substantive_spec))`. Docstring: fails loud with
     `AttributeError` on a non-conforming source; no defaulting path.
- **Files**: `src/charter/offering/missions/capabilities.py` (new)
- **Parallel?**: No — everything else depends on it.
- **Notes**: `from __future__ import annotations` first, matching the other offering modules.

### Subtask T002 – Publish on the seam manifest

- **Purpose**: Make the contract reachable through the one named public surface (FR-001).
- **Steps**:
  1. In `src/charter/offering/api.py`, add an import block in the existing style (comment naming
     the origin module and `PUBLIC` disposition) pulling the three symbols from
     `charter.offering.missions.capabilities`.
  2. Add the three names to `__all__`, keeping it sorted case-sensitively as the gate expects
     (`MissionTypeCapabilities`, `MissionTypeCapabilitySource` sort before `slug_for` and after
     `LANGUAGE_TOKENS`/`CatalogLoadResult` — verify with the gate, do not guess).
  3. Update the module docstring's disposition-provenance note only if the existing wording
     requires it; do not restate the manifest.
- **Files**: `src/charter/offering/api.py`
- **Parallel?**: No (after T001).
- **Notes**: the offering public-surface gate requires each origin module to be `PUBLIC` in the
  census — WP03 adds that row; until then run the gate expecting exactly that one failure and say
  so in your progress note. Do **not** add the row here (WP03 owns the gate file).

### Subtask T003 – Re-export through the `charter.missions` facade

- **Purpose**: Give the seam a live in-repo caller and a sanctioned runtime door (FR-005).
- **Steps**:
  1. In `src/charter/missions.py`, add
     `from charter.offering.api import (MissionTypeCapabilities, MissionTypeCapabilitySource, capabilities_of)`
     in a clearly separated block with a comment that these are the **PUBLIC** seam symbols (the
     file's existing docstring explains that everything else there is `FACADE-ONLY` — extend that
     explanation rather than contradicting it).
  2. Add the three names to `__all__`, sorted.
- **Files**: `src/charter/missions.py`
- **Parallel?**: Yes, with T004.
- **Notes**: the facade must re-export *from* `charter.offering.api` (not from the origin module)
  — the coverage gate parses `node.module == "charter.offering.api"`.

### Subtask T004 – Add the additive capability property on the DTO

- **Purpose**: Let a resolved mission type hand back the seam's value object, so the DTO is
  explicitly part of the contract without the seam knowing about the DTO (FR-004).
- **Steps**:
  1. In `src/charter/activation/mission_type_profiles.py`, import
     `MissionTypeCapabilities` / `capabilities_of` from
     `charter.offering.missions.capabilities` (activation → offering is the sanctioned
     direction).
  2. Add `@property def capabilities(self) -> MissionTypeCapabilities:` immediately **after**
     `requires_substantive_spec` (keep it away from the capability *fields* at the top of the
     dataclass — #6327 edits near those).
  3. Docstring: returns the offering-seam capability snapshot derived from this bundle's own
     `wp_driven` / `requires_substantive_spec`; derived, not decided; `wp_driven` advisory vs the
     frozen DAG.
  4. Do not add a thunk, do not memoise, do not change any existing attribute.
- **Files**: `src/charter/activation/mission_type_profiles.py`
- **Parallel?**: Yes, with T003.
- **Notes**: keep the diff to one import line + one property. Anything larger is out of scope.

## Test Strategy

- `uv run pytest tests/charter_offering/test_mission_type_capabilities_seam.py -q` (WP01's test)
- `uv run pytest tests/charter/test_resolved_mission_type_context.py tests/charter/test_mission_type_profiles.py -q`
- `uv run pytest tests/architectural/test_charter_facades_reexport_offering.py tests/architectural/test_charter_offering_public_surface.py -q`
  (expect the disposition-coupling failure until WP03 adds the census row — report it honestly,
  do not skip it)
- `uv run mypy src/charter` (no new diagnostics)

## Risks & Mitigations

- **Inverting the layer** — any `charter.activation` import in the new module fails WP01's
  layering test; keep the module dependency-free.
- **Sorted `__all__`** — the gate compares against `sorted(...)`; fix ordering, not the gate.
- **Overlap with #6327** — the only shared file is `mission_type_profiles.py`; the property is
  added beside the existing capability properties to keep hunks apart.
- **Second source of truth** — do not import `BUILTIN_REQUIRES_SUBSTANTIVE_SPEC` into offering.

## Review Guidance

- Confirm the new module imports only `dataclasses` and `typing`.
- Confirm `capabilities_of` has no defaulting path.
- Confirm the facade re-exports from `charter.offering.api` and preserves object identity.
- Confirm the DTO diff is one import + one property, and that no capability semantics moved.
- Run the seam test and the two facade/gate files yourself; confirm the red-first ordering in the
  mission history.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
