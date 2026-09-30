---
title: 'Docs Consolidation (#2165 / #651) — four-lens review and direction'
description: Adversarial four-lens review of Common Docs adoption for spec-kitty, the premise corrections, and the operator's full-consolidation direction (era-split ADRs, living design).
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/adr/3.x/README.md
- docs/development/3-2-page-inventory.yaml
- docs/docfx.json
- docs/llms.txt
---
# Docs Consolidation (#2165 / #651) — four-lens review and direction

> **Historical (delivered).** The Common Docs consolidation described here shipped: see [ADR 2026-06-27-1](../../../adr/3.x/2026-06-27-1-common-docs-reconciliation.md) and the per-section `index.md` / frontmatter now used across `docs/`. Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

> Engineering note capturing the 2026-06-27 adversarial review of GitHub issue
> [#2165](https://github.com/Priivacy-ai/spec-kitty/issues/2165) (partial adoption of
> [Common Docs](https://github.com/velvet-tiger/common-docs) conventions), parented under
> epic #651 (Public Site and Documentation Experience), plus the operator's decision to
> pursue **full consolidation**. This is research/decision capture — the implementing
> mission is not yet specced.

## Context

#2165 proposed adopting a *subset* of Common Docs conventions (a machine-readable
`related:` frontmatter graph, per-directory `index.md`, frontmatter consistency, an
`llms.txt` routing rubric, a delete-stale curation policy). The project CTO (**@xtfer**)
pushed back in a comment, arguing for **full** adoption: *"The purpose of the standard
architecture is to reduce search times for humans and agents. The /architecture tree
appears to be about 5 files. Partial adoption isn't particularly useful and will result
in ongoing document sprawl."*

A four-lens adversarial squad was run (profile-loaded): **architect-alphonso**
(architecture), **doctrine-daphne** (docs governance), **paula-patterns** (full-adoption
path), and a second **architect-alphonso** (generated-docsite impact).

## Premise corrections (load-bearing — surface these to the CTO)

- **`architecture/` is 218 files, not ~5.** The "~5" is only the loose root files; the
  mass is **99 ADRs across `1.x/2.x/3.x`** plus `diagrams/audience/audits/vision/`, buried
  by directory depth. (Confirmed independently by alphonso and paula.)
- **0 of ~48 ADRs use YAML frontmatter.** They use a markdown table (~12) or bold-inline
  (~34) header. The issue's "~50% YAML" claim is wrong — and today's ADR metadata is
  **invisible to the site generator.**
- **A site generator already ships.** `docs/docfx.json` builds the Divio tree + version
  namespaces and **publishes to https://docs.spec-kitty.ai/ on every push to `main`**
  (`.github/workflows/docs-pages.yml`). `title`/`description` frontmatter is *already
  consumed* (`scripts/docs/seo_postprocess.py`). The "future Hugo" framing is wrong — the
  conventions land on a *live* generator today.
- **The split-brain @xtfer fears already exists.** `docs/1x|2x|3x` + `docs/architecture/`
  is a *shadow duplicate* of `architecture/1.x|2.x|3.x`, and the "never duplicate" boundary
  contract in `docs/architecture/README.md` **is already leaking.**
- **Blast radius of a structural move:** ~**503 referencing files / 1,589 link
  occurrences** (42 in `src/` — a missed rewrite is a *runtime* break, not a dead link;
  151 hits on `docs/adr/3.x` alone).

## The four lenses (summary)

| Lens | Verdict | Core point |
|---|---|---|
| **alphonso — architecture** | refine scope | The `related:` graph duplicates the **freshness-gated** page-inventory `citation_refs` (populated 6/565 rows). Unify, don't fork. Split into janitorial + design slices. |
| **daphne — doctrine** | half-ready | `status`/`updated` frontmatter duplicates the inventory's gated lifecycle SSOT (split-brain); `status` also collides with the WP-lane term. Needs ONE reconciliation ADR; frontmatter should stay `title`+`description`. |
| **paula — full-adoption** | achievable, but a mission | Full adoption *is* achievable and history-preservable (relax Common Docs' flat-`adr/` to `adr/<era>/`). The CTO's direction has merit (the split-brain is real). But it's a real mission (503/1,589), not a P3. |
| **alphonso — docsite** | "partial structure, full convention" | A flat single root **erases the version-stance axis** the live site + `llms.txt` are built around. Three make-or-break choices: YAML ADRs, resolvable+validated `related:` paths, redirect/alias on every move. |

## DIRECTION — full consolidation (operator decision, 2026-06-27)

The operator **overrides "partial structure"** toward consolidation, with a sharp
refinement that reconciles the version-stance concern with the maintainer-confusion
problem:

1. **ADR history → `adr/<era>/`.** Keep the era-split **only for the immutable ADR
   record** — this preserves historical reasoning (why past decisions were made in their
   era). This is the alphonso/paula `adr/<era>/` idea, and it satisfies the docsite lens's
   version-stance concern *for the historical layer*.
2. **Living architectural design → ONE location.** The current era-split of the *living*
   design (current C4 models, present-state architecture) **makes it hard for maintainers
   to understand the current state**. Collapse the living design into a single, unversioned
   location. (Era belongs to history, not to the current design.)
3. **Consolidate `architecture/` + `docs/` + `development/` + `engineering_notes/`** into
   one Common Docs root. **This is the crucial part** — the multi-root + shadow-tree
   split-brain is the core defect; partial adoption leaves it in place (the "ongoing
   document sprawl" @xtfer rightly objects to).

**Why this reconciles all four lenses:** version stance is *kept where it matters* (ADR
history via `adr/<era>/`) and *dropped where it confuses* (the living design); the
machine-readable conventions are adopted **fully and uniformly** (all four lenses agree on
this); and the existing split-brain is *resolved* rather than perpetuated.

## Convention decisions to carry into the mission

- **One gated SSOT for cross-refs + lifecycle.** Do *not* stand up a hand-maintained
  `related:` graph beside the freshness-gated `page-inventory.citation_refs` + the doctrine
  DRG. The reconciliation ADR must pick a direction and **generate the other half**:
  - candidate A (docsite lens): **in-file frontmatter is per-page SSOT** (generators read
    frontmatter, not the sidecar); the inventory becomes a *generated/validated rollup*.
  - candidate B (doctrine lens): **inventory stays SSOT**; frontmatter is generated from it.
  - **This is the central open question** — see "metadata-in-file" below.
- **Three make-or-break choices** (docsite lens):
  1. **YAML frontmatter on ADRs** (table/bold is invisible to DocFX/any SSG).
  2. **`related:` = resolvable repo-relative paths + a build-time link validator** (else the
     field is inert decoration).
  3. **A redirect/alias convention applied at every file move** (DocFX has no native
     aliases; the consolidation *moves and deletes* files → URL churn + SEO loss otherwise).
- **`status` needs a controlled vocabulary** (`active|draft|superseded|archived`) tied to a
  publish gate, and the bare term collides with the WP-lane status model — namespace or
  rename it (terminology-canon).
- **Anti-sprawl ratchet** (the CTO's core worry): a `tests/architectural/` gate that fails
  CI on a second doc root, any `docs/*/` dir missing `index.md`, ADRs missing the
  frontmatter schema, or a re-introduced `docs/<version>x` shadow tree. (Per the
  gate-unmask-cannot-self-validate rule, pair it with a full-gate dry-run before merge.)

## Slicing

- **Ship now (hygiene, no design dependency):** `index.md` for `engineering_notes/` +
  `development/`, fix `CLAUDE.md:531` dead link → `docs/architecture/documentation-mission.md`,
  backfill the 7 missing ADRs in `docs/adr/3.x/README.md`, verify-and-close the
  `docs/adr/3.x/` shim (already symlinks), retire the 2.x-stale `NAVIGATION_GUIDE.md`,
  add the `llms.txt` routing rubric.
- **Consolidation mission (gated by ONE reconciliation ADR first):** paula's four lanes —
  (A) single-root + history move (`adr/<era>/`) + collapse the `docs/*x` / `architecture/*.x`
  split-brain + unify the living design; (B) scripted link rewrite (`src/` → doctrine →
  `kitty-specs/` → `tests/` → `docs/`) + redirect shim; (C) frontmatter / `related:` /
  `index.md` normalization + YAML-ADR conversion; (D) anti-sprawl ratchet gate.

## Open questions — resolved (reconciliation ADR 2026-06-27-1 + Mission A WPs)

Both open questions below were resolved before Mission B opens.

1. **Full adoption mechanics** — resolved by the reconciliation ADR (D1–D7) and
   Mission A WPs. The Common Docs agent skills (scaffold / write / find) are
   implemented in Mission A as **doctrine tactics** (WP02), not as installed Agent
   Skills (`.agents/skills/`). The three built-in tactics are at
   `src/doctrine/tactics/built-in/common-docs-scaffold.tactic.yaml`,
   `common-docs-write.tactic.yaml`, and `common-docs-find.tactic.yaml`; the
   `common-docs-find` tactic explicitly rejects the static lookup table and
   instead resolves topic→path through the DRG + page-inventory lockfile. The
   ADR's Neutral consequences note ("install as peer skills") predates this
   decision and is superseded; it will be reconciled in Mission B. See
   `02-common-docs-standard.md` §2.
2. **Metadata SSOT** — resolved: **Candidate A** (in-file frontmatter is the
   per-page SSOT; the page-inventory becomes a generated lockfile). See ADR D1
   and the detailed verdict in `02-common-docs-standard.md` §3.

## References

- Issue #2165; Epic #651; CTO comment by @xtfer.
- Key files: `docs/development/3-2-page-inventory.yaml`, `scripts/docs/check_docs_freshness.py`,
  `scripts/docs/version_leakage_check.py`, `tests/docs/test_docs_seo.py`, `docs/docfx.json`,
  `.github/workflows/docs-pages.yml`, `scripts/docs/seo_postprocess.py`,
  `docs/architecture/README.md` (the boundary contract this supersedes), `docs/adr/3.x/`,
  `docs/architecture/NAVIGATION_GUIDE.md`, `docs/llms.txt`, `src/doctrine/graph.yaml` (DRG).
