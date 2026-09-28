# Tracer: Approach

Mission: `ci-nightly-interpreter-matrix-45min-timeout-01M3G17F`

## Shard partition method

Test module/file/directory partition (top-level `tests/` directories grouped
into N disjoint sets, expressed as positional pytest paths plus `--ignore`
globs for "everything not explicitly assigned elsewhere"). Explicitly NOT
`.github/ci-module-registry.yml`'s `shard_count` LPT bin-packing mechanism —
ledger SK-247 documents that mechanism as silently falling back to
uniform/count-based weighting for 20 of its 21 modules because committed
durations and live collected node ids are paired positionally and drift out
of sync. A directory-level partition, re-derived from a fresh measurement
every time a boundary needs to move (rather than a long-lived committed
duration list), cannot inherit that specific failure mode.

## N sizing method

N and each shard's `timeout-minutes` are sized exclusively from the
build/implement phase's own `workflow_dispatch` run 1 (baseline/timing
capture) on `ubuntu-24.04` — the mission's own branch, the real runner class
this leg executes on. The issue's local 24-core-workstation numbers (~5036s
serial / ~475.87s with `-n auto`, ~34,835 tests) are explicitly rejected as a
sizing input: they are a categorically larger machine than a GitHub-hosted
`ubuntu-24.04` standard runner, and the two real prior dispatch runs already
prove the local `-n auto` figure (~8 minutes) does not transfer — both real
attempts died at the 45-minute cap with no verdict. `.github/ci-shard-timings.json`
is likewise never read as a sizing input (it belongs to `module-tests.yml`,
out of scope per C-002). See plan.md §A/§B for the full method and the
per-shard `timeout-minutes` formula (`ceil(real_wallclock_minutes * 1.3-1.5)`,
mirroring the `#4948` perf/e2e/stress precedent's own headroom ratio).

## Reuse-vs-rejection decision (FR-017/SC-010)

**Reused**: `tests/architectural/_gate_coverage.py`'s `Gate` dataclass,
`parse_workflow`, and `collect_job_nodeids` — pure, general-purpose
primitives (parse a workflow into gates; collect real `pytest --collect-only`
node-ids for a gate) that need no baseline-file machinery to be useful.
Also reused: the `BaselineTarget` dataclass and `gates_for_target` function,
constructed as LOCAL values inside a new test module (one `BaselineTarget`
per roster-declared shard), NOT by adding entries to the shared
`BASELINE_TARGETS` tuple.

**Rejected**: wiring FR-004/FR-016 through the shared `BASELINE_TARGETS`
tuple and `collect_real_union_for_target`/`freeze_baselines`. That layer's
semantic is "has this ONE job's selection drifted since a human last froze
it" (a historical-drift oracle backed by a committed, manually-regenerated
snapshot file) — not "do these N independently-named jobs' LIVE selections
union to exactly today's full selection, with zero gap/zero overlap, on
every CI run." Repurposing it would either redefine what a `BaselineTarget`
means for every future consumer of the shared tuple, or require one frozen
baseline file per shard that must be manually regenerated every time a
shard boundary moves — reintroducing, one layer up, the exact "committed
data silently drifts from live reality" hazard SK-247 already documents.

Verified first-hand (2026-09-27, direct read of `_gate_coverage.py`):
`BASELINE_TARGETS` is currently `()` (empty); no test file anywhere in
`tests/` imports `collect_real_union_for_target`, `gates_for_target`, or
`BaselineTarget`; no Makefile/workflow target invokes
`--emit-census`/`--verify-census`/`--freeze-baselines`. This mechanism is
unconsumed today, not merely unconfigured — so this decision is "extend AND
author a new consumer" (`tests/architectural/test_interpreter_shard_coverage.py`),
not "flip a switch." Full write-up: plan.md §A, "Reuse-vs-rejection decision
against `_gate_coverage.py`'s coverage-oracle substrate."

## Dispatch evidence (filled in during build/implement phase)

