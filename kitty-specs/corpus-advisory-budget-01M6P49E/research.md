# Discovery — corpus-advisory-budget-01M6P49E

Issue: [#7206](https://github.com/spec-kitty/spec-kitty/issues/7206) — "Advisory corpus
suite job runs at its 20-minute budget and times out on unrelated PRs".
Surface: `.github/workflows/packs.yml`, job `built-in-corpus-suite`
(`built-in / -m corpus suite (advisory)`), `timeout-minutes: 20`, `continue-on-error: true`,
`needs: [changes]`, outside `packs-gate.needs`.

## D1 — The issue still reproduces on current `main` (`b4d1e918e2`)

`packs.yml` still carries `timeout-minutes: 20`. Four budget-expiry cancellations are on
record inside ~36 h (job annotations say
`The job has exceeded the maximum execution time of 20m0s`, then `The operation was canceled.`):

| run | event | job conclusion | job wall clock |
| --- | --- | --- | --- |
| 42025031565 | pull_request | cancelled (budget) | 20m16s |
| 42032240687 | pull_request | cancelled (budget) | 20m24s |
| 42042085444 | push (main) | cancelled (budget) | 20m18s |
| 41892414319 | pull_request | cancelled (budget) | 20m19s |

Not superseded: no merged PR or ADR changes the cap; `git log -S"timeout-minutes: 20"` on
`packs.yml` shows the cap unchanged since the lane was created.

## D2 — Measured duration distribution (55 advisory-job runs, 2026-11-04/05)

Durations of the advisory job across the recent `packs.yml` runs in which it actually ran
(superseded <1 min run-level cancellations excluded):

- successful: 648 s … 1154 s; the bulk at 1127–1154 s (18m47s–19m14s)
- budget-expiry cancellations: 1216–1224 s (20m16s–20m24s)
- **p95 ≈ 1218 s = 20.3 min**, i.e. **102 % of the 20-minute cap**
- p50 ≈ 766 s but only because many `skipped`/fast legs are included; the *executed*
  population clusters at 18–20 min.

The variance between a fast run (10m50s) and a slow one (19m40s) is runner load, not item
count: every run collects the same 1 624 corpus items.

## D3 — Where the 20 minutes actually goes (raw job logs)

Two per-worker timing lines make the split measurable: `policy-scan: files=… cache_hit=…
read_hash=… lock_setup=… scan_write=…` (stderr, so the timestamp is the real one — the
pytest header line is block-buffered and its log timestamp lags by minutes).

| run | event | collection | wall-clock policy scan | test execution | step total |
| --- | --- | --- | --- | --- | --- |
| 42036269868 | push | ≈ 8.0 min | 212 s (cache miss) | ≈ 6.3 min | 18m11s |
| 42030726408 | pull_request | ≈ 8.8 min | 219 s (cache miss) | ≈ 6.2 min | 19m09s |
| 42011233256 | push | ≈ 6.0 min | 0 s (cache hit) | ≈ 4.9 min | 11m35s |
| 41936048259 | push | — | cache hit | — | 14m31s |

So for a PR run (the reported failure mode):

- **collection ≈ 8 min (40 %)** — `pytest` collects the *whole* `tests/` tree (4 429 modules,
  69 099 tests) in each of the 4 xdist workers in order to run the 1 624 corpus-marked items
  (103 modules). This is the largest single cost and it is fixed, not test work.
- **policy scan ≈ 3.5 min (18 %)** — `_fail_on_wall_clock_assertions` in
  `tests/conftest.py:pytest_collection_modifyitems` runs the content-addressed
  `wall-clock-assertion-scan`. PR runs never restore that cache (deliberate: the
  `.github/actions/policy-scan-cache` trust boundary restores/publishes on the default branch
  only), so one worker scans 4 429 files while the other three block on the file lock.
- **test execution ≈ 6.3 min (31 %)** — with a long tail (88→93 % took 82 s, 93→97 % 67 s,
  97→100 % 97 s); heavy `tests/charter_offering` setups dominate.
- job overhead (checkout `fetch-depth: 0`, `uv sync`, `sync-packs`) ≈ 0.5 min.

The same fixed costs are paid by every other pytest job in the repo; they are not corpus-lane
specific and are not this issue's blast radius.

## D4 — Sharding the `-m corpus` selection is measured *and* architecturally ruled out

Sharding the selection by test path would cut collection and execution, but two existing
pinned invariants forbid narrowing this job's positional path list, and both are live guards
that would fail (they are the reason the lane is trustworthy):

1. `tests/ci/test_corpus_blocking_home.py::test_positive_control_a_corpus_test_only_packs_reaches_is_reported`
   plants a corpus test at an arbitrary path (`tests/planted_corpus/test_orphan.py`) and
   asserts the advisory Packs run selects it. The advisory lane is the one lane that reaches a
   corpus-marked test **anywhere** in the tree (#3008); a static path list silently drops the
   next one.
2. `tests/ci/test_contracts_routing.py` asserts the job runs **exactly one** pytest
   invocation (`len(gates) == 1` for `built-in-corpus-suite`), so a matrix of shard legs is
   rejected by the gate parser that models per-job selection.

Narrowing `--ignore`s instead of paths keeps invariant (1) but only removes ~38 % of the
collected modules (the corpus-bearing directories — `tests/specify_cli` alone is 1 370
modules — dominate), for ~2 min, at the cost of a second hand-maintained path encoding plus a
new drift guard. Not worth it once the cap is derived from measurement.

## Decision

Fix the budget from measurement, using the repository's own recorded-headroom convention
(`tests/ci/test_nightly_timeout_headroom.py`, #5378):

```
cap >= ceil((measured_max_suite + 0:30) * 1.5)
```

Measured max suite: the budget-expiry run 42042085444 reached 97 % at 19m39s of step time and
was killed; the slowest completed suite is 18m11s. Recording `max-suite>=19:55` gives
`ceil((19:55 + 0:30) × 1.5) = 31` minutes.

Check against the issue's acceptance criterion: p95 (20.3 min) ÷ 31 min = **65 % ≤ 75 %**. With
the current cap the same figure is 102 %.

Additionally, make a budget expiry legible instead of a bare cancellation (#4437): a
step-level `timeout-minutes` below the job cap means the existing `if: failure()` advisory
notice always runs, and that notice says the suite is **INCOMPLETE — not a test failure**.
Green still never means "tests passed that did not run": a killed run stays non-green.

## Rejected alternatives

- **Raise the cap alone, no rationale** — what the issue asks *not* to do; the cap is derived
  from a measured max and the derivation is machine-checked by the extended guard.
- **Shard by path / matrix** — see D4 (two pinned invariants, silent-drop risk for #3008).
- **Make the wall-clock policy scan parallel** — a 2 727-line policy scanner used by every
  pytest job; a scanner-speed refactor belongs in its own mission (noted in the PR's
  `## Deferred`).
- **Drop `--cov=charter.offering`** — changes reported coverage; maintainer decision, deferred.
- **Larger runner** — cost/billing decision, deferred.

## Open questions

- None blocking. The one maintainer-facing judgement is whether 1.5× the measured max is the
  right headroom factor for an advisory lane; the repo already codified that factor (#5378),
  so this mission reuses it rather than inventing another.
