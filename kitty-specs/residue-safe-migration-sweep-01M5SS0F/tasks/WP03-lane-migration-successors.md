---
work_package_id: WP03
title: Lane-migration successors (0.9.0 / 0.9.1)
dependencies:
- WP02
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 2 - Supersession
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py
- src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py
- tests/specify_cli/upgrade/test_residue_safe_lane_successors_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py
- src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py
- tests/specify_cli/upgrade/test_residue_safe_lane_successors_6669.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Lane-migration successors (0.9.0 / 0.9.1)

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

- `0.9.0_frontmatter_only_lanes` and `0.9.1_complete_migration` are superseded by:
  - `0.9.0_residue_safe_frontmatter_only_lanes`
  - `0.9.1_residue_safe_complete_migration`
- Each successor subclasses the shipped class. No residue folder is moved, rewritten or frontmatter-normalised, whether it sits under the main `kitty-specs/` or under `.worktrees/*/kitty-specs/`. Real legacy Missions are migrated exactly as before (FR-004, FR-005).
- Each successor sits immediately after its predecessor in `order_manifest.txt` with the same `target_version` and a `# tie:` annotation (FR-006). Its `detect()` is False when the predecessor is settled in the selection view, via WP02's `predecessor_settled` (FR-007).
- The worktree clean-up part of 0.9.1 (agent command dirs and `.kittify/scripts` in `.worktrees/*`) is unchanged.
- Requirement refs: FR-004, FR-005, FR-006, FR-007.

## Context & Constraints

- Prerequisite: WP02, which provides `_residue_successor.py`, `settled_in_selection_view`, the supersession table and the parametrized supersession pins.
- Shipped modules (frozen, never edit):
  - `src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py`: class `FrontmatterOnlyLanesMigration`, per-folder predicate `_is_legacy_format`, used by `detect` and `_find_features_to_migrate`.
  - `src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py`: class `CompleteLaneMigration`, id `0.9.1_complete_migration`. Its per-folder predicate `_has_remaining_lane_dirs` is used by `detect` part 1 and `_find_features_with_lanes`. `_normalize_all_frontmatter` collects every `*.md` under `kitty-specs/` (and the worktree specs) with `rglob` and writes through the shared `specify_cli.frontmatter.normalize_file`.
- **Out-of-map edits**: the 2 lines in `src/specify_cli/upgrade/supersession.py` and the 2 lines in `order_manifest.txt` belong to WP02's files. This WP runs after WP02 in the same lane. Record each edit with a one-line rationale via `spec-kitty agent tasks add-history WP03 --note "out-of-map: supersession + manifest entries for the 0.9.x successors"`.
- The residue decision is `is_kitty_specs_residue(folder, repo_root=<checkout root>)`. For a `.worktrees/<wt>/kitty-specs/<slug>` folder the checkout root is `<wt>` (the default, `path.parent.parent`).

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

