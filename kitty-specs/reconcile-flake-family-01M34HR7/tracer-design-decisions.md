# Tracer: Design Decisions — reconcile-flake-family-01M34HR7

Seeded at plan phase (2026-09-22). Append entries during implementation; assess at mission close.
See `plan.md` for full rationale; this file is the running log of decisions and their "why", for
a future reader who does not want to re-read the whole plan.

## Plan phase

1. **One generic, stdlib-only bounded-retry primitive (`scripts/ci/reconcile_retry.py`), shared
   by all three retrying surfaces** (`fleet_verdict.py::report()`, `fleet_main.py::report()`,
   the new `wait_for_artifacts.py`), rather than three hand-copied loops or a GitHub-specific
   helper limited to the FR-008-named pair. Rationale: FR-008 already flags the
   fleet_verdict/fleet_main duplication risk; the same risk applies a third time to
   `wait_for_artifacts.py` if its loop is hand-rolled separately. A single primitive that takes an
   `attempt: Callable[[], T | None]` and returns the stabilized `T` or `None` on exhaustion keeps
   the *terminal-behavior* decision (skip-and-defer vs. fail-loudly) with each caller, so it does
   not encode FR-004's fleet-verdict-only semantics into a primitive `wait_for_artifacts.py` must
   not inherit. Reviewers should scrutinize whether this over-generalizes relative to FR-008's
   literal (fleet_verdict/fleet_main-only) framing — it is a plan-phase judgment call, not spec
   text.
2. **`wait_for_artifacts.py` polls only the SELECTED (must-be-fresh) shard set, not the full
   registry.** Polling for the full registry would exhaust its budget on every ordinary
   diff-scoped PR, because `ci-modules.yml`'s diff-scoping deliberately never runs unselected
   modules' shards at all (documented in `ci-aggregate.yml`'s own header comment) — those
   artifacts will never appear, retried or not. This requires moving the existing "Download the
   triggering run's selected-module set" step earlier in `ci-aggregate.yml`'s `collect` job (from
   after `download-previous` to before the new polling step), which is a real re-sequencing of
   existing steps, not just an insertion — flagged for reviewer attention.
3. **`reconcile_shards.py` is imported from, never edited.** `wait_for_artifacts.py` calls its
   exported `parse_registry`/`read_selected_modules` to avoid a second, drifting shard-naming
   authority. This is read-only reuse and does not change `reconcile_shards.py`'s own shape or
   behavior (Key Entities item 3 in spec.md is preserved).

## Implement phase — decisions, including reversals (2026-09-22)

The reversals below are recorded because they are the more valuable entries: a decision that
looked right at plan time and turned out wrong under real code is worth more to a future
mission than a decision that simply held.

4. **REVERSED: retry inside `reconcile_shards.py::main()` was specified, then found
   vacuous, and moved to a new `ci-aggregate.yml` polling step instead.** The original design
   direction (plan-phase framing) put the retry loop inside `reconcile_shards.py::main()`
   itself. Under implementation this proved vacuous: `main()` has no network access and only
   re-reads an already-static local directory listing (the artifacts have already been
   downloaded to disk by the time `reconcile_shards.py` runs) — retrying a read of a directory
   that will not change between retries cannot help a late-arriving artifact become visible.
   The actual fix had to sit earlier in the pipeline, where a network read of the *live*
   GitHub Actions artifact list can genuinely observe a late upload — hence WP03's new
   `wait_for_artifacts.py` module polling via `api.pages(...)` before the download step, wired
   into a new step in `ci-aggregate.yml`'s `collect` job. `reconcile_shards.py` itself remains
   unmodified (decision 3 above still holds) — the fix moved to sit in front of it rather than
   inside it.
5. **`plan.md` was amended twice after it had already PASSED its own review squad, on
   operator authority** (recorded in `reviews/tasks.ruling.md`). First fix: a structurally
   impossible claim about the elif/retry boundary in the original plan text — plan.md as
   originally reviewed described a retry/elif interaction that could not actually occur given
   the real control flow, and the operator authorized a correction after the squad had already
   signed off. Second fix: the first fix's narrow scope (corrected only the specific
   impossible claim) left the surrounding document self-contradictory with an adjacent
   section that still assumed the old (wrong) framing, so a second, wider amendment was
   authorized to bring the whole section back into internal consistency. Both amendments are
   on operator authority after squad pass, not a self-authorized implement-phase change — the
   review squad never re-ran against the amended text, which is a deliberate, operator-owned
   exception to the normal "review gates before proceeding" sequencing, not an oversight.
