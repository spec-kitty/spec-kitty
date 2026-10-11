# Tasks: Repo-relative retrospective record_path (#5868)

**Mission**: `retrospective-record-path-relative-01M4PG0M`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Single cohesive work package: a red-first regression plus the one-line surface
fix that makes `RetrospectiveCaptured.record_path` repository-relative.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Land an issue-pinned (`#5868`) red-first regression asserting `emit_captured` persists a repo-relative `record_path` through the real entry point (RED before fix) | WP01 | |
| T002 | Fix `emit_captured._build` to persist `canonical_path.relative_to(repo_root).as_posix()` instead of `str(canonical_path)` | WP01 | |
| T003 | Prove green (new regression + existing `tests/retrospective/test_events.py`), settle the test into its functional home (no lingering `regression` marker), confirm `ruff`/`mypy` clean | WP01 | |

## Work Packages

### WP01 — Repo-relative record_path + red-first regression

- **Priority**: P1 (the mission)
- **Goal**: `emit_captured` writes `record_path = kitty-specs/<slug>/retrospective.yaml` (repo-relative, POSIX), leaking no absolute/home/username segment; envelope otherwise byte-identical.
- **Independent test**: In a tmp repo whose root contains a username-like segment, call `emit_captured`, read the event back, assert `record_path` is relative, equals the expected value, and contains no host-root segment.
- **Included subtasks**: T001, T002, T003
- **Implementation sketch**:
  1. (T001) Add a focused test to `tests/retrospective/test_events.py` that calls `emit_captured` with a `tmp_path` repo root and asserts the persisted `record_path` is `kitty-specs/<MISSION_SLUG>/retrospective.yaml` (relative, no leading `/`, no host-root/username segment). Mark it `@pytest.mark.regression` and reference `#5868` while proving RED.
  2. (T002) In `src/specify_cli/retrospective/lifecycle_events.py` `emit_captured._build`, change `record_path=str(canonical_path)` to the repo-relative POSIX form (`canonical_path.relative_to(repo_root).as_posix()`).
  3. (T003) Run the new test + the existing retrospective suite; settle the test as a permanent focused unit test in its functional home (drop the `regression` marker per ADR 2026-07-17-1, keep the `#5868` citation in the docstring); confirm `ruff check` + `mypy` clean on both touched files.
- **Dependencies**: none
- **Risks**: `relative_to` would raise if `canonical_path` were not under `repo_root` — grounded as impossible for this input (home is composed under `repo_root`); the regression's tmp-root case exercises exactly this.

**Prompt**: [tasks/WP01-repo-relative-record-path.md](./tasks/WP01-repo-relative-record-path.md)

## MVP

WP01 is the entire mission.
