---
title: '4.x Architectural Decision Records'
description: 'Index for Spec Kitty 4.x architectural decision records: where new ADRs land from the 4.0.0 cycle onward, the naming convention, and how to register one.'
doc_status: active
updated: '2026-10-04'
type: explanation
audience: docs/context/audience/internal/system-architect.md
---

# 4.x ADRs

Architectural Decision Records for the 4.x line. **New ADRs land here.**

## Era history

The 4.x line began with the 4.0.0 release-candidate cycle (`4.0.0rc1`, 2026-09-13). The
cycle's intent is declared in [`docs/changelog/4.0.0.md`](../../changelog/4.0.0.md) and
executed against the [4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md).

This folder opened on 2026-09-30. ADRs written earlier in the 4.0.0 cycle (dated
2026-09-13 to 2026-09-29) stay in [`docs/adr/3.x/`](../3.x/index.md): ADRs are immutable
and moving them would break every link to them. Read the two folders together for the
full 4.0.0 decision record.

## Naming

- `YYYY-MM-DD-N-descriptive-title-with-dashes.md` where `N` is `1, 2, 3, …` per ADR landed on a given date.

After adding an ADR file, run (from the repository root, so `scripts` resolves as a
package) `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<your-adr>.md`
to update the page-inventory lockfile and add the row to the index table below.

## Status Conventions

- `Accepted` means the decision remains current policy.
- `Superseded` means a newer ADR replaced the decision; keep the file for history, but do not implement from it.
- `Deprecated` means the direction is in active retirement and should not receive new work.

## Template

Use the shared template at [`docs/architecture/adr-template.md`](../../architecture/adr-template.md).

## Index

| Date | Title |
| --- | --- |
| 2026-09-30 | [allowlist ratchets are priced debt](2026-09-30-1-allowlist-ratchets-are-priced-debt.md) |
| 2026-10-01 | [dead-symbol allowlist identity is (module, name)](2026-10-01-1-dead-symbol-allowlist-module-name-identity.md) |
| 2026-10-01 | [a mission status read API replaces the CLI-bundled dashboard (extract and replace)](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) |
| 2026-10-01 | [the decision ledger is a PRIMARY-partition kind (reverses the #3928 COORD intent)](2026-10-01-3-decision-ledger-primary-partition.md) |
| 2026-10-03 | [replace charter reads and writes through a staged Java service strangler](2026-10-03-1-charter-read-write-service-strangler.md) |
| 2026-10-04 | [a Mission waives the contracts/ deliverable with a meta.json declaration](2026-10-04-1-mission-contracts-waiver-in-meta-json.md) |
| 2026-10-04 | [a started work package keeps its recorded execution lane on re-finalize](2026-10-04-2-started-work-package-lane-membership-is-frozen.md) |