6. **WP03's poller deliberately returns/exits 0 on budget exhaustion rather than failing
   hard.** `wait_for_artifacts.py`'s own module docstring states this as an "Architectural
   floor (do not regress)": on exhaustion it always exits 0 and never raises — it only
   WIDENS the window before the workflow falls through to the existing
   `actions/download-artifact` steps. Hard-failing here would disable the downstream
   fallback path (`ci-aggregate.yml`'s existing steps that already tolerate a shard being
   absent) and turn a recoverable late-shard race into a hard job failure on every ordinary
   slow-artifact occurrence, not just genuine unrecoverable ones. The fail-closed floor for
   genuine incompleteness stays exactly where it already was: `reconcile_shards.py`'s own
   unmodified, unmoved `must_be_fresh` guard is the single terminus that decides
   completeness (FR-006) — `wait_for_artifacts.py` is explicitly "not part of that decision
   and must never become one" (its own docstring's words). `test_composing_reconcile_shards_still_fails_closed_when_poller_exhausts`
   (WP03's T014) is the test proving this composition holds.
7. **A test whose name promised "refuses obsolete p0" stopped exercising that exact path
   after WP02's pre-loop `snapshot()` shifted call parity, and was renamed rather than left
   misleading.** The pre-fix version of this test (in `test_fleet_main.py`) covered a head
   move between a single snapshot pair causing an immediate raise. WP02's fix added a
   pre-loop `snapshot()` call ahead of `_attempt()`'s own read (to fix the `dry_run`
   boundary), which changed which `git/ref/heads/main` read absorbs the head move — the old
   test's scenario now resolves through the pre-existing `evidence["state"] != "red"`
   informational-print branch instead of a raise, so it no longer exercises the binding
   two-attempt-coverage path its old name implied. It was renamed to
   `test_main_head_move_before_attempt_read_yields_nothing_to_report` (its docstring now
   states explicitly: "this is NOT the binding two-attempt-coverage test") and a new,
   supplementary test, `test_attempt_change_during_publication_refuses_stale_verdict`, was
   added to directly cover the head-only-disagreement-within-an-attempt case the old test's
   name had promised. Both tests are in `tests/ci/test_fleet_main.py`.
8. **The verification ceiling: this mission's own PR cannot exercise its own fix.**
   `workflow_run`-triggered workflows always execute the copy of the workflow file (and every
   script it references) that lives on the repository's default branch at trigger time, never
   the triggering PR's own branch copy. All three affected workflows fire on `workflow_run`.
   This means unit tests over mocked racy sequences are the only pre-merge evidence available
   for this fix — there is no way to make this PR's own CI runs exercise the real race
   through the real trigger path. Confirmation the race is actually closed requires watching
   real post-merge `main`-head CI cycles (spec.md SC-004, explicitly a post-merge, out-of-WP,
   out-of-mission observation window). See `tracer-approach.md`'s close-out entry for the
   full restatement of this scope note.

## Implement-phase judgment calls not already recorded at plan time

9. **`retry_with_backoff`'s sleep-indexing convention.** `backoff_seconds(i)` receives the
   1-indexed COUNT of attempts already completed, not a 0-indexed retry counter: after
   attempt 1 returns `None`, `backoff_seconds(1)` is called before attempt 2; after attempt 2
   returns `None`, `backoff_seconds(2)` is called before attempt 3; and so on, with no sleep
   after the final attempt (`i < max_attempts` guards the sleep call). This was a genuine
   naming/off-by-one choice WP01 had to resolve and document explicitly in the primitive's
   own docstring, since "attempt count" and "retry count" differ by one and either could
   plausibly be what a `backoff_seconds` callback expects.
10. **`_attempt()` decomposition shape in `fleet_verdict.py`/`fleet_main.py`.** Both files
    extract the retry body into a private `_attempt(api, root, ..., attempt) -> _Outcome`
    closure/function that `report()` passes to `retry_with_backoff`, keeping `report()`
    itself as a thin orchestration wrapper (pre-loop `snapshot()` for the `dry_run` boundary,
    then the retry call, then act on the outcome). This is the shape WP02 converged on
    independently in both files to keep each under the complexity-15 ceiling (`ruff`'s
    `C901`/Sonar's `S3776`) without changing either file's externally-observed behavior —
    the same decomposition pattern applied twice rather than only once and copied, which
    keeps both files consistent with each other.
11. **`wait_for_artifacts.py`'s artifact-response-shape assumption.** The real
    `GitHub`/`GitHubCLI.pages()` boundary returns a list of dicts with at minimum a `"name"`
    key; WP03 had to decide how to read the shard's attempt number back out of that response.
    Rather than trusting a separate `"attempt"` field in the artifact metadata (which the
    GitHub Actions artifacts API does not reliably provide per-artifact), the implementation
    parses the attempt number out of the artifact NAME itself via
    `select_source_artifacts.py`'s existing `ARTIFACT` regex (imported, not re-derived) and
    applies a carried-forward-attempt tolerance: an artifact's own encoded attempt number may
    be `<= run_attempt`, not necessarily exactly equal to it, matching the same tolerance
    `select_source_artifacts.py` already applies elsewhere. This resolves an
    artifact-response-shape assumption WP03 had to make explicit rather than inherit
    silently.

## Gate Statement — confirmed held (close-out)

Re-verified directly at close-out, not merely trusted from plan.md's Gate Statement table:
`ruff check .` and `ruff format --check .` both hard-enforced and confirmed clean across the
whole repo (T016); the `TID251` import-linter check confirmed clean across the whole repo;
`clean-install-verification` unaffected — this mission adds no new dependency (no
`pyproject.toml`/`uv.lock` change in the diff); `ci-modules.yml`'s `ci` shard over
`tests/ci/` verified in full via T016's `tests/ci/` run (412 passed / 0 failed); diff-cover
≥90% does not apply per C-008 (the `ci` module's `cov_targets` are `kernel`/
`specify_cli.core`, not `scripts/ci`, confirmed at plan time and unchanged); `sonar-pr`
remains advisory/non-blocking (`continue-on-error: true`, excluded from `aggregate-gate`'s
`needs:` set) and was not separately re-run from this WP, consistent with its non-blocking
status. All hard gates held.
