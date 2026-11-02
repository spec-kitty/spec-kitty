# Implementation Plan: Golden dry-run rendering is order-independent

**Branch**: `kitty/mission-golden-dry-run-order-independence-01M6EJX3` | **Date**: 2026-11-02 | **Spec**: `kitty-specs/golden-dry-run-order-independence-01M6EJX3/spec.md`
**Input**: Mission specification from `kitty-specs/golden-dry-run-order-independence-01M6EJX3/spec.md`

## Summary

`test_golden_applied_dry_run` pins the whole rendered output of `spec-kitty upgrade --dry-run`, but
one of its inputs is computed live from the pytest-isolated home: the supporting-repair preview
count. On an empty worker home that count is 125; once an earlier test in the same worker has run a
real upgrade it is 1. The golden therefore passes module-wide and fails node-selected.

The technical approach is to stop letting the golden read that environment and keep everything
else. The dry-run golden stubs `upgrade_module._supporting_repair_preview` — the seam the same
module's matrix rows and the integration tests already use — with the exact complete-preview
sentence the pinned text already contains, asserts the stub was consulted exactly once, and keeps
the byte-identical expected-output constant. No production code changes.

## Technical Context

**Language/Version**: Python 3.11 (repository standard; `uv run --frozen`)
**Primary Dependencies**: pytest, typer `CliRunner`, `unittest.mock.monkeypatch` (test-only change; no new dependency)
**Storage**: N/A — the test fixture writes a throwaway git-backed project under pytest `tmp_path`
**Testing**: targeted pytest node and module runs (`tests/upgrade/test_upgrade_outcome_rendering.py`), single-node selection first (red), then the whole module (green), then the neighbouring upgrade suites
**Target Platform**: Linux, macOS, Windows 10+ (the test must stay platform-neutral: no path or mode assumptions added)
**Project Type**: single project (CLI package `src/specify_cli/`, tests under `tests/`)
**Performance Goals**: unchanged; no new subprocess pytest run and no new test file (NFR-002)
**Constraints**: exact-match golden output; no skip/xfail/deselect; no `src/` diff (C-001, C-002, FR-004)
**Scale/Scope**: one test plus one module-level constant in one file; plus changelog fragment and mission artifacts

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-First (C-011) / DIRECTIVE_034** — the red is the existing golden failing through the
  pre-existing entry point (the real `upgrade --dry-run` command) under node selection; the fix
  makes that same node green with no change to what it asserts about rendering. PASS.
- **DIRECTIVE_041 (judge the test)** — the assertion is valid (it pins real rendered text); its
  *input* is stale/environment-derived. The rule's verdict here is "fix the test's input", not
  "delete the assertion" and not "change the product". PASS.
- **acceptance-criteria-non-vacuity** — the stub is paired with a call-count assertion so a refactor
  that stops previewing cannot pass silently; the production entry point (the CLI command) is still
  the thing under test. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — validation is the owning module plus the two neighbouring
  upgrade suites; CI owns the rest. PASS.
- **Smallest-viable-diff (RECONCILE_CHANGE_SCOPE_TENSIONS)** — one test file, one constant, one
  comment; no `src/`, no fixture, no conftest change. PASS.
- **Terminology canon** — no new user-facing strings; the existing rendered text is unchanged. PASS.
- **Pre-existing Failure Reporting Rule** — the only red encountered is this mission's own subject;
  no unrelated red observed at grounding time (whole-module run is green on `main`). PASS.

No violations, so Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/golden-dry-run-order-independence-01M6EJX3/
├── plan.md              # this file
├── research.md          # discovery findings (D1-D4, grounding evidence)
├── spec.md              # requirements and acceptance scenarios
├── issue-matrix.md      # #7030 claim + terminal verdict
├── traces/              # tooling-friction.md, approach.md, design-decisions.md
└── tasks.md             # owned by /spec-kitty.tasks
```

No `data-model.md`, `contracts/` or `quickstart.md`: the mission adds no entity, no wire contract
and no operator procedure — it changes one test's inputs.

### Source Code (repository root)

```
tests/
└── upgrade/
    └── test_upgrade_outcome_rendering.py   # golden + matrix rows (the only production test file touched)

docs/
└── changelog/
    └── unreleased/
        └── <pr>.internal.md                # non-user-facing fragment (test-only change)
```

`src/` is untouched by design (FR-004); `git diff --stat origin/main -- src/` must stay empty.

**Structure Decision**: single-project layout, existing `tests/upgrade/` suite — no new directory,
no new module, no new fixture.

## Complexity Tracking

None — the Charter Check has no violations.

## Implementation Concern Map

### IC-01 — Deterministic dry-run preview input for the golden

- **Purpose**: Remove the only environment-derived input from the dry-run golden so the test's
  result depends on the code under test and nothing else, without dropping the preview line from
  what the golden proves.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003,
  SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/upgrade/test_upgrade_outcome_rendering.py` — `_GOLDEN_APPLIED_DRY_RUN`,
  `test_golden_applied_dry_run`, and the module's existing preview-stub helpers
  (`_PREVIEW_NOTICE`, `_stub_incomplete_preview`, `test_step_dry_run_*`)
- **Sequencing/depends-on**: none
- **Risks**: (a) a stub whose text silently drifts from the pinned golden — mitigated by deriving
  the stub's return value from one module constant and asserting the pinned text contains its
  rendering; (b) over-generalising the stub to other tests that intentionally exercise the
  incomplete-preview branch — mitigated by leaving `_stub_incomplete_preview` and the matrix rows
  untouched; (c) mistaking the fix for a coverage loss — mitigated by the call-count assertion and
  by recording in the PR that no existing test exercises the live count.
