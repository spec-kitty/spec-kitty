---
work_package_id: WP04
title: Collapse residue notices in the upgrade runner
dependencies:
- WP01
requirement_refs:
- FR-008
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
phase: Phase 3 - Reporting
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/runner.py
create_intent:
- tests/upgrade/test_residue_notice_collapse.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/runner.py
- tests/upgrade/test_residue_notice_collapse.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Collapse residue notices in the upgrade runner

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- In one `spec-kitty upgrade` run, every residue folder skipped by any step is named **at least once and at most once** in the run's warnings, in both human and `--json` output. Up to 5 steps can skip it: four successors plus the 3.2.0a4 normalization (FR-008; DM 01M5SVE8QC28KRAZM25PR2N4PT: "runner collapses").
- Only residue notices built from WP01's `RESIDUE_NOTICE` are collapsed. Every other warning passes through unchanged, in order.
- The collapse key is the **resolved folder path**: `(checkout_root / residue_notice_path(line)).resolve()`. One seen-set is shared by the main-checkout loop and the worktree loop. A main-checkout successor that walks `.worktrees/wt1/kitty-specs/x` and the worktree's own run that names `kitty-specs/x` therefore collapse to one line, while the same slug in two different checkouts stays two folders (post-tasks review M6).
- Requirement refs: FR-008.

## Context & Constraints

- `src/specify_cli/upgrade/runner.py` collects warnings:
  - main checkout: `result.warnings.extend(migration_result.warnings)` (≈ line 325);
  - worktrees: `result["warnings"].extend([f"Worktree {worktree.name}: {w}" ...])` (≈ line 766).
- The frozen 3.2.0a4 migration prefixes the slug (`f"{result.slug}: {warning}"`), and worktree lines carry `Worktree <name>: `. Do not compare whole lines: WP01's `residue_notice_path(line)` extracts the embedded project-relative path from any prefix form. The first line seen for a folder is the one kept.
- Check how the CLI renders warnings: `src/specify_cli/upgrade/outcome.py` and `cli/commands/upgrade.py`. Collapse at the single collection point, so both renderers see the collapsed list. Do not add a second rendering filter.
- Keep complexity ≤ 15 in the touched runner methods. Extract a small pure helper, e.g. `_append_warnings(target: list[str], new: list[str], seen_residue: set[str])`.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

```bash
spec-kitty agent action implement WP04 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T016 – Locate the collection path

- Map every place a `MigrationResult.warnings` list joins `UpgradeResult.warnings` or the worktree `result["warnings"]`, and where the `--json` payload reads them. Record the list in the WP history.

### Subtask T017 – Collapse exact residue notices

- Add a pure helper in `runner.py`, e.g. `_append_warnings(target: list[str], new: list[str], *, checkout_root: Path, seen: set[Path]) -> None`. It uses WP01's `residue_notice_path`; do not duplicate the notice text (Sonar S1192).
- The runner owns one `seen: set[Path]` per `upgrade` run and passes it to both the main-checkout collection (≈ line 325) and the worktree collection (≈ line 766).

### Subtask T018 – Tests

- **File**: `tests/upgrade/test_residue_notice_collapse.py`.
- **Cases**:
  1. Pure-helper tests: three identical residue notices collapse to one, two different folders keep two, and a non-residue duplicate warning is not collapsed (other warnings keep today's behaviour exactly).
  2. A runner-level test with two stub migrations registered (`MigrationRegistry.clear()` / register, as in `tests/upgrade/test_worktree_stamp_guard.py`). Each emits the same residue notice for folder X, and the `UpgradeResult.warnings` contains it once.
  3. The worktree path keeps its `Worktree <name>: ` prefix. A main-checkout notice for `.worktrees/wt1/kitty-specs/x` and a worktree-run notice for `kitty-specs/x` in `wt1` collapse to one line.
  4. The same slug `x` in the main checkout and in `wt1` (two different folders) gives two lines.
  5. The `--json` payload shows the collapsed list.

## Test Strategy

```bash
uv run --frozen pytest tests/upgrade/test_residue_notice_collapse.py tests/upgrade/test_worktree_stamp_guard.py tests/upgrade/test_upgrade_outcome_rendering.py tests/upgrade/test_upgrade_outcome_kind.py -q
uv run --frozen mypy --strict src/specify_cli/upgrade/runner.py
```

## Risks & Mitigations

- **Hiding a real warning**: collapse only exact residue notices.
- **Overlap with #6655** (worktree failure semantics in the same file): keep the diff local to warning collection, so a later merge stays trivial.

## Review Guidance

- Confirm a single collection point, no rendering-side filter, and no duplicated literal.
- Confirm that mypy strict passes on `runner.py` (one pre-existing `cast` is fine).

## Progress & Status

- `spec-kitty agent tasks add-history WP04 --note "..."`, `spec-kitty agent tasks move-task WP04 --to <status>`, `spec-kitty agent tasks status`.
