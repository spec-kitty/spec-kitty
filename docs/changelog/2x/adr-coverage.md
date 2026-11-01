---
title: 2.x ADR Coverage
description: Historical Spec Kitty 2.x archive page for 2.x ADR Coverage; use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/context/README.md
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/README.md) for current docs.

# 2.x ADR Coverage

## Audit Summary

A fresh-clone audit compared `docs/adr/2.x/` against current 2.x code surfaces.

Result:

1. Runtime and status/event areas were already covered by ADRs.
2. Doctrine artifact governance and living glossary architecture were implemented but undocumented.
3. This gap is closed by new ADRs dated `2026-02-23`.

## Coverage Matrix

| Code Surface | ADR Coverage |
|---|---|
| `src/specify_cli/runtime/*` and canonical `next` loop | `2026-02-17-1`, `2026-02-17-2`, `2026-02-17-3` |
| Status/event-lifecycle model | `2026-02-09-1`, `2026-02-09-3`, `2026-04-06-1`, `2026-05-01-1` plus the superseded history in `2026-02-09-2` and `2026-04-03-2` |
| Doctrine artifact model (`src/doctrine/**`, charter compiler/commands) | `2026-02-23-1` |
| Living glossary model (`glossary/**`, glossary hook integration) | `2026-02-23-2` |
| Versioned docs strategy (`docs/1x`, `docs/2x`, docs workflow) | `2026-02-23-3` |

## New ADR Files Added in This Update

1. `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
2. `docs/adr/2.x/2026-02-23-2-living-glossary-context-and-curation-model.md`
3. `docs/adr/2.x/2026-02-23-3-versioned-1x-2x-docs-site-without-hosted-platform-scope.md`
