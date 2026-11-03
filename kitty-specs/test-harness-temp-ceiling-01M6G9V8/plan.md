# Implementation Plan: Test harness temp ceiling

**Branch**: `issue-7076-test-harness-temp-ceiling` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/test-harness-temp-ceiling-01M6G9V8/spec.md`
**Input**: Mission specification from `kitty-specs/test-harness-temp-ceiling-01M6G9V8/spec.md`

## Summary

Point the whole test run's `tempfile` root at `<basetemp>/tmp`, which is inside the
`GIT_CEILING_DIRECTORIES` ceiling #7022 installs, so the 59 modules that build temporaries with
`tempfile` are bounded by the harness instead of escaping into a possibly-foreign repository
(`/tmp/.git` on this host). Carry the same ceiling into the six child environments that are built
from an allowlist or have `GIT_*` stripped, because those are the places the harness boundary
silently disappears. Then retire the second, test-only boundary mechanism: `stop=` leaves
`locate_project_root` and `find_repo_root`, and its three test callers use the per-test
`GIT_CEILING_DIRECTORIES` narrowing instead.

## Technical Context

**Language/Version**: Python 3.11+ (`pyproject.toml` floor; 3.13 in CI matrix)
**Primary Dependencies**: pytest 9.0.3, pytest-xdist (lazy basetemp), stlib `tempfile`
**Storage**: N/A
**Testing**: pytest; harness support lives in `tests/_support/`; the affected suites are
`tests/unit`, `tests/tasks`, `tests/status`, `tests/specify_cli/{core,cli/commands,charter_preflight,session_presence}`,
`tests/charter_offering`, `tests/kernel/git`, `tests/cross_cutting/packaging`, `tests/scripts`,
`tests/upgrade`, `tests/consolidation`
**Target Platform**: Linux CI shards, macOS developer machines, Windows `windows_ci` job
**Project Type**: single project (library + CLI)
**Performance Goals**: one extra `mkdir` per process; no per-test hook (NFR-002)
**Constraints**: no dependency on unmerged PR #7082; no gate weakened; per-test narrowings stay
**Scale/Scope**: 2 harness modules + `tests/conftest.py`, 6 child-environment sites, 2 `src/`
signatures with 3 test call sites, one regression test module

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
| --- | --- |
| Single canonical authority | **Pass** — the plan removes a second boundary authority (`stop=`) rather than adding one; the ceiling stays the one authority, read through `git_ceiling_dirs()`. |
| ATDD-First Discipline (DIRECTIVE_034) | **Pass** — every requirement lands with a failing test first: the harness temp-root invariant, the hostile-temp-root walk, the child-environment carry, and the signature removal each have a red test before the change (see tasks `T00x` red-first pairs). |
| Locality of change (DIRECTIVE_024) / smallest viable diff | **Pass** — no home-isolation, reaper, or `run_basetemp` change; the temp root is a subdirectory of a tree that already has a lifecycle. |
| Test-only production surface | **Pass** — the only `src/` change *removes* API (`stop=`), it does not add test hooks to production code. |
| Pre-existing Failure Reporting Rule | **Pass** — CI reds outside the diff are classified against the merge base and named in the PR's `## Deferred`. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | **Pass** — the plan runs targeted modules plus the fast/architectural gates, never a full heavy suite. |
| Windows parity | **Pass with risk noted** — `TMPDIR` is what `tempfile` reads first on Windows too; `TEMP`/`TMP` follow so child tools agree. Risk: longer paths under the basetemp on the Windows job; mitigated by keeping the subdirectory name short (`tmp`) and by the existing short run-dir name. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/test-harness-temp-ceiling-01M6G9V8/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 evidence (census, repro, pytest source)
├── tasks.md             # Phase 2 output (/spec-kitty.tasks)
└── tasks/               # work-package briefs
```

### Source Code (repository root)

```
tests/
├── conftest.py                              # pytest_configure: install the temp root after the ceiling
├── _support/
│   ├── git_ceiling.py                       # unchanged (ceiling owner)
│   ├── temp_root.py                         # NEW: temp root install + harness env for children
│   └── test_temp_root.py                    # NEW: unit tests for the install (fast, no subprocess)
├── unit/test_harness_temp_root.py           # NEW: harness-level red-first proof (ceiling covers tempfile)
├── upgrade/preview_support/process.py       # child_environment: carry the ceiling
├── scripts/test_activate_isolated_env.py    # _clean_env: carry the ceiling
├── charter_offering/conftest_pack_remote.py # _env: carry the ceiling
├── kernel/git/test_remote_fetch_commit_subtree.py  # _env: carry the ceiling
├── cross_cutting/packaging/test_sdist_offline_wheel.py  # _offline_env: carry the ceiling
└── consolidation/test_bake_commit_scope_meta_only.py    # _hermetic_env: restore the ceiling after the strip

