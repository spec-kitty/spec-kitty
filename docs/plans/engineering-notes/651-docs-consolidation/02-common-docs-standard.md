---
title: Common Docs standard — full-adoption mechanics & the metadata-SSOT verdict
description: What the Common Docs standard mandates, how spec-kitty adopts it fully, and the verdict that in-file frontmatter becomes the metadata SSOT with a regenerated inventory lockfile.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/page-inventory.yaml
- docs/docfx.json
- docs/plans/engineering-notes/651-docs-consolidation/03-target-structure-mapping.md
- docs/plans/engineering-notes/651-docs-consolidation/index.md
---
# Common Docs standard — full-adoption mechanics & the metadata-SSOT verdict

> **Historical (delivered).** The Common Docs consolidation described here shipped: see [ADR 2026-06-27-1](../../../adr/3.x/2026-06-27-1-common-docs-reconciliation.md) and the per-section `index.md` / frontmatter now used across `docs/`. Kept as a record; the active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

> Research capture (paula-patterns, 2026-06-27) of the **actual** Common Docs standard
> (<https://github.com/velvet-tiger/common-docs>) for the #2165/#651 full-consolidation
> direction. Companion to [the four-lens review](./index.md) and
> [the target-structure mapping](./03-target-structure-mapping.md).

## 1. What the standard actually mandates

### Canonical directory set — single `docs/` root, 13 sections, no era namespaces

```
docs/
├── index.md          # master entry ("Start at docs/index.md")
├── context/          # product.md, domain.md, competitive.md, stakeholders.md
├── architecture/     # overview, data-model, api-design, infrastructure, services, constraints
├── adr/              # index.md, template.md, NNNN-short-title.md  (FLAT, zero-padded)
├── plans/            # roadmap.md, epics/EPIC-NNN-name.md, features/<name>.md
├── api/              # endpoints, authentication, errors, rate-limiting, changelog
├── configuration/    # environment, feature-flags, secrets
├── integrations/     # <service-name>.md
├── security/         # threat-model, auth, data-handling, vuln-management, incident-response
├── guides/           # getting-started, development, deployment, testing, contributing
├── operations/       # monitoring, disaster-recovery, capacity-planning, runbooks/
├── migrations/       # YYYYMMDD-description.md
└── changelog/        # YYYY-MM-DD-vX.Y.Z.md
```

Every directory carries its own `index.md`. The standard has **no concept of
version/era namespaces** — this is the one place spec-kitty must deviate (see §2).

### Naming & curation rules

- `kebab-case`, lowercase, no underscores — **except** numeric prefixes: ADRs
  `NNNN-short-title.md` (zero-padded 4 digits, sequential, **never reused**), migrations
  `YYYYMMDD-`, changelog `YYYY-MM-DD-vX.Y.Z`.
- One concern per file; split when a file exceeds ~300 lines.
- "`docs/` is not a wiki" — curated, versioned alongside code; **stale docs are deleted**
  (deprecated removed after ~6 months unreferenced).
- Every behaviour-changing PR updates the relevant `docs/` files in the same commit.

### Frontmatter schema — the answer to "metadata in the file?"

Required on **every** `.md`:

```yaml
title:        # short descriptive title
description:  # one sentence
status:       # draft | active | deprecated | superseded
updated:      # YYYY-MM-DD
```

Optional: `authors: [Name]`, `related: [path/to/related.md]` (repo-relative `.md` paths).
ADR-only: `date:`, `supersedes:`, `superseded-by:`.

**`related:` is a flat YAML list of repo-relative paths** — not URNs, not labelled, not
bidirectional, and the standard defines **no validator** for it. Resolvability and
anti-sprawl enforcement are entirely **bespoke** (spec-kitty must supply them).

### The three agent skills — scaffolding/authoring only

| Skill | Automates | Does NOT do |
|---|---|---|
| `common-docs-scaffold` | the 13-dir tree + `index.md` stubs + frontmatter templates; appends a section table to project config; never overwrites | content, validation |
| `common-docs-write` | substantive content + full frontmatter (`status: draft`, today's `updated`) | bidirectional `related:`, link validation, index/sidecar updates (only *suggests*) |
| `common-docs-find` | topic→path navigation via a **static lookup table** | read frontmatter/`related:`/index — it's a pre-built table |

**Net: the standard provides the *shape*, not the *enforcement*.** Every load-bearing
guarantee spec-kitty needs — resolvable `related:` paths, the link rewrites, the
redirect/alias-on-move, the anti-sprawl ratchet — is bespoke.

## 2. Full-adoption mechanics for spec-kitty

### Tree → Common Docs mapping (see [03](./03-target-structure-mapping.md) for the operator's decisions)

| spec-kitty today | → target | Notes |
|---|---|---|
| `architecture/` living design (root C4/overview) | `docs/architecture/` | collapse the era-split — operator: era belongs to history |
| `architecture/{1.x,2.x,3.x}/adr/` (99 ADRs) | `docs/adr/<era>/` | **relax the standard's flat `adr/`** to preserve historical reasoning |
| `docs/architecture/diagrams,audience,audits,vision/` | `docs/architecture/` + `docs/context/` | vision→context, audits→architecture |
| `docs/{tutorials,how-to,reference,explanation}` | `docs/guides/` + `docs/api/` + `docs/architecture/` | Divio folds onto Common Docs sections |
| `docs/{1x,2x,3x}/` + `docs/architecture/` shadow | **deleted** | the split-brain — consolidation's core payload |
| `development/` + `docs/development/` | `docs/guides/development.md` + `docs/operations/` | |
| `engineering_notes/` (incl. this note) | open — see [03](./03-target-structure-mapping.md) | `plans/` vs `operations/` undecided |

### `adr/<era>/` — reconciling the standard vs the operator's direction

The standard mandates **flat `docs/adr/NNNN-`**. spec-kitty has **99 ADRs across three
eras**, and **0 use YAML frontmatter** (~12 markdown-table, ~34 bold-inline → invisible to
DocFX). Full adoption therefore requires:

1. **Relax flat → `docs/adr/{1.x,2.x,3.x}/`** for the immutable history (justified
   deviation: preserves era-of-decision reasoning; satisfies the docsite lens's
   version-stance concern *for history only*).
2. **Convert all 99 ADRs to YAML frontmatter** (`title/description/status/updated` + ADR
   `date/supersedes/superseded-by`) — non-negotiable, else they stay invisible to the
   generator.
3. **Living design unifies** into a single unversioned `docs/architecture/`.

### Skills — implemented as doctrine tactics (WP02; ADR note superseded, reconciliation deferred to Mission B)

The standard's three skills are adopted in Mission A as **doctrine tactics** (WP02), not
as installed agent skills (`.agents/skills/`). The three built-in tactics live at
`src/doctrine/tactics/built-in/`:

| Tactic | File | What it governs |
|---|---|---|
| `common-docs-scaffold` | `common-docs-scaffold.tactic.yaml` | Scaffold a new Common Doc: pick the owning section, create the file, seed the `doc_status` frontmatter |
| `common-docs-write` | `common-docs-write.tactic.yaml` | Author body + frontmatter to pass live gates (SEO band, `related:` form, Divio type, naming) |
| `common-docs-find` | `common-docs-find.tactic.yaml` | Locate the owning doc via the DRG + page-inventory lockfile — **rejects** the static lookup table |

The ADR (`docs/adr/3.x/2026-06-27-1-common-docs-reconciliation.md`) records in its
Neutral consequences that the three skills "install as peer skills" — that note predates the
operator's doctrine-tactics decision and is **superseded** by the WP02 outcome. The ADR is
intentionally not edited in Mission A; its Neutral consequences will be reconciled in Mission B.

**Bespoke (the real mission weight):** ~**1,589 link rewrites across ~503 files** (42 in
`src/` — a missed rewrite is a **runtime break**, not a dead link; 151 on
`docs/adr/3.x`); a build-time **`related:` path validator**; the **redirect/alias
shim** (DocFX has no native aliases → URL/SEO churn on every move); the **anti-sprawl
ratchet** (`tests/architectural/` gate).

## 3. Metadata-in-file — the A-vs-B verdict

**Does the standard put metadata in the file?** Yes, unambiguously — all metadata lives
in-file frontmatter; there is **no sidecar concept**. Frontmatter *is* the per-page SSOT
by design (`related:` for cross-refs, `status`/`updated` for lifecycle).

### spec-kitty's split-brain today (measured)

The sidecar `docs/development/page-inventory.yaml` (565 rows) is SSOT for
`path/tag/divio_type/owning_workstream/current_target/citation_refs`. The gates split:

- **SEO gate** (`tests/docs/test_docs_seo.py`) reads **in-file frontmatter** (`title`,
  `description`) — already frontmatter-native.
- **Freshness completeness** — every `.md` under `docs/` must appear in the sidecar.
- **`version_leakage_check.py`** — sidecar `tag` is SSOT, but it **cross-checks the page's
  frontmatter `version_tag` against the row** (`LEAK-FRONTMATTER-MISMATCH`). *The
  split-brain made literal: the same datum lives in both places and a gate enforces
  agreement.*
- `citation_refs` is populated in only **6 of 565 rows** — the sidecar's cross-ref half is
  effectively dead; a hand-maintained `related:` graph beside it would fork a third copy.

### Verdict: **Candidate A — in-file frontmatter is the SSOT; the page-inventory becomes a generated/validated lockfile.**

Rationale:

1. **Generator-native** (the operator's explicit factor): the live DocFX site reads
   in-file frontmatter, **not** the sidecar; `seo_postprocess.py` + the SEO gate already
   consume it. In-file is *already* the SSOT for everything the published site shows.
2. **Standard-aligned**: Common Docs mandates in-file. Candidate B (sidecar SSOT,
   frontmatter generated) is a permanent deviation from the standard the operator chose to
   fully adopt.
3. **Kills the duplication by construction**: under A, `version_tag` lives in one place →
   `LEAK-FRONTMATTER-MISMATCH` becomes structurally impossible; `related:` replaces the
   dead `citation_refs`.
4. **Authoring ergonomics**: every agent edits the file; nobody remembers a 565-row
   sidecar. Frontmatter-at-point-of-edit is the only convention that survives agents.

**Caveat (don't drop a load-bearing invariant):** the sidecar carries rollup semantics
frontmatter can't — completeness ("every `.md` inventoried"), workstream ownership,
deterministic alphabetical diff. A must **preserve these as a generated artifact**, not
delete them.

### Gate-reconciliation under A

| Gate | Today | Under A |
|---|---|---|
| SEO (`test_docs_seo.py`) | reads frontmatter | unchanged — already frontmatter-native |
| Freshness completeness | sidecar lists every `.md` | **regenerate the inventory FROM frontmatter** (walk `docs/`, parse → emit); gate asserts the committed rollup is in sync with a fresh generation (drift = CI fail). Inventory becomes a *lockfile*. |
| `version_leakage` | sidecar `tag` SSOT, cross-checks frontmatter | frontmatter is SSOT; leakage reads it directly; `LEAK-FRONTMATTER-MISMATCH` **retired** |
| `related:` validator (new) | n/a | build-time: every `related:` path resolves to an existing `.md` |
| anti-sprawl ratchet (new) | n/a | fail CI on: 2nd doc root, any `docs/*/` missing `index.md`, ADR missing frontmatter, re-introduced `docs/<version>x` shadow tree |

### Migration to A

1. **Reconciliation ADR first** (gates everything) — records A, the controlled `status`
   vocabulary, and **namespaces `status`** to avoid the WP-lane `status` collision
   (terminology-canon — e.g. `doc_status` or `publish_state`).
2. **Backfill frontmatter** from the 565-row sidecar into each file (scripted lift; `tag`
   is mechanical; `citation_refs`→`related:` for the 6 populated rows).
3. **Convert the 99 ADRs to YAML frontmatter** (concurrent with the `adr/<era>/` move).
4. **Flip the freshness gate** to *generate-and-compare* the inventory.
5. **Add the `related:` validator + anti-sprawl ratchet** — paired with a full-gate
   dry-run before merge (a ratchet that only bites post-merge can't catch its own
   offenders).
