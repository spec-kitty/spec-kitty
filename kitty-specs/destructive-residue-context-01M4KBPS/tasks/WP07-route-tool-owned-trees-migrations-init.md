---
work_package_id: WP07
title: 'Route tool-owned tree deletions: upgrade migrations, migration runner, init, runtime merge, utils'
dependencies: [WP02]
requirement_refs:
- FR-007
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:35:32.260977+00:00'
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 4 - Routing
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_migration_tree_removal_routing.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/migrations/m_0_7_2_worktree_commands_dedup.py
- src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py
- src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py
- src/specify_cli/upgrade/migrations/m_0_6_5_commands_rename.py
- src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py
- src/specify_cli/migration/runner.py
- src/specify_cli/cli/commands/init.py
- src/specify_cli/runtime/merge.py
- src/specify_cli/core/utils.py
- tests/upgrade/test_migration_tree_removal_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP07 – Route tool-owned tree deletions: upgrade migrations, migration runner, init, runtime merge, utils

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP07 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Route the remaining bare `shutil.rmtree` calls (upgrade migrations, the migration runner, `init`, the runtime managed-dir merge, and `core/utils.safe_remove`) through `remove_tool_owned_tree` or, where the code already proves ownership, through `asset_preservation.guard.guard_destructive_removal`.

## Sites
- Migrations: `m_0_7_2_worktree_commands_dedup.py:~69`, `m_0_9_1_complete_lane_migration.py:~324, ~425, ~453`, `m_0_9_0_frontmatter_only_lanes.py:~272`, `m_0_6_5_commands_rename.py:~141`, `m_2_0_6_consistency_sweep.py:~449, ~466`. Several of these delete directories inside a worktree (`wt_commands`, `lane_dir`); the `.git` check in the helper is on the target and its ancestors up to `owned_root`, so choose `owned_root` as the managed directory (for example `<worktree>/.claude/commands`), never the worktree root. If a site really deletes user-authored files, route it through `asset_preservation.guard.guard_destructive_removal` like `m_3_1_1_charter_rename.py` does.
- `migration/runner.py:~89, ~128, ~170, ~201` (backup dirs and `kitty_specs`; ~128 deletes `kitty-specs` — read it carefully; that is user content, so it must go through the asset-preservation guard or be proven a restored-from-backup copy)
- `cli/commands/init.py:~459` (`project_path` rmtree on a failed init the same run created) and `~1595` (scratch)
- `specify_cli/runtime/merge.py:~69` (managed dirs)
- `core/utils.py:~232` `safe_remove`: find its callers; give it an `owned_root` parameter or replace its callers.

## Subtasks
### T038 — Migrations (8 calls)
### T039 — migration/runner.py (treat `kitty_specs` with care, see above)
### T040 — init.py and runtime/merge.py
### T041 — core/utils.safe_remove and its callers (callers outside the owned list: record a one-line out-of-map rationale in the activity log, or leave `safe_remove`'s signature compatible and route internally)
### T042 — Tests and blast radius
- `tests/upgrade/test_migration_tree_removal_routing.py`: per group, normal path still deletes; a planted `.git` makes the helper refuse.
- Blast radius: existing tests for each touched migration and module, plus `tests/upgrade tests/migration -q -n 4 --dist loadfile`; record counts. Migrations are covered by `tests/architectural/test_migration_chain_integrity.py`; run that file.

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
