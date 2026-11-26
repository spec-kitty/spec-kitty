# Adversarial squad records

Procedure: `adversarial-squad-deployment`. Squads are advisory and record findings with dispositions.

## Squad 1: pre-spec investigation (2026-11-20)

Lenses:
- claude::architect-alphonso
- claude::researcher-robbie
- claude::reviewer-renata (QA)
- claude::reviewer-renata (security/integrity)
- claude::planner-priti (related-issue sweep)

Synthesis was sent to the orchestrator.

Operator rulings, 2026-11-20:
- Approaches A, B and E are adopted. C is rejected. D′ goes to #7324.
- The merge-tree attribute and driver sanitization is folded in.
- `--dependency-ref` laundering is filed separately as #7766.
- The vacuous #7307 tests are folded in.
- #7497 is folded in.
- #7767 is filed and folded in.

| Finding | Disposition | Evidence |
|---|---|---|
| Stale remedy contradicts the gate on approved lanes | accepted | FR-001, FR-002, FR-003 |
| Rollback erases the stale state (#7755) | accepted | FR-002, FR-003 |
| Late, generic refusal; approved bound skips merges | accepted | FR-004, FR-005 |
| Refusal hint names `--dependency-ref` | accepted | FR-006 |
| Re-review route works only with a synthetic stamp; it is untested | accepted | FR-008 |
| Review diff hides the resolution bytes | accepted | FR-007 |
| Approach C is unsound | accepted | C-001 |
| Pre-mutation forecast (D′) | deferred_with_rationale | Operator ruling: tracked in #7324 (C-005) |
| Merge-tree honours clone-local attributes and drivers | accepted | FR-010 |
| `--dependency-ref` laundering | deferred_with_rationale | Filed as #7766. Only hint suppression is in this Mission (FR-006, C-005) |
| #7307 tests return early (vacuous) | accepted | FR-012 |
| ADR gap: #7630 trust model not recorded | accepted | FR-013 |
| Auto-rebase merges survive rollback | accepted | Issue #7767; FR-009 |
| Canceled content via a re-approved dependency lane | accepted | FR-011 (#7497) |
| Original "linearise" remedy wording | changed | Linearising now refuses. The route is re-review instead (FR-001) |
| Owned-files overlap check at for_review (defence in depth) | deferred_with_rationale | Outside the operator-ruled scope (C-005 spirit). Not filed |

## Squad 2: post-specify brownfield (2026-11-20)

Lenses:
- claude::reviewer-renata (fakeability)
- claude::doctrine-daphne (single authority / ADR fit)
- claude::architect-alphonso (feasibility)

| Finding | Disposition | Evidence |
|---|---|---|
| FR-009 contradicts ADR 2026-09-19-1 A2 and pinned tests | accepted | FR-009 now restores only from the run's recorded move, inside the rollback authority; FR-013 amends the ADR |
| FR-009 must resync the checkout and reset the lane work-tip ref; it must define the "moved since" outcome and keep the record | accepted | FR-009 |
| #7767 `--resume` refusal may not reproduce at HEAD | changed | FR-009 is red-first on the observed harm; US6 updated |
| FR-001 needs a sibling-incorporation command; raw `git merge` is forbidden by the #7285 A-10 rule | changed | Operator question DM-01M7WX8AX56E23AXBZRWGNX4EM. FR-001 references the ruling |
| FR-001 route must use the sibling's approval-stamp SHA | accepted | FR-001 |
| FR-001 / SC-001 pass with zero commands; SC-001 wording | accepted | FR-001 test executes each printed command; SC-001 reworded |
| FR-002 / FR-003 accept over-inclusive answers | accepted | Three-lane control; exact path list; FR-003 adds the no-worktree and merge-in-progress cases |
| FR-004 had no owning seam and a second "reviewed" predicate | accepted | FR-004 shares the gate's predicate (C-003). It uses the existing refusal family and an agreement test |
| FR-004 reaches orchestrator-api and `--dry-run`, so the contract is bumped | accepted | FR-004, C-007 |
| A strict xfail would XPASS | accepted | FR-012 |
| FR-005 record: lifetime, writers, threat model; negative shape control | accepted | FR-005: durable record, all writers, never exempts at the gate; message-forged and Mission-branch hand merge controls |
| FR-010 misses the remerge-diff probe (reproduced); attack set too narrow (working tree, attributesFile) | accepted | FR-010 and US7 widened; positive control keeps spec-kitty's own registered drivers |
| FR-007 contradicts review-context contract C-001 (commands only) | changed | FR-007 prints a labelled remerge-diff command; FR-013 amends the contract |
| FR-008 lacks a real-lifecycle control | accepted | FR-008: unforced, distinct actors, N3, three-lane variant |
| Reviewed novel line lands by design | accepted | Recorded as a residual in Edge Cases |
| FR-011 names a retired harness; no-op mark false if green | accepted | FR-011 uses the existing builder and pins the code; the green-at-base path is stated |
| FR-012 vs FR-004: gate rule left unexercised | accepted | FR-012 keeps a gate-level assertion |
| NFR-001 unattainable as worded | accepted | NFR-001 restated relative to the existing enumeration; version check cached |
| US4 cannot be reached end to end once FR-004 exists | accepted | US4 is a renderer-level test; mixed divergence control added |
| US3-3 end verdict for an auto-resolved source conflict | accepted | US3-3 states the gate still judges it |
| FR-013 amendment list incomplete | accepted | FR-013 adds 2026-09-19-1, 2026-11-08-2 plus the contract, #7285 rule and CLAUDE.md |
| `done` WP send-back needs `--force`; earlier-release merges without a record | accepted | Edge Cases |
| orchestrator-api stale remedy stance | deferred_with_rationale | Decided in plan (C-006: same renderer) |
