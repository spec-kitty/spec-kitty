# Mission Specification: CI Nightly Wall-Clock Budget

**Mission Branch**: `issue-4865-ci-nightly-wallclock-budget`
**Created**: 2026-09-22
**Status**: Draft
**Input**: GitHub issues #4865 (P1) and #4864 (P2), combined into one mission by
operator decision because they share the nightly CI surface, share the
`.github/ci-module-registry.yml` / `ci-shard-timings.json` measurement
infrastructure, and share a common root cause — CI wall-clock budgets that were
never derived from a fixture-aware, per-suite measurement.

## Summary

Two independent defects on the nightly CI surface, combined into one mission
because they are both symptoms of the same underlying gap (budgets/shard counts
set without fixture-aware measurement), not because they are the same
deliverable:

1. **#4865** — `.github/workflows/ci-nightly.yml`'s `performance-and-e2e` job
   (lines ~68-172) runs three independently-owned suites (`performance`, `e2e`,
   `stress`) serially inside ONE job with a single `timeout-minutes: 60` cap and
   one job-level verdict. Nightly run `35683539593` (2026-09-22) ran 65 minutes
   and was `cancelled` by the cap, truncating the stress suite before it could
   report. Because all three suites share one verdict, a genuine e2e regression
   on 2026-09-20 was indistinguishable from routine timeout cancellation.
2. **#4864** — `.github/ci-module-registry.yml`'s `charter` module row (line
   ~150) hardcodes `shard_count: 5`, but the ~27-32 minute long pole in this
   morning's charter shard run (27m20s / 27m41s / 17m37s / 21m13s / 16m22s) is
   not something the registry's own architectural gate
   (`tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent`,
   NFR-005) can actually validate, because `charter`'s committed per-test
   durations were captured with a method that structurally cannot detect skew
   for this module (see Clarifications below).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Split the nightly perf/e2e/stress job so each suite gets its own budget and verdict (Priority: P1)

As the Spec Kitty maintainer team, we want the nightly `performance`, `e2e`, and
`stress` suites to run as three independent jobs, each with its own
wall-clock budget sized to its own observed run time and its own pass/fail
verdict, so that (a) the stress suite is never truncated by a shared 60-minute
cap sized for a different suite's needs, and (b) a genuine regression in any
one suite produces a job verdict a human can act on without first
re-deriving which suite actually failed from raw log text.

**Why this priority**: P1 — the current shared job actively hides information
(#4865's core harm: 2026-09-20's genuine e2e regression was indistinguishable
from ordinary timeout cancellation) and actively loses test coverage (the
2026-09-22 run's stress suite never completed). This is the more severe of the
two issues.

**Independent Test**: Can be fully tested by dispatching `ci-nightly.yml` via
`workflow_dispatch` (`mode: full`) on this mission's branch before merge and
observing that (a) three separate job entries appear with three independent
verdicts, (b) the stress job completes without being cancelled by another
suite's budget, and (c) `tests/architectural/test_performance_marker_guard.py`
still passes (modified per FR-010 to reference the three new job names in its
three hardcoded-job-name tests, but otherwise proving no `pull_request`
trigger was introduced). This delivers value independently of User Story 2 —
it does not require any change to the module-registry shard sizing.

**Acceptance Scenarios**:

1. **Given** `ci-nightly.yml` on this mission's branch, **When** a maintainer
   reads `jobs:`, **Then** they find three independent jobs — one each for
   `performance`, `e2e`, and `stress` — each with its own `timeout-minutes`
   value sized to its own suite's observed wall-clock (not a copy of the old
   shared 60-minute cap), and no single job that runs more than one of the
   three marker-selected suites.
