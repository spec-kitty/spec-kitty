---
work_package_id: WP01
title: Red-first proof of the seam capability contract
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-007
- FR-008
- NFR-002
- SC-001
- SC-003
planning_base_branch: issue-6331-mission-type-capability-offering-seam
merge_target_branch: issue-6331-mission-type-capability-offering-seam
branch_strategy: Planning artifacts for this mission were generated on issue-6331-mission-type-capability-offering-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6331-mission-type-capability-offering-seam unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Red
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter_offering/
create_intent:
- tests/charter_offering/test_mission_type_capabilities_seam.py
execution_mode: code_change
owned_files:
- tests/charter_offering/test_mission_type_capabilities_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6331'
---

# Work Package Prompt: WP01 – Red-first proof of the seam capability contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: claude

---

## Objectives & Success Criteria

Write `tests/charter_offering/test_mission_type_capabilities_seam.py` **before** any source
change, so the mission's red-first proof exists in history. The module pins, from the consumer's
side, the whole contract the mission adds:

- the three symbols (`MissionTypeCapabilities`, `MissionTypeCapabilitySource`, `capabilities_of`)
  are importable from `charter.offering.api` and listed in its `__all__`;
- a consumer that imports the capability surface **only** from `charter.offering.api` reads
  `wp_driven` and `requires_substantive_spec` off a resolved mission type for all four built-in
  families, the typeless bundle and a custom org-layer type;
- the runtime-checkable protocol accepts a conforming source and rejects one that lacks a
  capability (the negative control that keeps the check non-vacuous);
- the value object is frozen and compares by value;
- importing `charter.offering.missions.capabilities` in a fresh interpreter registers no
  `charter.activation*` module, with a positive control proving the detector works.

Success: the module is complete, honest, and **red** on the current tree (every capability test
fails at import/attribute resolution, not at an unrelated setup step). Record the red output.

## Context & Constraints

- Spec: `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/spec.md` (FR-001..FR-004,
  FR-007, FR-008).
- Contract: `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/contracts/mission-type-capabilities-contract.md`.
- Data model: `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/data-model.md`.
- Architectural constraint C-001: `charter.offering` must not import `charter.activation`.
  The *test* may import activation (it is a consumer), the *offering module* may not.
- The issue is #6331; siblings #6330 (contract hardening) and #6327 (`code_producing`) are out of
  scope — do not assert on `code_producing`.

## Branch Strategy

- **Strategy**: Planning base and merge target are `issue-6331-mission-type-capability-offering-seam`.
- **Planning base branch**: `issue-6331-mission-type-capability-offering-seam`
- **Merge target branch**: `issue-6331-mission-type-capability-offering-seam`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Built-in family parametrisation through the seam read

