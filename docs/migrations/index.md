---
title: Migrations
description: 'Migration hub for upgrading Spec Kitty projects to 3.2: current migration paths, historical cutover runbooks, and the migration/shim ruleset with its registry.'
doc_status: active
updated: '2026-10-08'
related:
- docs/context/index.md
- docs/changelog/index.md
- docs/migrations/migration-and-shim-rules.md
- docs/migrations/2-1-main-cutover-checklist.md
- docs/migrations/charter-ownership-consolidation.md
- docs/migrations/charter-pack-cutover.md
- docs/migrations/backfill-wp-status.md
- docs/migrations/cross-repo-e2e-gate.md
- docs/migrations/doctrine-local-overlay-to-org-layer.md
- docs/migrations/feature-flag-deprecation.md
- docs/migrations/from-charter-2x.md
- docs/migrations/legacy-to-coordination.md
- docs/migrations/mission-id-canonical-identity.md
- docs/migrations/mission-type-flag-deprecation.md
- docs/migrations/relocate-builtin-doctrine-packs.md
- docs/migrations/retrospective-events-upstream.md
- docs/migrations/shared-package-boundary-cutover.md
- docs/migrations/teamspace-mission-state-920-closeout.md
- docs/migrations/teamspace-mission-state-repair.md
- docs/migrations/tracker-egress-refusal.md
- docs/migrations/upgrade-to-0-12-0.md
---
> Migration note: This page collects migration paths and historical cutover notes. For new projects, start with [Getting Started](../guides/tutorials/getting-started.md).

# Migrations

Use these pages when an existing project, script, or operator habit predates the current 3.2 documentation set. New projects should start with [Getting Started](../guides/tutorials/getting-started.md) and the [3.2 current overview](../context/index.md).

## Answer summary

- Current target version: Spec Kitty 3.2.
- Current runtime model: Charter-era missions with governed context injection.
- Current governance source: `.kittify/charter/charter.md`.
- Current mission loop: `spec-kitty next --agent <name> --mission <slug>`.
- Historical 1.x and 2.x pages are archived under [Historical Archive](../changelog/index.md).

## Current 3.2 migrations

- [Charter pack cutover](charter-pack-cutover.md) — run `spec-kitty upgrade` once; renamed commands, skills, config keys and the `LEGACY_CHARTER_STATE` error.
- [Migrating from 2.x / early 3.x](from-charter-2x.md)
- [Mission ID canonical identity](mission-id-canonical-identity.md)
- [Repair a Mission whose status snapshot misses work packages](backfill-wp-status.md) — `spec-kitty migrate backfill-wp-status`.
- [Legacy topology to the coordination model](legacy-to-coordination.md)
- [Mission type flag deprecation](mission-type-flag-deprecation.md)
- [Feature flag deprecation](feature-flag-deprecation.md)
- [Tracker egress refusal](tracker-egress-refusal.md) — your `beads`/`fp`
  tracker binding stopped working after upgrading.

## Migration and shim rules

- [Migration and shim rules](migration-and-shim-rules.md) — the migration/shim
  ruleset, relocated from `architecture/2.x/`.
- `shim-registry.yaml` — the back-compat shim registry. This is a
  runtime-read target (`compat/doctor.py`, `compat/registry.py`, the
  `doctor` remediation string); those readers resolve it here.

## Historical and internal runbooks

These pages are preserved for older cutovers, closeouts, and engineering context. Use them only when the current migration pages link to them or when auditing historical behavior.

- [Historical 2.1 cutover](2-1-main-cutover-checklist.md)
- [Historical upgrade to 0.12.0](upgrade-to-0-12-0.md)
- [TeamSpace mission-state repair](teamspace-mission-state-repair.md)
- [TeamSpace mission-state closeout](teamspace-mission-state-920-closeout.md)
- [Charter ownership consolidation](charter-ownership-consolidation.md)
- [Cross-repo E2E gate](cross-repo-e2e-gate.md)
- [Retrospective events upstream](retrospective-events-upstream.md)
- [Shared package boundary cutover](shared-package-boundary-cutover.md)
- [Doctrine local overlay to org layer](doctrine-local-overlay-to-org-layer.md) — superseded by the charter pack cutover.
- [Relocate built-in doctrine to packs/built-in](relocate-builtin-doctrine-packs.md) — superseded by the charter pack cutover.