2. **Given** a manually dispatched nightly run on this mission's branch (`mode:
   full`), **When** the run completes, **Then** the GitHub Actions run page
   shows three separate job results for perf/e2e/stress (not one
   `performance-and-e2e` job), and the `nightly-summary` job's `needs:` list
   includes all three new job names (previously it named the single
   `performance-and-e2e` job at line ~337).
3. **Given** the dispatched run's stress job, **When** it runs the full `stress
   and not windows_ci` suite serially, **Then** it completes and reports a
   verdict (pass, fail, or "no tests collected" per the existing exit-5
   convention) rather than being cancelled mid-run by a timeout budgeted for a
   different suite.
4. **Given** `tests/architectural/test_performance_marker_guard.py` run against
   this mission's branch, **When** it inspects every workflow file for a
   `pull_request` trigger combined with `-m performance` / `-m e2e` / an
   interpreter matrix, **Then** `test_nightly_workflow_never_triggers_on_pull_request`
   and `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs`
   (the two tests this AC is actually about) still pass, proving the three new
   jobs and any workflow-level trigger changes introduce no `pull_request`
   trigger. Separately, and expectedly (FR-010), the file's three OTHER tests
   that hardcode the literal job key `"performance-and-e2e"`
   (`test_nightly_suite_steps_are_fail_loud`,
   `test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing`,
   `test_nightly_workflow_houses_performance_and_interpreter_jobs`) are edited
   to reference the three new job names and pass against them — this is
   in-scope maintenance of a stale literal, not evidence of a trigger
   regression.

**How each AC fails (falsifiability)**:

- AC1 fails if the three suites still execute inside a single job body (a
  `grep` for `uv run --frozen pytest -m` inside one job's `steps:` finds more
  than one marker selection), or if any new job's `timeout-minutes` is a bare
  copy of the old 60 (rather than re-partitioned from the 65-minute observed
  total).
- AC2 fails if the dispatched run's job list still shows one
  `performance-and-e2e` entry, or if `nightly-summary`'s `needs:` still lists
  fewer than the three new job names (the aggregator would then silently
  ignore one or more suites' results).
- AC3 fails if the dispatched run's stress job is still reported as
  `cancelled` (not `success`/`failure`) by the GitHub Actions API, or if its
  xunit report (`out/reports/xunit-nightly-stress.xml`) is missing/truncated
  because the job was killed mid-suite.
- AC4 fails if `test_nightly_workflow_never_triggers_on_pull_request` or
  `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs`
  reports a new violation naming any of the three new job names, or a new
  workflow-level trigger — that is the genuine regression this AC guards
  against. AC4 does **not** fail merely because
  `test_nightly_suite_steps_are_fail_loud`,
  `test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing`, or
  `test_nightly_workflow_houses_performance_and_interpreter_jobs` needed their
  hardcoded `"performance-and-e2e"` literal updated to the new job names
  (FR-010) — that edit is expected, in-scope maintenance, not a violation.

---

### User Story 2 - Recapture charter's shard timings with the fixture-aware tool so the skew gate is real, then re-derive shard_count (Priority: P2)

As the Spec Kitty maintainer team, we want `.github/ci-shard-timings.json`'s
`charter` entries to come from `scripts/ci/capture_shard_timings.py` (which
measures setup+call+teardown per test, serially, matching the consumer's own
selection) instead of the old ad-hoc bulk `-n auto --dist loadfile` run, so
that `test_inter_shard_skew_within_twenty_percent` (NFR-005) can actually
detect skew for `charter` instead of vacuously passing for any `shard_count`
from 1 to 4211, and so that the resulting `shard_count` in the registry is
genuinely derived from measured data rather than guessed or carried over
unchanged.

**Why this priority**: P2 — this is a correctness-of-measurement defect, not an
active outage. The nightly run still completes for `charter` today (17-32 min
per shard, under the 30-minute `module-tests.yml` per-shard timeout); the harm
is that the registry's own claim ("shard sizing is measured, never guessed")
is currently false for this module, and the gate that is supposed to catch
that is itself unable to.

**Independent Test**: Can be fully tested by running
`scripts/ci/capture_shard_timings.py --module charter --write`, then running
`uv run --frozen pytest
tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent
-q`, and confirming both that `charter`'s `module_capture_provenance` entry in
`.github/ci-shard-timings.json` is no longer `None` and that the recomputed
skew for `charter`'s (possibly revised) `shard_count` is a genuine, non-trivial
number (not ~0% regardless of `shard_count`). This delivers value
independently of User Story 1 — it does not require any change to
`ci-nightly.yml`.

**Acceptance Scenarios**:

1. **Given** a fresh capture run
   (`scripts/ci/capture_shard_timings.py --module charter --write`), **When**
   `.github/ci-shard-timings.json` is inspected, **Then**
   `module_capture_provenance["charter"]` is a populated record (run id,
   command, `captured_at`, `test_dirs`, `selection`,
   `unique_tests_measured`, `exit_code`, `producer`) instead of `None`, matching
   the shape already present for e.g. `auth`.
2. **Given** the recaptured timings, **When**
   `test_inter_shard_skew_within_twenty_percent` recomputes `charter`'s
   LPT bin-packing skew from the new per-test durations, **Then** the
   recomputed skew is a value that is sensitive to `shard_count` — i.e. it is
   not ~0% for every `shard_count` from 1 to the test count, proving the gate
   is now capable of failing for this module if a future `shard_count` change
   is wrong.
3. **Given** the recaptured, fixture-aware durations, **When** `shard_count`
   for `charter` is re-derived from them via the existing LPT skew-balancing
   method (`test_module_shard_registry.py`'s `_lpt_bin_pack`/`_skew_of`
   helpers — the genuine precedent is one of the 7 correctly-captured rows,
   e.g. `auth`; NOT the manual wall-clock÷test-count heuristic used for
   `agent`/`upgrade` in commit `349b73fc0`, which C-002 explicitly rejects as
   a precedent for this mission), **Then** the registry's `charter` row (line
   ~150) records that derived value, with a comment documenting the
   derivation basis (not silently left at the old `5` unless re-derivation
   independently lands on 5).
4. **Given** a manually dispatched nightly run on this mission's branch
   (`mode: full`) after the recapture, **When** the `full-module-matrix` job's
   `charter` shards complete, **Then** each shard's wall-clock is visible in
   the run's job list and the long pole (slowest shard) is no worse than
   before the fix, and ideally more balanced across shards than the pre-fix
   27m20s/27m41s/17m37s/21m13s/16m22s spread.

**How each AC fails (falsifiability)**:

- AC1 fails if `module_capture_provenance["charter"]` is still `None` after
  the mission's change lands, or if the capture command's `exit_code` is
  non-zero (a failed/incomplete capture).
- AC2 fails if, after recapture, `test_inter_shard_skew_within_twenty_percent`
  still computes ~0% skew for `charter` regardless of what `shard_count` is
  set to — that would mean the recapture did not actually change the
  near-uniformity of the underlying per-test durations, i.e. the gate is still
  vacuous for this module.
- AC3 fails if `shard_count` for `charter` is changed (or left unchanged)
  without a traceable derivation from the new timings — e.g. if it is bumped
  by a wall-clock÷target heuristic instead of the LPT skew-balancing method,
  which would repeat the explicitly-rejected `349b73fc0` shortcut.
- AC4 fails if the dispatched run's `charter` shards are unavailable (job
  cancelled/errored) or if the per-shard wall-clocks cannot be observed from
  the run (e.g. no artifact/log evidence to compare against the pre-fix
  spread).

---

### Edge Cases

- What happens when a nightly dispatch (`workflow_dispatch`, `mode: full`) is
  run on this mission's branch before the split lands, then again after? Both
  runs are legitimate evidence under the Verification Reality policy below;
  the "before" run documents the existing truncation/blended-verdict problem
  and the "after" run is the acceptance evidence — neither is required to wait
  for the 03:17 UTC cron or the first nightly after merge.
- How does the split handle a suite that is *skipped* (marker-empty, pytest
  exit code 5) rather than *failed*? Each of the three new jobs must preserve
  the existing "exit 0 or exit 5 both pass; only a genuine failure exit fails
  the job" convention from the current `performance-and-e2e` job's terminal
  fail-loud step — this is existing, tested behavior that the split must not
  regress.
- What happens if `charter`'s re-derived `shard_count` (User Story 2) turns
  out to still be 5, or turns out to be lower/higher than 5? Any outcome is
  acceptable as long as it is a genuine LPT-derived result from the recaptured
  timings, not a number chosen to match the old value or avoid re-plumbing
  `module-tests.yml`'s shard matrix.
- What happens to the ~110 minutes of serial test execution the `charter`
  recapture requires? This is accepted, budgeted cost (this morning's 5 shards
  already summed to ~110 min combined) — it must be sized into the plan as its
  own explicit step, not silently folded into "edit a YAML number."
- What if pre-existing test failures are encountered while running the
  `charter` recapture or while validating the perf/e2e/stress split? Per the
  charter's binding Pre-existing Failure Reporting Rule, a GitHub issue must be
  filed (command run, failure summary, why judged pre-existing) before those
  failures are treated as accepted baseline — see Clarifications, Correction
  #3.
- What happens if PR #4886 (open, touches `.github/ci-module-registry.yml`'s
  unrelated `core_misc` row) merges before this mission's PR? A merge conflict
  in the registry file is possible and must be resolved by re-applying this
  mission's `charter`-row-only change on top of upstream, not assumed away.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Split `performance-and-e2e` into three independent jobs | As a Spec Kitty maintainer, I want the nightly performance, e2e, and stress suites to run as three separate GitHub Actions jobs so that each has its own verdict and budget. | High | Open |
| FR-002 | Size each new job's `timeout-minutes` from its own observed wall-clock | As a Spec Kitty maintainer, I want each split job's timeout budget derived from that suite's own historical run time (not a copy of the old shared 60-minute cap) so stress has enough room and perf/e2e are not over-provisioned. | High | Open |
| FR-003 | Update `nightly-summary`'s `needs:` to the three new job names | As a Spec Kitty maintainer, I want the terminal aggregator job to depend on all three new jobs (replacing the single `performance-and-e2e` dependency) so the full-mode summary never silently omits a suite's result. | High | Open |
| FR-004 | Preserve the existing pass/exit-5-skip/fail-loud convention per job | As a Spec Kitty maintainer, I want each of the three new jobs to keep the `set +e` capture + `if: always()` + terminal fail-loud pattern (treating exit 0 and exit 5 as non-failing) so the split does not regress the run-all-regardless nightly posture. | High | Open |
| FR-005 | No `pull_request` trigger introduced by the split | As a Spec Kitty maintainer, I want `tests/architectural/test_performance_marker_guard.py` to keep passing after the split so none of the three new jobs (or the workflow itself) accidentally gains a `pull_request` trigger that would put `performance`/`e2e`/an interpreter matrix on the per-PR blocking path. | High | Open |
| FR-006 | Recapture `charter`'s shard timings with the fixture-aware tool | As a Spec Kitty maintainer, I want `scripts/ci/capture_shard_timings.py --module charter --write` run so `.github/ci-shard-timings.json`'s `charter` entries measure setup+call+teardown per test (matching the module's real fixture cost) instead of the stale ad-hoc bulk-run data. | High | Open |
| FR-007 | Re-derive `charter`'s `shard_count` from the recaptured timings | As a Spec Kitty maintainer, I want `.github/ci-module-registry.yml`'s `charter` row `shard_count` (line ~150) set from the recaptured, LPT-balanced data via the existing skew-derivation method, not left unchanged or bumped by a wall-clock heuristic. | High | Open |
| FR-008 | Non-vacuous skew gate for `charter` | As a Spec Kitty maintainer, I want `test_inter_shard_skew_within_twenty_percent` to be capable of failing for `charter` post-recapture (i.e. produce a real, `shard_count`-sensitive skew number), closing the defect class described in Standing Order #5, not merely re-passing by coincidence. | High | Open |
| FR-009 | Manual `workflow_dispatch` evidence before merge | As a Spec Kitty maintainer, I want both fixes exercised via a manual `workflow_dispatch` (`mode: full`) run of `ci-nightly.yml` on this mission's branch before merge, since neither fix's real acceptance criterion is provable by a unit test alone. | High | Open |
| FR-010 | Update the guard's hardcoded-job-name tests for the split | As a Spec Kitty maintainer, I want the three `tests/architectural/test_performance_marker_guard.py` tests that hardcode the literal job key `"performance-and-e2e"` (`test_nightly_suite_steps_are_fail_loud` and `test_nightly_fail_loud_step_treats_marker_empty_exit_5_as_non_failing`, both iterating `for job_name in ("performance-and-e2e", "interpreter-matrix")`, plus `test_nightly_workflow_houses_performance_and_interpreter_jobs`'s `assert "performance-and-e2e" in jobs`) updated to the three new job names (or refactored to iterate the job list dynamically) as part of this mission's diff, so the guard keeps enforcing its fail-loud/exit-5/job-presence guarantees against the post-split jobs instead of a job key FR-001 removes. This is in-scope maintenance distinct from FR-005's pull_request-trigger guarantee — see AC4/SC-004. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Independent job verdicts | Each of the three split jobs (perf/e2e/stress) must report a GitHub Actions job conclusion (`success`/`failure`/`cancelled`) that reflects ONLY that suite's own exit status — never blended with another suite's result. | Reliability | High | Open |
| NFR-002 | Stress suite completes without truncation | The stress job's `timeout-minutes` budget must be sufficient for the full `stress and not windows_ci` suite to complete under normal conditions, based on the wall-clock actually observed for stress within the 2026-09-22 65-minute combined run (the current combined job never let stress finish, so its true individual duration must be measured fresh via the dispatch evidence in FR-009, not assumed). | Performance | High | Open |
| NFR-003 | Non-vacuous inter-shard skew gate (charter) | `test_inter_shard_skew_within_twenty_percent` must be able to report a `charter` skew value other than ~0% for at least one `shard_count` in a plausible range, proving the gate can detect an imbalanced `shard_count` for this module post-recapture. Mirrors Standing Order #5's "a gate-unmask cannot self-validate" requirement. | Reliability | High | Open |
| NFR-004 | Cost of the recapture is accepted, not hidden | The ~110 minutes of serial `charter` test execution the recapture requires must be explicitly sized into the plan/tasks as its own step (evidenced by a task/WP naming it), not silently absorbed into a generic "update registry" task. | Process | Medium | Open |
| NFR-005 | 3x checkout+sync cost is accepted | Splitting into three jobs means `actions/checkout` + `uv sync --frozen --all-extras` now runs 3 times instead of once for this workflow segment; this is accepted, documented cost, not a defect to eliminate in this mission. | Performance | Low | Open |
| NFR-006 | Dispatch evidence is recorded durably, not just claimed | The pre-merge `workflow_dispatch` run's URL and each relevant job's conclusion (performance / e2e / stress for User Story 1's AC2-AC4; `full-module-matrix`'s `charter` shards for User Story 2's AC4) must be recorded in the PR description or a dedicated review-evidence location (e.g. a mission tracer file) before the mission is considered complete, and the stress job's xunit report (`out/reports/xunit-nightly-stress.xml`) existence must be confirmed as part of that evidence — not left as a verbal claim a later reviewer has to trust. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No `pull_request` trigger anywhere in the split | None of the three new jobs, and no workflow-level trigger change, may cause `ci-nightly.yml` (or any workflow) to run `-m performance` / `-m e2e` / an interpreter matrix on a `pull_request` event. Enforced by `tests/architectural/test_performance_marker_guard.py`. | Technical | High | Open |
| C-002 | Charter recapture uses the purpose-built tool only | The `charter` shard-timings recapture MUST use `scripts/ci/capture_shard_timings.py --module charter --write`. The manual wall-clock÷target heuristic used for `agent`/`upgrade` in commit `349b73fc0` is explicitly rejected as a precedent for this mission (see Clarifications). | Technical | High | Open |
| C-003 | Scope boundary — only `charter` is recaptured | Of the 21 registry modules, only 7 (`auth`, `ci`, `dashboard`, `merge`, `specify_cli_runtime`, `status`, `unit`) have ever been captured with the correct tool. 14 are stale, including `charter` (fixed here) and 13 others (`agent`, `cli`, `core_misc`, `execution_context`, `glossary`, `kernel`, `lanes`, `missions`, `next`, `post_merge`, `release`, `review`, `upgrade`). Recapturing those 13 is explicitly OUT OF SCOPE for this mission; per Standing Order (no follow-up issues — fold, escalate, or ledger), this scope boundary is recorded here for ledgering at mission exit, not filed as a new GitHub issue. | Business | High | Open |
| C-004 | Locality of change — registry edit scoped to the `charter` row | The `.github/ci-module-registry.yml` edit for this mission touches only the `charter` module's row (and its `shard_count` comment). Pre-existing format drift or other rows' staleness elsewhere in the file is out of scope for this mission's diff. This explicitly includes the four other disposition-ledger `reason:` comments in the same file (around lines 622, 641, 669, 692) and the comment in `tests/e2e/test_worktree_owned_root_concurrency.py:377` that name `performance-and-e2e` as the marker home for excluded test directories — after FR-001's split these comments describe a job that no longer exists, and that documentation drift is accepted as out-of-scope prose for this mission, not fixed here. | Technical | Medium | Open |
| C-005 | `ruff format --check .` is enforced, but repo-wide drift is not this mission's to fix | This checkout enforces `ruff format --check .` repo-wide (`ci-quality.yml`/`ci-router.yml`, `tests/architectural/test_ruff_format_enforcement.py`). This mission's changed files must pass it; pre-existing repo-wide format drift elsewhere is out of scope. | Technical | Medium | Open |
| C-006 | diff-cover ≥90% (ci-aggregate.yml) | The per-PR diff-cover gate in `ci-aggregate.yml` applies to this mission's diff like any other; since the changes are CI workflow/registry YAML plus the tooling-generated timings JSON, the plan phase must confirm how (or whether) this gate applies to non-Python diff lines. | Technical | Medium | Open |
| C-007 | SonarCloud `sonar-pr` is reported, not required | The `sonar-pr` job in `ci-aggregate.yml` runs `continue-on-error` and is excluded from the terminal `aggregate-gate`; this mission is aware of it but does not need to satisfy it as a blocking gate. | Technical | Low | Open |

### Key Entities

- **Nightly job (post-split)**: one of three independent GitHub Actions jobs
  (`performance`, `e2e`, `stress`) in `ci-nightly.yml`, each with its own
  `timeout-minutes`, its own checkout/sync steps, its own `set +e` capture +
  fail-loud terminal step, and its own job-level conclusion consumed by
  `nightly-summary`'s `needs:` list.
- **`ci-shard-timings.json` entry**: a per-module record of measured per-test
  durations plus a `module_capture_provenance` record (run id, command,
  `captured_at`, `test_dirs`, `selection`, `unique_tests_measured`,
  `exit_code`, `producer`) proving how the durations were measured. `charter`'s
  provenance is currently `None` (never captured via
  `capture_shard_timings.py`); this mission populates it.
  `.github/ci-module-registry.yml` row: one module's CI test-matrix
  configuration (`roots`, `cov_targets`, `tier`, `shard_count`, optional
  `test_dirs`). `charter`'s `shard_count: 5` (line ~150) is re-derived by this
  mission from recaptured timings.

## Clarifications / Decisions

This section records binding operator decisions, verified corrections, and the
key vacuous-gate finding as durable spec content — not only as prompt context,
which is lost when a session's context rolls.

### Binding operator decisions

1. **#4865 → SPLIT the job, do not raise the timeout.** `performance-and-e2e`
   is split into three independent jobs (perf / e2e / stress), each with its
   own `timeout-minutes` sized to its own observed wall-clock (the current
   65-minute combined total must be re-partitioned, not copied to each new
   job). Raising the single job's cap (e.g. to 90-120 minutes) was explicitly
   considered and **rejected as a half-fix**: it would leave the three suites'
   failure causes blended into one job verdict, which is the exact harm
   evidenced by 2026-09-20's e2e regression being indistinguishable from a
   timeout. Accepted downstream effects: (a) each new job repeats
   `actions/checkout` + `uv sync --frozen --all-extras`, paid 3x instead of
   once — acceptable cost (NFR-005); (b) `nightly-summary`'s `needs:` list
   (currently `[performance-and-e2e, interpreter-matrix, full-module-matrix]`
   at line ~337) must grow to include all three new job names (FR-003); (c)
   the split must not introduce a `pull_request` trigger on any of the three
   new jobs or at the workflow level — this is a hard constraint/AC (C-001,
   FR-005), not just a note, enforced by
   `tests/architectural/test_performance_marker_guard.py`.

2. **#4864 → RECAPTURE properly; the heuristic shortcut is explicitly
   rejected.** Run `scripts/ci/capture_shard_timings.py --module charter
   --write` (fixture-aware: measures setup+call+teardown, serially, purpose-
   built for exactly this fixture-dominated-module failure mode — its own
   docstring names `tests/upgrade` as the standing example), then re-derive
   `shard_count` from that real data via the existing
   `test_inter_shard_skew_within_twenty_percent` gate. The ~110 minutes of
   serial test execution this requires (this morning's 5 `charter` shards
   summed to ~110 min) is accepted cost, sized into the plan as its own real
   step (NFR-004), not folded silently into "edit a YAML number." The
   heuristic shortcut used for `agent`/`upgrade` in commit `349b73fc0` (bump
   shard count by wall-clock÷target, skip recapture) is **explicitly
   rejected** as a precedent for this mission (C-002), because it would leave
   NFR-005's "measured, not guessed" claim false for `charter` too, exactly as
   it remains false for `agent`/`upgrade` today.

### Scope boundary (binding)

Only 7 of the registry's 21 modules (`auth`, `ci`, `dashboard`, `merge`,
`specify_cli_runtime`, `status`, `unit`) have ever been captured with the
correct tool. 14 are stale, including `charter` (fixed by this mission) plus
13 others (`agent`, `cli`, `core_misc`, `execution_context`, `glossary`,
`kernel`, `lanes`, `missions`, `next`, `post_merge`, `release`, `review`,
`upgrade`).
**Recapturing those other 13 is explicitly out of scope for this mission**
(C-003). Per this project's standing charter order, no follow-up GitHub issue
is opened for that broader gap — it is folded, escalated internally, or
ledgered by the orchestrator on mission exit. This boundary is stated here so
a later reader, or an R1-R6 reviewer, does not read the vacuous-gate finding
below as license to recapture every stale module in this mission.

### The vacuous-gate finding (Standing Order #5 tie-in)

`charter`'s committed per-test durations in `.github/ci-shard-timings.json`
came from an old ad-hoc bulk `-n auto --dist loadfile` run —
`module_capture_provenance["charter"]` is `None`, confirmed by direct
inspection of the committed JSON, never captured via the purpose-built
`scripts/ci/capture_shard_timings.py`. That bulk method measures only
pytest's **call phase**, excluding fixture-setup cost. Because `charter`'s
4211 measured per-test durations are near-uniform (mean ~0.098s, summing to
only ~411s), the LPT bin-packing skew computation
`test_inter_shard_skew_within_twenty_percent` performs returns **~0% skew for
ANY `shard_count` from 1 to 4211** — the ≤20% skew gate (NFR-005) is
**mathematically vacuous for this module**: it cannot fail, and it cannot
validate a new `shard_count` either.

This exactly mirrors a defect the repo already diagnosed and fixed twice for
`agent`/`upgrade` (commit `349b73fc0`, see the `agent` and `upgrade` rows'
comments in `.github/ci-module-registry.yml`) — but that fix used a manual
test-count heuristic that **bypassed the timings file entirely**, and is
explicitly rejected as a precedent for this mission (see binding decision #2
above), because it would leave the registry's own "shard sizing is measured,
never guessed, never from file counts" claim (NFR-005, restated in the
registry's own `description:` header) false for `charter`, exactly as it is
currently false for `agent`/`upgrade`.

**Charter tie-in.** `.kittify/charter/charter.md` Quality & Tech-Debt Standing
Order #5, "Architectural gate discipline": *"Close defect classes by
construction with a NON-VACUOUS call-site gate (concrete floor + self-mutation
test + shrink-only allowlist); a gate-unmask cannot self-validate."* This
mission treats non-vacuity of the `charter` skew gate as a charter obligation
(FR-008, NFR-003), not an optional nice-to-have: recapturing `charter`'s
timings with the fixture-aware tool is what turns the existing gate from
vacuous back into a real check for this module.

### Corrections (verified first-hand by the orchestrator before this spec was written)

1. `pytestarch` imports fine in this checkout after `uv sync --frozen
   --all-extras`. An earlier readiness report's claim of a broken import was a
   stale-venv false red (per CLAUDE.md's documented category-4 gotcha). No
   remediation for it is planned in this spec.
2. GitHub issue #3284 ("23 untracked failures on main") is CLOSED and stale as
   a cited baseline. This mission calls for the pre-existing-failure baseline
   to be measured fresh at mission start (e.g. `uv run --frozen pytest tests/
   -q` or the relevant scoped subset, recorded before any change lands), not
   quoted from #3284 or any other old source.
3. This repo's charter carries a binding Pre-existing Failure Reporting Rule:
   if pre-existing failures are encountered during this mission, a GitHub
   issue MUST be filed (command run, failure summary, why judged pre-existing)
   BEFORE those failures are treated as accepted baseline. This is the one
   sanctioned exception to the "no follow-up issues" scope rule — noted here
   as a possible/conditional action during implementation, not something to
   do unconditionally now.
4. `ruff format --check .` IS enforced in this checkout (CI's
   `ci-quality.yml`/`ci-router.yml` run it repo-wide;
   `tests/architectural/test_ruff_format_enforcement.py` enforces it in `make
   test-full`, #3952) — not merely advisory. Pre-existing repo-wide format
   drift is not swept into this mission's diff (C-005, locality of change).
5. SonarCloud's `sonar-pr` job in `ci-aggregate.yml` DOES run on
   PR-triggered runs (#3993, #4334); it is `continue-on-error` and excluded
   from the terminal `aggregate-gate`, so it is reported, not required (C-007)
   — this mission is aware of it but does not need to satisfy it as blocking.
6. `ci-aggregate.yml` additionally enforces a per-PR diff-cover ≥90% gate
   (C-006).
7. Open PR #4886 also touches `.github/ci-module-registry.yml`, but only an
   unrelated, distant `core_misc` row (`test_dirs` addition) — low collision
   risk with this mission's `charter`-row-only edit, but a guaranteed clean
   merge is not assumed (see Edge Cases).
8. The mission scaffold's auto-commit (`2c9f9ef38`) is known
   commitlint-invalid / terminology-canon-violating. This is handled at
   PR-prep time by a later phase, not amended here, and not mentioned as a fix
   target in this spec's scope.

### Verification reality (must not be hand-waved)

Neither fix's real acceptance criterion — stress completes without
truncation; a genuine e2e/perf/stress regression produces a verdict
distinguishable from a timeout; `charter`'s long pole and shard skew are now
genuinely measured/balanced — can be proven by a unit test alone. The natural
feedback loop is a nightly run. `ci-nightly.yml` supports `workflow_dispatch`
(with a `mode` input, default `full`), so a manual dispatch of the workflow on
the PR/mission branch **before merge** is a legitimate, available evidence
path (FR-009) — not limited to waiting for the 03:17 UTC cron or the first
nightly after merge. Every acceptance criterion above states explicitly how it
fails, per this policy — see the "How each AC fails" subsections under both
user stories.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A manually dispatched `ci-nightly.yml` run (`workflow_dispatch`,
  `mode: full`) on this mission's branch shows three independent job entries
  (perf / e2e / stress) in place of the single `performance-and-e2e` job, each
  with its own conclusion.
- **SC-002**: In that same dispatched run, the stress job's conclusion is
  `success` or `failure` (a real verdict from a completed run), never
  `cancelled` due to another suite's timeout budget.
- **SC-003**: `nightly-summary`'s `needs:` list contains all three new job
  names (verifiable by reading `ci-nightly.yml` directly), and the summary
  step's echoed output reports a result line for each of the three.
- **SC-004**: `tests/architectural/test_performance_marker_guard.py` is
  modified (per FR-010, updating the three hardcoded-`"performance-and-e2e"`
  tests to the new job names) and still passes, still enforcing the same
  pull_request-trigger-detection guarantee: zero new violations from
  `test_nightly_workflow_never_triggers_on_pull_request` and
  `test_no_pull_request_workflow_selects_performance_or_interpreter_jobs`.
  The file is not expected to be "unchanged" — only to keep enforcing the
  same guarantee.
- **SC-005**: `.github/ci-shard-timings.json`'s
  `module_capture_provenance["charter"]` is a populated record (not `None`)
  after the recapture, matching the shape of existing populated entries (e.g.
  `auth`).
- **SC-006**: `tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent`
  passes for `charter` post-recapture, AND the recomputed skew value for
  `charter`'s shard_count is demonstrably sensitive to `shard_count`. Because
  the test's own pass condition is an aggregate `checked_multi_shard >= 1`
  across all 21 registry modules — it already passes today regardless of
  whether `charter` specifically becomes non-vacuous — the test alone is not
  sufficient proof. A manual spot-check during plan/implement verification,
  run with `charter`'s genuinely derived `shard_count` AND with at least one
  deliberately-wrong `shard_count`, must have its command and both recomputed
  skew values recorded as durable evidence (the PR description, a task/WP
  completion note, or a comment alongside the `charter` row in
  `.github/ci-module-registry.yml`) — not left uncommitted — showing a
  non-zero skew for the wrong value and proving the gate can now fail for
  this module. Optionally, a narrow `charter`-specific unit test asserting
  `charter`'s own recomputed skew is non-zero for its derived `shard_count`
  would be a stronger, re-runnable alternative proof, but is not required.
- **SC-007**: `.github/ci-module-registry.yml`'s `charter` row `shard_count`
  is set to a value traceably derived from the recaptured timings (documented
  in a code comment analogous to the `agent`/`upgrade` rows), not left at the
  prior `5` by default without re-derivation, and not set via the rejected
  wall-clock÷target heuristic.
- **SC-008**: No pre-existing failure is silently absorbed as this mission's
  own baseline without a filed GitHub issue, per the charter's Pre-existing
  Failure Reporting Rule (conditional — only applies if pre-existing failures
  are actually encountered).
