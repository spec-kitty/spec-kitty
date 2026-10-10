---
work_package_id: WP01
title: 'Red-first reproductions for #5965 and #5966'
dependencies: []
requirement_refs:
- FR-008
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T17:36:56.878231+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Red-first
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent:
- tests/consolidation/test_coord_teardown_only_copy_5965.py
- tests/consolidation/test_abort_resync_other_mission_5966.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/consolidation/test_coord_teardown_only_copy_5965.py
- tests/consolidation/test_abort_resync_other_mission_5966.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Red-first reproductions for #5965 and #5966

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP01 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Land two issue-pinned reproductions that are RED on the current code for the reported reason, through the real entry points (ADR 2026-07-17-1, ATDD red-first). Nothing in `src/` changes in this WP.

Done when both files exist, are marked `@pytest.mark.regression` and `@pytest.mark.p0_repro(issue=N)`, fail on this branch's base with the data-loss assertion (not a fixture error), and the failure output is pasted into the WP activity log.

## Context

- #5965: `spec-kitty agent tasks move-task WP01 --to planned --no-auto-commit` on a coordination-topology Mission leaves `tasks/WP01-*/review-cycle-1.md` uncommitted in the coordination worktree. A hand-written `traces/notes.md` sits there too. `consolidate` then reaches `coordination/workspace.py::CoordinationWorkspace.teardown`, whose residue predicate (`is_toolchain_generated_churn` with `mission_slug` but no topology) classifies both as coordination residue, so `guarded_worktree_remove` force-removes the worktree; `coordination/teardown.py::_destroy_coordination_worktree` swallows any refusal; exit 0.
- #5966: `consolidation/rollback.py::_resync_kept_coord_checkout` and `_restore_one` pass the bare `is_toolchain_generated_churn` (no Mission, no topology → COORD projection). Mission B's uncommitted review-cycle and `traces/` files in the repository root checkout are judged residue and `reset --hard` destroys them during Mission A's `consolidate --abort`.
- Read the issue threads first: `unset GITHUB_TOKEN; gh issue view 5965 -R spec-kitty/spec-kitty --comments` (and 5966). They carry reporter scripts; mirror their steps.
- Fixture factories live in `tests/_factories/` (`coord_mission.py` and siblings). Reuse them; do not hand-roll a repository layout. Look at `tests/consolidation/` for existing end-to-end consolidate tests that drive `cli.commands.consolidate` via `CliRunner` or a subprocess, and copy their shape.

## Subtasks

### T001 — #5965 reproduction through move-task and consolidate
- File: `tests/consolidation/test_coord_teardown_only_copy_5965.py`.
- Build a coordination-topology Mission with at least one approved/done WP ready to consolidate and a second WP that is rejected through the REAL `move-task --to planned --no-auto-commit` entry point (that call decides where the review-cycle file lands; do not plant it by hand). Then write `kitty-specs/<slug>/traces/notes.md` in the coordination worktree.
- Run the real `consolidate` entry point.
- Assert (these are the assertions that must be RED today): the review-cycle file and `traces/notes.md` still exist with their bytes; the coordination worktree directory still exists; the exit code is non-zero.
- Positive control on the same fixture (FR-002 no-op guard): a second test where the only uncommitted file in the coordination worktree is regenerated tool output (for example the Mission's own `status.json`) — teardown removes the worktree and consolidate exits 0. This must be GREEN today and stay green.
- If consolidate refuses earlier for an unrelated reason (for example the rejected WP blocks the claim), restructure the fixture so the rejected WP's lane is canceled or excluded the way the issue's script did; document the choice in the test docstring.

### T002 — #5966 reproduction through consolidate --abort
- File: `tests/consolidation/test_abort_resync_other_mission_5966.py`.
- Two Missions in one repository: Mission A (`lanes` topology) mid-consolidation with a persisted snapshot so `--abort` performs a rollback and the kept-coordination resync or a branch restore with `resync_checkouts=True` on the repository root checkout; Mission B with uncommitted `kitty-specs/<B>/tasks/WP01-*/review-cycle-1.md` and `kitty-specs/<B>/traces/notes.md` in the repository root checkout.
- Easiest real route: start `consolidate` for A, interrupt after the first mutation (the existing tests in `tests/consolidation/` that exercise `rollback_to_snapshot` show how to get a persisted `pre_mutation_refs`), then invoke `consolidate --abort`.
- Assert RED today: Mission B's two files survive byte-for-byte. Assert the abort either exits non-zero naming them or leaves the checkout untouched (the fixed behaviour is a refusal naming the files; write the assertion for the refusal and note it).
- Positive control: Mission A's own stale status copy is the only dirty file → the resync cleans it (green today, stays green).

### T003 — Prove red for the right reason
- Run both files on the WP base: `.venv/bin/python -m pytest tests/consolidation/test_coord_teardown_only_copy_5965.py tests/consolidation/test_abort_resync_other_mission_5966.py -q -p no:randomly`.
- The red tests must fail on the file-survival assertion. If they fail on setup, fix the fixture. Paste the failing assertion lines into the activity log.

### T004 — Mark and commit
- Markers: `@pytest.mark.regression`, `@pytest.mark.p0_repro(issue=5965)` / `(issue=5966)`. Check `pytest.ini` for how `p0_repro` is registered and whether it deselects by default (it runs only in the nightly p0 lane unless `SPEC_KITTY_RUN_P0_REPRO=1`); run with that variable set to prove red.
- Commit: `test(consolidate): red-first reproductions for only-copy loss (#5965 #5966)`.

## Definition of Done
- Two files, red for the reported reason, positive controls green, markers present, failure output recorded.

## Reviewer guidance
- Reject if any file is planted where the real flow never writes it, or if a red test fails for a fixture reason.

## Branch Strategy

- Planning branch: `fix/5965-5966-destructive-residue-context`; final merge target: `fix/5965-5966-destructive-residue-context` (it reaches `main` by PR).
- Execution worktrees are allocated per computed lane from `lanes.json` by `spec-kitty agent action implement <WP> --agent claude --mission destructive-residue-context-01M4KBPS`. Never create or guess a worktree path yourself.
- In a lane worktree, set `PYTHONPATH=$PWD/src:$PWD` (absolute) for any subprocess-driven CLI test, and run pytest with `.venv/bin/python -m pytest` from the repository root's venv; never a bare `uv run` (it re-syncs and rewrites `uv.lock` to a private mirror). If `uv.lock` shows as modified, `git checkout -- uv.lock` before committing.
- Run narrow, file-scoped pytest only; never `make test-full` or a whole `tests/` directory sweep from inside the WP.

## Standing rules for this WP

- Complexity ≤ 15 per function; ruff, `ruff format --check --force-exclude <files>` and mypy clean on every touched file. No new `# noqa` / `# type: ignore` without an inline reason.
- Every new branch or helper gets a focused test in the same commit (diff coverage ≥ 90%).
- Commit frequently with conventional messages that cite the issue (`fix(consolidate): ... (#5965)`), ending with the Co-Authored-By / Claude-Session trailers.
- Terminology: Mission, consolidate, coordination worktree, repository root checkout. Never "feature"; never bare "primary" or "merge" (name the sense).
- Append witnessed tooling friction, approach notes and design notes to `kitty-specs/destructive-residue-context-01M4KBPS/traces/*.md` (commit them immediately; mission commands can rewrite the mission directory).
