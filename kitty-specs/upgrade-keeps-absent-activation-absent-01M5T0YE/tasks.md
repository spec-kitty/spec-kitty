# Tasks: Upgrade keeps an absent activation key absent

**Mission**: `upgrade-keeps-absent-activation-absent-01M5T0YE` · **Issue**: #6629 (refs #6549)
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Pin the end-to-end red-first reproduction | WP01 | |
| T002 | Write the successor migration module | WP01 | |
| T003 | Register the supersession and the manifest entry | WP01 | |
| T004 | Focused unit tests of the successor | WP01 | |
| T005 | Seeded-list hint and dry-run preview | WP01 | |
| T006 | Move the shipped-migration pins to the successor (the deny-gate move went to WP01) | WP02 | [P] |
| T007 | Update docstrings that name the shipped promotion as live | WP02 | [P] |
| T008 | ADR amendment and CHANGELOG entry | WP02 | [P] |

## Phase 1 — Core fix

### WP01 — Successor promotion migration (P1)

**Goal**: an upgrade promotes interview selections into present lists through the activation ledger seam, never materialises an absent key, and settles after one run. The shipped `unify_charter_activation_promote_answers` becomes a recorded no-op.
**Independent test**: `tests/specify_cli/upgrade/test_upgrade_keeps_absent_activation_6629.py` is red on main and green after the change.
**Prompt**: [tasks/WP01-successor-promotion-migration.md](tasks/WP01-successor-promotion-migration.md)

Included subtasks (tracked through `spec-kitty agent tasks mark-status`):

T001 Pin the end-to-end red-first reproduction (WP01)
T002 Write the successor migration module (WP01)
T003 Register the supersession and the manifest entry (WP01)
T004 Focused unit tests of the successor (WP01)
T005 Seeded-list hint and dry-run preview (WP01)

Dependencies: none. Risks: the upgrade-scope source resolution; perpetual re-selection, if `detect()` ever returns False on a project with selections.

## Phase 2 — Pins, gates and docs

### WP02 — Move pins and gates, and document the supersession (P2)

**Goal**: the architectural deny-guard gate and the shipped-migration tests drive the successor, the docstrings stop naming the shipped promotion as live, and the ADR and CHANGELOG record the change.
**Independent test**: `tests/architectural/test_deny_list_survives_upgrade.py` and `tests/architectural/test_migration_order_manifest.py` are green, and the docs checks pass.
**Prompt**: [tasks/WP02-pins-gates-and-docs.md](tasks/WP02-pins-gates-and-docs.md)

Included subtasks:

T006 Move the shipped-migration pins to the successor; the deny-gate move went to WP01 (WP02)
T007 Update docstrings that name the shipped promotion as live (WP02)
T008 ADR amendment and CHANGELOG entry (WP02)

Dependencies: WP01.

## MVP

WP01 alone fixes the reported defect. WP02 keeps the gates honest and records the change.
