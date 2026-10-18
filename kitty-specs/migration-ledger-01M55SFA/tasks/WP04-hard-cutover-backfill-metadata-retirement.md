---
work_package_id: WP04
title: Hard-cutover backfill + applied-state metadata retirement (IC-06)
dependencies:
- WP01
- WP02
requirement_refs:
- FR-012
- FR-013
- NFR-003
- C-001
- SC-003
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-18T04:22:10.774303+00:00'
subtasks:
- T022
- T023
- T024
- T025
- T026
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- tests/upgrade/test_backfill_ledger.py
execution_mode: code_change
lane: planned
owned_files:
- src/specify_cli/upgrade/metadata.py
- src/specify_cli/upgrade/migrations/m_3_2_6_meta_traces_merge_drivers.py
- src/specify_cli/upgrade/migrations/m_3_2_6_decisions_event_log_merge_driver.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py
- src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py
- tests/upgrade/test_backfill_ledger.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_summary.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_0rc35_provenance_gitignore.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_4_derived_views_gitignore.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_5_agents_skills_gitignore.py
- tests/specify_cli/upgrade/migrations/test_session_presence_upgrade_smoke.py
- tests/specify_cli/upgrade/test_charter_bundle_v2_migration.py
- tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py
- tests/upgrade/migrations/test_m_2_1_1_repair_skill_pack.py
- tests/upgrade/test_auto_discovery.py
- tests/upgrade/test_metadata_final_file_5229.py
- tests/upgrade/test_migration_robustness.py
- tests/upgrade/test_runner_status_classification.py
- tests/upgrade/test_symlinked_ignore_guard.py
- tests/upgrade/test_upgrade_auto_commit_unit.py
- tests/upgrade/test_upgrade_commit_outcomes_5443.py
- tests/upgrade/test_upgrade_idempotency.py
- tests/upgrade/test_upgrade_integration.py
- tests/upgrade/test_upgrade_outcome_rendering.py
- tests/upgrade/test_upgrade_surface_repair_step.py
- tests/upgrade/test_version_stamp_boundary.py
- tests/upgrade/test_worktree_stamp_guard.py
- tests/upgrade/test_upgrade_preview_acceptance.py
- tests/upgrade/test_upgrade_cli_contract.py
- tests/upgrade/test_preview_oracle.py
- tests/upgrade/preview_support/test_public_witnesses.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Hard-cutover backfill + applied-state metadata retirement

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`role: implementer`). Implementation command (depends on WP01, WP02):
`spec-kitty implement WP04 --base WP02`

> **Seam split (why this WP does NOT create the backfill migration):** the backfill MIGRATION
> (`m_4_0_0rc8_backfill_migration_ledger.py`) and its `order_manifest.txt` entry both live in **WP01**
> — they depend only on the ledger, and co-locating the file with its manifest entry keeps WP01's
> build gate (dangling-entry check) green. **WP04 owns the metadata CUTOVER**, which needs WP02's
> record-path flip first: drop `migrations.applied` from `_model_owned_mapping` (this makes the R4
> strip PERMANENT — the block is never re-added), retire `record_migration`/`has_migration` as
> authority, and repoint the 4 cross-migration readers. Land AFTER WP02 to avoid a merge seam.

---

## Objective

Cut existing projects over to the ledger in ONE direction and retire `metadata.yaml.applied_migrations`
as an authority — **no dual-write mirror** (C-001 single authority; NFR-003 accepted back-compat
cost). A pre-ledger project's prior work is recognised and NOT redone (guard G-2).

Grounded in `plan.md` **IC-06 (F1–F4)**; spec FR-012/013, NFR-003, C-001, SC-003.

## Context & Constraints — design invariants (carry these exactly)

- **The backfill migration is WP01's.** `m_4_0_0rc8_backfill_migration_ledger.py` is created and
  listed first in the manifest by WP01, where it is proven to WRITE ledger records (tracked
  unconditional / clone-local detect-gated). WP04 does NOT create or edit it. WP04 makes the cutover
  that turns those writes into the SOLE authority.
- **Drop `migrations.applied` from `_model_owned_mapping`** — `save()` no longer writes applied
  state (the hard cutover). This is what makes the R4 strip **permanent**.
- **R4 — the stale on-disk block stays gone.** WP01's backfill may strip the `migrations:` block
  once; because `_model_owned_mapping` (after this WP) no longer owns `migrations.applied`, the
  merge-preserving `_merge_onto_disk` will not re-add it. Assert the block is gone **and stays gone
  across a subsequent `save()`** (forbidden as a dead second authority by C-001).
- **`record_migration` / `has_migration` / `applied_migrations` survive only for F1 to READ once.**
  Repoint the cross-migration readers to the ledger (see pointcuts).
- **VERIFY the version/schema stamp is unchanged** — it is NOT the applied authority; only the
  applied list leaves the file.
- Do **NOT** edit `base.py` / `runner.py` (owned by WP02). If a reader repoint appears to need a
  `runner.py` edit, STOP and flag the seam to the orchestrator.

## Pointcut Map (file:line → change)

