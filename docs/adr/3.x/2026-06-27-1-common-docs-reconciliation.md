---
title: 'ADR: Common Docs Consolidation — Reconciliation of Metadata, Structure, Redirects,
  Glossary Read-Path, ADR Migration, and Curation'
description: 'Folds four documentation roots into one Common Docs tree and makes in-file frontmatter the per-page metadata source, with the page inventory regenerated as a lockfile.'
status: Accepted
date: '2026-06-27'
---

## Context and Problem Statement

Spec Kitty's documentation has accreted into a **multi-root, shadow-tree split-brain** that
the standard [Common Docs](https://github.com/velvet-tiger/common-docs) conventions are meant
to cure. Four defects, all measured in the research, frame this decision:

1. **Four-root + shadow-tree split-brain.** `architecture/`, `docs/`, `development/`, and
   `engineering_notes/` are four parallel documentation roots, and `docs/{1x,2x,3x}/` +
   `docs/architecture/` is a *shadow duplicate* of `architecture/{1.x,2.x,3.x}/`. The
   "never duplicate" boundary contract in `architecture/README.md` is already leaking. This
   is the "ongoing document sprawl" the operator objects to and the core payload to resolve.

2. **Metadata split-brain.** The same lifecycle datum lives in two places. The sidecar
   `docs/development/3-2-page-inventory.yaml` (568 rows) is SSOT for
   `path/tag/divio_type/owning_workstream/current_target/citation_refs`, while in-file
   frontmatter carries `title`/`description` (consumed today by `scripts/docs/seo_postprocess.py`
   and the SEO gate). `version_leakage_check.py` literally enforces agreement between the two
   (`LEAK-FRONTMATTER-MISMATCH`), and `citation_refs` is populated in only **6 of 568 rows** —
   the sidecar's cross-reference half is effectively dead.

3. **DocFX-on-GitHub-Pages, no native redirects.** A site generator already ships
   (`docs/docfx.json`) and publishes to <https://docs.spec-kitty.ai/> on every push to `main`
   (`.github/workflows/docs-pages.yml`). DocFX on GitHub Pages has **no native alias/redirect
   mechanism**, and the consolidation *moves and deletes* files across ~503 referencing files /
   ~1,589 link occurrences (42 in `src/` — a missed rewrite is a *runtime* break, not a dead
   link). Without a redirect convention, every move is URL churn and SEO loss.

4. **ADR invisibility and era-less ADRs.** The repository holds ~117 unique ADRs (191 files),
   and **0 use YAML frontmatter** (~12 markdown-table, ~34 bold-inline headers) — invisible to
   DocFX. Of these, **20 ADRs live only in the flat `architecture/adrs/` shim** with no era
   home, so a structural move has nowhere to put them without a decision.

The operator has chosen **full consolidation** (not partial adoption). This ADR is the
**serial spine** of Mission A (the governed foundation): it must record every mechanism the
consolidation depends on so that **Mission B (the execution mission) opens with zero undecided
design**. The decisions below are pre-settled by the five-lens squad; this ADR records them in
canonical form — it does **not** re-litigate them, and it does **not** itself move, rename, or
mutate any documentation file (its own relocation is Mission B's job; C-006).

## Decision Drivers

- **Resolve the split-brain by construction**, not by convention — one root, one SSOT per datum.
- **Generator-native**: the live DocFX site reads in-file frontmatter; the SSOT must be what the
  published site already consumes.
- **Standard-aligned where it helps, justified deviation where it doesn't** — adopt Common Docs
  fully, but preserve the era-of-decision history the live site and `llms.txt` are built around.
- **Preserve every load-bearing invariant** — completeness rollups, the dashboard glossary
  read-path, the glossary-as-doctrine extraction seam — none may be silently dropped.
- **No URL/SEO regression** across a move that touches ~503 files / ~1,589 links.
- **Terminology-canon clean** — the frontmatter status key must not collide with the WP-lane
  status model (C-004).
- **Mission B must not start on undecided design** — every mechanism is decided here, ahead of
  execution (C-001).

## Considered Options

The squad converged on a single recommended value for each of the seven open mechanisms; the
losing alternatives are recorded per-decision in [Pros and Cons of the Options](#pros-and-cons-of-the-options).
The headline fork was **metadata SSOT**: Candidate A (in-file frontmatter SSOT, inventory
regenerated as a lockfile) versus Candidate B (sidecar inventory stays SSOT, frontmatter
generated from it).

## Decision Outcome

**Full consolidation into a single Common Docs root, with seven binding mechanism decisions.**
Each decision below is recorded at its pre-settled value. Mission B executes them; it does not
re-decide them.

### D1 — Metadata SSOT: Candidate A (in-file frontmatter), inventory becomes a generated lockfile

**Decision:** **In-file frontmatter is the per-page metadata SSOT.** The page-inventory
(`docs/development/3-2-page-inventory.yaml`) is **regenerated FROM frontmatter** as a
generated/validated **lockfile**: a build step walks `docs/`, parses frontmatter, and emits the
rollup; the freshness gate asserts the committed rollup is in sync with a fresh generation
(drift = CI failure). The dead `citation_refs` field is **dropped**; cross-references move to a
`related:` frontmatter list of resolvable repo-relative `.md` paths, validated at build time.

**Rationale:** generator-native (the live site already reads frontmatter, not the sidecar);
standard-aligned (Common Docs mandates in-file metadata, no sidecar concept); kills the
duplication by construction (`version_tag` lives in one place → `LEAK-FRONTMATTER-MISMATCH` is
retired); and survives agents (frontmatter-at-point-of-edit beats a remembered 568-row sidecar).

**Load-bearing caveat (do not drop):** the sidecar's *rollup* semantics — completeness ("every
`.md` inventoried"), workstream ownership, deterministic alphabetical diff — **must be preserved
as the generated lockfile artifact**, not deleted. Candidate A converts the inventory from a
hand-maintained SSOT into a generated-and-asserted lockfile; it does not abolish it.

### D2 — Frontmatter status key is namespaced as `doc_status`

**Decision:** The frontmatter lifecycle key is **`doc_status`** (controlled vocabulary
`draft | active | deprecated | superseded`), tied to a publish gate. The bare key `status`
**collides with the WP-lane status model** (C-004 / terminology-canon) and is therefore
prohibited as a frontmatter key. `updated: YYYY-MM-DD` carries the freshness date.

**Rationale:** a bare `status` in a `.md` frontmatter is indistinguishable, to a reader and to
greps, from the WP-lane `status` term; namespacing removes the collision without losing the
controlled vocabulary the publish gate needs.

### D3 — Target tree is the 13-section Common Docs structure, with `adr/<era>/`

**Decision:** Adopt the **13-section single-root Common Docs structure** under one `docs/` root:
`index.md`, `context/`, `architecture/`, `adr/`, `plans/`, `api/`, `configuration/`,
`integrations/`, `security/`, `guides/`, `operations/`, `migrations/`, `changelog/`. Every
directory carries its own `index.md`.

**Justified deviation:** the standard mandates a *flat* `adr/NNNN-`; spec-kitty instead uses
**`adr/<era>/`** (`adr/1.x/`, `adr/2.x/`, `adr/3.x/`) to preserve the era-of-decision reasoning
across ~117 ADRs and satisfy the docsite lens's version-stance concern *for the immutable
history only*. The **living architectural design collapses into a single unversioned
`docs/architecture/`** — era belongs to history, not to the current design. All ADRs are
converted to YAML frontmatter (today 0 use it → invisible to DocFX).

**Amendment (2026-07-04, [#2353](https://github.com/Priivacy-ai/spec-kitty/issues/2353)):** `release-goals/` is promoted to a published fourteenth section (declared release-line intent) — a further justified deviation from the standard 13-section tree.

### D4 — Redirect mechanism: generated `<meta http-equiv="refresh">` stub pages per old path

**Decision:** Because DocFX on GitHub Pages has **no native redirect/alias mechanism**, every
moved/deleted URL is preserved by a **generated `<meta http-equiv="refresh">` stub page emitted
at the old path** into the DocFX `_site` output. The stubs are produced by a **post-build step
in `scripts/docs/`** that reads a **checked-in redirect map** (old-path → new-path). A
**captured baseline URL inventory** (the pre-move site URL set) is the **denominator** for
Mission B's "100% of URLs resolve" NFR — every baseline URL must resolve (directly or via a
refresh stub) after the move.

**Rationale:** a client-side `<meta refresh>` stub is the only redirect primitive available on a
static GitHub Pages site fronting DocFX; emitting it per old path from a reviewed map makes the
URL-preservation guarantee testable and the denominator explicit.

### D5 — Glossary read-path: preserve the `.kittify/glossaries/<scope>.yaml` seed read-path (load-bearing)

**Decision (the load-bearing C-001 decision):** The dashboard's `GlossaryHandler`
(`src/specify_cli/dashboard/handlers/glossary.py`) reads **`.kittify/glossaries/<scope>.yaml`
seed files** via `load_seed_file()` (`src/glossary/scope.py:108`) — **not** the human-readable
`glossary/contexts/*.md`. These are two distinct artifacts on two distinct paths:

- **Machine read-path (must not break):** `.kittify/glossaries/<scope>.yaml` seed files, consumed
  by `load_seed_file()` at three call sites (the dashboard `GlossaryHandler`, the template
  renderer, and the glossary CLI), and loaded into the store by `glossary/pipeline.py`.
- **Human narrative artifact (the one that moves):** `glossary/contexts/*.md`, the markdown
  per-context glossary that the consolidation relocates into `docs/context/`.

**Binding constraint:** the move of `glossary/contexts/*.md` → `docs/context/` **MUST preserve or
regenerate the `.kittify/glossaries/<scope>.yaml` seed read-path** so the dashboard, renderer, and
CLI keep resolving. The seed file is also the **doctrine-extraction source** — the glossary stays
extractable as a doctrine artifact from the seed, not locked into a docs-only markdown location.
Concretely: only the human markdown relocates; the seed YAML stays at (or is regenerated to)
`.kittify/glossaries/`, and both seams (dashboard read + doctrine extraction) remain intact. Any
plan that moves the markdown without preserving the seed read-path is rejected.

### D6 — Era-less ADR migration: the 20 flat-only ADRs → `adr/3.x/` by date; shim closes after

**Decision:** The **20 ADRs that live only in the flat `architecture/adrs/` shim** (no era home)
are **3.x-era by date** → migrate them to **`adr/3.x/`** (sorted by their dated filename). This
migration is **executed in Mission B**. The flat `architecture/adrs/` shim **closes only after**
the migration completes — it is not removed before its contents have a durable era home, so no
ADR is orphaned mid-move.

### D7 — Curation: delete-stale policy + distil-then-retire lifecycle

**Decision:** Adopt Common Docs' **delete-stale curation policy** — `docs/` is not a wiki; one
concern per file; stale/deprecated docs are deleted after ~6 months unreferenced; every
behaviour-changing change updates the relevant `docs/` files in the same commit.

For **in-flight investigations and traces** (today's `engineering_notes/`), the home is
**`plans/`** with an explicit **distil-then-retire lifecycle**, not a permanent wiki home:
`doc_status: draft|active` while in-flight → **distil** the durable finding into `adr/` (a
decision) or `architecture/` (a design) → mark the raw investigation `doc_status: deprecated`
and let the delete-stale policy retire it. The discipline (distil, then retire) matters more
than the bucket; `plans/` is the chosen bucket because investigations are forward-looking
decision-support, which `operations/` (production-ops-shaped) is not.

### Merge boundary (C-001)

**Mission B (the execution mission) is BLOCKED until this ADR is Accepted AND merged into
`docs/2165-consolidation-research`.** C-001 is a **merge boundary**, not intra-mission ordering:
the remaining Mission A work packages and all of Mission B's structural moves, link rewrites,
redirect-shim generation, frontmatter backfill, and ADR migration depend on the decisions
recorded here being on the integration branch first. No consolidation move may begin against an
un-merged spine.

### Consequences

#### Positive

- **Split-brain resolved by construction** — one documentation root, one SSOT per datum; the
  shadow `docs/{1x,2x,3x}` tree and the four-root sprawl are eliminated, not perpetuated.
- **`LEAK-FRONTMATTER-MISMATCH` retired** — under D1 the leaked datum lives in exactly one place,
  so the cross-check gate becomes structurally unnecessary.
- **URL/SEO preserved** across ~503 files / ~1,589 links via D4's per-path refresh stubs against a
  captured baseline denominator.
- **ADRs become first-class on the live site** — D3's YAML-frontmatter conversion makes ~117 ADRs
  visible to DocFX for the first time, with era history intact via `adr/<era>/`.
- **Dashboard and doctrine glossary seams stay intact** — D5 keeps the seed read-path and the
  doctrine-extraction source load-bearing through the move.
- **Mission B opens with zero undecided design** — every mechanism is settled here.

#### Negative

- **Bespoke enforcement weight.** The standard provides shape, not enforcement: the `related:`
  path validator, the link-rewrite tooling, the redirect-shim generator, and the anti-sprawl
  ratchet are all spec-kitty-bespoke and are Mission B's real cost.
- **One-time conversion churn.** Converting ~117 ADRs to YAML frontmatter and backfilling
  frontmatter from the 568-row sidecar is mechanical but large.
- **Forward-only.** This ADR decides; it does not itself move anything. A regression that
  re-introduces a second doc root or a shadow tree is only caught once Mission B's anti-sprawl
  ratchet lands (pair it with a full-gate dry-run before merge — a ratchet that only bites
  post-merge cannot catch its own offenders).

#### Neutral

- The Divio axis (tutorials/how-to/reference/explanation) folds onto Common Docs sections
  (`guides/` + `api/` + `architecture/`) — a relabelling, not a loss of content.
- The three Common Docs Agent Skills (`scaffold`/`write`/`find`) shipped as **three doctrine
  tactics** (`common-docs-scaffold` / `common-docs-write` / `common-docs-find`) rather than as
  peer skills, superseding the earlier "install as peer skills" wording. `find`'s static lookup
  table is still **not** adopted — its topic→path role is backed by the richer, gated DRG +
  page-inventory.

### Confirmation

The decisions are confirmed when, in Mission B: (1) a single `docs/` root exists with all 13
sections present and each carrying `index.md`, and no second doc root or `docs/<version>x` shadow
tree survives (anti-sprawl ratchet green); (2) the page-inventory is regenerated from frontmatter
and the freshness gate asserts lockfile sync (D1); (3) no frontmatter uses a bare `status` key
(D2); (4) every captured-baseline URL resolves directly or via a generated refresh stub (D4
against the baseline denominator); (5) the dashboard `GlossaryHandler` still resolves terms via
`load_seed_file()` after the `context/` move (D5); (6) the 20 flat-only ADRs resolve under
`adr/3.x/` and the flat shim is closed only afterward (D6); and (7) the curation policy retires a
distilled investigation note end-to-end (D7). This ADR itself is confirmed Accepted and merged
into `docs/2165-consolidation-research` before any Mission B work begins (C-001).

## Pros and Cons of the Options

### D1 — Candidate A (in-file frontmatter SSOT) vs Candidate B (sidecar SSOT)

**Candidate A (CHOSEN) — in-file frontmatter is SSOT; inventory regenerated as a lockfile.**

- **Pros:** generator-native (the live site already reads frontmatter); standard-aligned;
  kills duplication by construction; survives agents (edit-at-point); retires
  `LEAK-FRONTMATTER-MISMATCH`.
- **Cons:** must explicitly preserve the sidecar's rollup semantics as a generated artifact,
  or completeness/ownership invariants are lost.

**Candidate B — sidecar inventory stays SSOT; frontmatter generated from it.**

- **Pros:** keeps the existing gated sidecar as the single authority; one machine to trust.
- **Cons:** a **permanent deviation** from the standard the operator chose to fully adopt; the
  published site still wouldn't read the SSOT (it reads frontmatter); authors must keep a
  568-row sidecar in mind — the convention that does not survive agents.

### D3 — flat `adr/` (standard) vs `adr/<era>/` (chosen)

- **Flat `adr/NNNN-` (standard):** simplest, standard-pure; **but** erases the version-stance
  axis the live site and `llms.txt` are built around, and flattens ~117 ADRs across three eras
  into one undifferentiated list, losing era-of-decision reasoning.
- **`adr/<era>/` (CHOSEN):** a justified deviation that preserves historical reasoning for the
  immutable record while the *living* design collapses to a single unversioned location — era
  where it matters (history), dropped where it confuses (current design).

### D4 — `<meta refresh>` stubs vs alternatives

- **`<meta http-equiv="refresh">` stubs (CHOSEN):** the only redirect primitive available on a
  static GitHub Pages site fronting DocFX; per-path, generated from a reviewed map, testable
  against a baseline denominator.
- **No redirect / accept URL churn:** rejected — ~1,589 link occurrences and live SEO would
  regress on every move.
- **Server-side redirects / DocFX native aliases:** unavailable — GitHub Pages serves static
  files and DocFX has no native alias mechanism.

### D7 — `plans/` vs `operations/` for in-flight investigations

- **`plans/` (CHOSEN):** forward-looking, which is what an in-flight investigation is; pairs with
  the distil-then-retire lifecycle.
- **`operations/`:** production-ops-shaped (monitoring, disaster-recovery, runbooks);
  investigations fit it poorly.

## More Information

- **Mission split:** This is Mission A (governed foundation); Mission B is the execution mission
  (structural moves, link rewrites, redirect-shim, frontmatter backfill, ADR migration,
  anti-sprawl ratchet). C-001 gates B on this ADR's merge.
- **Research ground truth (pre-settled values):**
  [`docs/plans/engineering-notes/651-docs-consolidation/index.md`](../../plans/engineering-notes/651-docs-consolidation/README.md),
  [`02-common-docs-standard.md`](../../../docs/plans/engineering-notes/651-docs-consolidation/02-common-docs-standard.md),
  [`03-target-structure-mapping.md`](../../../docs/plans/engineering-notes/651-docs-consolidation/03-target-structure-mapping.md).
- **Key code/seams referenced:** `src/glossary/scope.py` (`load_seed_file`),
  `src/specify_cli/dashboard/handlers/glossary.py` (`GlossaryHandler`),
  `docs/development/3-2-page-inventory.yaml`, `docs/docfx.json`,
  `.github/workflows/docs-pages.yml`, `scripts/docs/seo_postprocess.py`,
  `scripts/docs/version_leakage_check.py`, `scripts/docs/check_docs_freshness.py`.
- **Standard:** <https://github.com/velvet-tiger/common-docs>.
- **Cross-references:** [#2165](https://github.com/Priivacy-ai/spec-kitty/issues/2165),
  [#651](https://github.com/Priivacy-ai/spec-kitty/issues/651).
