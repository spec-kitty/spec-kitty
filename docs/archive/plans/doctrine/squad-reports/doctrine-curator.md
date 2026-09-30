---
title: Doctrine-curator lens — exemptions, accreditation, provenance
description: "Doctrine integrity review of the creed design: the per-kind exemption table, the value_impact vs value_bias split, accreditation placement, and the gates it trips."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/creed-and-values-design-hardened.md
- docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md
---
# Doctrine-curator lens — exemptions, accreditation, provenance

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> Squad report, 2026-07-26. Profile-loaded (`doctrine-daphne`), read-only. Evidence base for
> [`creed-and-values-design-hardened.md`](../creed-and-values-design-hardened.md).
> Directives applied: DIRECTIVE_044 (canonical sources), DIRECTIVE_003 (decision
> documentation), DIRECTIVE_032 (conceptual alignment), DIRECTIVE_018 (doctrine versioning),
> DIRECTIVE_043 (close defect classes by construction).

## Findings

**[BLOCKER]** `creed-and-values-design-as-proposed.md:47-49` — "all behavioural doctrine
artefacts (assets and templates are exempt)" diverges from the canonical exclusion set
`_NON_AUGMENTATION_ELIGIBLE_KINDS` (`src/doctrine/artifact_kinds.py:201-203`), which excludes
`{TEMPLATE, ASSET, ANTI_PATTERN}`. The design omits `anti_pattern` — the one kind structurally
incapable of carrying the field. It also never defines "behavioural", leaving `toolguide` /
`mission_step_contract` / `glossary_pack` unruled. **Recommendation:** express the exemption set
as a named frozenset in `artifact_kinds.py` per that file's own docstring rule at `:30-32` ("no
second kind enumeration may be re-declared elsewhere").

**[BLOCKER]** `src/doctrine/drg/models.py:292, :328` — `DRGNode` and `DRGEdge` have **no
`model_config` at all** → Pydantic v2 default `extra="ignore"`. Part 2's `impacts` field would be
**silently dropped on load**. The `DRGNode.tags` docstring at `:305-311` documents this exact
hazard verbatim: `tags` had to be explicitly modelled "so an authored `tags: [...]` key
round-trips instead of being silently dropped on load." **Recommendation:** add
`extra="forbid"` to both before any edge-field work, with the round-trip assertion in the same
commit.

**[BLOCKER]** `src/doctrine/drg/migration/extractor.py:1210-1217, :1219-1229` — `_node_to_dict`
and `_edge_to_dict` are explicit field-by-field writers (`urn`/`kind`/`label`/`tags`;
`source`/`target`/`relation`/`when`/`reason`). Even a correctly modelled `impacts` vanishes at
graph regeneration. Note `DRGNode.provenance` / `DRGEdge.provenance` are **already** deliberately
omitted here, so graph-level provenance does not survive regeneration and cannot be relied on.
**Recommendation:** model + writer + round-trip test in one commit, or do not add the field.

**[BLOCKER]** `src/doctrine/agent_profiles/profile.py:254` — `AgentProfile.model_config =
ConfigDict(populate_by_name=True)`. No `extra="forbid"`, no `frozen`. A `value_bias:` key loads
and **silently vanishes at model level**; only the generated `agent-profile.schema.yaml:7`
`additionalProperties: false` catches it, and only where the schema validator actually runs.
**This is the single most likely way this design ships inert.**

**[HIGH]** `src/charter/schemas.py:286` — `CharterYaml.model_config = ConfigDict(frozen=True,
extra="forbid")`. A `creed:` key at the root of `.kittify/charter/charter.yaml` is **rejected
today**. **Recommendation:** add a typed `creed: CreedConfig | None = None`. Do **not** route it
through the untyped `overrides: dict[str, Any]` escape hatch at `:305` — that reproduces the
unvalidated-slot problem. If the creed lives in a separate `creed.yaml`, it needs its own model
**and** a place in `charter/hasher.py` + `charter/versioning.py` or it never participates in
charter freshness. **That is Part 3's real unstated gap.**

