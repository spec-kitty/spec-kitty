---
work_package_id: WP09
title: Route Mission-type, VCS adapter, husk, worktree-memory, coordination-seed and charter-pack-source sites
dependencies: [WP02]
requirement_refs:
- FR-007
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:38:58.715914+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T048
phase: Phase 4 - Routing
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/git/test_guarded_site_routing_misc.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/core/vcs/git.py
- src/specify_cli/status/doctor_husks.py
- src/specify_cli/core/worktree.py
- src/specify_cli/coordination/coord_seed.py
- src/specify_cli/charter_packs/sources/git_source.py
- tests/specify_cli/git/test_guarded_site_routing_misc.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP09 – Route Mission-type, VCS adapter, husk, worktree-memory, coordination-seed and charter-pack-source sites

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP09 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Second half of the former WP05 (split after the post-tasks review): route these sites through the guard. Behaviour on the clean path must not change (NFR-001).

## Sites (re-locate by qualname)
| File | Line / qualname | Op | Route |
|---|---|---|---|
| `cli/commands/mission_type.py` | ~1187 `branch -D`; `_remove_lane_worktrees` ~1234 `worktree remove --force` | | `guarded_branch_delete` (creation base or reachability rule, FR-009); `guarded_worktree_remove` with a LANE context. This runs during Mission close. |
| `core/vcs/git.py` | `GitVCS.remove_workspace` ~252 | `worktree remove --force` | The guard's docstring says this is dead code with zero production callers. Confirm with `codegraph explore "GitVCS.remove_workspace"` and a grep. If dead, delete it and its tests; otherwise route it. |
| `status/doctor_husks.py` | ~180 | rmtree of a husk worktree | `guarded_tree_delete` with the husk's role. Never `remove_tool_owned_tree`: a husk whose `.git` file is gone can still hold unique work (post-tasks review). |
| `core/worktree.py` | ~559 | rmtree of `worktree_memory` | Read it. If it is a tool-created directory with no user content, `remove_tool_owned_tree(owned_root=<the memory root>)`; otherwise `guarded_tree_delete`. |
| `coordination/coord_seed.py` | ~486 | rmtree (`ignore_errors=True`) | Read it and route it the same way. |
| `charter_packs/sources/git_source.py` | `GitSource._update` ~165 `reset --hard`; rmtree ~93, ~99, ~134, ~144 | | The pack cache checkout is tool-owned: `guarded_reset_hard(context=TOOL_OWNED)` (this module is on WP08's TOOL_OWNED list). Temp dirs: `remove_tool_owned_tree`. |

## Subtasks
### T028 — mission_type.py
### T029 — core/vcs/git.py (delete if dead, else route)
### T030 — doctor_husks, core/worktree, coord_seed
### T031 — charter_packs git_source
### T048 — Tests and blast radius
- `tests/specify_cli/git/test_guarded_site_routing_misc.py`: for each site group, a clean path that behaves as before, plus a refusal when the target holds an only-copy file or a commit no other ref reaches.
- Blast radius: the existing test files of each touched module (`grep -rl "<module>" tests/ --include="*.py"`), plus `tests/status tests/charter_packs -q -n 4 --dist loadfile`. Record the counts.

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
