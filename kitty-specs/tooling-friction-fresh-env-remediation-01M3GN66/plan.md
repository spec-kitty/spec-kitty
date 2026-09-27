# Implementation Plan: Tooling friction — fresh-env derived-state & partition remediation

**Branch**: `claude/tooling-friction-investigation-gpb1yl` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/spec.md`

## Summary

Remediate the fresh-environment tooling-friction cluster (#4873, #4955, #5160, #5113). The dominant defect is that **derived / append-only mission state is treated as authoritative-and-git-mergeable, and coord-vs-primary partition surfaces disagree on write ownership.** The fixes converge on one canonical re-materialization authority for `status.json`, canonical union drivers for append-only logs seeded across all four registry surfaces, a corrected C-006 completeness guard, a primary-anchored planning `feature_dir`, plus one packaging mirror and one remedy-text correction.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, pytest, pytestarch, spec_kitty_events, spec_kitty_tracker
**Storage**: git-tracked mission artifacts (`kitty-specs/**`, `kitty-ops/**`); append-only JSONL event logs; derived JSON snapshots
**Testing**: pytest; `make test-fast` baseline + targeted blast-radius module tests; `tests/architectural/` for cross-cutting (pyproject/gitattributes/registry) changes
**Target Platform**: Linux/macOS developer + CI
**Project Type**: single (CLI + libraries under `src/`)
**Performance Goals**: N/A (correctness/reliability mission)
**Constraints**: preserve the #4785 charter-write-guard invariant (C-001); #5113 remedy-text-only (C-002); canonical sources only (C-003); no test skip/disable to green (C-004)
**Scale/Scope**: ~7 source seams + their tests; one cross-cutting packaging change; one merge-driver registry expansion (four bound surfaces + migration)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — status.json regeneration must be ONE shared helper (NFR-002); merge drivers seeded across the four bound surfaces (NFR-001). PASS by design.
- **Architectural alignment** — respect the placement seam (coord/primary) and the Status Model (event log is sole authority). PASS.
- **ATDD-first / red-first** — each fix pairs with a reproduction that is red before and green after (SC no-op-passable = no). PASS by design.
- **Terminology adherence** — Mission canon; run `tests/architectural/test_no_legacy_terminology.py` on prose/doctrine touches. PASS gate.
- **Canonical sources** — merge-driver additions via `_MergeDriverSeedingMigration`, reducer via `status/reducer.py`, no improvised substitutes. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/
├── spec.md              # committed
├── plan.md              # this file
├── tasks.md             # WP manifest (/spec-kitty.tasks)
└── tasks/               # WP prompt files
```

### Source Code (repository root)

```
src/specify_cli/
├── lanes/merge.py                     # _MERGE_DRIVERS registry; squash seam (_merge_branch_into)
├── lanes/worktree_allocator.py        # lane allocation merges (planning-commit / dependency-tip)
├── merge/bookkeeping_projection.py    # _rematerialize_status_snapshot (shared re-materialize authority)
├── decisions/index_fold.py            # fold_events (decisions/index.json re-fold)
├── cli/commands/merge_driver.py       # driver entrypoints
├── cli/commands/init.py               # init driver seed
├── coordination/surface_resolver.py   # CoordinationWorktreeUnmaterialized remedy text (#5113)
└── upgrade/migrations/                # new MergeDriverSeedingMigration subclass
src/mission_runtime/
├── artifacts.py                       # _MISSION_FILE_KIND_BY_BASENAME (guard enumeration)
└── resolution.py                      # resolve_action_context (planning feature_dir anchor)
.gitattributes                         # committed merge= driver lines
pyproject.toml                         # [dependency-groups].dev mirror of pytestarch
tests/…                                # regression + guard tests co-located with each seam
```

**Structure Decision**: single-project layout; each concern edits its owning module and adds tests in the mirrored test dir. No new top-level packages.

## Complexity Tracking

No charter violations. Keep new/edited functions ≤15 complexity (NFR-004) by extracting helpers (e.g. the shared re-materialization wrapper).

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Charter JSON contract test isolation (#4873)

- **Purpose**: Let the three charter JSON error-contract tests assert their contracts from any cwd, so `make test-fast` is green from an isolated linked worktree.
- **Relevant requirements**: FR-001; C-001 (no production change).
- **Affected surfaces**: `tests/cli/commands/test_charter_json_error_contract.py` (add the canonical `autouse` `_isolate_cwd_from_worktree_guard` fixture from `tests/specify_cli/cli/commands/test_charter_resynthesize.py`).
- **Sequencing/depends-on**: none.
- **Risks**: none; test-only, mirrors an existing canonical fixture.

### IC-02 — Dev-dependency packaging mirror (#5160 friction 2)

- **Purpose**: Ensure a plain `uv sync` / `uv run --frozen` lane venv carries `pytestarch`, so architectural tests don't false-red.
- **Relevant requirements**: FR-002.
- **Affected surfaces**: `pyproject.toml` `[dependency-groups].dev` (+ `uv.lock` regen); a pyproject-shape guard in `tests/architectural/test_pyproject_shape.py`.
- **Sequencing/depends-on**: none.
- **Risks**: cross-cutting (pyproject) → run `tests/architectural/` in full.

### IC-03 — Shared `status.json` re-materialization authority (NFR-002)

- **Purpose**: One helper that regenerates `status.json` from a union-merged event log, reused by both lane allocation and the squash seam (no second copy).
- **Relevant requirements**: NFR-002; enables FR-003 and FR-004.
- **Affected surfaces**: `src/specify_cli/merge/bookkeeping_projection.py::_rematerialize_status_snapshot` (hoist/extract a shared entry), `src/specify_cli/status/reducer.py`.
- **Sequencing/depends-on**: precedes IC-04 and IC-05.
- **Risks**: the T012 AST lint whitelists a specific write shape — keep the sanctioned seam.

### IC-04 — Lane-allocation derived-state regeneration (#5160 friction 1)

- **Purpose**: After the allocation merges, regenerate a conflicting derived `status.json` from the merged log instead of failing closed.
- **Relevant requirements**: FR-003; consumes IC-03.
- **Affected surfaces**: `src/specify_cli/lanes/worktree_allocator.py` (`_merge_recorded_planning_commit`, `_merge_dependency_lane_tips`).
- **Sequencing/depends-on**: IC-03.
- **Risks**: must NOT green-wash human-authored conflicts (`tasks/WP*.md`); preserve the #4905 `wp_task_conflicts` diagnostic.

### IC-05 — Squash-seam reconciliation + driver registry + C-006 guard (#4955)

- **Purpose**: Reconcile derived/append-only artifacts on the mission→target squash: re-materialize `status.json`, add a union driver for `mission-events.jsonl`, decide `kitty-ops/lifecycle.jsonl` (bespoke union or documented block) and `decisions/index.json` (re-fold or documented block); correct the guard so no artifact is silently exempt.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, FR-008; NFR-001; consumes IC-03.
- **Affected surfaces**: `lanes/merge.py` (registry + post-squash hook), `merge/bookkeeping_projection.py` (+ optional `_refold_decisions_index`), `cli/commands/merge_driver.py`, `mission_runtime/artifacts.py`, `.gitattributes`, `cli/commands/init.py`, new `MergeDriverSeedingMigration`, `tests/architectural/test_merge_reconciliation_class_guard.py`.
- **Sequencing/depends-on**: IC-03.
- **Risks**: four registration surfaces must stay in sync (bound guards); guard classification is a *decision*, re-decide explicitly (don't silently flip). Largest concern — likely splits into ≥2 WPs.

### IC-06 — Planning-action `feature_dir` primary anchor (#5160 friction 3)

- **Purpose**: Make `context resolve --action tasks` agree with `check-prerequisites` on the primary `feature_dir` for planning actions; keep coord surface for status actions.
- **Relevant requirements**: FR-009.
- **Affected surfaces**: `src/mission_runtime/resolution.py` (`resolve_action_context`/`_resolve_mission_slug`); optionally hoist a shared primary-anchor authority so the two entry points can't re-diverge.
- **Sequencing/depends-on**: none.
- **Risks**: must not regress status-action resolution (coord surface).

### IC-07 — Coordination-materialization remedy text (#5113, remedy-only)

- **Purpose**: Correct the `CoordinationWorktreeUnmaterialized` remedy to name a working `git worktree add` command; optionally add a defensive CLI `except` arm. Materialize-before-write is OUT OF SCOPE (deferred to #5108).
- **Relevant requirements**: FR-010; C-002.
- **Affected surfaces**: `src/specify_cli/coordination/surface_resolver.py`; optional `src/specify_cli/cli/commands/decision.py`.
- **Sequencing/depends-on**: none.
- **Risks**: keep strictly to remedy text; do not touch `CoordinationWorkspace.resolve` (owned by #5108).
