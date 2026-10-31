# Implementation Plan: A clean consolidation rollback leaves no stale baseline (#6770)

**Branch**: `issue-6770-consolidate-rerun-fresh-baseline` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/spec.md`
**Input**: Mission specification from `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/spec.md`

## Summary

The single post-mutation rollback door (`executor._report_rollback`) currently prints
its report and re-raises, leaving the consolidation record on disk even when the
report says every branch was restored. Because
`resolve._load_or_create_merge_state` treats *any* existing record as a resumed run,
the next plain `consolidate` re-reads `state.pre_mutation_target_sha` from attempt 1
and offers every commit landed on the target since as mission content
("un-attributable"), then rolls the target back over them; and a plain `--abort`
afterwards refuses because the clean rollback already dropped the recorded post tips.

The fix is one invariant, delivered at one site: **an attempt's transaction geometry
survives only while some of its attempt is still on the target.** When the door's
report says the attempt was undone (`RollbackReport.fully_restored`),
`rollback.rebaseline_after_full_restore` drops the attempt's target baseline,
snapshot, restore targets and per-attempt progress (the fields the next attempt must
re-derive from the live tips) and the door says so in one operator line. A partial
rollback keeps all of it. The reconciliation claim's coordination/lane authorship
anchors always stay: after a full restore they are still accurate and a resume needs
them (#5001, #5051). No new state field, no migration, no change to the rollback
authority's per-branch decisions, and `--abort` is untouched: with no snapshot it
takes its existing no-snapshot path (clean finish, exit 0).

## Technical Context

**Language/Version**: Python 3.11+ (this repo's CLI; `uv`-managed, `mypy --strict`)
**Primary Dependencies**: typer, rich, pytest; internal `specify_cli.consolidation`
modules (`rollback`, `state`, `resolve`, `executor`) and `specify_cli.git.ref_advance`
**Storage**: files — `.kittify/runtime/merge/<mission_id>/state.json` plus its
reconciliation marker, cleared by `state.clear_state`
**Testing**: pytest. Red-first regression on real git through the real
`_run_lane_based_consolidation` / `spec-kitty consolidate` entry points
(`tests/terminus` fixtures: `build_lanes_mission`, `run_terminus`), plus the
`tests/consolidation` rollback unit files for the report contract
**Target Platform**: the `spec-kitty` CLI on Linux/macOS/Windows
**Project Type**: single project (`src/specify_cli`, `tests/`)
**Performance Goals**: no measurable cost; one extra `unlink` pair on the failure path
**Constraints**: no new persisted field or migration (NFR-001); the rollback
authority's branch decisions are unchanged (NFR-002); no heavy suite locally (NFR-003)
**Scale/Scope**: `rollback.py` (one report property), `executor.py` (the door body,
~20 lines), a new integration test file, two re-pinned tests, changelog + one how-to
page

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority.** The clear reuses `clear_state`; the "was the attempt
  undone?" question is answered once, by `RollbackReport`, not re-derived at the door. ✅
- **ATDD-first / red-first (DIRECTIVE_034).** A failing regression through the
  pre-existing entry point lands before the fix; it is kept as a regression test
  (`@pytest.mark.regression`), not deleted. ✅
- **Smallest viable diff + locality (DIRECTIVE_024).** One behaviour, one call site,
  one report property; the re-pins are test-only, forced by the behaviour change and
  named in the PR body. ✅
- **Campsite cleaning (DIRECTIVE_025).** The touched functions already carry their
  rationale; no unrelated refactor is folded in. ✅
- **No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION).** Targeted files only:
  `tests/terminus/test_rollback_record_rebaseline.py`, `test_rollback_door.py`,
  `test_abort_restores_snapshot.py`, `tests/consolidation/test_rollback_authority.py`,
  `test_single_rollback_authority.py`, `test_executor_rollback_wiring.py`,
  `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`. ✅
- **Changelog + docs (procedure step 9).** One `[Unreleased]` entry with the
  `(#6770)` reference and a how-to subsection in
  `docs/guides/how-to/recovery/troubleshoot-merge.md` (frontmatter `updated:` bumped). ✅
- **Terminology canon.** Mission/branch wording only; no version numbers in scope. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding, decisions, re-pin list)
├── spec.md              # Mission specification
└── tasks.md             # Phase 2 output (NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── rollback.py          # RollbackReport: the "was the attempt undone?" verdict
├── executor.py          # _report_rollback: the single rollback door
├── state.py             # clear_state (unchanged; the one owner of the clear)
└── resolve.py           # _load_or_create_merge_state (unchanged; fresh vs resume)

