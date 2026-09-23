# PR body — ci-nightly-wallclock-budget-01M34HNZ (issues #4865, #4864)

> Assembled by Wrangler Wendy (WP07) for operator review before `gh pr create`. Sourced from each
> WP's own recorded Activity Log / commit — see
> `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tracer-approach.md`'s "Evidence Summary"
> section for full per-WP citations.

## What it fixes

**#4865** — `ci-nightly.yml`'s `performance-and-e2e` job ran perf+e2e+stress serially under one
60-minute cap and one blended verdict. Split into three jobs with their own budgets: `performance`
35m, `e2e` 40m, `stress` 10m.

- Evidence of the old harm, run **35683539593**: job `cancelled` at 65m01s, stress truncated. **And
  worse** — its steps show `performance` **success**, `e2e` **success**, stress killed mid-step
  (`Run stress-marked suite`: `in_progress`), then `Upload nightly performance/e2e reports` **never
  ran** (`status: pending`). Because upload sat downstream of the suite that timed out, two
  already-passing suites had their evidence **destroyed**. Confirmed on 2 of 3 checked pre-split
  nightlies — `35683539593` (above) and `35557999753` (performance/e2e both `success`, stress
  `failure`, `Upload nightly performance/e2e reports` **`skipped`**, never ran); the third
  (`35486813855`) preserved its artifact (performance/e2e/stress all `success`, upload step
  `success`) and failed via the terminal `Fail the job if any nightly suite was red` step working
  as designed. This is stated with that precision — it does not generalise to all six red
  nightlies. (All three run/step conclusions independently re-verified by WP07 via `gh run view
  <id> --json jobs`, 2026-09-22.)
- Evidence it works, run **35756657364**: three jobs started at the same instant and returned three
  independent conclusions — `performance` **failure** 23m23s, `e2e` **success** 9m04s, `stress`
  **success** 4m44s. One suite failing while two pass is what the old job structurally could not
  express.
- Incidental win: the old job set `SPEC_KITTY_RUN_PERFORMANCE=1` at **job level**, so ~20
  `performance`-marked wall-clock cases ran in all three steps. Now scoped to `performance` alone,
  they run once. Explains stress 16m18s→4m44s and e2e 24m44s→9m04s. A `DO NOT add...` warning
  guards it at both sites in the workflow (commit `7b0cda679`).

**#4864** — filed as "rebalance charter shards (32m long pole)". **The real cause is different.**
`module-tests.yml` pairs committed durations to collected node ids **positionally** and silently
falls back to `durations = [1.0] * len(node_ids)` when lengths disagree. charter's committed list
held **4211** entries against **6156** collected — so its timings were discarded entirely and its
five shards were balanced by test **count**, not time. Observed on run 35756657364: 21m10s /
27m45s / **31m13s** / 22m20s / 24m36s — the long pole, and a ~23–32% spread against a gate that
mandates ≤20% and passed anyway.

- Fixed by recapturing with the purpose-built `scripts/ci/capture_shard_timings.py`: 4211→**6156**
  entries (== the consumer's collection), provenance recorded, `exit_code: 0`, durations now
  including fixture cost (410.8s→**1134.2s**; ≤2ms share 77.3%→**36.3%**). Took 18m59s, against a
  budgeted ~110-minute estimate.
- `shard_count` stays **5**, justified by projected per-shard wall-clock against
  `module-tests.yml`'s real `timeout-minutes: 40` via the measured ~6.72× CI/local ratio (5 shards,
  run 35756657364: 7624s CI / 1134.188s local) — **not** by skew.
- New gate `tests/architectural/test_module_length_agreement.py` asserts committed length == live
  collection, with a frozen shrink-only allowlist (20 known-mismatched modules).
