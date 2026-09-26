---
work_package_id: WP01
title: 'Architectural census/coverage guards non-vacuity (#4105 #4388 #4408)'
dependencies: []
requirement_refs:
- FR-002
- FR-004
- FR-005
- NFR-001
- C-001
- C-002
planning_base_branch: issue-4036-test-guard-non-vacuity-hardening
merge_target_branch: issue-4036-test-guard-non-vacuity-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-4036-test-guard-non-vacuity-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4036-test-guard-non-vacuity-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-guard-non-vacuity-hardening-01M37EW8
base_commit: 2b3e9e20cd548b2b5d5713b0a2b67602493c4d23
created_at: '2026-09-23T15:58:51.028801+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- at: '2026-09-23T02:30:00Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_gate_coverage_composite_path.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_no_dead_src_path_literals.py
- tests/architectural/test_module_shard_registry.py
- tests/architectural/_gate_coverage.py
- tests/architectural/test_gate_coverage_composite_path.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
`/ad-hoc-profile-load python-pedro`; apply it and state what you applied. Run pytest with `PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest …` (never a bare `uv run`).

## Objective
Make three vacuous `tests/architectural/` guards discriminate. Read `../spec.md` (US2/FR-002, US4/FR-004, US5/FR-005) and `../plan.md`. Each fix lands a RED-first non-vacuity demonstration (the guard currently PASSES on a planted broken input; after the fix it FAILS on it while still passing on the real tree). C-003: test-infra only.

## Owned files (touch ONLY these)
`tests/architectural/test_no_dead_src_path_literals.py`, `tests/architectural/test_module_shard_registry.py`, `tests/architectural/_gate_coverage.py`, `tests/architectural/test_gate_coverage_composite_path.py` (new). **Do NOT touch `tests/architectural/_dead_path_scan.py`** (different helper; 4 sibling importers).

## Subtasks
### T001 — #4105 frontmatter-scope the dead-src-path gate
In `test_no_dead_src_path_literals.py`: `is_retired_doc(text)` consumes `_DOC_STATUS_RE` (`:102`, MULTILINE) via `finditer(text)` (`:225`) over the WHOLE file, so a `doc_status:` line in a page's BODY/prose skips the file and a dead `src/…` literal in it passes vacuously. Scope `is_retired_doc` to the leading `---…---` frontmatter block only. Delete the unreachable `"kitty-specs/"` from `ARCHIVE_PATH_PREFIXES` (`:95`; `collect_dead_paths` only walks `docs/**`). Fix the over-claiming `:98-101` comment. **RED-first demo**: a `docs/*.md` fixture whose BODY (not frontmatter) has `doc_status: superseded` + a dead `src/nonexistent_xyz.py` → currently skipped (guard green = vacuous); after fix the dead path is caught, and a genuinely frontmatter-deprecated page still skips.

### T002 — #4388 anchor `_PYTHON_FILE_PATTERNS` to pytest.ini
In `test_module_shard_registry.py`: add a test that parses `pytest.ini` (`configparser`) and asserts it carries NO `python_files` override (or that it equals `_PYTHON_FILE_PATTERNS` `:412`). READ `pytest.ini`; do NOT edit it. **RED-first demo**: with a (transient, uncommitted) `python_files = check_*.py` planted in `pytest.ini`, the new assertion fails; without it, passes.

### T003 — #4408 `_composite_action_path` reject `..`
In `_gate_coverage.py` `_composite_action_path` (`:1136-1152`): after computing `name`, normalize and add an `is_relative_to(actions_dir)` containment check (mirror `_resolve_script_path` `:722-730`); a `..`-laden `uses:` must resolve to `None`, not a file outside the actions tree. The fn is private/self-referenced only — no signature change visible to the ~18 importers. **RED-first demo** (new `test_gate_coverage_composite_path.py`): `_composite_action_path("./.github/actions/../../secrets", actions_dir)` currently returns a path outside `actions_dir`; assert it returns `None` after the fix.

### T004 — non-vacuity demos become permanent
Ensure each demo above is committed RED-first (guard vacuous on base) then GREEN; leave them as the guards' permanent non-vacuity tests (docstring-pin the issue #; not left `@pytest.mark.regression` if they belong as unit tests). 

## DoD
- Each of #4105/#4388/#4408 has a demonstration RED on base / GREEN after (record evidence).
- `git diff --stat` shows ZERO `src/` files.
- Targeted: `PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest tests/architectural/test_no_dead_src_path_literals.py tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_coverage_composite_path.py` + any `_gate_coverage` consumer (`tests/architectural/test_marker_job_completeness.py`) — record counts. ruff/ruff-format/mypy clean on touched files; complexity ≤15.
- Commit ≥ RED-first demo(s) before the fix per finding. End messages with the Co-Authored-By/Claude-Session trailer.

## Reviewer guidance
Verify each demo genuinely fails on base (vacuous) before the fix. Reject if `_dead_path_scan.py` was touched, if `_composite_action_path` signature changed, or if any demo is comment-only / non-discriminating.