| # | file:line | change | what |
|---|-----------|--------|------|
| F1 | `src/specify_cli/upgrade/migrations/m_4_0_0rc8_backfill_migration_ledger.py` | **OWNED BY WP01** | the backfill migration + its manifest entry live in WP01 (created there, proven to write ledger records). WP04 consumes it; do NOT edit it. |
| F2 | `src/specify_cli/upgrade/metadata.py:243-274` (`_model_owned_mapping`) | **MODIFY** | drop the `migrations.applied` block — `save()` no longer writes applied state. This makes the R4 strip permanent (the block is never re-added by the merge-preserving save). |
| F3 | `metadata.py:287` (`record_migration`) / `:276` (`has_migration`) | **MODIFY/retire-as-authority** | runner stops calling `record_migration`; keep `applied_migrations`/`has_migration` for F1 to READ once. Repoint the cross-migration readers below to the ledger. |
| F3a | `src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py` | **MODIFY** | `has_migration(...)` reader → ledger lookup. |
| F3b | `src/specify_cli/upgrade/migrations/m_3_2_6_meta_traces_merge_drivers.py` | **MODIFY** | `has_migration(...)` reader → ledger lookup. |
| F3c | `src/specify_cli/upgrade/migrations/m_3_2_6_decisions_event_log_merge_driver.py` | **MODIFY** | `has_migration(...)` reader → ledger lookup. |
| F3d | `src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py:425` | **MODIFY** | direct `for record in metadata.applied_migrations:` reader → ledger lookup. |
| F4 | `runner.py:216-229` / `:252-263` (`VersionStamp.capture`) | **VERIFY (no edit)** | version/schema stamp unchanged; NFR-003 recorded. (Owned by WP02 — verify only.) |

## Owned files (disjoint)

- `src/specify_cli/upgrade/metadata.py`
- `src/specify_cli/upgrade/migrations/m_3_2_6_meta_traces_merge_drivers.py`
- `src/specify_cli/upgrade/migrations/m_3_2_6_decisions_event_log_merge_driver.py`
- `src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py`
- `src/specify_cli/upgrade/migrations/m_3_1_1_charter_rename.py`
- `tests/upgrade/test_backfill_ledger.py`

## Red-first tests to write FIRST

**`tests/upgrade/test_backfill_ledger.py`** (NEW — the cutover END-STATE; the record-writing itself is
proven by WP01's `test_backfill_migration.py`):
- after the cutover run, a **pre-ledger fixture**'s prior migrations are **not re-run**;
- `metadata.yaml.migrations.applied` is **removed as authority**, with **no dual-write**;
- the `migrations:` block is **gone AND stays gone across a subsequent `save()`** (permanence —
  `_model_owned_mapping` no longer re-adds it);
- **no-op control (G-2):** a re-run makes no commit and changes no managed file.

— FR-012, FR-013, SC-003. Write red first, then green.

## Subtasks & Detailed Guidance

### T022 – Drop `migrations.applied` from `_model_owned_mapping` (F2, FR-012, NFR-003)
`save()` no longer writes applied state; this makes WP01's R4 strip permanent (the block is never
re-added by the merge-preserving save). Record the accepted back-compat cost (NFR-003).

### T024 – Retire `record_migration`/`has_migration` as authority (F3, FR-012)
Runner no longer records via metadata (that moved to the ledger in WP02); keep the read helpers only
for F1's one read.

### T025 – Repoint cross-migration readers (F3a–F3d, FR-013)
Repoint the four readers (`m_4_0_0rc6_charter_pack_cutover`, `m_3_2_6_meta_traces_merge_drivers`,
`m_3_2_6_decisions_event_log_merge_driver`, `m_3_1_1_charter_rename:425`) to the ledger. If any needs
a `runner.py` edit, STOP and flag the WP02 seam.

### T026 – Land the cutover end-state test green incl. the no-op control (SC-003, G-2)
Make `test_backfill_ledger.py` green: prior work not re-run, `applied_migrations` removed as
authority with no dual-write, `migrations:` block gone and stays gone across a `save()`, and the
re-run no-op control.

## Test strategy & blast radius (targeted — NOT whole dirs)

Run and record counts: `tests/upgrade/test_backfill_ledger.py`, plus `tests/upgrade/` and
`tests/specify_cli/upgrade/` (the repointed readers have tests there). CI owns full suites.

## Quality gates

`ruff check` + `ruff format --check` clean; `mypy` zero new; complexity ≤15; literals hoisted; no
suppressions. SC-008 ratchet untouched.

## Acceptance criteria satisfied

SC-003 (pre-ledger backfill, not re-run, no dual-write); FR-012/013, NFR-003, C-001.

## Risks & Mitigations

- **R3 wrong backfill re-runs everything (G-2):** the cutover must recognise WP01's backfilled
  records; pre-ledger fixture + re-run no-op control.
- **R4 stale `migrations:` block:** dropping it from `_model_owned_mapping` (T022) makes WP01's strip
  permanent; assert it stays gone across a `save()`.

## Review Guidance

Confirm: tracked unconditional vs clone-local detect-gated; no dual-write; the `migrations:` block
is gone after backfill; all four readers repointed; version stamp untouched.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