- **Purpose**: Prove US-1 acceptance scenarios 1–4 with real resolution, not a hand-built DTO.
- **Steps**:
  1. Create the test module with `pytestmark = pytest.mark.fast` and a module docstring naming
     #6331 and the seam.
  2. Import the capability surface only from `charter.offering.api`
     (`from charter.offering.api import MissionTypeCapabilities, MissionTypeCapabilitySource,
     capabilities_of`). Import `resolve_mission_type_context` separately from
     `charter.activation.mission_type_profiles` — that is the consumer's own tier and the point of
     the test is that the *contract* comes from the seam.
  3. Add a small local `_write_config(repo_root, activations)` helper writing
     `.kittify/config.yaml` with `mission_type_activations:` (same shape as the existing
     `tests/charter/test_resolved_mission_type_context.py` fixture — read it, do not copy a
     previous mission's layout).
  4. Parametrise the four built-ins with the values the contract table pins:
     `software-dev` → `(True, True)`, `research` → `(False, True)`, `documentation` →
     `(False, False)`, `plan` → `(False, False)`.
  5. Assert both `capabilities_of(bundle)` and `bundle.capabilities` return exactly those values
     and are equal to each other — the seam read derives from the DTO, it never disagrees.
- **Files**: `tests/charter_offering/test_mission_type_capabilities_seam.py`
- **Parallel?**: Yes, with T002 (same file, disjoint tests — coordinate edits).
- **Notes**: `resolve_mission_type_context(tmp_path, mission_type=...)` needs a real built-in
  pack tree; the tests run from the repo root where `packs/built-in` is synced.

### Subtask T002 – Protocol negative control and value-object semantics

- **Purpose**: Prove the protocol check is not vacuous and the snapshot is a real value object.
- **Steps**:
  1. Assert `isinstance(bundle, MissionTypeCapabilitySource)` is `True` for a resolved built-in
     bundle.
  2. Define a minimal `_OnlyWpDriven` class with `wp_driven` but no
     `requires_substantive_spec`, and assert `isinstance(..., MissionTypeCapabilitySource)` is
     `False`. Keep the class defined inside the test so `runtime_checkable`'s
     attribute-presence check is the thing under test.
  3. Assert `capabilities_of(_OnlyWpDriven())` raises `AttributeError` — a non-conforming source
     fails loud rather than defaulting to `False`.
  4. Assert `MissionTypeCapabilities()` defaults to `(False, False)`, that assignment raises
     `dataclasses.FrozenInstanceError`, and that two instances with the same fields are equal and
     hash-equal.
- **Files**: same module.
- **Parallel?**: Yes, with T001.
- **Notes**: `runtime_checkable` protocols check presence only — do not assert on wrong-typed
  attributes as if they were rejected.

### Subtask T003 – Typeless and custom-type reads, plus the layering proof

- **Purpose**: Pin the two edge cases the contract calls out, and prove the boundary instead of
  asserting it (C-001, FR-007).
- **Steps**:
  1. Typeless: `resolve_mission_type_context(tmp_path)` with no mission type yields
     `(False, False)` through `capabilities_of` and does not raise.
  2. Custom type: build the org-layer fixture (`<org>/mission_types/qa.yaml` declaring
     `requires_substantive_spec: true`, `<org>/missions/qa/mission-runtime.yaml` with
     `specify`/`implement`/`review`) and a `_StubPack`, patch
     `charter.activation.mission_type_profiles.existing_mission_types` and
     `charter.activation.pack_context.PackContext.from_config` exactly as the existing
     `tests/charter/test_resolved_mission_type_context.py::TestCapabilityFacets` does, and assert
     the seam read returns `(True, True)` (declared value wins).
  3. Layering: in a fresh subprocess
     (`subprocess.run([sys.executable, "-c", ...], capture_output=True, text=True)`), import
     `charter.offering.missions.capabilities` and print the sorted `charter.activation*` entries in
     `sys.modules`; assert the list is empty. Then run the **positive control**: the same probe
     importing `charter.activation.mission_type_profiles` and assert the list is non-empty — this
     proves the probe can see activation when it is there.
  4. Static half: assert the contract module's source contains no `charter.activation` import
     (`inspect.getsource` + a simple `"charter.activation" not in source` / AST check — prefer an
     AST walk so a docstring mention does not trip it; the module docstring will mention
     activation in prose).
- **Files**: same module.
- **Parallel?**: No — depends on T001's helpers.
- **Notes**: the subprocess probe must not rely on the parent's working directory imports beyond a
  normal `python -c` from the repo root; assert on the printed list, not on a return code alone.

## Test Strategy

- Run: `uv run pytest tests/charter_offering/test_mission_type_capabilities_seam.py -q`.
- Expected before WP02: collection/attribute failure naming the missing seam symbols. Paste that
  output into the PR's red-first evidence.
- Expected after WP02: all tests green.

## Risks & Mitigations

- **Vacuous layering test** — an in-process `sys.modules` check passes because other imports
  already loaded activation. Mitigation: fresh subprocess + positive control.
- **Fixture drift** — hand-building a `ResolvedMissionType` would let a wrong resolver pass.
  Mitigation: resolve through `resolve_mission_type_context`.
- **Over-asserting** on activation internals — keep assertions on the seam surface only.

## Review Guidance

- Confirm the module imports the capability names only from `charter.offering.api` (grep the
  imports).
- Confirm the negative control actually fails the protocol check (mutate it locally: adding the
  missing attribute makes the test fail — do not commit the mutation).
- Confirm the layering test uses a subprocess and carries the positive control.
- Confirm the red-first evidence exists in the mission history/PR.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
