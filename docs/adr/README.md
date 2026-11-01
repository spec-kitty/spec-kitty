---
title: Architecture Decision Records
description: 'Architecture Decision Records for Spec Kitty, organized by release era (1.x to 4.x); new ADRs land in the 4.x era. Each ADR records one decision and its rationale.'
doc_status: active
updated: '2026-11-01'
related:
- docs/adr/1.x/README.md
- docs/adr/2.x/README.md
- docs/adr/3.x/README.md
- docs/adr/4.x/README.md
- docs/architecture/README.md
- docs/README.md
---
# Architecture Decision Records

Architecture Decision Records (ADRs) capture a single architectural decision and
the rationale behind it. They are organized by release era so the history of the
system is navigable across major versions.

## Eras

- [1.x ADRs](1.x/README.md) — decisions from the 1.x lineage.
- [2.x ADRs](2.x/README.md) — decisions from the 2.x lineage.
- [3.x ADRs](3.x/README.md) — decisions from the 3.x line, plus those written early in the
  4.0.0 cycle (up to 2026-09-29), before the 4.x folder opened.
- [4.x ADRs](4.x/README.md) — **current.** New ADRs land here.

## Adding an ADR

Add the ADR file under `docs/adr/<era>/` (use `4.x` for a new decision) and
nothing else: do not add its era index-table row or regenerate the
page-inventory lockfile (`docs/development/page-inventory.yaml`) in your PR.
After merge, the `ci/regen-docs-index` bot pull request runs
`python -m scripts.docs.freshen_adr_inventory --all`, which adds every missing
row in one idempotent, date-ordered pass and regenerates the inventory and the
docs retrieval index. A PR that adds an era row fails the `docs-lint` guard.
Use `--check` locally to see what the bot will add.

To rename or delete an ADR, rename or delete the file only and leave its row
alone. The bot runs `--all --prune`, which also removes every row whose ADR file
no longer exists, so a renamed ADR's old row is dropped and its new row is added
in the same bot pull request. Use `--check --prune` locally to see dangling rows.

## See also

- [Documentation home](../README.md)
- [Architecture](../architecture/README.md)
