---
work_package_id: WP01
title: Coverage-honesty guards + authority fix (RED-first)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-002
planning_base_branch: feat/ci-coverage-honesty
merge_target_branch: feat/ci-coverage-honesty
branch_strategy: Planning artifacts for this mission were generated on feat/ci-coverage-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-coverage-honesty unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-coverage-honesty-01M3CZVN
base_commit: 8c58f4fe8352281ae14dc80322d5f40a2544ce85
created_at: '2026-09-25T20:05:04.600026+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation (guards)
history:
- at: '2026-09-25T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_foreign_coverage_guard.py
- tests/architectural/test_src_reachability_guard.py
- scripts/ci/coverage_guard_lib.py
- .github/ci-foreign-coverage-baseline.json
- tests/ci/test_coverage_guards.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_foreign_coverage_guard.py
- tests/architectural/test_src_reachability_guard.py
- tests/architectural/test_gate_selection_authority.py
- scripts/ci/coverage_guard_lib.py
- .github/ci-foreign-coverage-baseline.json
- tests/ci/test_coverage_guards.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the profile in the frontmatter before anything else.
- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Add the two enforced coverage-honesty invariants and fix the phantom-mirror authority bug. **GREEN-AT-BASELINE (revised per implementer finding F17 — NOT red-first).** The guards pass at a committed measured baseline (recording honest current debt) and fail only on a regression (a new dark package/root); WP02 remediation SHRINKS the baseline. The authority-gate fix is green-preserving. This dissolves the earlier atomic-landing risk — no red guard reaches main's always-on battery.

**Success (ALL GREEN at baseline)**:
- `pytest tests/architectural/test_foreign_coverage_guard.py tests/architectural/test_src_reachability_guard.py` PASSES at the seeded baseline (records `next`→`specify_cli.runtime` dark root + the ~50 in-matrix-dark packages + per-row ratios). Add a negative unit test proving a synthetic NEW dark package/root FAILS the guard.
- The src-reachability **truly-dark baseline** is seeded at the measured set (23 today per F18) and the guard passes at baseline; a NEW truly-dark package hard-fails. Data-only packages (no non-`__init__` `.py`) excluded.
- `pytest tests/architectural/test_gate_selection_authority.py tests/architectural/test_pyproject_shape.py` stays GREEN (C-002); baseline was 22 passed.
- `pytest tests/ci/test_coverage_guards.py` green.
- Each guard ≤ 5 s (NFR-002; F17 measured ~1682 files parsed once).

Read `contracts/guards-contract.md`, `research.md` (D1/D3/D8/D9 + ledger F17), and `data-model.md` before coding. The T001 lib + T004 authority fix were prototyped viable by the prior implementer; build on that.

## Subtasks

### T001 — Shared guard lib (`scripts/ci/coverage_guard_lib.py`)
Build the reusable analysis on `specify_cli.ast_analysis.imports` primitives (`module_of_import_from`, etc. — same as `tests/architectural/test_no_dead_symbols.py`). Provide:
- `imports_under_package(test_file: Path, pkg_prefix: str) -> bool` using a **full `ast.walk`** (deferred/function-level imports count).
- `resolve_test_dirs(row) -> list[Path]` with **module-tests.yml precedence** (explicit `test_dirs` else `tests/{module}`), NOT `_canonical_test_mirror`.
- `enumerate_src_packages() -> list[str]` — fs-walk `__init__.py`-bearing subpackages + loose top-level `*.py` modules under the 6 wheel roots (`kernel, glossary, mission_runtime, runtime, specify_cli, charter`); exclude data-only dirs (no `__init__.py`, e.g. `schemas`).
- `own_root_ratio(row) -> float` and `in_matrix_test_dirs() -> list[Path]`.
Scope every scan to the resolved dirs (NFR-002); add a hash cache only if the naive scan exceeds ~5 s.

### T002 — foreign-coverage guard (`test_foreign_coverage_guard.py`, FR-001) — green-at-baseline
For each row whose roots resolve to importable src packages:
- **INV-1a dark-root baseline (shrink-only)**: dark roots (imported by no test in resolved dirs) may not grow beyond the committed baseline. Today's baseline includes `next`→`specify_cli.runtime`. Does NOT hard-fail `next`. `agent` per-root floor is already met (do not expect it to fire).
- **INV-1b ratio ratchet (shrink-only)**: ratio ≥ committed baseline. No fixed global threshold.
- **Exempt** (recorded): non-src-root rows (`ci`); aggregate/inventory rows (`execution_context, core_misc, unit, specify_cli_runtime`).
Passes at baseline. Include a negative unit test: a synthetic new dark root FAILS.

### T003 — src-reachability guard (`test_src_reachability_guard.py`, FR-002) — two shrink-only baselines (F18-corrected)
- **Truly-dark baseline (shrink-only, hard-fail on GROWTH)**: packages imported by NO test anywhere. Seed the measured baseline (23 today, F18 — NOT ≈0; import analysis can't see subprocess/CLI-tested modules). Fail only on a NEW truly-dark package.
- **In-matrix-dark baseline (shrink-only)**: packages reachable only out-of-matrix/nightly (27 today, F18). Fail only on growth. `live_work` is already in-matrix-reachable.
- **Data-package exclusion (F18)**: exclude packages with no non-`__init__` `.py` module (`schemas`, `charter.activation.corpus`, `charter.activation.packs`, `specify_cli.skills.data`).
Passes at baseline; include negative unit tests (new truly-dark → hard fail; new in-matrix-dark → fail; shrink → pass).

### T004 — phantom-mirror fix (`test_gate_selection_authority.py`, FR-003) — GREEN-PRESERVING
Change tree derivation to default `tests/{module}` (exists) instead of `_canonical_test_mirror` (phantom `tests/agent_utils`); add INV-2 (every derived dir EXISTS on disk). Keep the file GREEN — do NOT let RED land here.

### T005 — seed baseline sidecar (`.github/ci-foreign-coverage-baseline.json`)
Compute and commit the CURRENT measured baseline so all guards pass at baseline: per-row own-root ratios, the dark-root set (incl. `next`→`specify_cli.runtime`), and the in-matrix-dark package set (~50). Document "MEASURED, never guessed" provenance in a header key. All fields are shrink-only.

### T006 — unit tests (`tests/ci/test_coverage_guards.py`)
Directly exercise the lib: import-under-package true/false (incl. a deferred import), resolver precedence, subpackage enumeration excludes data dirs + includes loose modules, ratio computation. These are the focused tests Sonar new-code coverage expects for the new helpers.

## Branch Strategy
Planning base `feat/ci-coverage-honesty`; final merge target `main` via one squashed PR. Execution worktree allocated per computed lane from `lanes.json`. **Do not merge this WP's red guards to `main` alone** — WP02 greens them; they land together (D9).

## Definition of Done
- All success criteria met; `ruff check`, `ruff format --check`, `mypy` clean on new files; no new `# noqa`/`# type: ignore`.
- Guards GREEN at seeded baseline; negative unit tests prove a new dark package/root FAILS; truly-dark floor reports ≈0; authority + pyproject-shape green.

## Reviewer guidance
Verify: guards pass at baseline AND a synthetic regression fails (not vacuously passing); truly-dark floor is a real hard check; authority test stays green; resolver uses module-tests precedence not the mirror; `ast.walk` catches deferred imports; baseline is measured with documented provenance; guard runtime ≤5 s.
