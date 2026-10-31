# Implementation Plan: Step-contract URN identity (#6741)

**Branch**: `issue-6741-step-contract-urn-identity` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/step-contract-urn-identity-01M68JDC/spec.md`
**Input**: GitHub issue spec-kitty/spec-kitty#6741; discovery in `<mission_dir>/research.md`

## Summary

A built-in mission step contract has two identities: the DRG node the doctrine pack ships
(`mission_step_contract:documentation/accept`) and the declared id every activation surface uses
(`documentation-accept`). Four modules independently mint a URN from the declared id
(`"<kind>:<declared id>"`), which for this one kind is not a node, so the activation filter, the
config↔graph parity check and deny resolution all disagree with the shipped graph.

The fix makes **one authority** answer "which DRG URN does this activation token name?" —
`IdentityIndex.urn(kind, token)` — with the mission-scoped rule for step contracts stated once
(`charter.offering.missions.step_contracts.step_contract_urn`, also used by the DRG minter). The
four consumers delegate to it. The activation filter's own logic is untouched: it still compares
full URNs, and the mission-type ownership rule keeps its precedence over the per-id gate (C-002).
An architectural gate then fails if a built-in DRG node URN and the declared identity of the
artifact it names ever disagree again.

## Technical Context

**Language/Version**: Python 3.11 (`uv run`, `uv sync --frozen --all-extras`)
**Primary Dependencies**: pydantic (contract models), ruamel.yaml (identity/activation reads) — all
already in the graph; no new dependency
**Storage**: files on disk — `*.step-contract.yaml` contracts, the fetched `packs/built-in/` DRG
fragments, `.kittify/charter/activation.yaml`
**Testing**: pytest (`-m fast` / targeted files), ruff, mypy (strict on touched modules), diff-cover
≥ 90 % on changed lines, `scripts.docs.check_docs_freshness`
**Target Platform**: CLI/library, no platform-specific surface
**Project Type**: single project (`src/` + `tests/`)
**Performance Goals**: no per-node I/O on the activation gate — resolution stays O(kinds × tokens);
at most one cached file read per distinct activated step-contract token per index instance
(NFR-001)
**Constraints**: `packs/built-in/` is fetched from the pinned `spec-kitty-open-packs` commit and is
git-ignored — the fix must not touch it (C-001); `filter_graph_by_activation`'s signature and
precedence are frozen (C-002); `kernel <- charter <- specify_cli` (C-003)
**Scale/Scope**: 4 source modules + 1 offering helper + facade re-export; ~8 test files; 1
architectural gate; changelog + one architecture-doc paragraph

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan honours it |
| --- | --- |
| Single canonical authority (Governing Principles) | The whole point: one function states the step-contract URN rule, one method maps token → URN; four duplicated constructions collapse onto them. |
| `DIRECTIVE_001` Architectural Integrity | Change stays inside the existing `charter.activation` + `charter.offering.missions` seams; no new module, no boundary crossed. |
| `DIRECTIVE_024` Locality of Change / `change-apply-smallest-viable-diff` | No shipped-doctrine edit, no filter rewrite, no graph regeneration; two existing call sites re-pointed, one method added. |
| `DIRECTIVE_030` Test and typecheck quality gate + diff-cover ≥ 90 % | Every changed line is covered by the red-first regression tests and the new gate. |
| `DIRECTIVE_034` Test-first bug-fixing (ATDD-first) | Red-first: each of the three behaviour changes gets a failing test through the pre-existing entry point before the fix. |
| `DIRECTIVE_040` Recurring-bug structural intervention | The drift gate is the structural intervention, not a one-off patch: it fails on a planted mismatch. |
| `DIRECTIVE_043` Close defect class by construction | Deny in URN space and the truthful remedy are fixed as the same class, not deferred. |
| `DIRECTIVE_044` Canonical sources and unification | The three `<kind>:<declared id>` sites were a duplicated authority; they now delegate. |
| `NFR-001` of the ledger contract (fail-closed by report) | The gate never raises on an unknown token; the parity check keeps its record-and-suggest shape. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Targeted files + `make test-fast` only. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/step-contract-urn-identity-01M68JDC/
├── plan.md              # this file
├── research.md          # discovery + Phase 0 decisions
├── data-model.md        # Phase 1: identity objects and their invariants
├── quickstart.md        # Phase 1: how to verify by hand
├── contracts/
│   └── urn-identity-contract.md
└── tasks/               # finalize-tasks output
```

