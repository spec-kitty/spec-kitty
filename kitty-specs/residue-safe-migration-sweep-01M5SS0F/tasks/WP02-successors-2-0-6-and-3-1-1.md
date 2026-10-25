---
work_package_id: WP02
title: 'Successor plumbing: selection-view settled check and residue walk'
dependencies:
- WP01
requirement_refs:
- FR-007
- C-002
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-residue-safe-migration-sweep-01M5SS0F
base_commit: 1c6fc2f6513dc6fac6c1e3ddde7602151622bc5f
created_at: '2026-10-25T17:25:51.533275+00:00'
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Supersession
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-10-25T16:40:00Z'
  actor: claude
  action: 'Re-cut after the post-tasks adversarial review: plumbing only; the successors moved to WP03'
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/specify_cli/upgrade/migrations/_residue_successor.py
- tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/migrations/_residue_successor.py
- tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Successor plumbing: selection-view settled check and residue walk

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

- A public `settled_in_selection_view(project_path, migration_id) -> bool` in `src/specify_cli/upgrade/registry.py` uses **the same predicate** as `MigrationRegistry.get_applicable`: `migration_settled(ledger, m) or m.migration_id in _pending_adoption_ids(ledger, <all declared>, project_path)`. Refactor `get_applicable` to call the same internal expression so the two cannot drift (FR-007 groundwork).
- A private, non-migration module `src/specify_cli/upgrade/migrations/_residue_successor.py` gives the four successors (WP03) one copy of:
  - `predecessor_settled(project_path, predecessor_id) -> bool`, which delegates to the registry helper;
  - `partition_kitty_specs(kitty_specs: Path, checkout_root: Path) -> tuple[list[Path], list[Path]]`, which walks children once and returns `(missions, residue)` via WP01's `is_kitty_specs_residue(..., repo_root=checkout_root, tracked=<computed once>)`. The parameter is named `kitty_specs`, a tainted name the walker gate sees (see WP03);
  - `residue_warnings(residue: list[Path], project_path: Path) -> list[str]`, built from WP01's `residue_notice(...)` with the **project-relative path**.
- **No migration is registered in this WP**, so no registry gate changes state: order manifest, dead modules and walker inventory all stay as they are.
- Requirement refs: FR-007 (groundwork), C-002.

## Context & Constraints

- Read `src/specify_cli/upgrade/registry.py` (`get_applicable`, `migration_settled`, `_pending_adoption_ids`, `_within_target`) and the precedent `m_4_0_0rc6_charter_pack_cutover._is_first_application`.
- `ledger_adoption` migrations are never target-capped, so passing every declared migration to `_pending_adoption_ids` is equivalent to what `get_applicable` passes (verified by the post-tasks review).
- Auto-discovery skips modules without the `m_` prefix, so a private `_residue_successor.py` is never imported as a migration (verified by probe). Register nothing in it.
- `registry` must not import migration modules at import time, so keep any new import lazy.
- `get_by_id(id)` returns the `SupersededMigration` substitute for a superseded id. The substitute has the same id, so `migration_settled` still matches the predecessor's ledger records.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep
- Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T006 – `settled_in_selection_view` in the registry

1. Extract the expression `migration_settled(ledger, migration) or migration.migration_id in adopting` from `get_applicable` into a private helper used by both. The public function builds `ledger` and `adopting` inside `legacy_upgrade_scope(path)`, exactly as `get_applicable` does.
2. An unknown migration id returns False ("never recorded").
3. `get_applicable`'s behaviour stays byte-for-byte: the existing registry tests pass unchanged.

### Subtask T007 – `_residue_successor.py`

1. `predecessor_settled(project_path: Path, predecessor_id: str) -> bool`.
2. `partition_kitty_specs(kitty_specs: Path, checkout_root: Path)` returns sorted child directories. Compute `tracked = tracked_mission_paths(checkout_root)` once and pass it to `is_kitty_specs_residue`. A missing `kitty_specs` returns `([], [])`.
3. `residue_warnings(residue, project_path)` returns one notice per folder, naming `folder.relative_to(project_path).as_posix()`. This includes `.worktrees/<wt>/kitty-specs/<slug>` folders. The text comes only from WP01's `residue_notice`.
4. Every function carries a docstring citing #6669 and has complexity ≤ 15.

### Subtask T008 – Tests

- **File**: `tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py` (uses `git_repo`).
- **Cases**:
  1. **Equivalence with selection.** For each ledger state (no record, `success`, `skipped`, `failed`), and for a pre-ledger project pending adoption at versions `2.0.6` and `3.2.0`, `settled_in_selection_view(p, id)` equals `migration not in get_applicable(..., project_path=p)` for a representative registered migration.
  2. An unknown id returns False.
  3. `partition_kitty_specs` in a tracked project splits a real Mission from a residue folder (an untracked `tasks/WP01.md`). In a non-git project the tasks-only folder lands in `missions` (fallback mode).
  4. `residue_warnings` names project-relative paths, including a `.worktrees/wt1/kitty-specs/x` folder, and its text equals `residue_notice` exactly.
  5. Importing the module registers no migration: compare a registry snapshot before and after the import.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py tests/upgrade/test_order_manifest.py tests/upgrade/test_auto_discovery.py -q
uv run --frozen pytest $(git ls-files 'tests/upgrade/test_registry*.py' 'tests/specify_cli/upgrade/test_registry*.py') -q
uv run --frozen mypy --strict src/specify_cli/upgrade/registry.py src/specify_cli/upgrade/migrations/_residue_successor.py
```

## Risks & Mitigations

- **Behaviour drift in `get_applicable`**: covered by the equivalence test, with the existing registry tests left unchanged.

## Review Guidance

- Confirm there is one shared predicate, nothing is registered in the private module, and imports are lazy.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "..."`, `spec-kitty agent tasks move-task WP02 --to <status>`, `spec-kitty agent tasks status`.
