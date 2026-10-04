---
work_package_id: WP04
title: Nightly integration-slice harness
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- SC-003
planning_base_branch: kitty/nightly-reds-b-2026-10-04
merge_target_branch: kitty/nightly-reds-b-2026-10-04
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-b-2026-10-04. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-b-2026-10-04 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-b-01M42YYF
base_commit: f3d6e32aadf812f77730ddbece8f2ee17c5df01c
created_at: '2026-10-04T08:10:01.819321+00:00'
subtasks:
- T010
- T011
- T012
phase: Phase 1 - Nightly red repair
history:
- at: '2026-10-04T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- tests/test_repo_root_status_guard.py
- tests/characterization/test_trio_json_envelope.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Nightly integration-slice harness

## Objectives & Success Criteria

These integration-slice reds (run 37177460494, job 111362964895) pass in the slice's real environment:

- `tests/upgrade/test_mission_corpus_recovery.py` (9 tests) — fail from a `fetch-depth: 1` checkout.
- `tests/test_repo_root_status_guard.py::test_leak_attribution_does_not_straddle_into_the_next_test` — fails with `CI=true`.
- `tests/characterization/test_trio_json_envelope.py::TestImplementRecoverJson::test_coord_mission_no_crashed_sessions`.

Requirement refs: FR-006, FR-007, FR-008, NFR-001, NFR-002, SC-003.

## Subtasks & Detailed Guidance

### Subtask T010 – Full history for the slice

- The `integration-slice` job in `.github/workflows/ci-nightly.yml` uses `actions/checkout` with no `with:` (depth 1). The corpus suite `git archive`s pinned historical commits (e.g. `c0054153b9bce0778cf41a85d11ecd4e9650031d`) from the repository's own object store. Every other job running that suite already sets `fetch-depth: 0` (`module-tests.yml`, `ci-router.yml`, the nightly architectural job; commit `6ce98087b`). Add `with: fetch-depth: 0` with a comment naming the corpus suite, mirroring the existing comments.
- Evidence: from a `git clone --depth 1 file://<repo>` scratch clone, `git cat-file -t c0054153b9bce0778cf41a85d11ecd4e9650031d` fails; from the full clone it succeeds and `tests/upgrade/test_mission_corpus_recovery.py::test_physical_omission_cannot_redefine_pinned_corpus` passes.
- Run `tests/ci/test_nightly_integration_slice.py` and `tests/ci/test_nightly_exit_code_honesty.py` (they may pin this job's shape), plus any other `tests/ci/` file that greps `ci-nightly.yml` for checkout steps (`grep -ln "ci-nightly" tests/ci`).

### Subtask T011 – CI-mode summary parsing

- With `CI` (or `BUILD_NUMBER`) set, pytest appends ` - <message>` to `-rA` summary lines; the nightly log shows `ERROR test_polluter.py::test_a_… - tests._support…RepoRootStatusArtifactLeak: …`. `_RESULT_LINE_RE` requires end-of-line right after the node id.
- Change the regex to accept an optional ` - <message>` suffix (`(?:\s+-\s.*)?$`). Keep every assertion. Prove: `CI=true` run of the whole file red before, green after; and green without `CI`.

### Subtask T012 – Materialized coordination worktree for the recover characterization

- Since `2fd7eabf0` a coordination read on an unmaterialized coordination worktree fails closed by design; `mission create` materializes it. The `coord_repo` fixture never does, and the sibling accept test on that fixture was already re-pinned to the refusal.
- Add a fixture that builds the coordination Mission with its coordination worktree materialized (use the module's existing builder — check whether `_build_mission_repo` already supports materialization; if not, add it the way the module's other fixtures materialize, e.g. `git worktree add <CoordinationWorkspace.worktree_path(...)> <branch>`), point `test_coord_mission_no_crashed_sessions` at it, and update the module docstring's recover bullet. Keep the success assertions.

## Review Guidance

- No test is skipped or deselected; the corpus suite runs exactly as in the other lanes.

## Branch Strategy

- **Strategy**: lanes_with_coord
- **Planning base branch**: kitty/nightly-reds-b-2026-10-04
- **Merge target branch**: kitty/nightly-reds-b-2026-10-04

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Binding rules for this WP

- Commits: author AND committer are `Stijn Dejongh <stijn.dejongh@sddevelopment.be>`; set `git config user.name "Stijn Dejongh"` and `git config user.email "stijn.dejongh@sddevelopment.be"` in the lane worktree before committing. End every commit message you write with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests foreground by named node id or file only: `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" <ids>`. Never a directory, never `make test-full`.
- No retries, skips, xfails, deselections, timeout or budget changes; keep every assertion except the stale literal named below.
- Do not touch any file outside `owned_files`.
- `ruff check` and `uv run --frozen ruff format --check --force-exclude` on every touched Python file.

## Activity Log

- 2026-10-04T08:10:00Z – system – Prompt created.
