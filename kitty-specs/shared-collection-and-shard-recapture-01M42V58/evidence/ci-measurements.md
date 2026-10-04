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

## Run 2

`pending` (the push that carries the leg-selection fix).

## Run 3

`pending` (a re-run of run 2's jobs, which also shows whether the stored collection is restored from the cache).

## What each column proves

- Pre-test step outcome and later requests that reused: NFR-001, SC-001.
- Collecting test setup: NFR-002, SC-002.
- Pre-test step seconds: NFR-003.

## Not observable on a pull request

The nightly comparison job and the scheduled recapture run from the primary branch (`main`) on a schedule, so this pull request's runs do not exercise them. They are first exercised after the merge.
