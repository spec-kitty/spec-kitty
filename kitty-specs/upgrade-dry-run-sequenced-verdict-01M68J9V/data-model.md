# Data Model: Upgrade dry-run sequenced verdict

This Mission adds no persisted data structure. It adds one *declaration* on the migration
base class and one per-run in-memory view inside the migration runner. Both are described
here as domain language, not as a schema.

## Entity: Detection-input declaration (`sequenced_after`)

| | |
|---|---|
| **Definition** | A migration's declared list of migration ids whose application, earlier in the same run, changes the state its `detect()` reads. |
| **Owner** | `BaseMigration` (`src/specify_cli/upgrade/migrations/base.py`), class-level tuple, empty by default. |
| **Lifecycle** | Authored with the migration. Read only by the migration runner during a dry run. Never persisted, never hashed, never recorded in the ledger. |
| **Invariants** | (1) It is detect-input metadata, **not** execution order — `order_manifest.txt` remains the single order authority (ADR 2026-10-17-1 §2). (2) An id that is not in this run's selection changes nothing. (3) An unknown (renamed/removed) id changes nothing. (4) A real run never consults it. |
| **Populated by** | `3.2.6_issue_matrix_driver_repoint` → `("3.2.6_gate_artifact_merge_drivers",)`. Every other migration keeps the empty default. |

## Entity: Sequenced run view

| | |
|---|---|
| **Definition** | The set of migration ids the current run has reported applied — for a real run an observable fact about the tree, for a dry run the only record of what a real run would already have done at that point in the order. |
| **Owner** | `MigrationRunner`, per run (reset with the run, like the run's residue bookkeeping). |
| **Lifecycle** | Grows in manifest order as the loop reports `applied`; discarded at the end of the run. |
| **Invariants** | Holds only ids from this run's selection. Holds a predicted id exactly when its declaration named an id already in the set. |

## Entity: Predicted verdict

| | |
|---|---|
| **Definition** | A dry-run verdict for a migration whose `detect()` is False on the current tree but whose declared predecessor this run has reported applied. |
| **Observable shape** | Status `applied` (so `migrations_applied` and the `--json` payload carry it exactly as a real run's verdict would), with the change line `dry-run: would apply after <id>` naming the predecessor(s). |
| **Rules** | Only under `dry_run`. Only after `can_apply` allows it; a refusal keeps the ordinary `can_apply` skip and its reason. Writes nothing: no file, no ledger record, no metadata stamp. |

## State transitions (one migration, one run)

| From | Condition | To |
|------|-----------|-----|
| selected | ledger already settled it | `skipped` — "already applied, skipping" (unchanged) |
| selected | `detect()` True | `applied` (real run applies; dry run reports `apply(dry_run=True)`'s summary) — unchanged, and the id joins the sequenced view |
| selected | `detect()` False, real run | `skipped` — `not needed (project already in target state)` (unchanged) |
| selected | `detect()` False, dry run, declaration names an applied predecessor, `can_apply` allows | `applied` — predicted, change line `dry-run: would apply after <id>` |
| selected | `detect()` False, dry run, declaration names an applied predecessor, `can_apply` refuses | `skipped` — the `can_apply` reason (unchanged shape) |
| selected | `detect()` False, dry run, no applied declared predecessor | `skipped` — `not needed on the current tree` (rewording of the dry-run claim) |
