---
title: 'ADR: Unify Pack Metadata on a Single Manifest — Enumerated Constituents + Delegated Lineage'
description: 'Unifies the two divergent pack manifests (counts vs enumerated) onto one canonical pack-manifest schema for every pack type, splitting authored lineage from generated constituents.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-16'
related:
- plans/investigations/2026-08-pack-level-metadata-manifest
- plans/domains/doctrine-charter-domain-plan
---

# Unify Pack Metadata on a Single Manifest — Enumerated Constituents + Delegated Lineage

**Filename:** `2026-08-16-1-pack-metadata-manifest-unification.md`

**Status:** Accepted

**Date:** 2026-08-16

**Deciders:** Maintainer

**Technical Story:** [#2467 (KEYSTONE — split built-in doctrine into packs + compound packs)], corroboration in [`docs/plans/investigations/2026-08-pack-level-metadata-manifest.md`]

---

## Context and Problem Statement

A pack — built-in, org, fetched, or a charter bundle — has no single, first-class
record of **what it contains** and **where it sits in a lineage** (its parent pack,
and, for a charter pack, which doctrine pack it accompanies). The information exists,
but scattered across **two divergent manifest formats that disagree**:

- `pack-manifest.yaml` for org doctrine packs (`src/specify_cli/doctrine/snapshot.py:157-180`)
  records per-kind **`artifact_counts`** (`:195-212`) — counts, not an enumerated list —
  carries **no lineage**, and is **not written** for the built-in or git-managed packs
  (`…/contracts/pack-layout.md:104-107`).
- `synthesis-manifest.yaml` for charter/project bundles
  (`src/charter/synthesizer/manifest.py:46-112`) records **enumerated**
  `artifacts:[{kind, slug, path, content_hash}]` plus a self-integrity `manifest_hash`
  (`:107`) — the "constituent parts" model — but exists only for charter bundles.

The **built-in reference pack that every org pack extends has no pack-level manifest at
all** — `packs/built-in/*.graph.yaml` carry only `schema_version`/`generated_by` headers.
Packs also have **no stable identity** — they are keyed only by config `name`
(`org_pack_config.py:166`) — and a charter pack's binding to its doctrine pack exists
only **per-activation** as `doctrine_pack_id` (`src/charter/activations.py:241`), never
as one pack-level pointer.

Left unaddressed, adding pack metadata would ship a **third** format and deepen the
fragmentation. The decision is whether to **unify** onto one schema or **bridge** the two.

## Decision Drivers

- **Single canonical authority** (charter governing principle): one description of a
  pack, not two that drift.
- **Trust/verifiability:** a `constituents[] + content_hash + manifest_hash` inventory is
  the substrate for the pack-trust / verified-distribution epic (#2539/#2543); two formats
  means two things to sign and verify.
- **Cost asymmetry:** three of the required gaps (built-in manifest, stable `pack_id`, the
  charter→doctrine binding) are net-new *regardless* of unify-vs-bridge; bridge avoids only
  the (mechanical, M-sized) migration of `artifact_counts` readers, at the permanent cost of
  a two-format "add every field twice" tax.
- **Lossless dominance:** `constituents[]` strictly dominates `artifact_counts` — counts are
  a derivable projection of the enumerated list, never the reverse.

## Considered Options

1. **Unify** — one `pack-manifest` schema for all pack types; enumerated constituents
   canonical; counts become a derived view; `synthesis-manifest.yaml` becomes the charter
   pack's instance (via a charter profile block).
2. **Bridge** — keep both formats, reconcile behind a read adapter, fill gaps per format.

## Decision Outcome

**Chosen: Unify.** Pack metadata is canonicalized on a single manifest schema for every
pack type, with two structural rules:

### 1. One schema, enumerated constituents, charter profile

`constituents: [{kind, id, path, content_hash}]` is the canonical inventory across all
packs. `artifact_counts` is **retired** as stored state and, where still needed, computed
from `constituents[]`. The charter bundle's extra fields (`mission_id`,
`bundle_content_hash`, `synthesizer_version`) live in an optional `charter:` **profile
block** on the same schema — not a forked format. `synthesis-manifest.yaml` becomes the
charter pack's generated manifest instance.

### 2. Two files: authored identity/lineage vs generated constituents

The pack-layout contract forbids authors editing the generated manifest
(`pack-layout.md:104`). Rather than fence an authored block inside a generated file, the
manifest is split:

- **`pack.yaml`** (authored, hand-edited): `pack_id` (stable identity, minted once —
  mirrors the `mission_id` ULID identity model), `pack_version`, `parent_pack`,
  `accompanies_doctrine_pack`, human metadata.
- **`pack.md`** (authored): human-readable pack description.
- **`pack-manifest.yaml`** (generated, never hand-edited): `schema_version`,
  `generated_by`/`generated_at`, `manifest_hash`, `constituents[]`, and the optional
  `charter:` profile block.

This matches the operator's original instinct ("a yaml + markdown pair accompanying a
pack"): the yaml+md are the *authored* meta + human doc; the generated constituent record
is their verifiable sibling.

### 3. Lineage delegates, never re-walks

`parent_pack` and `accompanies_doctrine_pack` **store** edges only. Resolution order is
delegated to the existing `src/charter/org_extends.py::resolve_extends_order` (the
canonical `extends:` resolver with cycle detection). A second walker is prohibited — it
trips the C-005 no-parallel-resolver ratchet (`org_extends.py:14-21`).

### Bridge is a migration tactic, not a destination

If the `artifact_counts`-reader migration proves deeper than expected, a bridge-then-unify
sequence is permitted **only** with a stated unify-by release; two permanent formats are
not an acceptable end state.

## Consequences

**Positive.** One canonical pack description; a single signing/verification target for
#2539; stable `pack_id` for trust and lineage keys; the charter→doctrine binding gains a
pack-level home; every future field is added once.

**Negative / cost.** Requires migrating `artifact_counts` readers to the derived view
(mechanical, M). Requires a new generator emitting `pack-manifest.yaml` for the built-in
pack from its per-kind `*.graph.yaml` `nodes:`. Introduces a `pack_id` minting/backfill
step for existing packs.

**Scope note.** This ADR fixes the *schema and split*; it is the first deliverable of
#2467's pack-manifest bullet and is sequenced with the pack-trust epic **#2539** (the
manifest is the verifiability carrier). The broad "compound packs" work in #2467 remains a
separate slice. Implementation decomposes into: WP-core (unify schema + built-in writer),
WP-identity (`pack_id`), WP-lineage (`parent_pack` delegation + `accompanies_doctrine_pack`),
WP-split (authored vs generated files).

