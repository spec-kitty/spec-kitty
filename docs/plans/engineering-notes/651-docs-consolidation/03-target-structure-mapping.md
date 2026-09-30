---
title: 'Target structure & tree mapping — #651 docs consolidation'
description: The canonical Common Docs top-level structure for spec-kitty and the per-tree mapping decisions, including the glossary/dashboard constraint and engineering_notes location.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/651-docs-consolidation/02-common-docs-standard.md
- docs/plans/engineering-notes/651-docs-consolidation/index.md
---
# Target structure & tree mapping (#651 docs consolidation)

> **Historical (delivered).** The Common Docs consolidation described here shipped: see [ADR 2026-06-27-1](../../../adr/3.x/2026-06-27-1-common-docs-reconciliation.md) and the per-section `index.md` / frontmatter now used across `docs/`. Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

> Operator-directed target structure and mapping decisions (2026-06-27). Companion to
> [the four-lens review](./index.md) and [the standard analysis](./02-common-docs-standard.md).

## Canonical top-level structure (operator-confirmed)

```
docs/
├── index.md          # Master entry point
├── context/          # Why we exist, who we serve, domain vocabulary
├── architecture/     # Current system design
├── adr/              # Architecture Decision Records  (spec-kitty: adr/<era>/ — see below)
├── plans/            # Future work, roadmap, feature specs
├── api/              # API reference
├── configuration/    # Configuration reference
├── integrations/     # Third-party integrations
├── security/         # Security posture and practices
├── guides/           # How-to guides for humans and agents
├── operations/       # Production operations
├── migrations/       # Database and data migrations
└── changelog/        # Release changelog
```

## Per-tree mapping decisions

| spec-kitty source | → target | Decision / constraint |
|---|---|---|
| `CHANGELOG.md` | `changelog/` | **Trivial.** |
| `docs/{tutorials,how-to,reference,explanation}` → guides | `guides/` (+ `api/`, `architecture/`) | **Trivial-ish.** Divio folds onto Common Docs sections. |
| **glossary + audiences** | `context/` | **Dual constraint — does not simplify to a plain move.** Must remain (1) **accessible by the dashboard** (preserve the dashboard's glossary read path) AND (2) **open to future glossary-as-doctrine distribution** (the glossary must stay extractable as a doctrine artifact, not get locked into a docs-only location). The move to `context/` must keep both seams intact. |
| **user journeys** | `plans/` | **Fold into `plans/`** (forward-looking intent). |
| `architecture/` living design | `architecture/` | Collapse the era-split — *era belongs to history, not the current design.* |
| `architecture/{1.x,2.x,3.x}/adr/` (99 ADRs) | `adr/<era>/` | **Preserve era subdirs** for historical reasoning (justified deviation from the standard's flat `adr/`). |
| `docs/{1x,2x,3x}` + `docs/architecture/` shadow tree | **deleted** | The split-brain — consolidation's core payload. |
| **in-progress investigations & traces** (today's `engineering_notes/`) | **OPEN — `operations/` vs `plans/`** | Operator undecided. See recommendation below. |

## Open question: where do in-progress investigations & traces live?

**Recommendation: `plans/`, with a lifecycle — not `operations/`.**

- `operations/` is **production-ops-shaped** (monitoring, disaster-recovery, capacity,
  runbooks). In-flight investigations and debugging traces are research/decision-support,
  not production operations — they fit `operations/` poorly.
- `plans/` ("future work, roadmap, feature specs") is **forward-looking**, which is what an
  in-flight investigation is: it feeds a future decision or work item. This note itself is
  a good example — it exists to drive a future consolidation mission.
- **The real tension** (per the standard's "`docs/` is not a wiki / stale docs deleted"):
  these notes are inherently **transient**. Whatever bucket they land in needs a
  **lifecycle**, not a permanent home: `status: draft/active` while in-flight → distil the
  durable finding into `adr/` (a decision) or `architecture/` (a design) → let the raw
  investigation go `deprecated` and be deleted by the curation policy. The home matters
  less than the distil-then-retire discipline.
- **Defer the final call to the reconciliation ADR** (it owns the curation policy that
  governs these notes' retirement).

## Constraints carried from the reviews (binding for the mission)

- **`adr/<era>/`** (not flat) — preserve the 99-ADR history; convert all ADRs to YAML
  frontmatter (today 0/48 use it → invisible to the DocFX generator).
- **One gated SSOT — Candidate A:** in-file frontmatter is SSOT; the page-inventory is
  regenerated as a validated lockfile (see [02](./02-common-docs-standard.md)).
- **Three make-or-break choices:** YAML ADRs; resolvable + build-validated `related:`
  paths; a redirect/alias convention applied at **every** file move (DocFX has no native
  aliases).
- **Anti-sprawl ratchet** (`tests/architectural/`) — paired with a full-gate dry-run
  before merge.
- **Namespace `status`** in frontmatter to avoid colliding with the WP-lane status model.

## Sequencing

- **Ship now (hygiene, no design):** `index.md` for `engineering_notes/` + `development/`,
  `CLAUDE.md:531` dead-link fix, ADR README backfill, verify-close the `docs/adr/3.x/`
  shim, retire `NAVIGATION_GUIDE.md`, add the `llms.txt` routing rubric.
- **Consolidation mission (gated by the reconciliation ADR first):** single-root +
  history move (`adr/<era>/`) + collapse the split-brain + unify the living design; link
  rewrite + redirect shim; frontmatter / `related:` / `index.md` normalization + YAML-ADR
  conversion; anti-sprawl ratchet.
