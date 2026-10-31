# Data Model — Step-contract URN identity (#6741)

Three identity objects and one invariant. No persisted schema changes.

## Identity objects

### Activation token

The spelling an operator writes into `.kittify/charter/activation.yaml`
(`activated_<plural>` / `deactivated_<plural>`).

| Form | Example | Resolution |
| --- | --- | --- |
| config stem | `documentation-accept` | `IdentityIndex` stem lookup |
| declared id | `documentation-accept` (same here; `DIRECTIVE_001` differs) | `IdentityIndex` id lookup |
| `<kind>:`-prefixed | `procedure:PROC_CANVAS_REVIEW` | prefix stripped, then as above |
| mission-scoped step spelling | `software-dev/implement` | not a known token for the index; keeps itself (deny path) |

### Declared identity

The `id:` field of an artifact file. Canonical for every activatable kind. For a mission step
contract it is flat: `documentation-accept`, `implement`, `plan-plan`.

### DRG URN

`"<kind>:<tail>"`. The tail rule per kind:

| Kind | URN tail | Source of the tail |
| --- | --- | --- |
| every activatable kind except `mission_step_contract` | the declared id | the artifact's `id:` field |
| `mission_step_contract` | `<mission>/<action>` | the contract's `mission` + `action` fields |

Why the exception: the filter's ownership rule (`_owning_mission_type`) and the pre-review gate join
(`gate_bindings`) both key on the `(mission, action)` pair, and org-pack fragments already author
step-contract nodes in that shape. The *rule* is stated once
(`charter.offering.missions.step_contracts.step_contract_urn`) and both the DRG minter and the
identity lookup use it.

## Invariant (the thing the drift gate pins)

> For every node in the shipped built-in DRG whose kind is a charter-activatable `ArtifactKind`,
> `IdentityIndex.urn(kind, urn_tail) == node.urn`, and the tail names an artifact that exists.

Two directions, both required:

1. **No orphan node** — every activatable-kind node in the shipped graph resolves to a declared
   artifact (catches URNs minted from the wrong field, or a renamed `id` whose graph was not
   regenerated).
2. **No missing node** — every shipped step contract has a node (catches a contract added upstream
   whose graph fragment lags).

## State and flow

```
activation ledger token
        │  IdentityIndex.urn(kind, token)          ← the one authority
        ▼
canonical DRG URN ──────┬──► filter_graph_by_activation  (per-id gate: full-URN membership)
                        ├──► consistency_check parity     (gap reported only if the node is absent)
                        ├──► DenySet.urns                 (deny matches the node's URN)
                        └──► gate_bindings join           (activated set ∋ owning contract URN)
```

## Failure modes and their representation

| Failure | Representation | Behaviour |
| --- | --- | --- |
| token unknown to the index | `IdentityIndex.urn` → `None` | caller skips it; `_check_unknown_references` reports it once (never raises) |
| step-contract file unreadable for `mission`/`action` | `IdentityIndex.urn` → `None` | same as unknown; the artifact's own repository rejects the file at load |
| token resolves, node absent from the DRG | parity gap, suggestion = regenerate/resynthesize | unchanged wording |
| token resolves, node present but activation-filtered out | parity gap, suggestion names the activation keys | new wording (#6741) |