## Delivery status (this slice)

Mission `pack-metadata-manifest-unification-01M052PT` shipped this ADR's schema and the
built-in-pack writer as a **library-first slice**; it does not yet mean all 4 pack types
emit the unified manifest on disk. Read the ADR's present tense above as "the decision," not
"the rollout" — the rollout is partial by design, tracked here:

**Shipped:**
- The unified `pack-manifest` schema and its models.
- The single hasher used for `manifest_hash` / `content_hash`.
- The built-in pack's generated `pack-manifest.yaml` (via `spec-kitty doctrine
  regenerate-graph`) plus its authored `pack.yaml` / `pack.md`.
- The lineage adapter — delegates to `org_extends.resolve_extends_order`, fail-closed — and
  its non-vacuous architectural ratchet guarding against a second walker.
- The `counts_by_kind` derive seam (a computed view over `constituents[]`).
- `pack_version` derive-else-fallback (authored value wins; generated value covers packs
  without one).

**Deferred to a future integration WP:**
- Org and fetched pack manifest **writers**, and the charter pack's on-disk unified
  emission — absorption ships as an **in-memory bridge only**, to keep NFR-005 readers
  green without forcing an on-disk format change yet.
- On-disk retirement of stored `artifact_counts` for org/fetched packs — still stored today
  because `_has_recognisable_pack_manifest` requires the key.
- The `pack_id`-keyed resolver cutover and the retirement of name-based lookup — `pack_id`
  ships now as an optional field plus a validator and an idempotent backfill, not yet the
  resolution key.
- Wiring the lineage / `accompanies_doctrine_pack` resolvers and `absorb_synthesis_manifest`
  into production callers.
- The `accompanies_doctrine_pack` cutover away from per-activation `doctrine_pack_id`.

A downstream reader should not assume all 4 pack types already emit the unified manifest —
only the built-in pack does, as of this slice.
