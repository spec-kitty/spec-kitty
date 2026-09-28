# Implementation Plan: Per-PR charter shard-timings recapture friction

**Branch**: `issue-5189-per-pr-shard-timings-recapture-friction` | **Date**: 2026-09-27 | **Spec**: `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/spec.md`
**Input**: Feature specification from `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/spec.md`, both operator rulings in `reviews/spec.ruling.md`, `tracer-approach.md`, `tracer-design-decisions.md`.

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

## Summary

**Amendment note (2026-09-28):** after this plan's original `ready` verdict, `main` was found to
carry PR #5240, which already merged a demotion mechanism for this same file ahead of this mission.
The paragraph below and item (d) are amended to absorb it — see the "Design amendment" entry in
`tracer-design-decisions.md` and `reviews/amendment.ruling.md` for the full ruling.

WP01 **absorbs** PR #5240 (`5469c4d77`, merged to `main` 2026-09-27, "ci(tests): make shard-timings
count drift non-blocking per PR (#5189 interim)"): the demotion of
`test_charter_is_not_allowlisted_and_agrees` **and** the cross-module
`test_non_allowlisted_modules_agree_with_live_collection` (both in
`tests/architectural/test_module_length_agreement.py`) from a hard per-PR failure to a visible
`ShardTimingsDriftWarning`, hard-failing again under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, is
already-merged code by the time this amendment is written. WP01 verifies that mechanism against the
merged code and adds the red-first tests #5240 itself leaves unmet, rather than reimplementing the
`_charter_disposition`/`pytest.xfail` design this plan originally specified (see item (d) for the
full replacement). Separately, add one new dedicated,
`schedule`+`workflow_dispatch`-only GitHub Actions workflow
(`.github/workflows/ci-charter-shard-recapture.yml`) that recaptures `charter`'s shard timings on a
cadence and opens a PR only when the recapture shows genuine length drift, skipping entirely
(never pushing, force-pushing, commenting, or opening anything) when a recapture PR from its one
fixed head branch (`ci/recapture-charter-shard-timings`) is already open — a plain `git push --force`
to that branch is used only in the no-open-PR path, to replace a stale (previously-closed-PR)
branch or create it fresh. All decision logic (open-PR detection,
drift comparison, the mechanism-crash/ordinary-failure distinction, the missing-secret check) lives
in one new, unit-tested script, `scripts/ci/recapture_charter_shard_timings.py`, never inline YAML.
`capture_shard_timings.py` is not modified — it already propagates a genuine mechanism exception
uncaught out of `main()`, which is exactly the signal the new wrapper needs. That same workflow
additionally runs the architectural length-agreement gates under
`SPEC_KITTY_STRICT_SHARD_TIMINGS=1` as a second, independent job — giving the exact-count invariant
a real, scheduled, hard-failing home (see item (a2)).

## Technical Context

**Language/Version**: Python 3.11+ (repo-standard).
**Primary Dependencies**: stdlib (`argparse`, `subprocess`, `json`, `os`), `gh` CLI (invoked via
`subprocess`, mirroring `scripts/ci/stale_running_sweep.py`), PyYAML (already a capture-time
dependency of `capture_shard_timings.py`), `pytest` (only as the thing being wrapped/tested, not a
new dependency).
**Storage**: `.github/ci-shard-timings.json` (existing, git-committed; no new storage).
**Testing**: `pytest`, targeted per `NO_FULL_HEAVY_SUITES_IN_MISSION` — the specific files this
mission touches/adds, never a full-directory or whole-repo sweep. See "Baseline" (item f) below.
**Target Platform**: GitHub Actions, `ubuntu-24.04` runner (matches every sibling scheduled
workflow in this repo).
**Project Type**: Single project — this is a CI-infrastructure + architectural-test-suite change
inside the existing spec-kitty monorepo, not a new component.
**Performance Goals**: The recapture job completes within its stated timeout budget (30 minutes —
see item (a)); the new, independent strict-mode job (amended 2026-09-28, item (a2)) completes
within its own 10-minute budget; the already-merged demotion mechanism (#5240) adds no new
subprocess calls beyond what it already reuses (the existing session-scoped
`_collected_counts`/`_live_timings_state` fixtures).
**Constraints**: `charter`-only scope (C-001/CL-003); never fall back to `GITHUB_TOKEN` (C-004);
`main` is PR-only (C-003); the scheduled job must be concurrency-guarded (C-006); public-repo
hygiene — no literal `/home/<user>` paths or credential values in any committed artifact (C-005).
**Scale/Scope**: One new workflow file (now two jobs — the recapture job and, per the 2026-09-28
amendment, an independent strict-mode job), one new script + its unit test file, and (amended
2026-09-28) a purely additive test-only change to one existing file — no behavioural edit, since
PR #5240 already merged the demotion mechanism ahead of this mission — adding one verification
subtask and ~5-6 new fast unit tests. **No new runtime dependency, no new package, no touched
`pyproject.toml`.**

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first**: every FR below is red-first — the new script's decision functions are pure and
  unit-tested with injected fakes (no real `gh`/`git`/`pytest.main()` calls needed to prove the
  logic). **Amended (2026-09-28):** the demotion mechanism itself is already merged (#5240,
  `ShardTimingsDriftWarning`/`_report_drift`/`_strict_mode`) — WP01 verifies it rather than
  reimplementing it, and closes the one red-first gap #5240 leaves: its own 3 new unit tests exercise
  `_report_drift`/`_strict_mode` in isolation only, never the two production gate functions
  (`test_charter_is_not_allowlisted_and_agrees` and
  `test_non_allowlisted_modules_agree_with_live_collection`) themselves, so a revert of either
  function's body to a bare hard `assert` would not be caught today. WP01 adds tests exercising both
  functions directly against a constructed disagreement (`pytest.warns(ShardTimingsDriftWarning)`), a
  strict-mode variant of each (hard `pytest.fail` under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`), and a
  missing-artefact fixture pinning `_load_timings`/`_load_registry`'s existing `pytest.fail`
  behavior — see item (d). PASS.
- **Standing Order #5 (architectural gate discipline)**: this mission *is* the operationalization of
  spec.md's "Charter Tension" section — the exact-count invariant is relocated (scheduled workflow;
  **amended (2026-09-28)**: WP03's own scheduled workflow now also runs the gate under
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` in a new, independent job, giving it a real, hard-failing
  scheduled home — item (a2)), `charter` never enters `_MISMATCH_ALLOWLIST` (unconditional assertion
  kept), the three allowlist-ratchet tests are untouched, and drift stays visible via a
  `ShardTimingsDriftWarning` (never a silent pass) on **both** live-collection gates — charter's own
  and the cross-module gate — per #5240, absorbed rather than reimplemented by WP01. PASS — see
  items (d) and Charter Tension cross-reference below.
- **Standing Order #2 (campsite cleaning)**: the one file this mission edits
  (`test_module_length_agreement.py`) plus the one unmodified file its design depends on
  (`capture_shard_timings.py`) were both read in full; no debt was found in either that is in-scope
  to this change. See item (e) — "none needed" is stated with a concrete reason, not asserted
  blindly.
- **DIRECTIVE_044 (canonical sources, no improvise)**: the new script's shape (pure decision
  functions + a thin `gh`-calling `main()` edge, module loaded by file path in its test file)
  directly mirrors `scripts/ci/stale_running_sweep.py` / `scripts/ci/release_nightly_gate.py` /
  `tests/ci/test_sonar_project_version.py` — no new pattern invented.
- **Git/workflow discipline (DIRECTIVE_045)**: the new workflow never pushes to `main` (C-003); it
  pushes only to its own fixed, dedicated branch and opens a PR for human review, consistent with
  `protect-main.yml`.
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: this plan's Baseline (item f) and every implementation-time
  test run is scoped to the specific files this mission implicates — never a bare
  `tests/architectural/` or whole-repo run.

No charter violation requires a Complexity Tracking entry (see that section below — empty by
design).

## Gate Authority (superseding stale references elsewhere)

Re-verified 2026-09-23 against `.github/workflows/` on `main` (per dispatch); this table, not any
design-pipeline overlay or review-lens text that lists commitlint, kernel/mission-loader 90%
coverage floors, Bandit/pip-audit, a blocking SonarCloud gate, or a Typer JSON error-surface gate,
is the authority for this mission. Those five are **stale** — none of them exist as enforced gates
in this repository's current CI, confirmed by reading the live workflow files, not by trusting the
overlay text:

**ENFORCED on a PR**: `ruff check` + `ruff format --check` (always-on); `uv lock --check`
(always-on); banned-API/import-boundary ruff TID251 via import-linter (always-on); `spec-kitty regen
--check` (always-on — not applicable here, see item (j)); `test_no_legacy_terminology.py`
(always-on); layer rules / pyproject shape (always-on); archive freeze (always-on); the heavy
architectural battery (`architectural-heavy`), **CODE-SCOPED by path filter** — confirmed directly
in `.github/workflows/ci-router.yml`'s `architectural-heavy` job `if:`, which ORs the `architectural`
group (`tests/architectural/**`) alongside the src-backed module groups, so this mission's edit to
`tests/architectural/test_module_length_agreement.py` triggers it; routed test groups / per-module
shards (diff-scoped — confirmed via `scripts/ci/gate_selection.py`: the `ci` registry module's
`roots` are `scripts/ci/**` and `.github/workflows/**`, so this mission's new script AND new
workflow file both select the `ci` module's shard, running `tests/ci/` — note `ci` is **not** a
`src_backed_groups` member (no `src/**` glob) and so does **not** itself gate `architectural-heavy`,
it only gates the module-test shard); diff-cover >=90% of changed lines (`ci-aggregate.yml`,
real per-PR coverage gate — satisfied here because every new function in the new script gets a
direct unit test, per item (d)); wheel build + clean-install-verification (always-on); doctrine
packs gate (path-filtered to pack sources — does **not** apply to this mission's diff, since no
`packs/**` path is touched).

**NOT enforced** (never promise these in review): commit-message lint (`commit-msg` prints only,
never fails); markdownlint (`|| true`); Bandit/pip-audit (in no workflow); mypy (in no workflow);
"kernel 90%"/"mission-loader 90%" coverage floors (no such gates exist); SonarCloud
(`sonar-pr` is `continue-on-error`, excluded from the terminal `aggregate-gate` by a `needs:`
set-equality assertion); Typer JSON error surface / `patch()` target validation / Contextive
glossary freshness (no dedicated job for any of these).

### `make ci-parity` — actual output for the current diff (honest, not fabricated)

Ran `make ci-parity` in this checkout. The diff **currently on disk** is only this mission's
planning artifacts under `kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/` — no code
change exists yet (plan phase writes no code). Its real output:

```
Selected jobs (12): archive-freeze, commit-msg, import-linter, layer-rules, markdownlint,
  prose-scan, regen-check, router-gate, ruff, terminology, tests-corpus, uv-lock
Selected code shards (0): (none)
```

This is the honest baseline for *today's* diff shape (docs/spec-only), not a fabricated preview of
the eventual code diff. Once implementation adds the three real files (an edit to
`tests/architectural/test_module_length_agreement.py`, a new `.github/workflows/*.yml`, and a new
`scripts/ci/*.py` + `tests/ci/*.py` pair), the gate table above (verified directly against
`ci-router.yml` and `.github/ci-module-registry.yml`, not `make ci-parity`'s current no-code-diff
output) predicts: `architectural-heavy` fires (via the `architectural` path-filter group), the `ci`
module's shard (`tests/ci`) fires (via the `ci` registry module's `roots` matching both
`scripts/ci/**` and `.github/workflows/**`), and `diff-cover` applies to the new script's lines. The
implementer should re-run `make ci-parity` once that diff exists and confirm it matches this
prediction, recording the real output in the PR.