```bash
spec-kitty agent action implement WP03 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T012 – `0.9.0_residue_safe_frontmatter_only_lanes`

- **Steps**:
  1. New module. Write `@MigrationRegistry.register class ResidueSafeFrontmatterOnlyLanesMigration(FrontmatterOnlyLanesMigration)` with `migration_id = "0.9.0_residue_safe_frontmatter_only_lanes"`, `target_version = "0.9.0"` and its own `description`.
  2. Override `_is_legacy_format(self, feature_path)`: return False when `is_kitty_specs_residue(feature_path)`, else `super()._is_legacy_format(feature_path)`.
  3. Override `detect(project_path)`: return False when `predecessor_settled(project_path, "0.9.0_frontmatter_only_lanes")`, else `super().detect(project_path)`.
  4. Override `apply()` to call `super().apply()` and append residue warnings. Collect the residue folders seen; a small walk using `_residue_successor.non_residue_dirs` over main and worktree specs is fine.
  5. Confirm that subclass registration does not register the parent twice, and that the parent is still replaced by its `SupersededMigration` substitute in the registry.

### Subtask T013 – `0.9.1_residue_safe_complete_migration`

- **Steps**:
  1. New module. `ResidueSafeCompleteLaneMigration(CompleteLaneMigration)`, `migration_id = "0.9.1_residue_safe_complete_migration"`, `target_version = "0.9.1"`.
  2. Override `_has_remaining_lane_dirs`, which covers `detect` part 1 and `_find_features_with_lanes`.
  3. Override `_normalize_all_frontmatter`. Re-implement only the file collection so that `*.md` files under a residue folder are excluded, then normalise through the same shared `normalize_file` (and the same dry-run comparison), with the same change and warning strings. Keep complexity ≤ 15 by extracting helpers. No new writer: the write stays in `specify_cli.frontmatter.normalize_file`.
  4. Override `detect` with the settled gate, then `super().detect()`. Worktree clean-up stays inherited.
  5. Add residue warnings in `apply()`, as for 0.9.0.
- **Notes**: list every method of `CompleteLaneMigration` that walks `kitty-specs/`. The T015 AST check pins this.

### Subtask T014 – Supersession entries and manifest ties (out-of-map)

- `SUPERSEDED_MIGRATIONS["0.9.0_frontmatter_only_lanes"] = "0.9.0_residue_safe_frontmatter_only_lanes"` and `SUPERSEDED_MIGRATIONS["0.9.1_complete_migration"] = "0.9.1_residue_safe_complete_migration"`.
- In `order_manifest.txt`, add each successor right after its predecessor (lines 30–31 today) with a `# tie:` comment citing #6669.
- Run `tests/architectural/test_migration_order_manifest.py` and WP02's parametrized supersession pins.

### Subtask T015 – Registry-driven tests

- **File**: `tests/specify_cli/upgrade/test_residue_safe_lane_successors_6669.py` (`git_repo`).
- **Cases**:
  1. Resolve each successor via `MigrationRegistry.get_by_id`. In a tracked project, a residue folder holding an untracked `tasks/doing/WP01-x.md` is byte-identical after `apply()`, both under main `kitty-specs/` and under a `.worktrees/wt1/kitty-specs/` copy.
  2. A real legacy Mission (committed `spec.md` plus `tasks/doing/WP01-x.md`) is migrated: the file moves to `tasks/WP01-x.md` with `lane` set, exactly as the shipped class does. Prove parity by running the shipped class via a direct import on a twin fixture and comparing trees; this is the only allowed direct import, used as the oracle.
  3. 0.9.1 frontmatter normalisation skips residue `*.md` but normalises a real Mission's WP file.
  4. Settled gate: with a ledger `success` for the predecessor, `detect()` is False.
  5. AST pin: every method of the shipped class that references `"kitty-specs"` or calls `iterdir`/`rglob` on a kitty-specs path is either overridden in the successor or only reachable through an overridden predicate. Document the mapping in the test.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/upgrade/test_residue_safe_lane_successors_6669.py tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py tests/architectural/test_migration_order_manifest.py -q
uv run --frozen pytest tests/upgrade/migrations -q -k "0_9 or lane"   # existing 0.9.x tests stay green (they import the shipped classes directly)
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'   # empty
uv run --frozen mypy --strict src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py
```

## Risks & Mitigations

- **A missed walker** in the 575-line 0.9.1 module: the AST pin.
- **`noqa: C901` in the frozen methods**: the successor must not copy it. Extract helpers instead.
- **Frontmatter write gates** (`tests/specify_cli/test_locked_frontmatter_writers.py`): writes still go through `normalize_file`, so no new site is expected. Run the gate.

## Review Guidance

- Confirm the residue decision is only `is_kitty_specs_residue`, that no frozen file changed, and that worktree clean-up is unchanged.
- Confirm the out-of-map edits are recorded in history.

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "..."`, `spec-kitty agent tasks move-task WP03 --to <status>`, `spec-kitty agent tasks status`.