- Run 1 (baseline/timing-capture): https://github.com/spec-kitty/spec-kitty/actions/runs/36294808024
  (dispatched 2026-09-27T04:36:39Z, `mode=full`, on branch
  `issue-4951-ci-nightly-interpreter-matrix-timeout`). Overall run conclusion:
  `failure` (job-level: shard-1 `success` 351s, shard-2 `success` 639s,
  shard-3 -- the initial "everything else" bucket -- `cancelled` at the
  45min cap after a real 2779s/29710-test run, plus a pre-existing red on
  `integration-next` and one `module-tests` shard, both unrelated to this
  mission's diff). This run's DATA (not its pass/fail) was the goal: it
  proved the initial N=3 partition badly imbalanced and supplied the real
  counts/timings used to redraw it into 6 shards (see
  tracer-design-decisions.md, "Shard boundary redraw (T009)"). Counts
  against the operator's up-to-3 budget: 1/3 used.
- Run 2 (validation): https://github.com/spec-kitty/spec-kitty/actions/runs/36300726806
  (dispatched 2026-09-27T06:39:11Z, `mode=full`, on the finalized 6-shard
  shape). **SC-001/SC-002 CONFIRMED**: every one of the 6 shards reached a
  real, completed `success`/`failure` conclusion -- ZERO `cancelled` --
  within its own `timeout-minutes` budget:

  | Shard | Wall-clock | Budget | Utilization | Conclusion |
  |---|---|---|---|---|
  | shard-1 | 597s (9.9min) | 15min | 66% | `success` |
  | shard-2 | 1074s (17.9min) | 20min | 89% | `success` |
  | shard-3 | 673s (11.2min) | 25min | 45% | `failure` (pre-existing, see below) |
  | shard-4 | 792s (13.2min) | 25min | 53% | `failure` (pre-existing, see below) |
  | shard-5 | 1374s (22.9min) | 25min | 92% | `success` |
  | shard-6 | 420s (7.0min) | 25min | 28% | `success` |

  Note: shard-5's 92% budget utilization has less headroom margin than the
  ~1.5-2x design target (the extrapolated timeout for shards 3-6 was a
  same-population-aggregate estimate, not a direct per-shard measurement --
  see tracer-design-decisions.md); it still completed well inside budget, so
  this is a watch item for a future re-tune, not a defect in this PR.

  **FR-012 (fail-fast:false / shard independence) CONFIRMED empirically**:
  shard-3 and shard-4 failed while shard-1/2/5/6 succeeded, all six running
  to their own independent completion -- no shard's failure masked, blocked,
  or cancelled another.

  **Shard-3/shard-4 failures are PRE-EXISTING, not caused by this mission's
  diff**: every failing test (`test_installer.py`, `test_release_ci_ownership.py`,
  `test_doctor_cli_surface_golden.py`, `test_review_durability_matrix.py`,
  `test_verdict_provenance_backfill.py`, `test_mission_close_guard.py`,
  `test_pinning_inventory_fresh.py`, `test_mission_type_current_fallback_signal.py`,
  `test_decision_command_shape_consistency.py`,
  `test_installer_global_reassess_convergence.py`,
  `test_audit_tail_readers.py`, `test_dispatch.py`,
  `test_terminology_guards.py`, `test_orphan.py` (charter_lint),
  `test_events_envelope_matches_resolved_version.py`) is an existing,
  unrelated functional test with no dependency on `.github/workflows/ci-nightly.yml`,
  the shard roster, or the architectural guard -- none of this mission's
  touched files. Several of these EXACT test names also failed in run 1's
  pre-redraw shard-3 bucket (same population, differently partitioned),
  confirming determinism, not flakiness. This is the concrete, first-ever
  real evidence for tracked issue **#3189** ("no pytest job runs above
  Python 3.12, so interpreter-divergence defects are invisible to the
  gate") -- exactly the defect class #3189 already tracks, now finally
  visible because this mission's fix lets the leg complete. Per this
  session's explicit dispatch instructions ("Do not comment on issues or
  PRs"), this evidence is recorded here and in the final report for the
  orchestrator to post to #3189 (or file a fresh linked issue), rather than
  being posted by this WP session itself.
- Run 3 (spare): NOT DISPATCHED. Run 2 already satisfies SC-001/SC-002/FR-012
  with real, complete verdicts on every shard; the two red shards fail for
  pre-existing, deterministic reasons a re-run cannot fix (per plan.md's own
  stop rule: run 3 is for a "fixable issue a second attempt can plausibly
  resolve," which does not describe this case). Total dispatch count for
  this mission: 2 of the operator's up-to-3 budget.

This section must be completed with real run URLs and per-shard conclusions
before the mission's PR is marked `ready-for-squad` (NFR-005).

## 2026-09-28 — real 3.13 validation (run 36393904544 on #5263)

All six shards ran on CPython 3.13.15 and finished inside their caps:
- shard 1: 13.0 of 15 min
- shard 2: 11.2 of 20 min
- shard 3: 13.2 of 25 min
- shard 4: 10.6 of 25 min
- shard 5: 22.1 of 25 min
- shard 6: 6.1 of 25 min

Shards 3, 4 and 6 are red. A local re-run of each red shard's selection on 3.13.12 and
3.11.15 gave identical failure sets (24, 11 and 13), with none that fail only on 3.13.
That is main drift (#4916, #5187, #5128) plus uid-0 permission tests. #5244's timings
had in fact been measured on 3.11. Shards 1 and 5 run at 87–88% of their caps on 3.13,
so they are the first to re-tune.
