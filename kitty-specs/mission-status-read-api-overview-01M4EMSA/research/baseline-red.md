# Baseline: pre-existing red versus introduced red (plan section 6, Q-4)

Append-only. The first entry is written by the orchestrator before WP01 is claimed.

## 2026-10-10: before WP01

- **Merge-base / base:** `dfde95c39` (`origin/main`), in a scratch detached worktree. Running `uv sync --frozen --all-extras` first.
- **Branch:** `issue-5529-mission-status-read-api-overview` at `bc696eec4`, rebased onto that base. Only `kitty-specs/` differs from the base.
- **Commands** (each run on the base, then on the branch):
  - `make test-fast`
  - `uv run --frozen pytest tests/contract tests/ci <the arch gate files of plan section 5> -n auto --dist loadfile -p no:cacheprovider -q -rfE`
  - The arch gate files are:
    - `test_archive_root_byte_identical`
    - `test_ci_corpus_trigger_completeness`
    - `test_layer_rules`
    - `test_module_shard_registry`
    - `test_no_duplicate_suite_execution`
    - `test_no_invalid_windows_filenames`
    - `test_no_legacy_terminology`
    - `test_pyproject_shape`
    - `test_workflow_coherence`

### Results

| Run | Base | Branch |
|---|---|---|
| `make test-fast` | 12 failed, 2487 passed, 5 skipped, 24 errors | 12 failed, 2487 passed, 5 skipped, 0 errors |
| targeted (contract + ci + arch gates) | 8 failed, 5705 passed, 43 skipped | 0 failed, 5714 passed, 43 skipped |

**Introduced red: none.** Nothing is red on the branch that is green on the base.

### Red on both, local-environment class (category 2)

`make test-fast`: the same 12 tests fail on the base and the branch.

- `tests/status/test_drain_fanout.py::TestRepoScopedGateReadsTheEmittingRepo`: the 3 fanout tests. The handler is called 0 times.
- `tests/status/test_locking_reentrancy_migration.py::test_project_event_log_lock_shares_the_same_reentrancy_contract`: the lock holder file is absent.
- `tests/status/test_mission_write.py::test_the_non_repository_probe_pins_git_to_the_c_locale`: the probe environment carries the agent harness's own variables.
- `tests/unit/migration/test_mission_state_lanes_rebuild.py`: 7 tests, all with `MissionStateRepairError: No mission directories found to repair`.

CI on `main` at the same SHA `dfde95c39` is green: CI Router run 38049916579 and CI Aggregate run 38050759713 both succeeded. These failures therefore come from the local agent-harness environment (inherited environment variables, temp layout), not from the code. They are not genuinely pre-existing failures under the charter's reporting rule, so no issue is opened.

If one of them shows up red in PR CI, it is reclassified and an issue is opened then.

### Red on the base only (worktree environment)

These are red on the base and green on the branch, which by definition is not introduced:

- `tests/status/test_zeitgeist_decision_moment_docker_local.py`: 24 errors from a subprocess or docker failure.
- `tests/contract/test_mission_status_reality.py`: the 8 corpus tests. The drift scan answered 500, and the fallback lists differed. The scratch worktree under the temp directory has no project-local state that the corpus reader expects.

Java: the baseline is empty because the tree is new. A red `Mission Status API gate` is always introduced (plan section 6 item 5).

Re-run this baseline before the PR (tasks-overview, wrap-up).
