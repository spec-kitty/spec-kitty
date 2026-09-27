---
work_package_id: WP02
title: Accept gate and stamp fail closed
dependencies:
- WP01
requirement_refs:
- C-003
- FR-003
- FR-004
- FR-005
- FR-010
planning_base_branch: claude/project-thread-zj01ct
merge_target_branch: claude/project-thread-zj01ct
branch_strategy: Planning artifacts for this mission were generated on claude/project-thread-zj01ct. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/project-thread-zj01ct unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-fails-closed-01M3HS4V
base_commit: 8b07d554784a27d76aa2319b829a5339baf20004
created_at: '2026-09-27T17:18:08.294860+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Implementation
history:
- at: '2026-09-27T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/specify_cli/acceptance/test_issue_4974_accept_concurrent_verdict.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/acceptance/gates_core.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/cli/commands/accept.py
- tests/specify_cli/acceptance/test_issue_4974_accept_concurrent_verdict.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Accept gate and stamp fail closed

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it.

Mission: `accept-fails-closed-01M3HS4V`. Read `../spec.md`, `../plan.md`, `../research.md`.

## Objectives & Success Criteria

- `_evaluate_acceptance_matrix` (`gates_core.py` ~L476-615): keep the pre-lock read, review-evidence population and negative-invariant enforcement OUTSIDE the lock (NFR-001). Replace the unconditional `write_acceptance_matrix(matrix_dir, acc_matrix)` with WP01's `locked_reread_splice_and_write(..., commit=False, splice=lambda fresh: splice_owned_rows(fresh, snapshot, judged))`, where `snapshot` is a deep copy taken right after the read. Then validate evidence and judge `overall_verdict` from the returned FRESH matrix (FR-003, FR-004). Diagnose mode (`mutate_matrix=False`) writes nothing and takes no lock. Extract helpers so no function exceeds complexity 15.
- On `FeatureStatusLockTimeoutError` in the gate: record an activity issue + blocked check (`acceptance_matrix_lock`) so `summary.ok` is False and no write happens (FR-005). Make sure `accept` exits non-zero with that diagnostic.
- `AcceptanceSummary` gains `acceptance_matrix_dir: Path | None = None`, set to the gate's `matrix_dir` whenever the matrix gate evaluated (thread it through whatever collects the gate outputs).
- `_commit_acceptance_meta`: call `record_acceptance(...)` inside `locked_acceptance_verdict_guard(repo_root, summary.acceptance_matrix_dir)`; translate the guard's refusal into `AcceptanceError` so `accept` exits 1 with no `accepted_at`. Keep the git commit OUTSIDE the lock span (no subprocess may need the lock while it is held). If `acceptance_matrix_dir` is None on a non-checklist path, fail closed (do not silently skip) unless you can prove the path is unreachable — document the choice (FR-010).
- `--no-commit` still leaves HEAD unchanged (C-003).

## Red-first tests (new file `tests/specify_cli/acceptance/test_issue_4974_accept_concurrent_verdict.py`, `pytestmark = [pytest.mark.git_repo, pytest.mark.regression]`)

Build fixtures with the existing helpers used by `tests/specify_cli/acceptance/test_acceptance_verdict_command.py` and `tests/specify_cli/test_acceptance_regressions.py` (single-lane manifest via `write_single_lane_manifest`, approved WP, convention dirs, matrix FR-001=pass + pending NI-SLOW). Drive the real `spec-kitty accept` CLI (CliRunner on the app, `--mission <slug> --lenient --json` as the issue does).

1. NI variant: monkeypatch the `enforce_negative_invariants` name `gates_core` imports so the wrapper calls the real function then invokes the real `acceptance-verdict` command (NI-FAIL, custom_command `exit 1`) once. Assert exit != 0, no `accepted_at`, NI-FAIL `still_present` on disk AND in `git show HEAD:<matrix path>`.
2. Criterion variant: mid-check `--criterion FR-001 --result fail`; FR-001 stays `fail`, refuse.
3. Positive control, same fixture, no concurrent verdict → accepted.
4. SC-005 late verdict: wrap `record_acceptance` (or the point just before the guard) so a failing verdict is committed after the gate's splice and before the stamp → refuse; control accepts.
5. SC-006: hold the status lock from another holder (e.g. `feature_status_lock` in a thread / pre-acquired machine file lock) → accept fails closed with the lock diagnostic and the matrix unchanged; control accepts.
6. Re-registration edge: NI-SLOW re-registered with a new command mid-check → fresh pending row kept → refuse.
Prove half-by-half: record in the Activity Log that reverting the splice alone and the fresh-verdict judgement alone each turns test 1 red.