### Source Code (repository root)

```
src/charter/offering/missions/step_contracts.py   # + step_contract_urn(mission, action)
src/charter/mission_steps.py                      # re-export the new helper (facade)
src/charter/offering/drg/migration/extractor.py   # mint via step_contract_urn
src/charter/activation/identity_index.py          # + IdentityIndex.urn(kind, token)
src/charter/activation/drg_activation.py          # _resolve_activated_urns_for_kind → identity.urn
src/charter/activation/consistency_check.py       # parity stem → identity.urn + truthful remedy
src/charter/activation/activation_ledger.py       # _spell → identity.urn; IdentityLookup + urn
src/specify_cli/review/gate_bindings.py           # owning_contract_urn → step_contract_urn

tests/charter/activation/test_step_contract_urn_identity.py     # red-first regression (new)
tests/architectural/test_drg_urn_identity_parity.py             # drift gate + non-vacuity (new)
tests/charter/activation/test_deny_identity_space.py            # _FakeIdentity gains urn()
```

**Structure Decision**: Single project. The change is split across the existing
`charter/offering` (naming rule), `charter/activation` (consumers) and `specify_cli/review` (gate
join) layers exactly where those responsibilities already live; no new package or module boundary.

## Complexity Tracking

*No violations — the table is intentionally empty.*

## Implementation Concern Map

### IC-01 — The one URN authority

- **Purpose**: State the step-contract URN rule once and expose a single token → DRG URN mapping, so
  no consumer derives identity from a declared id again.
- **Relevant requirements**: FR-001, FR-002, NFR-001, C-001, C-003
- **Affected surfaces**: `src/charter/offering/missions/step_contracts.py` (new
  `step_contract_urn`), `src/charter/offering/drg/migration/extractor.py`
  (`_discover_mission_step_contract_nodes`), `src/charter/activation/identity_index.py`
  (`IdentityIndex.urn`), `src/charter/mission_steps.py` (facade re-export)
- **Sequencing/depends-on**: none
- **Risks**: reading `mission`/`action` per step-contract token must be lazy and cached (NFR-001);
  the extractor must keep failing loudly on a duplicate `(mission, action)` pair *and* on a
  duplicate declared id (both are authoring collisions).

### IC-02 — Consumers re-pointed, remedy made truthful

- **Purpose**: Make the three activation surfaces and the gate join ask the authority instead of
  re-deriving the URN, and stop blaming a resynthesis for a node that exists but was filtered out.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, NFR-002, NFR-003, C-002
- **Affected surfaces**: `src/charter/activation/drg_activation.py`,
  `src/charter/activation/consistency_check.py`, `src/charter/activation/activation_ledger.py`,
  `src/specify_cli/review/gate_bindings.py`
- **Sequencing/depends-on**: IC-01 (needs `IdentityIndex.urn`)
- **Risks**: the filter's node-visit logic must not change (precedence is frozen); the parity
  suggestion must stay byte-identical for the "not in the DRG at all" arm, since existing tests and
  operators rely on that wording.

### IC-03 — Gates and evidence

- **Purpose**: Prove the three behaviour changes red-first, and leave a gate that fails if the DRG
  URN and the declared identity drift again.
- **Relevant requirements**: FR-007, SC-001–SC-004
- **Affected surfaces**: `tests/charter/activation/test_step_contract_urn_identity.py` (new),
  `tests/architectural/test_drg_urn_identity_parity.py` (new),
  `tests/charter/activation/test_deny_identity_space.py`, `docs/changelog/CHANGELOG.md`,
  `docs/architecture/doctrine-kinds.md` (mission step contract section: state the URN rule)
- **Sequencing/depends-on**: IC-01, IC-02 (the gate must be red before the fix lands)
- **Risks**: a gate that passes for the wrong reason — hence a planted-divergence arm and a
  corpus-wide arm over the shipped graph, not a single hand-picked node.
