---
work_package_id: WP02
title: '#4454 + #4208: ci-router.yml honesty (tests-only routing + gate classification)'
dependencies: []
requirement_refs:
- FR-004
- FR-005
planning_base_branch: fix/ci-honesty-actionable-fixes
merge_target_branch: fix/ci-honesty-actionable-fixes
branch_strategy: Planning artifacts for this mission were generated on fix/ci-honesty-actionable-fixes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-honesty-actionable-fixes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-honesty-actionable-fixes-01M2JAXX
base_commit: c9dc9ee55f1b06b600e7c9cd5a4ad9a68e077d44
created_at: '2026-09-15T12:39:11.096468+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - CI honesty fixes
history:
- at: '2026-09-15T11:45:58Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/ci-router.yml
create_intent:
- scripts/ci/router_gate.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- scripts/ci/router_gate.py
- tests/architectural/test_gate_selection_authority.py
- tests/architectural/test_dual_mode_contract.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – #4454 + #4208 ci-router.yml honesty

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Two router-honesty fixes that share `.github/workflows/ci-router.yml` (consolidated into one WP to
keep the file in a single worktree). Done when:

- **#4454**: a diff confined to `tests/<module>/**` selects the SAME module group set a
  `src/**` change to that module selects; RED-first in `tests/architectural/test_gate_selection_authority.py`.
- **#4208**: a timeout-killed job is reported `timed_out` distinctly from external-cancel at the
  router-gate, with the pass/fail **blocking decision byte-identical to baseline**; RED-first in
  `tests/architectural/test_dual_mode_contract.py`.
- Both tests RED on base `36d866d4fa`, GREEN on the fix; `ruff`/`ruff format`/`mypy --strict` clean.

## Context & Constraints

- Design: `research.md` (Decisions 2 & 3), `contracts/helper-contracts.md` (router_gate contract),
  `work/ci-honesty-4437/lenses/A-gate-classification.md` and `lenses/D-out-of-matrix.md` (#4454).
- **#4454 mechanism**: `select_modules` (`scripts/ci/gate_selection.py:213`) intersects matched
  router groups with the registry inventory; no group carries a `tests/<module>/**` glob → a
  tests-only diff selects `[]`. Fix (Option 1): add `tests/<module>/**` (+ `tests/ci/**`) globs to the
  hand-authored router filter groups so the existing parser selects the owning module. Mirror into the
  SAME groups the module's `src/**` paths live in (e.g. `status` src is in `status`, `unit`,
  `execution_context`, `core_misc` — mirror `tests/status/**` into the same four). Two-authority
  contract preserved (C-002): NO second test-dir→module map.
- **#4208 mechanism**: `ci-router.yml:568-572` folds `cancelled` into the blocking set with `failure`;
  a `timeout-minutes` kill collapses to `cancelled` in the `needs` context (which cannot carry
  `timed_out`). Fix (Shape 1): extract `scripts/ci/router_gate.py` `classify(conclusions)` reusing the
  jobs-API conclusion vocabulary in `scripts/ci/fleet_verdict.py:89`; the router-gate step reads the
  jobs-API conclusions and calls `classify`, reporting `timed_out` distinctly. **Blocking policy
  unchanged** (NFR-001).
- **OUT OF SCOPE (C-001)**: do NOT touch the `ci-router.yml` concurrency stanza (`:35-37`, that is
  #4347), `ci-fleet-verdict.yml`, or the aggregate.
- **Watch**: `tests/architectural/test_no_duplicate_suite_execution.py` — adding `tests/<module>/**`
  must not make `tests/docs/**` / `tests/e2e` double-route; and `test_gate_selection_authority.py`'s
  authority/consistency guards (`:91`, `:104`).

## Branch Strategy

- **Planning base branch**: `main` · **Merge target branch**: `main`
- Execution worktree allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T006 – [P] RED: tests-only selects owning module (#4454)
- **Steps**: In `tests/architectural/test_gate_selection_authority.py` add
  `test_select_modules_selects_owning_module_on_tests_only_change`: assert `"status" in select_modules(["tests/status/test_store.py"])`
  and `"ci" in select_modules(["tests/ci/test_ci_module_wiring.py"])`. RED on base (returns `frozenset()`).
- **Files**: `tests/architectural/test_gate_selection_authority.py`.

### Subtask T007 – Add router filter-group globs (#4454)
- **Steps**: In `.github/workflows/ci-router.yml` add `tests/<module>/**` globs to each module's
  existing filter groups (and `tests/ci/**` to the `ci` group), mirroring the exact group set each
  module's `src/**` paths occupy. Do not narrow to one owning module.
- **Files**: `.github/workflows/ci-router.yml`.
- **Notes**: `gate_selection.py` parses the router live — no code change to `select_modules` needed.

### Subtask T008 – [P] RED: timed_out distinct + blocking unchanged (#4208)
- **Steps**: In `tests/architectural/test_dual_mode_contract.py` add a test that
  `classify({"tests-cli":"timed_out","tests-e2e":"failure"})` labels `tests-cli` as `timed_out`
  (distinct from `cancelled`) and blocks; and that `{"tests-cli":"cancelled","tests-e2e":"cancelled"}`
  still blocks (byte-identical verdict). RED on base (no classifier exists).
- **Files**: `tests/architectural/test_dual_mode_contract.py`.

### Subtask T009 – Extract + wire the classifier (#4208)
- **Steps**: Create `scripts/ci/router_gate.py` with `classify(conclusions) -> GateDecision`
  (contract C-gate-1..4), reusing the conclusion vocabulary from `fleet_verdict.py:89`. Update the
  `ci-router.yml` router-gate step (`:551-577`) to populate conclusions from the Actions jobs API and
  call `classify`, reporting `timed_out` distinctly in the summary/`SystemExit` message. Blocking set
  membership unchanged.
- **Files**: `scripts/ci/router_gate.py` (new), `.github/workflows/ci-router.yml`.
- **Notes**: Declare `__all__`; `mypy --strict`. Consider a shared conclusion-vocabulary constant with
  `fleet_verdict.py` rather than duplicating the set (Sonar S1192).

### Subtask T010 – Verify red→green (both fixes)
- **Steps**: `pytest tests/architectural/test_gate_selection_authority.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_no_duplicate_suite_execution.py -q`;
  full `tests/architectural/` + `tests/ci/` blast radius; `ruff check . && uv run --frozen ruff format --check . && mypy --strict scripts/ci/router_gate.py`.
- **Notes**: Record red-on-base/green-on-fix for BOTH #4454 and #4208 in the Activity Log.

## Test Strategy

Two RED-first pins (T006, T008), both red on `36d866d4fa`. Blast radius: full `tests/architectural/`
(router transcription/authority + no-duplicate-suite guards) and `tests/ci/`.

## Risks & Mitigations

- **Double-routing** from new `tests/` globs → `test_no_duplicate_suite_execution` guards it (T010).
- **Second-authority drift** (#4454) → Option 1 keeps a single authority (globs in the router).
- **Accidentally changing the blocking verdict** (#4208) → C-gate-2 pins byte-identical blocking.

## Review Guidance

- Both RED-first tests red on base, green on final.
- #4208 blocking decision unchanged; #4454 mirrors the identical group set (not one module).
- No edits to concurrency stanza `:35-37` / fleet-verdict (C-001).

## Activity Log

- 2026-09-15T11:45:58Z – system – Prompt created.
