# WP03 review feedback (cycle 1) — reviewer-renata

**Verdict: REJECTED.** There is one blocking finding, about DD-09. Everything else I checked holds.

## Blocking

### B-1. "Advisory" covers `router-gate` only. A failed `docs-site` still turns the CI Router run red, and the fleet verdict and main P0 intake read that run.

DD-09 (`traces/design-decisions.md:13`) and the comment on `ADVISORY_JOB_NAMES` (`scripts/ci/router_gate.py:53-59`) present the job as one that "run[s] but do[es] not gate yet". That is true of the `router-gate` check only. The job has no `continue-on-error`, and `test_the_job_is_bounded_and_never_swallows_a_failure` (`tests/ci/test_docs_site_job.py:194`) forbids one. So when `docs-site` fails, the **CI Router workflow run concludes `failure`**. Two consumers read that run-level conclusion:

- **`ci-fleet-verdict.yml`** fires on `workflow_run` of `CI Router`. `scripts/ci/fleet_verdict.py::classify` (around line 114) returns `red` when any run in the required set has `conclusion == failure`, so the PR's `[ci]` verdict goes red over a job that is meant to be optional.
- **The same workflow's "Reconcile main CI into the fleet P0 intake" step** (`scripts.ci.fleet_main`) files a main-red P0 issue when a push to `main` turns the CI Router run red. `docs_site` folds to `true` in full mode, so the job does run on `main`.

`green_match.py` (skip-if-green) also requires `run.conclusion == success`, so a red docs build stops a green run from being reused.

The repository already treats this as the second half of a non-blocking guarantee. `ci-aggregate.yml` (around lines 661-669) says job-level `continue-on-error` "already holds the run conclusion green" for `sonar-pr`, and calls that "the workflow-run-conclusion half of the non-blocking guarantee". DD-09 gives `docs-site` only the `router-gate` half. So the design is not yet honest about what "not required until #6937" means (FR-008, issue #6930). Today a failed docs build makes a PR red in the fleet protocol and opens a P0 on `main`.

**Fix: pick one, and record the choice in DD-09:**

- **(A) Make the run-conclusion half true as well (recommended).** This is the narrowest code change, and it follows the `sonar-pr` precedent.
  1. Add job-level `continue-on-error: true` to `docs-site`, with a comment that cites #6937.
  2. Keep the `ADVISORY_JOB_NAMES` skip. The job's row in the jobs API still reads `failure`, or no conclusion while it runs.
  3. Adjust `test_the_job_is_bounded_and_never_swallows_a_failure` so it allows job-level `continue-on-error` and still forbids it per step, along with `|| true` and `set +e`.
  4. Add a test that a ci-router job has job-level `continue-on-error: true` **if and only if** its `name:` is in `ADVISORY_JOB_NAMES`. #6937 then has to remove both together, and the set stays self-draining.
  5. Commit the new or changed tests red first.
- **(B) Keep the job red-visible on purpose.** Leave the code as it is, but amend DD-09 and the `router_gate.py` comment to state that a failure still reddens the CI Router run, the fleet verdict, skip-if-green reuse and the main P0 intake. Then get the operator to accept that explicitly, recorded against #6937 or #6930, because it partly contradicts "not required yet".

## Answers to the coordinator's questions (no change needed)

- **Does the advisory skip weaken the gate for any other job?** No. It is an exact display-name match against a frozenset with one entry. Matrix jobs carry suffixed names, and `test_a_required_row_still_blocks_beside_an_advisory_one` shows that a failing required row still blocks next to the advisory one.
- **Is it the narrowest option for `router-gate`?** Yes. Leaving the job out of `needs:` alone would have blocked on its row anyway. The gate reads every jobs-API row (#4208), and the row has no conclusion while the job runs.
- **Is coupling to the job's `name:` sound?** Yes. Three tests keep it honest: `test_the_job_is_advisory_to_the_terminal_gate`, `test_every_advisory_name_is_a_router_job_outside_router_gate_needs` (it fails on a dead or renamed entry), and the `test_dual_mode_contract.py` subtraction. One nit: two jobs that share a display name would collapse in the `by_name` map, which is negligible.

## Verified and passing

- **Red first:**
  - `a498c1da` precedes the job: `ci-router.yml` at `b3a619d9` has no `docs-site:`.
  - `b3a619d9` precedes `ADVISORY_JOB_NAMES`: zero occurrences at that commit.
- **Action pins:**
  - `pnpm/action-setup@ea17c68…` is the peeled commit of tag `v6.1.0`, committed 2026-09-05.
  - `actions/setup-node@949feb2…` is `v7.1.0` (also `v7`), committed 2026-10-07. Both are more than two weeks old.
  - `checkout` and `upload-artifact` reuse SHAs already pinned across the workflows.
- **pnpm/action-setup inputs:** at that commit `action.yml` has an optional `version` and a `package_json_file` input. The dist code reads `packageManager` when no version is given, so leaving `version` out is valid.
- **Contract check on the stdlib only:** `env -i PATH=/usr/bin:/bin /usr/bin/python3 -S -m scripts.docs.site_contract --check` exits 0. `-S` means no site-packages at all.
- **No credential:** the workflow sets `permissions: contents: read` at the top level, and the job reads no secrets.
- **Timeout:** `timeout-minutes: 20`.
- **DocFX untouched:** `git diff origin/main -- .github/workflows/docs-pages.yml` is empty.
- **Scrub row:** it equals the router group.
- **Changelog fragment:** the section `internal` is valid.
- **Lint and types:** ruff check, ruff format --check --force-exclude and mypy --strict are clean on `router_gate.py`, `test_docs_site_job.py` and `test_dual_mode_contract.py`.
- **Router blast radius:** `tests/ci` plus `test_dual_mode_contract`, `test_gate_selection_authority`, `test_ci_quality_path_filters`, `test_ci_router_transcription_guards`, `test_ci_integrity_oracle_nonvacuous`, `test_no_duplicate_suite_execution`, `test_battery_scan_scope_routing`, `test_local_gate_parity`, `test_workflow_coherence`, `test_suite_jobs_gate_blocking` and `tests/release/test_release_ci_ownership.py` gave 3170 passed, 2 skipped, 0 failed.
