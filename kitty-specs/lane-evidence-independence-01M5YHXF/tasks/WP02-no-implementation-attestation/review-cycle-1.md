---
affected_files: []
cycle_number: 1
mission_slug: lane-evidence-independence-01M5YHXF
reproduction_command:
reviewed_at: '2026-10-27T20:47:16Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (reviewer-renata), cycle 1

Verdict: changes requested, for one blocking finding.

What holds up:
- The attestation lifts only `IMPLEMENTATION_MISSING`.
- It is never the approving actor. `_latest_actor_for_transition` skips it.
- It is never an approval stamp. `approved_bound._is_approval` treats a forced `approved -> approved`
  as no approval: `from_lane` is not `in_review`, and the arbiter override needs `old_lane == planned`.
  A forced `-> done` is not an approval either.
- The hollow-review force count discounts it.
- Every other reader of `policy_metadata.attestation` checks for its own value.
- All requests are validated before any is recorded.
- The flag, the exit-2 refusal and the dry-run notice are wired and tested.

## Blocking

**1. A stale attestation keeps lifting `IMPLEMENTATION_MISSING` after the work package is reopened and approved again (fail-open).**
- Where: the reader `wp_evidence.no_implementation_attested_wp_ids` / `attested_no_implementation`
  (wp_evidence.py ~L152-164) honors ANY non-migration no-implementation attestation the work
  package ever recorded. The writer (`no_implementation_attestation.py`) records it with no scope.
- Failure scenario (probe `/tmp/claude-0/-home-user-spec-kitty/98a00833-f8c1-5968-adf2-832916f6ed94/scratchpad/probe/test_stale_attest.py`):
  1. WP01 is approved by an independent reviewer.
  2. An operator records `--attest-no-implementation WP01` (for example during a consolidate that
     then refused for another reason).
  3. WP01 is reopened (`approved -> planned`, for example because the reviewer found it does owe
     work).
  4. WP01 is claimed again, still commits nothing, and is approved again by a different reviewer.
  5. `evaluate_evidence` returns refusal `None` and `lifted_wp_ids = {WP01}`. The hollow
     re-approval lands `done`.
  This is exactly the #6715 hollow case (distinct reviewer, no owned change) that
  `IMPLEMENTATION_MISSING` exists to stop. The attestation was the operator's statement about an
  earlier approval, not about the new one.
- Precedent: `--attest-approved-reviewed` is superseded by a later review approval
  (`approval_is_attested` reads the newest approval). The canceled-superseded attestation only
  covers up to its own `lane_head`. Both are bounded in time; this attestation should be too.
- Required fix: an attestation counts only while the work package has stayed in the approved
  claim since it was recorded. Disregard it when a later non-migration event for that work package
  moves it to a lane outside `{approved, done}`. Every reopen, rejection and re-approval does that,
  while the run's own `approved -> done` and an interrupted run's resume keep it.
  - Put the rule in the one reader in `wp_evidence` (an out-of-map one-line edit with rationale;
    the reader cannot import `no_implementation_attestation`, which imports it).
  - Apply the same scope to `attested_reason`, so the consolidate notice names the live
    attestation's reason.
  - Add a regression test for the probe scenario (refuses `IMPLEMENTATION_MISSING`) and one where
    the run's own `approved -> done` keeps the lift.

## Non-blocking

- Atomicity residual, the same pattern as the existing attestations: all requests are validated
  before any is recorded, and a canceled-attestation refusal happens before anything is written.
  But if a write fails partway (a seam refusal or I/O error on a later attestation) after earlier
  attestations were recorded, those stay recorded. Also, an attestation recorded before a claim
  that then refuses (for example `REVIEW_NOT_INDEPENDENT`) persists by design. Mention this in the
  help text or docs.
- `tests/integration/test_6715_no_implementation_attestation.py`: the landed case asserts `done`,
  the notice and the banner. Consider also asserting that `main` advanced only by the other work
  packages' content (nothing for WP02 on the target).
- The attestation's `evidence.review.reviewer` is the merge actor, as for `--attest-approved-reviewed`.
  If the reducer's `review` snapshot slot takes it, the done evidence names the operator as the
  reviewer. That is cosmetic, but check `resolve_event_stream_review`.