## Validation

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/acceptance/ tests/specify_cli/test_accept_no_commit_readonly.py tests/specify_cli/test_acceptance_regressions.py tests/specify_cli/test_canonical_acceptance.py tests/cross_cutting/misc/test_acceptance_support.py tests/integration/test_accept_matrix_coord_partition.py tests/specify_cli/cli/commands/test_accept_guard.py tests/acceptance/test_provenance_and_deferral.py -q
make test-fast
```

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: claude/project-thread-zj01ct
- **Merge target branch**: claude/project-thread-zj01ct

## Governance

- Load `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`.
- ATDD / red-first: commit the issue-pinned `@pytest.mark.regression` test(s) first and show them RED against the pre-fix product code, then the fix.
- New code: ruff, `ruff format --check`, mypy clean; complexity ≤ 15; tests in the same commit as new branches/helpers. Terminology: Mission, never feature.
- Do NOT run `make test-full`, the whole `tests/architectural/` directory, or e2e/performance suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Run the targeted files listed below plus the owning subsystem's fast tier.

## Post-tasks squad folds (binding; out-of-map edits below are pre-authorized under ownership-map leeway)

- Never call `feature_status_lock` directly in `gates_core.py` / `acceptance/__init__.py`; use only WP01's seam and guard (the lock-composition census in `tests/architectural/test_status_events_writes_gate.py` is exact-set).
- `tests/specify_cli/acceptance/test_acceptance_cores.py` (~L475-600) and `tests/characterization/test_trio_pure_cores.py` (~L400-460) stub the gate with `SimpleNamespace` matrices and patch `matrix.write_acceptance_matrix` / `read_acceptance_matrix`. Update them to patch the seam (or use real `AcceptanceMatrix` objects) so their assertions stay meaningful; run both.
- Planning-artifact-only missions skip the matrix gate (`gates_core.py` ~L268-274) with `summary.ok` True: record on the summary WHY the matrix gate was not evaluated and let ONLY that skip bypass the FR-010 guard; any other `acceptance_matrix_dir is None` on a stamping path fails closed. Keep a planning-artifact-only accept test from `tests/specify_cli/test_acceptance_regressions.py` / `tests/specify_cli/test_canonical_acceptance.py` green.
- Half-by-half proof (SC-001): the FR-010 guard would mask a reverted FR-004, so test 1 must assert the GATE's refusal (JSON/activity text "Acceptance matrix verdict is 'fail'"), not only the exit code.
- NFR-001 witness at the gate: a spy asserting `populate_criteria_from_review_evidence` and `enforce_negative_invariants` run while the status lock is NOT held. Add NFR-001 to this WP's refs in the Activity Log.
- The FR-010 guard can raise `FeatureStatusLockTimeoutError` (`specify_cli.status.locking`, re-exported by `specify_cli.status`); translate it to `AcceptanceError` in `_commit_acceptance_meta`.
- SC-006: patch `specify_cli.acceptance.matrix.BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS` (or the seam's timeout kwarg) to a short value and hold the lock from ANOTHER THREAD (the lock is re-entrant per thread), or reuse the `_timeout_lock` pattern at `test_acceptance_verdict_command.py` ~L1134.
- Patch target for test 1: `gates_core` imports `enforce_negative_invariants` lazily inside the function, so patch `specify_cli.acceptance.matrix.enforce_negative_invariants`.

## Activity Log

- 2026-09-27T18:40:59Z – claude – Half-by-half proof (SC-001, NFR-001 ref): reverting the FR-003 splice alone (write judged in place of the fresh re-read, ignoring the concurrently-committed row) turned test_ni_variant_survives_and_accept_refuses red on data loss (NI-FAIL erased, accept exit 0). Reverting the FR-004 fresh-verdict judgement alone (judge pre-splice judged instead of the returned fresh_matrix) turned the same test red specifically on the gate's own 'Acceptance matrix verdict is fail' message going missing -- the FR-010 guard masked the reverted FR-004 via a different exit path, confirming the test's message-level assertion (not just exit code) is load-bearing per SC-001. Both mutations were restored and reverified green. NFR-001 (review-evidence population + negative-invariant enforcement run OUTSIDE the status lock) is covered by test_nfr001_population_and_enforcement_run_outside_the_status_lock, a spy wrapping feature_status_lock to record lock-held state at each call.