**[HIGH]** `creed-and-values-design-as-proposed.md:41-52` — one concept covers two semantics: a
**weight** ("how important is this to us", `:43-45`) and a **delta** ("how does this
support/weaken", `:46-49`). §5.1's own analysis says why they differ. Deltas compose by
summation; weights do not. **Recommendation:** two fields, two Pydantic types.

**[HIGH]** `src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml` — **zero
attribution**: no `notes` block, no sddevelopment/Crossland provenance, no URL. Line 61 cites
"the first-order impact matrix from the AMMERSE practice article" — an unresolvable external
pointer with no toolguide. Both an unaccredited use of a trademarked system and an undocumented
external reference. **Close in the same change** — it is the artifact a reader lands on when
asking "what are these seven axes?", so it is where accreditation is actually *read*. Cheapest,
highest-value item on the list.

**[HIGH]** `LICENSE` + repo root — `LICENSE` is MIT, "Copyright GitHub, Inc."; the repo does not
assert its own authorship there. There is **no `NOTICE` file**. Appending an AMMERSE trademark
line to this LICENSE would be actively misleading about who attributes what.
**Recommendation:** create `NOTICE` at repo root; **verify it is in the sdist/wheel packaged
data** or the accreditation does not ship to consumers — precisely the "so it is not lost"
failure mode.

**[HIGH]** `src/doctrine/anti_pattern.graph.yaml:5-33` — `anti_pattern` nodes carry exactly
`urn`/`kind`/`label`/`tags`. There is **no field able to hold a rationale**, and the design makes
rationale mandatory. An anti-pattern literally cannot satisfy the design's own invariant.
Compounded by `extractor._KIND_MAP` (11 entries — `anti_pattern` absent), so any such edge
vanishes at extraction. **Exempt.** A negative-only vector is the natural *form* for an
anti-pattern and that is exactly why it must not be **authored** — it is derivable as the
sign-flip of the artifact that `rejects` it. Authoring it duplicates that vector with an
independent drift surface and re-creates the field-authored-relationship shape the repo excised.

**[MEDIUM]** `scripts/generate_schemas.py:4-16` — the design treats "`additionalProperties:
false` on all seven schemas" as seven obstacles. The schemas are **generated** from the Pydantic
models ("the single source of truth"); the flag is a consequence of `extra="forbid"`. One action,
not seven. **But** no `generate_schemas` reference was found in `.github/workflows/` — only
`tests/doctrine/agent_profiles/test_schema_generation.py:9`. If `--check` is not CI-wired, a
field can exist in the model and not in the schema.

**[MEDIUM]** `src/doctrine/directives/models.py:52-68` — `Directive` has **no `notes` field**.
`notes` exists on only 2 of 12 kinds — `tactic` and `procedure`. So the existing "Adapted from
patterns.sddevelopment.be" credit pattern is structurally **unavailable** on the majority of
kinds that would carry a value vector. **Accreditation must live on the value-set artifact,
referenced by id — not replicated as prose per artifact.**

**[MEDIUM]** `src/doctrine/import_candidates/models.py` — `CurationImportCandidate` and all four
sub-models are `frozen=True` **without** `extra="forbid"`, unlike `LegacyImportCandidate`.
Unknown keys on the record type meant to carry provenance are silently ignored. Also **zero
authored instances exist on disk** — the type is itself a slot-without-a-producer. The 36-vector
import is its first real producer; **the design should claim this benefit and does not.**

**[MEDIUM]** `creed-and-values-design-as-proposed.md:54-60` — Part 2 straddles two incompatible
readings: (a) **add** `impacts` alongside `in_tension_with`, or (b) **replace** it. (a) is
additive and cheap — no new `Relation` member, so `RELATION_DESCRIPTIONS` completeness and
`test_relation_doc_parity` do **not** fire, and `DRGEdge.reason` already establishes
free-text-on-edge precedent. (b) trips both, plus `scan_unreconciled_tensions()`
(`src/charter/consistency_check.py:977`) and requires an ADR superseding `2026-07-21-1`.
**Pick (a) explicitly and say so in the doc.**

**[MEDIUM]** Pre-existing kind-universe divergence — **ten** lists: `ArtifactKind` = 12;
`_NON_AUGMENTATION_ELIGIBLE_KINDS` excludes 3; `CHARTER_KIND_TOKENS` = 9 + mission-type;
`NodeKind` superset; `extractor._KIND_MAP` = 11; `generate_schemas._REFERENCE_KINDS` = 7;
`directive.schema.yaml` reference enum = 9; `CharterYaml.activated_*` = 8; `pack_context`
valid-kinds = 11 with 10 read helpers; `charter/packs/default.yaml:2` claims "all 9 activation
kinds" while `:5-13` lists 8. **This design must not become the eleventh list.**

**[MEDIUM]** §5.6 — if deltas are **imported**, a hard mandatory-negative constraint cannot be a
schema rule at all: it would make 39% of the source corpus unimportable and would invite the
importer to **invent** a negative to satisfy the gate. **A fabricated negative is worse than a
missing one** — unfalsifiable data with the appearance of rigour. Import ⇒ the rule is
**advisory**, never schema `minItems`.

**[MEDIUM]** `tests/doctrine/test_artifact_compliance.py` — an optional field passes; a
**required** one red-lines ~310 artifacts at once. But optional is exactly the shape the 3-for-3
argument condemns. **Take optional + a coverage ratchet in the same commit** — a test asserting
an explicitly-enumerated allow-list of artifacts carries the field, list-only-grows. That
converts "partial population" from a silent state into a ratchet.

**[LOW]** `src/doctrine/glossary_packs/` — no JSON schema file exists. A field added there would
be Pydantic-validated only — an asymmetric gate. Independent reason to exempt.

**[LOW]** `tests/architectural/test_no_legacy_terminology.py:30-36` — `_FORBIDDEN_TERMS` covers
exactly two retired nouns; `_SCAN_ROOTS = ("src","tests","docs")` excludes `.kittify/`. None of
the new vocabulary is banned; `creed.yaml` would be unscanned. **Do not represent this change as
terminology-gate-verified.**

## Exemption table — all 12 `ArtifactKind` members

| # | Kind | Verdict | Field | Reason |
| --- | --- | --- | --- | --- |
| 1 | `directive` | **IN** | `value_impact` | A constraint you adopt. "Adopting this rule changes Minimal by −0.25" is exactly the corpus `delta` semantics. Caveat: no `notes` field, so the vector must be self-contained. |
| 2 | `tactic` | **IN** | `value_impact` | Highest-fidelity mapping — the calibration corpus *is* tactics (36 of 38 practice-shaped). Has `notes`. |
| 3 | `styleguide` | **IN**, caveated | `value_impact` | A convention set you adopt. Caveat: language-scoped and multi-principle, so one vector over five principles is an *average*. The schema must state the vector is artifact-level, not per-principle. |
| 4 | `toolguide` | **OUT** | — | **Descriptive, not adopted.** Fields are `tool`/`guide_path`/`summary`/`commands`. You consult a toolguide; there is no Δ-from-not-adopting. Zero of 36 corpus entries is tool documentation. |
| 5 | `paradigm` | **IN**, but | `value_bias` | **The design's hidden trap.** A paradigm *is* a value commitment, so its vector is a *stance*, not a Δ-from-baseline — semantically identical to a profile's bias. The real split is **stance-bearing** vs **adoptable-rule** kinds, not "profiles vs everything else." |
| 6 | `procedure` | **IN** | `value_impact` | A gated workflow; running it has costs and benefits. Caveat: deltas dominated by gate cost, so procedures cluster. |
| 7 | `agent_profile` | **IN**, different field | `value_bias` | A profile does not change the system's values by existing; it declares which it weights when acting. Bias, not delta. Hazard: `profile.py:254` lacks `extra="forbid"`, so getting this wrong fails **silently**. |
| 8 | `mission_step_contract` | **OUT** | — | Structural I/O contract — wiring, not a behavioural rule. A vector **double-counts**: the same delta counted once on the step and again on the directives its action resolves. |
| 9 | `template` | **OUT** | — | No behaviour of its own. **The corpus corroborates:** `TEMPLATE_PRACTICE` is one of the 14 all-non-negative vectors — the source library scored a template as pure upside, the tell that templates carry no adoption cost. §5.6 is evidence *for* this exemption. |
| 10 | `asset` | **OUT** | — | A blob behind a minimal sidecar manifest; content never parsed. Loose contract by design. |
| 11 | `glossary_pack` | **OUT** | — | Terminology, not behaviour — no adoption delta. Sharper: it already carries **`provenance: str` as a required field** — the only kind that does. If a value vector needs provenance, this is the model to **copy**, not the kind to extend. Also has no JSON schema at all. |
| 12 | `anti_pattern` | **OUT** as authored | — | Three blockers: not an artifact file (nodes hold 4 fields, no rationale slot); `DRGNode` has no `model_config`; `_KIND_MAP` lacks it. Negative-only is its natural form — hence **derivable**, never authored. |

**Net: 6 IN (4 `value_impact`, 2 `value_bias`), 6 OUT.** Exemption set =
`_NON_AUGMENTATION_ELIGIBLE_KINDS` ∪ `{TOOLGUIDE, MISSION_STEP_CONTRACT, GLOSSARY_PACK}`,
declared **once** in `artifact_kinds.py`. The design diverges from the canonical set by exactly
one member, and in the direction that is unimplementable.

## `value_impact` vs `value_bias` — three arguments

1. **Different referent.** A directive's delta is a *causal claim about the system*; a profile's
   is a *dispositional claim about an actor*. Δ(system state) vs a coefficient in a utility
   function.
2. **Different arithmetic — the killer.** Deltas are summable across the active artifact set;
   that is *why* `delta` is the right word. Biases are **not**: two profiles each weighting
   Minimal at 0.8 does not give 1.6. A single field name invites the illegal sum and nothing in
   the schema would catch it.
3. **Different position in the algebra.** `alignment = creed_weights · artifact_deltas` puts a
   profile on the **left** and a directive on the **right**. One shared name guarantees someone
   eventually dots a profile with a directive.

**Corollary the design misses:** the creed's field should also be `value_bias` — the creed *is*
the project's profile. Use **different Pydantic types** (`ValueImpact` vs `ValueWeighting`), not
one model with a `mode` discriminator, so the type system prevents the cross-product
structurally (DIRECTIVE_043).

**Two useful precedents:** `AgentProfile.routing_priority` (`ge=0, le=100`) is a scalar bias
register on profiles that **did not go inert** — 18 authored producers plus live consumers. It is
the shape `value_bias` should copy. And `model_task_routing`'s `task_fit` is the closest existing
multi-axis bias vector with a consumer.

## Accreditation placement

**GATED** = must carry a test in the same commit.

1. **The value-set artifact — the single authority. GATED.** A loadable artifact with a
   **required** provenance field. Copy `GlossaryPack.provenance` (required) and `SourceEntry`
   (`name`/`url`/`access_method`/`snapshot_at`/`license_notes`). Fields: `value_set_id`, `name`,
   `attribution` (required, non-empty), `trademark_notice` (required), `source{url, accessed_on}`,
   `authorization_basis`. Gate: a validator rejecting empty/whitespace `attribution`.
2. **Schema `$comment` — the design's placement is wrong.** Schemas are **generated**; a
   hand-added `$comment` is **erased by the next regeneration**. Author it as
   `Field(json_schema_extra=...)`, then regenerate.
3. **`NOTICE` at repo root — new file. GATED.** MIT requires retaining the copyright notice; it
   does not carry third-party trademark notices. Verify it is in the packaged sdist/wheel.
4. **The AMMERSE tactic — close the gap in the same change.** `notes:` with attribution + source
   URL; `references` gets the practice-article URL that `:61` only gestures at.
5. **Unify the drifted second copy BEFORE accrediting.** Two prose copies exist, already
   divergent ("impact on nature" lost from the template's Environmental definition).
   **Accrediting a misquoted definition is worse than not accrediting.**
6. **Generated / rendered output. GATED.** If vectors reach agent context, accreditation must
   ride with the *value-set name*. The always-on surface is
   `src/specify_cli/tool_surface/profiles/_render_helpers.py:47-65` (13 harnesses, outside the
   token budget). Cheapest compliant form: "AMMERSE (J.B. Crossland)" once per block.
7. **Docs.** One human-readable page, linked from the doctrine index and `src/doctrine/README.md`.
8. **`creed.yaml`** carries `value_set: <id>` — a pointer, not inline axis names.

**Not sufficient:** prose in `notes`; a hand-edited `$comment` in a generated schema; a line
appended to `LICENSE`; a mention only under `docs/plans/`.

## Provenance shape

**Import, not hand-authoring — and the machinery already exists.** `import_candidates` defines
`CurationImportCandidate` with `source{title,type,publisher,url,accessed_on}`,
`classification{target_concepts,rationale}`, `adaptation{summary,notes}`, `source_references[]`,
`external_references[]{url, attribution_reason, extraction_action}`, `status`,
`resulting_artifacts[]`. **`external_references[].attribution_reason` is literally the field for
the AMMERSE trademark obligation.**

One import-candidate artifact per import *batch*, `status: adopted`, plus on each artifact's value
field a two-field origin marker — never a copy of the prose:

- `value_impact.source_ref: AMMERSE-DELTA-IMPORT-001`
- `value_impact.source_digest: <sha256 of the imported 7-tuple as authored>`

**Drift detection — three layers:**

1. **Content drift (library ↔ doctrine copy). GATED.** Promote the corpus JSON to a packaged
   fixture, then recompute `source_digest` per artifact and assert a match. A hand-edit of an
   imported delta then fails immediately. **That is the check that would have caught the "impact
   on nature" loss.**
2. **Definition drift (copy ↔ copy in-repo). GATED as a single-authority assertion** — assert the
   seven definition strings appear in exactly **one** file. A single-authority assertion is
   refactor-stable; a two-copy diff test rots.
3. **Upstream drift. NOT gateable — accept explicitly.** Record `accessed_on`; **never**
   wall-clock-expire (the routing catalog documents why); surface staleness in
   `spec-kitty doctor doctrine`.

**One constraint to absorb:** graph-level provenance does not survive regeneration, so provenance
for the `impacts` edge field cannot live on the edge — it must live on the artifact or in the
import record.

## Composition with #2216

`#2216` is P2 and **blocked_by `#2467`**; its all-artefact child is **`#2591`**
(`component-type` on all doctrine artefacts). **Sequence, do not batch — and `#2591` goes
first:**

1. `component-type` is a discriminator the value field's applicability should be *expressed in*.
   Landing the value field first hardcodes a kind-keyed approximation into 7 schemas.
2. **Asymmetric reversibility.** `component-type` defaults to `open`, absent = today's behaviour.
   The value field requires 7 numbers + 7 rationales per artifact across ~310 nodes.
3. **Batching shares a failure mode** — one schema regeneration, one compliance update, one bulk
   YAML edit tripping the bulk-edit occurrence gate, one unreviewable diff.
4. The value field is gated on `#2538`; `component-type` is not.

**Ordering:** `#2467` → **`#2591`** → `#2538` arm-B → *if positive* the value field.
**Hard prerequisite before either:** the three silent kind-drop sites. **And correct the count:
three all-surface sweeps, not two** — the `impacts` edge field is an all-**edge** sweep the design
does not name.

## Gates tripped

| Gate | Fires? | Detail |
| --- | --- | --- |
| `additionalProperties: false` × 7 | **Yes, one action** | Schemas are generated from the models. Confirm `--check` is CI-wired. |
| `extra="forbid"` on models | **Yes — the gaps are worse than the gate** | **Missing** on `AgentProfile`, `DRGNode`/`DRGEdge` (no `model_config` at all), and all five curation import models. A `value_bias` on a profile and an `impacts` on an edge **silently vanish today**. |
| Extractor writers | **Yes** | Field-by-field; fixing models is insufficient. |
| `CharterYaml` `extra="forbid"` | **Yes — blocks `creed` outright** | Needs a typed field, not `overrides`. A separate `creed.yaml` needs a place in `hasher.py` + `versioning.py`. |
| DRG freshness / golden counts | **Yes** | `tests/doctrine` absent from the ceilings map → implicit ceiling 0. New `== N` needs `# golden-count`. |
| `RELATION_DESCRIPTIONS` + doc parity | **No, if `impacts` stays additive** | Fires only if `IN_TENSION_WITH` is retired/reinterpreted — which also needs a superseding ADR. |
| Glossary integrity | **Partly — the miss is the finding** | `delta` (= git diff in repo prose), `impact` (vs "AMMERSE **Impact** Analysis"), `bias`, `value` are ambiguous against existing vocabulary. Per the `primary`/`merge` footgun precedent these need canonical `docs/context/` entries **before** the tokens reach agent-facing render. Nothing forces a new noun into the glossary — discipline, not a gate. |
| Terminology guard | **No — do not claim verification** | |
| Docs freshness | **Yes** | inventory → index → `--ci`; relative-link check. |
| `test_artifact_compliance` | **Yes** | Optional passes; required red-lines ~310. Take optional + a coverage ratchet. |
| Bulk-edit gate | **Yes** | ~300 YAML files needs an `occurrence_map.yaml`. |

## Concession

- **Templates and assets are correctly exempt, and §5.6 is evidence *for* that.** I hunted the
  counter-example; `TEMPLATE_PRACTICE` turns out to be one of the 14 all-non-negative vectors —
  the library scored a template as pure upside, the tell that a template has no adoption cost.
- **§5.1's insistence that `delta` is the right word is load-bearing**, not pedantry, and it is
  what let me answer the field-split question cleanly.
- **Provenance is the design's strongest under-claimed asset.** `import_candidates` has had zero
  authored instances since WP03; a 36-vector import is its first genuine producer.
- **`routing_priority` refutes "3-for-3" as a law.** 18 authored producers and live consumers
  from inception. The rule is a strong empirical regularity, not a structural impossibility, and
  the discriminating variable is *a consumer in the same seam*. I will not carry 3-for-3 as a
  blocker against this design.
- **Part 2 is cheaper than feared**, provided it stays additive.

## Verdict

The design keeps the artifact catalog coherent only if three things change, each a small edit
rather than a rebuild. **First, the exemption boundary must be code, not prose** — it diverges
from the canonical set by omitting `anti_pattern`, the one kind structurally incapable of
carrying the mandatory rationale, and five more are ruled out on semantics, leaving 6 in and 6
out; as a prose sentence this becomes the eleventh divergent kind enumeration in a codebase whose
canonical kind file forbids a second one. **Second, `agent_profile` needs a genuinely different
field — `value_bias`, a distinct Pydantic type** — because deltas compose by summation and
biases do not, and the operation this design enables puts profiles and directives on opposite
sides of a dot product; the design also does not anticipate that `paradigm` belongs on the
profile side of that split. **Third, accreditation must be a required field on a loadable
value-set artifact**, because prose is unavailable where needed (`notes` on 2 of 12 kinds),
`LICENSE` says "Copyright GitHub, Inc.", there is no `NOTICE`, and a hand-added schema
`$comment` is erased by the next generation — and the unification of the two drifted definition
copies must land first, or you accredit the drift. On sequencing: three all-surface sweeps, and
`#2591` goes first. Finally, the two gates most likely to let this ship inert are not the ones
the design names: `AgentProfile` lacks `extra="forbid"` and `DRGNode`/`DRGEdge` have no
`model_config` at all, so a `value_bias` on a profile and an `impacts` on an edge both load and
**silently vanish today** — and the extractor writers would drop them again at regeneration even
after the models are fixed.
