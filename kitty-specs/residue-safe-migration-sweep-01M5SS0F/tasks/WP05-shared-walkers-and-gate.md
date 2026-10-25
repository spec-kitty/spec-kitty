---
work_package_id: WP05
title: Shared migration walkers skip residue
dependencies:
- WP01
requirement_refs:
- FR-003
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-residue-safe-migration-sweep-01M5SS0F
base_commit: ebcf7cb199a8d9dae3087080e834ea78b245d424
created_at: '2026-10-25T17:27:14.251918+00:00'
subtasks:
- T019
- T020
- T021
phase: Phase 1 - Foundation
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-10-25T16:40:00Z'
  actor: claude
  action: 'Re-cut after the post-tasks adversarial review: walkers only; the gate reclassification moved to WP03'
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/specify_cli/migration/test_residue_shared_walkers_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/migration/backfill_runtime_state.py
- src/specify_cli/migration/runner.py
- tests/specify_cli/migration/test_residue_shared_walkers_6669.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Shared migration walkers skip residue

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

- Two shared walkers skip residue folders. The decision comes only from WP01's `is_kitty_specs_residue`, with `tracked` computed once per walk (FR-003):
  - `migration/backfill_runtime_state._mission_dirs`, which backs `migrate backfill-runtime-state` and `migrate backfill-wp-status`;
  - `migration/runner._move_derived_files`, the 3.0.0 canonical-context derived-file move.
- A skipped folder is reported without naming it a second time during upgrade. Choose one approach and state it in the docstring:
  - the per-Mission result carries a residue skip reason that uses `RESIDUE_NOTICE`, so WP04 collapses it; or
  - the skip is logged only.

  JSON shapes stay additive-only.
- Real Missions are processed exactly as before.
- This WP edits no gate file. WP03 reclassifies the walker inventory after this WP lands, so its `_FILTERS` labels are true.
- Requirement refs: FR-003.

## Context & Constraints

- WP01 delivers the rule. Read the existing result dataclasses in `backfill_runtime_state.py` before deciding how a skip is reported.
- `tests/architectural/test_json_contract_enumeration.py` must stay green.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep
- Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP05 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T019 – `backfill_runtime_state._mission_dirs`

- Filter with `is_kitty_specs_residue(d, repo_root=repo_root, tracked=tracked)`. Keep the walker's variable name; the gate already sees it.
- Find the covering suites with `git grep -l "backfill_runtime_state\|backfill_wp_status" tests`, and keep them green.

### Subtask T020 – `migration/runner._move_derived_files`

- Apply the same filter, with `tracked` computed once.

### Subtask T021 – Behaviour tests

- **File**: `tests/specify_cli/migration/test_residue_shared_walkers_6669.py` (uses `git_repo`).
- For each walker, set up a tracked project with one real Mission and two residue folders: one holding only `status.json`, one holding only `tasks/`. The residue folders stay untouched and the skip is reported as chosen above; the Mission is processed.
- Add a non-git control: there, the same tasks-only folder is processed (fallback mode).

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/migration -n 6 --dist loadfile -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_backfill_runtime_state_cli.py tests/integration/test_migration_backfill.py tests/architectural/test_json_contract_enumeration.py -q
uv run --frozen mypy --strict src/specify_cli/migration/backfill_runtime_state.py src/specify_cli/migration/runner.py
```

## Risks & Mitigations

- **CLI JSON shape changes**: keep them additive-only; the contract enumeration test guards this.

## Review Guidance

- Confirm the skip is reported, not silent, and that no folder is named twice during upgrade.

## Progress & Status

- `spec-kitty agent tasks add-history WP05 --note "..."`, `spec-kitty agent tasks move-task WP05 --to <status>`, `spec-kitty agent tasks status`.
