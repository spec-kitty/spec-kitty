---
work_package_id: WP01
title: The one URN authority
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- C-001
- C-003
planning_base_branch: issue-6741-step-contract-urn-identity
merge_target_branch: issue-6741-step-contract-urn-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6741-step-contract-urn-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6741-step-contract-urn-identity unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Identity authority
history:
- at: '2026-10-31T08:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: src/charter/offering/missions/
create_intent:
- tests/charter/activation/test_identity_index_urn.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/missions/step_contracts.py
- src/charter/mission_steps.py
- src/charter/offering/drg/migration/extractor.py
- src/charter/activation/identity_index.py
- tests/charter/activation/test_identity_index_urn.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The one URN authority

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of this
prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: *(the harness running this WP)*

## ⚠️ IMPORTANT: Review Feedback

Read the `review_ref` field in the status event log (`spec-kitty agent tasks status`) before
starting. Address every feedback item before marking the WP done.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- `charter.offering.missions.step_contracts.step_contract_urn(mission, action)` is the single place
  that spells a mission step contract's DRG URN tail (`<mission>/<action>`).
- The DRG extractor mints built-in step-contract nodes through that function, so the minting rule has
  one implementation.
- `IdentityIndex.urn(kind, token)` is the single forward map from an activation token (config stem,
  declared id, or `<kind>:`-prefixed token) to its canonical DRG URN.
- The shipped graph's step-contract URNs are unchanged (this WP changes *where* the rule lives, not
  what it produces).
- NFR-001 holds: resolution adds no per-node I/O and at most one cached file read per distinct
  step-contract token per index instance.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6741. Discovery + decisions: `kitty-specs/step-contract-urn-identity-01M68JDC/research.md`.
  Contract: `kitty-specs/step-contract-urn-identity-01M68JDC/contracts/urn-identity-contract.md`.
- Why the URN tail is `<mission>/<action>` rather than the declared id: `filter_graph_by_activation`'s
  mission-type ownership rule (`_owning_mission_type`) and `gate_bindings.owning_contract_urn` both
  key on that pair, and org-pack fragments already author step-contract nodes in that shape. The
  shipped DRG itself (`packs/built-in/`) is fetched from the pinned `spec-kitty-open-packs` commit
  and is **git-ignored** — do not edit it (C-001).
- Layer discipline: `kernel <- charter <- specify_cli`. The extractor
  (`charter.offering.drg.migration`) may import `charter.offering.missions.step_contracts` — it
  already imports `charter.offering.missions.repository`, `mission_step_repository` and
  `step_projection`.
- Do not add a runtime dependency; `ruamel.yaml` and pydantic are already in both import graphs.

## Branch Strategy

- **Strategy**: `{{branch_strategy}}`
- **Planning base branch**: `issue-6741-step-contract-urn-identity`
- **Merge target branch**: `issue-6741-step-contract-urn-identity`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Execution worktrees are
> allocated per computed lane from `lanes.json`; never hand-build a workspace path.

## Subtasks & Detailed Guidance

### Subtask T005 – Tests first (write this before T001–T004)

- **Purpose**: Pin the behaviour this WP introduces, red first.
- **Steps**: Create `tests/charter/activation/test_identity_index_urn.py` with `pytest.mark.fast`
  and `pytest.mark.doctrine` markers. Cases:
  1. `step_contract_urn("documentation", "accept") == "mission_step_contract:documentation/accept"`.
  2. `IdentityIndex.build(repo_root).urn(ArtifactKind.MISSION_STEP_CONTRACT, "documentation-accept")`
     (stem) and `...("documentation-accept")` given as a declared id both return the mission-scoped
     URN — use a real built-in contract, not a fixture.
  3. `IdentityIndex.urn(ArtifactKind.DIRECTIVE, "DIRECTIVE_001")` and the stem
     `001-architectural-integrity-standard` both return `directive:DIRECTIVE_001` (proves ordinary
     kinds are untouched).
  4. A `<kind>:`-prefixed token (`procedure:PROC_CANVAS_REVIEW` if present, else another real id)
     resolves like its bare id.
  5. An unknown token returns `None` (never raises).
  6. Layer precedence: a project-overlay step contract with the same stem as a built-in one wins,
     and its own `mission`/`action` decide the URN (build a temp project layer with
     `project_pack_root()`; use the existing helpers in `tests/charter/activation/` as a pattern).
- **Files**: `tests/charter/activation/test_identity_index_urn.py` (new).
- **Parallel?**: No — it defines the API the other subtasks implement.
- **Notes**: Run it before implementing and record the failure output (it will be
  `AttributeError: 'IdentityIndex' object has no attribute 'urn'`); that is the red evidence for the
  PR body's `## Tests run` section.

### Subtask T001 – `step_contract_urn` in the offering layer

- **Purpose**: One implementation of the step-contract URN spelling.
- **Steps**: In `src/charter/offering/missions/step_contracts.py` add:

  ```python
  def step_contract_urn(mission: str, action: str) -> str:
      """Canonical DRG URN of the step contract for ``(mission, action)``.

      ``mission_step_contract:<mission>/<action>`` -- the tail is the owning pair, not the
      declared id, because the activation filter's ownership rule and the pre-review gate join
      both key on it (see #6741).
      """
      return f"{ArtifactKind.MISSION_STEP_CONTRACT.value}:{mission}/{action}"
  ```

  Add it to `__all__`.
