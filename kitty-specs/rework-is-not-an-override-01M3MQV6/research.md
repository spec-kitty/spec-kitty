# Research — rework-is-not-an-override-01M3MQV6

The sources are the pre-planning squad (code-truth, similar-issues and campsite lenses) and the post-spec squad (scope/sizing and fakeability lenses). Their live `move-task` probes ran on `main` @ `894f7cb9`.

## R-01 — How the ownership guard learns roles

- **Decision**: add allow-arms driven by one event-log role fact (`latest_implementer`) resolved in pass 1. The agent slot is never mutated differently.
- **Rationale**: the #4673 slot re-plant is a deliberate, tested design (`test_move_task_rollback_clears_claim.py::…replants_claim`). The allow-arms fix every red route (a forced `for_review → planned`, `in_review → in_progress`, and review acts after the resubmit) without touching the slot. They are also symmetric with `start_review_status` (`status/work_package_lifecycle.py:~290`), which already starts review without an ownership check.
- **Alternatives considered**:
  - (A) Release or restore the slot on unforced rejection edges. Rejected: it only fixes the rejection routes, not the review acts after the resubmit, and it perturbs the #4673/#4899 slot semantics (`test_tasks_move_task_seam.py:1309`).
  - (B-wide) Allow any distinct actor on any review lane. Rejected: it would weaken the `in_review` reviewer-race classification (C-008) and C-004.

## R-02 — Which transitions are "review acts" and which are "rework moves"

- **Decision**:
  - Reviewer arm: `old = for_review` and `target ∈ {in_review, approved, planned}` (post-plan squad: `done` dropped, since FR-003 does not require it), and the requester's tool differs from the latest implementer's tool.
  - Implementer arm: `old ∈ {planned, claimed, in_progress}` and `target ∈ {claimed, in_progress, for_review}`, and the requester's tool equals the latest implementer's tool.
  - `in_review → *` is unchanged (claim-holder only).
- **Rationale**: these are exactly the refused hops the probes found. Keeping the `in_review` verdicts claim-holder-only preserves the race classification. The implementer arm does not need a "rejection happened" precondition: outside a reviewer re-plant, the slot already equals the latest implementer. An explicit takeover (a forced claim by X) makes X the latest implementer, so the original implementer is then correctly refused.
- **Alternatives considered**: requiring a prior rejection for the implementer arm. Rejected: it adds a second event scan and brings no safety gain.

## R-03 — Failure behaviour of the new read

- **Decision**: fail closed toward today's behaviour. Any exception from reading events yields `latest_implementer = None`, which means no allowance, so the guard behaves exactly as today.
- **Rationale**: pass-1 facts must be skip-safe (`_mt_build_request`), and a corrupt log must never widen access.

## R-04 — Parallel "latest actor" authority (split-brain scan)

- **Finding**: `src/specify_cli/consolidation/preflight.py::_latest_actor_for_transition` (`:504`) and `_independent_reviewer_confirmed` (`:542`) compute a similar "latest implementer vs reviewer" from the raw JSONL.
- **Decision**: do not unify in this mission. `consolidation/**` belongs to Slice 1 (C-001), and those functions answer a different question (independence at consolidation). The new pure projection is the candidate canonical seam. Recorded as a follow-up for #3010, which already owns the independence and `force_count` semantics.
- **Third authority** (pre-PR squad): `status/reducer.py::_project_implementer_attribution` writes the `implementer_of_record` slot (#4786), which `acceptance/summary_core.py` and `status/doctor.py` read. It takes the latest `planned → claimed` claimant from `policy_metadata['agent']`. The ownership guard instead needs the actor that most recently moved the WP into `claimed` or `in_progress`, a set that includes `action implement` takeovers and legacy `move-task` claims without policy metadata, and it needs reviewer rework verdicts excluded. So `review_roles.latest_implementer_actor` deliberately answers a narrower, guard-specific question. Unifying the three answers (preflight, `implementer_of_record`, `review_roles`) into one role projection is the follow-up carried with #3010.
- **Additional authorities** (post-plan squad, D5):
  - `retrospective/generator.py:454-573::_is_arbiter_event` classifies "arbiter" by substring match on the note. It disagrees with the classifier in both directions, and it is #2267's surface (out of scope).
  - `consolidation/preflight.py:504-560` takes the latest `→ in_progress` actor as a raw string and includes the reviewer's `in_review → in_progress` rejection. Counterexample for route 2: REV `in_review→in_progress`, IMPL `in_progress→for_review`, REV approves. Consolidation then sees implementer = reviewer and raises a false hollow-review warning, while this mission's projection says IMPL. That code is C-001 territory, so the counterexample goes to #3010.
  - The agent slot and the reduced `role` slot (`review_claim_predicate.py`) are consistent with the design, because `in_review → *` stays slot-only.
- **Other "override" deciders** (checked; none change here): `--skip-review-artifact-check` → `ReviewOverride` (`tasks_transition_core.py:549`); the automatic `emit_force` on backward edges (`:341-373`); the pre-review gate `--force` (`tasks_move_task.py:~1696`); `--done-override-reason`; `--self-review-fallback` → `ReviewerSelfApproval`. Only `_is_arbiter_override` decides "arbiter override".

## R-05 — #3473 disposition

- **Decision**: closed as a duplicate of #3010 via a tracker comment (not this PR). A single `--self-review-fallback` does warn, via `ReviewerSelfApproval` (`consolidation/preflight.py:596-629`), pinned by `tests/consolidation/test_hollow_review_warnings.py`.

## R-06 — Rejected-verdict guard (#4116): not folded

- **Finding**: `_guard_rejected_verdict` refuses approval when the latest verdict is `changes_requested`. An ordinary `in_review → approved` records its own approval (review-gates.md).
- **Decision (post-plan probe)**: not folded. `_guard_rejected_verdict` (`tasks_transition_core.py:507-545`) refuses only on an unparseable verdict, or on `--skip-review-artifact-check` without `--note`. With every hop driven through the CLI after an `in_review → planned` rejection:
  - unforced `for_review → approved` exits 0 (expanded to `→ in_review → approved`) and writes review-cycle-2;
  - unforced `in_review → approved` exits 0.

## R-07 — Pre-existing residuals (documented, not fixed)

- Same-tool self-approval from `for_review` passes unforced once the implementer holds the slot (C-007 family).
- Unforced multi-hop `planned → approved` by the slot holder is legal. The classifier requires `force`, so it records nothing. Arbiter guidance (`SKILL.md` Step 5) forces `--to approved` wherever the WP sits. After an `in_review → in_progress` rejection the WP is not in `planned`, so that override goes unrecorded.
- `agent action implement` after an `in_review → in_progress` rejection: `start_implementation_status`'s IN_PROGRESS branch checks `_actors_compatible` against the latest transition actor (the reviewer), so the implementer likely gets `WorkPackageClaimConflict`. This comes from reading the code and was not probed. It is outside `move-task`, so it is not fixed here. FR-008 pins only the `planned` route.
- Arbiter runner read path (D4): `_run_arbiter_override` reads the rejection `review_ref` through `read_events_transactional`, while the classifier uses `read_events`. They agree whenever the WP is in `planned`. Divergence under a coordination topology is not exercised by this mission (LANES), so it is left as a residual.
- Fixture warning: `test_move_task_reject_fix_approve_cycle.py` seeds rework hops with past timestamps, so they order before the real rejection. New acceptance tests drive every hop through the CLI.

## Adversarial evidence

No dependency change, so the supply-chain section does not apply.
