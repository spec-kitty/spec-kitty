# WP01 review — cycle 1

Reviewer: reviewer-renata profile (review role, stronger tier than the implementation).
Base: `kitty/mission-test-harness-temp-ceiling-01M6G9V8` → `7d9dc2152d` (+ `8adefccea1`).
Verdict: **approved**.

## Anti-pattern checklist

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Dead code | PASS (with note) | `tests/_support/temp_root.py` is harness support, not `src/`; `install_temp_root` has one live caller (`tests/conftest.py::pytest_configure`), `ensure_temp_root`/`temp_root_for`/`temp_root_dir`/`TEMP_ROOT_NAME` are used by the install path and the two new test modules. **`harness_env` has no caller yet by design** — WP02 (`dependencies: [WP01]`) consumes it for the six child environments. If WP02 were dropped from the mission, `harness_env` would become dead code and must be deleted with it. |
| 2 | Synthetic-fixture test | PASS | `test_tempfile_root_is_below_the_run_basetemp` reads the state the real `pytest_configure` produced (no fixture shapes it), and `test_a_tempfile_dir_under_a_hostile_temp_root_resolves_no_project` calls the real `locate_project_root`, not a stub. Deleting the install reds the first (verified: `/tmp` vs the run basetemp). |
| 3 | Silent empty return | PASS | `install_temp_root` returns `None` only when the run has no basetemp (documented, and the unit test pins it); `_register_guard` returns early only for a pluginmanager-less stub config (documented). No `except: pass`. |
| 4 | FR coverage | PASS | FR-001: `test_install_points_every_temp_variable_at_the_root`. FR-002: the guard; **measured** — removing `_register_guard(...)` reds `test_tempfile_root_is_below_the_run_basetemp`, because `getbasetemp()`'s `rm_rf` deletes the root and `tempfile.gettempdir()` then *silently* falls back to `/tmp`. FR-003: the hostile-root test plus its non-vacuity control. |
| 5 | Frozen surface | PASS | `tests/conftest.py` is frozen on definition order (`tests/architectural/test_home_owner_behaviour.py`); no `FunctionDef` was added — an import, a call and one comment — and that module passes (22 passed with the new tests). |
| 6 | Locked decision | PASS | No `MUST NOT` in spec/plan/contracts is contradicted: no per-test fixture (NFR-002), no second reaper (C-004), no dependency on #7082 (NFR-004). |
| 7 | Shared-file ownership | PASS | `tests/conftest.py`, `tests/_support/temp_root.py`, `tests/_support/test_temp_root.py`, `tests/unit/test_harness_temp_root.py` appear only in WP01's `owned_files` (lanes.json lane-a). |
| 8 | Production fragility | N/A | No production code in this WP. |

## Findings raised and resolved in the WP

- **The guard's failure mode is silent** — with the guard removed, `tempfile` does not
  raise: `gettempdir()` validates candidates and falls through to `/tmp`. That makes the
  guard easy to delete in a future refactor without a loud error. Fixed in
  `8adefccea1`: the module docstring now states it, with the measured symptom.

## Verified

- `uv run pytest tests/unit/test_harness_temp_root.py tests/_support/test_temp_root.py tests/architectural/test_home_owner_behaviour.py -q` → 22 passed.
- `-n 2` worker run of the two new modules plus the ceiling/paths/tasks suites → 71 passed, 1 skipped (workers each get their own `popen-gwN/tmp`).
- `tests/status/test_store.py`, `tests/runtime/test_cold_install_sentinel_relocation.py`, `tests/unit/runtime/test_prompt_tmp_namespace.py`, `tests/specify_cli/lanes/test_resolve_lanes_dir.py`, `tests/architectural/test_session_reaper.py` → 82 passed (the `tempfile.gettempdir()` monkeypatchers are unaffected).
- Ruff check + format clean; mypy clean on `tests/_support/temp_root.py`.
