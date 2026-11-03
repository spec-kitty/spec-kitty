# Research: Owned files unresolved fail closed

Pre-spec squad, 2026-11-03 (procedure `adversarial-squad-deployment`, point-cut pre-spec). Lenses: `researcher-robbie` (tracker), `architect-alphonso` (code surface), `planner-priti` (scope). Each profile was loaded.

## Findings and dispositions

| # | Finding (lens) | Disposition | Evidence location |
|---|---|---|---|
| F1 | The owned read reported in #7149 is already fixed on `main` by #7099 (`088c2f1661`, PR #7103). The issue was reproduced on `01dbf46158`, which predates it. `test_owned_acceptance_authority_6023.py` passes on `main` and fails on `01dbf46158` (architect). | accepted: not re-implemented (C-002) | spec.md Background; comment on #7149 |
| F2 | The topology read (`is_single_branch_mission`) also reads the repository root (planner). | changed: rejected after adjudicating from source. On `main` it takes `owned=` and `evaluate_evidence` passes it (`wp_evidence.py:758`) | this table |
| F3 | Unresolved ownership is still judged `IMPLEMENTATION_MISSING` and can be lifted by attestation (architect). | accepted: the mission's core | FR-001..FR-004; IC-01, IC-02 |
| F4 | `acceptably_canceled_wp_ids` reads the repository root on `accept --owned-checkout` (architect, planner). | accepted | FR-006; IC-03 |
| F5 | Owned `move-task` reports `not patterns` as generic `OWNED_IMPLEMENTATION_MISSING` (architect). | changed: the work package file is already read there, so empty patterns mean an authored empty list (a resolved declaration). Only the refusal detail is made honest; the code is kept. | FR-007; IC-04 |
| F6 | Flip `missing_owned_ownership` in the 6023 test to the new code (architect). | changed: that scenario authors `owned_files: []`, which stays `IMPLEMENTATION_MISSING` under the refined trigger. It is kept as the FR-008 ratchet. | IC-01 Evidence |
| F7 | #7081 tracer-append (PR #7129 in flight) and #5458 (collides with PR #7146) (researcher, planner). | deferred_with_rationale: separate seams with open work | spec.md C-003 |
| F8 | `add-history` lacks `--owned-checkout`; `consolidate` / `orchestrator-api` have no owned support (all lenses). | deferred_with_rationale: different commands or a capability gap; follow-up issues at closeout | spec.md C-003 |
| F9 | Open PR #7146 (#7120) edits `wp_evidence.py` and `tasks_move_task.py` (planner). | deferred_with_rationale: edits are kept to `_judge`, the scan and the owned move-task branch; rebase at closeout | plan.md Constraints |

## Decisions

- **Signal.** Decision: unresolved ownership means the work package is absent from the resolved ownership map; an authored list, even an empty one, is resolved. Rationale: no new I/O (NFR-001), and `finalize-tasks` accepts `owned_files: []` for non-`code_change` work packages. Alternative considered: treat empty as unresolved (rejected, because it would block legitimate empty declarations behind an unliftable code).
- **New code, not reuse.** Decision: add `OWNERSHIP_UNRESOLVED` (+ `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`). Rationale: `IMPLEMENTATION_UNREADABLE` means the window diff is unreadable and its recovery (restore the branch) points the wrong way. `OwnedRefusalCode` is owned-checkout-only, and this verdict also applies to repository-root Missions.
- **Not liftable.** Decision: the attestation refuses it. Rationale: an attestation vouches for "nothing to implement", not for an unread declaration.

## Post-tasks squad (2026-11-03)

Lens: `reviewer-renata` (decomposition, non-vacuity, test economy). Verdict: GO-with-edits.

| # | Finding | Disposition | Evidence location |
|---|---|---|---|
| P1 | The recovery text naming `--attest-no-implementation` would trigger `orchestrator_api/consolidation.py::_no_implementation_attestation_note`'s attestation hint | accepted: the recovery ends "No attestation lifts this." with no flag literal | WP01 T004 |
| P2 | No existing test exercises `_refuse_unliftable` | accepted: one parametrized planner test plus a control; event log asserted unchanged | WP01 T005 |
| P3 | The contract version bump was undecided against the spec assumption | accepted: 1.22.0 → 1.23.0 (decision `plan.contract.version-bump`); docs follow at closeout | WP01 T006; spec Assumptions |
| P4 | Three docstrings become wrong; place new entries to keep the PR #7146 conflict small | accepted | WP01 T003 step 6, T004 |
| P5 | An omitted `owned_files` key defaults to `[]` and reads as present | accepted: treated as resolved (matches today and FR-008), commented in code | WP01 T003 step 5 |
| P6 | The new 6023 row must commit the deletion and use `stale_primary=True` | accepted | WP01 T001 step 3 |
| P7 | Spec scenario 3 named a file while the contract names the directory | accepted: "the directory or file it read" | spec.md US1 scenario 3 |
| P8 | Only the neutral code belongs in `_UNLIFTABLE_VERDICTS` (verdicts are canonicalised) | accepted | WP01 T005 step 2 |
| P9 | WP02 T009 has no observable accept-level difference; the integration test would be vacuous | accepted: the prompt's fallback (a unit test through `acceptably_canceled_wp_ids(owned=...)` plus a non-owned control) is the route | WP02 T009 step 4 |
