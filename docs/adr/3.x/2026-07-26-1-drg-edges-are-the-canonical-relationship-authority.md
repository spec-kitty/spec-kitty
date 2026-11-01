---
title: 'ADR: DRG edges are the canonical artefact-relationship authority; inline `references:` blocks are pre-DRG residue to be migrated and retired'
description: 'DRG edges become the only artefact-relationship vocabulary; 559 inline `references:` entries migrate to `*.graph.yaml` fragments and the field closes to relationship growth.'
status: Accepted
date: '2026-07-26'
doc_status: active
kind: ADR
updated: '2026-07-26T00:00:00Z'
---

**Status:** Accepted

**Date:** 2026-07-26

**Deciders:** Operator (Stijn Dejongh), who identified the drift directly: *"the doctrine
schema and assets predate the DRG canonical system; the yaml files often contain references
to other artefacts that are to be migrated to DRG edges/relationships."* Recorded during
the #2935 doctrine-authoring session, after the finding invalidated an in-flight "fix".

**Technical Story:** raised while authoring the test-quality doctrine series
([#2935](https://github.com/Priivacy-ai/spec-kitty/issues/2935)) on PR
[#2936](https://github.com/Priivacy-ai/spec-kitty/pull/2936); triggered by an
asset-support finding on [#2918](https://github.com/Priivacy-ai/spec-kitty/pull/2918).
Continues the excision begun by mission `excise-doctrine-curation-and-inline-references-01KP54J6`.
Sibling ADRs: [2026-07-18-1](2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md)
(the authoring-authority + extractor-retirement pattern this ADR applies to the doctrine layer),
[2026-07-22-1](2026-07-22-1-gate-binding-content-vs-relationship.md) (content-vs-relationship
principle), [2026-07-21-1](2026-07-21-1-in-tension-with-drg-edge.md) (tension relations).

---

## Context and Problem Statement

The doctrine artifact **schemas** (`src/doctrine/schemas/*.schema.yaml`) and the **assets**
layout predate the Doctrine Relationship Graph (DRG). They were designed when an artefact
declared its own relationships inline, in its own YAML body. The DRG later introduced typed,
traversable edges as the way relationships are modelled. Both surfaces are still live, and
the doctrine layer therefore has **two authorities for one concept**.

**Surface A — inline `references:` blocks.** 139 built-in artifact YAMLs carry a
`references:` list of `{type, id, when?}` entries. Four schemas (`directive`, `paradigm`,
`procedure`, `tactic`) bless this shape via a `<kind>_reference` definition whose `type`
property carries a **hand-copied enum of doctrine kinds**.

**Surface B — DRG edges.** 14 per-kind `*.graph.yaml` fragments under `src/doctrine/`
holding ~774 typed edges over the `Relation` vocabulary
(`requires`/`suggests`/`scope`/`refines`/`rejects`/`in_tension_with`/…).

Crucially, **B is not independent of A**: every fragment is stamped
`generated_by: drg-migration-v1`, and `drg/migration/extractor.py` *derives* edges by walking
the inline `references:` blocks (the reference passes at lines ~387–636), supplemented by
`drg/migration/hand_authored_overlay.py` for edges that have no inline source. So the inline
blocks remain the de-facto authoring surface for most of the graph, and the graph is largely a
**build output** of the surface it was meant to replace.

A partial excision already landed: mission
`excise-doctrine-curation-and-inline-references-01KP54J6` hard-rejects the *scalar* inline
ref fields (`tactic_refs`, `styleguide_refs`, …) with `InlineReferenceRejectedError`. The
**structured** `references:` block survived that pass — the residue this ADR addresses.

Four consequences of the split were observed empirically, not theorised:

1. **The duplicated kind enum has already drifted.** All four schema copies omit `asset` and
   `glossary_pack`; the `tactic` copy has drifted further still, additionally missing
   `agent_profile` and `mission_step_contract`. So `ArtifactKind.ASSET` — a first-class kind
   with shipped built-in artifacts — **cannot be named from an artefact body at all**. On
   #2918 this read as an "asset support is not end-to-end" bug. It is not: it is the legacy
   surface correctly refusing to grow. Widening the enum would have entrenched the second
   authority, and was abandoned mid-change once the operator named the drift.
2. **The migration instruction the system prints is unfollowable.** `InlineReferenceRejectedError`
   tells operators to *"add edge {source, target, relation: requires} to `src/doctrine/graph.yaml`"* —
   but mission #2680 sharded that monolith into per-kind fragments and **`src/doctrine/graph.yaml`
   no longer exists**. **18 files** repeat the stale path — `.py` models, errors and exceptions,
   four READMEs, a shipped tactic, and the brownfield paradigm's own notes. The one piece of
   guidance pointing from the legacy surface to the canonical one points at nothing. (An earlier
   revision said "ten"; measured, it is 18. Note some mentions are *deliberate* — this ADR and the
   `doctrine-daphne` profile name the path in order to forbid it — so a naive grep gate would
   false-red, and `.kittify/doctrine/graph.yaml` is a live project-tier path that must not be
   swept in.)
3. **The inline shape cannot express the modern vocabulary.** `references:` carries only
   `type`/`id`/`when` — there is no relation field. Every relation richer than "related to"
   (`refines`, `rejects`, `in_tension_with`, `reconciles_tension`) is *inexpressible* inline
   and must be hand-authored as an edge. Measured on the shipped graph: `suggests` 332,
   `requires` 259, `scope` 157, `rejects` 8, `instantiates` 8, `specializes_from` 4,
   `reconciles_tension` 3, `in_tension_with` 2, `applies` 1, and **`refines` 0** — first-class
   since #2079, never yet exercised in a built-in fragment.
4. **Relationship semantics get flattened on the way in.** Because an inline entry has no
   relation, the extractor must *infer* one per kind (e.g. `_relation_for_procedure_reference`).
   The authored intent and the resulting edge type are decided in different files.

## Decision Drivers

* **Single canonical authority** (charter governing principle) — one owning source per
  surface. Two relationship authorities is the exact smell the principle names, and
  "reconcile/extend the existing authority" means extending the DRG, not the residue.
* **Content vs relationship** (ADR 2026-07-22-1) — an artefact's YAML body owns its
  *content*; relationships between artefacts are *edges*. The inline block is a body field
  doing a relationship's job.
* **No legacy compat branches in resolvers** (ADR 2026-07-01-1) — the answer to a
  legacy surface is retirement on a migration path, not indefinite parity.
* **Authoring-authority + extractor retirement** (ADR 2026-07-18-1) — the doctrine layer
  faces structurally the same call the charter layer already made: stop deriving canonical
  structure from a legacy authoring surface, and retire the extractor that does it.
* **Intent dominates over capability** — fix the tooling to serve the intended model; do not
  relabel artefacts, or widen a deprecated schema, to fit what currently works.

## Considered Options

* **Option 1 (chosen)** — Pin DRG edges as the sole relationship authority; fix the stale
  migration hint; **and migrate all 559 relationship entries now**, retiring **all** edge
  production behind a structured-diff proof (see the Amendment).
* **Option 2** — Keep both surfaces, and bring the inline surface to full parity (widen the
  four kind enums, add a `relation:` field to `references:`, keep deriving the graph).
* **Option 3 (initially chosen, then withdrawn)** — Pin the direction and *freeze* the inline
  surface, but defer the migration and the pass retirement to follow-up work.
* **Option 4** — Declare the inline blocks canonical and treat the fragments as pure build
  output (invert the other way).

## Decision Outcome

**Chosen option: 1.**

The end state this ADR pins:

1. **DRG edges are the single canonical authority for artefact→artefact relationships.**
   Relation semantics live in `doctrine.drg.models.Relation`. No schema, body field, or
   sidecar may declare a second relationship vocabulary.
2. **The inline `references:` block stops carrying artefact relationships.** Every one of the
   559 relationship-bearing entries migrates to a hand-authored edge in the per-kind
   `*.graph.yaml` fragment, in this mission. The field survives only for raw non-artefact
   material (14 entries), and is closed to growth in every case: no new artefact adds a
   relationship entry.
3. **The four `<kind>_reference.type` enums are frozen, not fixed.** A kind that cannot be
   named inline is *correct* behaviour, not a defect. Specifically: **do not add `asset` (or
   any kind) to those enums** — the pull request that tries is repeating the mistake this ADR
   exists to stop. Assets are referenced via `requires`/`suggests` edges only.
4. **The migration hint must point at the real layout.** `InlineReferenceRejectedError` and
   the ~10 sites repeating `src/doctrine/graph.yaml` are corrected to the sharded per-kind
   fragment path (`src/doctrine/<kind>.graph.yaml`). Guidance that cannot be followed is
   worse than none.
5. **The extractor's reference passes are retired in this mission**, following ADR 2026-07-18-1:
   migrate each file's relationship entries into hand-authored edges (preserving the
   per-kind inferred relation *explicitly*, so authored intent and edge type stop living in
   different files), then delete the reference-extraction passes so fragments are authored,
   not derived. Sequenced so the proof comes first: commit the baseline manifest → migrate →
   assert the structured diff → prove pass deletion by observed RED (in-process ablation).
6. **New doctrine artefacts are edge-native from birth.** An artefact authored today declares
   zero inline references and all its relationships as edges.

### Scope: the migration happens now, in this mission

An earlier revision of this ADR deferred the migration of the inline blocks to follow-up work,
on the grounds that it is wide and needs its own idempotency proof. **That deferral was
withdrawn by the operator**, and the reasoning is worth recording because it generalises:

> We are working on the `3.2.6`-unreleasable issues, and have been extreme boyscouting for over
> a week. We will continue this practice and philosophy until 3.2.6 is stable, and we covered as
> many of the existing "ticking timebombs" as we can. Similar to how we stopped greenwashing, we
> desperately need to stop deferring structural issues.

The deferral was also a weak argument on its own terms: "it needs a proof first" is a reason to
**build the proof**, not to postpone.

**Measured composition** (derived, never hand-counted — run
`PYTHONPATH=src python scripts/doctrine/inline_reference_inventory.py`; the FR-015 gate imports
that module rather than restating a literal). **171 files carry 761 entries across six inline
surfaces**, in three dispositions:

| Disposition | Entries | Surfaces |
| --- | --- | --- |
| **MIGRATE** — denotes an artefact→artefact relationship | **559** | `references` 414 · `steps[].references` 15 · `context-sources.directives` 67 · `directive_refs` 34 · `tactic-references` 29 |
| **GOVERNANCE** — zero DRG edges; seeds the charter closure. **Do not migrate** | 188 | `directive-references` 68 · `context-sources.{additional,doctrine-layers,tactics}` 120 |
| **RAW_MATERIAL** — path strings to non-artefact files. **Keep** | 14 | enumerated `(file, path)` allowlist |

**An earlier revision of this ADR said 414, in six places. That figure was the top-level
`references:` row alone** — correct as far as it went, mistaken as a total. It missed 15
step-level entries (in 7 tactic files, **4 of which carry no top-level block at all**, so a
file-driven migration would never have opened them) and it missed five sibling surfaces entirely,
including `directive_refs`, which mints 34 real edges and is schema-blessed in 12 paradigms.

The **GOVERNANCE** row is the load-bearing correction. `directive-references` produces no DRG
edges but is the seed set for the entire charter governance closure, so sweeping it would empty
every profile-routed prompt's directives while byte-identical fragments, golden counts, and a
zero-structured-entries gate all stayed green. That is this ADR's own defect class — silence —
reproduced by its remediation, and it is why the scope must name surfaces rather than say "all
inline relationships".

**The `references:` field is not deleted outright.** 14 entries point at raw reference material —
`src/doctrine/skills/README.md`, `docs/adr/...`, Divio templates, an action `index.yaml`. Those
denote no artefact relationship, produce no edge today (`_resolve_path_ref` fails closed on
them by design, NFR-003), and the doctrine README explicitly sanctions carrying raw reference
material. Forcing them into edges would invent relationships that do not exist — the same
category error as widening the kind enum.

The end state is therefore **not** "no `references:` blocks" but the sharper invariant:

> Zero MIGRATE-class entries across all five migrating surfaces. A `references:` list may contain
> only plain path strings to **non-artefact** material. The 188 GOVERNANCE entries are untouched.

This is gateable, and it is what the confirmation criteria below assert.

### Amendment (2026-07-26) — three decisions taken after this ADR was first accepted

This ADR was Accepted before three operator rulings that change its scope and its proof. They are
recorded here because **this ADR, not a spec table, is the citable record** (DIRECTIVE_003), and an
implementer reading the original text would have built the wrong proof against a scope 26% too
small.

1. **Full retirement, not reference passes only.** `generate_graph` has nine steps; the reference
   passes are one. The others produce ~215 further edges — 157 `scope` from action indexes, 21
   mission-type projection, 8 template instantiation, 13 from a *second* hardcoded Python registry
   (`_CURATED_ARTIFACT_EDGES`, holding all four `specializes_from`), plus a calibrator that
   **synthesises** `scope` edges from the inequality `|review| ≥ 0.80 × |implement|`. **All 774
   edges become authored.** Node discovery stays derived; the extractor becomes a node minter plus
   validator. Both Python edge registries are absorbed and deleted — otherwise the surface count
   holds flat at 11 while claiming consolidation.
2. **The proof is a structured diff, not byte-identity.** Byte-identity was the original invariant
   and it is withdrawn: preserving the 68 procedure rationales and the 219 reference labels breaks
   it *by design*, and a byte proof would therefore pressure the migrator into **deleting authored
   content to make the proof pass**. The invariant is now "the regenerated graph differs from the
   committed pre-migration baseline manifest only by the enumerated, ledgered deviations". Two
   further corrections ride along: the baseline must be a **committed** manifest written before any
   YAML is edited (otherwise "regenerate and compare" degenerates into
   `regenerate(tree) == regenerate(tree)`, a tautology of determinism blind to content loss), and
   pass deletion is proven by an **observed RED via in-process ablation**, because as a git
   sequence it is unachievable — the extractor must be alive as the migration oracle, and once the
   authored tier carries the edges the deletion is a no-op again.
3. **Labels move to `aliases` on artefacts, not `DRGEdge.label`.** Measured: the 219 label
   occurrences collapse to **102 distinct artefacts**, and the 8 targets carrying more than one
   label are genuine synonym sets. They were never edge metadata — they are artefact names repeated
   at every pointer. `aliases: list[str]` on the artefact deduplicates them, merges the 8
   disagreements into legitimate alias lists, enables grep now and semantic search later, and
   removes a `DRGEdge` schema change with a six-consumer ripple.

Sibling: [ADR 2026-07-26-3](2026-07-26-3-impacts-edge-subsumes-in-tension-with.md) adds
`Relation.IMPACTS` and `is_symmetric` to the same edge model. `is_symmetric` is expanded **by the
generator**, so the authored tier holds one edge and the cache holds both directions — consistent
with the source-plus-cache split this ADR's amendment relies on.

### Consequences

#### Positive

* One authority for relationships; the drift class (four hand-copied enums) stops mattering
  because the surface they guard is closed rather than widened.
* The `#2918` "asset support" finding is correctly reclassified from *bug* to *the deprecated
  surface working as intended*, which retires an entire strand of would-be remediation.
* Edge-native authoring gets the full relation vocabulary — including `refines`, which the
  inline shape could never express.
* Operators receive a migration hint that names a file that exists.

#### Negative

* Authoring relationships is now a two-file edit (artefact body + graph fragment), which is
  less locally-obvious than an inline list. Accepted: it is the cost of typed relations.
* The migration touches 139 artefact files and the generated fragments in one change — a large
  mechanical diff inside an already-wide PR. Mitigated by the structured-diff invariant plus the
  inventory gate, which together make the migration verifiable by assertion rather than by
  reviewing 559 individual edge moves.
* The 14 surviving raw-material path entries mean `references:` does not disappear entirely, so
  a reader must know the distinction between "a path to a doc" and "a relationship". The gate
  encodes it, and this ADR explains it.

#### Neutral

* `hand_authored_overlay.py` becomes the *primary* authoring path rather than a supplement;
  its name will read oddly once extraction retires and should be revisited then.
* The `Relation` vocabulary itself is untouched by this ADR.

### Immediate application to #2935 (the mission that surfaced this)

* The artefact-series proposal's edge-based design is **correct by construction** — it already
  routes asset references through `requires`/`suggests` edges rather than a `type: asset`
  body field. No redesign needed.
* The `DIRECTIVE_041` intent split must **not** add inline references. `041` is itself one of
  the legacy carriers (5 structured entries), so those five migrate to edges with the rest;
  the new `DIRECTIVE_041 --refines--> paradigm:tests-as-scaffold-not-friction` link is
  authored as an edge from the start. Note the ordering constraint: because editing `041` is
  its own reviewed change, do its migration *with* the intent split rather than as an
  anonymous line in the bulk pass.
* That edge is the **first `refines` edge in any built-in fragment** (histogram above: 0).
  Round-trip verification through the org→DRG bridge on regeneration is therefore a real
  risk item, not a formality — #2079 fixed a silent `refines`→`applies` downgrade, and
  nothing built-in has exercised the fix.

### Confirmation

* **Zero** structured `{type, id}` reference entries remain anywhere under `src/doctrine/`, and
  **zero** remaining path-string entries resolve to a built-in artefact via `_resolve_path_ref`.
  The only surviving entries are raw non-artefact paths. Enforced by a gate, not by inspection.
* The regenerated graph differs from the **committed** pre-migration baseline manifest only by
  the enumerated, ledgered deviations (preserved rationales and labels; any relation changed by
  review). Every other node, edge, relation, `when` and `reason` is unchanged. Completeness is
  asserted separately by the inventory gate — the diff proves preservation, not completion.
* The four `<kind>_reference.type` enums are byte-identical to their pre-ADR state (no kind
  added), and a comment in each schema marks the definition frozen with a pointer here.
* No source site tells an operator to edit `src/doctrine/graph.yaml`; the rejection-hint
  regex and its schema fixture name the per-kind fragment path.
* During the migration, at every increment: regenerating fragments after migrating a file produces a
  **zero diff**, proving the hand-authored edge preserved the previously-inferred relation
  before any extraction pass is deleted.

## Pros and Cons of the Options

### Option 1 — Pin edges as canonical and complete the migration now (chosen)

**Pros:** ends the two-authority condition outright rather than documenting it; the doctrine
layer has exactly one relationship authority when the PR lands, so no reader has to hold
"which surface is live?" in their head. The structured-diff invariant plus the inventory gate make
a 559-entry mechanical migration *cheaper to verify than to review* — assertions cover every
entry. Deleting the extraction passes removes the mechanism that keeps re-deriving the legacy
surface, so the class cannot regrow. Also reclassifies the #2918 finding and unblocks #2935.
**Cons:** a large mechanical diff inside an already-wide PR; relationship authoring becomes a
two-file edit; `references:` survives for raw material, so the field does not vanish entirely.

### Option 2 — Full parity for the inline surface

**Pros:** locally-obvious authoring; no migration debt; the #2918 finding becomes a real fix.
**Cons:** entrenches two authorities permanently and *grows* the one that is deprecated;
requires adding a `relation:` field, i.e. re-implementing the `Relation` vocabulary in schema
form — a second authority for edge semantics. Directly contradicts single-canonical-authority
and ADR 2026-07-01-1. Rejected.

### Option 3 — Pin the direction, defer the migration (initially chosen, then withdrawn)

**Pros:** narrow change now; the wide mechanical migration sits behind its own proof and its
own review; the P0 and the #2935 series land sooner.
**Cons — and these carried the decision:** it leaves two readable surfaces live and the
extraction passes still *actively deriving* the deprecated one, so the class keeps regenerating
itself while the ADR asserts it is closed. "Frozen" without enforcement is the same posture that
produced nine dead files and the #2918 layout error. The stated blocker — "it needs an
idempotency proof first" — is an argument for building the proof, which turned out to be a
single byte-comparison, not a research project.

Withdrawn by the operator on the explicit ground that deferring structural work is the same
failure mode as greenwashing a test: it converts a known defect into an invisible one and
relies on a future maintainer having the same context. While `3.2.6` is unreleasable, the
standing posture is to clear ticking timebombs in the mission that finds them.

### Option 4 — Declare inline blocks canonical; fragments are pure build output

**Pros:** matches how much of the graph is *actually* produced today; single authoring site.
**Cons:** the inline shape provably cannot express the modern relation vocabulary
(`refines`/`rejects`/tension), so it would cap the DRG at its weakest historical expressiveness
and require inferring relations forever. Rejected as the wrong direction of travel.

## More Information

* Inline-ref excision precedent: mission
  `excise-doctrine-curation-and-inline-references-01KP54J6`; negative fixtures in
  `tests/doctrine/test_inline_ref_rejection.py`.
* Extraction passes: `src/doctrine/drg/migration/extractor.py`; overlay:
  `src/doctrine/drg/migration/hand_authored_overlay.py`; fragment sharding: mission #2680.
* Relation vocabulary: `src/doctrine/drg/models.py::Relation`.
* Test-quality series proposal: `docs/plans/doctrine/test_quality/doctrine-artefact-series-proposal.md`.
