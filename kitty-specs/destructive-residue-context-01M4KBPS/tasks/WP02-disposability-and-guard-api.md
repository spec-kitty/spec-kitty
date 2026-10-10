---
work_package_id: WP02
title: Context-aware disposability and the guard API
dependencies: [WP01]
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-009
- NFR-002
planning_base_branch: fix/5965-5966-destructive-residue-context
merge_target_branch: fix/5965-5966-destructive-residue-context
branch_strategy: Planning artifacts for this mission were generated on fix/5965-5966-destructive-residue-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5965-5966-destructive-residue-context unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-destructive-residue-context-01M4KBPS
base_commit: 5ecf837aa4e4673329be3b2d3a2b849594741586
created_at: '2026-10-10T17:57:10.989875+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Foundation
history:
- at: '2026-10-10T18:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- src/kernel/tree_removal.py
- tests/coordination/test_disposable_residue.py
- tests/kernel/test_tree_removal.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/coordination/coherence.py
- src/specify_cli/git/destructive_guard.py
- src/specify_cli/git/ref_advance.py
- src/kernel/tree_removal.py
- tests/coordination/test_disposable_residue.py
- tests/specify_cli/git/test_destructive_guard.py
- tests/git/test_ref_advance_resync_to_tip.py
- tests/kernel/test_tree_removal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Context-aware disposability and the guard API

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

---

Implement with:

```bash
spec-kitty agent action implement WP02 --agent claude --mission destructive-residue-context-01M4KBPS
```

Read first: `kitty-specs/destructive-residue-context-01M4KBPS/spec.md`, `plan.md`, `research.md` (decisions D1–D7), `data-model.md`, `contracts/refusal-codes.md`.

## Objective

Give the destructive guard everything it needs to decide disposability itself, and give every destructive operation a guard entry point. This WP adds the new API alongside the old `is_residue` parameter; the call sites move in WP03–WP07, and WP08 removes `is_residue`.

## Subtasks

### T005 — `CheckoutRole` and `ResidueContext`
- In `src/specify_cli/coordination/coherence.py` (next to `is_toolchain_generated_churn`, line ~347): add `class CheckoutRole(StrEnum)` with `REPOSITORY_ROOT`, `COORDINATION`, `MISSION`, `LANE`, `TOOL_OWNED`, and a frozen dataclass `ResidueContext(role, mission_slug, topology)` per `data-model.md`.
- Validation in `__post_init__`: for every role except `TOOL_OWNED`, `mission_slug` must be a non-empty string and `topology` a `MissionTopology`; otherwise raise `ValueError`. No `None` defaults.
- Factory `ResidueContext.for_mission(repo_root, mission_slug, role)` reads the stored topology through the existing reader the merge dirty gate already uses (find it: `grep -rn "stored topology\|read_topology\|MissionTopology(" src/specify_cli/consolidation/phase_teardown.py` — `_remove_lane_worktrees` threads it, issue #4978). An unreadable topology raises; never projects COORD.
- Export both from `specify_cli.coordination` only if that package's `__init__` already re-exports `is_toolchain_generated_churn`; otherwise import from the module.

### T006 — `is_disposable_residue(path, context)`
- Same module. Decision table from `data-model.md` (first match wins): TOOL_OWNED → True; another Mission's `kitty-specs/<slug>/` path → False; `is_self_bookkeeping_churn` → True; COORDINATION role → False; otherwise `is_coord_residue_churn(path, mission_slug=..., topology=...)`.
- Parse the Mission segment of a path with the same helper `is_coord_residue_churn` uses for its `mission_slug` check (do not write a new regex; C-001).
- Tests in `tests/coordination/test_disposable_residue.py`, parametrized over role × path kind: review-cycle, `traces/notes.md`, `acceptance-matrix.json`, `issue-matrix.md`, `status.events.jsonl`, `status.json`, `meta.json`, `spec.md`, a source file, another Mission's review-cycle. Include the exact #5965 case (COORDINATION + review-cycle → False) and #5966 case (REPOSITORY_ROOT + other Mission's traces → False), plus positive controls (own `status.json` in COORDINATION → True via self-bookkeeping? check: `status.json` may be coord-residue rather than self-bookkeeping; if so, decide with the classifier's real behaviour and document it in the test — the NFR-001 normal path must keep cleaning the Mission's own regenerated status copy in the repository root checkout).

