# Contract: token → DRG URN identity

**Owner**: `charter.activation.identity_index.IdentityIndex` (lookup) and
`charter.offering.missions.step_contracts.step_contract_urn` (the one step-contract URN rule)
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-003, C-002

## Obligation

Every consumer that needs the DRG URN an activation token names asks
`IdentityIndex.urn(kind, token)`. Nothing re-derives `"<kind>:<declared id>"` locally.

```python
def urn(self, kind: ArtifactKind, token: str) -> str | None:
    """Canonical DRG URN *token* names for *kind*; ``None`` when the index does not know it."""
```

## Behavioural cases

| Case | Token | Expected `urn` |
| --- | --- | --- |
| ordinary kind, stem | `001-architectural-integrity-standard` | `directive:DIRECTIVE_001` |
| ordinary kind, declared id | `DIRECTIVE_001` | `directive:DIRECTIVE_001` |
| step contract, stem | `documentation-accept` | `mission_step_contract:documentation/accept` |
| step contract, declared id | `documentation-accept` (project overlay, same id) | the mission-scoped URN of *that* file |
| `<kind>:`-prefixed token | `tactic:qa-seven` | `tactic:qa-seven` (prefix stripped, then resolved) |
| unknown token | `no-such-artifact` | `None` |

## Consumer obligations

1. `drg_activation._resolve_activated_urns_for_kind` builds its URN set from `identity.urn`; an
   unknown token is skipped, never raised (the gate is consumed by a fail-closed-**report** caller).
2. `consistency_check._resolve_graph_kind_parity_stem` compares `identity.urn(kind, token)` to the
   surviving node set. Two distinct suggestions:
   - node absent from the **unfiltered** graph → the existing "Regenerate graph.yaml / run
     `spec-kitty charter resynthesize`" wording (unchanged);
   - node present but filtered out → name the activation keys that can filter an artifact
     (`activated_kinds`, and `activated_mission_types` for a step contract).
3. `activation_ledger._spell` mints the `DenySet` URN through `identity.urn`; the unknown-token arm
   keeps `artifact_to_urn(kind, token)` so a mission-scoped deny spelling still works.
   `IdentityLookup` therefore gains `urn` next to `declared_id` / `stem`.
4. `specify_cli.review.gate_bindings.owning_contract_urn` delegates to `step_contract_urn`, so the
   gate join's URN and the graph's URN come from the same function.
5. `filter_graph_by_activation`'s signature and node-visit order are **unchanged**: ownership is
   still checked before the per-id gate (C-002).

## What this contract does NOT change

- The shipped `packs/built-in/mission_step_contract.graph.yaml` URN spelling (C-001: the tree is
  fetched from the pinned open-packs commit).
- The per-id gate's precedence relative to the mission-type ownership rule (C-002).
- `kind_vocabulary.resolve_artifact_urn` / `resolve_config_id`: a different seam (tension scan,
  `deactivate`), and a different question ("which artifact owns this stem/URN"), left untouched and
  recorded as a known non-overlap in the PR body.