- **Files**: `src/charter/offering/missions/step_contracts.py`.
- **Parallel?**: Yes, with T004.
- **Notes**: Keep the docstring honest about *why* it differs from the declared-id rule; add a
  cross-reference to `IdentityIndex.urn`.

### Subtask T002 – Facade re-export

- **Purpose**: Let `specify_cli` reach the helper without importing `charter.offering` directly
  (ADR 2026-03-27-1; `specify_cli/review/gate_bindings.py` already imports `charter.mission_steps`).
- **Steps**: Add `step_contract_urn` to the import block and `__all__` in
  `src/charter/mission_steps.py`, keeping it a pure re-export (`X as X` form, no wrapper).
- **Files**: `src/charter/mission_steps.py`.
- **Parallel?**: Yes.
- **Notes**: The module docstring says "pure re-export module — no behaviour, no wrappers"; keep it
  that way.

### Subtask T003 – The extractor mints through the rule

- **Purpose**: Remove the second implementation of the spelling.
- **Steps**: In `_discover_mission_step_contract_nodes`
  (`src/charter/offering/drg/migration/extractor.py`), replace
  `artifact_to_urn("mission_step_contract", f"{mission}/{action}")` with
  `step_contract_urn(mission, action)`. Keep **both** guards: the duplicate-URN guard loses its
  ability to spot a duplicate `(mission, action)` with different ids, so keep an explicit
  `seen_pairs` guard raising `ValueError` (same message shape as today) and add the declared-id
  guard: two contracts declaring the same `id` in the same built-in directory are also an authoring
  collision. Update the docstring: the node is minted from `mission` + `action` through the shared
  rule.
- **Files**: `src/charter/offering/drg/migration/extractor.py`.
- **Parallel?**: No — needs T001.
- **Notes**: Existing tests
  (`tests/charter_offering/drg/migration/test_extractor_projection.py`) assert duplicate
  `(mission, action)` raises; keep them green. Verify the regenerated graph in-memory equals the
  shipped fragment (`mission_step_contract.graph.yaml`) via the WP03 gate.

### Subtask T004 – `IdentityIndex.urn`

- **Purpose**: The forward map the activation consumers will call instead of re-deriving
  `"<kind>:<declared id>"`.
- **Steps**: In `src/charter/activation/identity_index.py`:

  ```python
  def urn(self, kind: ArtifactKind, token: str) -> str | None:
      """Canonical DRG URN *token* names for *kind*; ``None`` when the index does not know it."""
  ```

  - Resolve the entry with the existing `_lookup` (stem first, then declared id, `_bare` strips a
    `<kind>:` prefix).
  - For `ArtifactKind.MISSION_STEP_CONTRACT`, return `step_contract_urn(mission, action)` read from
    the entry's file (`mission` + `action` keys), cached per `Path` in a private dict
    (`_step_contract_pairs`), one read per file per index instance. A missing/unreadable/malformed
    file, or a missing field, returns `None` — never raise (NFR-003).
  - Every other kind returns `f"{kind.value}:{entry.declared_id}"`.
  - Update the module docstring's "lookups" list to name `urn` as the canonical-URN authority.
- **Files**: `src/charter/activation/identity_index.py`.
- **Parallel?**: Yes, with T001/T002.
- **Notes**: Read the two fields with `ruamel.yaml` (`YAML(typ="safe")`) rather than the pydantic
  contract model — the index stays a light, read-only scanner. Do **not** call it from per-node
  loops: callers resolve once per kind/token set (NFR-001).

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_identity_index_urn.py -q
uv run pytest tests/charter_offering/drg/migration/test_extractor_projection.py -q
uv run ruff check src/charter/offering/missions/step_contracts.py src/charter/mission_steps.py \
  src/charter/offering/drg/migration/extractor.py src/charter/activation/identity_index.py
uv run mypy src/charter/activation/identity_index.py src/charter/offering/missions/step_contracts.py
```

`mypy` config lives in `pyproject.toml`; match what CI runs for the `charter` package.

## Risks & Mitigations

- **Import cycle** between `charter.offering.drg.migration.extractor` and
  `charter.offering.missions.step_contracts`: the latter imports only `charter.offering.base`,
  `charter.offering.artifact_kinds` and pydantic. Verify with
  `uv run pytest tests/architectural/test_layer_rules.py -q`.
- **Perf regression** (`NFR-001`): the pair cache is per index instance and keyed by path; a call
  with no activated step contract reads nothing.
- **A silent URN change**: T003 must produce exactly the URNs already in
  `packs/built-in/mission_step_contract.graph.yaml`; the WP03 gate proves it.

## Review Guidance

- Confirm `IdentityIndex.urn` never raises and returns `None` on unknown input.
- Confirm the extractor keeps a duplicate `(mission, action)` guard.
- Confirm no other kind's URN spelling moved.
- Confirm the facade stayed a pure re-export.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
