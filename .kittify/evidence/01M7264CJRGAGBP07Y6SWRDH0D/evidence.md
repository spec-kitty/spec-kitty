# #7492 code grounding: nightly acceptance-bdd red with no failing test

Op `01M7264CJRGAGBP07Y6SWRDH0D` (python-pedro). Branch `fix/7492-nightly-acceptance-bdd`.

## The issue

#7492 (P0, from:ci, milestone 4.0.0 release scope, parent epic #5106) was auto-opened by
`scripts/ci/nightly_escalation.py` for run 42748989805. Its body says only "The xunit report listed
no failing tests". In the operator's comment, three escalations in three days point to a root cause,
not to flakes. Earlier occurrences: #7343 (a real regression, fixed in #7364), #7465, #7190, #7062 and #6369.

## Evidence from the runs (job and step timings, via the Actions API)

| Run | Date | Windows leg | Gating step | @wip step |
|-----|------|-------------|-------------|-----------|
| 42748989805 | 11-10 | cancelled at 60:23 | success 03:24-04:11 (47 min) | cancelled 04:11-04:22 |
| 42556248147 | 11-09 | success at 59:58 | success (48 min) | success (11 min) |
| 42516534769 | 11-08 dispatch | success at 58:48 | success (47 min) | success (11 min) |
| 42333589392 | 11-07 | success at 58:45 | success (47 min) | success (11 min) |
| 41961190305 | 11-05 | cancelled at 60:25 | success (48 min) | cancelled |
| 41766680757 | 11-04 | success at 40:02 | success (31 min) | success (7 min) |

In every row the gating pass is green on all three OSes, and Linux and macOS finish in under 30 minutes.
In the shapes that were not caused by the timeout, 42442477189 (11-08) has real gating failures (#7343),
and 41571798610 and 41382886325 (11-02/03) have an Ubuntu setup or pin-check step failure (#7062).

**Root cause.** `.github/workflows/ci-nightly.yml` job `acceptance-bdd` (60-minute job cap) runs:
- the gating step, with a 55-minute step cap;
- the non-gating `@wip` step, which has `continue-on-error` and no step cap.

The 55-minute gating cap uses up the whole #6787 reserve of 5 minutes, so the `@wip` step has no room
of its own. After the gating pass grew to about 47 minutes on Windows, the `@wip` pass ran the leg into
the job cap. GitHub then cancelled the job, which made `needs.acceptance-bdd.result` read `cancelled`.

The escalation is fail-closed (only `success` closes), so it filed a P0. The gating JUnit had no failures,
which produced the "no failing tests" body. This contradicts FR-014 (a WIP scenario never fails the leg).

**Escalation defect.** `nightly_escalation.py` never sees the job result. A red that comes from a
cancellation, a skip or a step outside the tests therefore reads only as "the xunit report listed no failing tests".

## Invariants kept

- NFR-005 (no retry on the gating run), FR-011 (an evidence bundle per leg, schema v1), FR-014.
- ADR 2026-10-15-1 (one deduped P0 for all legs, suite key `acceptance-bdd`).
- #6787 (a suite step's cap sits under its job cap by a 5-minute reserve).
- #5169 (mainline-only escalation).
- The fail-closed escalation: `--conclusion` alone decides open, bump and close.
- The artifact name `acceptance-bdd-results-<os>`, which spec-kitty-qa consumes.

## Gates that pin the touched code

- `tests/ci/test_acceptance_bdd_job.py`, `test_acceptance_evidence.py`, `test_nightly_escalation.py`.
- `test_nightly_suite_step_timeout.py`: the step-cap reserve; the new wip step is a suite step because
  its evidence reads `steps.wip.outcome`.
- `test_nightly_timeout_headroom.py`, `test_nightly_tooling_cache.py`, `test_fork_guard.py`.
- `test_release_nightly_gate.py`, `tests/architectural/test_workflow_coherence.py`.
- `test_no_duplicate_suite_execution.py`, `test_no_legacy_terminology.py`.

All of these are kept green honestly: they are re-pointed, and nothing is loosened.

## Delivery shape and operator decisions

This is a governed Op, not a Mission: a local CI wiring fix, with no runtime contract change. The
operator decided two things through AskUserQuestion:
1. Split `@wip` into its own job (chosen over raising the cap inside the job, and over a short cap that kept the existing caps).
2. Fold the escalation honesty fix into this PR.

## Fold candidates

| Issue | Recommendation | Reason |
|-------|----------------|--------|
| escalation "red with no failing ids" | **fold** | same defect shape, same script |
| #7488 security-scans outage vs finding | don't fold | different job; needs pip-audit/bandit JSON classification; can reuse `--job-result` |
| #7114, #7115 (open from:ci) | don't fold | shard-timings and architectural battery budgets, unrelated |
| #7465, #7190 (closed) | related | same timeout shape, auto-opened then closed |

## In-flight work

No overlap with:
- #7490 (consolidation window provenance);
- the docs-site slice (epic #6100);
- #7493 (`lanes/implement_support.py`);
- #7346, #7434 and #7159.

## Residual risk (not in scope)

The Windows gating pass is now 47-48 minutes against its 55-minute step cap (about 1.15x headroom),
up from about 31 minutes on 11-04. A gating timeout would now be named in the P0 (`--job-result`),
but the budget needs a follow-up.
