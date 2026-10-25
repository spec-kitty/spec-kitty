---
work_package_id: WP01
title: Successor promotion migration
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
- C-005
- C-006
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6629-upgrade-seeded-activation-provenance
merge_target_branch: issue-6629-upgrade-seeded-activation-provenance
branch_strategy: Planning artifacts for this mission were generated on issue-6629-upgrade-seeded-activation-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6629-upgrade-seeded-activation-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core fix
history:
- at: '2026-10-25T17:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
- tests/specify_cli/upgrade/test_m_4_0_0rc8_promote_interview_selections.py
- tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/upgrade/supersession.py
- tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py
- tests/specify_cli/upgrade/test_m_4_0_0rc8_promote_interview_selections.py
- src/charter/activation/api.py
- src/charter/activation/activation_engine.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/architectural/test_no_dead_modules.py
- tests/architectural/test_deny_list_survives_upgrade.py
- tests/specify_cli/upgrade/test_requires_git_repository_audit.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Successor promotion migration

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item, and record each change with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- A pre-activation-ledger project whose interview selected only artifacts already in force ends the upgrade with **no** `activated_<kind>` key for any of the 8 promoted kinds. `charter synthesize --dry-run --json` then reports `fresh_project_seed_dry_run` (FR-001, FR-002, SC-001).
- An answers-only id is still appended to a **present** list, in identity space, through the activation ledger seam. `config.yaml` never gains an activation key on a ledger project (FR-003, FR-004).
- `unify_charter_activation_promote_answers` is registered as a `SupersededMigration`, and its module stays byte-identical (FR-005, C-001).
- Deactivated ids are neither seeded nor appended, and an unresolved id is warned about (FR-006).
- On a project with selections, the first run records `success` and a later upgrade does not select the migration, also after an operator `--only` narrowing (FR-007, NFR-001).
- A present list that is set-equal to the full in-force set, where the interview selected only part of it, gets a non-mutating warning that names the narrowing commands (FR-008).
- The bundle hash is re-stamped after a write (FR-009), and a dry run previews and writes nothing (FR-010).

## Context & Constraints