- **AC4 follow-up dispatch (run 35781833461, post-recapture): honest result, not spun.** The five
  `charter` shards ran 16m02s / 27m11s / **29m57s** / 29m11s / 15m36s. The long pole (29m57s) is
  **2m16s worse** than the pre-fix spread spec.md cites (27m20s/27m41s/17m37s/21m13s/16m22s, long
  pole 27m41s) — AC4's literal "no worse than pre-fix" bar is **not met** by this dispatch, though
  it is 1m16s better than the mid-mission diagnostic run that first exposed the bug (31m13s) and
  leaves ~10 minutes of margin under `module-tests.yml`'s real 40-minute timeout. This is consistent
  with, not contradicted by, the point above: `shard_count=5` was justified by wall-clock margin,
  never by skew or by beating the pre-fix baseline (local skew stays ≈0% both before and after
  recapture, per the Decision Moment below) — the ~2x shard-to-shard spread here is CI-side runner
  variance the recapture was never positioned to fix. Full table in `tracer-approach.md`.

## Limitations

1. **FR-008 / NFR-003 / SC-006 are NOT satisfied.** The spec required the skew gate to become
   "genuinely `shard_count`-sensitive" post-recapture. It did not: skew is ~0% across the operating
   range **both before and after**, and the pre-recapture data crossed the 20% ceiling *earlier*
   (k=52, 20.1%) and *worse* (k=67: 39.4% vs 19.9%). The high-k failure is structural — the largest
   single test (20.99s) exceeding a whole ideal bin. Recorded in immutable Decision Moment
   **DM-01M3584PY5A6F79DWX1QFDHW87**.
2. **The new gate will not run on this PR.** `ci-router.yml`'s `architectural-heavy` is code-scoped
   and this PR touches no `src/`, so path-filter routing won't select it — the class issue **#3241**
   names. It *is* reached by `ci-nightly.yml mode: full`, `make test-full`, and any future
   src-touching PR, and its correctness was proven by local mutation (two independent mutation
   demonstrations, both restored clean). Severity 2, non-blocking, surfaced loudly here.
3. **charter's length agreement has no mechanism keeping it.** The next test added under
   `tests/charter` or `tests/doctrine` silently re-desyncs it and returns charter to uniform
   weighting with all gates green.
4. **20 of 21 modules remain mismatched** — only `charter` agrees. `cli` 2704 vs 682; `next` 1588
   vs 559; `core_misc` 5927 vs 3574; `status` 1702 vs 1758; and more. Frozen as a shrink-only
   baseline per charter Standing Order #2. **Out of scope by operator ruling** — this PR does not
   fix shard weighting repo-wide.

## Blast radius (plan.md, cited verbatim)

Downstream consumers of the three files this PR changes: any downstream automation naming
`performance-and-e2e` literally (a dashboard query, a Slack alert rule, a status-check
branch-protection reference, or a sibling repo's workflow watching this job's conclusion via the
GitHub API) breaks silently the moment this merges — it will simply stop finding that job name.
This repo's own `nightly-summary` and `test_performance_marker_guard.py` are the only in-repo
consumers found by grep. `team-kitty-missions` and `muster-missions` were **not found** by this
mission's own grep sweep to reference `performance-and-e2e` by name, but **neither checkout was
searched directly** (out of this worktree's reach) — flagged as an unverified-but-likely-low-risk
external surface, not silently assumed zero-risk. `.github/ci-module-registry.yml`'s `charter` row
and `.github/ci-shard-timings.json`'s `charter` entries change value only, never shape — no
consumer's parsing logic is at risk.

## PR #4886 — known collision, checked twice, clean both times

PR #4886 (`fix(init,upgrade): prove ownership before deleting operator content in mutating flows`)
touches `.github/ci-module-registry.yml`'s `core_misc` row — distant from, non-overlapping with,
this PR's `charter`-row-only edit. It merged **2026-09-22T13:48:39Z** (merge commit
`7ff43479c094337ae8709e08eac1b838ee30dfe8`), before this branch's `charter`-row edits. Checked
twice: once by WP05 (T026, mid-mission) and again by WP07 immediately pre-push (T039) —
`git diff origin/main -- .github/ci-module-registry.yml` shows only the `charter` row's comment
block changed; `core_misc` does not appear in the diff. **Outcome both times: merged-but-clean.**