## Concrete Design Decisions (dispatch items a–j)

### (a) Scheduled job placement — a NEW dedicated workflow file

**Decision**: `.github/workflows/ci-charter-shard-recapture.yml` (new file), not a job appended to
`ci-nightly.yml`.

**Why**: `ci-nightly.yml`'s own header states it is the ONLY home for the performance/e2e/stress
cadence and the interpreter matrix, with a structural guard
(`tests/architectural/test_performance_marker_guard.py`) asserting exactly what selects those
markers/matrices and that this file's own shape holds. Adding an unrelated recapture-and-open-a-PR
job risks that guard's scope and mixes concerns. More concretely, this job's authorization shape
differs from every job in that file: it needs a dedicated PAT (`CHARTER_SHARD_RECAPTURE_TOKEN`,
item (b)) checked out with write credentials so `git push`/`gh pr create` work, whereas every
`ci-nightly.yml` job today runs with the workflow-level `permissions: contents: read` plus, at most,
a job-level `issues: write` for escalation — never a repo-write credential. `ci-stale-running-sweep.yml`
is the closer structural precedent this plan follows instead: a dedicated file, its own cadence, its
own least-privilege permission set, and a thin `gh`-calling Python script under `scripts/ci/`,
unit-tested.

**Timeout budget** (same measured-evidence + ~1.5x-headroom methodology `ci-nightly.yml` uses): the
issue's own figure is `capture_shard_timings.py --module charter` taking ~18 minutes serial locally.
18 × 1.5 ≈ 27; rounded up (mirroring `ci-nightly.yml`'s own rounding, e.g. its `stress` job's 4m44s
× 1.5 → 10min) to **30 minutes**, with headroom left for checkout/`uv sync`/git-push/`gh pr create`
overhead on top of the measured capture time. This is stated explicitly as a **pre-dispatch
projection**, not a measured Actions-runtime figure — NFR-002 requires the plan to record the
actual measured in-Actions runtime once dispatched; that measurement can only happen post-merge
(see item (c)), mirroring how `ci-nightly.yml`'s own budgets were iteratively tightened after WP03's
first real dispatch. NFR-002's "measured in-Actions runtime" obligation is satisfied by deferral,
not by this plan: **this mission's own implementation PR** — the PR that lands this plan's code,
opened during `sk-implement`/normal mission review, **not** the automated, scheduled-workflow-opened
recapture PR that FR-010's fixed three-field template governs — will have its description (or
"Tests run"/notes section) updated to carry the actual measured in-Actions runtime after the first
real dispatch, not plan.md, and this 30-minute figure remains only the interim, falsifiable
pre-dispatch projection until that PR body records the real number. The
implementer/reviewer should flag this budget for revisit after the first
real scheduled or manually-dispatched run.

**Cadence**: daily, `cron: '41 4 * * *'` — off a round hour/minute, distinct from `ci-nightly.yml`'s
`17 3 * * *` and `ci-stale-running-sweep.yml`'s `23 */4 * * *`, so the three scheduled workflows do
not contend for the same runner-availability window.

### (a2) Strict-mode home for the exact-count invariant — a new job in WP03's own scheduled workflow (operator ruling point 4, amended 2026-09-28)

**Decision**: `.github/workflows/ci-charter-shard-recapture.yml` (the same workflow WP03 already
owns and creates — no new file) gets a **second, independent job** that runs the architectural
length-agreement gates under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, e.g.:

```yaml
strict-shard-timings-check:
  runs-on: ubuntu-24.04
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
    - name: Install uv
      uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
    - name: Set up environment
      run: uv sync --frozen --all-extras
    - name: Run architectural length-agreement gates under strict mode
      env:
        SPEC_KITTY_STRICT_SHARD_TIMINGS: "1"
      run: uv run --frozen pytest tests/architectural/test_module_length_agreement.py -q
```

The checkout and `Install uv`/`Set up environment` steps mirror this repo's existing
`astral-sh/setup-uv` pattern — the same pinned ref every job in `ci-nightly.yml` that runs
`uv sync`/`uv run` already uses (do not invent a different setup sequence). The job name,
`timeout-minutes: 10`, the `SPEC_KITTY_STRICT_SHARD_TIMINGS: "1"` env var, and the pytest
invocation line are the fixed, non-negotiable pieces WP03's T020 must not deviate from.

**Independence from the recapture job**: no `needs:` between this job and the existing recapture
job — the same pattern `ci-nightly.yml` itself uses for its independent `performance`/`e2e`/
`stress`/`interpreter-matrix`/`integration-next`/`specify-cli-out-of-matrix` jobs (verified directly
against that file: none of those carry a `needs:` on one another; only `full-module-matrix` needs
its own `generate-full-matrix` job, and the terminal `nightly-summary` job aggregates all of them
with `needs: [...]` + `if: always()`). Because there is no `needs:` edge, the recapture job still
runs, and can still open a fix-PR for charter drift, regardless of whether the strict-check job goes
red.

**What a red run means, and why this workflow is the right home**: this workflow already runs on
`schedule` + `workflow_dispatch` only (no `pull_request`/`push` trigger), so a failure in this new
job is a genuinely visible, hard red Actions run — the real, scheduled, hard-failing home Standing
Order #5 requires and that maintainer note 2 says is currently missing. Verified directly (not taken
on faith): nothing in `ci-nightly.yml` runs `tests/architectural` today — its `full-module-matrix`
job only expands `.github/ci-module-registry.yml`'s `modules[]` rows, and that registry's own
`out_of_matrix_test_dirs` block explicitly excludes `tests/architectural` and
`tests/architectural/tool_artifact_enrolment`, with the stated reason that their per-PR home is
`ci-router.yml`'s "architectural battery" job — a module row (or a nightly row) would only
double-run it.

