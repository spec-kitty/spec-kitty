---
work_package_id: WP06
title: 'Route tool-owned tree deletions: charter packs, skills, templates, runtime, charter'
dependencies: [WP02]
requirement_refs:
- FR-007
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:32:07.240152+00:00'
subtasks:
- T033
- T034
- T035
- T036
- T037
phase: Phase 4 - Routing
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/charter_packs/
create_intent:
- tests/specify_cli/test_tool_owned_tree_callers.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/charter_packs/snapshot.py
- src/specify_cli/charter_packs/template_render/resolve.py
- src/specify_cli/charter_packs/template_render/pipeline.py
- src/specify_cli/skills/catalog.py
- src/specify_cli/template/asset_generator.py
- src/specify_cli/template/manager.py
- src/runtime/next/runtime_bridge_query.py
- src/runtime/next/runtime_bridge_io.py
- src/charter/offering/packs/pack_assembler.py
- tests/specify_cli/test_tool_owned_tree_callers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – Route tool-owned tree deletions: charter packs, skills, templates, runtime, charter

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP06 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Replace every bare `shutil.rmtree` in these modules with `kernel.tree_removal.remove_tool_owned_tree`, naming the root the caller owns. None of these trees is a git checkout; the helper proves that at run time.

## Sites
- `charter_packs/snapshot.py` (~114-206, 8 calls: temp and old snapshot dirs)
- `charter_packs/template_render/resolve.py` (~245, ~252), `pipeline.py` (~132, ~184, ~218: staging, backup, root)
- `skills/catalog.py` (~264, ~295 `atexit.register(shutil.rmtree, ...)`, ~321, ~330)
- `template/asset_generator.py` (~49, ~89), `template/manager.py` (~195; read the #4759 back-up-first comments: keep that behaviour, route only the delete)
- `src/runtime/next/runtime_bridge_query.py` (~439), `runtime_bridge_io.py` (~777, ~881): run-store dirs
- `src/charter/offering/packs/pack_assembler.py` (~417, ~443)

## Subtasks
### T033 — charter_packs (snapshot, template_render)
### T034 — skills/catalog (the `atexit.register` call becomes `atexit.register(remove_tool_owned_tree, root, owned_root=..., reason=..., best_effort=True)`)
### T035 — template (asset_generator, manager)
### T036 — runtime bridge and charter pack assembler (layering: `src/runtime` and `src/charter` may import `kernel`; confirm against `tests/architectural/test_layer_rules.py`)
### T037 — Tests and blast radius
- For each call, `owned_root` is the directory the same function created or the documented cache root; `ignore_errors=True` becomes `best_effort=True` (behaviour preserved).
- `tests/specify_cli/test_tool_owned_tree_callers.py`: a smoke test per module group that the delete still happens on the normal path, and one test that planting a `.git` directory inside a target makes the helper refuse (proving the runtime guard reaches these callers).
- Blast radius: existing tests of each touched module (`grep -rl`), plus `tests/charter_packs tests/skills tests/runtime -q -n 4 --dist loadfile`; record counts.

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
