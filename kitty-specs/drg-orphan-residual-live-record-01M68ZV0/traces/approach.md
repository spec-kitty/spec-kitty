# Approach tracer — drg-orphan-residual-live-record-01M68ZV0 (#6513)

## 2026-10-31 — grounding decided the shape of the mission (pi)

The reported red does **not** reproduce on `main` (`dfe9efb0e8`): the shipped graph carries 25
incidence orphans and `DOCUMENTED_ORPHAN_RESIDUAL` is already 25, raised in `bd7fdb7f36` (the #6437
fold of #6432) for the four `mission_step_contract:plan/*` nodes vendored by #6379.

The four are **edge-less by construction** (`_EDGELESS_BY_CONSTRUCTION` in
`tests/charter_offering/drg/migration/test_extractor_projection.py`): the step-contract fragment
ships `edges: []` and activation resolves a contract by URN lookup on the `(mission_type, action)`
join. So neither honest remedy available to a *code* change applies — wiring an edge would be
metric-gaming (D-C2 / C-003) and the ceiling must not move.

The honest residue is documentation: the record the gate names
(`kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`) is an
immutable archive root, so the gate's remedy was unexecutable; its last state (ceiling 29 -> 30 over
17 step contracts) contradicts the shipped 25 over 21; and nothing binds the constant to any record,
so a one-line raise still goes green. Mission scope follows from that: live record + retargeted
instructions + a guard, with the ceiling fixed and the graph untouched.

## 2026-10-31 — red-first, then the record (pi)

The guard (`test_documented_residual_matches_measured_shipped_orphans`) was written before the
record existed and failed naming all 25 URNs as measured-but-not-recorded. The record then made it
green, and the guard was proven in both directions by temporary mutation (dropping
`toolguide:powershell-syntax`; substituting `tactic:does-not-exist` for
`agent_profile:human-in-charge`). Both transcripts are in the PR body.