**Relation to the recapture PR** (this is what "relation to the recapture PR" in the ruling asks
for, stated explicitly): if `charter` is what drifted, the strict-check job goes red **and** —
independently, in the same scheduled run — the recapture job detects the same drift and
opens/updates its fix PR: the red job is the visible alarm, the PR is the fix, and the next
scheduled run after that PR merges goes green again. If a **different** non-allowlisted module
drifts (today the only other one is `agent` — see below), the strict-check job goes red (a genuine
signal — nothing else catches this today) but the recapture job, hardcoded to `charter` only
(FR-009/C-001), does nothing about it. That is intentional — out of scope for auto-fix per CL-003 —
but now at least **visible** instead of silently unblocked.

**A red run must be triaged by test name first.** The job's `run:` step invokes the whole file
unfiltered (no `-k`/`-m`), so it also collects the three always-hard-failing allowlist-ratchet
tests (`test_allowlist_does_not_exceed_baseline`, `test_allowlisted_modules_still_genuinely_mismatch`,
`test_allowlist_entries_are_real_registry_modules`), which are unrelated to shard-timings drift. A
red run can therefore mean an unrelated pre-existing allowlist-hygiene defect instead of the two
outcomes above — whoever triages it checks which test(s) failed before assuming a drift signal.
This is a deliberate trade-off, not an oversight: the full-file run also catches a
`.github/ci-module-registry.yml`-only edit, which no per-PR job selects today (per the file's own
docstring), so scoping the invocation down to just the two demoted gate functions would close that
ambiguity at the cost of losing this coverage.

