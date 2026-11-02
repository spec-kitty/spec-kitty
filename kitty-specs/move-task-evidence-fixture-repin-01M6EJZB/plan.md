# Implementation Plan: Re-pin the move-task fixtures refused by the owned-file evidence gate

**Branch**: `issue-7057-move-task-evidence-fixture-repin` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/move-task-evidence-fixture-repin-01M6EJZB/spec.md`

The planning questions are answered by `research.md`: the 8 refusals reproduce on
`origin/main` `9aed3a8012`, every one is led by `IMPLEMENTATION_MISSING` from the #6715
owned-file evidence gate, and the verdict in every case is that the **fixture** is stale
— the gate's contract is intended and already has its own coverage.

## Summary

Make `tests/tasks/test_move_task_git_validation_unit.py` model a Mission that
`finalize-tasks` could actually produce, so #6715's evidence gate passes on honest
evidence and the guards the module exists to test are reachable again:

1. the `git_repo_with_worktree` fixture's WP01 declares `owned_files` (`src/**`, the
   lane's own `write_scope`);
2. the fixture's lane branch commits its implementation inside that ownership
   (`src/implementation.py`) instead of an unowned root `implementation.txt`;
3. `test_move_to_done_with_override_reason_succeeds_when_unmerged` supplies the reviewer
   identity that #6715's independence gate requires for a `done` move
   (`--agent reviewer-renata`).

Nothing under `src/` changes. No test is skipped, xfailed, deselected or retried; the
15 nodes keep their names, markers and assertions.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest, typer/click `CliRunner`, the module's own git fixture helpers (`tests/lane_test_utils.py`)
**Storage**: N/A (git repositories created under `tmp_path`)
**Testing**: red-first on the exact module: 8 failed / 7 passed on the planning base, 15 passed after the fixture is re-pinned; then the neighbouring `tests/tasks` and `tests/agent` move-task surfaces that share `write_single_lane_manifest`
**Target Platform**: Linux CI (out-of-matrix `tests/tasks`; owned by the nightly shard that runs that directory)
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: no `src/` change; no skip/xfail/force; the gate's refusal text and ordering untouched
**Scale/Scope**: one test module, a one-line changelog fragment, and the Mission's own artifacts

## Charter Check

- **Test-remediation discipline (Standing Order #4) — judge the test, red first.** The
  product behaviour (refuse a review-ward move with no owned change; refuse a placeholder
  approver) is intended and covered by its own #6715 tests. The stale seam is the
  fixture, so the fixture is re-pinned and the product is not patched. Red first on the
  exact 8 node ids, then green on the same module.
- **Red-main discipline (Standing Order #9).** Clear the red at the root: no skip, xfail,
  deselection or retry, and no new `--force` on a node to dodge a gate.
- **Canonical authority (Standing Order #6).** The fixture declares ownership once, in the
  WP frontmatter, which is the same source `move-task` and `consolidate` read
  (`wp_evidence.owned_patterns`); no second list is introduced in the test.
- **Locality of change (DIRECTIVE_024) / smallest viable diff.** Two hunks in one fixture
  plus one invocation's flags; no reformatting, no new helper, no new test module.
- **Campsite (Standing Order #2).** The stale `implementation.txt` root deliverable is
  replaced in place with an owned `src/implementation.py`, and the fixture gains a
  comment saying why `owned_files` is load-bearing, so the next reader does not delete it
  and silently re-break 8 nodes.

## Project Structure

### Documentation (this mission)

```
kitty-specs/move-task-evidence-fixture-repin-01M6EJZB/
├── spec.md
├── plan.md
├── research.md
├── issue-matrix.json
├── traces/
│   ├── approach.md
│   ├── design-decisions.md
│   └── tooling-friction.md
└── tasks/
    └── WP01-repin-move-task-evidence-fixtures.md
```

### Source Code (repository root)

```
tests/tasks/test_move_task_git_validation_unit.py   # the only code change
docs/changelog/unreleased/<pr>.internal.md          # per-PR fragment (test-only change)
```

Reference (read, **not** modified): `tests/lane_test_utils.py`,
`src/specify_cli/cli/commands/agent/tasks_move_task.py`,
`src/specify_cli/consolidation/wp_evidence.py`,
`tests/integration/test_6715_lane_autowalk_guards.py`.

## Complexity Tracking

No charter violations; the mission is a test-fixture re-pin. Nothing to justify.

## Implementation Concern Map

### IC-01 — Fixture evidence: the WP owns what its lane branch commits

- **Purpose**: Make the fixture's evidence window show an owned change so the #6715 gate
  stops short-circuiting every review-ward node.
- **Relevant requirements**: FR-001, FR-002 (SC-001, SC-002)
- **Affected surfaces**: `git_repo_with_worktree` in
  `tests/tasks/test_move_task_git_validation_unit.py` (WP01 frontmatter string and the
  lane-branch commit)
- **Sequencing/depends-on**: none
- **Risks**: the fixture's `write_scope` is `src/**`, so the deliverable must live under
  `src/`, not merely be named in `owned_files`; the window base is the planning commit
  `write_single_lane_manifest` records before the task-file commit, so the owned commit
  must be on the lane branch after that base (it is). `test_move_for_review_from_worktree_keeps_commit_history_unchanged`
  asserts the lane head subject stays `Add implementation` — keep the message.

### IC-02 — Approval identity: a done move names its reviewer

- **Purpose**: Keep the done-override node testing the done-override path now that the
  evidence gate no longer pre-empts it, without weakening #6715's independence gate.
- **Relevant requirements**: FR-003 (SC-001, SC-004)
- **Affected surfaces**: `test_move_to_done_with_override_reason_succeeds_when_unmerged`'s
  argument list
- **Sequencing/depends-on**: IC-01 (the node cannot reach the independence gate until the
  evidence gate passes)
- **Risks**: a generic identity (`user`, `agent`, `system`) is refused by design; a full
  `tool:model:profile` is accepted too, but the node's subject is the override reason, so
  a plain non-generic `--agent reviewer-renata` is enough and matches the seeded
  `test-fixture` actor (no implementer of record is recorded, so independence passes).

### IC-03 — Proof and history hygiene

- **Purpose**: Record the red-first pair (planning base vs branch) and keep the branch
  honest: no `src/` diff, node count unchanged, internal changelog fragment.
- **Relevant requirements**: FR-004 (SC-003)
- **Affected surfaces**: the mission's own records; `docs/changelog/unreleased/<pr>.internal.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: `tests/tasks` is out-of-matrix, so nothing in per-PR CI proves the module;
  the proof has to be an explicit run of the file (and, where available, the nightly
  shard), recorded in the PR's Tests-run section.
