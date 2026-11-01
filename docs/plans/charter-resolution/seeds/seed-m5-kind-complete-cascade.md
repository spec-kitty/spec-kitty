---
title: Mission Seed M5 - Kind-Complete Cascade and Orphan Wiring
description: 'Specify-intake seed for the mission closing #2829 and the residual of #3009: expand the cascade relation set and wire the remaining orphaned artefacts.'
doc_status: active
updated: '2026-08-19T00:00:00Z'
kind: Planning
---

# Mission Seed — M5: Kind-Complete Cascade + Orphan Wiring

> **Status:** seed. Feed to `/spec-kitty.specify` in a fresh session.
> **Part of:** charter-resolution program (see `../program-brief.md`).
> **Closes:** #2829, and the residual of #3009.
> **Effort:** L, **ADR-worthy.** **Depends on:** land **LAST** — it changes cascade reach and ripples golden counts, so it must re-ledger once, atop M2's fragment edges.

## Problem

Two complementary reach gaps:

- **#2829 — relation-set dead-end.** `REFERENCE_RELATIONS = {requires, suggests, refines}`. `mission_type` nodes carry only `requires→action`; `action` nodes carry `scope→{directive,tactic,…}` and `instantiates→template` — never requires/suggests/refines. The forward closure reaches the `action` node, `_referenced_artifacts` drops it (action is not an artifact kind), and finds nothing. **Measured: cascade from every built-in mission_type returns 0 activated kinds.**
- **#3009 residual — absent inbound edges.** A handful of charter-activated artefacts have zero inbound edges of any followed relation, so cascade reaches none of them. **Most of #3009 already landed** (membership set replacing the bare count, wire-8-delete-1, reachability companion metric); only ~5 `_ACTIVATED_BUT_ORPHANED` artefacts remain to author edges for (or mark direct-activation-only): `styleguide:deployable-skill-authoring`, `quadruple-a-test-format`, `given-when-then-authoring`, `toolguide:sonar`, `toolguide:gherkin`.

These are complementary, not one subsuming the other: #2829 fixes nodes that *have* `scope`/`instantiates` inbound but are never followed; #3009 fixes nodes with *no* inbound edges at all.

## Fix approach

- **#2829:** expand the cascade traversal so activating a `mission_type`/`action` reaches every kind its actions depend on — add `scope` and `instantiates` (the action-hop relations; consider `vocabulary`) to the followed set, OR reuse `resolve_context`'s scope→requires→suggests algorithm for the action hop. Keep `in_tension_with`/`reconciles_tension`/`rejects`/`delegates_to`/`applies` excluded. `_referenced_artifacts` must still yield terminal artifact kinds, not intermediate `action` nodes. **Likely its own ADR; re-ledger golden counts.**
- **#3009 residual:** author real inbound edges for the ~5 remaining orphaned artefacts (or mark by-design direct-activation-only) and shrink the ledger membership set accordingly. Shares the per-artefact-review authoring activity with M3's triage.

## Open operator decisions (resolve at this mission's discovery / ADR)

- **Which relations join the followed set** for the action hop — `scope` + `instantiates` only, or also `vocabulary`? This is the ADR's core call.
- **Orphan dispositions:** for each of the ~5 `_ACTIVATED_BUT_ORPHANED` artefacts — author an inbound edge or mark direct-activation-only?

## Scope

- **In:** the cascade relation-set expansion (with ADR), the ~5 residual orphan-edge authoring, the single golden re-ledger.
- **Out:** everything the other missions own. Do not re-do the already-landed #3009 pieces.

## Key seams

- `charter/cascade.py` (`REFERENCE_RELATIONS`, `_referenced_artifacts`, `_forward_reference_closure`)
- the golden-count ledger surfaces (re-ledger once)
- `resolve_context`'s scope→requires→suggests algorithm (reuse candidate)

## Sequencing

Land **after** M2 so the fragment edges are already in the graph when the relation-set expansion re-ledgers golden counts — counts move once, not twice.
