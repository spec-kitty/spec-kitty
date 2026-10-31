# Work Packages: Step-contract URN identity (#6741)

**Inputs**: Design documents from `kitty-specs/step-contract-urn-identity-01M68JDC/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/urn-identity-contract.md, quickstart.md

**Tests**: Required — this is a defect fix under ATDD-first discipline (`DIRECTIVE_034`). Every
behaviour change ships with a test written before the fix, through the pre-existing entry point.

**Organization**: Three work packages matching the plan's Implementation Concern Map. Subtasks are
reference rows; completion is recorded with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`.

---

## Work Package WP01: The one URN authority (Priority: P0)

**Goal**: State the step-contract URN rule once and expose one token → DRG URN mapping
(`IdentityIndex.urn`), used by the DRG minter and available to every activation consumer.
**Independent Test**: `IdentityIndex.urn(ArtifactKind.MISSION_STEP_CONTRACT, "documentation-accept")`
returns `mission_step_contract:documentation/accept`, and the extractor mints the same URN from the
contract file.
**Prompt**: `tasks/WP01-urn-authority.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, C-001, C-003

### Included Subtasks

T001 [P] Add `step_contract_urn(mission, action)` to `src/charter/offering/missions/step_contracts.py`
T002 [P] Re-export `step_contract_urn` through the `src/charter/mission_steps.py` facade
T003 Mint built-in step-contract DRG nodes through `step_contract_urn` in `src/charter/offering/drg/migration/extractor.py`, keeping both authoring-collision guards
T004 Add `IdentityIndex.urn(kind, token)` to `src/charter/activation/identity_index.py` with a lazy, cached `mission`/`action` read for step contracts
T005 Tests for `step_contract_urn` and `IdentityIndex.urn` (stem, declared id, `<kind>:` token, unknown token, layer precedence) in `tests/charter/activation/test_identity_index_urn.py`

### Implementation Notes

- T005 is written first (red where it can be red: `IdentityIndex.urn` does not exist yet).
- The URN tail rule must remain `<mission>/<action>`; only its implementation location changes.
- `IdentityIndex.urn` returns `None` for an unknown token or an unreadable contract file; it never
  raises (NFR-003).
- One cached read per distinct step-contract path per index instance (NFR-001): no per-node I/O.

### Parallel Opportunities

T001/T002 and T004 are independent files; T003 depends on T001.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Import cycle `charter.offering.drg.migration` → `charter.offering.missions.step_contracts`: the
  extractor already imports three siblings from `charter.offering.missions`; verify with an import
  smoke check and `tests/architectural/test_layer_rules.py`.
- Accidental behaviour change in the extractor: the shipped graph is regenerated in-memory in the
  WP03 gate and must stay byte-identical apart from nothing at all (the URN spelling does not
  change).

---

## Work Package WP02: Consumers re-pointed, remedy made truthful (Priority: P0)

**Goal**: The activation filter, the config↔graph parity check, deny resolution and the pre-review
gate join all ask the authority for the URN instead of re-deriving it; the parity suggestion stops
prescribing a resynthesis for an artifact that exists but was activation-filtered.
**Independent Test**: With `documentation-accept` the only activated step contract,
`filter_graph_by_activation` keeps the `mission_step_contract:documentation/accept` node, the parity
check reports no gap for it, and denying `implement` by declared id removes
`mission_step_contract:software-dev/implement`.
**Prompt**: `tasks/WP02-consumers-and-remedy.md`
**Requirement Refs**: FR-003, FR-004, FR-005, FR-006, NFR-002, NFR-003, C-002

### Included Subtasks

T006 Red-first regression tests in `tests/charter/activation/test_step_contract_urn_identity.py` (parity coherence, filter survival, deny by declared id, truthful suggestion for a filtered node)
T007 Re-point `_resolve_activated_urns_for_kind` in `src/charter/activation/drg_activation.py` at `identity.urn`
T008 Re-point `_resolve_graph_kind_parity_stem` in `src/charter/activation/consistency_check.py` at `identity.urn` and split the suggestion by "absent from the DRG" vs "filtered out by activation"
T009 Re-point `_spell` in `src/charter/activation/activation_ledger.py` at `identity.urn`, extend the `IdentityLookup` protocol, and update the test double in `tests/charter/activation/test_deny_identity_space.py`
T010 Delegate `owning_contract_urn` in `src/specify_cli/review/gate_bindings.py` to `step_contract_urn`

### Implementation Notes

- T006 must fail on the WP01 head (red) and pass after T007–T010.
- Do not touch `_node_is_activated`'s decision tree: ownership still precedes the per-id gate
  (C-002). Only the *source of the URN set* changes.
- Keep the existing "Regenerate graph.yaml / run `spec-kitty charter resynthesize`" wording
  byte-identical for the absent-node arm; existing tests assert it.
- `IdentityLookup` gains `urn`; every implementation (the index and the test double) must provide it.

### Parallel Opportunities

T007, T008, T009 and T010 are four independent files once T006 is written.

### Dependencies

- Depends on WP01 (`IdentityIndex.urn`, `step_contract_urn`).

### Risks & Mitigations

- A silent behaviour change for non-step-contract kinds: `identity.urn` returns exactly
  `"<kind>:<declared id>"` for them; add an explicit assertion per kind in the WP02 test file.
- The filter is called on hot paths → NFR-001: no extra per-node work, and the resolved map is still
  built once per call.

---

## Work Package WP03: Gates, docs and evidence (Priority: P1)

**Goal**: Leave a gate that fails if the shipped DRG URN and the declared identity drift again,
prove it is not vacuous, and document the step-contract URN rule where operators read it.
**Independent Test**: `pytest tests/architectural/test_drg_urn_identity_parity.py` fails on a
planted mismatch and passes on the shipped graph; the changelog entry exists; the architecture doc
states the tail rule.
**Prompt**: `tasks/WP03-drift-gate-and-docs.md`
**Requirement Refs**: FR-007, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T011 [P] Architectural drift gate over the shipped built-in DRG in `tests/architectural/test_drg_urn_identity_parity.py` (both directions: no orphan node, no missing node)
T012 [P] Non-vacuity arm for that gate: a planted divergent node must be reported
T013 [P] Document the step-contract URN tail rule in `docs/architecture/doctrine-kinds.md`
T014 [P] `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead with `(#6741)`, before/after, under 1,200 characters)
T015 Verification sweep: targeted pytest files, `make test-fast`, `ruff`, `mypy` on touched modules, `python -m scripts.docs.check_docs_freshness --ci`

### Implementation Notes

- The gate reads the **built-in** graph only (`packs/built-in/*.graph.yaml`), so it is deterministic
  and independent of this repository's org pack.
- Non-vacuity is mandatory (`architectural-gate-non-vacuity`): same checker function, planted input.
- T015 records the exact commands and their results for the PR body's `## Tests run` section.

### Parallel Opportunities

T011–T014 are independent files; T015 runs last.

### Dependencies

- Depends on WP01 and WP02 (the gate must observe the fixed authority).

### Risks & Mitigations

- A gate that silently skips kinds: assert a non-zero count of checked nodes per kind so an empty
  scan cannot pass.
- Docs churn outside this diff: only the one architecture section and one changelog entry.
