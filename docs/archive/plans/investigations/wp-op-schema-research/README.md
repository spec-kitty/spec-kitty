---
title: WP & Op Schema Model — Research Squad Reports
description: 'Verbatim archived reports from the three-lens research squad that grounded the WP & Op schema-model idea note on 2026-07-16.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/plans/investigations/wp-op-schema-model.md
---
# WP & Op Schema Model — Research Squad Reports

> **Historical (verbatim research report, 2026-07-16).** Archived input to the [WP & Op schema model](../../../../plans/investigations/wp-op-schema-model.md) idea note; milestone references are to the closed 3.2.x cycle and the retired 3.3.x line. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

Verbatim archived reports from the three-lens research squad dispatched
2026-07-16 to ground [../wp-op-schema-model.md](../../../../plans/investigations/wp-op-schema-model.md). The
synthesis lives in that note; these are the unedited source reports.

| Lens | Profile | Report |
|---|---|---|
| Code as-is (WP/Op lifecycle + hash machinery) | architect-alphonso | [code-as-is.md](code-as-is.md) |
| Roadmap / vision / ADR binding | researcher-robbie | [roadmap-adr.md](roadmap-adr.md) |
| Feasibility / whack-a-field / smallest slice | paula-patterns | [feasibility.md](feasibility.md) |

All three converged independently: the idea's diagnosis is real, but the model
is ~60–70% already shipped (`WPMetadata`, `wps.yaml`→`tasks.md` derived
generation, event-log ownership of lane/review), and the useful residual is a
narrow content-hash / field-eviction fix plus an optional Op scope field — not a
new store or a markdown-body rewrite.