- Spec: `kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/spec.md`. Plan, including its **Design** section: `.../plan.md`.
- **Never edit `src/specify_cli/upgrade/migrations/m_unify_charter_activation.py`** (DIRECTIVE_044). Do not import its private helpers either: resolve through public seams.
- Supersession mechanism: `src/specify_cli/upgrade/supersession.py` (#6589, ADR 2026-10-17-1 Amendment 2026-10-25).
- Activation writes go through `charter.activation.pack_manager.resolve_activation_write_target` and `charter.activation.activation_engine.promote_activations` only. The model to follow is `src/specify_cli/cli/commands/charter/interview.py::_promote_interview_selections`.
- Every `BaseMigration` public method runs inside `legacy_upgrade_scope`. After `4.0.0rc8_activation_ledger` has created the activation ledger, the resolver names it (LEDGER). On a project with no keys anywhere there is no ledger, and the resolver names the legacy target; then no key is present, so nothing is written.
- Complexity ≤ 15 per function. Repeated literals become module constants. No new `# noqa` / `# type: ignore` unless individually justified.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-6629-upgrade-seeded-activation-provenance; completed changes must merge back into issue-6629-upgrade-seeded-activation-provenance.
- **Planning base branch**: issue-6629-upgrade-seeded-activation-provenance
- **Merge target branch**: issue-6629-upgrade-seeded-activation-provenance
- This is a `single_branch` mission: the WP runs in the repository root checkout. No lane worktree is created.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude --mission upgrade-keeps-absent-activation-absent-01M5T0YE
```

## Subtasks

### T001 — Pin the end-to-end red-first reproduction

- File: `tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py`. It already exists in the working tree and is red on main: the upgrade leaves explicit directive and paradigm lists.
- It builds a git project and records `ProjectMetadata(version="3.2.0rc30")`. The version must stay below the shipped promotion's 3.2.6rc1, because a higher stamp lets the ledger-adoption backfill settle the shipped promotion without running it, and the reproduction then never witnesses the bug.
- It writes `answers.yaml` with built-in-only `selected_directives` and `selected_paradigms`, and runs `MigrationRunner(project).upgrade("4.0.0rc8")`.
- It asserts four things:
  - no allow list exists for any of the 8 kinds;
  - `_build_synthesis_request` gives `selected_directives == []`;
  - `_catalog_is_established` is False;
  - `charter synthesize --dry-run --json` returns `mode == "fresh_project_seed_dry_run"`.
- Record the red run (command plus failing assertion) in the WP history before touching product code. Keep the `@pytest.mark.regression` mark only while the test is red. Once it is green, drop the mark: the test stays as an integration pin of the behaviour, not a P0 repro (ADR 2026-07-17-1).
- Add a second scenario to the same file: upgrade, then `charter activate directive <id> --only` (or write the narrowed list through `seed_activation_ledger`), then upgrade again. The narrowed list must be unchanged (FR-007).

### T002 — Write the successor migration module

- File: `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py`.
- Class `PromoteInterviewSelectionsMigration(BaseMigration)`, registered with `@MigrationRegistry.register`. Attributes:
  - `migration_id = "4.0.0rc8_promote_interview_selections"`
  - `target_version = "4.0.0rc8"`
  - `runs_on_worktrees = False`
  - `description` stating that it promotes answers-only interview selections into present activation lists and never writes an absent key.
- Module docstring: explain #6629, the supersession, the "absent key is never written" rule and why it is zero-drop (absence puts every available artifact in force, so a resolved id is in force already or names no available artifact), and the settle-on-first-run rule.
- Kinds: the same 8 as the shipped migration (directive, tactic, styleguide, toolguide, paradigm, procedure, agent_profile, mission_step_contract). Define them as a module constant.
- `detect(project)`: True when `.kittify/charter/interview/answers.yaml` holds a non-empty `selected_<plural>` list for any of those kinds. Read it with a safe YAML load, and treat a malformed file as no selections. It reads nothing else.
- `can_apply`: `(True, "")` when detect is True, otherwise `(False, "no interview selections to promote")`.
- `apply(project, dry_run=False)`:
  1. Resolve the offering root (`charter.activation.catalog.resolve_offering_root`). On failure, return a failed `MigrationResult` with the error.
  2. For each kind, resolve every answers id with `charter.activation.kind_vocabulary.resolve_selected_id_to_stem(kind, raw, offering_root=...)`. `UnrepresentableDirectiveIdError` or `None` adds the id to the unresolved list.
  3. `target_path, data, save = resolve_activation_write_target(project)`.
  4. For each kind whose `data.get(f"activated_{plural}")` is not `None`, normalise each list entry to a stem with the same resolver (keep the raw entry when it does not resolve). The promotion is the answer stems that are not in that set, in answers order with no duplicates. Skip absent kinds.
  5. Seeded-list hint (T005).
  6. When `dry_run` is set, return the preview (T005) without writing.
  7. If there are promotions, call `promote_activations(promotions, config_path=target_path, config_data=data, save=save, effective_sets={}, repo_root=project)`. If `outcome.committed` is non-empty, call `charter.activation.api.restamp_bundle_hash(project)`.
  8. `changes_made`: `Promoted [...] into activated_<plural>` per committed plan, or `"No interview selections to promote (every selection is already in force)"`. Warnings: the plan warnings, `outcome.left_absent_messages()`, `skipped_denied` (`"Kept deactivated: ..."`), the unresolved ids, and the hints.
  9. Always `success=True` when no exception occurred, so the runner records `success` and the migration settles.
- Keep each function at complexity ≤ 15: split resolution, promotion computing, hinting and result building into helpers.

### T003 — Register the supersession and the manifest entry

- In `supersession.py`, add `"unify_charter_activation_promote_answers": "4.0.0rc8_promote_interview_selections"`, with a two-line comment citing #6629: "seeded an absent key with the whole in-force set; the successor never writes an absent key".
- In `order_manifest.txt`, insert `4.0.0rc8_promote_interview_selections  # tie: shares target_version 4.0.0rc8 with 4.0.0rc8_activation_ledger; runs after it so it promotes into the activation ledger the move created` directly after the `4.0.0rc8_activation_ledger` line.
- Run `tests/architectural/test_migration_order_manifest.py` and `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`. The latter has `test_every_supersession_entry_names_registered_manifest_migrations`, which checks the new entry.

### T004 — Focused unit tests of the successor

File: `tests/specify_cli/upgrade/test_m_4_0_0rc8_promote_interview_selections.py`. Mark it `unit`/`fast` where no git or runner is needed. Use `tests._factories.activation_ledger.seed_activation_ledger` for ledger projects. Cover:

- `detect` is False with no answers, False with empty selections, False with malformed YAML, and True with one selection.
- Absent key with every id in force: no write on the ledger or on `config.yaml`, and `success` is True (FR-001).
- Present list (ledger) missing one answers id: the ledger gains exactly that id, and `config.yaml` is unchanged (FR-003, FR-004).
- Present list that spells an artifact by its declared id (`DIRECTIVE_024`) while the answers name its stem: nothing is appended (#6423).
- A deactivated answers id: not appended, the deny list is byte-identical, and the result carries a "Kept deactivated" warning (FR-006).
- An unresolvable id: a warning naming it (FR-006).
- A direct re-apply after a promotion changes 0 bytes (NFR-001).
- The registered `unify_charter_activation_promote_answers` is a `SupersededMigration` naming the successor, and its `content_hash` equals the shipped class's (FR-005).
- The bundle restamp: after a promotion on a project with a synthesis manifest, the stamp equals the recomputed hash. If building a manifest is heavy, assert instead that `restamp_bundle_hash` is called once, with a narrow monkeypatch of the module attribute (FR-009).

### T005 — Seeded-list hint and dry-run preview

- **Hint**: candidate kinds are those whose list is present, whose answer stems are non-empty, and whose list has more entries than the answer stems.
  - For the candidates, call `charter.activation.effective_set.resolve_effective_sets(project, [keys])` once.
  - For each resolved `EffectiveSet`, a list whose stem set equals `set(entry.ids)` while the answer stems are a strict subset gets the warning:
    `"activated_<plural> lists every available <token> (<n>), which an earlier upgrade seeded; your interview selected <m>. To keep only those, run `spec-kitty charter interview --narrow-activation` or `spec-kitty charter activate <token> <id> --only`; `charter synthesize` then asks for companion tactics only for what you keep."`
  - Hoist the template to a constant.
  - No write, ever. Test it: on a seeded fixture the warning is present, and on an operator-chosen list (not set-equal) it is absent.
- **Dry run**: `changes_made = ["dry-run: would promote {key: [ids]}"]` or `["dry-run: nothing would be promoted"]`, with the same warnings. Test that the files are unchanged afterwards.

## Post-tasks squad folds (planner-priti, 2026-10-25)

- **Activation seam gate.** `test_runtime_charter_activation_boundary.py` is shrink-only. Import every `charter.activation` symbol through `charter.activation.api`, and add identity re-exports for any that are missing: `promote_activations`, `PromotionOutcome`, `resolve_offering_root`, `resolve_effective_sets`, `resolve_selected_id_to_stem`, `UnrepresentableDirectiveIdError`. Table each in `test_charter_activation_api_reexport.py`, and add `PromotionOutcome` to the engine's `__all__`.
- **Dead-module gate.** List the new module in `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`.
- **Deny gate.** The `BUILDERS`/`ORDER_EXEMPT` move belongs here, not in WP02: WP01 is what turns the gate red. The builder also selects the fixture-denied `DIRECTIVE_003`.
- **Deactivated ids.** Filter them out of the promotion before calling `promote_activations`, using `load_activation_ledger(...).deny_for(kind)` in stem space. A deactivated-only selection then writes nothing and does not restamp. Word the warning with `PromotionOutcome.skipped_denied_messages()`.
- **Restamp condition.** Restamp only when a committed plan activated something.
- **Git-repository audit.** The populated fixture of `test_requires_git_repository_audit.py` gains `answers.yaml` and a present list, so the audit reaches the successor's write path.
- **Limit kept deliberately.** Org-pack and project-layer interview ids are not resolved (parity with the shipped migration). The module docstring records this.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py tests/specify_cli/upgrade/test_m_4_0_0rc8_promote_interview_selections.py tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py tests/architectural/test_migration_order_manifest.py tests/architectural/test_runtime_charter_activation_boundary.py tests/architectural/test_no_dead_modules.py tests/architectural/test_deny_list_survives_upgrade.py tests/architectural/test_charter_activation_api_reexport.py tests/specify_cli/upgrade/test_requires_git_repository_audit.py -q
uv run --frozen ruff check <changed files>; uv run --frozen ruff format --check --force-exclude <changed files>; uv run --frozen mypy <changed src files>
```

## Definition of Done

- The T001 reproduction is red before the fix and green after it. Both runs are recorded in the WP history.
- All T004/T005 tests pass. ruff, ruff format and mypy are clean on the changed files, and complexity is ≤ 15.
- `m_unify_charter_activation.py` is byte-identical to `origin/main` (`git diff origin/main -- <path>` is empty).

## Risks

- **`resolve_effective_sets` cost.** It builds the doctrine service. Call it only for hint candidates, and at most once.
- **`promote_activations` with `effective_sets={}`.** This is correct only for present keys. Never include an absent key in `promotions`.
- **A malformed activation ledger.** `resolve_activation_write_target` raises `ActiveCharterConfigError`. Let it surface as a failed result (an error string), never a silent pass.

## Reviewer Guidance

- Verify that no code path writes an absent key, and that `detect` never returns False on a project with selections.
- Verify that the shipped module is untouched and that the supersession entry and manifest line are present.
- Re-run the reproduction against the pre-fix `supersession.py` (`git stash` the change) to confirm it goes red.
