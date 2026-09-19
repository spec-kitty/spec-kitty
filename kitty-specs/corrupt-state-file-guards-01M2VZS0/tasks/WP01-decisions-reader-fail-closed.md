---
work_package_id: WP01
title: Decisions reader fails closed
dependencies: []
requirement_refs:
- FR-002
- FR-004
planning_base_branch: fix/4642-corrupt-state-file-guards
merge_target_branch: fix/4642-corrupt-state-file-guards
branch_strategy: Planning artifacts for this mission were generated on fix/4642-corrupt-state-file-guards. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/4642-corrupt-state-file-guards unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-corrupt-state-file-guards-01M2VZS0
base_commit: 8faa3332e66a44f9b8deca8de08ba32ea2fa9328
created_at: '2026-09-19T05:07:26.135759+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- by: orchestrator
  at: '2026-09-19T05:00:00Z'
  note: 'Authored from IC-1 (mission corrupt-state-file-guards, #4642).'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/decisions/store.py
- src/specify_cli/decisions/__init__.py
- tests/specify_cli/decisions/test_store.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load` (profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and TDD discipline for this work package.

## Objective

Make `decisions/store.py:load_index` fail closed on a corrupt `decisions/index.json`: malformed JSON, non-UTF-8 bytes, and valid-JSON-wrong-shape must all surface as a new typed `DecisionIndexReadError` (never a raw `JSONDecodeError`/`UnicodeDecodeError`/pydantic `ValidationError`). The missing-file case must remain an empty index. Fixing this one reader closes the reader half for all six decision subcommands (WP02 wires the boundary).

## Context

- Root reader today (unguarded): `src/specify_cli/decisions/store.py:load_index` does `json.loads(path.read_text(encoding="utf-8"))` + `DecisionIndex.model_validate(raw)` with only a missing-file guard.
- Canonical precedent to MIRROR: `MissionMetaReadError` + `load_meta_fail_closed` in `src/specify_cli/core/paths.py`, which routes through the kernel decoder `kernel.meta_decode.decode_meta`.
- `kernel.meta_decode.decode_meta(raw: bytes|str, on_malformed=...)` is the canonical `bytes → dict` decoder: it does an explicit `.decode("utf-8")` on bytes (covering `UnicodeDecodeError`) then `json.loads` (covering `JSONDecodeError`) and rejects non-`dict` top level, raising `MetaDecodeError(ValueError)`. **Reuse it — do not hand-roll a parallel decoder.**
- `src/specify_cli/decisions/ownership.py:531` already re-implements this guard locally; you are moving the guard to the source reader (a later cleanup may retire the local one — out of scope here, just don't break it).

## Subtasks

### T001 — Red-first unit tests (write FIRST, must be RED)
In `tests/specify_cli/decisions/test_store.py` add focused unit tests that call `load_index(mission_dir)` directly:
- malformed JSON (`{ not json`) → raises `DecisionIndexReadError`
- non-UTF-8 bytes (`b"\xff\xfe\x00corrupt"` via `write_bytes`) → raises `DecisionIndexReadError` (NOT `UnicodeDecodeError`)
- wrong-shape dict (`{"entries": "not-a-list"}`) → raises `DecisionIndexReadError` (from the pydantic validation wrap)
- missing file → still returns an empty `DecisionIndex` (regression guard on the preserved branch)
- happy path: a valid index round-trips byte-identically to today
Run them first and confirm the three corruption cases are RED (raw exceptions today).

### T002 — Define `DecisionIndexReadError`
In `store.py`, add `class DecisionIndexReadError(RuntimeError)` mirroring `MissionMetaReadError`: carry `index_path: Path` and `cause`, and a message of the fail-closed shape including the offending path AND the `run: spec-kitty doctor` remediation hint (Q1 decision — unify on the doctor-hint shape). Keep the exact text aligned with `MissionMetaReadError`'s "fail-closed" phrasing so both read identically.

### T003 — Extract `_decode_index(path) -> DecisionIndex` helper
- `raw = decode_meta(path.read_bytes(), on_malformed="raise")` inside `try/except (MetaDecodeError, OSError) as exc: raise DecisionIndexReadError(path, exc) from exc`.
- Then `DecisionIndex.model_validate(raw)` inside `try/except ValidationError as exc: raise DecisionIndexReadError(path, exc) from exc` (import `ValidationError` from `pydantic`).
- Keep the helper small so `load_index` stays under complexity 15.

### T004 — Rewire `load_index` + export
- `load_index` keeps the missing-file guard FIRST (unchanged → empty index), then delegates to `_decode_index(path)`.
- Export `DecisionIndexReadError` from `src/specify_cli/decisions/__init__.py` so WP02's boundary can import it.

### T005 — Confirm green
Run the unit tests; all pass. Confirm the happy-path parse result is unchanged (the `read_text`→`read_bytes` switch is behavior-identical on valid UTF-8).

## Branch Strategy

Planning/base branch: `fix/4642-corrupt-state-file-guards`. Final merge target: `fix/4642-corrupt-state-file-guards`. Execution worktrees are allocated per computed lane from `lanes.json` — enter the workspace `spec-kitty implement WP01` resolves; do not reconstruct paths.

## Test Strategy (red-first, ADR 2026-07-17-1)

Unit tests in T001 are the red-first proof for this reader. They are unit-level (not `@regression`) because the entry-point `@pytest.mark.regression` repros live in WP02 (decisions boundary) and WP03 (next). Run:
```
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/decisions/test_store.py -q
```

## Definition of Done

- [ ] `load_index` raises `DecisionIndexReadError` for malformed-JSON, non-UTF-8, and wrong-shape; missing-file still returns empty index.
- [ ] `_decode_index` reuses `kernel.meta_decode.decode_meta`; no parallel decoder; no bare `except`.
- [ ] `DecisionIndexReadError` message carries the path + fail-closed + `run: spec-kitty doctor` hint.
- [ ] Exported from `decisions/__init__.py`.
- [ ] Complexity ≤ 15 on touched functions; ruff + mypy clean; no new suppressions.
- [ ] Unit tests green; happy path byte-identical.

## Risks / Reviewer guidance

- Wrong-shape fixture MUST be a dict; a JSON array is rejected by `decode_meta` as non-object before validation (still fine, but tests the wrong branch).
- Do not alter the missing-file→empty semantics; `open_decision` on a fresh mission depends on it.
