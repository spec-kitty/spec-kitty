---
work_package_id: WP02
title: Move pins and gates, and document the supersession
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- C-003
- NFR-003
planning_base_branch: issue-6629-upgrade-seeded-activation-provenance
merge_target_branch: issue-6629-upgrade-seeded-activation-provenance
branch_strategy: Planning artifacts for this mission were generated on issue-6629-upgrade-seeded-activation-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6629-upgrade-seeded-activation-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Pins, gates and docs
history:
- at: '2026-10-25T17:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/upgrade/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/upgrade/test_unify_charter_activation_migration.py
- tests/upgrade/test_consolidate_charter_bundle_migration.py
- src/charter/activation/effective_set.py
- src/specify_cli/cli/commands/charter/interview.py
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Move pins and gates, and document the supersession

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address every item and record it with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- The architectural deny-guard gate (`tests/architectural/test_deny_list_survives_upgrade.py`) builds a fixture for the successor and exempts the superseded shipped promotion, so the gate is not vacuous.
- The shipped-migration test module asserts that the registered class is the superseded substitute. Its direct-import tests keep pinning the shipped behaviour.
- No docstring still names the shipped promotion as a live writer.
- The ADR 2026-10-17-1 supersession amendment lists the new pair, and the CHANGELOG `[Unreleased]` → `### Fixed` section carries an impact-first entry for #6629 that also names the remedy for already-seeded projects.

## Context & Constraints

- Depends on WP01: the successor id `4.0.0rc8_promote_interview_selections` and the supersession entry.
- Only edit docstrings and comments in `src/` files. Behaviour changes belong to WP01. `m_unify_charter_activation_finalize.py` is a shipped migration module: **do not edit it**. Its bytes are its `content_hash` (DIRECTIVE_044), so record any MG6 drift in the test docstrings and the ADR instead. `src/charter/activation/effective_set.py` is not a migration, so its docstring may be corrected.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-6629-upgrade-seeded-activation-provenance; completed changes must merge back into issue-6629-upgrade-seeded-activation-provenance.
- **Planning base branch**: issue-6629-upgrade-seeded-activation-provenance
- **Merge target branch**: issue-6629-upgrade-seeded-activation-provenance
- `single_branch` mission: work in the repository root checkout.

```bash
spec-kitty agent action implement WP02 --agent claude --mission upgrade-keeps-absent-activation-absent-01M5T0YE
```

## Subtasks

### T006 — Move the deny-guard gate and shipped-migration pins to the successor

- *(Moved to WP01 by the post-tasks squad: the deny gate's `BUILDERS`/`ORDER_EXEMPT` move.)* For reference, the original guidance was: in `tests/architectural/test_deny_list_survives_upgrade.py`:
  - **`BUILDERS`:** replace the `"unify_charter_activation_promote_answers"` entry with `"4.0.0rc8_promote_interview_selections": _build_answers_only_selection`. Extend that builder so its answers also select the fixture-denied directive `003-decision-documentation-requirement` (as `DIRECTIVE_003`). The gate then proves that a deactivated selection is not re-added.
  - **`ORDER_EXEMPT`:** add `"unify_charter_activation_promote_answers": "SupersededMigration: detect() is always False"`.
  - **Check the gate's assertions still hold:** `test_every_activation_touching_migration_is_built_or_exempt` (does `activation_touching_modules` see the new module?), and the manifest-index check of the order-exempt test.
- In `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py`:
  - Add one test: `MigrationRegistry.get_by_id("unify_charter_activation_promote_answers")` (after `MigrationRegistry.clear(); auto_discover_migrations()`) is a `SupersededMigration` whose `superseded_by` names the successor.
  - Add a short module-docstring note that the class is pinned through direct import because it is superseded (#6629).
  - Do not change the existing assertions: they pin the shipped class.
- In `tests/upgrade/test_consolidate_charter_bundle_migration.py`, update the docstrings or comments that call the promote migration a live seed the fold relocates. The asserts stay.

### T007 — Update docstrings that name the shipped promotion as live

- `src/specify_cli/cli/commands/charter/interview.py` (around :118-121) calls the shipped migration the live job for non-root selections; point the docstring at the successor.
- `src/charter/activation/effective_set.py`: where the docstring lists `m_unify_charter_activation` as a consumer, name the successor instead, and note that it reads the set only for the seeded-list hint.
- Grep for other prose that names `unify_charter_activation_promote_answers` as a running writer: `git grep -n "promote_answers\|m_unify_charter_activation\b" -- src docs ':!docs/changelog'`. Fix non-migration modules only. Shipped migration modules stay byte-identical.

### T008 — ADR amendment and CHANGELOG entry

- **ADR** `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`: in the Amendment 2026-10-25 supersession section, add the pair `unify_charter_activation_promote_answers` → `4.0.0rc8_promote_interview_selections` (#6629). Give the reason in one sentence: it seeded an absent key with the whole in-force set, so synthesis read the result as an operator's activation. Note that the successor settles on its first run, so a later `--only` narrowing is never undone. If the ADR has an `updated:` frontmatter date, bump it.
- **CHANGELOG** `docs/changelog/CHANGELOG.md`, `[Unreleased]` → `### Fixed`. Write one impact-first entry with a bold lead and `(#6629)`, then **Before:** / **After:**, in the house style. Content:
  - **Before:** the upgrade wrote every available directive (38) and paradigm (14) into the activation list of a project whose interview predates the activation ledger, so `charter synthesize` demanded a companion tactic per directive, skipped the fresh-project seed, and `implement` stopped with `synthesized_drg missing`.
  - **After:** the upgrade leaves an absent key absent and appends only interview selections a present list lacks, through the activation ledger.
  - **What to do:** a project an earlier build already seeded keeps its list. The upgrade warns, and `charter interview --narrow-activation` or `charter activate <kind> <id> --only` keeps only what you selected.
  - Also mention that the upgrade no longer writes a second activation list into `.kittify/config.yaml` on a project whose keys already moved (#6549).
- Run the docs checks named in `docs/development/how-to/review-gates.md` (spelling and changelog style), and run `tests/architectural/test_no_legacy_terminology.py`.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_migration_order_manifest.py tests/specify_cli/upgrade/test_unify_charter_activation_migration.py tests/upgrade/test_consolidate_charter_bundle_migration.py tests/architectural/test_no_legacy_terminology.py -q
```

## Definition of Done

- The tests above are green, and the docs checks are clean.
- `git diff origin/main -- src/specify_cli/upgrade/migrations/m_unify_charter_activation.py src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py` is empty.

## Reviewer Guidance

- The deny gate must exercise the successor with a fixture on which `detect()` is True, and must prove that the deny lists are unchanged.
- The CHANGELOG entry is consumer-facing and names the remedy.
