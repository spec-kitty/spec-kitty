---
work_package_id: WP04
title: Route the remaining consolidation-family destructive sites
dependencies: [WP02]
requirement_refs:
- FR-007
- NFR-001
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T18:25:24.609916+00:00'
subtasks:
- T020
- T021
- T022
- T023
- T024
- T025
phase: Phase 4 - Routing
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_guarded_consolidation_sites.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/consolidation/resume_recovery.py
- src/specify_cli/consolidation/git_probes.py
- src/specify_cli/consolidation/workspace.py
- src/specify_cli/consolidation/mission_number/bake.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/review/baseline.py
- tests/consolidation/test_guarded_consolidation_sites.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – Route the remaining consolidation-family destructive sites

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP04 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Move every remaining raw destructive operation in the consolidation family behind the guard, with the right context, so none of them can discard an only copy. Behaviour on clean or residue-only checkouts must not change (NFR-001).

## Sites (main `f810b924a9`; re-locate by qualname, lines drift)
| File | Qualname | Op | Route |
|---|---|---|---|
| `consolidation/resume_recovery.py` | `_recover_behind_head_primary_on_resume` | `reset --hard HEAD` | `guarded_reset_hard(worktree, "HEAD", context=<role of the checkout being recovered>)` — the "provably pure" check stays; the guard is the second line |
| `consolidation/git_probes.py` | `_refresh_primary_checkout_after_merge` | `reset --hard HEAD` | `guarded_reset_hard`, REPOSITORY_ROOT role |
| `consolidation/workspace.py` | `cleanup_merge_workspace` (+ rmtree at ~79, ~142) | `worktree remove --force`, rmtree | scratch under `.kittify/runtime/merge/<id>/workspace`: TOOL_OWNED context for the worktree remove; `remove_tool_owned_tree(path, owned_root=<.kittify/runtime/merge/<id>>, reason=...)` for the directories |
| `consolidation/mission_number/bake.py` | `_compute_next_mission_number_or_none`, `_write_mission_number_to_branch` | `worktree remove --force` (+ an `is_residue=` at ~694) | scratch worktrees: TOOL_OWNED; the `is_residue` call → context |
| `lanes/consolidation.py` | `preview_mission_target_integration`, `_merge_branch_into` | `worktree remove --force` (scratch), `merge --abort` ×2, `is_residue=` at ~1480/1565 | scratch → TOOL_OWNED; `merge --abort` → `guarded_merge_abort` with the checkout's context; `is_residue` → context |
| `lanes/auto_rebase.py` | `_abort_with_failure` | `merge --abort` | `guarded_merge_abort`, LANE role |
| `review/baseline.py` | `_baseline_worktree` | `worktree remove --force` (scratch temp) | TOOL_OWNED |

## Subtasks

### T020 — resume_recovery and git_probes
Route both `reset --hard HEAD` calls. Keep the existing provably-pure gate in front. Test: dirty only-copy file → refusal, nothing reset; residue-only → reset as today.

### T021 — Scratch worktrees (consolidation/workspace, bake, lanes/consolidation preview, review/baseline)
Use a TOOL_OWNED context. Confirm each path is created by the same function under `.kittify/runtime/` or a `tempfile.mkdtemp` root; if any is not, use the Mission's real role instead and say why in the activity log. Replace each `shutil.rmtree(..., ignore_errors=True)` with `remove_tool_owned_tree(..., owned_root=..., reason=..., best_effort=True)`.

### T022 — merge --abort sites
`lanes/consolidation.py::_merge_branch_into` (2) and `lanes/auto_rebase.py::_abort_with_failure`: `guarded_merge_abort`. A merge in progress whose conflict files are the operator's edits must refuse rather than abort over them. Read #4754 in the CHANGELOG for the prior fix in this area before changing behaviour.

### T023 — Residual `is_residue=` callers in owned files
`bake.py:~694`, `lanes/consolidation.py:~1480, ~1565`: switch to `context=`.

### T024 — Tests
`tests/consolidation/test_guarded_consolidation_sites.py`: one clean-path and one only-copy-refusal test per routed site group (parametrize where the shape is shared). Use real git repositories in `tmp_path`.

### T025 — Blast radius
`.venv/bin/python -m pytest tests/consolidation tests/lanes tests/review -q -n 4 --dist loadfile`; record counts. Classify any red against the base (CLAUDE.md baseline-red gotcha).

## Definition of Done
No raw destructive argv or bare `shutil.rmtree` left in the owned files; tests green.

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
