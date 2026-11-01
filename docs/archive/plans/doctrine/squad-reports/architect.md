---
title: Architect lens — seams, types, and concrete shapes
description: "Structural hardening of the creed/FoundationalValues design: where each part plugs in, the concrete type shapes, and the composition invariant enforced as a type."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/creed-and-values-design-hardened.md
- docs/archive/plans/doctrine/creed-and-values-design-as-proposed.md
---
# Architect lens — seams, types, and concrete shapes

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> Raw squad report, 2026-07-26. Profile-loaded, read-only. Preserved verbatim as the
> evidence base for [`creed-and-values-design-hardened.md`](../creed-and-values-design-hardened.md).
> Forbidden-legacy-term literals are redacted where quoted, so the docs terminology guard stays green.

I have the full picture. Here is the hardening.

---

# Hardening: creed / FoundationalValues / `impacts`

**Profile directives applied:** 001, 003, 031, 032, 041, 043, 044 + tactic `development-bdd` (stated above).
All paths relative to the repository root (the `docs-manifesto-tier` worktree at the time). Read-only; no git run, no file edited.

---

## FINDINGS

**[BLOCKER]** `tests/architectural/test_artifact_selection_completeness.py:55-62` — `_doctrine_artifact_kinds()` discovers **every** `@property` on `DoctrineService` by introspection, and demands a matching `selected_<kind>` on `DoctrineSelectionConfig` (`src/charter/schemas.py:82`) **and** `required_<kind>` on `OrgCharterPolicy`. `DoctrineService` has exactly 9 properties today (`src/doctrine/service.py:65-150`). → **Do not expose the value-set repository as a `DoctrineService` property.** Doing so silently converts a 2-file change into a 3-way lockstep across two packages. Expose it via a named accessor (`resolve_active_value_set()`), not a property.

**[BLOCKER]** `src/charter/sync.py:249-251` — the canonical section-loader pattern treats an absent section as "empty config" with an `logger.info`. That *is* the 3-for-3 decay shape the verdict names (`Directive.severity`: 162 days inert behind green tests). A `load_creed_config` that copies this fallback ships pre-decayed. → `load_creed_config` must return a **three-state** result (`absent` / `partial` / `complete`), and the `absent` state must be surfaced by `run_consistency_check` (`src/charter/consistency_check.py:1050`), not logged at info.

**[MAJOR]** `src/charter/schemas.py:286` — `CharterYaml` is `frozen=True, extra="forbid"`, but it is only ever *constructed* (`src/charter/compiler.py:573`, `src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py:223`); `model_validate` against the on-disk document appears **only in tests** (`tests/charter/test_charter_yaml_model.py:86`). Every production reader goes through raw ruamel (`src/charter/charter_yaml_io.py:90`, consumed at `src/charter/sync.py:227`). → A `creed:` block on disk would be **silently unvalidated**: the mirror image of the three silent-drop sites. The validation entry point must be an explicit per-section `CreedConfig.model_validate(...)` at the `sync.py:252` seam.

**[MAJOR]** `src/doctrine/tactics/models.py:74` + `src/doctrine/schemas/tactic.schema.yaml:6` — dual gate. Models are `extra="forbid"`; schemas are `additionalProperties: false` and are **not** enforced at load (`src/doctrine/base.py:175` calls only `model_validate`; `src/doctrine/tactics/validation.py:17` has no callers) but **are** enforced by `tests/doctrine/test_artifact_compliance.py:21` / `test_tactic_compliance.py:68`. → Every per-artefact field must land in **both** places in one commit, ×6 kinds = 12 files minimum.

