---
work_package_id: WP02
title: 'Perf + support guards non-vacuity (#4210 #4536 #4036)'
dependencies: []
requirement_refs:
- FR-001
- FR-003
- FR-006
- NFR-001
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-4036-test-guard-non-vacuity-hardening
merge_target_branch: issue-4036-test-guard-non-vacuity-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-4036-test-guard-non-vacuity-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4036-test-guard-non-vacuity-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-guard-non-vacuity-hardening-01M37EW8
base_commit: 2b3e9e20cd548b2b5d5713b0a2b67602493c4d23
created_at: '2026-09-23T15:59:25.507593+00:00'
subtasks:
- T010
- T011
- T012
- T013
history:
- at: '2026-09-23T02:30:00Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_performance_marker_guard.py
- tests/performance/test_cli_startup_budget_4409.py
- tests/_support/repo_root_status_guard.py
- tests/test_repo_root_status_guard.py
- pytest.ini
- .github/workflows/ci-nightly.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro`; apply it and state what you applied. `PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest …` (never a bare `uv run`).

## Objective
Make the performance-marker guard, the CLI startup-budget guard, and the repo-root status guard discriminate. Read `../spec.md` (US3/FR-003, US6/FR-006, US1/FR-001) and `../plan.md`. RED-first non-vacuity demo per finding. **C-003: test-infra only — zero `src/` change** (verified safe by the scout: no dynamic jsonschema import in `src/`).

## Owned files (touch ONLY these)
`tests/architectural/test_performance_marker_guard.py`, `tests/performance/test_cli_startup_budget_4409.py`, `tests/_support/repo_root_status_guard.py`, `tests/test_repo_root_status_guard.py`, `pytest.ini`, `.github/workflows/ci-nightly.yml`.

## Subtasks
### T010 — #4210 additive real-tree walk + marker desc + env-scope invariant
In `test_performance_marker_guard.py`: the guard runs only on planted TEXT (`_MISMARKED_FUNCTIONAL_PERFORMANCE_TEST` etc.), never AST-walks the real tree. ADD `_iter_performance_marked_test_sources()` + a test that AST-parses each real `tests/**/test_*.py` and calls the **UNCHANGED pure** `find_functional_assertions_under_performance_marker(source)` per file — **do NOT change that function's signature** (`test_timing_coverage_invariant.py:51/525` imports and calls it). Bound the walk: `rglob("test_*.py")`, `try/except SyntaxError`, explicit exemption list; if it exceeds sub-second, drop the module's `fast` marker. Correct the stale `pytest.ini` marker desc (`:58` "not selected by any live CI job" — the nightly `-m performance` job runs it). The "e2e double-run" is a GHOST (already removed by #4865): instead add a REAL invariant asserting `SPEC_KITTY_RUN_PERFORMANCE` is set on the performance nightly job ONLY (not leaked to any other job). Any `ci-nightly.yml` edit must keep sibling assertions green (`test_marker_job_completeness.py`, this file's own workflow tests `:217-384`). **RED-first demos**: a planted real `@pytest.mark.performance` test with a functional assertion is caught; a planted `SPEC_KITTY_RUN_PERFORMANCE` on a non-performance job is caught.

### T011 — #4536 startup-budget floor + dynamic-import + docstring
In `tests/performance/test_cli_startup_budget_4409.py`: `test_jsonschema_stays_out_of_module_scope` builds `offending` from `(REPO_ROOT/"src").rglob("*.py")` (`:92-96`) with NO min-count assertion → a mis-rooted/empty glob passes vacuously; add `assert len(scanned) > <floor>`. Extend `_module_scope_jsonschema_imports` (`:55-83`) to also flag `importlib.import_module("jsonschema")` / `__import__("jsonschema")` string args. Correct the docstring (`:18-19/:88-91`) — it walks all of `src/`, not "the CLI's import graph". **RED-first demos**: a mis-rooted/empty scan fails the floor; a planted dynamic `import_module('jsonschema')` (in a fixture string, NOT src/) is flagged.

### T012 — #4036 window-scope the status-guard self-test + document straddle
In `tests/test_repo_root_status_guard.py`: the self-test `assert not (REPO_ROOT / name).exists()` (`:163-164`) is an absolute claim (flaky under `-n auto`, doesn't express "this test didn't leak"). Window-scope it to the guard's per-test window. In `tests/_support/repo_root_status_guard.py`: document the concurrent-worker/between-tests straddle in the "Boundary" block (`:52-56`). **RED-first demo (must be REAL — the scout flagged this as the easiest to fake)**: prove a write that STRADDLES the per-test window (setup snapshot → teardown compare, `:166-188`) is now caught/correctly-attributed — not merely that a comment was added. The guard already has a genuine e2e firing proof (`:142-164`); this is a narrow discrimination tightening.

### T013 — demos permanent
Each demo committed RED-first (guard vacuous on base) then GREEN; leave as the guards' permanent non-vacuity tests (docstring-pin issue #).

## DoD
- Each of #4210/#4536/#4036 has a demo RED on base / GREEN after (record evidence; #4036's demo proves a real straddle).
- `git diff --stat` shows ZERO `src/` files (C-003/NFR-003).
- Targeted: `PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest tests/architectural/test_performance_marker_guard.py tests/architectural/test_marker_job_completeness.py tests/architectural/test_timing_coverage_invariant.py tests/performance/test_cli_startup_budget_4409.py tests/test_repo_root_status_guard.py` — record counts (the timing-coverage sibling MUST stay green → proves the pure-fn signature preserved). ruff/ruff-format/mypy clean; complexity ≤15.
- RED-first demo commit(s) before the fix. End messages with the Co-Authored-By/Claude-Session trailer.

## Reviewer guidance
Verify: the pure perf fn signature is UNCHANGED (`test_timing_coverage_invariant.py` green); the #4210 tree walk is bounded/non-flaky; #4036's demo proves a real straddle (not comment-only); the e2e-ghost was re-scoped to the env-scope invariant (not a no-op); zero `src/` files touched.
