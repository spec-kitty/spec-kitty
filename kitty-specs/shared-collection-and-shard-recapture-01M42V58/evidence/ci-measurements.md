# Evidence: per-PR CI measurements

Pull request #5688 (PR). Values are read from the job logs and the jobs API; a cell that has not been observed says `pending`.

## Run 1: commit `77d75cca33`, 2026-10-04

Workflow runs 37209872517 (`ci-router.yml`) and 37209872825 (`ci-modules.yml`), both `pull_request` events. All 36 checks passed; 7 were skipped by path routing.

| Job | Pre-test step outcome | Pre-test step seconds | Later requests that reused | Collecting test setup (slowest) | `check` verdict | Job duration |
|---|---|---|---|---|---|---|
| Battery leg 1/2 | `collected` / `no-record` | 187.3 | 2 | 4.90 s (`test_same_tier_uniqueness.py`) | Reuse held | 8m41s |
| Battery leg 2/2 | `collected` / `no-record` | 232.6 | 0 | none in this leg | Reuse held | 11m39s |
| `ci` module shard | `collected` / `no-record` | 89.6 | 1 | 12.36 s (`test_corpus_blocking_home.py`) | Reuse held | 7m30s |

What this run shows:

- No test collected for itself in a consuming job, and every collecting test reused the stored collection (NFR-001 holds for this run).
- Setup of the collecting tests: 4.90 s and 12.36 s (NFR-002, bound 15 s, holds for this run; the first-draft bound of 10 s would have been missed by the `ci` shard).
- Pre-test step: 89.6, 187.3 and 232.6 s (NFR-003, bound 320 s, holds for this run; the first-draft bound of 90 s would have been missed by both battery legs). Collecting on a CI runner takes three to four minutes; the planning figure of 35–45 s was wrong.
- The cost of collecting did not go down. It moved out of the test, where it counted against the 180 s per-test bound.
- Battery leg 2/2 ran the pre-test step with no collecting test in its partition: 232.6 s spent for nothing. Both collecting tests were in leg 1/2 on this commit, because the partition is rebalanced from timings. Fixed after this run: a leg runs the step only when its partition holds a collecting test.
- No request was bypassed for a dirty checkout. The cache save step succeeded in all three jobs; restoring on a re-run has not been observed yet.

## Run 2: commit `223781458a`, 2026-10-04

Workflow runs 37211538228 and 37211538302, first attempt. All 36 checks passed; 7 were skipped by path routing. This commit carries the leg-selection fix.

| Job | Pre-test step outcome | Pre-test step seconds | Later requests that reused | Collecting test setup (slowest) | `check` verdict | Job duration |
|---|---|---|---|---|---|---|
| Battery leg 1/2 | `collected` / `no-record` | 199.5 | 2 | 9.35 s (`test_same_tier_uniqueness.py`) | Reuse held | 11m29s |
| Battery leg 2/2 | not run: the leg holds no collecting test | n/a | n/a | n/a | not run | 9m25s |
| `ci` module shard | `collected` / `no-record` | 118.5 | 1 | 4.37 s (`test_corpus_blocking_home.py`) | Reuse held | 9m58s |

- Leg 2/2 decided it holds no collecting test and skipped the key, restore, collect, save and check steps.
- Job durations are noisy between runs: leg 1/2's pytest phase took 455 s here and 307 s in run 1 on the same selection.

## Run 3: re-run of run 2's two consuming jobs (second attempt), 2026-10-04

| Job | Cache | Pre-test step outcome | Pre-test step seconds | Later requests that reused | Collecting test setup (slowest) | `check` verdict | Job duration |
|---|---|---|---|---|---|---|---|
| Battery leg 1/2 | restored from the key saved in run 2 | `reused` | 0.578 | 2 | 4.83 s | Reuse held | 6m37s |
| `ci` module shard | restored from the key saved in run 2 | `reused` | 0.348 | 1 | 4.01 s | Reuse held | 7m45s |

- The stored collection was restored from the Actions cache and passed the consumer's verification; no collection ran in either job.
- The save step was skipped on the cache hit, as designed.

## Result against the requirements

| Requirement | Bound | Run 1 | Run 2 | Run 3 | Holds |
|---|---|---|---|---|---|
| NFR-001: no collection inside a test; every collecting test reuses | 0 collections in a test | 0 | 0 | 0 | yes |
| NFR-002: collecting test setup on the reused path | 15 s | 4.90, 12.36 | 9.35, 4.37 | 4.83, 4.01 | yes |
| NFR-003: pre-test step, first run | 320 s | 187.3, 232.6, 89.6 | 199.5, 118.5 | n/a | yes |
| NFR-003: pre-test step, restored re-run | 15 s | n/a | n/a | 0.578, 0.348 | yes |

The bounds for NFR-002 and NFR-003 were restated after run 1 (see `spec.md`). Against the first-draft bounds (10 s and 90 s), run 1 missed both and run 2 missed the 90 s bound.

Runs 1 and 2 are different commits and run 3 is a re-run, so these are three runs, not three runs of one commit.

## What each column proves

- Pre-test step outcome and later requests that reused: NFR-001, SC-001.
- Collecting test setup: NFR-002, SC-002.
- Pre-test step seconds: NFR-003.

## Not observable on a pull request

The nightly comparison job and the scheduled recapture run from the primary branch (`main`) on a schedule, so this pull request's runs do not exercise them. They are first exercised after the merge.
