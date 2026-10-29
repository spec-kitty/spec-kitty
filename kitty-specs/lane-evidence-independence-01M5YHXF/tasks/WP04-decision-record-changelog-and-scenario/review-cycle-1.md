---
affected_files: []
cycle_number: 1
mission_slug: lane-evidence-independence-01M5YHXF
reproduction_command:
reviewed_at: '2026-10-29T11:09:22Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback (reviewer-renata), cycle 1

Verdict: changes requested. Two small places where the ADR disagrees with the code; the docs are
the defect in both. Everything else holds against lane-d's code:

- The amendment describes correctly:
  - the codes and the evidence windows, including the merge-base dependency widening;
  - the claim-time consolidate check, `PREFLIGHT_FAILED`, `MISSION_NOT_READY` with
    `data.evidence_error_codes`, and contract 1.19.0;
  - the force semantics and the attestation scope;
  - the placeholder ruling.
- The six rulings are quoted accurately.
- The residuals are fair; the merged-in-content residual and the forced-review residual match
  what I found in review.
- The changelog entry is accurate and operator-facing, and its `updated:` is bumped. The ADR
  `updated:` is bumped too.
- The `AGENTS.md` paragraph is a short pointer.
- The scenario: the five existing scenario names are unchanged (ledger keys are `file::scenario`
  and still resolve). The new Rule's refusal has a same-fixture positive control (committed work,
  then `for_review` succeeds). Tests:
  - `tests/architectural/test_scenario_contract.py` together with
    `tests/architectural/test_no_legacy_terminology.py`: 139 passed.
  - `gradle -p acceptance-jvm test -Dcucumber.filter.tags=@evidence`: BUILD SUCCESSFUL, 2
    scenarios run, 0 failures (109 skipped by the tag filter).

## Required fixes

**1. The paragraph the WP edited still names functions that no longer exist.**
- Where: `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md`, line 173
  ("Planning lanes and `single_branch` missions").
- You updated the move-gate name in that paragraph. It still says the #5939 axis is
  `reconciliation._single_branch_evidence_refusal`, "exposed to `orchestrator-api consolidate-mission`
  via `single_branch_evidence_refusal`".
- WP01 removed both functions. `grep -rn single_branch_evidence_refusal src/` finds nothing.
- Fix: name the current authority the same way you did for the move gate:
  `consolidation/wp_evidence.py` (`evaluate_evidence`, called by `build_approved_wp_set`), and the
  orchestrator-api path through `wp_evidence.mission_evidence_report`. For example: "(... before
  #6715; since then the single_branch voice of `consolidation/wp_evidence.py`)".

**2. "Where it runs" overstates the independence check at the move.**
- The amendment says "an unforced move into `approved` or `done` needs independence".
- The code (`tasks_move_task._mt_require_independent_approval`) refuses at the move only in two
  cases:
  - the approver's identity positively equals the implementer of record;
  - the approval would be recorded as a generic placeholder.
- An unknown implementer passes at the move, by ruling; only `accept` and `consolidate` are strict
  there.
- Fix: say exactly that in "Where it runs", or add it as a residual beside the forced-review one.
  The positively-same-only rule at the move is an operator ruling (the WP03 brief), so either quote
  it with the rulings or cite it.

## Non-blocking

- The scenario's control moves the work package to `for_review`, not to `approved`. That is the
  right choice, since `claude` approving its own work would refuse `REVIEW_NOT_INDEPENDENT`. A
  one-line comment in the feature file would save the next reader the same question.
