# Implementation Plan: Changelog WP acceptance reads the canonical lane

**Branch**: `issue-6612-changelog-wp-lane-reducer` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/changelog-wp-lane-reducer-01M66FMR/spec.md`

## Summary

`src/specify_cli/release/changelog.py::_wp_lane_from_event_log` (consumed by `_is_accepted_wp`, called from `build_changelog_block`) decides whether a work package appears in the release changelog. It currently (a) reads `mission_dir / "status.events.jsonl"` directly instead of the resolved status surface, (b) takes the last `to_lane` in file order instead of the reduced lane, and (c) silently skips corrupt lines. The fix routes the read through the canonical lane reader (`specify_cli.status.get_wp_lane`) over the status surface resolved by the placement seam (`placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)`), keeping the legacy frontmatter fallback for missions with no event log and letting corrupt logs fail loudly (`StoreError`) the way every other reader does. Red-first tests pin the out-of-order-log case and the coordination-topology case (issue #6612 / gap G-13).

## Technical Context

**Language/Version**: Python 3.11 (repo standard, `uv`-managed)
**Primary Dependencies**: `mission_runtime` (placement seam, `MissionArtifactKind`), `specify_cli.status` (`get_wp_lane`, `CanonicalStatusNotFoundError`, `Lane`), `specify_cli.coordination.surface_resolver` (`CoordinationWorktreeUnmaterialized` — caught for the fresh-clone window). No new dependencies.
**Storage**: filesystem only (`kitty-specs/<slug>/status.events.jsonl` on the resolved surface); zero network, zero writes (release-prep FR-014).
**Testing**: pytest; existing suite `tests/release/test_release_prep.py` owns the `build_changelog_block` contract. New red-first tests join it. The coordination-topology fixture needs a real git repo (pattern: `tests/status/test_agent_status_emit_aggregate_wiring.py` — `git init`, coord branch, worktree at `.worktrees/<slug>-<mid8>-coord`).
**Target Platform**: Linux/macOS dev machines and CI (the CLI's platforms).
**Project Type**: single (Python package `specify_cli` + shared `mission_runtime`).
**Performance Goals**: unchanged; the changelog already reads every mission's log once. `get_wp_lane` reduces the same file the raw loop read — same order of work.
**Constraints**: smallest viable diff (C-001); canonical seams only, no hand-composed status paths (C-002); never touch the reducer, the placement seam, or the status store.
**Scale/Scope**: one production function pair (`_wp_lane_from_event_log`, `_is_accepted_wp` + their call site in `build_changelog_block`), ~4 new tests, one changelog entry, one doc row.

## Charter Check

- Single canonical authority: the lane authority becomes `get_wp_lane` + the placement seam (one authority, not two). PASS after this change; the charter violation being fixed is the raw second reader.
- Architectural alignment: routed through the placement seam's `STATUS_STATE` read and the lane reader — the same surfaces the retrospective gate, preflight and aggregate use. No new boundary crossed.
- ATDD-first: red tests through `build_changelog_block` (the pre-existing entry point) come before the fix.
- Terminology: "lane", "reducer", "status surface" used per `docs/architecture/event-ledger-writers-and-readers.md` and the spec's Terminology section.
- No violations; no complexity-tracking rows.

## Project Structure

### Documentation (this mission)

```
kitty-specs/changelog-wp-lane-reducer-01M66FMR/
├── plan.md              # this file
├── spec.md              # mission specification
├── tasks.md             # /spec-kitty.tasks output
└── traces/              # tracer files (approach, design-decisions, tooling-friction)
```

### Source Code (repository root)

```
src/specify_cli/release/
└── changelog.py                 # _wp_lane_from_event_log, _is_accepted_wp, build_changelog_block

tests/release/
└── test_release_prep.py         # owns the build_changelog_block contract (new red-first tests)

docs/
├── changelog/CHANGELOG.md       # [Unreleased] entry (user-facing)
└── architecture/event-ledger-writers-and-readers.md   # G-13 row update
```

**Structure Decision**: single-project layout; the fix is confined to `src/specify_cli/release/` and its owning test suite. No new modules — importing `get_wp_lane` from `specify_cli.status` (lazy, mirroring the repo's late-import convention for `mission_runtime`).

## Implementation Concern Map

### IC-01 — Canonical lane read for changelog acceptance

- **Purpose**: Replace the raw file-order `to_lane` scan with `get_wp_lane` over the resolved status surface so there is one lane authority for the changelog.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/release/changelog.py`, `tests/release/test_release_prep.py`
- **Sequencing/depends-on**: none
- **Risks**: (1) Signature change of the two private helpers ripples only inside this module (verified: no other importers). (2) Failure policy must distinguish "no canonical surface" (legacy missions → frontmatter fallback; `CoordinationWorktreeUnmaterialized` → frontmatter fallback, never the stale primary copy) from "surface says the log is corrupt" (`StoreError` propagates). (3) `CoordinationBranchDeleted` propagates unchanged (the #1848 guard). (4) Post-consolidation missions clear `coordination_branch` in `meta.json`, so the changelog's dominant case (past missions) still resolves to the primary dir — no regression for releases.