tests/
├── terminus/
│   ├── test_repro_6770.py               # NEW: red-first regression (real git + CLI)
│   ├── test_rollback_door.py            # re-pin: a fully rolled-back run clears its record
│   └── rollback_harness.py              # existing helpers (state_path, ref_shas, flat)
├── consolidation/
│   ├── test_rollback_authority.py       # report contract stays green
│   └── test_single_rollback_authority.py
└── specify_cli/cli/commands/
    └── test_merge_coord_worktree_resync_1826.py   # re-pin of the same assertion

docs/
├── changelog/CHANGELOG.md               # [Unreleased] entry (#6770)
└── guides/how-to/recovery/troubleshoot-merge.md  # what a clean rollback now leaves
```

**Structure Decision**: single project; the change is entirely inside the existing
consolidation package and its tests, plus one recovery how-to page.

## Complexity Tracking

No charter violations. No new module, no new persisted field, no new CLI flag.

## Implementation Concern Map

### IC-01 — The door clears a record it has fully undone

- **Purpose**: make "nothing of the attempt is left, so nothing changes how the next
  attempt derives its baseline" true on disk, not only in the report.
- **Relevant requirements**: FR-001, FR-002, FR-005, NFR-001, C-001, C-002
- **Affected surfaces**: `consolidation/rollback.py`
  (`RollbackReport.fully_restored` verdict, `rebaseline_after_full_restore`),
  `consolidation/executor.py::_report_rollback`
- **Sequencing/depends-on**: none
- **Risks**: the clear must be attempted only after the report is computed and printed
  (the operator must still see the rollback report), and it must never mask the
  re-raised error. It must not run for `refused_verified_landing` or any
  `NOT_RESTORED` outcome — that is exactly what the verdict excludes.

### IC-02 — Red-first regression: a re-run after a target commit uses the current tip

- **Purpose**: prove the reported defect and its two consequences (stale window base,
  wedged plain `--abort`) through the real entry points, and keep the proof.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, SC-001, SC-002
- **Affected surfaces**: new `tests/terminus/test_rollback_record_rebaseline.py`; re-pinned assertions
  in `tests/terminus/test_rollback_door.py` and
  `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`
- **Sequencing/depends-on**: the test is authored and observed red before IC-01 lands
- **Risks**: the fixture must fail the gate exactly once (a real one-shot FAIL, not a
  permanently patched verifier) so attempt 2 exercises the real reconciliation path;
  the window base is observed by wrapping `phase_claim.build_approved_wp_set`, which
  keeps the assertion on the production path (not a helper-only probe).

### IC-03 — Operator-facing surfaces tell the truth

- **Purpose**: the changelog entry and the recovery how-to describe what a clean
  rollback now leaves, so an operator does not look for a record that is gone.
- **Relevant requirements**: SC-001..SC-003 (documentation of the delivered
  behaviour), charter "Changelog + docs" standing rule
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`,
  `docs/guides/how-to/recovery/troubleshoot-merge.md`
- **Sequencing/depends-on**: IC-01 (behaviour must be final)
- **Risks**: keep the entry under 1,200 characters and impact-first; do not restate
  the code's internal names beyond the record path.
