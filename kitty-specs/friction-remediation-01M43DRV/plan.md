# Implementation Plan: Regression-slice friction remediation

**Branch**: `issue-5552-friction-remediation` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/friction-remediation-01M43DRV/spec.md`; grounding in [research/code-grounding.md](research/code-grounding.md).

## Summary

The Mission fixes two product bugs that the regression-slice cleanup Mission hit:

- **#5552**: squash consolidate falsely REFUSEs because `quickstart.md` and `contracts/**` have no Mission artifact kind, so the squash projection treats them as coordination bookkeeping.
- **#5298**: strict `accept` blocks on a missing `contracts/` even for Missions that define no interfaces.

The fixes:

- **#5552**: register `quickstart.md` (as `CHECKLIST`, the classification `accept` already uses) and a new PRIMARY-partition kind `CONTRACT` for the `contracts/` directory in the single classifier, `mission_runtime.artifacts`.
- **#5298**: add one fail-closed `meta.json` waiver reader (`contracts: "none"` plus `contracts_rationale`) in `core/paths.py`, and have `evaluate_path_conventions` pass the waived artifact token to `validate_mission_paths`.

#5653 and #5654/#5186 are sequenced behind PRs #5650 and #5656 (Decision Moment `01M43DSJXP334BFKRQFAVMH22J`).

## Technical Context

- **Language/Version**: Python 3.11+
- **Primary Dependencies**: typer, rich, ruamel.yaml (existing; no new dependencies)
- **Storage**: git refs and files: `meta.json` and `kitty-specs/<mission>/` artifacts
- **Testing**: pytest. Red-first through the pre-existing entry points:
  - #5552: `bookkeeping_projection._post_checkpoint_mission_paths` on a real git fixture;
  - #5298: `evaluate_path_conventions` and `collect_feature_summary` with `strict_metadata=True`.
- **Target Platform**: cross-platform CLI
- **Project Type**: single
- **Performance Goals**: no measurable change. The classifier adds one dict lookup, and the waiver adds one `meta.json` read per `accept`, which already reads `meta.json`.
- **Constraints**: complexity ≤ 15; ruff, format and mypy clean; no gate loosened; no edits to `mission_finalize.py`, `tasks_move_task.py` or `orchestrator_api/commands.py`.
- **Scale/Scope**: about 6 source files and about 6 test files.

## Charter Check

- **Single canonical authority**:
  - One file→kind classifier gains entries; no second classifier.
  - One waiver reader, used by the one `validate_mission_paths` caller.
  - `acceptance/__init__.py`'s `quickstart → CHECKLIST` choice now agrees with the registry instead of standing alone.
- **ATDD / red-first (SO-4, C-011)**: each WP commits its failing test before the fix commit.
- **Campsite (SO-2)**: tidy-first only where it enables the change. No god-surface is opened: `acceptance/__init__.py` is not edited.
- **Gate discipline (SO-5)**:
  - `test_write_surface_placement_guard.py` and `test_merge_reconciliation_class_guard.py` are re-pointed. Each gains one enumerated member, which classifies the new entries; nothing is loosened.
  - No new gate and no allowlist.
- **Pack tiers**: no `packs/` edit is needed. The waiver lives in `meta.json`, not in `mission.yaml`, so `doctrine regenerate-graph` is not triggered.
- **Terminology**: Mission, never feature. `consolidate` is local only.
- **ADR placement**: the charter's Charter Resolution Hints say new ADRs land in `docs/adr/4.x/`. The brief suggested `3.x`; the charter wins, and the PR flags this.

## Project Structure

### Documentation (this mission)

```
kitty-specs/friction-remediation-01M43DRV/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── traces/{approach,design-decisions,tooling-friction}.md
├── tasks.md
└── tasks/WP01-*.md, WP02-*.md
```

### Source Code (repository root)

```
src/mission_runtime/artifacts.py                     # WP01: classifier entries + CONTRACT kind
src/specify_cli/coordination/commit_router.py        # WP01: CONTRACT is a pre-tasks kind
src/specify_cli/core/paths.py                        # WP02: read_contracts_waiver_from_meta
src/specify_cli/validators/paths.py                  # WP02: waived_artifact_tokens keyword
src/specify_cli/acceptance/summary_core.py           # WP02: apply the waiver
src/specify_cli/mission_metadata.py                  # WP02: MissionMetaOptional fields
docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md   # WP02
```

**Structure Decision**: single project; existing modules only.

## Complexity Tracking

None. No charter violation is needed.

## Implementation Concern Map

### IC-01 — Classify quickstart.md and contracts/** as PRIMARY

- **Purpose**: stop squash consolidate projecting planning artifacts as coordination bookkeeping (#5552).
- **Relevant requirements**: FR-001, FR-002, FR-003
- **Affected surfaces**:
  - `src/mission_runtime/artifacts.py`;
  - `src/specify_cli/coordination/commit_router.py` (`_PRE_TASKS_ARTIFACT_KINDS`);
  - `tests/architectural/test_write_surface_placement_guard.py`;
  - `tests/architectural/test_merge_reconciliation_class_guard.py`;
  - a new consolidation test.
- **Sequencing/depends-on**: none
- **Risks**:
  - `safe-commit` and `workflow.py` now route these paths to the primary target instead of HEAD or the coordination branch. This is intended and is the same as `spec.md`.
  - A legacy coord-only post-checkpoint copy is no longer projected (see grounding §1).

### IC-02 — meta.json contracts waiver honoured by strict accept

- **Purpose**: let a Mission declare, auditably, that it defines no contracts (#5298).
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007
- **Affected surfaces**: `core/paths.py`, `validators/paths.py`, `acceptance/summary_core.py`, `mission_metadata.py`, a new ADR, and new acceptance tests.
- **Sequencing/depends-on**: none (independent of IC-01)
- **Risks**:
  - Malformed waivers must never relax the check.
  - A corrupt `meta.json` must still raise.
  - The existing dedup test must stay green.

### IC-03 — Sequenced work (#5653, #5654, #5186)

- **Purpose**: tidy-first extraction and test-hygiene repairs.
- **Relevant requirements**: FR-008, FR-009
- **Affected surfaces**: `cli/commands/consolidate.py`, `consolidation/canceled_attestation.py`, and the test files listed in the brief.
- **Sequencing/depends-on**: PR #5650 and PR #5656 merged on `main`.
- **Risks**: stacking on or duplicating an open PR. If either is still open, defer with `Refs`.
