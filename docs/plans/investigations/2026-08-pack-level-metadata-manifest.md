---
title: 'Pack-level metadata manifest: constituent parts + lineage'
description: 'Corroborates one pack-level manifest recording each pack''s enumerated constituents and parent/lineage — a consolidation of two divergent existing manifests, not a new format.'
doc_status: deprecated
updated: '2026-08-16'
related:
- docs/plans/3-2-x-milestone-roadmap.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/README.md
- docs/adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md
---

> **RETIRED (shipped)** — this investigation's unify-vs-bridge proposal was ratified in ADR
> [`2026-08-16-1`](../../adr/3.x/2026-08-16-1-pack-metadata-manifest-unification.md) and
> shipped (library-first slice) by mission `pack-metadata-manifest-unification-01M052PT`
> (PR #3507; closes #3500–#3503, slice of keystone #2467). Retained for historical
> reference; do not consult for current behavior.

# Pack-level metadata manifest: constituent parts + lineage

**Scope:** a `proposed` investigation on the distil-then-retire working surface —
**not** a canonical ADR. It corroborates an operator design proposal (a pack-level
manifest recording constituent parts + parent/lineage, for doctrine packs and the
charter pack that accompanies one) against the shipped code, and records the
readiness read + gap list. The unify-vs-add decision and the manifest schema, once
settled, belong in an ADR under `docs/adr/3.x/`. Evidence base:
`work/bug-triage-research/alphonso-pack-metadata-review.md` (architect-alphonso,
2026-08-16).

## The proposal

> Each **doctrine pack's** meta-information should carry a record of **its
> constituent parts** and/or its **parent pack**. The same applies to a **charter
> pack** — a `yaml` + `markdown` pair that *accompanies* a doctrine pack.

I.e. first-class **pack-level metadata**: a manifest recording (a) what a pack
contains, and (b) lineage (parent pack / which doctrine pack a charter pack
accompanies).

## Verdict: SOUND, with one reframe

The model is correct, but the load-bearing finding is that **~70% of it already
exists** — this is a *consolidation*, not a greenfield feature. The real risk is
shipping a **third** manifest format. Two pack manifests already ship and **disagree**:

| Manifest | Where | What it records | Gap vs. the proposal |
|---|---|---|---|
| `pack-manifest.yaml` (org doctrine packs) | `src/specify_cli/doctrine/snapshot.py:157-180` | `pack_version`, `source_*`, **`artifact_counts`** (per-kind counts, `:195-212`); normative per `…/contracts/pack-layout.md:23,102-109` | counts, not enumerated; **no lineage**; not written for built-in or git-managed packs (`pack-layout.md:104-107`) |
| `synthesis-manifest.yaml` (charter/project bundle) | `src/charter/synthesizer/manifest.py:46-112` | **enumerated `artifacts:[{kind, slug, path, provenance_path, content_hash}]`** + `manifest_hash` self-integrity (`:107`), `bundle_content_hash`, `schema_version`, `mission_id` | already *is* the "constituent parts" model — but charter-only |

**The built-in pack has no pack-level manifest at all** — `packs/built-in/*.graph.yaml`
carry only `schema_version`/`generated_at`/`generated_by` headers
(`directive.graph.yaml:1-3`); there is no `references.yaml`, `pack.yaml`, or root
manifest anywhere.

### What already exists (reuse, don't reinvent)

- **Constituent parts** live implicitly in three places: the DRG `nodes:` URN
  inventory per kind, the `artifact_counts` bucket (org), and the enumerated
  `artifacts[]` (charter only). A surfacing/unification problem, not greenfield.
- **Parent/lineage** is already modeled twice: pack→pack via `extends:` on
  `OrgCharterPolicy` (`src/specify_cli/doctrine/org_charter.py:147-155`), resolved
  with cycle detection by `src/charter/org_extends.py::resolve_extends_order`; and
  profile-level via the `specializes_from` DRG edge
  (`src/doctrine/drg/validator.py:50-51`). A manifest `parent_pack` field **must
  delegate** to `org_extends.py` — a second walker trips the C-005 no-parallel-
  resolver ratchet (`org_extends.py:14-21`).

### The one genuinely thin spot — the charter↔doctrine binding

This is exactly what the proposal names. A charter pack is not a yaml+md pair; it is
`charter.yaml` + `charter.md` + `graph.yml` + `synthesis-manifest.yaml` +
`provenance/`. And the binding to a doctrine pack exists only **per-activation** as
`doctrine_pack_id` in the `(activation_context, doctrine_pack_id, artifact_id,
artifact_kind)` 4-tuple (`src/charter/activations.py:241,305`). There is **no single
pack-level "this charter accompanies doctrine pack Y" pointer** — a real, unfilled gap.

## Recommended design

**Extend `pack-manifest.yaml` into the single pack-level manifest for ALL packs**
(built-in, org, fetched, charter), promoting `synthesis-manifest.yaml`'s
`ManifestArtifactEntry` as the shared "constituent" sub-schema. Shape:

- `pack_id` — stable identity (**missing today**; org packs are keyed only by config
  `name`, `org_pack_config.py:166` — mirror the `mission_id` identity model).
- `pack_version`, `schema_version`, `generated_by`, `generated_at`, `manifest_hash`
  (self-integrity; reuse `manifest.py:107`).
- `parent_pack` — **delegate** semantics to `org_extends.resolve_extends_order`.
- `accompanies_doctrine_pack` — the missing charter→doctrine pack-level binding.
- `constituents: [{kind, id, path, content_hash}]` — enumerated, superseding
  `artifact_counts`.

**Authored-vs-generated split (a design decision to settle first).** The pack-layout
contract forbids authors editing `pack-manifest.yaml` (`pack-layout.md:104-105,138`),
but `parent_pack` / `accompanies_doctrine_pack` are **authored** data while
`constituents` / hashes are **generated**. The manifest must carry an authored
section and a generated section, or the two concerns collide.

## Readiness read

**Closer than it looks on *data*, further on *unification*.** Every ingredient —
enumerated constituents, per-artifact content hashes, a self-integrity manifest hash,
pack `extends:` lineage, and a charter→doctrine `doctrine_pack_id` reference — already
ships, which is what makes it *feel* ready. What makes it *less* ready: the data lives
in two schemas that disagree (counts vs. enumerated), the built-in reference pack that
everything extends has no manifest, "parent pack" is an org-charter concern rather than
a pack-root field, and there is no stable `pack_id` to hang trust on. A naive "add a
pack manifest" ships a third format and deepens the fragmentation. **Ready to roll only
*after* the unify-vs-add decision; the engineering after that is modest.**

## Gaps (ordered, load-bearing first)

1. **Unify the two divergent schemas** (counts `snapshot.py:195` vs. enumerated
   `manifest.py:46`) before adding anything. Skip it → ship a third format. **Size: M**
   (pick the enumerated shape canonical; migrate `artifact_counts` readers).
2. **Built-in pack has no pack-level manifest** (`packs/built-in/`). It is the
   reference every org pack extends — no uniformity without it. **Size: M** (new writer
   wired into the build/upgrade path).
3. **No stable `pack_id`** (packs keyed only by config `name`, `org_pack_config.py:166`).
   Blocks trust/verifiability + lineage keys; mirror the `mission_id` identity model.
   **Size: S**.
4. **No single charter→doctrine-pack binding** (only per-activation `doctrine_pack_id`,
   `activations.py:241`). The proposal's "accompanies" needs one pack-level pointer.
   **Size: S**.
5. **`parent_pack` must reuse `org_extends.py`** (`extends:` in `org-charter.yaml`,
   `org_charter.py:147`) or trip the C-005 no-parallel-resolver ratchet. **Size: S–M**.
6. **Authored-vs-generated split** in the manifest (contract forbids authoring the
   generated file, `pack-layout.md:104`). Small code, load-bearing design decision to
   settle first. **Size: S**.

## Decision needed from the operator

The first move is a **decision, not code**: **unify on `pack-manifest.yaml` with the
enumerated `constituents[]` shape (recommended), or keep two manifests and bridge.**
Gaps #1–#2 are the real work; #3–#6 are small once the call is made. The design is
trust-adjacent — the constituent-parts + content-hash manifest is the natural carrier
for the pack-trust / verified-distribution epic **#2539** and DIRECTIVE_018 doctrine
versioning, so it should be sequenced with (or under) that epic rather than as an
isolated line.

## Open questions for the operator

- **Unify vs. bridge** (above) — the load-bearing call; recommended: unify.
- **Home** — a member of the pack-trust epic #2539, or its own line? (Recommended:
  under #2539, since the manifest is the verifiability carrier.)
- **`pack_id` minting** — reuse the ULID `mission_id` machinery, or a pack-specific
  scheme? (Recommended: reuse the identity model for consistency.)
