---
title: 'in_tension_with and reconciles_tension DRG edges (retiring opposed_by)'
description: 'Retires `opposed_by` for symmetric, non-transitive `in_tension_with` plus `reconciles_tension` DRG relations, so tension is one traversable graph edge.'
status: Superseded
date: '2026-07-21'
doc_status: superseded
kind: ADR
updated: '2026-07-21T00:00:00Z'
---
# in_tension_with and reconciles_tension DRG edges (retiring opposed_by)

**Filename:** `2026-07-21-1-in-tension-with-drg-edge.md`

**Status:** Superseded by [ADR 2026-07-26-3](2026-07-26-3-impacts-edge-subsumes-in-tension-with.md) (2026-07-26)

> **Do not implement from this ADR.** A signed `impacts` edge subsumes `in_tension_with`:
> `impacts < 0` **is** a tension claim, so the boolean relation retires and a new
> `Relation.IMPACTS` carries the value. `reconciles_tension` survives, re-pointed at
> negative-`impacts` pairs. The symmetric single-edge storage convention described below
> retires with the boolean; symmetric tensions become directed pairs. Kept for history.

**Date:** 2026-07-21

**Deciders:** Stijn Dejongh (operator), Architect Alphonso; input from Lynn Cole (#2537/#2538)

**Technical Story:** [#2537](https://github.com/Priivacy-ai/spec-kitty/issues/2537) (supersedes the `at_tension_with` name proposed there), experiment [#2538](https://github.com/Priivacy-ai/spec-kitty/issues/2538), epic [#2466](https://github.com/Priivacy-ai/spec-kitty/issues/2466); related ADR [2026-07-18-1](2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md) (charter.yaml authoring authority + extractor retirement).

---

## Context and Problem Statement

The Doctrine Reference Graph (DRG) models **obligation** in abundance and **tension** almost not at all. Measured on the current built-in layer (`docs/plans/engineering-notes/doctrine-drg-missing-links-analysis.md`): 255 `requires` + 330 `suggests` edges, and **zero** edges that say "these two rules compete." When two `requires`d directives land in the same activated context with no arbitration, the competition is invisible to the runtime and the agent silently picks which one wins — the "premature victory / quiet deferment" problem #2537 traces.

The only machine-readable "these two are at odds" signal today is the `opposed_by` field, and it is broken three ways:

1. **It is mis-encoded in the graph.** The extractor (`src/doctrine/drg/migration/extractor.py:373-391, 484-494`) maps every `opposed_by` entry to `Relation.REPLACES`. `replaces` is a directional supersession relation; tension is neither directional nor supersession. The live result in `src/doctrine/directive.graph.yaml` is a nonsensical mutual cycle: `DIRECTIVE_024 --replaces--> DIRECTIVE_025` **and** `DIRECTIVE_025 --replaces--> DIRECTIVE_024`. Two co-valid rules cannot each replace the other.
2. **It is consumed inconsistently.** The extractor emits `opposed_by` edges for directives and paradigms but **not** for tactics — the tactic block only walks `references`/`steps`. So `tactics/built-in/change-apply-smallest-viable-diff.tactic.yaml`'s `opposed_by: DIRECTIVE_025` produces no edge at all. The field is dead for one of the three kinds that declare it.
3. **Nothing reads it for its stated purpose.** No activation-time or consistency-check path inspects `opposed_by` or any tension signal. `charter pack consistency-check` (`src/charter/consistency_check.py`) checks reference parity, kind violations, and duplicates — never tension. The lint `ContradictionChecker` (`src/specify_cli/charter_runtime/lint/checks/contradiction.py`) checks ADR-topic clashes and duplicate glossary senses — unrelated to `opposed_by`. The reconciliation prose that already exists inside `025`'s `opposed_by.reason` never reaches an agent as structure.

Separately, `opposed_by` is **semantically overloaded**. Its six live usages split into two different concepts:

- **Genuine tension between two co-valid, activatable artefacts:** `024 ↔ 025` (locality vs boy-scout) and `change-apply-smallest-viable-diff ↔ DIRECTIVE_025`. Both sides are real doctrine, both stay valid, both can be simultaneously active.
- **Rejection of a named anti-pattern:** the three paradigm usages (`domain-driven-design`, `brownfield-onboarding`, `c4-incremental-detail-modeling`) point `opposed_by` at anti-patterns — `anemic-domain-model`, `big-ball-of-mud`, `big-upfront-design`, `code-is-the-documentation`, plus the tactics `database-driven-design`/`single-diagram-architecture`. The anti-pattern targets are **not real doctrine artefacts** — they exist only as phantom nodes the extractor invents in `paradigm.graph.yaml` to hang the (mis-labelled) `replaces` edge on. This is "this good approach supersedes that bad one," which is closer to `replaces` than to tension.

Finally, the codebase is mid-migration **away from field-authored relationships toward authored DRG edges**: WP06/WP07 already moved `specializes-from`/`enhances`/`overrides` from artifact fields to typed edges, guarded by `tests/doctrine/test_relationship_migration.py::test_built_in_relationships_authored_in_drg`, which asserts **no** field-authored relationships remain. ADR 2026-07-18-1 retired the extractor as authoring authority. `opposed_by` is the last field-form relationship holdout, and it points the wrong way against the established direction of travel.

## Decision Drivers

- Make doctrine competition **queryable structure**, not prose buried in 18 artifact bodies.
- Encode tension with correct semantics (symmetric, non-supersession) instead of borrowing `replaces`.
- Give `charter activate` / `charter pack consistency-check` a way to **warn** the operator when co-activated artefacts are in tension, with a concrete resolution.
- Stay on the field→edge migration path (WP06/WP07 precedent, extractor retirement) rather than entrenching a field form.
- Do not force the anti-pattern-rejection usages into a tension shape they do not fit.
- Warn, do not hard-block (Lynn's explicit constraint in #2537).
- Every relation is self-describing, with the glossary holding the same definition (single canonical authority — no drift between code and docs).
- Cascade / multi-tier activation must reach every doctrine artefact kind, so tension between any co-activated kinds can actually surface.

## Considered Options

- **Option A — First-class symmetric `in_tension_with` DRG edge + `reconciles_tension` edge, remove `opposed_by`.** (Chosen.)
- **Option B — Keep `opposed_by` as a field, but wire an activation-time reader for it.**
- **Option C — Add the tension edge but keep `opposed_by` too (dual representation during a deprecation window).**

## Decision Outcome

**Chosen option: "Option A"**, because it fixes the semantics, aligns with the field→edge migration already in flight, and gives the activation and consistency-check surfaces a single graph relation to traverse. The operator decisions below (Decisions 1–6, plus a related cross-cutting directive on cascade coverage) are the binding content of this ADR.

### Decision 1 — Relation name is `in_tension_with`

Add `IN_TENSION_WITH = "in_tension_with"` to `Relation` (`src/doctrine/drg/models.py`). This supersedes the `at_tension_with` name proposed in #2537 (grammatically correct: "A is in tension with B"). Feasible with no ripple: `Relation` is a plain `StrEnum` consumed by string comparison; there are **no exhaustive `match`/`case` statements over `Relation`** anywhere in `src/`, so a new member breaks no exhaustiveness contract. `graph.yaml` fragments validate against the enum via Pydantic, so the member must exist before any fragment authors the relation.

### Decision 2 — `in_tension_with` is symmetric, NOT transitive

**Symmetric (bidirectional):** `A in_tension_with B` implies `B in_tension_with A`. (The operator's note "A→B means A→C" is a typo for the symmetric closure "A→B ⇒ B→A"; the corrected semantics are stated here explicitly.)

**Not transitive:** `A⋈B` and `B⋈C` do **NOT** imply `A⋈C`. Transitivity is never computed; the checker inspects only declared pairs.

**Storage recommendation — store one canonical edge, treat symmetrically at query time.** DRG edges are directed (`source`→`target`) and every existing consumer, including the cascade forward-closure, assumes direction. The DRG has no symmetric relation today. The two viable encodings are:

- *(a) Store one edge, query both directions.* Author a single `A --in_tension_with--> B`. The tension checker builds the undirected view by unioning `graph.edges_from(urn, IN_TENSION_WITH)` and `graph.edges_to(urn, IN_TENSION_WITH)` (both helpers already exist on `DRGGraph`).
- *(b) Materialize both directions.* Author `A→B` and `B→A`.

**Recommend (a).** It keeps authoring DRY and — critically — removes a live data-integrity smell: today's `024`/`025` pair carries **two divergent `reason` texts** pointing opposite ways, which can (and did) drift. One canonical edge has one canonical reason. Materializing both directions doubles the authoring surface and invites exactly that drift, and it buys nothing because cascade must not follow this relation anyway (Decision 3). Canonical direction: author from the lexicographically-smaller URN to the larger, so the pair is deterministic and de-duplicable.

### Decision 3 — Activation and consistency-check FLAG co-activated tension; two resolution paths

When two artefacts that are `in_tension_with` each other are both active (or both about to be activated), the tooling raises an operator-facing finding. A tension pair `(A, B)` is treated as **resolved** iff **either**:

- **(a) Non-activation of one side** — A and B are not both in the active set; or
- **(b) Reconciliation artefact(s) bridge both sides** — each side has an **active** `reconciles_tension` edge pointing at it. This is the implemented general rule: the checker tests **per-side URN membership** in the set of reconciled targets (any active artefact with a `reconciles_tension` edge into that URN counts), not "does a single artefact `R` carry edges to both." The common case is one active artefact `R` with edges `R --reconciles_tension--> A` and `R --reconciles_tension--> B`; the rule is equally satisfied by two **distinct** active artefacts `R1 --reconciles_tension--> A` and `R2 --reconciles_tension--> B`, each bridging one side. `R`/`R1`/`R2` are local (or built-in) doctrine artefacts whose bodies carry the reconciliation guidance; the `reconciles_tension` edge(s) are how the graph records that the adjudication reaches this specific pair — a single reconciler spanning both sides is a special case of per-side bridging, not a separate, stricter requirement.

Add `RECONCILES_TENSION = "reconciles_tension"` to `Relation`. A pair is resolved by (b) only when **each** side has at least one active `reconciles_tension` edge pointing at it — a pair with only one side bridged (a half-reconciled pair, whichever artefact(s) are involved) is still flagged as unreconciled.

**Where it hooks in:**
- `charter pack consistency-check` (`run_consistency_check`, `src/charter/consistency_check.py`) is the natural home. It already loads the activation-filtered DRG (`filter_graph_by_activation`) and holds the per-kind activation set. Add a new finding category (e.g. `tension_unreconciled`) computed from the activated graph's `in_tension_with` pairs minus those satisfied by (a) or (b). Keep it advisory (see consequences) rather than flipping `coherent` to hard-fail by default.
- `charter activate` (`src/specify_cli/cli/commands/charter/activate.py`) surfaces the same check as a `[yellow]Warning[/yellow]` for the artefact being activated, alongside the existing no-cascade warning path.

**Cascade integration (`REFERENCE_RELATIONS`).** Both new relations are deliberately **excluded** from `charter.cascade.REFERENCE_RELATIONS`:

- `in_tension_with` must **not** cascade — activating `A` must never auto-activate its opponent `B`; that would manufacture the exact conflict we are trying to make visible.
- `reconciles_tension` must **not** cascade — a reconciler (`R`, or `R1`/`R2` when the two sides are bridged separately) reconciles `A` and/or `B` but does not *require* them; the reconciliation is only meaningful when `A` and `B` are already both active, so activating a reconciler must not drag them in.

So the cascade reference set stays `{REQUIRES, SUGGESTS, REFINES}`. The tension checker reads these two relations directly off the graph; it does not ride the cascade closure. This keeps the cascade engine's "pure reachability, no per-kind logic" contract intact.

### Decision 4 — Remove `opposed_by`, superseded by the edge representation

`opposed_by` predates the DRG, is less maintainable, is mis-encoded (Decision context), and fights the field→edge migration. Remove it. Genuine tensions become `in_tension_with` edges; the anti-pattern-rejection usages become `rejects` edges (Decision 5).

### Decision 5 — `rejects` relation for anti-pattern rejection; anti-pattern/smell artefacts carry a marker

The paradigm `opposed_by` usages that point at anti-patterns (`anemic-domain-model`, `big-ball-of-mud`, `big-upfront-design`, `code-is-the-documentation`, plus tactic targets `database-driven-design` / `single-diagram-architecture`) are **rejections of a bad approach**, not tension between co-valid peers. Add `REJECTS = "rejects"` to `Relation`: a directional edge `good-artefact --rejects--> anti-pattern`. This supersedes the earlier "keep them as `replaces`" fallback — `replaces` implies the target was once a valid predecessor, which an anti-pattern never was. `rejects` is directional (not symmetric) and does **not** cascade (excluded from `REFERENCE_RELATIONS` alongside the tension relations).

The anti-pattern targets must be **first-class, marked nodes**, not phantom nodes the extractor invents. Anti-pattern / smell artefacts carry an explicit marker — a `tags`/`labels` attribute (e.g. `tags: [anti-pattern]` or `[smell]`) — so consumers, the rejection/tension checkers, and rendered agent context can distinguish "avoid this" targets from ordinary doctrine. This makes `rejects` validatable (a `rejects` edge must terminate at a marked anti-pattern/smell node) and keeps the graph honest about which nodes represent things to avoid rather than things to do.

### Decision 6 — Every `Relation` member is self-describing, with glossary parity

Each `Relation` enum member MUST carry a human-readable description of its meaning at the point of definition (`src/doctrine/drg/models.py`), and the project glossary MUST hold the same definition. The three members introduced by this ADR — `in_tension_with`, `reconciles_tension`, `rejects` — each get a description in the enum and a matching glossary entry; this is also a standing rule applied to existing relations going forward. Single canonical authority (charter principle): the enum description and the glossary definition are the same text (or, for the human-facing `docs/context` glossary, a definition drawn from it), so relation semantics cannot drift between code and docs.

**Actual enforcement surfaces (as implemented):** `RELATION_DESCRIPTIONS` in `src/doctrine/drg/models.py` is the single canonical authority for the description text. `docs/architecture/doctrine-relationships.md` ("Tension vocabulary" section) mirrors that text verbatim for human readers, and `tests/doctrine/test_relation_doc_parity.py` is a content-equality test that fails red — naming the diverging relation — the moment that mirror drifts from the registry. The human-facing project glossary (`docs/context/charter.md`) additionally carries `in_tension_with`, `reconciles_tension`, and `rejects` as glossary entries, with definitions drawn from the registry text; the other nine pre-existing `Relation` members (`requires`, `suggests`, `refines`, `replaces`, `specializes_from`, `delegates_to`, `enhances`, `overrides`, `applies`, `scope`, `vocabulary`, `instantiates`) do not yet have individual `docs/context` glossary entries — backfilling those is out of scope here (spec.md Assumption A2) and is tracked as follow-up. There is no separate "terminology guard / glossary integrity pipeline" test wired to this parity obligation today; `test_relation_doc_parity.py` (scoped to `doctrine-relationships.md`) is the concrete, executable guard, and the `docs/context/charter.md` entries are presently maintained by convention rather than an automated content-equality check.

### Related operator directive (broader than this ADR) — cascade applies to ALL doctrine artefact kinds

The operator directs that the cascade / multi-tier pack + charter-activation system apply to **every** doctrine `artefactKind`, not just the subset reachable today. This is the substrate the tension check (Decision 3) depends on: if activation cannot co-activate scoped directives/tactics/templates across kinds, tension between them can never surface. The missing-links analysis on this branch shows cascade currently dead-ends — `REFERENCE_RELATIONS` reaches actions from a mission-type but not the directives/tactics/templates those actions `scope`/`instantiate`. Making cascade kind-complete is broader than tension and is recorded here as the governing directive; the concrete relation-coverage work is its own design/mission scope (candidate for a dedicated ADR under epic #2466). Interaction note: `in_tension_with` / `reconciles_tension` / `rejects` remain **excluded** from the cascade reference set even under kind-complete cascade — Decision 3's rationale is unchanged.

### Note — `delegates_to` is a topological relation with little/no runtime impact today

`delegates_to` is a doctrine relation (an authored edge between agent profiles) that currently carries essentially **no runtime behaviour** — the missing-links analysis on this branch measured **zero** `delegates_to` edges in the built-in layer. It is recorded here so future readers do not mistake it for dead vocabulary. Its intended purpose is to enable **loose-governance, self-organizing cooperation between agents**, as an alternative to running a full scripted mission. The model: the operator opens a limited-scope op and simply says "get it done"; the agents then **swarm and self-steer along the `delegates_to` edges** rather than following a mission pipeline. Illustrative chain — Alphonso writes an ADR → a reviewer/writer agent reviews it → an implementation agent automates the change → the writer agent updates the docsite, each handoff following a `delegates_to` edge. Making `delegates_to` runtime-effective (a self-steering delegation loop) is future scope, independent of the tension edges decided here; the relation is documented so its intent survives until that work is scheduled.

### Consequences

#### Positive

- Tension becomes queryable: one relation the activation and consistency surfaces can traverse, and one relation an agent's composed context can render ("these two compete; here is how they reconcile").
- The nonsensical mutual `replaces` cycle on `024`/`025` disappears; supersession semantics stop being borrowed for tension.
- The tactic tension (`change-apply-smallest-viable-diff ↔ 025`) that the extractor silently dropped is now representable — a previously-lost signal is recovered.
- Removing the last field-form relationship completes the WP06/WP07 migration direction and keeps `test_relationship_migration.py`'s "no field-authored relationships" invariant honest.
- One canonical edge = one canonical reason; the divergent-reason drift on `024`/`025` is eliminated.

#### Negative

- The built-in default pack ships `024` and `025` **both active** and **in tension**, so a naive hard-block would fail the default pack out of the box. Mitigation: ship a **built-in reconciliation artefact** for the `024`/`025` (and `smallest-viable-diff`/`025`) pair — the reconciliation text already exists verbatim in `025`'s `opposed_by.reason` — and wire it with `reconciles_tension` edges so the default pack is self-consistent. Until that artefact exists, the tension check must be advisory, not coherence-failing. This matches Lynn's "warn, do not hard-block."
- Removal touches schemas, models, the shared `Contradiction` model, the extractor, six built-in YAMLs, generated graph fragments, docs, and tests in one migration (blast radius below). The dead-symbol gate requires `Contradiction` and the `contradiction` schema definition to be removed once the last field usage is gone.
- Introduces the DRG's first symmetric relation; every future tension consumer must remember to query both directions (documented in Decision 2).

#### Neutral

- The anti-pattern-rejection paradigm usages are re-classified to `rejects` edges, not deleted (Decision 5 / Migration). The phantom anti-pattern nodes are promoted to first-class marked nodes (`tags: [anti-pattern]`) rather than extractor-invented.
- No change to the cascade reference set — the three new relations stay excluded even under the kind-complete cascade directive.
- Cascade kind-completeness (related directive) is broader than this ADR and lands as separate scope; this ADR only records the directive and its dependency relationship to the tension check.

### Confirmation

- `Relation.IN_TENSION_WITH`, `Relation.RECONCILES_TENSION`, and `Relation.REJECTS` exist, each with a description; `graph.yaml` fragments validate.
- `docs/architecture/doctrine-relationships.md` defines `in_tension_with`, `reconciles_tension`, `rejects` with text matching the enum descriptions verbatim (Decision 6); `tests/doctrine/test_relation_doc_parity.py` passes. `docs/context/charter.md` additionally carries a human-glossary entry for each of the three relations, consistent with the enum descriptions.
- `grep -rn "opposed_by" src/` returns no hits across the doctrine authoring surfaces after migration (field, schema, model, extractor, built-in YAML); the only remaining `src/` hits are the `spec-kitty migrate rewrite-opposed-by` subcommand (`migration/rewrite_opposed_by.py`, `cli/commands/migrate_cmd.py`), which names the legacy field it rewrites for downstream/org packs.
- `tests/doctrine/test_relationship_migration.py::test_built_in_relationships_authored_in_drg` still passes (no field-authored relationships).
- Every `rejects` edge terminates at a node marked `tags: [anti-pattern]`/`[smell]` (Decision 5) — a test asserts no `rejects` edge points at an unmarked node.
- A focused test asserts: (i) `024`/`025` resolves to a single `in_tension_with` edge, not a `replaces` cycle; (ii) an unreconciled active tension pair produces the new consistency finding; (iii) adding an active `reconciles_tension` artefact clears it; (iv) activating one side of a tension does **not** cascade-activate the other; (v) the paradigm anti-pattern usages resolve to `rejects` edges, not `in_tension_with`.
- Confidence: high on Decisions 1, 2, 4, 5, 6 (mechanical, precedented); medium on Decision 3's default-pack self-consistency (depends on authoring the built-in reconciliation artefact before any hard-block is enabled). The cascade-all-kinds directive is out of scope for confirmation here.

## Migration plan and blast radius

**Concept split governs the migration.** Only genuine two-active-artefact tensions become `in_tension_with`. The paradigm anti-pattern rejections are a different concept and MUST NOT be forced into symmetric tension (doing so would falsely claim "big-ball-of-mud is in tension with DDD" and demand a reconciliation artefact for an anti-pattern). Their disposition (Decision 5): author them as directional `rejects` edges, and mark each anti-pattern/smell target node with a `tags`/`labels: [anti-pattern]` (or `[smell]`) attribute so it is a first-class node rather than a phantom the extractor invents.

**`replaces` stays canonical — do not remove it.** `replaces` (and the pack-augmentation family `enhances`/`overrides`/`specializes_from`) are canonical relations whose primary role is **multi-tier pack composition** (an org/project pack superseding or augmenting built-in doctrine). Spec Kitty does not currently set up its own multi-tier pack layering, so these relations are sparse-to-absent in the built-in layer **by design** — that is expected, not a gap. This migration removes `replaces` edges **only** where they were mis-minted from `opposed_by` (the `024↔025` cycle and the paradigm anti-pattern usages); every other `replaces` edge is left intact. The relations this ADR removes from the codebase entirely are the **phantom lint-only relations `governs` and `supersedes`** (never enum members, never authorable — see the orphan-rule cleanup), not `replaces`.

**`in_tension_with` edges to author (genuine tensions):**
- `directive:DIRECTIVE_024 ↔ directive:DIRECTIVE_025` — one canonical edge in `src/doctrine/directive.graph.yaml`, replacing the two mutual `replaces` edges.
- `tactic:change-apply-smallest-viable-diff ↔ directive:DIRECTIVE_025` — one edge (previously never emitted).

**Blast radius (concrete file/impact list):**

| Area | File | Impact |
| --- | --- | --- |
| Enum | `src/doctrine/drg/models.py` | Add `IN_TENSION_WITH`, `RECONCILES_TENSION`, `REJECTS` to `Relation`; each member carries a description (Decision 6); document symmetric-not-transitive for `in_tension_with`. |
| Doc parity | `docs/architecture/doctrine-relationships.md`, `tests/doctrine/test_relation_doc_parity.py` | Mirror the enum descriptions verbatim for `in_tension_with`, `reconciles_tension`, `rejects`; enforce content-equality parity against `RELATION_DESCRIPTIONS` with a dedicated test (Decision 6). |
| Glossary | `docs/context/charter.md` | Add human-glossary entries for `in_tension_with`, `reconciles_tension`, `rejects`, consistent with the enum descriptions (Decision 6). |
| Node marker | anti-pattern/smell target nodes | Add `tags`/`labels: [anti-pattern]` (or `[smell]`) marker to anti-pattern nodes so `rejects` targets are first-class and validatable (Decision 5). |
| Schema | `src/doctrine/schemas/directive.schema.yaml` | Remove `opposed_by` property + the `contradiction` definition. |
| Schema | `src/doctrine/schemas/tactic.schema.yaml` | Remove `opposed_by` property + `contradiction` definition. |
| Schema | `src/doctrine/schemas/paradigm.schema.yaml` | Remove `opposed_by` property + `contradiction` definition. |
| Model | `src/doctrine/directives/models.py` | Remove `opposed_by` field + `Contradiction` import. |
| Model | `src/doctrine/tactics/models.py` | Remove `opposed_by` field + `Contradiction` import. |
| Model | `src/doctrine/paradigms/models.py` | Remove `opposed_by` field + `Contradiction` import. |
| Model | `src/doctrine/shared/models.py` | Remove now-dead `Contradiction` model + `__all__` entry (dead-symbol gate). |
| Extractor | `src/doctrine/drg/migration/extractor.py` | Remove both `opposed_by` blocks (directive ~373-391, paradigm ~484-494) that emit `Relation.REPLACES`. (No tactic block exists — the tactic field was never extracted.) Extractor is retired as authoring authority (ADR 2026-07-18-1) but the code path still runs; leaving the blocks would keep minting `replaces` from a removed field. |
| Built-in YAML | `src/doctrine/directives/built-in/024-locality-of-change.directive.yaml` | Remove `opposed_by`. |
| Built-in YAML | `src/doctrine/directives/built-in/025-boy-scout-rule.directive.yaml` | Remove `opposed_by`; preserve its reconciliation text (source for the built-in reconciliation artefact). |
| Built-in YAML | `src/doctrine/tactics/built-in/change-apply-smallest-viable-diff.tactic.yaml` | Remove `opposed_by`. |
| Built-in YAML | `src/doctrine/paradigms/built-in/domain-driven-design.paradigm.yaml` | Remove `opposed_by`; its rejections re-express as authored `rejects` edges. |
| Built-in YAML | `src/doctrine/paradigms/built-in/brownfield-onboarding.paradigm.yaml` | Same. |
| Built-in YAML | `src/doctrine/paradigms/built-in/c4-incremental-detail-modeling.paradigm.yaml` | Same. |
| Generated graph | `src/doctrine/directive.graph.yaml` | Replace the two `024↔025` `replaces` edges with one `in_tension_with` edge. |
| Generated graph | `src/doctrine/paradigm.graph.yaml` | Author the paradigm rejection `rejects` edges; promote phantom anti-pattern targets to marked nodes (`tags: [anti-pattern]`). |
| Generated graph | `src/doctrine/tactic.graph.yaml` | Author the `smallest-viable-diff → 025` `in_tension_with` edge. |
| New built-in | reconciliation directive/tactic + `reconciles_tension` edges | Ship a reconciliation artefact for the `024`/`025` (and smallest-diff/`025`) tension so the default pack is self-consistent under the check. |
| Orphan lint (#2737) | `src/specify_cli/charter_runtime/lint/checks/orphan.py` | Remove the phantom `governs` (directive) and `supersedes` (adr) branches from `_ORPHAN_RULES` — neither is a `Relation` enum member, so neither is ever authorable; they misfire on 100% of directives. Retire those branches (or, for directives, re-point at the relations that actually reach them: `scope`/`requires`/`suggests`) so only the 2 genuinely-disconnected directives surface. Closes #2737. |
| Consistency check | `src/charter/consistency_check.py` | Add the `tension_unreconciled` finding computed over the activation-filtered graph. |
| CLI | `src/specify_cli/cli/commands/charter/activate.py` | Surface the tension warning on activate. |
| Docs | `docs/architecture/04_implementation_mapping/README.md` (lines ~250, 260-263, 310-312, 335) | Replace `opposed_by` reference-direction + "Contradiction semantics" + schema-table + status-table entries with the edge model. |
| Docs | `docs/guides/synthesize-doctrine.md` | Update the contradictions mention. |
| Tests | `tests/doctrine/test_directive_consistency.py` | Drop/replace `opposed_by` assertions. |
| Tests | `tests/doctrine/drg/migration/test_extractor.py` | Drop the `opposed_by → replaces` mapping test; add the new-edge expectations. |
| Fixtures | `tests/doctrine/fixtures/paradigm/valid/with-tactic-refs.yaml` | Drop `opposed_by` (schema `additionalProperties: false` will reject it). |

**Runtime-read safety confirmed.** `grep -rn "opposed_by" src/` shows the only runtime *readers* are the extractor blocks (→ `replaces`). Nothing else reads the field: not the models beyond declaration, not `consistency_check.py`, not the lint `ContradictionChecker` (which is about ADR topics/glossary), not `charter activate`. Removing the field therefore silently breaks nothing at runtime — the only behavioral change is that the mis-encoded `replaces` edges stop being minted.

## Pros and Cons of the Options

### Option A — symmetric `in_tension_with` + `reconciles_tension`, remove `opposed_by` (chosen)

**Pros:** correct semantics; queryable at activation/consistency-check; completes the field→edge migration; recovers the dropped tactic tension; one canonical reason per pair.
**Cons:** first symmetric relation (consumers must query both directions); default pack needs a reconciliation artefact before any hard-block; multi-file migration touching the dead-symbol gate.

### Option B — keep `opposed_by` as a field, add a reader

**Pros:** smaller diff; no enum change.
**Cons:** entrenches the field form against the WP06/WP07 direction and ADR 2026-07-18-1; leaves the field consumed inconsistently across kinds (dead for tactics); the graph still lacks a tension relation, so cascade/lint/consistency all keep improvising; the mis-encoded `replaces` edges persist.

### Option C — dual representation (edge + field) during a deprecation window

**Pros:** gradual migration.
**Cons:** two sources of truth for the same fact invite drift (already observed in the `024`/`025` divergent reasons); the "no field-authored relationships" invariant cannot hold during the window; more surface to test and reconcile for no lasting benefit given the small, enumerable usage set (six files).

## More Information

- Analysis: `docs/plans/engineering-notes/doctrine-drg-missing-links-analysis.md` (cascade dead-ends, relation-usage census).
- Migration precedent: `tests/doctrine/test_relationship_migration.py` (field→edge, zero-loss, no-field invariant).
- Cascade engine + reference set: `src/charter/cascade.py` (`REFERENCE_RELATIONS`).
- Consistency check surface: `src/charter/consistency_check.py`; CLI `spec-kitty charter pack consistency-check`.
- Related: ADR 2026-07-18-1 (charter.yaml authoring authority, extractor retirement).
