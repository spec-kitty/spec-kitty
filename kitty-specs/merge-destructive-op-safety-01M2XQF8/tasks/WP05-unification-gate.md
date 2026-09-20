---
work_package_id: WP05
title: Unification routing gate (NFR-006)
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-007
- NFR-006
planning_base_branch: fix/merge-destructive-op-safety
merge_target_branch: fix/merge-destructive-op-safety
branch_strategy: Planning artifacts for this mission were generated on fix/merge-destructive-op-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/merge-destructive-op-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-destructive-op-safety-01M2XQF8
base_commit: be5c1b306d01072628732d4a015e0be2d2c1b980
created_at: '2026-09-19T23:25:31.245001+00:00'
subtasks:
- T018
- T019
- T020
phase: Phase 1 - Implementation
history:
- at: '2026-09-19T21:10:00Z'
  actor: system
  action: Prompt generated for merge-destructive-op-safety mission
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_destructive_op_routing.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_destructive_op_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4752'
- '4753'
- '4754'
---

# Work Package Prompt: WP05 – Unification routing gate

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
before anything else. Then read `spec.md` (NFR-006), `plan.md` (IC-5), and
`contracts/routing-invariant.md`.

## Objective

Lock the defect class shut by construction with a NON-VACUOUS architectural gate
(DIRECTIVE_043): the three destructive commands may execute ONLY behind the WP01
guard / WP02 chokepoint, and no new parallel dirty predicate may be introduced.
This is the difference between a fix that holds and one that re-forks next quarter.

## Context

- **The allowlist MUST be built from a live census — do not trust a pre-baked list.**
  The post-tasks lens proved a hand-written baseline was factually wrong (omitted
  real sites, listed a phantom). Run the census against the mission's own branch
  (post WP01–WP04) and adjudicate EVERY site.
- Known sites to adjudicate (verify at current line; classify each in→routed vs
  out→allowlist-with-inline-rationale):
  - `reset --hard`: `git/ref_advance.py` (allow — resync after ref advance),
    `merge/git_probes.py` (allow — now guarded by WP03),
    `doctrine/sources/git_source.py` (allow — doctrine CLONE dir, not repo_root),
    `lanes/worktree_allocator.py` alloc-rollback (allow — atomic rollback to a
    pre-loop ref).
  - user-facing `worktree remove --force`: `merge/executor.py` lane cleanup (routed
    → WP03), `coordination/workspace.py` teardown + stale-prune (routed → WP02),
    `orchestrator_api/commands.py` (routed → WP02), `lanes/worktree_allocator.py`
    fresh-worktree removal (adjudicate: allow-with-rationale — tree known-clean — or
    route).
  - detached/scratch/temp (allow): `merge/ordering.py`, `lanes/merge.py`,
    `review/baseline.py`, `merge/workspace.py` scratch (C-006),
    `mission_type.py --discard` (intentional), `core/vcs/git.py remove_workspace`
    (unused adapter, zero callers).
  - `git merge --abort` on `repo_root`: gated by WP04.

## Subtasks

### T018 — Routing gate (`tests/architectural/test_destructive_op_routing.py`)
FIRST run a live AST/grep census of `src/specify_cli/` for every `reset --hard`,
`worktree remove --force`, and `merge --abort` command site. Partition each into
{in-scope → must route through the WP01 guard/`guarded_worktree_remove`} vs
{out-of-scope → allowlist with a one-line inline rationale}. Encode the resulting
allowlist as a shrink-only frozen baseline; growth FAILS, shrink WARNS. The gate
must be GREEN on the routed tree — if it reds on an untouched site, that site is
mis-classified (adjudicate it), NOT silently widened.

### T019 — No-new-parallel-predicate assertion
Assert the mission did not add a new module-level `git status --porcelain`-parsing
"is dirty" predicate in the merge/vcs/coordination seams beyond the reused
`_dirty_entries` + WP01 guard. (A curated known-predicate set + a fail-on-growth
check.)

### T020 — Self-mutation companion test
Add a test proving non-vacuity: simulate routing a destructive op around the
chokepoint (e.g. a fixture string / temporary allowlist removal) and assert the
gate goes RED — so a future real regression cannot pass silently.

## Branch Strategy

Planning base: `fix/merge-destructive-op-safety`. Final merge target: `main`.
Enter the lane workspace `spec-kitty implement WP05` prepares. Depends on WP02,
WP03, WP04 being approved (the routing must be complete before the gate asserts it).

## Test Strategy

The gate IS the test. It must be GREEN on the routed tree (post WP02–WP04) and RED
under the T020 self-mutation. Targeted:
`.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py -q`.
Do NOT run the whole `tests/architectural/` suite locally (it is heavy) — run this
file only.

## Definition of Done

- Gate green on the integrated tree; RED under the self-mutation case.
- Allowlist built from a live census; every entry carries an inline rationale;
  shrink-only.
- No-new-predicate assertion present and meaningful.
- **C-004 follow-up recorded**: add the deferred standalone `git branch -D`
  unmerged-commit loss surface (executor/orchestrator/mission_creation) as a note
  for the PR body (distinct loss surface, needs an is-branch-merged guard — a
  separate mission).
- `ruff`/`mypy` clean; no suppressions.

## Risks

- **Vacuous gate** (passes even when a site is unguarded) — T020 is the guard
  against that; a reviewer must confirm the self-mutation actually reds the gate.
- **Over-broad match** flagging legitimate temp-worktree removals — scope the
  allowlist precisely per `contracts/routing-invariant.md`.

## Reviewer Guidance

Verify the self-mutation test genuinely fails the gate; confirm the allowlist
matches the frozen baseline and only shrinks; confirm the predicate-count check is
not trivially satisfiable.
