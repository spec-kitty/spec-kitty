---
work_package_id: WP01
title: Facade re-export gate sees non-class values
dependencies: []
requirement_refs:
- FR-001
planning_base_branch: feat/charter-kind-tier-vocab-closeout
merge_target_branch: feat/charter-kind-tier-vocab-closeout
branch_strategy: Planning artifacts for this mission were generated on feat/charter-kind-tier-vocab-closeout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/charter-kind-tier-vocab-closeout unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
phase: Phase 1 - Facade enabler
history:
- at: '2026-10-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: tests/architectural/test_charter_facades_reexport_offering.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_charter_facades_reexport_offering.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Facade re-export gate sees non-class values

Closes #5836 (test-only). Enabler for WP02.

## Objectives & Success Criteria

- `tests/architectural/test_charter_facades_reexport_offering.py::test_facade_all_reexports_are_tabled` must also catch a re-exported **non-class** value (tuple/frozenset) that lacks `__module__`.
- A planted non-class `charter.offering`-origin re-export advertised in `__all__` but absent from `_FACADE_TABLE` is **reported**.
- The existing class path and the existing `test_planted_non_identical_offering_reexport_is_reported` self-test stay green; all 120+ live facade cases stay green.

## Context & Constraints

Root cause (grounded): `_untabled_reexports` (around line 377) does `origin = getattr(getattr(facade, name, None), "__module__", None)`. A plain value has no `__module__` → `origin is None` → the symbol is silently skipped. Today `CORE_KIND_PLURALS` (via `charter.drg`) and `RECOGNISED_ARTIFACT_DIRS` (via `charter.packs`) are covered only by hand-added `_FACADE_TABLE` rows, not enforced.

`_IDENTITY_REQUIRED_ORIGINS = {"charter.offering", "spec_kitty_events", "spec_kitty_tracker"}`. Red-first (C-003): T001 before T002.

## Subtasks & Detailed Guidance

### Subtask T001 – Non-class re-export self-test (RED first)

- Build on the existing `test_planted_non_identical_offering_reexport_is_reported` pattern. Plant a fake module exposing a non-class value (e.g. a `tuple`) that `is` an attribute of a real `charter.offering` module (reuse an actual offering constant so identity holds), advertised in `__all__`, not in `covered`.
- Assert `_untabled_reexports(planted, set())` reports it, and `_untabled_reexports(planted, {name})` does not.
- Confirm it FAILS against the current `__module__`-only implementation (RED).

### Subtask T002 – Identity-scan origin resolution

- Change `_untabled_reexports` so that for a symbol whose object yields no usable `__module__`, it resolves origin by scanning the `_IDENTITY_REQUIRED_ORIGINS` modules (and their already-imported submodules) for an attribute that `is` the facade object; if found, treat that module as the origin and require a table row.
- Keep the fast `__module__` path for classes/functions. Match plain values strictly by `is` identity (never `==`) so two equal-but-distinct tuples are not conflated.
- Avoid import cycles / heavy new imports: scan modules already reachable via the origins, not an arbitrary walk of `sys.modules`.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_charter_facades_reexport_offering.py -q` (or `uv run --frozen pytest ...`).
- `ruff check` + `ruff format --check --force-exclude` the file; `mypy` clean.

## Review Guidance

- Verify RED→GREEN: T001's assertion fails on the pre-T002 code and passes after.
- Confirm no live facade case regressed and the existing wrapper self-test still passes.

## Activity Log

- 2026-10-09T20:40:00Z – system – Prompt created.
