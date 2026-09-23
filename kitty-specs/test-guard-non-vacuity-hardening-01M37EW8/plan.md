# Implementation Plan: Arch/Perf Test-Guard Non-Vacuity Hardening

**Branch**: `issue-4036-test-guard-non-vacuity-hardening` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)

## Summary

Tighten six deferred squad-flagged test-guards (epic #4883) so each **fails on the planted broken input it exists to catch** — closing the non-vacuous-guard defect class by construction (DIRECTIVE_043). **Test-infra only** (`tests/`, `pytest.ini`, `.github/workflows/ci-nightly.yml`); zero `src/` production change. Fix seams confirmed by the post-spec brownfield scout:

- **#4036** `tests/_support/repo_root_status_guard.py` + `tests/test_repo_root_status_guard.py`: window-scope the `assert not (REPO_ROOT/name).exists()` self-test (`:163-164`); document the concurrent-worker/between-tests straddle in the boundary block (`:52-56`). RED-first must prove a real cross-window straddle is caught.
- **#4105** `tests/architectural/test_no_dead_src_path_literals.py` **only**: scope `is_retired_doc`/`_DOC_STATUS_RE` (`:102/:225`) to the leading `---…---` frontmatter block; drop the unreachable `kitty-specs/` prefix from `ARCHIVE_PATH_PREFIXES` (`:95`); fix the `:98-101` comment. (`_dead_path_scan.py` OUT — different helper, 4 sibling importers.)
- **#4388** `tests/architectural/test_module_shard_registry.py`: add a test parsing `pytest.ini` (configparser) asserting no `python_files` override (or that it equals `_PYTHON_FILE_PATTERNS` `:412`). Reads `pytest.ini`, does not edit it.
- **#4408** `tests/architectural/_gate_coverage.py`: `_composite_action_path` (`:1136-1152`) must normalize/reject `..` and add an `is_relative_to(actions_dir)` containment check, mirroring `_resolve_script_path` (`:722-730`). Private fn, self-referenced only.
- **#4210** `tests/architectural/test_performance_marker_guard.py` + `pytest.ini` (marker desc `:58`) + `.github/workflows/ci-nightly.yml`: ADD a real-tree AST walk (`_iter_performance_marked_test_sources()` + a test calling the **unchanged pure** `find_functional_assertions_under_performance_marker(source)` per real `tests/**/test_*.py`, bounded + exemption list — signature preserved for `test_timing_coverage_invariant.py:51/525`); correct the stale marker desc; re-scope the ghost "e2e double-run" (already removed by #4865) to an invariant that `SPEC_KITTY_RUN_PERFORMANCE` stays scoped to the performance job.
- **#4536** `tests/performance/test_cli_startup_budget_4409.py`: add a min-scanned-file floor (`:92-96`), extend the AST visitor to flag `importlib.import_module`/`__import__` string args (`:55-83`), correct the docstring (`:18-19/:88-91`). C-003-safe (no dynamic jsonschema import in `src/`).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest (+ stdlib `ast`, `configparser`, `pathlib`) — test-infra only, no new runtime deps
**Testing**: pytest over `tests/architectural/`, `tests/performance/`, `tests/_support/`
**Target Platform**: CI (Linux) + local dev
**Project Type**: single (test-infra hardening)
**Performance Goals**: guards stay deterministic and sub-second where `fast`-marked (bound the #4210 tree walk)
**Constraints**: test-infra only (zero `src/` production change, C-003); every guard non-vacuous by construction (DIRECTIVE_043)
**Scale/Scope**: 6 guards across 6 disjoint files, 2 work packages

## Charter Check
- **DIRECTIVE_043 non-vacuity** ✅ — each tightened guard carries a self-mutation/planted-broken-input demonstration (C-001/C-002).
- **Test-infra only (C-003)** ✅ — scout verified no finding's real fix requires a `src/` change.
- **No whack-a-field** ✅ — `_dead_path_scan.py` (4 importers) and the pure perf fn signature (sibling import) are explicitly preserved; only private/self-referenced surfaces change behaviour.

## Work Package decomposition (disjoint edit sets → parallelizable)

```
WP01 (architectural guards): #4105 + #4388 + #4408   — tests/architectural/*
WP02 (perf + support guards): #4210 + #4536 + #4036  — tests/performance/, tests/_support/, pytest.ini, ci-nightly.yml
```

- **WP01 owns**: `tests/architectural/test_no_dead_src_path_literals.py` (#4105), `tests/architectural/test_module_shard_registry.py` (#4388), `tests/architectural/_gate_coverage.py` (#4408). Three disjoint architectural guard files. #4388 only READS `pytest.ini`.
- **WP02 owns**: `tests/architectural/test_performance_marker_guard.py` + `pytest.ini` + `.github/workflows/ci-nightly.yml` (#4210), `tests/performance/test_cli_startup_budget_4409.py` (#4536), `tests/_support/repo_root_status_guard.py` + `tests/test_repo_root_status_guard.py` (#4036).
- **No cross-WP edit collision**: only WP02 EDITS `pytest.ini` (marker desc) and `ci-nightly.yml`; WP01's #4388 only reads `pytest.ini` (a different concern — `python_files`), so consolidation is clean. Independent, no dependencies, parallelizable.
- Each WP lands **one issue-pinned `@pytest.mark.regression` non-vacuity demonstration per finding** (RED on base = guard passes on planted broken input; GREEN after = guard fails on it), then the demonstration becomes the guard's permanent non-vacuity test (not left `regression`).

## Risks
- **R1 (#4210 tree-walk cost)** — AST-parsing `tests/**/test_*.py` on a `fast`-marked guard is the only cost concern; bound it (`rglob("test_*.py")`, `try/except SyntaxError`, exemption list); drop the `fast` marker if it exceeds sub-second.
- **R2 (#4036 fakeable red-first)** — a straddle is hard to plant; the reviewer must confirm the demonstration proves a real cross-window write is caught, not a comment-only change.
- **R3 (#4210 workflow blast radius)** — the `ci-nightly.yml` edit must keep sibling assertions green (`test_performance_marker_guard.py` workflow tests, `test_marker_job_completeness.py`).
- **R4 (whack-a-field)** — do NOT touch `_dead_path_scan.py` (#4105) or change the pure perf fn signature (#4210); both ripple to siblings.

## Testing Strategy
- Per WP: run the touched guard modules + a demonstration that each is RED-on-base / GREEN-after. WP01: `tests/architectural/test_no_dead_src_path_literals.py test_module_shard_registry.py` + the `_gate_coverage` consumers. WP02: `tests/architectural/test_performance_marker_guard.py test_marker_job_completeness.py test_timing_coverage_invariant.py tests/performance/test_cli_startup_budget_4409.py tests/test_repo_root_status_guard.py`.
- Mission-level: `git diff --stat` proves 0 `src/` files (SC-003); the six demonstrations are RED→GREEN (SC-001/SC-004); the real tree stays green (SC-002).
