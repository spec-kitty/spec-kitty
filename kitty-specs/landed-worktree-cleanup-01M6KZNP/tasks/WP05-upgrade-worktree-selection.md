---
work_package_id: WP05
title: Upgrade worktree selection
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- SC-002
- SC-004
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-landed-worktree-cleanup-01M6KZNP
base_commit: 4898483095eb6a369303a5f639e0272af22da12f
created_at: '2026-11-04T23:50:45.566801+00:00'
subtasks:
- T018
- T019
- T020
- T021
- T022
- T023
phase: Phase 1 - Core behaviour
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/specify_cli/upgrade/worktree_selection.py
- tests/upgrade/test_upgrade_worktree_selection.py
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/worktree_selection.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/cli/commands/upgrade.py
- tests/upgrade/test_upgrade_worktree_selection.py
- tests/upgrade/test_upgrade_worktree_commit.py
- tests/upgrade/test_upgrade_integrating_worktrees.py
- tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py
- tests/upgrade/test_worktree_stamp_guard.py
- tests/upgrade/test_exclude_worktrees_migration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Upgrade worktree selection

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record changes with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Objectives & Success Criteria

- Default `spec-kitty upgrade` writes and commits into **no** non-Mission worktree (FR-007). Mission and detached worktrees stay skipped as today (#5457).
- `--include-worktree PATH` (repeatable) and `--all-worktrees` opt worktrees in (FR-008). A named path that is not a direct child of `.worktrees/` is refused **before any write** with exit 2 and `UPGRADE_WORKTREE_NOT_FOUND`; `--no-worktrees` combined with either opt-in flag is refused with exit 2.
- The normal preview (`--dry-run`) and the normal output list every `.worktrees/` entry with its disposition (FR-009), in the format of `contracts/upgrade-worktree-selection-cli.md`.
- `--plan-json` carries `intent.worktree_selection` and top-level `worktree_dispositions`; `commit_policy.worktrees_enabled` is true only when at least one worktree is selected (FR-010).
- SC-002: on the repro fixture a plain `upgrade --yes` produces 0 new commits on any non-Mission branch.

## Context & Constraints

- Code grounding (`research.md` §1): `upgrade/runner.py:164-195` (`_is_integrating_worktree`, `_worktrees_to_upgrade`), `_upgrade_worktrees` (~line 744), `upgrade_worktrees_only` (~446), `upgrade()` (include_worktrees); CLI `cli/commands/upgrade.py:822-854` (no-migrations stamp pass), `:2196-2207` (migration path), `:1680-1720` (`_empty_full_plan`), `:1760-1905` (plan JSON), options at `:1988`.
- This is a CLI selection change, not a migration: no Migration Ledger entry, no `order_manifest.txt` change.
- Open PRs #7094 and #7116 also edit `upgrade.py`; keep edits local to worktree handling to limit conflicts.
- Keep functions ≤ 15 complexity; the `upgrade` command function is already large — add parameters and delegate to helpers, do not inline logic.
- Do not change `--no-worktrees` semantics (it skips the worktree pass entirely).

## Branch Strategy

- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Run `spec-kitty agent action implement WP05 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the printed workspace.

## Subtasks & Detailed Guidance

### Subtask T018 – `upgrade/worktree_selection.py`

- `class SelectionMode(StrEnum)`: `NONE`, `NAMED`, `ALL`.
- `@dataclass(frozen=True) class WorktreeSelection: mode; named: tuple[Path, ...] = ()` with constructors `none()`, `all()`, `named_paths(paths)`, and `to_json()` → `{"mode": ..., "named": [str, ...]}`.
- `class DispositionAction(StrEnum)`: `SKIP_MISSION`, `SKIP_NOT_SELECTED`, `UPGRADE`.
- `@dataclass(frozen=True) class WorktreeDisposition: path; branch: str | None; action` + `to_json()`.
- `worktree_dispositions(worktrees_dir, selection) -> list[WorktreeDisposition]` in name order; Mission/detached → `SKIP_MISSION` (move the `_is_integrating_worktree` predicate here and keep a thin alias in the runner if other modules import it — grep first), others → `UPGRADE` iff mode `ALL` or resolved path ∈ resolved `named`.
- `validate_named(project_path, named) -> list[Path]` raising `UnknownWorktreeError(path)` when a path does not resolve to a direct child directory of `<project>/.worktrees/`. Accept absolute and project-relative paths.

### Subtask T019 – Runner threading

- Add `worktree_selection: WorktreeSelection | None = None` to `MigrationRunner.upgrade`, `upgrade_worktrees_only` and `_upgrade_worktrees`; `None` means `WorktreeSelection.none()` (safe default for every programmatic caller).
- `_upgrade_worktrees` iterates `[d.path for d in worktree_dispositions(...) if d.action is UPGRADE]` instead of `_worktrees_to_upgrade`, and returns the dispositions in its result dict (`"worktree_dispositions"`) so the CLI can print them.
- Update the docstrings that describe the old default (`_upgrade_worktrees`, module comments around #2385).

### Subtask T020 – CLI flags and refusals

- Options: `--include-worktree` (`list[Path] | None`, repeatable, help "Upgrade and commit into this non-Mission worktree (repeatable)") and `--all-worktrees` (help "Upgrade and commit into every non-Mission worktree under .worktrees/").
- Build the selection in a helper `_worktree_selection_from_options(project_path, include, all_worktrees, no_worktrees)`; refusals print one line and `raise typer.Exit(2)` before any migration runs (also for `--plan-json`, which should return a blocked plan with the code in `diagnostics`).
- Thread the selection to both runner call sites (`:844` and `:2202`).

### Subtask T021 – Dispositions in normal output

- Helper `_render_worktree_dispositions(dispositions)` printing the `Worktrees:` block (contract). For `SKIP_NOT_SELECTED` include the exact opt-in hint `use --include-worktree <rel path> or --all-worktrees`.
- Print it in the dry-run preview (in or right after `_show_migration_plan_and_confirm`, before the confirm prompt, so the operator sees it before agreeing) and after the run (both no-migrations and migrations paths). Compute dispositions once via `worktree_dispositions` for the preview (no writes).
- Skip the block when `.worktrees/` is absent or empty; skip it entirely with `--no-worktrees` but print one line `Worktrees: skipped (--no-worktrees)`.

### Subtask T022 – `--plan-json`

- `intent.worktree_selection`, top-level `worktree_dispositions`, and `commit_policy.worktrees_enabled = include_worktrees and any(d.action is UPGRADE)`. Update `_empty_full_plan` to carry the same keys (empty list / mode). Check `tests/upgrade/preview_support/` and `tests/upgrade/test_upgrade_cli_contract.py` for schema assertions and extend them, keeping `schema_version: 1` only if added keys are additive (they are).

### Subtask T023 – Tests

- New `tests/upgrade/test_upgrade_worktree_selection.py` (red-first: write it before changing behaviour and confirm it fails on the base):
  - default: two `wip/` worktrees + one Mission lane; `upgrade --yes` (CliRunner) → 0 new commits on `wip/*`, files untouched; output names all three with dispositions.
  - `--include-worktree .worktrees/a` → only `a` committed.
  - `--all-worktrees` → both committed (old behaviour).
  - `--dry-run` normal output lists every worktree; nothing written.
  - unknown path → exit 2, nothing written (assert metadata version of main unchanged).
  - `--no-worktrees --all-worktrees` → exit 2.
  - `--plan-json` has the new keys and `worktrees_enabled` false by default, true with `--all-worktrees`.
  - unit tests for `worktree_dispositions` and `validate_named` (relative, absolute, outside, nested path, missing).
- Existing tests that relied on the old default: pass `worktree_selection=WorktreeSelection.all()` (runner-level) or `--all-worktrees` (CLI-level) **explicitly**, keeping their assertions. Expected files: `tests/upgrade/test_upgrade_worktree_commit.py`, `test_upgrade_integrating_worktrees.py`, `test_issue_4972_idempotent_worktree_metadata.py`, `test_worktree_stamp_guard.py`, `test_exclude_worktrees_migration.py`. If others fail (grep `include_worktrees`/`upgrade_worktrees_only` in `tests/` incl. `tests/specify_cli/upgrade/`), fix them the same way and note each with a one-line rationale in the WP history (out-of-map edit).

## Test Strategy

```bash
uv run --frozen pytest tests/upgrade -q -p no:cacheprovider
uv run --frozen pytest tests/specify_cli/upgrade -q   # out of the CI matrix: must be run locally
uv run --frozen ruff check src/specify_cli/upgrade/ src/specify_cli/cli/commands/upgrade.py tests/upgrade/test_upgrade_worktree_selection.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/upgrade/worktree_selection.py src/specify_cli/upgrade/runner.py src/specify_cli/cli/commands/upgrade.py tests/upgrade/test_upgrade_worktree_selection.py
uv run --frozen mypy src/specify_cli/upgrade/worktree_selection.py src/specify_cli/upgrade/runner.py src/specify_cli/cli/commands/upgrade.py
```

Classify any red per CLAUDE.md "baseline-red gotcha" (e.g. #7093 is red on pristine main) before treating it as yours.

## Risks & Mitigations

- Hidden programmatic callers of the runner (e.g. `init`) silently changing behaviour: grep every `MigrationRunner(` call; the new default `NONE` is the intended safe behaviour, but note each caller in the WP history.
- Preview drift vs execution: both use `worktree_dispositions`.

## Review Guidance

- Default writes nothing into non-Mission worktrees (read the CliRunner test).
- Refusals happen before any write.
- Existing tests opt in explicitly rather than having assertions loosened.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP05 --note "..."`.
