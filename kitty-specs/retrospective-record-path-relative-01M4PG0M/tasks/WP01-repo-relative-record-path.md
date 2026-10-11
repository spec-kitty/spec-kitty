---
work_package_id: WP01
title: Repo-relative record_path + red-first regression
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: fix/retrospective-record-path-relative
merge_target_branch: fix/retrospective-record-path-relative
branch_strategy: Planning artifacts for this mission were generated on fix/retrospective-record-path-relative. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/retrospective-record-path-relative unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retrospective-record-path-relative-01M4PG0M
base_commit: 6a677683555bce6ccdccbf9b0a6de3973eb11c8a
created_at: '2026-10-11T22:14:38.176329+00:00'
subtasks:
- T001
- T002
- T003
phase: Bounded retrospective record_path fix
history:
- at: '2026-10-12T00:00:00Z'
  actor: planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: python-pedro
authoritative_surface: src/specify_cli/retrospective/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/retrospective/lifecycle_events.py
- tests/retrospective/test_events.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5868'
---

# Work Package Prompt: WP01 – Repo-relative record_path + red-first regression

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load **python-pedro** before parsing the rest.
Run `.venv/bin/spec-kitty agent profile show python-pedro`.
Load scoped implement charter context (`spec-kitty charter context --action implement --json`); do not improvise.

- **Profile**: python-pedro
- **Role**: implementer
- **Issue**: #5868, assigned to the operator (`stijn-dejongh`).

## Objective

Make the `RetrospectiveCaptured` status event persist a **repository-relative**
`record_path` (`kitty-specs/<slug>/retrospective.yaml`) instead of an absolute
filesystem path. The absolute path leaks the operator's home directory and
username into the Mission's tracked, committed `status.events.jsonl` (it had to
be hand-scrubbed on #5856). Land this **red-first** per ADR 2026-07-17-1.

## Context (grounded)

- **Defect site** — `src/specify_cli/retrospective/lifecycle_events.py`,
  `emit_captured._build` (around line 466):
  ```python
  feature_dir = resolve_retrospective_home(repo_root, record.mission_slug)
  ...
  canonical_path = feature_dir / RETROSPECTIVE_FILENAME
  ...
  record_path=str(canonical_path),   # ← ABSOLUTE; this is the bug
  ```
- `resolve_retrospective_home(repo_root, slug)` composes the durable home via
  `_compose_primary_feature_dir(repo_root, slug)`, which joins `KITTY_SPECS_DIR`
  directly onto `repo_root` (no `resolve()`), so `canonical_path` is **always** a
  descendant of `repo_root`. Therefore `canonical_path.relative_to(repo_root)` is
  total for this input and cannot raise.
- No existing test asserts the value `emit_captured` itself computes
  (`tests/retrospective/test_events.py::test_retrospective_captured_to_dict`
  only constructs the dataclass directly), which is why the bug went uncaught.

## Subtasks

### T001 — Red-first regression (RED before the fix)

**Purpose**: Prove the absolute-path bug through the real `emit_captured` entry
point, pinned to #5868.

**Steps**:
1. In `tests/retrospective/test_events.py`, add a test under `TestEmitCaptured`
   (reuse the file's `make_gen_record`, `MISSION_SLUG`, `_RUNTIME_ACTOR`,
   `_read_events` helpers) that:
   - Builds a record and a `tmp_path` repo root with
     `kitty-specs/<MISSION_SLUG>/` created (as the sibling tests do).
   - Calls `emit_captured(record, tmp_path, provenance_kind=..., actor=...)`.
   - Reads the emitted event back from `status.events.jsonl` and asserts:
     - `record_path == f"kitty-specs/{MISSION_SLUG}/retrospective.yaml"`.
     - `not record_path.startswith("/")` (not absolute).
     - `str(tmp_path) not in record_path` (no host-root / username segment).
2. While proving RED, mark it `@pytest.mark.regression` and cite `#5868` in the
   docstring. Confirm it is RED on the current surface:
   `.venv/bin/python -m pytest tests/retrospective/test_events.py -k <new_test> -q`
   (it must FAIL because the emitted path is absolute).

**Validation**: the new test fails before T002, for the right reason (absolute
path), not an import/fixture error.

### T002 — The surface fix

**Purpose**: Persist the repository-relative path.

**Steps**:
1. In `emit_captured._build`, replace `record_path=str(canonical_path)` with the
   repo-relative POSIX form, e.g.:
   ```python
   record_path=canonical_path.relative_to(repo_root).as_posix(),
   ```
2. Change nothing else in the envelope (NFR-001 — byte-identical except this
   field). Do not touch `canonical_path` itself (it remains the absolute `Path`
   used for I/O).

**Validation**: the T001 regression now passes.

### T003 — Prove green + settle the test + lint

**Steps**:
1. Run the new test and the full retrospective events suite:
   `.venv/bin/python -m pytest tests/retrospective/test_events.py -q` (all green).
2. Per ADR 2026-07-17-1, settle the transitional repro into its functional home:
   it already lives in `tests/retrospective/test_events.py` (the home of
   `emit_captured` tests), so **drop the `@pytest.mark.regression` marker** and
   keep it as a permanent focused unit test, retaining the `#5868` citation in
   the docstring. (Do not leave it marked `regression`.)
3. Confirm clean lint/type on both touched files:
   `.venv/bin/ruff check src/specify_cli/retrospective/lifecycle_events.py tests/retrospective/test_events.py`
   `.venv/bin/ruff format --check --force-exclude src/specify_cli/retrospective/lifecycle_events.py tests/retrospective/test_events.py`
   `.venv/bin/mypy src/specify_cli/retrospective/lifecycle_events.py`

**Validation**: all green; ruff + mypy report zero issues; no suppressions added.

## Branch Strategy

- **Planning base**: `fix/retrospective-record-path-relative`
- **Final merge target**: `fix/retrospective-record-path-relative` (then a PR targets upstream `main`)
- Execution worktree is allocated per the computed lane in `lanes.json`; do not pick a base branch manually.

## Definition of Done

- [ ] `emit_captured` persists `record_path = kitty-specs/<slug>/retrospective.yaml` (relative, POSIX).
- [ ] Red-first regression existed and was RED before T002, green after.
- [ ] Final test is a focused unit test in `tests/retrospective/test_events.py`, no lingering `regression` marker, cites #5868.
- [ ] Envelope otherwise unchanged (NFR-001).
- [ ] `ruff check`, `ruff format --check`, and `mypy` clean on both touched files; complexity ≤ 15; no suppressions.

## Reviewer Guidance

- Verify the regression genuinely fails on the pre-fix surface (not a vacuous assert).
- Verify no other envelope field changed and no other call site was altered.
- Verify the final test carries no `regression` marker and the `#5868` pin is preserved in prose.
- Confirm forward-only scope (no backfill/migration added).
