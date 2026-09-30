---
title: Architecture Decision Records
description: 'Architecture Decision Records for Spec Kitty, organized by release era (1.x to 4.x); new ADRs land in the 4.x era. Each ADR records one decision and its rationale.'
doc_status: active
updated: '2026-09-30'
related:
- docs/adr/1.x/index.md
- docs/adr/2.x/index.md
- docs/adr/3.x/index.md
- docs/adr/4.x/index.md
- docs/architecture/index.md
- docs/index.md
---
# Architecture Decision Records

Architecture Decision Records (ADRs) capture a single architectural decision and
the rationale behind it. They are organized by release era so the history of the
system is navigable across major versions.

## Eras

- [1.x ADRs](1.x/index.md) — decisions from the 1.x lineage.
- [2.x ADRs](2.x/index.md) — decisions from the 2.x lineage.
- [3.x ADRs](3.x/index.md) — decisions from the 3.x line, plus those written early in the
  4.0.0 cycle (up to 2026-09-29), before the 4.x folder opened.
- [4.x ADRs](4.x/index.md) — **current.** New ADRs land here.

## Adding an ADR

After adding an ADR file under `docs/adr/<era>/` (use `4.x` for a new decision), run (from the repository root, using the
`python -m` module form so `scripts` resolves as a package — #3227):

```bash
python -m scripts.docs.freshen_adr_inventory docs/adr/<era>/<your-adr>.md
```

This freshens **both** indexes the `docs-freshness` CI gate enforces — the
generated page-inventory lockfile (`docs/development/page-inventory.yaml`)
and the era `README.md` index table — in one idempotent, date-ordered pass.
Use `--all` to back-fill every missing row, or `--check` to verify without
writing.

## See also

- [Documentation home](../index.md)
- [Architecture](../architecture/index.md)
