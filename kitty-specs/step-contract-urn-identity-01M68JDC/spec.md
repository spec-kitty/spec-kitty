# Mission Specification: Step-contract URN identity

**Mission Branch**: `issue-6741-step-contract-urn-identity`
**Created**: 2026-10-31
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6741 — "Built-in mission-step-contract DRG URNs do not match their declared ids, so the activation graph filter never keeps them"; discovery recorded in `<mission_dir>/research.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An activated step contract is visible to the activation filter (Priority: P1)

An operator activates one built-in mission step contract (`spec-kitty charter activate
mission-step-contract documentation-accept`, which writes the declared id
`documentation-accept` to the activation ledger). The activation surfaces — the DRG activation
filter, the config↔graph parity check, and deny resolution — must agree with the DRG node the
doctrine pack ships (`mission_step_contract:documentation/accept`). Today they do not: the token
resolves to `mission_step_contract:documentation-accept`, which is not a node, so
`charter consistency-check` reports the artifact as a graph-kind gap and prescribes a resynthesis
that cannot change anything.

**Why this priority**: This is the reported defect and the silent single-authority break it
exposes. Without it, an operator who follows the CLI's own remedy loops forever, and a governance
surface (activation) reports a false state.

**Independent Test**: Populate a `PackContext` whose only activated step contract is
`documentation-accept`, run the activation filter and the config↔graph parity check over the real
built-in DRG, and assert the node survives and no gap is reported. Fails on the pre-fix tree.

**Acceptance Scenarios**:

1. **Given** the shipped built-in DRG and a ledger activating `documentation-accept`, **When** the
   activation filter runs, **Then** `mission_step_contract:documentation/accept` is in the surviving
   URN set and the parity check records no gap for that token.
2. **Given** the same ledger, **When** `charter consistency-check` runs, **Then** the report is
   coherent for step-contract identity (no `graph_kind_gaps` entry naming the token).

---

### User Story 2 - One authority answers "which DRG URN does this token name?" (Priority: P1)

A maintainer changes how an artifact kind's DRG URN is spelled, or renames a declared id. The
activation layer must not re-derive URNs from declared ids in three separate modules; it must ask
the one identity authority, so the drift can only be introduced in one place — and a gate must
catch it there.

**Why this priority**: The bug exists because four sites independently minted the same identity
(`_resolve_activated_urns_for_kind`, `_resolve_graph_kind_parity_stem`, `activation_ledger._spell`,
and the DRG extractor). Fixing only the symptom would leave the same class open.

**Independent Test**: Ask the identity index for the URN of a step-contract token given by stem, by
declared id and by `<kind>:`-prefixed token; all three must return the DRG node URN. Then plant a
node whose URN tail disagrees with the declared identity and confirm the drift gate fails.

**Acceptance Scenarios**:

1. **Given** a built-in step contract, **When** its URN is requested by stem (`documentation-accept`)
   or by declared id, **Then** the answer is `mission_step_contract:documentation/accept`.
2. **Given** a DRG node whose URN tail names no declared identity, **When** the drift gate runs,
   **Then** it fails and names the node.

---

### User Story 3 - Deny and the parity remedy tell the truth (Priority: P2)

An operator deactivates a step contract by its declared id, or activates one whose owning mission
type is inactive. The deny must remove the node from the activation-filtered graph, and the parity
check must not blame a missing regeneration for an artifact that exists but was filtered out.

**Why this priority**: Both are the same identity mismatch on adjacent surfaces; both mislead an
operator about what is wrong. Lower than P1 because they are consequences, not the reported symptom.

**Independent Test**: (a) Deny `implement` by declared id and assert the
`mission_step_contract:software-dev/implement` node is gone from the filtered graph — inert before
the fix. (b) Activate `documentation-accept` with the `documentation` mission type inactive and
assert the suggestion names the mission-type activation, not a resynthesis.

**Acceptance Scenarios**:

1. **Given** a ledger denying step contract `implement`, **When** the activation filter runs,
   **Then** `mission_step_contract:software-dev/implement` does not survive.
2. **Given** an activated step contract whose owning mission type is inactive, **When** consistency
   is checked, **Then** the gap remains reported but the suggestion points at mission-type
   activation, not at regenerating the graph.

---

### Edge Cases

- A step-contract file that cannot be read for its `mission`/`action` fields: the URN resolution
  returns "unknown" rather than inventing a URN; the gate never raises (it is consumed by a
  fail-closed-**report** caller).
- A token spelled as a `<kind>:` URN (`mission_step_contract:documentation-accept`): resolves like
  its bare declared id; the mission-scoped spelling (`documentation/accept`) stays an *unknown*
  token that keeps itself (existing behaviour for the deny path).
- An org-pack step-contract node authored in the mission-scoped shape: unaffected — the ownership
  rule still reads it from the URN, and the per-id gate keeps its existing precedence.
- A project overlay step contract with the same declared id as a built-in one: layer precedence is
  unchanged (the index already resolves first-match across layers).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Identity authority answers the URN | As a charter maintainer, I want the identity index to be the one place that maps an activation token to its DRG URN, so that no consumer re-derives identity from a declared id. | High | Open | [build] | no — the mapping does not exist today |
| FR-002 | Step-contract URN rule stated once | As a maintainer, I want the `<mission>/<action>` rule for step-contract URNs to exist in exactly one function used by both the graph minter and the identity lookup, so that the two cannot diverge. | High | Open | [build] | no — two independent implementations today |
| FR-003 | Parity resolves through the authority | As an operator, I want the config↔graph parity check to resolve each activated token's URN through the identity authority, so that an activated step contract is not reported as a graph gap. | High | Open | [build] | no |
| FR-004 | Filter resolves through the authority | As an operator, I want the activation filter's per-kind token resolution to use the same authority, so that the per-id gate compares full URNs that actually exist in the graph. | High | Open | [build] | no |
| FR-005 | Deny in URN space | As an operator, I want deactivating a step contract by its declared id to remove that contract's node from the activation-filtered graph. | Medium | Open | [build] | no — inert before the fix |
| FR-006 | Truthful remedy | As an operator, I want the parity suggestion to distinguish "this artifact is not in the DRG" from "activation filtered it out", so that following the remedy is not a loop. | Medium | Open | [build] | no |
| FR-007 | Drift gate | As a maintainer, I want an architectural gate that fails when a built-in DRG node's URN and the declared identity of the artifact it names disagree, so that this class cannot return silently. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No per-node I/O on the gate | Resolving activation tokens stays O(kinds × tokens), never O(nodes): at most one cached file read per distinct activated step-contract token per index instance, and no new filesystem access on the default (no activated step contract) path. | Performance | High | Open |
| NFR-002 | Surviving set unchanged for the default ledger | For this repository's own activation ledger (no explicit `activated_mission_step_contracts`), the activation-filtered DRG node URN set is byte-identical before and after the change; no kind other than `mission_step_contract` changes its resolution result. | Reliability | High | Open |
| NFR-003 | The gate never raises | An unknown or unresolvable token is skipped by the filter and reported by the existing unknown-reference check; the activation filter and parity check keep their fail-closed-by-report contract (no exception escapes). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No shipped-pack edit | `packs/built-in/` is git-ignored and fetched from the pinned `spec-kitty-open-packs` commit, so the fix lives in the identity/activation layer and does not change the shipped DRG URN spelling. | Technical | High | Open |
| C-002 | Public gate signature stable | `filter_graph_by_activation(graph, pack_context, *, identity=None)` and the precedence of the mission-type ownership rule over the per-id gate are unchanged. | Technical | High | Open |
| C-003 | Layer discipline | The fix respects `kernel <- charter <- specify_cli`: `charter` imports neither `specify_cli` nor a runtime module. | Technical | High | Open |

### Key Entities

- **Activation token**: the spelling an operator writes into the activation ledger — a config stem, a
  declared id, or a `<kind>:`-prefixed token.
- **Declared id**: the `id:` field of an artifact file; the canonical identity of that artifact and
  the tail of its DRG URN for every kind except mission step contracts.
- **DRG URN**: `"<kind>:<tail>"` node identity in the Doctrine Reference Graph. For a mission step
  contract the tail is `<mission>/<action>`, derived from the contract's `mission` and `action`
  fields, because the activation filter's ownership rule and the pre-review gate join both key on
  that pair.
- **Mission step contract**: a `*.step-contract.yaml` artifact declaring `id`, `mission`, `action`
  and `steps`; shipped built-in under `packs/built-in/missions/built_in_step_contracts/`, overlaid
  per project under `.kittify/charter-packs/mission_step_contracts/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 21 shipped built-in `mission_step_contract` DRG nodes resolve to a declared identity through the identity authority (today: 0 of 21). — [build] · no-op passable: no
- **SC-002**: Zero `graph_kind_gaps` entries for an activated step contract whose owning mission type is active, measured through `charter consistency-check`'s parity check. — [build] · no-op passable: no
- **SC-003**: The drift gate fails on a planted URN/declared-id mismatch and passes on the shipped graph — red-first evidence that it is not vacuous. — [ratchet] · no-op passable: no
- **SC-004**: A denied step contract (by declared id) is absent from the activation-filtered graph, and every other kind's filtered set is unchanged on the same fixture. — [build] · no-op passable: no
