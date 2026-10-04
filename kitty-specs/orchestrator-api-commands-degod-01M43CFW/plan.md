# Implementation Plan: Split the orchestrator-api commands god-module

**Branch**: `claude/funny-cannon-2kiwuz` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/orchestrator-api-commands-degod-01M43CFW/spec.md`

## Summary

`src/specify_cli/orchestrator_api/commands.py` (4,191 LOC) holds all 21 subcommands of the external `orchestrator-api` contract. We split it into one shared-helper module and five concern modules. `commands.py` stays the façade: it keeps the Typer `app`, the JSON error group, `contract-version`, and the two #5532 readers (`mission-state`, `list-ready`). It registers every other verb explicitly, in today's order, from a command table. Function bodies move verbatim.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer / click (vendored-click exception shims stay in the façade)
**Storage**: N/A
**Testing**: help-snapshot byte diff (before/after) plus the orchestrator-api blast-radius suite (baseline 1197 passed, 2 skipped, 2 xfailed)
**Target Platform**: CLI
**Project Type**: single
**Performance Goals**: N/A (import cost unchanged: the façade imports every concern module eagerly, as today)
**Constraints**: byte-identical contract; no new suppressions; complexity ≤15 is unchanged because bodies do not change
**Scale/Scope**: 1 package, ~4,200 LOC moved

## Charter Check

- Single canonical authority: one `app`, one shared-helper module. No helper is duplicated across concern modules.
- Architectural alignment: `orchestrator_api` stays inside `specify_cli`. No new cross-package imports.
- ATDD / red-first: this is a behaviour-preserving refactor with no defect to reproduce. The guard is a characterization test that pins the help snapshot and verb order. It is green before and after.
- Architectural gates that scan `commands.py` by path are re-pointed to the module that now holds the scanned code, in the same commit (gate-companion fold).

## Project Structure

### Source Code (repository root)

```text
src/specify_cli/orchestrator_api/
├── commands.py        # façade: app, _JSONErrorGroup, contract-version, mission-state, list-ready, command table
├── _common.py         # envelope/failure helpers, policy parsing, repo-root + mission/WP resolution
├── wp_lifecycle.py    # resolve-workspace, start-implementation, start-review, transition, append-history
├── consolidation.py   # accept-mission, consolidate-mission, merge preflight/execute/cleanup helpers
├── design_phase.py    # specify, plan, tasks, check-prerequisites, record-analysis
├── decision_verbs.py  # open/resolve/defer/cancel/answer-decision
└── design_status.py   # design-status
```

**Structure Decision**: The concern modules define plain functions with their typer `Option` signatures. They do not import `app`. The façade owns registration, so the command order lives in one place.

**Seam rule**: concern modules call the shared patch seams (`_get_main_repo_root`, `_resolve_mission_dir_or_fail`, `_mission_identity_payload`) through the `_common` module attribute, so a test that patches `_common.<name>` reaches every caller. Tests that patched `commands.<name>` move their patch target to the module that now owns the lookup.

## Implementation Concern Map

### IC-01 — Shared helpers

- **Purpose**: Give the envelope, failure, policy and resolution helpers one home.
- **Relevant requirements**: FR-003
- **Affected surfaces**: `orchestrator_api/_common.py`, `commands.py`
- **Sequencing/depends-on**: none
- **Risks**: Silent patch misses if a concern module binds a seam with `from ._common import X`. Mitigated by the seam rule.

### IC-02 — Concern modules + façade registration

- **Purpose**: Move each verb group verbatim and register it from the façade in today's order.
- **Relevant requirements**: FR-001, FR-002, FR-004
- **Affected surfaces**: the five concern modules, `commands.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: Command reordering in `--help` (the snapshot catches it). A helper used by only one concern must live with that concern, not in `_common`.

### IC-03 — Gates and tests follow the code

- **Purpose**: Re-point source-scanning gates and patch targets so they stay non-vacuous.
- **Relevant requirements**: C-003
- **Affected surfaces**: `tests/architectural/test_destructive_op_routing.py`, `tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py`, `tests/coordination/test_commit_outcome_consumer_pin.py`, `tests/runtime/test_bridge_engine.py`, the two `_COMMANDS_PY` source scans under `tests/specify_cli/orchestrator_api/`, and every `patch("…commands._…")` target
- **Sequencing/depends-on**: IC-02
- **Risks**: A scan that now reads a file lacking the pattern passes vacuously. Mitigated by re-pointing each scan to the file that holds the pattern; the scans assert presence.