### T007 — Guard and ref-advance accept `context`
- `git/destructive_guard.py`: `assert_worktree_clean` and `guarded_worktree_remove` gain keyword `context: ResidueContext | None = None`; exactly one of `context` / `is_residue` must be given (raise `TypeError` otherwise). When `context` is given, the predicate is `functools.partial(is_disposable_residue, context=context)`.
- `git/ref_advance.py`: the same for `advance_branch_ref`, `restore_branch_ref`, `resync_checkouts_to_tip`, and the private `_dirty_entries` / `_checkouts_ready_for` chain. Note `resync_checkouts_to_tip` resets every checkout of a branch, and different checkouts can have different roles: accept `context_for: Callable[[Path], ResidueContext]` OR a single context plus derive role per worktree with a small resolver `checkout_role_for(repo_root, worktree, mission_slug)` (repository root vs `.worktrees/*-coord` vs lane vs mission). Pick the resolver; keep it in `coherence.py` or the guard, with tests.
- The refusal message (`DestructiveOpRefused` / `RefAdvanceDirtyWorktreeError`) lists at most 20 entries then `... and N more` (NFR-002). Add that truncation where the message is built if it is not there.

### T008 — New guard entry points (D5)
- In `git/destructive_guard.py`: `guarded_reset_hard(worktree, target, *, context, env=None)`; `guarded_merge_abort(worktree, *, context, env=None)`; `guarded_worktree_prune(repo_root, *, env=None)` (prune only removes registrations whose directory is gone — assert that by listing `git worktree list --porcelain` prunable entries first and refusing if a listed path exists on disk); `guarded_branch_delete(repo_root, branch, *, creation_base: str | None, env=None)` implementing FR-009 (allowed when `branch` has no commits beyond `creation_base`, or every commit is reachable from another local ref; else raise `DestructiveOpRefused(error_code="BRANCH_HAS_UNIQUE_COMMITS")`); `guarded_tree_delete(path, *, context, env=None)` for a directory that is (or is inside) a git checkout: dirty-scan like `guarded_worktree_remove` with `treat_untracked_as_dirty=True`, then `shutil.rmtree`.
- Each runs its git argv through the module's `_run_git`, so the only raw destructive argv literals live in this module and `ref_advance.py`.
- Use the existing error-code constants style (`MERGE_UNSAFE_*`); add `DESTRUCTIVE_OP_ONLY_COPY` and `BRANCH_HAS_UNIQUE_COMMITS` per `contracts/refusal-codes.md`.

### T009 — `kernel.tree_removal.remove_tool_owned_tree`
- New `src/kernel/tree_removal.py`: `remove_tool_owned_tree(path: Path, *, owned_root: Path, reason: str, missing_ok: bool = True) -> bool`. Refuse with a `ToolOwnedPathUnproven(ValueError)` (code `TOOL_OWNED_PATH_UNPROVEN`) when `path.resolve()` is not inside `owned_root.resolve()`, or when `path` or any directory from `path` up to and including `owned_root` contains a `.git` entry (file or dir) — a git checkout is deleted only by `guarded_tree_delete`. Handle read-only entries on Windows the way `asset_preservation/guard.py::_rmtree_with_retry` does (copy the small onexc/onerror shim; kernel must not import `specify_cli`). `ignore_errors` is never used silently: return False when nothing existed, raise on a real failure, unless the caller passes `best_effort=True` (then log at debug and return False).
- Check `src/kernel/pyproject.toml` / `__init__.py` for an export list and the kernel import rules (`tests/architectural/test_layer_rules.py`): kernel imports only stdlib.
- Tests `tests/kernel/test_tree_removal.py`: inside-root removal; outside-root refusal; symlink escaping root refused; `.git` dir and `.git` file (linked worktree) refused; missing path; read-only file.

### T010 — Unit tests for the guard additions
- Extend `tests/specify_cli/git/test_destructive_guard.py`: each new entry point clean → runs; dirty only-copy → refuses with no mutation (assert HEAD, index and files unchanged); `guarded_branch_delete` with unique commits refuses, with merged commits deletes, with commits only beyond creation base refuses; prune refuses when a registered path exists.
- Extend `tests/git/test_ref_advance_resync_to_tip.py`: with `context` for a COORDINATION checkout, an uncommitted review-cycle refuses the resync; with REPOSITORY_ROOT context, another Mission's traces file refuses; own stale status copy is cleaned (positive control).

### T011 — Exactly-one-of contract tests
- This WP is purely additive: `is_residue` keeps working unchanged for every existing caller, so sibling tests that WP02 does not own (`tests/git/test_restore_branch_ref_resync.py`, `tests/git/test_ref_advance_git_paths.py`, and the others listed in WP08) stay green. Run those two files to prove it.
- Passing both `context` and `is_residue`, or neither, raises `TypeError` at every widened function. This is the hook WP08 uses to delete `is_residue` safely.

### T012 — Record design notes
- Append the role-resolver choice and any classifier surprise (for example where `status.json` actually lands) to `traces/design-trace.md`.

## Definition of Done
- New API in place, old `is_residue` path still works, all tests in the four owned test files green, ruff/mypy clean.

## Reviewer guidance
- Reject a filename list or regex that duplicates the partition rule (C-001).
- Reject any default that yields the destructive answer when context is missing (C-002).
- Reject any change that breaks an existing `is_residue` caller (this WP is additive).

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
