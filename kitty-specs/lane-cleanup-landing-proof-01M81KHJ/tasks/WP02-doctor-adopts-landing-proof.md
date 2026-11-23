---
work_package_id: WP02
title: Doctor adopts the landing proof
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-007
- SC-002
planning_base_branch: fix/7747-lane-cleanup-landing-proof
merge_target_branch: fix/7747-lane-cleanup-landing-proof
branch_strategy: Planning artifacts for this mission were generated on fix/7747-lane-cleanup-landing-proof. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7747-lane-cleanup-landing-proof unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-cleanup-landing-proof-01M81KHJ
base_commit: d9bada4c79aaedd9d095bffbb7ac3f7e75b163a0
created_at: '2026-11-23T21:22:39.642700+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 2 - Adoption
history:
- at: '2026-11-23T18:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py
- tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py
execution_mode: code_change
owned_files:
- src/specify_cli/workspace/landed_worktrees.py
- tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py
- tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Doctor adopts the landing proof

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- `doctor workspaces` rates a released Mission's lane (consolidated or pr-accepted, no active record, no retention) `landed` when `is_absorbed_but_for_mission_bookkeeping` holds against `<remote>/<primary>`, and `--prune` removes it through the guard with the same proof.
- Every other worktree keeps the plain `is_absorbed` proof (operator ruling 4).
- Today's verdict for those lanes is `not_landed` / `CONTENT_NOT_ON_PRIMARY` (#7747 comment 2026-11-21).

## Context & Constraints

- Spec FR-001, FR-007, SC-002. WP01 delivers the predicate.
- `released_mission_lane` (FR-039) keeps its contract and its callers; the slug comes from the matched Mission directory (`_mission_meta_for_lane`).
- The guard is unchanged (C-001); doctor passes the predicate as its `absorbed` proof (`_absorption_proof`).

## Branch Strategy

- **Planning base branch**: fix/7747-lane-cleanup-landing-proof
- **Merge target branch**: fix/7747-lane-cleanup-landing-proof

Implement with `spec-kitty agent action implement WP02 --agent claude --mission lane-cleanup-landing-proof-01M81KHJ`.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first doctor unit tests

- **File**: `tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py` (new, in-matrix via `core_misc`).
- Fixture like `test_landed_worktrees_mission_lane_prune.py::repo`, but the lane carries an older copy of `kitty-specs/<slug>/meta.json` and `status.json` brought in by a `--no-ff` merge of a coordination branch, and its own `src/lane.py`; the target (`main`) gets a squash of the coordination tip + `src/lane.py`, newer `meta.json` (with `merged_at`) and `status.json`; push `main` to a bare `origin`, `git remote set-head origin main`, fetch.
- Cases:
  - released lane → `Verdict.LANDED`; `prune_landed` removes it (worktree gone, branch deleted);
  - same lane without `merged_at` (unreleased) → `MISSION_OWNED` (unchanged);
  - a non-Mission worktree with the same file shape (branch not a Mission lane, e.g. `feature/x`) → `NOT_LANDED` / `CONTENT_NOT_ON_PRIMARY` (plain proof);
  - released lane whose own commit edited `tasks/WP01-*.md` body not on the target → `NOT_LANDED`.

### Subtask T008 – Red-first doctor acceptance (real CLI)

- **File**: `tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py` (nightly-only dir: disclose).
- Reuse `build` from `tests/integration/test_default_mission_consolidate_lands_primary.py`; consolidate with `--keep-worktree --keep-branch` (the run's flags, not `meta.json` retention) so the lanes stay; add a bare `origin`, `git push origin work:main`, `git remote set-head origin main`, `git fetch origin`; `assess_worktrees(root, current_dir=root, probe=<idle>)` → every lane `LANDED`; `prune_landed` removes all three.
- The run flags do not write `retain_*` into `meta.json` (retention is minted only at `mission create`, `core/mission_creation_decisions.py`), so the released-lane rules still apply. If the assessment shows `MISSION_OWNED` instead, stop and report to the dispatcher before improvising.

### Subtask T009 – Released Mission slug

- Refactor `_mission_meta_for_lane` to return the matched Mission directory name alongside its meta (e.g. `tuple[str, dict] | None`), add `released_mission_slug(repo_root, branch) -> str | None` that applies today's `released_mission_lane` rules and returns the directory name; `released_mission_lane` becomes `released_mission_slug(...) is not None`. Keep `released_mission_lane` public and unchanged in behavior.

### Subtask T010 – Adoption

- `_absorption(entry, ctx)`: `slug = released_mission_slug(ctx.repo_root, entry.branch)` when `entry.branch` parses as a Mission lane; with a slug call the predicate, else plain `is_absorbed` (keep `AbsorptionUnsupported` → `UNPROVEN` for the plain path).
- `_absorption_proof(repo_root, mission_slug: str | None)`: the guard's proof uses the same choice; `_prune_one` passes the slug for `verdict.branch`.
- Avoid computing the slug twice per worktree if cheap to thread; correctness first.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/workspace/ -q -n auto --dist loadfile
uv run --frozen pytest tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py -q   # nightly-only: disclose
uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -q       # out-of-matrix: disclose
make test-fast
uv run --frozen mypy src/specify_cli/workspace/landed_worktrees.py
```

## Risks & Mitigations

- A Mission directory missing on the checkout's working tree: no slug → plain proof (fails toward keeping).

## Review Guidance

- Red-first ordering; the non-Mission negative uses the plain proof; `released_mission_lane` behavior unchanged.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP02 --note "..."`.