## Related issues — do not conflate with our changes

- `Closes #4865` and `Closes #4864` (both required; this PR targets the default branch so they
  fire).
- **#4914** — filed by this mission:
  `test_run_consistency_check_completes_within_budget` flaky on shared runners (3.41s vs 3s limit;
  passes locally 3/3; its own docstring admits shared-runner flakiness). It is why run
  35756657364's `performance` job is red. **Not ours, not fixed, not retried-to-green.** Note: it
  is **not** why run `35781833461`'s `performance` job is red — that run's `performance` failure is
  a distinct instance of the same wall-clock-flaky-on-shared-runner family,
  `tests/specify_cli/test_doctor_doctrine.py::test_doctor_doctrine_within_budget`
  (`AssertionError: report build exceeded 4s budget: 4.972s`; passes locally 3/3 at 1.23–1.25s vs a
  4.0s budget). #4914's own test passed on that run. Not filed as a separate issue by this WP
  (out of scope) — flagged for the operator to decide: new issue, a second instance recorded on
  #4914, or leave as known shared-runner variance. **Not ours either way.**
- **#4866** — `interpreter-matrix` 3.13 leg perma-red on a stale venv. Pre-existing and identical to
  `main` (14 errors both). Assigned to a human with a concurrent mission. **Not ours.** Reproduces
  identically on run `35781833461` too (`Interrupted: 14 errors during collection`).

## A red the maintainer must know about

`npx commitlint --from origin/main --to HEAD` fails on **exactly one** commit: `2c9f9ef38` ("Add
scaffold for feature ci-nightly-wallclock-budget-01M34HNZ") (`type-empty`, `subject-empty`). It is
**tool-generated by `spec-kitty agent mission create`**, and `commitlint.config.cjs`'s `ignores`
list covers `Add|Update (meta|spec|tasks|plan) for (feature|mission)` but not `Add scaffold for` —
ledger SK-64's documented gap. Every other commit passes. **Not fixed here**: rewording it means
rebasing ~60 commits and invalidating the review trail's commit-hash citations, and extending the
ignore list is a gate-config change out of this mission's scope. Documented here as a known red
with its cause, for the landing pass to classify.

## Tests run

- `uv run --frozen pytest tests/architectural/test_module_shard_registry.py
  tests/architectural/test_performance_marker_guard.py -q` — 28 passed (WP01 baseline).
- `make test-fast` — **1941 passed / 5 skipped**, independently re-run by WP07 at mission close
  (326.21s) — reproduces WP01's baseline exactly.
- `tests/architectural/` (full, `-m "not performance and not stress and not timing" -n auto --dist
  loadfile`) — WP06 recorded **2805 passed / 3 skipped / 2 xfailed without the new file**, **2813
  passed / 3 skipped / 2 xfailed with it**. WP07 independently re-ran the full suite (with the file
  present, as committed) and got **2813 passed / 3 skipped / 2 xfailed** (310.60s) — matches WP06's
  "with it" figure exactly. An earlier verbal telling of this mission's own baseline number ("2808
  passed / 4 skipped") does not match either WP06's committed Activity Log or this independent
  re-run and should not be quoted — the verified figures above are the real ones.
- `tests/architectural/test_module_length_agreement.py` — **8 passed**, independently re-run by
  WP07 (32.74s).
- `tests/architectural/test_module_shard_registry.py` — **17 passed**, independently re-run by
  WP07 (0.52s).
- `make format-check` — **2229 files already formatted**, independently re-run by WP07.
- `npx commitlint --from origin/main --to HEAD` — independently re-run by WP07: fails on exactly
  one commit (`2c9f9ef38`, `type-empty`/`subject-empty`), as described above.
- Known pre-existing xdist race on `test_charter_sole_door_resolver_imports.py` (scratch file
  under `src/` written by `test_topology_inference_retired.py`) — non-reproducing on immediate
  re-run, not ours.

Closes #4865
Closes #4864
