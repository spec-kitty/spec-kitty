---
title: Test-suite parallelization — CI shard topology status
description: 'Point-in-time mission-status snapshot of the CI shard-topology re-flip and stability-ratchet confirmation state, carved out of the durable parallel-run how-to.'
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/testing/testing-parallel.md
---
# Test-suite parallelization — CI shard topology status

> **Superseded.** The `fast-tests-*` shards, `PENDING-CI` markers and `ci-quality.yml` Sonar job described here no longer exist; the modular CI from #3995 (the lean CI reinstatement: `ci-router.yml` → `ci-modules.yml` → `ci-aggregate.yml`) replaced them. See [CI gate mechanics](../../../development/reference/ci-gate-mechanics.md). Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

This note carries the point-in-time mission-status snapshots (named mission IDs, PENDING
wall-clock records, and per-job CI-confirmation state) that used to live at the bottom of
[`docs/development/testing-parallel.md`](../../../development/testing/testing-parallel.md). The durable
how-to (the one correct local command, why `--dist loadfile` is required, per-worker HOME
isolation, the serial marker passes, volume env gates, and the stability ratchet entrypoint) stays
on that page; this page is the engineering-note-shaped record of *which* shard flips have
shipped, which are still `PENDING-CI`, and what mission each traces to.

## Status: local default vs CI shard flips

- **Local parallel command — validated and safe now.** Per-worker HOME isolation
  (WP04) is in place, so the local command above runs without touching your real
  `~/.spec-kitty`. Use it today.
- **This mission's CI shard flips (`ci-test-topology-performance-01KXBJRT`,
  §"CI shard topology" below) — shipped, no real CI run yet.** Collection
  equivalence for `integration-tests-next`, `slow-tests`, and the rebalanced
  `fast-tests-core-misc` was verified locally before landing, but (unlike
  the older flips below) this branch has not yet run in real CI at all — see
  [`docs/archive/plans/testing/ci-job-timings.md`](../testing/ci-job-timings.md)
  for the honest PENDING wall-clock record, filled in once a real run
  exists.
- **Older shard flips (a separate, earlier mission: `test-suite-acceleration`,
  [`docs/archive/plans/testing/test-suite-acceleration-plan.md`](../testing/test-suite-acceleration-plan.md))
  — landed, pending 3×-green confirmation.** `fast-tests-doctrine`,
  `fast-tests-cli`, `fast-tests-charter`, `fast-tests-agent`, and
  `fast-tests-status`'s re-route each carry a `PENDING-CI` comment in
  `.github/workflows/ci-quality.yml` noting collection-equivalence was
  verified locally but three consecutive green CI runs (the stability
  ratchet, C-RATCHET below) have not yet confirmed the flip under real
  runner contention. These are a distinct, still-open item from the current
  mission and are not resolved by it. The full "≥2× faster" claim for both
  sets of flips is host-dependent; locally you should still see a clear
  speedup on a multi-core machine regardless of either flip's CI-confirmation
  status.

## CI shard topology (`ci-test-topology-performance-01KXBJRT`)

The project's PR-gating CI (`ci-quality.yml`) re-topologized its slowest jobs
in mission `ci-test-topology-performance-01KXBJRT`, generalizing the
`arch-adversarial` shard mechanism (`tests/_arch_shard_map.py` +
`tests/conftest.py`'s collection hook + a parametrized completeness guard)
into a shared **N-group registry** so `arch` and `next` are two rows of one
mechanism, not two cloned ones (FR-002/C-003).

### `integration-tests-next` — the headline `next_shard_N` matrix

Previously a single, fully-serial job (69.2 min, 441 tests, no
`-n auto`/`--durations`). It is now a 3-leg matrix
(`next_shard_1`/`next_shard_2`/`next_shard_3`, `strategy.fail-fast: false`)
driven by `tests/_next_shard_map.py`'s registration into the shared
`SHARD_GROUPS` registry, covering the same 3 roots
(`tests/next`, `tests/specify_cli/next`, `tests/runtime`) across all three
legs — the `next_shard_N` pytest marker (applied at collection time by the
shared hook), not `paths`, partitions the work. Each leg runs
`-n auto --dist loadfile -p no:cacheprovider --durations=25`. **Known gap:**
the 3-way file assignment is still WP01's placeholder greedy bin-pack (by a
`def test_` count proxy) — it has not yet been rebalanced from a real
`--durations=25` run the way `fast-tests-core-misc` below was; see
[`ci-job-timings.md`](../testing/ci-job-timings.md) §4 for the
follow-up once real per-leg minutes exist.

### `slow-tests` — narrowed paths + parallel

Path-narrowed to the directories that actually hold `@slow`-marked tests
(derived via `git grep -rl "pytest.mark.slow" tests/`), with the pre-existing
`--ignore=tests/e2e --ignore=tests/cross_cutting` pair kept verbatim, plus
`--ignore=` entries for all 4 `FIXED_RANGE_SUITES` real-port members
(structural exclusion, not marker-only — see below) and `-n auto --dist
loadfile` added. Collection-equivalence verified locally against the
pre-narrowing selection (identical 45-test set at time of writing).

### Orphan-sweep hoisted to its own concurrent job

