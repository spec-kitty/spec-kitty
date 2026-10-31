# Implementation Plan: Record the planning commit in the birth-cutover fixture lanes.json

**Branch**: `issue-6801-birth-cutover-fixture-planning-commit` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/birth-cutover-fixture-planning-commit-01M66MFQ/spec.md`
**Input**: Mission specification from `kitty-specs/birth-cutover-fixture-planning-commit-01M66MFQ/spec.md`; issue spec-kitty/spec-kitty#6801.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Four anchor tests in `tests/migration/test_birth_cutover.py` fail deterministically on `main@512567eee7` because #6715's implementation-evidence gate (`src/specify_cli/consolidation/wp_evidence.py`) refuses the fixture's approved WP01 with `EVIDENCE_WINDOW_UNCOMPUTABLE`: `_write_single_lane` hand-writes a `LanesManifest` with no `planning_commit_sha`, and the fixture never runs the production `finalize-tasks` path that records one. Fix: the fixture records the planning commit exactly the way the production finalize path does — capture the current `target_branch` tip with `specify_cli.core.vcs.git.capture_branch_tip` at `lanes.json`-write time and store it as `LanesManifest.planning_commit_sha`, asserting the capture is non-None so a stale fixture fails at setup instead of three stages later. No `src/` behavior change, no assertion change, no gate change (see `research.md` for the fixture-vs-gate decision and its evidence).

## Technical Context

**Language/Version**: Python 3.11+ (uv-managed; `uv run --frozen`)
**Primary Dependencies**: pytest (fixtures under `tests/migration/`), `specify_cli` (test imports only)
**Storage**: N/A (test fixture files on disk: `kitty-specs/<slug>/lanes.json` inside a temp git repo)
**Testing**: `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q` — the four failing tests are the red-first proof (4 failed, 20 passed on main; must be 24 passed after). No full heavy suites in-mission (NO_FULL_HEAVY_SUITES_IN_MISSION).
**Target Platform**: Linux dev/CI
**Project Type**: single (CLI repo)
**Performance Goals**: N/A
**Constraints**: NFR-001 (no gate/assertion weakening), C-001 (test-only diff), C-002 (no xfail/skip)
**Scale/Scope**: one fixture helper (`_write_single_lane`) + its one caller in `tests/migration/test_birth_cutover.py`

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Pass. ATDD-first / red-first discipline is satisfied by the pre-existing failing tests (the defect is the fixture; the red exists on main and was reproduced before any change). Locality of change (DIRECTIVE_024) and smallest-viable-diff: a single helper edit plus a docstring. No structural boundary crossed; no ADR implicated (the planning-commit semantics of ADR `2026-07-29-1` are consumed as-is).

## Project Structure

### Documentation (this mission)

```
kitty-specs/birth-cutover-fixture-planning-commit-01M66MFQ/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding + fixture-vs-gate decision)
├── checklists/
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
tests/
├── migration/
│   └── test_birth_cutover.py   # _write_single_lane + _bootstrap_born_mission (the only touched file)
└── _support/                   # read-only imports (write_legacy_mission etc.)

src/
└── specify_cli/
    ├── consolidation/wp_evidence.py        # untouched (the gate stays fail-closed)
    ├── cli/commands/agent/tasks_finalize.py # read-only reference: the production capture semantics
    └── core/vcs/git.py                     # read-only: capture_branch_tip (the helper reused)
```

**Structure Decision**: single project; the change is confined to the migration test module that owns the broken fixture. No new files.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

None — no charter violations.

## Implementation Concern Map

*One small concern; no multi-area decomposition needed (the tasks step slices this into a single WP).*

### IC-01 — Fixture planning-commit parity

- **Purpose**: Make the hand-written `LanesManifest` record the `planning_commit_sha` the production finalize path would have recorded, so #6715's evidence window is computable and the four anchor tests pass again.
- **Relevant requirements**: FR-001, FR-002, NFR-002, C-001, C-002
- **Affected surfaces**: `tests/migration/test_birth_cutover.py` (`_write_single_lane`, `_bootstrap_born_mission` call site)
- **Sequencing/depends-on**: none
- **Risks**: (a) capture timing — the tip must be captured before the fixture's planning-content commit so the lane-tip tree diff contains the `src/a/**` change (verified for both topologies by the tests themselves); (b) silently recording `None` would recreate the red — mitigated by an explicit assertion (FR-002).
