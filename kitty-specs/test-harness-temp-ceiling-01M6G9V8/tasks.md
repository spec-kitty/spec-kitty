# Tasks: Test harness temp ceiling

**Mission**: `test-harness-temp-ceiling-01M6G9V8` (#7076)
**Plan**: `kitty-specs/test-harness-temp-ceiling-01M6G9V8/plan.md`
**Spec**: `kitty-specs/test-harness-temp-ceiling-01M6G9V8/spec.md`

## Subtask Index

| Subtask | Work package | One line |
| --- | --- | --- |
| T001 | WP01 | Red: `tempfile` escapes the ceiling; hostile-temp-root walk finds a project |
| T002 | WP01 | `tests/_support/temp_root.py`: install the temp root, expose the harness env for children |
| T003 | WP01 | Wire it into `pytest_configure` and re-create it after pytest's basetemp reset |
| T004 | WP01 | Unit tests for the install (no basetemp, env trio, `tempfile.tempdir` reset, idempotent re-create) |
| T005 | WP02 | Red: the six from-scratch / `GIT_*`-stripped child environments drop the ceiling |
| T006 | WP02 | Carry the ceiling into the five from-scratch helpers |
| T007 | WP02 | Restore the ceiling in the bake-commit `_hermetic_env` fixture |
| T008 | WP03 | Red: `inspect.signature` still shows `stop`, and the three callers use it |
| T009 | WP03 | Drop `stop=` from `locate_project_root` and `find_repo_root` |
| T010 | WP03 | Move the three callers onto the per-test `GIT_CEILING_DIRECTORIES` narrowing |

## Dependency graph

```
WP01 ──► WP02
WP03 (independent)
```

WP02 consumes the helper WP01 adds (`tests/_support/temp_root.py`), so it runs after it. WP03
touches `src/` signatures and three unrelated test modules; it shares no file with WP01/WP02.

---

## WP01 — The harness temp root

**Goal**: make `tempfile` land below the run's basetemp, inside the ceiling #7022 installed, and
keep it there across pytest's lazy basetemp reset.

**Priority**: P1. **Independent test**: `tests/unit/test_harness_temp_root.py` and
`tests/_support/test_temp_root.py` alone.

**Subtasks**: T001, T002, T003, T004.

**Implementation sketch**:

1. T001 red: a harness-level test that (a) asserts `Path(tempfile.gettempdir())` is below
   `tmp_path_factory.getbasetemp()`, (b) builds the hostile fixture — a basetemp inside a
   repository — and asserts a `tempfile`-made directory resolves to no project, with the same
   fixture proving the walk *does* find that repository once the ceiling is removed.
2. T002: `tests/_support/temp_root.py` — `temp_root_dir(config)`, `install_temp_root(config,
   environ)` (sets `TMPDIR`/`TEMP`/`TMP`, resets `tempfile.tempdir`), `ensure_temp_root(path)`,
   `harness_env(environ)` (the child-environment subset).
3. T003: call `install_temp_root` in `pytest_configure` after `install_git_ceilings`, and add one
   session-scoped autouse hook in `tests/conftest.py` that calls
   `ensure_temp_root(tmp_path_factory.getbasetemp() / "tmp")` — the only point after pytest has
   removed and recreated the given basetemp.
4. T004: unit tests for the helper's edges.

**Risks**: the wipe ordering (documented in `research.md`); the worker isolated home must keep
resolving under the platform temp root, so the install goes *after* `_worker_home_base`.

---

## WP02 — From-scratch child environments

**Goal**: the five allowlisted child environments and the `GIT_*`-stripping fixture carry the
harness `GIT_CEILING_DIRECTORIES`, so a child's git and root walks hold the same boundary.

**Priority**: P1. **Independent test**: the new child-environment test module, plus the six
modules that own the helpers.

**Subtasks**: T005, T006, T007.

**Implementation sketch**:

1. T005 red: one test module that builds each site's environment through its real helper and
   asserts the ceiling is present and equals the harness value (and that a per-test narrowing is
   what the child inherits).
2. T006: merge `harness_env()` into `tests/upgrade/preview_support/process.py::child_environment`
   (keeping its own `sandbox/tmp` temp root), `tests/scripts/test_activate_isolated_env.py::_clean_env`,
   `tests/charter_offering/conftest_pack_remote.py::_env`,
   `tests/kernel/git/test_remote_fetch_commit_subtree.py::_env`,
   `tests/cross_cutting/packaging/test_sdist_offline_wheel.py::_offline_env`.
3. T007: `tests/consolidation/test_bake_commit_scope_meta_only.py::_hermetic_env` restores the
   ceiling after its `GIT_*` strip.

**Risks**: the strips exist to keep credentials and git config out — restore only
`GIT_CEILING_DIRECTORIES`, never the rest of `GIT_*`.

---

## WP03 — One boundary mechanism

**Goal**: `locate_project_root` and `find_repo_root` take no test-only boundary; their three test
callers bound the walk with the per-test ceiling instead.

**Priority**: P2. **Independent test**: the signature test plus the three affected modules.

**Subtasks**: T008, T009, T010.

**Implementation sketch**:

1. T008 red: assert `"stop" not in inspect.signature(...).parameters` for both walks, and that
   the three callers' modules fail if the parameter is still accepted.
2. T009: remove the parameter, its boundary handling, and the docstring paragraphs that describe
   it in `src/specify_cli/core/paths.py` and `src/specify_cli/task_utils/support.py`.
3. T010: the three callers set `GIT_CEILING_DIRECTORIES` to their own tree.

**Risks**: `session_start._find_project_root` keeps its `stop=` (C-002) — do not sweep it along;
PR #7082 is rewriting `paths.py` around `stop=`, so expect one mechanical conflict.