`test_orphan_sweep.py` (the fixed-range daemon/real-port suite) used to be a
serial `-n0` *step* inside `fast-tests-sync`, sitting on that job's critical
path even though it never touched the parallel worker pool. It is now its own
job, `fast-tests-sync-orphan-sweep`, triggered by the same `sync` path filter
so it runs *concurrently* with `fast-tests-sync` instead of after it — still
serial (`-n0`, real ports are not protected by per-worker HOME isolation),
just no longer blocking a sibling job's completion. The equivalent serial
split exists on the integration side too:
`integration-tests-sync-real-port` carries the 3 other
`FIXED_RANGE_SUITES` members out of `integration-tests-sync`, which is
otherwise parallelized.

### `fast-tests-core-misc` — rebalanced 3-shard matrix

Already a shard matrix, but imbalanced (`specify-cli-rest` 12.2 min vs
`core-misc` 4.7 min). Rebalanced by splitting the heavy `specify-cli-rest`
leg's real subdirectories/files (measured via a real
`-m "fast and not windows_ci"` collect-only pass: 3241 of 6320 combined
tests) into a sibling `specify-cli-rest-2` shard — a plain path/`--ignore=`
bin-split (like the job's own existing `core-misc` residual pattern), not a
new `SHARD_GROUPS` registry row. `specify-cli-rest` keeps its
WP02-`_REQUIRED_CORE_MISC_SHARDS`-required name. Union verified unchanged
(3241 + 3079 == the pre-split 6320-test selection).

### `fast-tests-charter` / `fast-tests-agent` — split into concurrent jobs

`fast-tests-charter` (12.0 min) ran two sequential `-n auto` steps (charter,
then agent) that summed on one job's wall-clock despite each already being
parallel. `fast-tests-agent`'s historical `needs: fast-tests-charter` edge
was an ordering artifact, not a true cross-job data dependency (the two run
on separate runners with separate checkouts); it now mirrors
`fast-tests-charter`'s own upstream `needs` so both run concurrently.

### The serial `integration-tests-*` sweep

14 single-directory `integration-tests-*` jobs (`agent`, `charter`, `cli`,
`dashboard`, `doctrine`, `lanes`, `merge`, `missions`, `next`,
`post-merge`/`post_merge`, `release`, `review`, `status`, `sync`, `upgrade`)
now run `-n auto --dist loadfile -p no:cacheprovider`. `integration-tests-sync`
was split real-port-first the same way `fast-tests-sync` was: a parallel
residual plus a dedicated serial `integration-tests-sync-real-port` job.

### Real-port serial isolation is structural, not marker-only (closes #2590)

The fixed-range daemon family (`tests/_real_port_suites.FIXED_RANGE_SUITES`,
4 files under `tests/sync/` that bind `find_free_port_in_range`) is excluded
from every parallel pool with an explicit `--ignore=` entry, not just relying
on a module-level marker mismatching the job's `-m` filter — a marker-only
guarantee is not structural, and #2590 tracked exactly that gap. This is
enforced by `tests/architectural/test_serial_port_preservation.py` (GC-3,
generalized to consume the whole registry) and
`tests/architectural/test_workflow_dist_lint.py` (GC-4, C-002/C-007).

### Coverage-preservation guard (GC-2b)

Every re-topologized job's selection is checked against a **committed,
frozen pre-change baseline** of real `pytest --collect-only` node-ids
(`tests/architectural/baselines/<job>-nodeids.txt`,
`tests/architectural/test_gate_coverage.py`'s
`test_gc2b_current_selection_matches_baseline`) — 0 dropped, 0 double-run,
not merely "the same number of tests." See
[`ci-coverage-union-audit.md`](../testing/ci-coverage-union-audit.md)
for the mission's own cross-cutting run of this guard, including one found
(non-coverage) gap.

### Sonar coverage-denominator exclusions

`sonar-project.properties`' `sonar.coverage.exclusions` now removes
one-shot migration/backfill glue (`src/specify_cli/migration/**`, the
singular sibling the plural-only `**/migrations/**` `sonar.exclusions` glob
misses), non-Python dashboard assets (`**/static/**`), and thin CLI
entrypoints (`**/__main__.py`) from the coverage percentage denominator
(files stay in issue/duplication/hotspot analysis — only the coverage% is
affected). **Known drift from the original spec:** `spec.md`'s FR-012 also
named `src/specify_cli/next/**` (the 3.3.0 deprecation shim) as a 4th
exclusion target; the shipped change only carries the first 3. Re-add
`src/specify_cli/next/**` in a follow-up if it is still an uncovered
deprecation shim at merge time — do not assume this doc drift is
intentional without checking.

### UI-e2e coverage feed

`ui-e2e.yml` now runs its Playwright-driven `tests/ui/` suite with
`--cov=src/specify_cli/dashboard`, producing `coverage-ui-e2e.xml`. Two
scope decisions are documented in that file rather than silently left
incomplete:
- **Python coverage is produced but not yet Sonar-consumed** — `ci-quality.yml`'s
  `sonarcloud` job only discovers artifacts from its own workflow run
  (`download-artifact@v8`, including its `prev_run` fallback scoped to
  `workflow_id: 'ci-quality.yml'`), which cannot see an artifact uploaded by
  the separate `ui-e2e.yml` workflow run. Wiring a `ui-e2e.yml`-scoped
  download step into `ci-quality.yml`'s `sonarcloud` job is a tracked
  fast-follow, not yet done.
- **JS coverage (`dashboard.js`, ~720 lines) is deferred** — no
  Playwright-CDP or nyc/istanbul instrumentation was wired in this mission
  (judged out of budget for the job's 15-minute timeout); the interim
  mitigation is the `**/static/**` Sonar coverage exclusion above, which
  removes `dashboard.js` from the denominator rather than crediting it with
  real coverage.
