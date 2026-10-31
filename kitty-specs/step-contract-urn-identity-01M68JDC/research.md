# Discovery Research — step-contract URN identity (#6741)

Mission: `step-contract-urn-identity-01M68JDC`
Branch: `issue-6741-step-contract-urn-identity`
Grounding base: `origin/main` @ `35318ef51c`

## Problem statement (confirmed on current main)

A built-in mission step contract has two identities:

| Surface | Spelling for the `documentation/accept` contract |
| --- | --- |
| DRG node (`packs/built-in/mission_step_contract.graph.yaml`) | `mission_step_contract:documentation/accept` |
| Declared id in the contract file (`id:`) | `documentation-accept` |
| Activation token (`activated_mission_step_contracts`, `charter activate`) | `documentation-accept` |
| Pre-review gate join (`specify_cli/review/gate_bindings.py::owning_contract_urn`) | `mission_step_contract:<mission>/<action>` |

Every activation surface resolves a token to `"<kind>:<declared id>"`. The DRG node tail is
`<mission>/<action>`, minted by
`charter/offering/drg/migration/extractor.py::_discover_mission_step_contract_nodes` from the
contract's `mission` + `action` fields, ignoring `id:`.

## Evidence: the reproduction (pre-fix)

Script (`filter_graph_by_activation` on the real built-in graph, `PackContext` populated with
`activated_mission_step_contracts = {"documentation-accept"}`, mission types all active):

```
activated msc: frozenset({'documentation-accept'})
identity declared_id: documentation-accept
surviving msc: [... all 21 built-in nodes ...]
HAS mission_step_contract:documentation/accept: True
HAS mission_step_contract:documentation-accept: False
```

Two distinct defects fall out of the same mismatch:

1. **Parity gap (the reported symptom).** `consistency_check._resolve_graph_kind_parity_stem`
   computes `urn = f"{kind}:{declared}"` = `mission_step_contract:documentation-accept`, which is
   never a node, so every activated step contract is reported as a `graph_kind_gaps` entry with the
   remedy *"Regenerate graph.yaml / run 'spec-kitty charter resynthesize'"*. Resynthesis cannot
   change the shipped URN, so the operator loops.
2. **Deny is inert in URN space.** `activation_ledger._spell` mints the same
   `<kind>:<declared id>` URN, so `deactivated_mission_step_contracts: [implement]` never matches the
   node `mission_step_contract:software-dev/implement`. The bare-id spelling
   (`software-dev/implement`, used by the existing tests) happens to work because it is an
   *unknown* token and falls back to `artifact_to_urn(kind, token)`.

## Decisions

### D-1: The DRG URN form stays `mission_step_contract:<mission>/<action>`

The issue offers two acceptable directions. The mission-scoped form is the one the rest of the
system is built on:

- `filter_graph_by_activation._owning_mission_type` derives the owning mission type from that shape
  to honour FR-018's "kept only when the owning mission type is active" rule.
- `gate_bindings.owning_contract_urn` resolves the pre-review gate by `(mission, action)` (the
  contract repository's `get_by_action`), so the node identity *is* the pair.
- Org-pack fragments author step-contract nodes in the same shape
  (`tests/charter/test_org_pack_chain_drg_merge.py`), and `_owning_mission_type`'s docstring names
  it the "canonical URN form".
- The shipped graph is **not** in this repository: `packs/built-in/` is git-ignored and fetched
  from the pinned `spec-kitty-open-packs` commit (`.gitignore:251`, `make sync-packs`). Changing the
  built-in URN spelling would be a cross-repo change plus a pin bump, not this fix.

### D-2: One authority answers "which DRG URN does this token name?" — the identity index

Three call sites each re-derive the URN from the declared id:

- `charter/activation/drg_activation.py::_resolve_activated_urns_for_kind`
- `charter/activation/consistency_check.py::_resolve_graph_kind_parity_stem`
- `charter/activation/activation_ledger.py::_spell`

and a fourth (`extractor._discover_mission_step_contract_nodes`) mints the node URN from the
contract's `mission`/`action` fields. The fix adds `IdentityIndex.urn(kind, token)` as the single
forward map (stem/declared-id/URN token → canonical DRG URN), with the mission-scoped rule for
`mission_step_contract` sourced from one shared helper
(`charter/offering/missions/step_contracts.py::step_contract_urn`) that the extractor also uses to
mint the node. The filter is **not** touched: it keeps comparing full URNs.

### D-3: Do not change the filter's precedence (FR-018 before FR-038)

`_node_is_activated` Step 1 (mission-type ownership) deliberately returns before Step 3 (per-id
gate) for mission-scoped step contracts. Making the per-id allow list bite for step contracts would
drop contracts such as `plan/plan` for any ledger that carries an explicit
`activated_mission_step_contracts` list (the released `default.yaml` preset writes 17 ids), and the
step executor filters its own graph through the same call — a silent execution break. Out of scope;
recorded as an explicit non-goal.

### D-4: The residual misleading remedy gets a truthful suggestion

Activating a step contract whose owning mission type is inactive still (correctly) filters the node
out, and would still print "resynthesize". The parity check therefore distinguishes
"not in the DRG at all" (regenerate) from "in the DRG but filtered out by activation" (check
`activated_mission_types` / `activated_kinds`).

## Evidence: shipped corpus

- 21 built-in step contracts under
  `packs/built-in/missions/built_in_step_contracts/*.step-contract.yaml`; every file's `id:` equals
  its filename stem (`documentation-accept`, `implement`, `plan-plan`, …), so declared ids are
  unique and stable.
- `_charter_pack_cutover_snapshots.py` pins the released `default.yaml` activation set in
  **declared-id** spelling (17 ids), independent confirmation that the activation vocabulary is the
  declared id, not `<mission>/<action>`.
- The step contracts are also reachable through `IdentityIndex` since #6527
  (`kind_vocabulary._built_in_scan_dir` → `MissionStepContractRepository.built_in_dir()`), which is
  why the symptom moved from "could not resolve" to "graph-kind gap".

## Open questions (resolved by the spec/plan)

- Q1: does `IdentityIndex.urn` need the contract file's `mission`/`action`, or can the pair be
  derived from the path? → From the file: the path carries only the id. Read lazily, cached per
  path, only for step-contract tokens.
- Q2: what does the drift gate assert so it cannot be green for the wrong reason? → Two directions
  over the shipped built-in graph plus a planted-divergence non-vacuity arm; see plan.
- Q3: is `resolve_artifact_urn` (kind_vocabulary) also a producer of the wrong URN for step
  contracts? → It is a *different* seam (used by the tension scan and `deactivate`); the identity
  index is the one the activation filter and parity check consume. Left unchanged, noted in the
  plan's risks.
