# Tracer: Design Decisions

Mission: ci-nightly-wallclock-budget-01M34HNZ (issues #4865, #4864)

## Decision: split `performance-and-e2e` into three jobs, not a higher timeout

**Alternatives considered:** raise `timeout-minutes` on the single job (e.g.
90-120 minutes) to accommodate the observed 65-minute run plus margin.

**Rejected because:** the single-job design's actual defect is not that the
budget is too small — it is that three independently-owned suites share one
job verdict. Raising the cap would still leave a genuine e2e regression
indistinguishable from a slow-but-passing run in the job's pass/fail signal
(the exact ambiguity that made 2026-09-20's real regression invisible against
routine timeout cancellation). This was an explicit operator ruling, not a
default engineering preference, and is recorded verbatim in the spec's
Clarifications section so a later reader does not re-litigate it.

**Chosen:** three independent jobs (perf / e2e / stress), each timeout
re-partitioned from the observed 65-minute combined total rather than copied.
Accepted costs recorded explicitly rather than discovered late: 3x
checkout+sync cost (NFR-005), and a `needs:` list update on `nightly-summary`
(FR-003) so the aggregator does not silently drop a suite's result.

## Decision: `charter` recapture uses `capture_shard_timings.py`, not the `349b73fc0` heuristic

**Alternatives considered:** the manual heuristic already used twice for
`agent`/`upgrade` in commit `349b73fc0` — bump `shard_count` by
wall-clock÷target, without recapturing timings.

**Rejected because:** that heuristic bypasses `ci-shard-timings.json`
entirely. It would produce a `shard_count` that "works" operationally (keeps
the job under its timeout) but leaves the registry's own documented claim
("shard sizing is chosen by greedy LPT bin-packing of the MEASURED per-test
durations... never guessed, never from file counts") false for `charter`,
exactly as it remains false today for `agent`/`upgrade`. This is an explicit
operator ruling: the heuristic is not merely a lower-quality option, it is
named as a **rejected precedent** for this mission specifically because it
would perpetuate rather than close the defect class the mission targets.

**Chosen:** `scripts/ci/capture_shard_timings.py --module charter --write`,
then re-derive `shard_count` from the resulting real data via the existing
`test_inter_shard_skew_within_twenty_percent` LPT method. Cost (~110 min
serial execution) is accepted and explicitly budgeted as its own step.

## Decision: scope is `charter` only — the other 13 stale modules are out of scope, no follow-up issue

**Rationale:** 14 of 21 registry modules are stale by the same "never
captured with the correct tool" standard, but only `charter` is this
mission's target (#4864 names it specifically, and the P2 issue's motivating
evidence — this morning's 27-32 min long pole — is `charter`'s). Recapturing
the other 13 would multiply the ~110-minute serial cost per module and is a
mission-sized undertaking of its own, not something to silently fold into this
one via Standing Order #2's opportunistic-cleanup allowance — locality of
change (`DIRECTIVE_024`) is the brake here, not boy-scout expansion. Per this
project's "no follow-up issues" standing rule, no new GitHub issue is filed
for the remaining 13; the boundary is instead recorded in the spec's
Clarifications section for the orchestrator to fold, escalate, or ledger at
mission exit.

## Decision: verification is a pre-merge manual `workflow_dispatch`, not deferred to the next nightly

**Rationale:** neither fix's real acceptance criterion is provable by a unit
test alone (job verdict blending, timeout truncation, and shard-skew realism
are all runtime properties of a real nightly-shaped run). `ci-nightly.yml`
already supports `workflow_dispatch` with a `mode` input defaulting to `full`,
so dispatching it on the PR/mission branch before merge is legitimate,
available evidence — this was made an explicit part of the spec's Success
Criteria and every AC's falsifiability statement, rather than left as an
implicit "we'll see on the next nightly" assumption that would defer the real
proof past merge.

## Decision (plan phase, 2026-09-22): size the three new timeouts from real
pulled run data, not estimation

**Alternatives considered:** estimate each suite's share of the 65-minute
total by eyeballing the spec's prose description, or split evenly (~20 min
each).

**Rejected because:** the spec's Summary only states the job's total (65 min)
and that stress was truncated — it does not give per-suite splits, and an
eyeballed/even split would repeat exactly the "budget set without
measurement" root cause this mission exists to fix, just one level down (job
budget instead of module shard_count).

**Chosen:** pulled the cited run's own step-level timestamps directly —
`gh run view 35683539593 --repo spec-kitty/spec-kitty --json jobs` — which
gives exact wall-clock per suite step: `performance` 23m41s (03:32:57 →
03:56:38), `e2e` 24m44s (03:56:38 → 04:21:22), `stress` >=16m18s truncated
(04:21:22 → cancelled at 04:37:40, step still `in_progress`). Provisional
budgets (`performance` 35, `e2e` 40, `stress` 60 minutes) are derived from
this real data with headroom, not guessed — `stress`'s budget is deliberately
the most conservative of the three because its true duration is only a lower
bound (truncated, never completed) — explicitly flagged PROVISIONAL, to be
confirmed or corrected by the Phase 1 pre-merge `workflow_dispatch`'s actual
`stress` job conclusion before the PR is called done. Recorded in full in
`plan.md`'s "Real evidence used to size the new budgets" section.

## Correction (analyze phase, 2026-09-22): `stress`'s Stage A budget is 90 minutes, not the provisional 60 recorded above

The decision entry directly above records a provisional `stress` budget of 60 minutes. That value
was superseded before `plan.md` was finalized: the committed `plan.md` ("Real evidence used to
size the new budgets" section) and this mission's `tasks.md`/WP02/WP03 all use a two-stage sizing
design for `stress` instead — **Stage A**, a deliberately generous, MEASUREMENT-ONLY
`timeout-minutes: 90` used only for the first pre-merge `workflow_dispatch` (never itself the
shipped value), followed by an UNCONDITIONAL **Stage B** re-derivation (WP03, T017) from
`stress`'s real completed duration, with a bounded `90 -> 150 -> 300`-minute widen-retry ladder if
Stage A itself truncates. `60` does not appear anywhere in the committed `plan.md`/`tasks.md`/WP02/
WP03 text. Recorded here per the analyze-phase cross-artifact consistency pass
(`ci-nightly-wallclock-budget-01M34HNZ`'s `analysis-report.md`) as an appended correction rather
than by silently editing the decision entry above, preserving the historical record of what was
considered at each point in the mission's planning.