**Which modules this covers**: verified directly (not taken on the dispatch's summary on faith)
against `.github/ci-module-registry.yml` (21 `- module:` rows) and `_MISMATCH_ALLOWLIST` in
`tests/architectural/test_module_length_agreement.py` (19 entries, `_BASELINE_ALLOWLIST_COUNT = 20`)
— `charter` and `agent` are the only two registry modules NOT present in `_MISMATCH_ALLOWLIST`.
Under strict mode, both hard-fail on drift: `agent` via
`test_non_allowlisted_modules_agree_with_live_collection`'s per-module loop, `charter` via both that
same loop and its own dedicated `test_charter_is_not_allowlisted_and_agrees`. The 19 allowlisted
modules keep their existing allowlist semantics unchanged: `_find_mismatches` skips any module
present in `_MISMATCH_ALLOWLIST` regardless of the strict flag — allowlist membership and strict
mode are orthogonal axes, never coupled.

**Timeout budget**: the file's own docstring records live collection of all 21 registry modules at
~36 seconds measured locally (2026-09-22, via `.venv/bin/python`). Mirroring the same
"evidence + headroom costs nothing unless the job hangs" convention item (a)'s own 30-minute
recapture-job budget uses (and that `ci-nightly.yml`'s own cheaper jobs use, e.g. `stress`'s
10-minute budget for a ~4m44s measured run), **10 minutes** (`timeout-minutes: 10`) is chosen for
this job: ~36s measured, plus checkout/`uv sync`/environment overhead, leaves headroom well over an
order of magnitude above the measured collection time, without being large enough to mask a
genuinely hung job.

**Scope of this change — no frontmatter impact**: this is a new job inside the SAME workflow file
WP03 already owns and creates. WP03's `create_intent` (`.github/workflows/ci-charter-shard-recapture.yml`)
and `owned_files` (that file plus `docs/development/reference/known-friction-points.md`) are
**unchanged** by this addition — confirmed explicitly, since a frontmatter change would require
re-running `finalize-tasks`.

**Allowlist-ratchet interplay (operator ruling point 5, amended 2026-09-28).** A charter-only
recapture (WP02/WP03's existing mechanism) can never trip
`test_allowlisted_modules_still_genuinely_mismatch`, because that test iterates only over
`_MISMATCH_ALLOWLIST`'s own keys and `charter` is never a member of that dict —
`test_charter_is_not_allowlisted_and_agrees`'s own unconditional
`assert "charter" not in _MISMATCH_ALLOWLIST` pins that absence, unchanged by #5240. Forward-looking,
out of scope for this mission, noted for future readers per the ruling: if a future recapture ever
needs to cover an allowlisted module, that PR would need to prune
`_MISMATCH_ALLOWLIST`/`_BASELINE_ALLOWLIST_COUNT` in the same PR — a charter-only recapture never
needs to, and does not, do this.

### (b) Names — secret, branch, concurrency group, permissions, open-PR check (verbatim)

- **Secret**: `CHARTER_SHARD_RECAPTURE_TOKEN` — a dedicated PAT / GitHub App token, mirroring
  `RELEASE_NIGHTLY_DISPATCH_TOKEN`'s pattern (`release.yml`'s `nightly-gate` job). Read from the
  environment inside `scripts/ci/recapture_charter_shard_timings.py`; the workflow step sets
  `env: CHARTER_SHARD_RECAPTURE_TOKEN: ${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }}`. The presence
  check is a **truthy** test — `CHARTER_SHARD_RECAPTURE_TOKEN` counts as missing when it is unset
  **or** an empty string, because GitHub Actions injects `""` into an `env:` mapping for a
  referenced secret (`${{ secrets.NAME }}`) that does not exist as a repository secret. This
  mirrors the truthy pattern `scripts/ci/release_nightly_gate.py::resolve_token` uses (`if value:`
  after `os.environ.get(name)`), but this check must **NOT** copy that function's `GITHUB_TOKEN`
  fallback (its `for name in ("GH_TOKEN", "GITHUB_TOKEN")` loop) — falling back to `GITHUB_TOKEN`
  when `CHARTER_SHARD_RECAPTURE_TOKEN` is falsy would violate CL-002/C-004's operator decision that
  this design must never fall back to the default `GITHUB_TOKEN`. The default `GITHUB_TOKEN` is
  never read or referenced by this script for any git/`gh` operation — the same
  anti-recursion rationale `release.yml` records (a PR opened with `GITHUB_TOKEN` would not fire
  other workflows' `pull_request` events) applies identically here: the recapture PR must trigger
  the normal per-PR CI (`ci-router.yml` etc.) like any human-authored PR. **Ordering: this truthy
  check is `main()`'s very first action, full stop.** It runs, and fails loudly and exits, before
  ANY subprocess call of any kind — including the Open-PR check (verbatim) bullet's `gh pr list`
  call below — is ever made; the open-PR-check function is not invoked at all when the secret is
  missing. This is not merely "before any recapture work" (the capture-wrapper invocation) — it is
  before the open-PR check that itself authenticates with this same secret, closing the ordering
  gap a reader could otherwise infer from item (c)'s numbered sequence, which only starts once both
  the secret and the open-PR check are assumed already resolved.
- **Fixed head branch**: `ci/recapture-charter-shard-timings` — the exact name spec.md's Key
  Entities/FR-007 illustrate; adopted verbatim, no reason to deviate.
- **Stale-branch-replacement mechanism** (deferred to this plan by spec.md's Key Entities section):
  **plain `git push --force` to the fixed branch**, taken **only** in the no-open-PR path (confirmed
  by spec.md's Key Entities three-step sequence — open-PR check (1) → recapture (2) → drift check
  (3) — step (1), which found no PR open at that initial check). Chosen because it
  uniformly handles both sub-cases with one mechanism — the branch not existing yet (force-push
  creates it) and a stale branch existing with no open PR, e.g. a previously closed PR (force-push
  fully replaces its content) — without needing separate branch-existence-detection logic. This is
  explicitly **not** the case ruling 2 forecloses: ruling 2's "never force-pushes, in any case"
  guarantee is scoped to *while a PR from this branch is open*, and by construction this code path
  is only entered after confirming no such PR exists **at that point in the run**.

  **TOCTOU re-verification (narrows, but does not close, the window between the initial check and
  the push).** The initial open-PR check (spec.md's Key Entities step (1), detailed in the
  **Open-PR check (verbatim)** bullet below) runs before the ~18–30 minute capture step
  (item (a)'s timeout budget), so a PR can be opened against the fixed branch by something else
  during that multi-minute window — a check taken only once, at the start, cannot see it. The
  open-PR check (the same `gh pr list --repo <owner/repo> --head ci/recapture-charter-shard-timings
  --base main --state open --json number` call detailed in that same bullet below) is therefore
  **re-run a second time, immediately before the `git push --force` call itself** — not only at the
  start of the run. If
  that re-check now finds an open PR (one that opened during the capture window), the push is
  **aborted**: the job falls back to exactly the same skip-if-open behavior as step 1's own open-PR
  branch (writes one line to the job summary naming the newly-found PR's number, performs no
  push/force-push/commit/PR-open/comment, and exits successfully) instead of force-pushing over a PR
  that now exists. This reduces the exposure window from the original ~18–30 minute capture-step
  budget to the gap between two sequential local subprocess calls — the re-check's `gh pr list`
  process returning and the `git push --force` process starting, with no long-running operation
  between them, so the residual window is call-overhead scale (sub-second to at most a few seconds),
  not minutes. It does **not** make ruling 2 point 3's "only when no such PR is open" guarantee hold
  unconditionally at the moment of the push: the re-check and the push remain two separate,
  sequential subprocess calls, not one atomic check-and-push primitive, and no GitHub API offers an
  atomic "push only if no PR exists against this branch" primitive that would let this be
  engineered away. A PR opened in that narrow residual gap would still be silently force-pushed
  over. This residual, structurally irreducible window is an **accepted cost** — and its threat
  model is named explicitly, not left implicit: **this is not another invocation of this same
  workflow** — the Concurrency group bullet below establishes that C-006's static group already
  serializes those (a same-schedule race is exactly what that group prevents, so it cannot be the
  source of a PR appearing mid-window); **the residual actor here is any external push/PR-open
  against this repo-internal branch** (e.g. a human or another tool manually pushing to, or
  opening a PR from, the `ci/`-prefixed branch), however unlikely. This mirrors how ruling 2
  point 5 accepts a different residual cost (capture staleness while a PR sits open)
  elsewhere in this mission — not a claim of unconditional closure: the guarantee holds as of the
  re-check, with a documented, negligible residual gap after it. See fixture 7
  ("toctou-recheck-aborts-push") in item (c) below, which proves the re-check aborts correctly when
  told a PR is now open; it does not and cannot exercise the real sub-second gap between the two
  real subprocess calls, since that gap is not independently triggerable by a test.
- **Concurrency group**: `ci-charter-shard-recapture` — a plain, static group name (NOT
  `${{ github.ref }}`-suffixed, unlike `ci-nightly.yml`'s per-ref group), mirroring
  `ci-stale-running-sweep.yml`'s own static `concurrency: {group: ci-stale-running-sweep,
  cancel-in-progress: false}` shape. Static (not per-ref) is **deliberate**, kept even though this
  workflow does run against more than one ref: item (c)'s own pre-merge test strategy dispatches
  this exact workflow, via manual `workflow_dispatch`, from a topic branch's own copy of the
  workflow file — a different ref from the scheduled production run's `main` checkout — but both
  that rehearsal run and a `main`-triggered run push to the **same fixed recapture head branch**
  (`ci/recapture-charter-shard-timings`, item (b) above), because the head branch is a constant,
  never derived from the triggering ref. A **per-ref** group (`${{ github.ref }}`-suffixed, like
  `ci-nightly.yml`'s) would key the two runs' concurrency slots on *different* refs (the topic
  branch vs. `main`), letting a pre-merge rehearsal race a concurrent `main` run on the one thing
  they actually share — the fixed target branch both push to and both open-PR-check against. The
  **static** group keys both runs on the same slot regardless of triggering ref, so they correctly
  queue behind each other instead of racing FR-007's open-PR check and FR-006's drift check against
  a branch both are mutating at once — exactly C-006's concern, whichever ref triggered either run.
- **Open-PR check (verbatim)**:
  `gh pr list --repo <owner/repo> --head ci/recapture-charter-shard-timings --base main --state open --json number`
  invoked from inside the new script via `subprocess`, authenticated with `GH_TOKEN` set to the
  dedicated secret (never `GITHUB_TOKEN`). An empty JSON array means no open PR; a non-empty array's
  first element's `number` is the open PR to name in the job-summary line.
- **Permissions**: the workflow-level `permissions:` block is `permissions: {contents: read}` —
  the minimum a workflow can declare, matching `ci-nightly.yml`'s own workflow-level baseline cited
  in item (a) above. `git push`/`gh pr create` authenticate through the dedicated
  `CHARTER_SHARD_RECAPTURE_TOKEN` PAT (the Secret bullet above), never through `GITHUB_TOKEN`, so no
  job-level escalation (`contents: write`, `pull-requests: write`) is needed at the workflow level:
  `actions/checkout` only needs `contents: read`, and the PAT — not `GITHUB_TOKEN` — is what
  actually authorizes the push and PR-open calls. Granting `contents: write`/`pull-requests: write`
  here would be inert widening, not a functional requirement, so it is deliberately not granted.
- **Checkout credential mechanism (the concrete git-level wiring, not optional)**: the workflow's
  `actions/checkout` step is configured with
  `with: { token: ${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }} }` — `persist-credentials` is left at
  its default (`true`), so the checkout itself persists the PAT, not the ambient `GITHUB_TOKEN`, as
  the git remote credential for `origin`. The subsequent `git push --force` and commit-authoring
  steps therefore authenticate via that PAT-backed credential the checkout already persisted, never
  via the workflow's own ephemeral `GITHUB_TOKEN`. Without this `token:` override, `actions/checkout`
  would default to persisting the ambient `GITHUB_TOKEN` instead, and this workflow's
  `permissions: {contents: read}` block would then make a plain `git push` fail outright — or, if an
  implementer "fixed" that failure by granting `contents: write` at the workflow level instead of
  wiring the PAT into checkout, the push would succeed while silently authenticating with
  `GITHUB_TOKEN`, reintroducing exactly the GITHUB_TOKEN-authored-push behavior CL-002/C-004 forbid.
  This checkout-token override is therefore the load-bearing mechanism the Permissions bullet above
  depends on, not an optional refinement of it.

### (c) How the workflow is tested — pre-merge vs. post-merge-only

**Provable pre-merge** (this mission's actual test suite):
- Every decision function in `scripts/ci/recapture_charter_shard_timings.py` — open-PR matching,
  the length-drift comparison, and the mechanism-crash/ordinary-failure classifier — is a pure
  function taking plain data (no I/O), unit-tested in `tests/ci/test_recapture_charter_shard_timings.py`
  with injected fakes, mirroring `tests/ci/test_stale_running_sweep.py`'s `Candidate`-style pattern.
  Every required fixture (item (c) sub-bullets below) is one of these unit tests — no real `gh`,
  `git`, or `pytest.main()` call is needed to prove any of them.
- **Amended 2026-09-28**: the demotion mechanism itself is already merged (#5240) — WP01 verifies it
  and adds the red-first tests #5240 leaves unmet: two tests exercising the two production gate
  functions directly against a constructed disagreement (asserting `pytest.warns(ShardTimingsDriftWarning)`),
  a strict-mode variant proving `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` restores the hard failure at the
  integration level (not just the already-tested `_report_drift` helper), and one against the
  pre-existing `_load_timings()`/`_load_registry()` functions proving a genuine infra break still
  fails loudly — see item (d) for the full, current fixture list. No subprocess, no `slow` marker, no
  live collection needed for any of these.
- A **manual `workflow_dispatch`** against a deliberately-staled checkout (per spec.md's own
  "Independent Test" language, User Story 2) is achievable pre-merge from a topic branch once the
  workflow file and secret exist on that branch's PR — GitHub permits `workflow_dispatch` from a
  non-default branch's own copy of the workflow file when dispatched via the branch ref. This
  proves the real `gh pr list`/`git push`/`gh pr create` wiring works end-to-end, but requires the
  operator to have already created the `CHARTER_SHARD_RECAPTURE_TOKEN` secret (CL-002 — an operator
  prerequisite, not something this plan can satisfy in-repo).

**Only confirmable post-merge**:
- The actual `schedule` (cron) trigger firing on its own, since GitHub only evaluates `schedule`
  triggers on a workflow's copy on the **default branch** (`workflow_run`/`schedule` jobs are
  documented as untestable pre-merge from a PR — the same limitation this repo's own
  `docs/development/...` notes record for `workflow_run` jobs applies to `schedule`).
  Consequence: the cadence and the exact `04:41 UTC` cron firing at all is only verifiable after
  this PR merges to `main`.
- The recapture PR actually being opened against the **real** `main` (rather than a topic branch
  used for a manual-dispatch rehearsal), and that PR then correctly running the repo's normal
  per-PR CI lanes (confirming the anti-recursion PAT choice actually works in practice, not just in
  theory).

**Required fixtures** (all satisfied as pure unit tests in
`tests/ci/test_recapture_charter_shard_timings.py`, no real network/git/gh calls):

1. **skip-if-open**: a fake `gh pr list` JSON response with one open PR from the fixed branch →
   the open-PR-matching function returns that PR's number; the orchestration path that consumes it
   performs no push/commit/PR-open call (asserted by injecting a fake "would-push" callable and
   asserting it is never invoked).
2. **unrelated-PR-not-matched**: a fake `gh pr list` response is never queried by head-branch alone
   in a way that could false-positive — the test constructs an open-PR JSON payload whose `headRefName`
   is a *different* branch (the #5175/#5177 shape: an unrelated PR that also touches
   `.github/ci-shard-timings.json`) and asserts the matching function returns `None` (no match),
   even though the same JSON shape carries a PR number.
3. **no-drift-no-PR**: `has_drift(before_length=N, after_length=N)` (equal lengths, simulating that
   `--write` rewrote `run_id`/`captured_at`/duration-value noise but the list length is unchanged)
   returns `False`; the orchestration path that consumes it performs no commit/push/PR-open call.
4. **capture-failure-no-commit** (the mechanism-crash fixture from the design problem, see below):
   a fake `capture_main` callable that raises an exception → the wrapper returns a
   `mechanism_ok=False` outcome; the orchestration path that consumes it aborts before any
   commit/push/PR-open call and surfaces the caught exception's message.
5. **missing-secret-loud-failure**: two cases, both required because the truthy check (item (b)'s
   Secret bullet) must treat both as "missing" identically:
   - (a) `main()` invoked with `CHARTER_SHARD_RECAPTURE_TOKEN` set to the **empty string** `""` —
     mirroring what GitHub Actions actually injects into an `env:` mapping for a secret referenced
     via `${{ secrets.NAME }}` that does not exist as a repository secret;
   - (b) a companion case with `CHARTER_SHARD_RECAPTURE_TOKEN` **fully absent/unset** from the
     environment (deleted from `os.environ`, the "key not present at all" case).

   Both (a) and (b) must produce the **same loud, non-zero-exit failure**: a distinct non-zero exit
   code, an `::error::`-prefixed message naming the secret, and — proven via a spy/fake in place of
   the capture-wrapper callable — that callable is **never invoked at all** in either case (not
   merely "no branch/commit exists afterward", which cannot distinguish "recapture ran, then the
   check failed before commit" from "the check failed before recapture ran" — the dispatch's own
   point; asserting non-invocation of the callable closes that gap directly). The same spy/fake
   pattern is applied a second time, in the same test, to the open-PR-check callable (the function
   backing the "Open-PR check (verbatim)" bullet in item (b)): both the empty-string sub-case (a)
   and the fully-unset sub-case (b) must additionally assert that callable is **also never invoked**,
   proving the secret truthy-check fails and exits before the open-PR check is ever reached — not
   only before the capture-wrapper. Both cases must fail before any recapture work (the
   capture-wrapper invocation) **or** the open-PR check starts.
6. **drift-triggers-push** (the positive-path counterpart to fixture 3 — SC-003's actual
   deliverable, left unverified without this fixture): `has_drift(before_length=N, after_length=M)`
   with `N != M` returns `True`; the orchestration path that consumes a `True` result **DOES**
   invoke the commit/push/PR-open callable exactly once — proven via the same fake "would-push"
   callable pattern used by fixtures 1/3, asserting it **is** called (with the expected arguments)
   rather than asserting it is never called.
7. **toctou-recheck-aborts-push** (narrows the TOCTOU window described in item (b) above, per that
   item's accepted-residual-cost framing — this fixture cannot exercise the real sub-second gap
   between the two subprocess calls, only the injected-fake re-check outcome): a fake open-PR-check
   callable that returns "no PR open" on its first invocation (step 1) and "PR open, number N" on
   its second invocation (the re-check immediately before the push) → the orchestration path that
   consumes this sequence runs the capture, finds drift, but then **aborts before the
   push/commit/PR-open call** (asserted by injecting a fake "would-push" callable and asserting it
   is never invoked) and falls back to writing the job-summary line naming PR `N`, exactly mirroring
   fixture 1's skip-if-open outcome. Proves the re-verification gates the push against a PR the
   re-check itself observes, not only against the initial check's observation.
8. **mechanism-crash-via-systemexit**: a fake `capture_main` callable that raises `SystemExit(2)`
   (mirroring `capture_shard_timings.py`'s own `_parse_args` → `parser.error(...)` path, which
   raises `SystemExit`, a `BaseException` subclass — not an `Exception` subclass) → `run_capture_or_die`
   still returns `mechanism_ok=False` (the `SystemExit` never propagates uncaught out of the
   wrapper), and the orchestration path aborts before any commit/push/PR-open call, identically to
   fixture 4's `Exception`-raising case.
9. **post-write-logging-failure-fails-closed** (see "The mechanism-vs-ordinary-failure design
   problem" below): a fake `capture_main` callable that raises only *after* performing its own
   (simulated) write side effect → `run_capture_or_die` still returns `mechanism_ok=False` and the
   orchestration path aborts before any commit/push/PR-open call. This documents the deliberate,
   safe false-negative: no partial/corrupt data is ever committed or pushed, and the already-written
   local file is never re-read or trusted — the cost is an occasional missed recapture that the next
   scheduled run retries.
10. **ordinary-failure-continues** (FR-008's *second* required fixture — spec.md FR-008's own
    acceptance bar: "proving an ordinary failing measured test ... does not abort the commit/PR
    step" — the flip side of fixtures 4/8/9 above, which all prove the *mechanism-crash-aborts*
    half): a fake `capture_main` callable that returns a plain non-zero exit code (e.g. `1`)
    **without raising** → `run_capture_or_die` returns `mechanism_ok=True, pytest_exit_code=1`; the
    orchestration path that consumes this outcome proceeds to the drift check exactly as it would
    for `pytest_exit_code=0` — and, when that drift check also reports drift, on to commit/push —
    rather than aborting, proven by injecting the same fake "would-push" callable used by fixtures
    1/3/6 and asserting it **is** invoked (mirroring fixture 6's assertion style) when this outcome
    is paired with drift. This closes the gap the design-problem section (below) previously cited
    without a named, existing fixture to point at.
11. **snapshot-before-overwrite** (proves the sourcing pipeline itself — the ordering fixture
    PLAN-FRESH3-001 identifies as missing — not only the pure `has_drift(int, int)` comparator
    fixtures 3/6 above exercise): a fake `capture_main` callable that, when invoked, mutates a fake
    in-memory dict standing in for `.github/ci-shard-timings.json`'s parsed payload — appending or
    removing an entry from its `module_test_durations["charter"]` list in place, simulating the real
    `destination.write_text(...)` side effect at `capture_shard_timings.py:268,274`. The
    orchestration under test reads the fake dict's `charter` length as `before_length` **before**
    calling `run_capture_or_die(capture_main, argv)`, then — only after that call returns
    `mechanism_ok=True` — re-reads the (now-mutated) fake dict's `charter` length as `after_length`
    and calls `has_drift(before_length, after_length)`. Asserts `before_length` equals the
    pre-mutation length (never the post-mutation one) and that the resulting `has_drift` call
    correctly reports drift when the fake `capture_main` changed the list's length. This is the
    fixture that would fail if an implementer read both `before_length` and `after_length` from the
    same post-write state — a mistake none of fixtures 1–10 can catch, since none of them source
    their integers from a mutable object `capture_main` itself writes to.

### The mechanism-vs-ordinary-failure design problem — resolution

**Chosen approach: catch the exception at the call site; never trust the raw process exit code.**

`capture_shard_timings.main()`'s own body writes the merged JSON to disk (`destination.write_text`)
strictly **before** it reaches its final `return 0 if ... else 1` statement — that return statement
is only reached if `_capture_all()` (which loads the registry and runs `capture_module` for every
requested module) and `merge_capture()` both completed without raising. Therefore:

- **Any exception raised inside `_capture_all`/`capture_module`/`merge_capture`** (a malformed
  `.github/ci-module-registry.yml` raising in the registry loader, `resolve_test_dirs` raising
  `KeyError`/`FileNotFoundError`, or a crash inside the pytest-invoking machinery) propagates
  **out of `main()` before the write happens** — a genuine mechanism failure, and the write never
  occurs.
- **Any clean return from `main()`** (`0` or `1`) means the write has already happened — a `1`
  return means only that some *measured test itself* failed (`pytest.main()`'s own exit code,
  already fully recorded by `DurationRecorder` regardless of outcome), never that the mechanism
  failed to run.

**Known, accepted edge case — the "write already happened" guarantee is scoped to lines 268–274
only, and this design does not rely on anything past it.** Between the write at line 274 and the
`return` at line 282 sits an informational `print(..., file=sys.stderr)` loop (lines 276–281),
reporting on the `captures` list already fully computed by line 269 (`_capture_all(...)`) and merged
into `payload` by line 271. If that print ever raises (e.g. `BrokenPipeError`/`UnicodeEncodeError`
writing to stderr — practically unreachable on a GitHub Actions runner, whose stderr is always a
capturable pipe), the exception propagates out of `main()` exactly like a genuine pre-write
mechanism crash would, even though the merged JSON was **already written to disk**. Because
`capture_shard_timings.py` is deliberately left unmodified (item e) and `run_capture_or_die` only
observes the call site, the wrapper structurally cannot distinguish this from a real pre-write
failure. **Chosen remediation:** rather than widen `capture_shard_timings.py` itself (which item (e)
commits to not touching), this plan scopes the "write already happened" guarantee precisely to
lines 268–274 of `main()` (the existing-payload load, the capture-and-merge loop, and
`destination.write_text` itself) — not the full function body through its `return` — and states
explicitly that the new script's safety
boundary does not rely on `capture_shard_timings.main()`'s post-write print loop at all: if it ever
raises, `run_capture_or_die` conservatively reports `mechanism_ok=False` and the orchestration
aborts before any commit/push/PR-open call. This is a safe fallback, not a data-corruption risk —
nothing is ever committed or pushed based on the already-written local file, which is never re-read
or trusted — at the cost of an occasional missed recapture for that one scheduled run; the next
scheduled run retries from a clean state. See fixture 9 ("post-write-logging-failure-fails-closed")
in item (c) above.

So the raw process exit code is ambiguous only if `capture_shard_timings.py` were invoked as a
**subprocess** and its exit code trusted directly (an uncaught exception also exits the Python
interpreter with code 1 via the `__main__` traceback path — the same code a clean `return 1` would
produce). The fix is therefore: **never invoke it as a subprocess; call `capture_shard_timings.main(argv)`
directly, in-process, inside a `try`/`except (Exception, SystemExit)` in the new script**, and
classify:

```python
@dataclass(frozen=True)
class CaptureOutcome:
    mechanism_ok: bool
    pytest_exit_code: int | None
    error: str | None

def run_capture_or_die(capture_main: Callable[[list[str]], int], argv: list[str]) -> CaptureOutcome:
    try:
        exit_code = capture_main(argv)
    except KeyboardInterrupt:
        raise
    except (Exception, SystemExit) as exc:
        # Deliberately broad: ANY uncaught exception from the mechanism is a crash -- AND so is a
        # SystemExit, which Exception alone would miss (argparse's parser.error() raises SystemExit,
        # a BaseException subclass, not an Exception subclass; a wrapper-side argv bug or a
        # misbehaving conftest could otherwise crash the whole process uncaught instead of degrading
        # to mechanism_ok=False). KeyboardInterrupt is re-raised, never swallowed as a mechanism crash.
        return CaptureOutcome(mechanism_ok=False, pytest_exit_code=None, error=str(exc))
    return CaptureOutcome(mechanism_ok=True, pytest_exit_code=exit_code, error=None)
```

`mechanism_ok=False` aborts before any commit/push/PR-open step (fixtures 4, 8, and 9 in item (c)
above — FR-008's "mechanism-crash-aborts" half). `mechanism_ok=True` proceeds to the drift check
**regardless of `pytest_exit_code`** (fixture 10, "ordinary-failure-continues", in item (c)
above — FR-008's "ordinary failing test does not abort" half) — this is exactly
consistent with the currently-committed `module_capture_provenance.charter.exit_code: 1` entry
already in `.github/ci-shard-timings.json` today (a real, currently-accepted case of "some measured
test failed, but the mechanism succeeded and the data is trustworthy").

**Snapshot-then-capture-then-compare — where `before_length`/`after_length` actually come from.**
`has_drift(before_length, after_length)` (item (c) fixtures 3/6, FR-006) is a pure comparator over
two integers the orchestration must source correctly, and `capture_shard_timings.py`'s own `main()`
overwrites `.github/ci-shard-timings.json` in place as a side effect of the very call that produces
`after_length` (the pre-existing payload is loaded at line 268, then `destination.write_text(...)`
at line 274 replaces it when `--write` is passed). Reading the file only after calling
`capture_main`/`run_capture_or_die` would therefore read the *already-overwritten* value for both
`before_length` and `after_length`, computing `before_length == after_length` unconditionally on
every run. The orchestration in `scripts/ci/recapture_charter_shard_timings.py`'s `main()` MUST
therefore sequence as follows, and never in any other order:

1. **Before** calling `run_capture_or_die` at all, read `.github/ci-shard-timings.json` (the file
   on disk, pre-recapture) and extract `len(payload["module_test_durations"]["charter"])`, holding
   it as `before_length`.
2. Call `run_capture_or_die(capture_main, argv)` with `argv` containing `--module charter --write`
   (the wrapper from the code sketch above) — this is the call that overwrites
   `.github/ci-shard-timings.json` in place as its side effect.
3. Only when the returned `CaptureOutcome.mechanism_ok` is `True`, re-read
   `.github/ci-shard-timings.json` (now the freshly-written file) and extract the same `charter`
   length as `after_length`, then call `has_drift(before_length, after_length)` to decide whether to
   commit/push/open a PR. `mechanism_ok=False` short-circuits before this re-read — there is nothing
   trustworthy to compare against (fixtures 4/8/9).

The working-tree read in step 1 is sufficient (the checkout should be clean immediately after
`actions/checkout`); `git show HEAD:.github/ci-shard-timings.json` remains available as a defensive
alternative the implementer may choose instead, but is not required. See fixture 11 in item (c)
above, which proves this ordering directly against a fake `capture_main` that mutates a fake
filesystem/dict in place, rather than only exercising `has_drift` as a pure `(int, int)` comparator.

This logic lives in `run_capture_or_die`, a new function in `scripts/ci/recapture_charter_shard_timings.py`,
tested directly in `tests/ci/test_recapture_charter_shard_timings.py` by injecting a fake
`capture_main` that raises vs. one that returns `0`/`1` — no real pytest subprocess needed. This is
the "wrap the invocation so a genuine exception is caught and mapped to a distinct sentinel/exit
code" approach from the two alternatives offered, chosen over provenance/`run_id`-diffing because
it requires no extra file re-read round-trip and is directly, cheaply unit-testable via dependency
injection alone.

### (d) Red-first fixtures per changed behaviour

**FR-001/FR-002/FR-004 (demotion + visible drift + infra-crash-still-fails) — amended 2026-09-28:
already implemented by #5240, absorbed rather than reimplemented.**

PR #5240 (`5469c4d77`, merged to `main` 2026-09-27, "ci(tests): make shard-timings count drift
non-blocking per PR (#5189 interim)") landed ahead of this mission and already implements what this
section originally specified as a `_charter_disposition`/`pytest.xfail` design. That design is now
dead. The merged mechanism (`tests/architectural/test_module_length_agreement.py`) is a
`ShardTimingsDriftWarning(UserWarning)` class plus a `_report_drift(message, *, strict)` helper:
`warnings.warn(...)` by default, `pytest.fail(message)` when `_strict_mode()` reads
`SPEC_KITTY_STRICT_SHARD_TIMINGS == "1"`. **Both** `test_charter_is_not_allowlisted_and_agrees`
**and** the cross-module `test_non_allowlisted_modules_agree_with_live_collection` now call
`_report_drift(..., strict=_strict_mode())` on a mismatch — the demotion covers both live-collection
gates, not charter alone (operator ruling point 3; spec.md's FR-003 is corrected accordingly). This
is actually a closer match to spec.md's original CL-001 wording ("non-blocking warning") than the
`xfail` approach this plan originally specified ever was.

#5240 ships its own 3 new fast unit tests — `test_report_drift_warns_by_default`,
`test_report_drift_fails_in_strict_mode`, `test_strict_mode_reads_env_var` — but these exercise only
the `_report_drift`/`_strict_mode` **helper functions in isolation**, never the two production gate
functions themselves. A revert of either gate function's body back to a bare hard `assert` (leaving
`_report_drift`/`_strict_mode` and #5240's 3 tests untouched and still green) would **not** be caught
by #5240's own tests. There is also still no test proving a genuine infra break (a missing
`.github/ci-shard-timings.json` or `.github/ci-module-registry.yml`) still fails loudly via
`_load_timings()`/`_load_registry()` — both already call `pytest.fail(...)` on a missing file (old,
unchanged behavior), but nothing pins it today.

**WP01's job is exactly this residue**, per operator ruling point 2:

1. **Verify, don't re-implement**, that the merged code satisfies FR-001/FR-002/FR-004 for
   `charter`: read the merged file, confirm `_report_drift`'s warn/strict-fail behavior, confirm
   `assert "charter" not in _MISMATCH_ALLOWLIST` is still present and unconditional inside
   `test_charter_is_not_allowlisted_and_agrees`. Record this as a WP01 subtask — a documented
   read-and-confirm step, not a fixture.
2. Add the red-first tests #5240 leaves unmet, in the file's existing idiom (`pytest.mark.fast`, no
   subprocess, matching the bottom-section self-mutation-test style):
   a. A test calling `test_charter_is_not_allowlisted_and_agrees(...)` directly with constructed
      disagreeing `_live_timings_state`/`_collected_counts`-shaped arguments, asserting it emits
      `ShardTimingsDriftWarning` via `pytest.warns(...)` and never raises — catches a revert of that
      function's body to a bare hard `assert`, which #5240's own tests do not.
   b. The equivalent test for `test_non_allowlisted_modules_agree_with_live_collection`, using
      constructed fake `_live_registry_state`/`_live_timings_state`/`_collected_counts` values with
      one synthetic non-allowlisted module mismatching — same purpose, extended to the second gate
      the ruling brings into scope.
   c. A test that, with `SPEC_KITTY_STRICT_SHARD_TIMINGS` set to `"1"` (via `monkeypatch.setenv`),
      the same production function(s) from (a)/(b) raise pytest's fail outcome instead of warning,
      given a disagreement — proving strict mode restores the hard failure at the integration level,
      not just at the `_report_drift` helper level (#5240's own `test_report_drift_fails_in_strict_mode`
      already covers the helper in isolation, but not this integration point).
   d. A test that a missing `.github/ci-shard-timings.json` (or `.github/ci-module-registry.yml`)
      still fails loudly via `_load_timings()`/`_load_registry()` — monkeypatch the path constant to
      a nonexistent file, assert `pytest.fail`'s exception class is raised. This is FR-004's
      still-unmet "infra break, not silence" fixture.
3. **Optional, not gating** (operator ruling point 6): a distinct, behaviour-preserving commit
   fixing the `mypy` `no-any-return` finding in `_resolve_test_dirs` (same file) — admissible,
   domain-matched campsite debt, left to implementer judgment.

WP01 stays scoped to `tests/architectural/test_module_length_agreement.py` only — its
`owned_files`/`authoritative_surface` are **unchanged** by this amendment.

**FR-005 through FR-008** — the 11 fixtures listed in item (c) above (fixture-tested; spec.md marks
all four "no-op passable: no").

**FR-009/FR-010** — verified by code-shape inspection, not a dedicated fixture (spec.md marks both
"no-op passable: yes" — verifiable by inspection, no fixture required); see "FR-009, FR-010,
NFR-003 — concrete text" below.

**FR-002/FR-003 (unchanged invariants) — amended 2026-09-28: three tests, not four.** No new test
needed beyond the existing `test_allowlist_entries_are_real_registry_modules` /
`test_allowlist_does_not_exceed_baseline` / `test_allowlisted_modules_still_genuinely_mismatch`,
which are asserted (diff review, SC-006) to be byte-identical before/after — confirmed by not
touching any of their bodies. **`test_non_allowlisted_modules_agree_with_live_collection` is NOT one
of the unchanged tests** — #5240 demotes it too, via the same `_report_drift` mechanism as charter;
see WP01's red-first fixture 2b above, which exercises exactly that function.

### FR-009, FR-010, NFR-001, NFR-003 — concrete text (not left to the implementer)

- **FR-009 (charter-only scope)**: `scripts/ci/recapture_charter_shard_timings.py` hardcodes
  `MODULE = "charter"` as a module-level constant and passes `--module charter` to
  `capture_shard_timings.main()` internally. The script exposes **no** `--module` CLI flag at all
  (unlike `capture_shard_timings.py` itself, which is reused as a library, not re-wrapped
  generically) — there is no code path by which this workflow could silently expand to another
  module. **Precondition this scope also buys the in-process invocation choice (see "The
  mechanism-vs-ordinary-failure design problem — resolution" section above):**
  calling `pytest.main()` in-process (rather than as a subprocess) is safe here **only** because
  FR-009's hardcoded single `--module charter` call means exactly one `pytest.main()` invocation
  occurs per process. A future extension of this script to more than one module in the same process
  would need to re-audit pytest's own repeated-invocation state (stale `sys.modules` entries,
  assertion-rewrite hook accumulation, plugin-registration state) or reintroduce subprocess
  isolation before adding a second in-process call — this plan does not certify in-process
  invocation as safe for that case.
- **FR-010 (bot identity + fixed, falsifiable text)**:
  - Commit author identity: `spec-kitty-ci-bot <ci-bot@users.noreply.github.com>` (a fixed,
    non-human identity, set via `git -c user.name=... -c user.email=...` on the commit, never the
    PAT owner's own git identity).
  - Commit message: `chore(ci): automated charter shard-timings recapture`.
  - PR title: the same string as the commit message.
  - PR body (fixed template, filled only with the before/after lengths and this run's workflow
    run URL — no free-form prose): *"Automated recapture opened by the scheduled
    `ci-charter-shard-recapture.yml` workflow (`scripts/ci/recapture_charter_shard_timings.py`).
    Updates `.github/ci-shard-timings.json`'s `charter` entry: committed length `<before>` ->
    `<after>`. Workflow run: `<run_url>`. See spec-kitty#5189."* `<run_url>` is filled with the
    fixed GitHub Actions run-URL context expression
    `${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}` — never
    free-form prose. Every clause is fixed, falsifiable-by-inspection text
    per FR-010 — no identity-matching relationship to FR-007's branch-based open-PR check.
- **NFR-003 (no credential leakage)**: `CHARTER_SHARD_RECAPTURE_TOKEN`'s value is read once from
  the environment and passed only as the `gh`/git-credential process's own env var — never
  interpolated into a commit message, PR body, `print()`/`::notice::`/`::error::` string, or log
  line. The script's own error paths (missing-secret, mechanism-crash) print the secret's **name**,
  never its value, mirroring `release_nightly_gate.py`'s `_redact()` convention (that script's own
  `_redact` helper is a further precedent this script's own error-formatting should mirror if any
  GitHub API error text could ever echo the token back).
- **NFR-001 (gate protects shard balance, not correctness)**: this plan's design and the PR body
  must not claim or imply that demoting `test_charter_is_not_allowlisted_and_agrees` risks masking
  a test-coverage or correctness regression. Verification:
  `.github/workflows/module-tests.yml`'s "Select this shard's tests" step falls back to **uniform
  per-test weights for the whole module** — never dropping or skipping any test — when
  `len(durations) != len(node_ids)`, so the demoted assertion's sole protected property is
  shard-balance quality (bounded inter-shard skew), never which tests run or whether they run. The
  PR body states this claim explicitly (shard-balance only, never coverage) so NFR-001's own "must
  not claim or imply..." acceptance bar is demonstrably checked, not merely accidentally unviolated.

### (e) Campsite-clean scope — "none needed" for both named files, with reasons

- **`tests/architectural/test_module_length_agreement.py`**: read in full. No dead code, no stale
  comments, no complexity/duplication issue found. The file is well-documented and its existing
  structure (session-scoped fixtures, a pure `_find_mismatches` helper, self-mutation tests at the
  bottom) is exactly the shape this mission's own new helper/tests should match — no tidy-first
  commit needed; the change *is* additive, in the file's own established idiom.
- **`scripts/ci/capture_shard_timings.py`**: read in full. No dead code, no stale comments, no
  complexity/duplication issue found, and — per the design-problem analysis above — **this file
  requires zero edits**: its existing, unmodified control flow (write-before-return-decision,
  exceptions propagate uncaught) is exactly what the new wrapper depends on. "None needed" is
  stated with the concrete reason that campsite-clean does not mean inventing debt to justify a
  tidy-first commit when none exists — confirmed by a full read of both files, not asserted
  reflexively.

### (f) Baseline — targeted files only, on current HEAD, before any change

Per `NO_FULL_HEAVY_SUITES_IN_MISSION` (binding, supersedes the older "run `tests/architectural/` in
full for cross-cutting changes" line — CLAUDE.md's own "Test policy" section states this
supersession explicitly), the baseline is measured **only** against:

```
uv run --frozen pytest tests/architectural/test_module_length_agreement.py -q
```

(and, once created, `tests/ci/test_recapture_charter_shard_timings.py` — that file does not exist
yet on current HEAD, so its baseline is vacuously "does not exist / not run").

This baseline includes the `slow`-marked live-collection tests in that file (they are part of the
targeted file, not a full-directory or whole-repo sweep) — running one named file, however slow
its own tests are individually, is not the "full/heavy suite" `NO_FULL_HEAVY_SUITES_IN_MISSION`
forbids; a bare `tests/architectural/` directory invocation or `make test-full` would be.

**Any pre-existing red found in that targeted baseline needs a GitHub issue per the charter's
Pre-existing Failure Reporting Rule. Filing that issue is an ORCHESTRATOR action — this plan
explicitly does NOT file issues itself; it only records here that the orchestrator must do so if
the baseline surfaces any red.** (At plan-authoring time, this baseline has not yet been executed
by this plan-authoring agent — recording the *procedure*, not a claimed clean result, is the
plan's job; the implementer runs it red-first before making any edit.)

### (g) Blast radius

- **#5175** ("Merge-seam relocation, test-isolation sweep & model-slot verdict") and **#5177**
  ("fix(review): rejection feedback survives to the implementer's regenerated prompt") both listed
  `.github/ci-shard-timings.json` as a changed file at spec-authoring time. **Re-verified live at
  plan-authoring time (2026-09-27):** `gh pr view 5177 --json state` → `MERGED`; `gh pr view 5175
  --json state,mergeable` → `CLOSED` (not merged; `mergeable: CONFLICTING`, which is moot once
  closed). The three-way "whichever merges first" race spec.md's Reflexivity section framed no
  longer exists: #5177 has already merged, so this mission's branch simply rebases onto whatever
  `.github/ci-shard-timings.json` state #5177's merge produced on `main` — ordinary git-history
  churn, not a design concern this plan needs to engineer around. #5175 drops out of the blast-radius
  list entirely: it closed without merging, so none of its changes (including to
  `.github/ci-shard-timings.json`) ever landed on `main`. Neither PR touched
  `tests/architectural/test_module_length_agreement.py`, `.github/workflows/module-tests.yml`,
  `scripts/ci/capture_shard_timings.py`, or `.github/ci-module-registry.yml`, so there was never a
  direct code collision with this mission's diff regardless of merge order.
- **Downstream consumers of this repo** (every project that installs `spec-kitty-cli` / runs its
  own copy of these workflows via `spec-kitty upgrade`) are blast radius for anything touching
  `.github/workflows/**` or `tests/architectural/**` in general — but concretely, this mission adds
  a **new, additive** workflow file (no existing workflow is edited) and (**amended 2026-09-28**)
  adds red-first tests to **one existing** architectural test file, whose two live-collection gates'
  hard-fail → visible-`ShardTimingsDriftWarning` demotion (hard-fail restorable via
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`) already landed via #5240 ahead of this mission — this
  mission's own diff to that file is purely additive test coverage over an already-merged
  relaxation, never a new failure mode for anyone previously passing. No consumer-facing template
  under `packs/built-in/` is touched, so this has no `spec-kitty upgrade`-propagated effect on
  downstream projects at all — this repo's own CI is the only blast radius.

### (h) Branch-naming drift

Already settled in `tracer-design-decisions.md` (charter's `issue-<n>-<slug>` won over the sk-skill
doctrine's `<type>/<slug>-<issue>` convention for **this mission's own branch**). Not relitigated
here.

### (i) Seam / layering

**No seam applies.** This mission's diff touches only test/CI-infrastructure surfaces
(`tests/architectural/**`, `scripts/ci/**`, `tests/ci/**`, `.github/workflows/**`) — none of which
participate in the enforced `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`
import-direction chain (`tests/architectural/test_layer_rules.py` / `test_pyproject_shape.py`).
Confirmed, not assumed: no path this mission's design touches is under `src/charter/offering/**`,
`src/mission_runtime/**`, the orchestrator-api package, or a vendored `spec-kitty-events` contract
surface — spec.md's own Constraints/Non-Goals name no such surface either.

### (j) `spec-kitty regen`

**Not applicable.** No generated artifact (agent-directory copies, pack-derived templates, the
command-skills manifest) is touched by this mission's file list — confirmed against the plan's own
file list (one test-file edit, one new workflow file, one new script + its test file), none of
which is a `spec-kitty regen`-managed output.

## Project Structure

### Documentation (this mission)

```
kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/
├── plan.md              # This file
├── spec.md              # Already merged/ruled-on
├── reviews/spec.ruling.md
├── tracer-approach.md
├── tracer-design-decisions.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — not created by this phase)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` were generated by the scaffold
and none are needed: this mission adds CI infrastructure and a test-assertion change, not a new
data model, API contract, or user-facing quickstart flow.

### Source Code (repository root)

```
tests/architectural/
└── test_module_length_agreement.py   # edited: WP01 verifies #5240's already-merged
                                       # ShardTimingsDriftWarning/_report_drift demotion (both
                                       # live-collection gates) and adds the red-first tests #5240
                                       # leaves unmet (see item (d))

scripts/ci/
├── capture_shard_timings.py          # UNCHANGED (see item e)
└── recapture_charter_shard_timings.py  # NEW: pure decision functions + thin gh/git-calling main()

tests/ci/
└── test_recapture_charter_shard_timings.py  # NEW: unit tests for the 11 fixtures in item (c)

.github/workflows/
└── ci-charter-shard-recapture.yml    # NEW: schedule + workflow_dispatch; recapture job calls the
                                       # script above; a second, independent job runs the
                                       # architectural gates under SPEC_KITTY_STRICT_SHARD_TIMINGS=1
                                       # (see item (a2))
```

**Structure Decision**: Single project, additive-only. No existing workflow file is edited; no
existing script beyond the one test-assertion edit is modified.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

None. No charter violation was introduced by this design (see Charter Check above).

## Implementation Concern Map

### IC-01 — Demote the per-PR charter length assertion

- **Purpose**: Stop a bare charter test-count change from reding the per-PR architectural-battery
  shard, while keeping the drift visible and keeping a genuine infra break fatal.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004; User Stories 1 and 3.
- **Affected surfaces**: `tests/architectural/test_module_length_agreement.py` only.
- **Sequencing/depends-on**: none — independent of IC-02/IC-03.
- **Risks**: none identified. **Amended 2026-09-28**: the behavioural edit itself is no longer
  this WP's job — #5240 already merged it. The remaining work is a verification subtask plus ~4 new
  fast red-first tests in an already-clean file (item e); see item (d) for the full replacement.

### IC-02 — Recapture decision-logic script

- **Purpose**: Own every piece of decision logic (open-PR match, drift compare, mechanism-vs-ordinary
  failure classification, missing-secret fail-loud) as pure, unit-tested functions, with a thin
  `gh`/`git`-calling `main()` edge.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-008, FR-009, FR-010; C-003, C-004, C-006;
  User Story 2.
- **Affected surfaces**: new `scripts/ci/recapture_charter_shard_timings.py`, new
  `tests/ci/test_recapture_charter_shard_timings.py`.
- **Sequencing/depends-on**: none for IC-01; IC-03 depends on this (the workflow file calls this
  script).
- **Risks**: the manual-dispatch end-to-end rehearsal (item c) needs the operator-created secret to
  exist on the dispatching branch — flag this dependency explicitly in the PR rather than silently
  skipping that rehearsal.

### IC-03 — Scheduled workflow wiring

- **Purpose**: Wire IC-02's script into a `schedule`+`workflow_dispatch`-only workflow with its own
  concurrency group and least-privilege permissions. **Amended 2026-09-28**: this workflow also
  carries a second, independent job running the architectural length-agreement gates under
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` (item (a2)) — the exact-count invariant's real, scheduled,
  hard-failing home.
- **Relevant requirements**: FR-005, FR-007, FR-009; C-003, C-004, C-006; NFR-002.
- **Affected surfaces**: new `.github/workflows/ci-charter-shard-recapture.yml` (still the one file
  — the new strict-mode job does not change `create_intent`/`owned_files`).
- **Sequencing/depends-on**: IC-02 (for the recapture job only; the new strict-mode job has no
  dependency on IC-02's script).
- **Risks**: cron-firing and the real-`main` PR-open path are only confirmable post-merge (item c)
  — the PR body should say so explicitly rather than implying full pre-merge proof.

### IC-04 — Docs supersession note (optional, judgment call at implementation time)

- **Purpose**: Note in the PR body that `docs/development/reference/known-friction-points.md`'s
  existing bullet about this friction is now superseded (per spec.md Reflexivity — PR #5190 already
  recorded the friction and explicitly said it does not close #5189).
- **Relevant requirements**: Reflexivity section (not a numbered FR).
- **Affected surfaces**: `docs/development/reference/known-friction-points.md`, if implementation
  judges an edit warranted — spec.md explicitly leaves this to implementation's judgment, not
  prescribed here.
- **Sequencing/depends-on**: none.
- **Risks**: none — this is a non-blocking, optional doc touch-up.
