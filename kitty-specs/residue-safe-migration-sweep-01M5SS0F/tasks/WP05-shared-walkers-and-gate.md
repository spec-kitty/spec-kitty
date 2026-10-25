---
work_package_id: WP05
title: Shared walkers and an honest walker gate
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-003
- FR-013
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
- T022
phase: Phase 3 - Guardrails
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/specify_cli/migration/test_residue_shared_walkers_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/migration/backfill_runtime_state.py
- src/specify_cli/migration/runner.py
- tests/architectural/test_migration_walkers_use_mission_predicate.py
- tests/specify_cli/migration/test_residue_shared_walkers_6669.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Shared walkers and an honest walker gate

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

- `migration/backfill_runtime_state._mission_dirs` and `migration/runner._move_derived_files` skip residue folders, decided by `is_kitty_specs_residue` (FR-003). These back `migrate backfill-runtime-state`, `migrate backfill-wp-status` and the 3.0.0 canonical-context derived-file move.
- `tests/architectural/test_migration_walkers_use_mission_predicate.py` is reclassified under the new definition (FR-013):
  - `_REQUIRES_STATE` and `_REQUIRES_META` stay only where the new rule guarantees no write into residue. A folder with `meta.json` is never residue in either mode; a folder with only `status.json` or `tasks/` **is** residue in git-aware mode.
  - The four superseded walkers point at their successor, and the successors are inventoried as `_FILTERS`.
  - `_GUARDED_IDENTITY_ONLY` is removed.
  - `_PREDICATES` and `_GUARDED_SEAMS` include every new seam.
- Requirement refs: FR-003, FR-013.

## Context & Constraints

- WP01 delivers the rule. WP02 and WP03 deliver the four successors, so the gate inventory can name them.
- The walker gate (`tests/architectural/test_migration_walkers_use_mission_predicate.py`) reuses `_find_raw_walker_calls` from `test_mission_resolver_walker_gate.py`. It does not see walkers that use a module constant instead of the `"kitty-specs"` literal. Do not widen its detector in this WP (out of scope). Document the limit in the module docstring instead.
- `backfill_runtime_state._mission_dirs` feeds `backfill_runtime_state_repo` and `apply_wp_status_backfill_repo`. A residue folder must be skipped **and** reported, consistent with `cutover_repo`'s `residue=True` reporting. Decide on the smallest consistent signal (e.g. a skipped result with a residue reason) and keep the existing JSON shapes additive-only.
- `migration/runner._move_derived_files` copies `status.json` into `.kittify/derived/`. It writes outside the folder, but it must still not treat residue as a Mission.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

```bash
spec-kitty agent action implement WP05 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T019 – `backfill_runtime_state._mission_dirs`

- Filter with `is_kitty_specs_residue(d, repo_root=repo_root, tracked=tracked)`, with `tracked` computed once per walk. Report skipped residue in the per-Mission result the same way an existing "skip" is reported. Read the file's existing result dataclass first.
- Run `tests/specify_cli/migration/test_backfill_runtime_state*.py`, `tests/specify_cli/cli/commands/test_backfill_runtime_state_cli.py` and any `backfill-wp-status` tests (`git grep -l backfill_wp_status tests`).

### Subtask T020 – `migration/runner._move_derived_files`

- Skip residue the same way, with `tracked` computed once.

### Subtask T021 – Reclassify the walker inventory

- For each `_WALKER_INVENTORY` entry, re-derive the label under the new rule and write the reason in a comment where it changed.
- The superseded shipped walkers (`m_0_9_0`, `m_0_9_1`, `m_2_0_6`, `m_3_1_1`) get a label such as `_SUPERSEDED = "shipped migration registered as a no-op; its residue-aware successor walks instead"`. Add a test asserting every `_SUPERSEDED` module's migration id is a key of `SUPERSEDED_MIGRATIONS`.
- The successors' walker functions are `_FILTERS`; `test_filters_classification_is_true` must pass. Add `is_kitty_specs_residue` callers to `_GUARDED_SEAMS`.

### Subtask T022 – Behaviour tests

- **File**: `tests/specify_cli/migration/test_residue_shared_walkers_6669.py` (`git_repo`). For each walker, a tracked project with one real Mission and one residue folder (`status.json`-only, `tasks/`-only): the residue folder is untouched and reported, and the Mission is processed.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_migration_walkers_use_mission_predicate.py tests/architectural/test_mission_resolver_walker_gate.py tests/specify_cli/migration -n 6 --dist loadfile -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_backfill_runtime_state_cli.py tests/integration/test_migration_backfill.py -q
uv run --frozen mypy --strict src/specify_cli/migration/backfill_runtime_state.py src/specify_cli/migration/runner.py
```

## Risks & Mitigations

- **Changing CLI JSON shapes**: additive-only. `tests/architectural/test_json_contract_enumeration.py` must stay green.
- **Vacuous gate**: `test_filters_classification_is_true` keeps a `_FILTERS` label honest.

## Review Guidance

- Re-derive two or three labels independently and check that they hold under the new rule.
- Confirm the residue skip is reported, not silent.

## Progress & Status

- `spec-kitty agent tasks add-history WP05 --note "..."`, `spec-kitty agent tasks move-task WP05 --to <status>`, `spec-kitty agent tasks status`.
