# Implementation Plan: honest feedback file drop

**Branch**: `issue-6699-honest-feedback-file-drop` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/honest-feedback-file-drop-01M66FMD/spec.md`
**Input**: Mission specification from `kitty-specs/honest-feedback-file-drop-01M66FMD/spec.md` (issue spec-kitty/spec-kitty#6699)

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

`move-task` resolves `--review-feedback-file` on every edge, but only the rejection writer (review-rejection edges) and the approval writer (`→ approved`/`→ done`) consume it; on every other edge the file is validated and then silently dropped (#6699). The fix adds a leading arm to the pure guard `_guard_feedback_file` (`src/specify_cli/cli/commands/agent/tasks_transition_core.py`): when the flag is supplied on an edge that is neither a review-rejection edge (`is_review_rejection_edge`) nor an approval edge (`_APPROVAL_LANES`), refuse with exit 1 and an edge-naming message, before any lane hop or durable write. The arbiter-override-into-`approved`/`done` edge keeps its #6652 stderr warning and gains an end-to-end pin; the `--help` text (and its golden fixture) is narrowed. Red-first tests per edge drive the work through the real CLI (rework-loop harness).

## Technical Context

**Language/Version**: Python 3.11 (package `spec-kitty-cli` 4.0.0rc8)
**Primary Dependencies**: Typer (CLI), pytest (tests); no new dependencies
**Storage**: N/A (pure guard change; no persistence change)
**Testing**: pytest via `uv run pytest`; e2e through the real Typer app with `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py`; unit tests on the pure guard in `tests/specify_cli/cli/commands/agent/`
**Target Platform**: Linux/macOS CLI (spec-kitty)
**Project Type**: single (src layout: `src/specify_cli/`)
**Performance Goals**: N/A (guard is O(1) string compares)
**Constraints**: guard order and OLD-timing partial-write signals must be unchanged (`override_persist_signal`, `arbiter_persist_signal`); frozen `ReviewOverride` four-field shape untouched; `--help` golden fixture updated in the same change
**Scale/Scope**: one guard arm + message, one help paragraph + fixture, three e2e tests, guard unit tests

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Single canonical authority: the edge-applicability predicate reuses `is_review_rejection_edge` and `_APPROVAL_LANES` — no second source of truth for "which edges record the file". PASS.
- ATDD-first / DIRECTIVE_034: each edge gets a failing test through the real CLI before the fix. PASS.
- Locality of change (DIRECTIVE_024) / smallest viable diff: one leading arm inside the existing `_guard_feedback_file`, no new guard slot, no restructuring. PASS.
- Frozen contracts respected: `is_review_rejection_edge` (#4899), `ReviewOverride` shape, `_planned_rollback_message` texts stay untouched. PASS.
- No full heavy suites in-mission: only targeted test files run locally; CI owns the rest. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/honest-feedback-file-drop-01M66FMD/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding, decisions D-1..D-3)
├── reasons-canvas.md    # SPDD canvas
├── contracts/           # (none needed — no new contract; frozen ones cited)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── tasks_transition_core.py      # _guard_feedback_file gains the edge arm + message helper
├── tasks.py                      # --review-feedback-file help text narrowed
└── (read-only context: tasks_verdict_persistence.py, tasks_move_task.py)

tests/specify_cli/cli/commands/agent/
├── _rework_loop_harness.py       # existing shared e2e harness (reused, not modified)
├── test_issue_6699_feedback_file_edges.py   # new: red-first e2e tests per edge
└── fixtures/tasks_cli/help/move-task.help   # golden --help fixture updated

docs/changelog/CHANGELOG.md       # [Unreleased] entry
docs/api/agent-subcommands.md     # if it restates the help text
```

**Structure Decision**: single-project src layout, unchanged; the change is confined to the guard module, the CLI help registration, the golden fixture, tests and docs.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

None — no charter violations.

## Implementation Concern Map

### IC-01 — Refuse the flag on non-recordable edges (pure guard)

- **Purpose**: Make the silent drop impossible: `_guard_feedback_file` refuses (exit 1) when `feedback_provided` and the edge is neither review-rejection nor approval.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-002
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`; tests in `tests/specify_cli/cli/commands/agent/`
- **Sequencing/depends-on**: none
- **Risks**: the new arm must not change `arbiter_persist_signal` (its prefix slice includes `_guard_feedback_file`) — safe because the arm is inert whenever the target is `approved`/`done`, the only lanes where the signal arms; the refusal message must not shadow the missing-file message on rejection edges (arm ordering: edge check only when the edge is non-recordable).

### IC-02 — Pin the arbiter-override drop end-to-end

- **Purpose**: Pin, through the real CLI, that an arbiter override with `--review-feedback-file` succeeds, warns on stderr, records the note, and fabricates no approval cycle.
- **Relevant requirements**: FR-003, C-001
- **Affected surfaces**: `tests/specify_cli/cli/commands/agent/test_issue_6699_feedback_file_edges.py` (rework-loop harness)
- **Sequencing/depends-on**: none (independent of IC-01's code change; both land in one WP)
- **Risks**: none — pure test addition; pairs the warning assertion with the no-flag negative control on the same fixture (non-vacuity).

### IC-03 — Help text and docs

- **Purpose**: Narrow the `--review-feedback-file` help to state the refusal, update the golden fixture and the changelog.
- **Relevant requirements**: FR-004, C-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks.py`, `tests/specify_cli/cli/commands/agent/fixtures/tasks_cli/help/move-task.help`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (the text documents the refusal)
- **Risks**: the `--help` surface is golden-fixture-pinned; the fixture must be regenerated in the same change.
