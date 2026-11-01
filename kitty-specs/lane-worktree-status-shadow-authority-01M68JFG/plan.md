# Implementation Plan: Lane worktree status shadow authority

**Branch**: `issue-6466-lane-status-shadow` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/spec.md`
**Input**: Mission specification from `kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/spec.md`

## Summary

A mission's work-package lane state has exactly one authority: the resolved status surface
(the coordination husk on a coordination-routed mission, the primary/mission-branch copy
otherwise). A lane worktree carries a fork-time *copy* of `kitty-specs/<slug>/`
(`status.events.jsonl`, and `status.json` once the fork post-dates the first snapshot). Today
that copy can still answer a status read when the lane worktree root is handed in as the
repository root: the read reports the fork-time lane (`planned`) while the authority already
says `in_progress`, so a routine `for_review` transition is not a legal edge and the operator's
only escape is `--force` (#6466).

The fix re-anchors the guarded read-side seam to the repository's main worktree root whenever the
handed root classifies as a **lane worktree** — consuming the existing worktree-topology
classifier, so the coordination worktree (also a linked worktree, but the authority on a
coordination-routed mission) is untouched, and independent clones are untouched. The stale lane
copy stops being able to answer at all, which makes the divergence impossible rather than
something the operator reconciles by hand.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer CLI, `mission_runtime` (topology resolution), `kernel.git`
(worktree registry), `specify_cli.coordination` (surface resolver)
**Storage**: mission files on disk — `status.events.jsonl` (append-only authority) and the
derived `status.json` snapshot
**Testing**: pytest (`uv run pytest`), red-first fixture built with the orchestrator API
`start-implementation` surface exactly as `tests/specify_cli/lanes/test_for_review_gate_parity.py`
does
**Target Platform**: Linux/macOS developer machines and CI
**Project Type**: single CLI project
**Performance Goals**: no additional git shell-out per status read — the re-anchor runs only when
the handed root is a linked worktree, and the classification reuses the existing registry read
**Constraints**: no newest-timestamp-wins rule (C-001); no genuine guard weakened (C-002); the
seam keeps its documented "repo_root is the primary checkout" contract by *canonicalizing* a
lane-worktree root instead of trusting it
**Scale/Scope**: one seam (`specify_cli/missions/_read_path_resolver.py`), one regression test
file, changelog

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Single-authority resolution (charter: canonical state authority): the change adds no second
  resolution mechanism; it removes a second *answer* by canonicalizing the input root into the
  existing primary/coordination authority. PASS.
- Fail-closed posture: a registry that cannot be read keeps today's behaviour (NFR-002); nothing
  degrades to a guess. PASS.
- Test-first discipline (ATDD, DIRECTIVE_034): the regression test lands red before the fix, and
  the fix is proven by that test passing. PASS.
- No full heavy suite in the mission loop; targeted files only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/
├── spec.md
├── plan.md              # This file
├── tasks.md             # /spec-kitty.tasks output
└── tasks/WP*.md         # work package prompts
```

### Source Code (repository root)

```
src/specify_cli/missions/_read_path_resolver.py   # guarded read-side seam (re-anchor)
tests/specify_cli/missions/test_lane_worktree_status_shadow.py   # new regression test
docs/changelog/CHANGELOG.md                       # [Unreleased] entry
```

**Structure Decision**: Single CLI project. The change lives in the existing read-path resolver
module and is covered by one new test module next to the existing resolver tests.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Lane-worktree root canonicalization at the guarded read seam

- **Purpose**: Make a lane worktree root unable to answer a status read from its fork-time copy,
  so the authority is always the resolved status surface.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/missions/_read_path_resolver.py`
  (`resolve_handle_to_read_path` and the primary-meta/canonicalization legs it feeds)
- **Sequencing/depends-on**: none
- **Risks**: the coordination worktree is itself a linked worktree — the re-anchor must be keyed
  on the *classified* topology (`LANE_WORKTREE`), never on path shape or on "is a linked
  worktree". An independent clone is not a linked worktree of the mission's repository, so it
  keeps its own authority.

### IC-02 — Red-first regression fixture and non-vacuity controls

- **Purpose**: Prove the stale-shadow read and the spurious `--force` demand on a real lane
  worktree, and hold the coordination boundary so the fix cannot regress it.
- **Relevant requirements**: FR-001, FR-002, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/specify_cli/missions/test_lane_worktree_status_shadow.py`
- **Sequencing/depends-on**: IC-01 (the test is authored first and fails before IC-01 lands)
- **Risks**: the fixture must build a genuine registered lane worktree (git worktree + lanes
  manifest), not a directory that merely looks like one, or the test proves nothing.
