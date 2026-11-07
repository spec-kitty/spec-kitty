# REASONS Canvas — corpus-advisory-budget-01M6P49E

## Requirements

One sentence: the advisory corpus job's budget must be the one its measured worst case implies, and a
budget expiry must read as an incomplete advisory run rather than as a failing test (#7206, #4437).

- **Problem**: `built-in-corpus-suite` runs at `timeout-minutes: 20` while its measured p95 is 20.3
  min (102 % of the cap). A PR-unrelated run therefore reads red on `gh pr checks` for landing
  reasons no one can attribute, and the log ends at `The operation was canceled.` with the suite at
  97 % and no failing test.
- **Acceptance criteria**: see `spec.md` FR-001..FR-007 and SC-001..SC-004. Must (Safeguards): the
  selection semantics are byte-identical (marker, deselects, `continue-on-error`, trigger, exclusion
  from `packs-gate.needs`); the cap is derived by the repository's own #5378 formula and enforced by
  a guard that fails on the pre-fix value; an unfinished run never reads green. Should (Norms): the
  measured decomposition and the rejected alternatives live next to the cap. May (Approach options):
  parallelizing the wall-clock policy scanner, dropping `--cov=charter.offering`, a larger runner —
  all out of scope, deferred.
- **Definition of done**: a cap guard that is red on `main` and green with the change (with mutation
  controls); the recorded headroom line on the job; a step budget below the job cap with a legible
  notice; the docs and a per-PR changelog fragment; every existing live guard over the lane green.

## Entities

One sentence: the domain concepts are the advisory job, its declared budget, the recorded headroom
record, and the derived cap the guard enforces.

- **Advisory corpus job** (`built-in-corpus-suite` in `.github/workflows/packs.yml`): the sole
  advisory owner of `-m "corpus and not windows_ci"`; `continue-on-error: true`, outside
  `packs-gate.needs`.
- **Declared budget**: the job-level `timeout-minutes` and the suite step's own `timeout-minutes`.
- **Headroom record**: the structured comment above `timeout-minutes` carrying the measured maximum
  suite wall-clock, the run window and the formula (#5378).
- **Cap guard** (`tests/ci/test_nightly_timeout_headroom.py`, extended): the check that turns the
  record into a required cap for this job as it already does for the nightly and module workflows.
- **Measured decomposition**: collection / policy scan / test execution, the evidence that decides
  which fixes are available.

## Approach

One sentence: derive the cap from the measurement with the existing convention, and make the failure
mode legible, instead of narrowing the lane's selection to buy time.

- **Chosen**: record `max-suite>=19:55` and set `timeout-minutes: 31` (= `ceil((19:55 + 0:30) ×
  1.5)`), extend the existing cap guard to this job, add a suite-step `timeout-minutes` below the cap
  so the `if: failure()` notice always runs, and make that notice say the run is incomplete and
  advisory. p95 ÷ cap = 65 % ≤ the issue's 75 % criterion.
- **Rejected**: a path shard or matrix of the `-m corpus` selection — `tests/ci/test_corpus_blocking_home.py`
  requires the advisory lane to select a corpus test at any path (#3008) and
  `tests/ci/test_contracts_routing.py` requires exactly one pytest invocation, so sharding would
  trade coverage for time. Rejected: raising the cap with no recorded derivation (the issue asks for
  a rationale). Rejected: removing the wall-clock policy scan or the coverage flag from the job
  (both weaken what the lane proves).

## Structure

One sentence: one workflow file plus the guard that already owns cap derivation.

- `.github/workflows/packs.yml`: the corpus job's headroom record, cap, step budget, notice and
  rationale comment; the pytest command itself is untouched.
- `tests/ci/test_nightly_timeout_headroom.py`: gains `packs.yml::built-in-corpus-suite` as a pinned
  target (generalized from two hard-coded workflows; the existing nightly/module checks keep their
  exact behaviour).
- `tests/ci/test_corpus_suite_budget.py` (new): the step-budget and notice-legibility guards.
- `docs/development/reference/ci-gate-mechanics.md`: the advisory lane's budget and its derivation,
  next to the ownership statement it already carries.

## Norms

One sentence: the lane stays advisory, honest, and cheap to verify.

- No gate is skipped, xfailed or weakened; `continue-on-error` stays job-level so the advisory
  verdict surface is unchanged.
- Guards read workflow text only (`fast` tier, no collection, no CI run).
- The rationale lives with the value it explains, not in a PR description that decays.

## Safeguards

One sentence: every failure direction is louder than silence.

- Lowering the cap without re-recording a smaller measured max fails the guard.
- Recording a larger max without raising the cap fails the guard.
- A killed run is never green: the notice fires and the job conclusion stays non-success.
- The pre-existing guards (`test_corpus_blocking_home.py`, `test_contracts_routing.py`,
  `test_xdist_worker_policy.py`, `test_ci_corpus_trigger_completeness.py`) run unchanged and prove
  the selection semantics did not move.

## Options

One sentence: three measured levers were available; one is proportionate now.

- **Chosen now**: derived cap + legibility (no coverage trade, no scanner refactor).
- **Deferred**: parallelizing the wall-clock assertion scan (2 727-line policy scanner used by every
  pytest job), dropping `--cov=charter.offering` from the lane, and a larger runner — each is a
  separate maintainer decision, named in the PR's `## Deferred`.

## Needs

One sentence: nothing outside this repository.

- The measurement is reproducible from the Actions API and job logs (runs and jobs are named in
  `research.md`); no secret, no new dependency, no CI-runner change.

## Steps

One sentence: guard first, then the workflow, then the docs and the fragment.

1. Extend the cap guard to `packs.yml::built-in-corpus-suite` and show it red on the current cap.
2. Record the headroom line, derive the cap to 31, add the step budget and the legible notice.
3. Add the step-budget/notice guards and mutation controls.
4. Update the reference doc and add the changelog fragment.
5. Run the guards, the touched `tests/ci` files and the lane's existing invariants; open the PR.
