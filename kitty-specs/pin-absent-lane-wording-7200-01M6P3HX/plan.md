# Implementation Plan: Pin the absent-lane wording in move-task's evidence refusal

**Branch**: `kitty/mission-pin-absent-lane-wording-7200-01M6P3HX` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/pin-absent-lane-wording-7200-01M6P3HX/spec.md`

## Summary

Add one assertion to the existing real-Git refusal test so the shipped sentence `the lane branch kitty/mission-fx-lane-b does not exist in this checkout` is pinned on the missing-lane-with-a-sibling path. Prove the assertion is non-vacuous by mutating that sentence to `is unavailable` in `src/specify_cli/consolidation/wp_evidence.py`, observing the test fail, then restoring the source. The committed diff is the test file plus an internal changelog fragment; no production behaviour changes.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pytest, real `git` subprocesses; the move-task evidence gate (`specify_cli.cli.commands.agent.tasks_move_task`) and consolidation evidence wording (`specify_cli.consolidation.wp_evidence.absent_lane_window_cause`).
**Storage**: N/A — the fixture is a temporary real Git repository under pytest's `tmp_path`.
**Testing**: `uv run --frozen pytest tests/git_ops/test_move_task_evidence_refusals.py` (real-Git, `pytest.mark.git_repo`); the target case is `test_a_missing_lane_with_a_sibling_names_conditional_restore`.
**Target Platform**: Linux developer/CI host with Git installed.
**Project Type**: Single Python project.
**Performance Goals**: The focused three-case module stays under five minutes; no new slow setup is introduced (the existing `lanes_mission` fixture and `_gate_repo` helper are reused).
**Constraints**: No production file changes; no new test file or duplicate wording owner; no skipped/xfailed assertions; no full heavy suite.
**Scale/Scope**: One test function, one assertion (plus an explicit negative guard for the competing sentence if the wording makes it necessary), and one internal changelog fragment.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first / `DIRECTIVE_034` test-first-bug-fixing**: the defect is a missing guard; the failing-first proof is the production mutation that makes the new assertion red. The mutation is temporary and never committed.
- **Single canonical authority**: the absence wording keeps one test owner — the Git-backed refusal test the issue names. No copy appears in the pure move-gate or consolidation suites.
- **Locality of change / smallest viable diff**: the change stays in the existing test function and reuses its fixture; the only other file is the required changelog fragment.
- **`DIRECTIVE_041` / test economy**: the assertion guards a real FR-001 contract boundary (absence versus unreadability) rather than a copy-pasted shape check.
- **No full heavy suites**: only the focused real-Git module, scoped lint/format, changelog style and the standard PR gates are run locally.

No charter violations; no complexity justification needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pin-absent-lane-wording-7200-01M6P3HX/
├── plan.md              # This file
├── spec.md              # Mission specification
├── research.md          # Grounding: shipped behaviour and prior PR #7146
├── tasks.md             # Work-package outline (created by tasks step)
└── tasks/               # Work-package prompts
```

### Source Code (repository root)

```
tests/
└── git_ops/
    └── test_move_task_evidence_refusals.py   # target test owner

src/
└── specify_cli/
    └── consolidation/
        └── wp_evidence.py                    # read-only reference; mutated only for the red proof

docs/
└── changelog/
    └── unreleased/
        └── <pr>.internal.md                  # per-PR fragment
```

**Structure Decision**: reuse the repository's existing test layout. The test belongs in `tests/git_ops/` because it needs real local ref states (a sibling lane branch present while the target lane branch is absent); the production wording is read from `wp_evidence.absent_lane_window_cause` through the real move-task gate.

## Complexity Tracking

No violations.

## Implementation Concern Map

- **Wording pin**: assert the exact shipped absence sentence in the missing-lane-with-a-sibling refusal, keeping the existing conditional-restore and never-created assertions intact so the test still discriminates the three local shapes.
- **Non-vacuity proof**: apply and revert the `does not exist` → `is unavailable` mutation, capturing the red and green runs for the PR body.
- **Delivery hygiene**: add the internal changelog fragment, run scoped lint/format and the focused suite, and keep the commit linear with no production diff.
