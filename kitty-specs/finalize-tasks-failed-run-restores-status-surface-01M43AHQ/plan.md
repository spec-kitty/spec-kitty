# Implementation Plan: finalize-tasks: a failed run leaves the status surface as it found it

**Branch**: `kitty/fix-5641-finalize-tasks-atomic-status` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/finalize-tasks-failed-run-restores-status-surface-01M43AHQ/spec.md`

## Summary

`finalize-tasks` seeds every WP as `planned` before its final commit, and each seed is its own commit on the status surface. When the run fails before the final commit lands, the existing guard restores the Mission directory's bytes. Only an owned checkout also gets its HEAD back, through a mixed `git reset` that is not compare-and-swap. This plan replaces that owned-only HEAD restore with one status-surface guard for every topology:

1. **Capture**, at the start of `_run_commit_pipeline` (before the first status write, `_emit_local_canonical_events`):
   - the status write directory (`PlacementSeam.write_dir(STATUS_STATE)`, the authority the writer itself uses);
   - its checkout root and the branch checked out there;
   - the branch tip, the index tree (`git write-tree`), and the bytes of the status directory when it lies outside the Mission directory snapshot (the coordination worktree).
2. **Record** the branch tip right after the run's last status write, in a `finally`, so a bootstrap that raises part-way is still covered.
3. **Restore**, in the existing `except` arms when the finalize commit never landed, after the Mission directory restore. If the branch still points at the recorded tip, run `restore_branch_ref(..., expected_current_sha=<recorded tip>)` (compare-and-swap, no resync), then `git read-tree <captured index tree>` in that checkout, then restore the status directory bytes. Otherwise touch nothing and report the branch and the commits (`<before>..<current>`) the run made and could not undo, as an additional note next to the original error. The exit stays non-zero.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git (subprocess), the existing `specify_cli.git.ref_advance` CAS primitives
**Storage**: git refs, index, and files under `kitty-specs/<mission>/` (primary or coordination worktree)
**Testing**: pytest, real git repositories through `CliRunner` against the real `mission` Typer app (`tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py`)
**Target Platform**: Linux, macOS, Windows (git CLI)
**Project Type**: single
**Performance Goals**: at most four extra git calls per run on the success path (NFR-002)
**Constraints**: no new destructive git literal, no new gate allowlist entry (NFR-001); `consolidation/executor.py`, `pytest.ini`, `tests/conftest.py` and `tests/_support/p0_repro.py` untouched (C-002)
**Scale/Scope**: one CLI command's failure path

## Charter Check

- **Single canonical authority.** The new guard replaces `_capture_owned_head` / `_restore_owned_head`; it does not add a second restore beside them. The ref move goes through `restore_branch_ref`, the one compare-and-swap restore primitive. The checkout is NOT hard-reset: `resync_checkouts=True` belongs to `consolidation/rollback.py` alone (`test_single_rollback_authority.py`). This follows the `core/mission_creation.py` precedent (CAS restore plus `read-tree`).
- **Architectural gate discipline.** No gate is loosened. The destructive-op census, the rollback-authority gate, the git-path-listing owner gate and the status-write gates are re-run as named files.
- **Red-first.** The reproduction (PR #5657) is red on main for four topologies and is the acceptance test. The fix removes its `regression` marker.
- **Test economy.** One added test (the foreign-commit report, FR-002/FR-003). The retry evidence (FR-005) is a recorded run, not a new test. The existing coordination-boundary test is retired or strengthened at closeout, after a KEEP/RETIRE verdict.
- **Terminology.** Mission, never feature; `consolidate` is local.

## Project Structure

### Documentation (this mission)

```
kitty-specs/finalize-tasks-failed-run-restores-status-surface-01M43AHQ/
├── spec.md
├── plan.md
├── research/code-grounding.md
├── traces/{tooling-friction,approach,design-decisions}.md
├── tasks.md
└── tasks/WP01-*.md, WP02-*.md
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── finalize_status_surface.py   # NEW: capture / record / CAS-restore of the status surface (git only)
└── mission_finalize.py          # wire the guard into _run_commit_pipeline and the except arms; retire the owned-only HEAD restore
tests/specify_cli/cli/commands/agent/
└── test_finalize_atomicity.py   # reproduction un-marked; foreign-commit report test
docs/changelog/CHANGELOG.md      # ### Fixed entry
```

**Structure Decision**: The git-level guard goes in its own small module beside `mission_finalize.py`, which is already 5,678 lines with 52 commits in 90 days, so the hot file only gains wiring. The byte-level restore keeps using the existing `_snapshot_mission_write_scope` / `_restore_mission_write_scope` helpers, so no second byte-restore authority appears.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — Status-surface guard (capture, record, restore)

- **Purpose**: Undo the status commits of a failed run on every topology, through compare-and-swap, and report what cannot be undone.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/finalize_status_surface.py` (new), `src/specify_cli/cli/commands/agent/mission_finalize.py` (`_run_commit_pipeline`, `finalize_tasks` except arms, `_FinalizeBranchSetup`, retire `_capture_owned_head` / `_restore_owned_head`)
- **Sequencing/depends-on**: none
- **Risks**:
  - The order of the restores. The Mission directory bytes come first, then ref + index, then the coordination status bytes, and only after a successful ref restore, so a refused restore never leaves a coordination worktree diverged from its HEAD.
  - The owned-checkout behaviour must stay green.
  - A part-way bootstrap failure.

### IC-02 — Evidence, docs and changelog

- **Purpose**: Prove the retry seeds once. Make the code comment, the FR-015/NFR-001 wording and the changelog true.
- **Relevant requirements**: FR-005, FR-006
- **Affected surfaces**: `mission_finalize.py` comments, `docs/changelog/CHANGELOG.md`, the PR body
- **Sequencing/depends-on**: IC-01
- **Risks**: Prose drift. Check with `scripts.docs.check_changelog_style` and `scripts.docs.check_spelling`.