**[MAJOR]** `tests/doctrine/drg/test_kind_mapping_totality.py:49-52` — `_ENUM_CLASSES` understands `ArtifactKind` and `NodeKind` **only**. A `Relation`-keyed table (e.g. "which relations may carry `impacts`") has **no totality guard** and will rot on the next `Relation` addition. → If Part 2 introduces any `dict[Relation, ...]`, it must ship a Relation arm on this scanner in the same commit (DIRECTIVE_043: close the class, don't add to it).

**[MAJOR]** `src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml:61-62` and `:68` — the composition algebra is **already shipped doctrine**: `base + (0.5 × first_order_sum / 6)`, and `overall = base + (0.5 × first_order) + (0.25 × second_order)`. → `delta` == `base`, and it is the **only** term that may ever be persisted. Any schema with a field able to hold `first_order` or `overall` contradicts an activated tactic (`.kittify/config.yaml:53`, `.kittify/charter/charter.yaml:1436`, `src/charter/packs/default.yaml:47`). This is Q5's invariant, and it is authored, not invented.

**[MAJOR]** `src/doctrine/drg/models.py:299-303` — `DRGNode.provenance` is excluded from `graph.yaml` by "the extractor's explicit field-by-field writer". A new `DRGEdge.impacts` will therefore **not round-trip** unless that writer is taught the field — a silent-drop of exactly the class the verdict catalogues, in a fourth site nobody has listed.

**[MAJOR]** `src/charter/schemas.py:164` (`Directive.severity: str = "warn"`) and `:149` (`GovernanceConfig.enforcement: dict[str,str]`) are still present. Shipping a creed scoring register beside two known-dead ones voluntarily reproduces `070edbd4f`. → Campsite-delete both in the same mission that adds `creed`, per the verdict's WP01.

**[MAJOR]** `src/charter/consistency_check.py:934-952` — `_tension_candidate_pairs` builds pair membership by **exact relation equality** (`:947`) and set membership (`:949`). If `impacts` became the membership criterion (a "tension band"), pair membership becomes a function of a tunable threshold — and the verdict measured that no threshold separates genuine tensions (4–6) from unrelated pairs (2–4), overlapping at 4. → `impacts` must never gate membership. (Recommendation below.)

**[MINOR]** `src/charter/charter_yaml_io.py:61-66` — `_SCALAR_SECTIONS` / `OWNED_SECTIONS`; writing an unlisted section raises `UnknownCharterYamlSectionError` (`:151`). `"creed"` must be added to `_SCALAR_SECTIONS`, which is the correct one-line extension — it inherits the INV-9 anti-clobber invariant built for exactly this.

**[MINOR]** `.kittify/charter/` already carries five orphaned residue files (`directives.yaml`, `governance.yaml`, `metadata.yaml`, `references.yaml`, `graph.yml`) — none has a src writer. A sibling `creed.yaml` is the *known* residue-accumulation failure mode in this exact directory.

**[MINOR]** `src/charter/schemas.py:313-334` — `_OPTIONAL_EMPTY_OMIT_KEYS` + `_prune_optional_empties` (`:337`) enforce NFR-005 byte-stability. An absent creed must serialize to *nothing*, so `creed` must be `CreedConfig | None = None`, not a `default_factory`.

**[MINOR]** `src/doctrine/base.py:308-311` — `_merge` is `{**built_in.model_dump(), **project_data}`: **whole-field replace**. An org pack overriding a tactic's value vector replaces all seven axes; per-axis tuning is impossible. This is the *right* semantic (a half-authored vector is worse than none) but it must be documented, because operators will expect per-axis merge.

**[MINOR]** `src/doctrine/templates/architecture/ammerse-analysis-template.md:69` vs `.../ammerse-impact-analysis.tactic.yaml:41-42` — Environmental has lost "impact on nature and society" → "societal/ethical impact". Authoring 36 delta vectors against a drifted definition bakes the drift into data. DIRECTIVE_044 unification is a **prerequisite**, not a follow-up.

**[NOTE]** `src/doctrine/drg/migration/extractor.py:133-145` (`_KIND_MAP`, 11 entries), `src/charter/context.py:668-683` (`_classify_artifact_urns`, four `elif`, no `else`), `src/doctrine/drg/query.py:230-242` (16 kinds bucketed, 10 read out) — **these do not bite the design as specified below**, because nothing new becomes a DRG node. See Q6.

---

## Q1 — `FoundationalValues` as a "half-open enum"

**Verdict: do not build an enum, and do not build a half-open type. The construct does not need to exist.**

Reasoning, in three steps:

1. **A closed `StrEnum` is wrong** and the codebase proves why: `tests/doctrine/test_artifact_kinds.py:32` pins the exact 12-member set as a hardcoded literal, `tests/doctrine/drg/test_kind_mapping_totality.py:183` AST-scans all of `src/` for kind-keyed tables and demands totality-or-exemption, and `tests/doctrine/drg/test_models.py:58` pins `set(RELATION_DESCRIPTIONS) == set(Relation)`. Every enum in this repo is deliberately consumer-hostile. A consumer-replaceable set inside that machinery means "fork the CLI" — the objection the verdict raised at `manifesto-tier-verdict-and-handover.md:168`.

2. **The three-tier repository layering gives *most* of what is wanted, but not all of it.** `BaseDoctrineRepository` (`src/doctrine/base.py:82`) requires **only** `_schema` (`:114`) and `_glob` (`:122`) — it does **not** require an `ArtifactKind` member, an `ArtifactKind` plural, a glob entry, or a `NodeKind`. That is the enabling fact: **you can have a built-in→org→project layered doctrine repository with zero enum surface and zero DRG surface.** Confirmed by construction: `AgentProfileRepository` (`src/doctrine/agent_profiles/repository.py:219`) and `MissionTemplateRepository` (`src/doctrine/missions/repository.py:80`) already sit outside `BaseDoctrineRepository`, and `asset` has no repository at all.
   What layering does **not** give you: `_merge` at `src/doctrine/base.py:308-311` is a whole-field replace keyed on `obj.id`. `enhances`/`overrides` are per-artefact-ID augmentation edges (`src/doctrine/drg/models.py:229-247`) — they cannot express "add an eighth value to the built-in seven." An org replacing the value set replaces the **whole set artefact**, atomically. That is the correct semantic (a mixed 7+1 basis with a 7×7 matrix is incoherent) and it is exactly the "open–closed" the design asks for: closed for modification, open for substitution.

3. **The openness lives in the artefact, not the type.** Concrete shape:

- **No enum.** `ValueKey = str`, constrained by `Field(pattern=r"^[a-z][a-z0-9_]*$")`.
- `FoundationalValue` — frozen Pydantic model `{key, name, description}`.
- `ValueSet` — frozen Pydantic model owning an **ordered list** of `FoundationalValue` plus the connascence matrix; exposes `keys: frozenset[ValueKey]` as a computed property. This is the *runtime* authority against which every per-artefact vector is validated. Validation is **against the active `ValueSet`**, never against a module-level literal.
- `ValueSetRepository(BaseDoctrineRepository[ValueSet])` — `_glob = "*.valueset.yaml"`, built-in dir `src/doctrine/values/built-in/`. Free built-in→org→project substitution, zero enum cost, zero DRG cost.
- **The openness guard** (this is the part that makes it stay open, DIRECTIVE_043): an architectural test asserting that **no module under `src/` contains a literal collection of the seven AMMERSE keys**. Enum drift-guards pin a set closed; this pins it *open*. Without it, the first consumer of the value set will hardcode `("agile", "minimal", ...)` for a lookup table and re-close the set six months later, silently.

---

## Q2 — Where `creed` lives, exactly

**A `creed:` top-level block on `charter.yaml`. Not a new `.kittify/charter/creed.yaml`.** And the *weights* split from the *value set*.

| Concern | Home | Why |
| --- | --- | --- |
| Value names, descriptions, N×N matrix | `src/doctrine/values/built-in/ammerse.valueset.yaml` (doctrine tier, org-replaceable) | Reusable library knowledge, project-independent — the thing the verdict said must **not** be project data in a library, inverted: this half genuinely *is* library data |
| Weights (`"how important is this to us"`) + per-value rationale | `charter.yaml` → `creed:` block | Project-specific operator declaration. Resolves verdict objection at `manifesto-tier-verdict-and-handover.md:203` |

Why a block, not a sibling file — three citable reasons:

1. `src/charter/bundle.py:128-131` — `CANONICAL_MANIFEST` declares `tracked_files=[CHARTER_MD, CHARTER_YAML]` and `content_hash_files=[CHARTER_YAML]`. A sibling file must additionally be threaded into the manifest (`:76`), the content hash (`:141`), `first_missing_bundle_file` (`:199`), the freshness computer's `_BUNDLE_FILES` (`src/specify_cli/charter_runtime/freshness/computer.py:295-331`), and the bundle CLI gate (`src/specify_cli/cli/commands/charter_bundle.py:290-313`). A block inherits all five for free.
2. `.kittify/charter/` already holds five unowned residue files. Adding a sixth is the demonstrated failure mode of that directory.
3. `src/charter/charter_yaml_io.py:114` `update_charter_yaml_section` is the INV-9 anti-clobber chokepoint built precisely because three writers mutate one file. Adding `"creed"` to `_SCALAR_SECTIONS` (`:61`) is one line and inherits section-preservation structurally.

**Pydantic model:** new `CreedConfig` in `src/charter/schemas.py`, declared as `creed: CreedConfig | None = None` on `CharterYaml` (`:263`) — **not** nested under `GovernanceConfig` (`:132`). `GovernanceConfig` is the extracted/derived namespace whose two dead registers (`:149`, `:164`) are the decay precedent; a creed is a hand-authored operator declaration and belongs at the root beside `catalog`/`directives`. `None` default keeps `_prune_optional_empties` (`:337`) byte-stable per NFR-005.

**Producer, shipped in the same commit as the schema** (the 3-for-3 answer — Part 3 is the producer, and it must be *code*, not a plan):

| Stage | Surface | file:line |
| --- | --- | --- |
| Ask | `QUESTION_ORDER` / `QUESTION_PROMPTS` / `CharterInterview` | `src/charter/interview.py:125`, `:150`, `:187` |
| Default (non-interactive) | `default_interview` + packaged defaults | `src/charter/interview.py:254`, `:566`, `src/charter/defaults.yaml` |
| Persist answers | `write_interview_answers` | `src/charter/interview.py:345` |
| Write the block | `write_compiled_charter` → `update_charter_yaml_section(path, "creed", …)` | `src/charter/compiler.py:405`, `:445-446` pattern |
| Read the block | `load_creed_config(repo_root)` mirroring `load_governance_config` | `src/charter/sync.py:233` seam, validate at `:252` pattern |
| **Coverage gate, same commit** | `scan_creed_coverage(ctx)` mirroring `_check_unreconciled_tensions`'s fail-closed shape | `src/charter/consistency_check.py:1017` as the template; wired into `run_consistency_check` `:1050` |

The coverage gate is non-negotiable and is what distinguishes this from `severity`: it must report **absent** and **partial** creeds as findings, exactly as `scan_unreconciled_tensions` reports half-reconciled pairs (`:1013`). Note explicitly: do **not** copy `sync.py:249-251`'s silent empty-config fallback.

---

## Q3 — `impacts`: field on edges, not a Relation member — and `in_tension_with` survives

**Recommendation: optional annotation field on `DRGEdge`. `in_tension_with` is NOT retired and does NOT become a band.**

Cost of each option, priced:

| Option | Cost | Verdict |
| --- | --- | --- |
| New `Relation.IMPACTS` member | `RELATION_DESCRIPTIONS` totality (`src/doctrine/drg/models.py:138`; gate `tests/doctrine/drg/test_models.py:58`); a >40-char, **distinct** (`:77`) description; a verbatim-matching `### …\`impacts\`` section in `docs/architecture/doctrine-relationships.md`(`tests/doctrine/test_relation_doc_parity.py:49,123`); every`Relation`-keyed table. ~4 files, bounded. **But semantically wrong**:`impacts` is a *magnitude*, not an edge role. An `impacts` edge with no relation type says two nodes interact without saying how — the exact vector-wash the verdict identified. | **Reject** |
| Numeric field on `DRGEdge` | `src/doctrine/drg/models.py:328-339` already carries optional authored-only `when` and `reason`; `impacts` joins them additively. Real cost: the extractor's field-by-field writer (`:299-303`) must learn it or it silently won't round-trip; plus a validity domain (below). | **Adopt** |

**The load-bearing sub-answer.** Making `impacts` numeric does **not** make `in_tension_with` one band of a continuum, and it must not be allowed to:

- `in_tension_with` is a **typed existence claim with a lifecycle**: symmetric, stored as a single canonical lexicographic edge, and consumed as **set membership** by `_tension_candidate_pairs` (`src/charter/consistency_check.py:947,949`) and both-sides bridging by `_tension_reconciled_urns` (`:972`). A band makes pair membership a function of a tunable threshold — and the verdict measured that no threshold separates genuine tensions (opposition 4–6) from unrelated pairs (2–4), overlapping at 4, with 5/5 false positives across 47,900 candidate pairs.
- Therefore: **`impacts` is a strength annotation *on* an already-authored, already-typed edge, and is never a membership criterion.** `{relation: in_tension_with, impacts: "-0.7"}` reads "this authored tension is severe." `scan_unreconciled_tensions` (`:977`) is untouched; ADR `2026-07-21-1`'s single-relation decision is untouched; the 2 authored tension edges (`src/doctrine/directive.graph.yaml:90-93`, `:103-106`) keep working.

**What it costs, honestly.** `impacts` on `requires` is semantically murky (`requires` already implies positive coupling), so the field needs a documented validity domain — and the moment that domain is a `dict[Relation, ...]` or `frozenset[Relation]`, there is **no totality guard** (`tests/doctrine/drg/test_kind_mapping_totality.py:49-52` covers `ArtifactKind`/`NodeKind` only). Price: a `Relation` arm on that scanner in the same commit. Cheaper alternative I'd take first: **no per-relation table at all** — allow `impacts` on any relation, document it as "meaningful on `in_tension_with` / `rejects` / `refines`; ignored elsewhere," and let the *reader* decide. A `.get`-shaped consumer needs no table, and no table means nothing to rot.

---

## Q4 — Per-artefact field: exact kinds and shape

**Exact kind list — 6 kinds**, declared as a **positive** frozenset, not a negative exclusion:

`directive`, `tactic`, `styleguide`, `toolguide`, `paradigm`, `procedure`

Derivation: the 9 charter-activatable `ArtifactKind` members (`src/doctrine/artifact_kinds.py:210-214`, i.e. all 12 minus `_NON_AUGMENTATION_ELIGIBLE_KINDS` = `{template, asset, anti_pattern}` at `:201`), minus three that are not prescriptive practice statements:

| Excluded | Why |
| --- | --- |
| `template`, `asset` | Design says exempt. Structurally confirmed: `template` has no Pydantic model (only dataclasses at `src/doctrine/template_catalog.py:70,95`) and an empty glob (`src/doctrine/artifact_kinds.py:74`); `asset` has no repository. There is nowhere to put the field. |
| `anti_pattern` | No model, no artefact file (`src/doctrine/artifact_kinds.py:77-84`) — it is a re-kinded node inside a graph fragment. A value vector on a negation is ambiguous by construction. |
| `glossary_pack` | Terminology, not behaviour. No trade to score. |
| `agent_profile` | An *actor*, not a practice. A profile value vector is the §6 squad-composition mechanism the verdict killed for having zero prior art (`manifesto-tier-verdict-and-handover.md:169`). Also the only model that **ignores** extras (`src/doctrine/agent_profiles/profile.py:254`), so a stray field there fails silently rather than loudly. |
| `mission_step_contract` | Workflow I/O contract, structural not behavioural. |

**Positive, not negative, and this matters:** `_NON_AUGMENTATION_ELIGIBLE_KINDS` is an *exclusion* set — a new kind is silently included by default. For value-bearing that default is wrong: a new kind would silently acquire a scoring obligation nobody authored. A positive `_VALUE_BEARING_KINDS` frozenset means a new kind defaults to **not** value-bearing, and gets one only when someone writes it down. Pin it with an exactness test mirroring `tests/doctrine/test_artifact_kinds.py:151`.

**Field shape.** Name `values`, a **list** (not a mapping), of `{name, delta, rationale}` — field names verbatim from the corpus (`creed-and-values-design-as-proposed.md:100-107`) so the 36-vector calibration set imports with **zero transformation**. A list also preserves authored order; duplicate `name` is caught by a `mode="after"` validator (a mapping would give that free, but would break corpus round-trip — the round-trip is worth more).

**`delta`: string on the wire, `Decimal` in memory.** This is neither of the two options in the prompt, and it is the right one:

| | String | Float | **String→`Decimal`** |
| --- | --- | --- | --- |
| Round-trips corpus byte-identically | ✅ | ❌ `"0.9"` → `0.9` reformats | ✅ |
| Arithmetic for `base + 0.5×fo/6` | ❌ | ✅ | ✅ exact |
| Comparison needs tolerance | n/a | ✅ needs epsilon | ❌ exact |
| Preserves authored precision (`0.125`, `0.05` grid, `creed-…:172`) | ✅ | ⚠️ representation drift | ✅ |
| Range/granularity enforceable in schema | ⚠️ regex only | ✅ | ✅ both |

Pick **string→`Decimal`**. `condecimal(ge=-1, le=1, max_digits=4, decimal_places=3)` plus a `mode="before"` validator that **rejects a non-`str` raw input** — because `Decimal(float)` is lossy, so an unquoted `delta: 0.9` in YAML (which ruamel yields as `float`) must be a hard error, not a silent conversion. That closes the precision-drift defect class by construction rather than by authoring discipline (DIRECTIVE_043).

**On the mandatory-negative rule (§5.6):** measured, a hard `minItems: 1` on negatives rejects 39% of the operator's own corpus. Ship it as a **consistency-check finding**, not a validator — same tier as `scan_unreconciled_tensions`, in `src/charter/consistency_check.py`. That keeps the review heuristic (which the verdict says is the one contribution that survived all four lenses, `manifesto-tier-verdict-and-handover.md:135-141`) without making the calibration set unloadable. The operator's decision then becomes reversible in one line instead of a schema migration.

---

## Q5 — `ValueConnascence` N×N: home, reader, and the composition invariant

**Home:** inside the `ValueSet` artefact (`src/doctrine/values/built-in/ammerse.valueset.yaml`), **not** on the charter. It is library knowledge, org-replaceable, and it must travel with the basis it indexes — a matrix and a value list that can drift apart is the `ammerse-analysis-template.md:69` Environmental drift repeated at N² scale. Co-location makes basis/matrix consistency a **single-artefact validator** (`matrix` keys == `values` keys, both dimensions) instead of a cross-file freshness check.

**Representation:** a nested mapping `dict[ValueKey, dict[ValueKey, Decimal]]` with an `mode="after"` validator asserting squareness, key-set equality with `values`, and zero diagonal. Not a flat list of triples (unreadable at 49 entries), not a positional matrix (breaks the moment a consumer reorders).

**Reader:** exactly one — a pure function `project_values(deltas, value_set) -> tuple[ValueProjection, ...]`. No other module reads the matrix. That is how this avoids becoming the routing-catalog failure: the routing catalog rotted because `routing_policy`/`task_fit` had a schema and a scoring evaluator but a producer that covered 1 of 21 verbs. Here the producer (36 authored vectors) exists **before** the reader, and the reader is one function with one signature.

**The composition invariant — and it is already authored doctrine, not a new invention:**

`src/doctrine/tactics/built-in/analysis/ammerse-impact-analysis.tactic.yaml:61-62` and `:68`:
```
first_order path:  base + (0.5 × first_order_sum / 6)
high-stakes path:  overall = base + (0.5 × first_order) + (0.25 × second_order)
```
So: **authored `delta` == `base`. It is the only persisted term.** `first_order` and `overall` are derived. Any schema field able to hold them contradicts an activated, procedure-mandated tactic (`src/doctrine/procedure.graph.yaml:297-299`).

**The storage rule that prevents computed values being written back as authored ones — four structural locks, not one convention:**

1. **The persisted model cannot hold a computed value.** `ValueDelta` has exactly `{name, delta, rationale}`, `extra="forbid"`, `frozen=True` (mirroring `src/doctrine/tactics/models.py:74`). There is no field to write into and no setter to write with.
2. **The computed value is a different type in a different module, with no serializer.** `ValueProjection` is a frozen dataclass in `doctrine.values.projection`, carrying `base`, `first_order`, `overall`, `matrix_id`, `matrix_version`. It is **not** a Pydantic model — so it has no `model_dump()`, and therefore no path into any YAML writer, which is the actual mechanism (every doctrine writer in this repo serializes via `model_dump()`; see `src/doctrine/base.py:210`, `src/charter/schemas.py:377`).
3. **Provenance is mandatory on the projection.** `matrix_id` + `matrix_version` are required fields with no defaults, so a projection can never be mistaken for an authored base — a value without a matrix stamp *is* an authored base, by type.
4. **A pin test on the persisted shape:** `set(ValueDelta.model_fields) == {"name", "delta", "rationale"}` exactly. That is a legitimate closed pin (unlike the value *set*, which must stay open) and it goes red the day someone adds `computed_overall`.

Lock 2 is the load-bearing one. Locks 1, 3, 4 are cheap reinforcement.

---

## Q6 — What breaks, and do `FoundationalValues` become DRG nodes?

**No — nothing in this design becomes a DRG node, and the three silent-drop sites do not bite it.** That is the design's single best structural property.

| Design element | DRG surface | Silent-drop exposure |
| --- | --- | --- |
| `ValueSet` + matrix | `BaseDoctrineRepository` only; no `ArtifactKind`, no `NodeKind`, no URN, never in a `*.graph.yaml` | **None.** Never reaches `query.py:230-242` bucketing, `context.py:668-683`'s missing `else`, or `extractor.py:133-145`'s `_KIND_MAP` |
| `creed:` block | charter.yaml section | **None** — not a node |
| Per-artefact `values:` | field on an **existing** node's artefact YAML | **None** — the node already exists; the field never becomes an edge |
| `DRGEdge.impacts` | field on an existing edge | **Not `_KIND_MAP`** — but **does** hit the extractor's field-by-field writer (`models.py:299-303`), a *fourth* silent-drop site not in the verdict's list of three |

Consequence to state plainly: **the silent-drop closure is not a prerequisite for this design.** That is the difference between it and the rejected `manifesto` NodeKind (41–59 files, `manifesto-tier-verdict-and-handover.md:168`). But it is spent the instant anyone proposes making the value set a first-class kind so it can be `charter activate`d — at which point the full cost returns: `artifact_kinds.py` `_PLURALS`/`_PATTERNS`, the 12-member literal pin (`tests/doctrine/test_artifact_kinds.py:32`), the NodeKind superset (`tests/doctrine/drg/test_nodekind_artifactkind.py:18`), the AST totality scanner, and all three drop sites. **Forswear activation of the value set explicitly, in the ADR.**

---

## CONCRETE SHAPES

### 1. Value set + connascence matrix — `src/doctrine/values/built-in/ammerse.valueset.yaml`

```yaml
schema_version: "1.0"
id: ammerse
name: AMMERSE Value System
attribution: >
  The AMMERSE value system is the work of J.B. Crossland (https://www.ammerse.org).
  "AMMERSE", "AMMERSE Method", "AMMERSE Theory", and "AMMERSE Value System" are
  trademarks of J.B. Crossland. Used with the author's authorization. This artefact
  is an accreditation, not a license of the consultancy framework.

# Ordered. Order is presentation only -- the matrix is keyed, never positional.
values:
  - key: agile
    name: Agile
    description: >
      The ability to adapt quickly to changes, incorporate feedback, and maintain
      flexibility in processes and decision-making.
  - key: minimal
    name: Minimal
    description: >
      The focus on simplicity and avoiding unnecessary complexity in processes
      and systems.
  - key: maintainable
    name: Maintainable
    description: >
      The ease of keeping processes and systems in working condition over time.
  - key: environmental
    name: Environmental
    description: >
      Considering the broader context, including cultural fit, impact on nature
      and society, standards, and ethical considerations.
  - key: reachable
    name: Reachable
    description: >
      Setting practical goals and ensuring they are achievable within the given
      constraints.
  - key: solvable
    name: Solvable
    description: >
      The ability to effectively solve problems and address challenges that arise.
  - key: extensible
    name: Extensible
    description: >
      The capacity to extend or scale processes and systems to meet future needs.

# ValueConnascence. matrix[a][b] = "how a change in `a` propagates to `b`",
# on the same [-1;1] sabotages<->reinforces scale. Square, zero diagonal,
# keys == `values[].key` exactly (validated). Illustrative values below --
# the authored first-order matrix is imported from the licensed source under
# the attribution above; do NOT hand-invent cells.
connascence:
  matrix_version: "1.0"
  first_order:
    agile:         {agile: "0", minimal: "0.3",  maintainable: "-0.1", environmental: "0",    reachable: "0.2",  solvable: "0.1",  extensible: "0.1"}
    minimal:       {agile: "0.3",  minimal: "0", maintainable: "0.4",  environmental: "0.1",  reachable: "0.5",  solvable: "-0.1", extensible: "-0.3"}
    maintainable:  {agile: "-0.1", minimal: "0.4",  maintainable: "0", environmental: "0.2",  reachable: "-0.2", solvable: "0.2",  extensible: "0.4"}
    environmental: {agile: "0",    minimal: "0.1",  maintainable: "0.2", environmental: "0",  reachable: "0.1",  solvable: "0.1",  extensible: "0.1"}
    reachable:     {agile: "0.2",  minimal: "0.5",  maintainable: "-0.2", environmental: "0.1", reachable: "0",   solvable: "0.3",  extensible: "-0.2"}
    solvable:      {agile: "0.1",  minimal: "-0.1", maintainable: "0.2", environmental: "0.1", reachable: "0.3",  solvable: "0",    extensible: "0.2"}
    extensible:    {agile: "0.1",  minimal: "-0.3", maintainable: "0.4", environmental: "0.1", reachable: "-0.2", solvable: "0.2",  extensible: "0"}
  # second_order is OPTIONAL. Absent => the high-stakes path at
  # ammerse-impact-analysis.tactic.yaml:68 is unavailable and project_values()
  # raises rather than substituting zeros.
  second_order: null
```

### 2. Creed — `charter.yaml` block (weights only; no value definitions, no matrix)

```yaml
# .kittify/charter/charter.yaml  (top-level key, sibling of `governance:` / `catalog:`)
creed:
  value_set: ammerse          # resolves through ValueSetRepository (built-in|org|project)
  value_set_version: "1.0"
  # One entry per value in the resolved set. `weight` is importance-to-us on
  # [0;1] (NOT a delta -- a delta is a change, a weight is a standing priority).
  # `rationale` is mandatory and is the load-bearing field: it is what an LLM
  # reads. A weight without a rationale is unfalsifiable.
  weights:
    - name: minimal
      weight: "0.9"
      rationale: >
        Single canonical authority is the project's first principle; we would
        rather delete a surface than add a second one. We accept slower delivery
        of new capability to keep the surface count down.
    - name: maintainable
      weight: "0.85"
      rationale: >
        The corpus is dogfooded by agents with cold context; anything that needs
        a discipline reminder to stay correct is treated as structurally broken.
    - name: solvable
      weight: "0.7"
      rationale: >
        We prefer closing a defect class by construction over resolving the
        instance, and will pay a larger diff for it.
    - name: agile
      weight: "0.5"
      rationale: >
        Deliberately mid-ranked. We hold planning gates ahead of velocity and
        will refuse to ship a schema without its producer.
    - name: reachable
      weight: "0.4"
      rationale: >
        Explicitly de-prioritised: three scoring registers shipped as reachable
        slots and went inert. We now treat "ship the schema, populate later" as
        a defect, and give up short-term progress signals to do so.
    - name: extensible
      weight: "0.4"
      rationale: >
        Extension points are earned by a second real consumer, not anticipated.
    - name: environmental
      weight: "0.35"
      rationale: >
        Considered, but this is developer tooling; ecological and societal reach
        is indirect. We do not claim more than that.
```

### 3. Python — the four types + the two seams

```python
# src/doctrine/values/models.py
from __future__ import annotations
from decimal import Decimal
from typing import Annotated, Any, Self
from pydantic import BaseModel, ConfigDict, Field, condecimal, model_validator

#: A value key. Deliberately NOT an enum: the value set is consumer-replaceable
#: (built-in -> org -> project via ValueSetRepository). A closed StrEnum here
#: would mean "fork the CLI to add a value".
ValueKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]

#: [-1;1] at 0.05-grid resolution (22 distinct |values| measured in the
#: calibration corpus, one 0.125 outlier). Decimal, never float: exact
#: comparison, no tolerance, no representation drift.
Normalized = Annotated[Decimal, condecimal(ge=Decimal("-1"), le=Decimal("1"),
                                           max_digits=4, decimal_places=3)]


def _require_authored_as_string(raw: Any, field: str) -> Any:
    """Reject an unquoted YAML number for a normalized field.

    ruamel yields `float` for an unquoted `delta: 0.9`, and Decimal(float) is
    lossy -- so the authored precision the corpus depends on would silently
    drift. Rejecting non-str at the boundary closes that class by construction
    rather than by authoring discipline.
    """
    if isinstance(raw, dict) and field in raw and not isinstance(raw[field], str):
        raise ValueError(
            f"{field!r} must be authored as a quoted string (e.g. {field}: \"-0.25\"), "
            f"got {type(raw[field]).__name__}. Unquoted YAML numbers lose authored "
            f"precision."
        )
    return raw


class FoundationalValue(BaseModel):
    """One value in a replaceable value set. Not an enum member."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    key: ValueKey
    name: str
    description: str = Field(min_length=40)   # a slogan is not a definition


class ValueConnascence(BaseModel):
    """The N x N ripple matrix. matrix[a][b] = propagation of a into b."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    matrix_version: str
    first_order: dict[ValueKey, dict[ValueKey, Normalized]]
    second_order: dict[ValueKey, dict[ValueKey, Normalized]] | None = None


class ValueSet(BaseModel):
    """The runtime authority for which values exist and how they interact.

    Substitutable wholesale by an org/project layer (doctrine.base._merge is a
    whole-field replace) -- which is the correct grain: a 7-value list paired
    with a 5x5 matrix is incoherent, so the pair moves atomically.
    """
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    schema_version: str = Field(pattern=r"^1\.0$")
    name: str
    attribution: str | None = None
    values: list[FoundationalValue] = Field(min_length=1)
    connascence: ValueConnascence

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(v.key for v in self.values)

    @model_validator(mode="after")
    def _matrix_is_square_over_declared_keys(self) -> Self:
        declared = self.keys
        if len(declared) != len(self.values):
            raise ValueError("duplicate value key in `values`")
        for label, matrix in (("first_order", self.connascence.first_order),
                              ("second_order", self.connascence.second_order)):
            if matrix is None:
                continue
            if set(matrix) != declared:
                raise ValueError(
                    f"connascence.{label} rows {sorted(set(matrix))} != "
                    f"declared values {sorted(declared)}"
                )
            for row, cols in matrix.items():
                if set(cols) != declared:
                    raise ValueError(f"connascence.{label}[{row}] is not square")
                if cols[row] != 0:
                    raise ValueError(f"connascence.{label}[{row}][{row}] must be 0")
        return self


class ValueDelta(BaseModel):
    """One authored axis of a per-artefact value vector.

    THE PERSISTED SHAPE, AND THE ONLY ONE. `delta` is the *base* term of
    ammerse-impact-analysis.tactic.yaml:61-62 -- the change caused by adopting
    this artefact, relative to not adopting it. First- and second-order ripple
    are DERIVED (see ValueProjection) and have no field here to be written into:
    `extra="forbid"` + `frozen=True` make write-back structurally impossible,
    not merely discouraged.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: ValueKey
    delta: Normalized
    rationale: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _reject_unquoted_delta(cls, data: Any) -> Any:
        return _require_authored_as_string(data, "delta")
```

```python
# src/doctrine/values/projection.py  -- deliberately NOT Pydantic.
from dataclasses import dataclass
from decimal import Decimal

_FIRST_ORDER_COEFF = Decimal("0.5")
_SECOND_ORDER_COEFF = Decimal("0.25")


@dataclass(frozen=True)
class ValueProjection:
    """A COMPUTED value figure. Never persisted, and structurally unpersistable.

    This is a plain frozen dataclass, not a BaseModel, specifically so it has no
    `model_dump()`. Every doctrine/charter writer in this repo serializes via
    `model_dump()` (doctrine/base.py:210, charter/schemas.py:377), so there is
    no code path that can write a projection into an artefact or a charter.
    That is the composition invariant's enforcement -- not a comment.

    `matrix_id`/`matrix_version` are required with no defaults: a figure without
    a matrix stamp IS an authored base, by type.
    """
    name: str
    base: Decimal
    first_order: Decimal
    overall: Decimal
    matrix_id: str
    matrix_version: str


def project_values(
    deltas: tuple["ValueDelta", ...],
    value_set: "ValueSet",
    *,
    high_stakes: bool = False,
) -> tuple[ValueProjection, ...]:
    """The ONE reader of the connascence matrix.

    Implements ammerse-impact-analysis.tactic.yaml:61-62 (standard path) and
    :68 (high-stakes path). Raises when `high_stakes=True` and the active set
    carries no second_order matrix -- it never substitutes zeros, because a
    zero ripple and an unknown ripple are different claims.
    """
    ...
```

### 4. Per-artefact field — YAML + model (×6 kinds)

```yaml
# any of: *.directive.yaml | *.tactic.yaml | *.styleguide.yaml
#         | *.toolguide.yaml | *.paradigm.yaml | *.procedure.yaml
# Optional. Absent means "not assessed" -- NOT "neutral on every axis".
values:
  - {name: agile,         delta: "0.9",   rationale: "Strong focus on rapid adaptation and iterative learning."}
  - {name: minimal,       delta: "-0.25", rationale: "Adds documentation and experiment tracking; net negative but low."}
  - {name: maintainable,  delta: "-0.15", rationale: "Minor drag: one more artefact to keep current."}
  - {name: environmental, delta: "0.45",  rationale: "Surfaces blast radius before commitment."}
  - {name: reachable,     delta: "0.45",  rationale: "Bounds the change to something completable in one pass."}
  - {name: solvable,      delta: "0.6",   rationale: "Names the failure mode, so the fix is targetable."}
  - {name: extensible,    delta: "0.15",  rationale: "Neutral-to-slight: no extension points added or removed."}
```

```python
# added to EACH of the 6 models -- e.g. src/doctrine/tactics/models.py:84,
# after `notes`. Field name `values` is safe: Pydantic v2 reserves only the
# `model_` prefix.
    values: list[ValueDelta] = Field(default_factory=list)
    """Authored value-impact vector (optional).

    Empty list means NOT ASSESSED -- it is never read as "neutral on every
    axis". Keys are validated against the ACTIVE ValueSet at resolve time, not
    against a module-level literal, so a consumer-replaced value set works
    without a code change.

    NOTE on layering: doctrine.base._merge (base.py:308-311) is a whole-field
    replace. An org/project override of this artefact replaces the ENTIRE
    vector; per-axis tuning is not supported, deliberately -- a partially
    re-authored vector mixes two assessors' mental models.
    """

    @model_validator(mode="after")
    def _value_names_are_unique(self) -> Self:
        names = [v.name for v in self.values]
        if len(set(names)) != len(names):
            raise ValueError("duplicate value name in `values`")
        return self
```

```yaml
# src/doctrine/schemas/tactic.schema.yaml -- MUST land in the same commit,
# because additionalProperties:false at :6 is gated by
# tests/doctrine/test_artifact_compliance.py:21 / test_tactic_compliance.py:68.
# Add under `definitions:` (:12):
  value_delta:
    type: object
    additionalProperties: false
    required: [name, delta, rationale]
    properties:
      name:
        type: string
        pattern: ^[a-z][a-z0-9_]*$
      delta:
        type: string          # STRING, not number -- preserves authored precision
        pattern: ^-?(0(\.\d{1,3})?|1(\.0{1,3})?)$
        description: Change caused by adopting this artefact, on [-1;1]. Quoted.
      rationale:
        type: string
        minLength: 1
# ... and under top-level `properties:` (:64):
  values:
    type: array
    minItems: 1
    items:
      $ref: '#/definitions/value_delta'
    description: >
      Authored value-impact vector. Absent means not assessed. Keys are checked
      against the active value set at resolve time, not by this schema.
```

### 5. Edge field — `src/doctrine/drg/models.py:328-339`

```python
class DRGEdge(BaseModel):
    """A typed, directed relationship between two nodes."""

    source: str
    target: str
    relation: Relation
    when: str | None = None
    reason: str | None = None
    #: Bounded interaction strength on the sabotages <-> reinforces scale,
    #: [-1;1], authored as a quoted string. An ANNOTATION on an
    #: already-typed edge -- never a membership criterion.
    #:
    #: It does NOT make `in_tension_with` one band of a continuum:
    #: consistency_check._tension_candidate_pairs (:947-951) selects pairs by
    #: exact relation equality and set membership. Deriving pair membership
    #: from a numeric threshold was measured at 5/5 false positives over
    #: ~47.9k candidate pairs (opposition counts overlap: genuine 4-6,
    #: unrelated 2-4). ADR 2026-07-21-1's single-relation decision stands.
    #:
    #: Meaningful on `in_tension_with` / `rejects` / `refines`; carried but
    #: unread elsewhere. Deliberately NO dict[Relation, ...] validity table:
    #: test_kind_mapping_totality._ENUM_CLASSES (:49-52) covers only
    #: ArtifactKind/NodeKind, so a Relation-keyed table would ship with no
    #: totality guard and rot on the next Relation member.
    impacts: Normalized | None = None
    provenance: str | None = None
```
```yaml
# src/doctrine/directive.graph.yaml:90-93 -- the existing authored tension,
# annotated. The relation is unchanged; only strength is added.
- source: directive:DIRECTIVE_024
  target: directive:DIRECTIVE_025
  relation: in_tension_with
  impacts: "-0.7"
  reason: >
    Locality of Change vetoes growth of the file set that the Boy Scout Rule
    expands. See directive:RECONCILE_CHANGE_SCOPE_TENSIONS.
```

---

## SEAM-CHANGE INVENTORY

### Part 1 — Creed and Values

**New files**
- `src/doctrine/values/__init__.py`, `models.py`, `projection.py`, `repository.py` (`ValueSetRepository(BaseDoctrineRepository[ValueSet])`, `_glob = "*.valueset.yaml"`)
- `src/doctrine/values/built-in/ammerse.valueset.yaml`
- `src/doctrine/schemas/valueset.schema.yaml` (parity with the 7 existing schemas; note it will be dead at load time like the others — `src/doctrine/tactics/validation.py:17` has no callers — but live in `tests/doctrine/test_artifact_compliance.py:21`)
- `tests/doctrine/values/` — model validators, matrix squareness, string-only `delta`, projection formulas vs `ammerse-impact-analysis.tactic.yaml:61-62,:68`, the persisted-shape pin, the **openness** guard (no hardcoded 7-key literal in `src/`)

**Modified — per-artefact field (×6 kinds, 12 files)**
- `src/doctrine/directives/models.py:49` · `src/doctrine/tactics/models.py:84` · `src/doctrine/styleguides/models.py:79` · `src/doctrine/toolguides/models.py:9` · `src/doctrine/paradigms/models.py:67` · `src/doctrine/procedures/models.py:103`
- `src/doctrine/schemas/{directive,tactic,styleguide,toolguide,paradigm,procedure}.schema.yaml` (`:6` `additionalProperties: false`; add `definitions.value_delta` + `properties.values`)
- `src/doctrine/artifact_kinds.py` — new **positive** `_VALUE_BEARING_KINDS` frozenset beside `_NON_AUGMENTATION_ELIGIBLE_KINDS` (`:201`)
- `tests/doctrine/test_artifact_kinds.py` — exactness pin mirroring `:151`

**Deliberately NOT modified**
- `src/doctrine/service.py:65-150` — **no new `@property`** (see the BLOCKER); expose via a named accessor
- `src/doctrine/artifact_kinds.py:92` `ArtifactKind` — no new member
- `src/doctrine/drg/models.py:27` `NodeKind` — no new member
- any `*.graph.yaml`

**Campsite, same mission**
- delete `src/charter/schemas.py:164` `Directive.severity` and `:149` `GovernanceConfig.enforcement`
- DIRECTIVE_044 unification: `src/doctrine/templates/architecture/ammerse-analysis-template.md:33,45,57,69,81,93,105` → point at the value set instead of restating; restore "impact on nature" at `:69`

### Part 2 — `impacts` on edges

- `src/doctrine/drg/models.py:328-339` — add `impacts: Normalized | None = None`
- `src/doctrine/drg/migration/extractor.py` — teach the field-by-field edge writer (the mechanism named at `models.py:299-303`) to emit `impacts`; **without this the field silently does not round-trip**
- `src/doctrine/drg/validator.py` — range already enforced by the annotation; add nothing
- `src/doctrine/directive.graph.yaml:90-93`, `:103-106` — annotate the 2 authored tension edges (the only sensible first population)
- `docs/architecture/doctrine-relationships.md` — a note that `impacts` annotates, never types. **No new `###` section needed** because no `Relation` member is added, so `tests/doctrine/test_relation_doc_parity.py:49` stays green
- `tests/doctrine/drg/test_models.py` — `impacts` default `None`, range rejection, string-only, round-trip through `model_dump`
- **Untouched, and verify so:** `src/charter/consistency_check.py:934-1014`

### Part 3 — Charter creation

- `src/charter/schemas.py` — new `CreedWeight` + `CreedConfig`; `creed: CreedConfig | None = None` on `CharterYaml` (`:263`); add creed keys to `_OPTIONAL_EMPTY_OMIT_KEYS` (`:313`) if any list can be empty
- `src/charter/charter_yaml_io.py:61` — add `"creed"` to `_SCALAR_SECTIONS`
- `src/charter/sync.py` — new `load_creed_config(repo_root)` after `:269`, following the `:233→:252` validate pattern but **three-state, not silent-empty**
- `src/charter/compiler.py:405` `write_compiled_charter` — `update_charter_yaml_section(path, "creed", …)` beside `:445-446`; extend `_bootstrap_charter_yaml` (`:540`) and `CharterYaml(...)` (`:573`)
- `src/charter/interview.py:125,150,187,254,566` + `src/charter/defaults.yaml` — the creed question set (the producer). LLM-chosen probes per §3, mapped through `src/charter/synthesizer/interview_mapping.py`
- `src/specify_cli/cli/commands/charter/interview.py:237,303` and `_widen.py:266` — prompt wiring
- `src/charter/consistency_check.py` — `scan_creed_coverage(ctx)` + `_check_creed_coverage` mirroring `:1017`'s fail-closed shape; wire into `run_consistency_check` (`:1050`) and `ConsistencyReport` (`:147`)
- `src/specify_cli/upgrade/migrations/m_*.py` — seed an absent `creed:` in existing projects (pattern: `m_unify_charter_activation_finalize.py:315`)
- `docs/architecture/06_unified_charter_bundle.md:31-49` — the tracked/hash table gains the `creed` section
- `tests/charter/test_charter_yaml_model.py:73-201` — creed round-trip, absent-key three-state, `extra="forbid"` still rejects a stray nested key

---

## WHAT BREAKS

| # | Surface | Breaks how | Order |
| --- | --- | --- | --- |
| 1 | `tests/doctrine/test_artifact_compliance.py:21`, `test_tactic_compliance.py:68` | `values:` in a built-in YAML with `additionalProperties: false` still at `schemas/*.yaml:6` → red | Model + schema + data in **one** commit |
| 2 | `tests/architectural/test_artifact_selection_completeness.py:80,118,150` | Red **three ways** the moment `ValueSetRepository` becomes a `DoctrineService` property | Don't. Use a named accessor |
| 3 | `tests/charter/test_charter_yaml_model.py:86` | `CharterYaml.model_validate` on a dump containing `creed` fails until the field is declared (`schemas.py:286` `extra="forbid"`) | Field before data |
| 4 | `src/charter/charter_yaml_io.py:151` | `UnknownCharterYamlSectionError` on the first creed write | `_SCALAR_SECTIONS` before the writer |
| 5 | `src/charter/bundle.py:141` + `src/specify_cli/charter_runtime/freshness/computer.py:295-331` | `creed:` changes the bundle content hash → every existing project reads **stale** on upgrade | Migration in the same release |
| 6 | `src/doctrine/drg/migration/extractor.py` edge writer | `DRGEdge.impacts` silently absent from regenerated `*.graph.yaml`; graph-freshness tests then diff | Writer before any authored `impacts` |
| 7 | `tests/architectural/test_no_legacy_terminology.py` | `Mission`/canonical-term guard on new doctrine prose; CI-only job | Run locally pre-push (~0.1 s) |
| 8 | `tests/_arch_shard_map.py:81-87,155,226` + `tests/architectural/test_golden_count_ban.py:131,272` | Every new test **file** must be appended to a shard tuple; every new `len(x) == N` needs `# golden-count: cardinality-is-contract` | With each new test file |
| 9 | `src/charter/schemas.py:313-334` NFR-005 | An emitted `creed: null` / `creed: {}` breaks byte-stability of default fixtures | `CreedConfig \| None = None`, prune on empty |
| 10 | 36-vector import | Corpus authored against `ammerse-analysis-template.md:69`'s drifted Environmental definition | DIRECTIVE_044 unification **first** |

**Explicitly not broken** (and worth asserting in tests so it stays true): `src/doctrine/drg/query.py:230-242`, `src/charter/context.py:668-683`, `src/doctrine/drg/migration/extractor.py:133-145`, `tests/doctrine/test_artifact_kinds.py:32`, `tests/doctrine/drg/test_kind_mapping_totality.py:183`, `tests/doctrine/drg/test_nodekind_artifactkind.py:18`, `tests/doctrine/drg/test_models.py:58`, `tests/doctrine/test_relation_doc_parity.py:49`, `src/charter/consistency_check.py:934-1014`.

---

## CONCESSION

- **Nothing was executed.** Every "breaks" claim is a static read of test source. No pytest run, no `python -c`. Item 5 (bundle-hash staleness) and item 6 (extractor round-trip) are the two most likely to be wrong in detail, because both depend on runtime behaviour I inferred from docstrings — `models.py:299-303` *describes* an explicit field-by-field writer; I did not read that writer.
- **`_KIND_MAP`/`_classify_artifact_urns`/`query.py` non-exposure is an argument, not a measurement.** It follows from "no new `ArtifactKind`/`NodeKind` member," which is a design choice I am making, not a property I verified end-to-end. If any downstream consumer needs the value set to be `charter activate`-able, the whole exemption collapses and the full 41–59-file cost returns.
- **The matrix cells in shape #1 are illustrative and I invented them.** The verdict's correction 9 stands: the authored first-order matrix is not in this repository and both in-repo copies defer to an external URL. I marked them `do NOT hand-invent`, and then hand-invented placeholders to show the shape. Do not ship them.
- **`values` as a field name**: I assert Pydantic v2 reserves only the `model_` prefix. I did not test a model with a `values` field. If it collides, `value_deltas` is the fallback and the corpus import gains a one-line rename.
- **Out of my lens entirely**: whether the 7 axes *should* be adopted (the §5.6 all-non-negative decision is explicitly the operator's), whether the `#2538` gate should run first (planner-priti's call; the verdict says yes and I have no basis to disagree), and the trademark question. I designed the seam; I did not price the mission.
- **I did not re-litigate the rejected design**, per instruction — but one of its objections has a live residue I could not fully discharge: the verdict's §7.3 note that a per-artefact value field "collides with `#2216`'s `component-type` all-artefact sweep." I did not read `#2216`. If that sweep is adding a different field to the same 6 models, the two must be sequenced, and this design's 12-file edit becomes a merge conflict with someone else's 12-file edit.

---

## VERDICT

**Structurally sound — materially more so than the rejected design, and for one specific reason: it needs no new `ArtifactKind`, no new `NodeKind`, no new `Relation`, and therefore does not touch a single one of this repo's fail-closed enum drift-guards or the three silent-drop sites.** That is not a lucky accident of the proposal; it falls out of two facts the proposal half-saw — that `BaseDoctrineRepository` (`src/doctrine/base.py:114-122`) needs only `_schema` and `_glob`, and that a charter section is not a graph node. Once you take both, the "half-open enum" of Part 1 dissolves: there is no type to keep open, because the openness lives in a substitutable artefact and the validation target is the *active* value set rather than a module literal. Parts 2 and 3 are then genuinely cheap — `impacts` is a sibling of `when`/`reason` on `DRGEdge`, and `creed:` is a sibling of `governance:` on `charter.yaml` with the INV-9 chokepoint already built. The design's real exposure is not conceptual; it is the 12-file dual-gate (Pydantic `extra="forbid"` **and** `additionalProperties: false`, only one of which is load-enforced) and the `DoctrineService`-property tripwire, both of which are mechanical and both of which are now written down.

**The one change that most improves it:** stop treating `delta` as a persistence question and make the *composition invariant* the design's centre. It is already authored doctrine — `ammerse-impact-analysis.tactic.yaml:61-62` and `:68` define `base + 0.5×first_order/6` and `overall = base + 0.5×fo + 0.25×so` — so `delta` **is** `base`, it is the only persistable term, and the way to guarantee that is not a rule but a type: make the computed figure a plain frozen dataclass with no `model_dump()`, in a module no writer imports, carrying a mandatory `matrix_id`/`matrix_version` stamp. Every doctrine and charter writer in this repository serializes through `model_dump()` (`src/doctrine/base.py:210`, `src/charter/schemas.py:377`); a projection that cannot produce one cannot be written back, ever, by anybody, including a future agent who does not read this document. Do that and the design's worst failure mode — a computed ripple silently laundered into an authored assessment and then re-composed against itself — is closed by construction rather than by a discipline reminder, which is exactly the bar DIRECTIVE_043 sets.agentId: af50fe3ba00bc15fd (use SendMessage with to: 'af50fe3ba00bc15fd', summary: '<5-10 word recap>' to continue this agent)
<usage>subagent_tokens: 201287
tool_uses: 25
duration_ms: 946196</usage>