src/specify_cli/
├── core/paths.py                            # locate_project_root: drop stop=
└── task_utils/support.py                    # find_repo_root: drop stop= and the forwarded boundary
```

**Structure Decision**: single project. Harness policy is a `tests/_support/` module beside
`git_ceiling.py` (the ceiling owner) so `pytest_configure` keeps one call per concern and the
architectural frozen-definition-order test in `tests/architectural/test_home_owner_behaviour.py`
sees imported calls rather than new `FunctionDef`s in `tests/conftest.py`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Session-scoped autouse hook that re-creates `<basetemp>/tmp` | pytest removes and recreates a *given* basetemp on first use, so a configure-time directory is deleted before the first test | A bare `mkdir` in `pytest_configure` leaves `TMPDIR` pointing at a deleted directory; `PYTEST_DEBUG_TEMPROOT` does not apply to a given basetemp |

## Implementation Concern Map

### IC-01 — The harness temp root

- **Purpose**: Make `tempfile` land below the run's basetemp and survive pytest's lazy basetemp reset, so the ceiling #7022 installed covers every temporary the suite makes.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, NFR-003, C-004, SC-001, SC-002
- **Affected surfaces**: `tests/_support/temp_root.py`, `tests/conftest.py` (`pytest_configure` + one session autouse hook), `tests/unit/test_harness_temp_root.py`, `tests/_support/test_temp_root.py`
- **Sequencing/depends-on**: none
- **Risks**: the wipe window (mitigated by the hook ordering documented in `research.md`); xdist workers each own a basetemp, so the install must read the per-process option, not a controller constant; the worker isolated home must keep using the platform temp root (it is computed before the install).

### IC-02 — From-scratch child environments

- **Purpose**: Stop the six allowlisted/`GIT_*`-stripping child environments from dropping the harness boundary, so a child's git and root walks cannot climb out of the test's tree.
- **Relevant requirements**: FR-004, NFR-001, C-001, SC-003
- **Affected surfaces**: `tests/_support/temp_root.py` (the shared env helper), the five `_env`/`_clean_env`/`child_environment` helpers, `tests/consolidation/test_bake_commit_scope_meta_only.py::_hermetic_env`
- **Sequencing/depends-on**: IC-01 (the helper lives in the same module and the tests assert against the installed value)
- **Risks**: the strips exist to keep credentials and git config out — only `GIT_CEILING_DIRECTORIES` (a discovery boundary) is restored, never the rest; a site that pins its own temp root (`preview_support.child_environment` → `sandbox/tmp`) keeps its own and only gains the ceiling.

### IC-03 — One boundary mechanism

- **Purpose**: Remove the test-only `stop=` boundary from the two walks that already honour the ceiling, so contributors see one documented boundary.
- **Relevant requirements**: FR-005, FR-006, C-002, SC-004
- **Affected surfaces**: `src/specify_cli/core/paths.py`, `src/specify_cli/task_utils/support.py`, `tests/specify_cli/charter_preflight/test_cli.py`, `tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py`, `tests/status/test_lock_fallback_never_mints_marker.py`
- **Sequencing/depends-on**: IC-01 (the three callers need the harness ceiling to be real before they can rely on the narrower per-test one; in practice they set their own, so the order is for review clarity, not correctness)
- **Risks**: `session_start._find_project_root` keeps `stop=` (C-002) and must not be swept along; #7082 is rewriting `paths.py` around `stop=`, so the removal is the one conflict this branch is likely to meet and is mechanical to resolve.
