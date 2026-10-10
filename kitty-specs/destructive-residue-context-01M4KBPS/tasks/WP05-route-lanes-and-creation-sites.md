---
work_package_id: WP05
title: Route lane allocation and Mission-creation sites
dependencies: [WP02]
requirement_refs:
- FR-007
- FR-009
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:28:47.819571+00:00'
subtasks:
- T026
- T027
- T032
phase: Phase 4 - Routing
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/git/test_guarded_site_routing.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/core/mission_creation_rollback.py
- src/specify_cli/missions/_create.py
- src/specify_cli/cli/commands/agent/mission_create.py
- tests/specify_cli/git/test_guarded_site_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – Route lane allocation and Mission-creation sites

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP05 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Route the lane-allocation and Mission-creation destructive operations through the guard (the Mission-type, VCS adapter, husk, worktree-memory, coordination seed and charter pack source sites moved to WP09). These are the sites that today force through dirty state with no only-copy check.

## Sites (re-locate by qualname)
| File | Qualname / line | Op | Route |
|---|---|---|---|
| `lanes/worktree_allocator.py` | `_merge_dependency_lane_tips` (~1659) | `reset --hard pre_loop_ref`, `merge --abort` | `guarded_reset_hard` / `guarded_merge_abort`, LANE role |
| | `_merge_recorded_planning_commit` | `merge --abort` | `guarded_merge_abort`, LANE |
| | `_remove_lane_worktree` (~1914) | `worktree remove --force` | `guarded_worktree_remove`, LANE |
| | ~1147 | `worktree prune` | `guarded_worktree_prune` |
| `core/mission_creation_rollback.py` | ~163, ~240 rmtree; ~246 prune; ~262, ~352 `branch -D` | | `guarded_tree_delete` for both rmtree calls (a coordination Mission dir can hold unique work; never `remove_tool_owned_tree` here); prune → guard; `branch -D` → `guarded_branch_delete(creation_base=<sha recorded at create>)` (FR-009) |
| `missions/_create.py` | ~456 | `branch -D` | `guarded_branch_delete` with creation base |
| `cli/commands/agent/mission_create.py` | ~200 | `branch -D` of the start branch | `guarded_branch_delete` |
| `cli/commands/mission_type.py` | ~1187 `branch -D`, `_remove_lane_worktrees` ~1234 `worktree remove --force` | | guard (LANE role) |
| `core/vcs/git.py` | `GitVCS.remove_workspace` ~252 | `worktree remove --force` | the guard comment says this is dead code with zero production callers: confirm with `codegraph explore "GitVCS.remove_workspace"`; if dead, delete it (and its tests); else route |
| `status/doctor_husks.py` | ~180 | rmtree of a husk worktree | `guarded_tree_delete` with LANE/MISSION role, or prove it holds no `.git` and use `remove_tool_owned_tree` |
| `core/worktree.py` | ~559 | rmtree of `worktree_memory` | read it; likely a tool-owned dir inside a worktree → `remove_tool_owned_tree(owned_root=<the memory root>)` |
| `coordination/coord_seed.py` | ~486 | rmtree | read it; route accordingly |
| `charter_packs/sources/git_source.py` | `GitSource._update` ~165 `reset --hard`; rmtree at ~93, ~99, ~134, ~144 | | pack cache checkout is TOOL_OWNED → `guarded_reset_hard(context=TOOL_OWNED)`; temp dirs → `remove_tool_owned_tree` |

## Subtasks
### T026 — worktree_allocator (4 sites)
### T027 — Mission-creation rollback and branch deletes (FR-009; record the creation base at create time if it is not recorded yet; find where the branch is created in the same module)
### T032 — Tests and blast radius
- `tests/specify_cli/git/test_guarded_site_routing.py`: per site group, a clean path that behaves as before and an only-copy / unique-commit refusal. For Mission-creation rollback, prove a just-created branch with no commits beyond its base is still deleted (FR-009 positive control).
- Blast radius: run the existing test files for each touched module (find them with `grep -rl "<module_name>" tests/ --include="*.py"`), plus `tests/lanes tests/missions tests/status -q -n 4 --dist loadfile`; record counts.

For each subtask: route, keep behaviour on the clean path, and add the refusal test. Where a site intentionally forced through dirty state before (lane retry reset), the refusal is the new behaviour; describe it in the CHANGELOG notes you leave in the activity log for WP08.

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
