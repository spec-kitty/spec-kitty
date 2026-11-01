---
title: 'ADR: Steps are the mission-type building block; "template" is a doctrine artefact kind'
description: 'A step is the mission-type building block — the existing ACTION node enriched, not a new node kind — while `template` narrows to one doctrine artefact kind.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-07-16'
---

# Steps are the mission-type building block; "template" is a doctrine artefact kind

**Status:** Proposed · **Epic:** #2652 (mission-type unification) · **Builds on:** ADR
`2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes` (S0/S4), the merged #2712 (mission_type as a
DRG node + mission_type→action edges) and #2689 (`template_set` slot). **Grounding:** design + code +
adversarial squad (see `docs/plans/investigations/mission-type-step-model-unification.md`).

## Context

Three forces converged into a naming-and-authority problem:

1. **"template" is an overloaded discriminator.** The word names three disjoint things: `template_set`
   (a per-type flat map of `spec`/`plan` → *scaffold filenames*, #2689), the `template:` DRG artefact kind
   (16 reusable *doctrine exemplars*, #2712), and per-step *prompt/WP templates*. Using "template" as the thing
   a mission type is *made of* conflates a content scaffold with mission-type structure and collides nominally
   with the doctrine artefact kind.

2. **A step split-brain.** `mission_types/<type>.yaml` authors a **flat** `action_sequence` + `template_set`,
   while the rich per-step data already lives in a **separate** `mission-steps/<type>/<step>/step.yaml` tree
   parsed into the live `MissionStep` model (`doctrine/missions/models.py:87-125`, carrying `prompt_template`,
   `agent_profile`, `delegates_to`, `depends_on`) and consumed by the runtime. The DRG extractor reads only the
   flat `action_sequence` (`extractor.py:835`) and never sees `step.yaml`. Two authoring surfaces, one
   structure — the step model is ~70% shipped but not the authority.

3. **A fail-closed regression.** After #2689, `documentation`/`research`/`plan` (all default-activated) carry
   `template_set: null`, so creating a mission of those types hard-fails (`resolver.py:395`). Spec-deliberate,
   but three of four built-in types are uncreatable until their content templates are authored.

## Decision

**Adopt a single vocabulary and a single authority.**

### D1 — "template" is a doctrine artefact kind (narrowed, canonical)

A **template** is a doctrine artefact that is an *example/skeleton* — the existing `NodeKind.TEMPLATE`
population, one artefact kind among directive/tactic/procedure/paradigm/styleguide/toolguide/asset. "Template"
stops being a mission-type structural term.

### D2 — a **step** is the mission-type building block, and a step **is the existing `ACTION`/`MissionStep`

enriched — NOT a new node kind.** Action nodes already *are* the steps (one per `action_sequence` entry, with
`requires` in-edges from the mission type and `scope` out-edges to their governing doctrine). A mission type is
an ordered set of steps; each step carries: `description`, `recommended_role?`, `recommended_model_tier?`, a
parameterizable `prompt`, an optional `template` reference, and (later) `substeps`.

### D3 — one `template:` kind; the **relation** encodes the lifecycle

A step **`instantiates`** a fill-once *skeleton* template (`Relation.INSTANTIATES`, already exists); tactics and
directives **reference** a read-only *exemplar* template. Same `NodeKind.TEMPLATE`, different relation — so
there is no "fourth template," and the two lifecycles (mission-emitted output vs referenced doctrine exemplar)
stay distinguishable. This finishes the `mission_type → step → template` graph-backing that #2712 deferred
(#883) and the "unbacked filename string" ADR `2026-07-15-1` flags at Claim 4.

### D4 — `recommended_role` / `recommended_model_tier` are advisory doctrine **offers**, not routing truth

Routing (which agent, which model) remains a charter/runtime decision (the "doctrine offers / charter activates
/ runtime consumes" spine). Doctrine offers a hint; the runtime/charter retains override authority. The design
MUST define the override seam and switch consumers to read the step grain — role/model is authored in ≥4 places
today (WP frontmatter, `MissionStep.agent_profile`, governance-profile, action-index); consolidation is a win
only if it becomes the single source, not a fifth parallel authority.

### D5 — retain the governing-doctrine `scope` edges

The step schema keeps the `scope` (governing directives/tactics/procedures) edge population — the load-bearing
thing action nodes do today. It is not replaced by `template`/`prompt`.

### D6 — `MISSION_STEP_CONTRACT` is a step's typed I/O

The declared-but-empty `NodeKind.MISSION_STEP_CONTRACT` becomes a step's input/output signature, modelled as a
`step → mission_step_contract` edge (so contracts stay independently reusable/activatable).

## Slices (prioritized by the operator)

**Prio-0 (now):**

- **S-A — Rename / vocabulary.** Narrow "template" to the artefact kind; establish "step" as the mission-type
  structural term across docs, schema comments, and public surfaces. Low code, high clarity; unblocks the rest.
- **S-B — Step authority / alignment.** Collapse the split-brain: make `step.yaml` (the `MissionStep` tree) the
  **authority**; derive `action_sequence` (and `template_set`) as *projections*; teach the DRG extractor to emit
  from the step authority; switch consumers to the step grain (materialize WP role/model as caches, per D4).
  Add `recommended_model_tier` (net-new; authored nowhere today) and the `template` reference to the step
  schema.
- **S-C — Fix missing spec/plan exemplars.** Author the content templates the three default types lack, and
  graph-back them as `step → template` `instantiates` edges (D3) — mint the `spec`/`plan`/`task-prompt`
  scaffolds as `template:` nodes and teach the resolver to resolve-by-URN. This closes the #2689 uncreatable
  regression **and** #2712/#883. Each type's templates hang on *its own* step names (`research`:
  `scoping→methodology→…`; `documentation`: `discover→audit→…`) — do not assume a `specify`/`plan` shape.
  **Re-scoped 2026-07-17 (see Amendment below):** S-C also **retires the persisted `template_set` field**,
  reading the step authority throughout (tidy-first, before authoring); `action_sequence` symmetry is split
  to a distinct follow-up slice.

**Deferred (lower priority):**

- **S-D — Substeps (recursion).** Add a `DECOMPOSES_INTO` relation + a new validator acyclicity DFS (the
  validator guards only `requires`/`specializes_from` today) + nested step URNs. Declare the stop-rule:
  **substeps = doctrine-authored/static; WPs = mission-emitted/dynamic** — never both for the same decomposition.
- **S-E — Guards.** New `NodeKind.GUARD` + a `GATES` relation (net-new artefact modelling; guards are
  engine-baked condition strings today). Separate epic slice.

## Consequences

- **Positive.** One discriminator (steps), one template vocabulary (the artefact kind), one step authority
  (`step.yaml`). The `mission_type → step → template` chain becomes fully graph-backed and activation-gated,
  extending #2712 and subsuming #2689's `template_set` as a transitional read-projection (no rework of either).
  The step model is ~70% shipped, so S-A/S-B/S-C are *promote + graph-back*, not greenfield.
  **Superseded 2026-07-17 (see Amendment):** `template_set` is not retained even as a persisted projection —
  S-C retires the field and computes the projection at the consumption boundary from the step authority.
- **Costs / risks.** ~80 files / ~8 load-bearing seams. The two boundaries that must not be hand-waved into one
  PR: the **filesystem↔URN template duality** (S-C — a compatibility contract, resolve-by-name vs resolve-by-URN)
  and the **consumer read-source switch** for role/model (S-B — else a new parallel authority). Every new
  NodeKind trips the golden-count + `_ARCH_SHARD_N_FILES` arch markers (mechanical). The #2660 meta-less /
  fail-closed path must be preserved at every slice (do not reopen software-dev inference).
- **Explicitly NOT fixed by the schema alone.** The #2689 uncreatable regression is closed only by S-C
  *authoring the missing content*, not by the rename or authority collapse.
- **Deferred without debt.** Substeps and guards are net-new capabilities with their own DRG primitives; both
  ride the existing activation filter when added. Nothing in S-A/S-B/S-C forecloses them.

## Amendment — 2026-07-17: S-C re-scope (retire `template_set` as a persisted field)

**Status:** Accepted (operator direction change; validated by a 3-lens research squad + a 3-lens adversarial
verification squad, all LAND). Mission: `mission-step-creatability-01KXQA6R` (#2724).

**What changed.** The original decision kept `template_set` as a **transitional projected read-field** on
`MissionType` ("reuse the existing mechanism to limit blast radius"). On reflection this was judged a **partial
cutover**: consumption still read a flattened dict instead of the step authority, it perpetuated a **model
collision** with the unrelated scalar `doctrine.template_set` (separated only by the C-008 prose fence), and —
decisively — the still-authorable `MissionType.template_set` field plus the `raw.get("template_set")` fallback
(`mission_type_repository.py:200-201`) left a **live split-brain vector**: a community/pack-authored `template_set`
would be silently honored. All four concerns were confirmed in code.

**New direction.** S-C **retires the persisted `template_set` field** and deletes the raw-YAML fallback; the
single behavioral consumer (`resolve_configured_template`) reads the lazy `ResolvedMissionType.template_set`
`@cached_property`, whose thunk now computes `project_template_set(steps)` from the step authority
(`MissionStepRepository.resolve_all_for_mission_type(type, pack_context=None)`, cached). Sequenced **tidy-first**:
the cutover lands before the three types' content is authored, so they are born on the clean surface and can never
carry the split-brain. A future pack authoring `template_set:` must **fail loudly**, not be silently honored or
dropped.

**Verified (adversarial squad).** Behavior-preserving — proven byte-for-byte at runtime (`stored ==
project_template_set(steps)` for all four types); no `mission_types/*.yaml` authors `template_set`, so the fallback
is already dead code. Blast radius ~4-5 code sites + ~6 field-pin test files; the resolver signature and the
\#2689/#2660 fail-closed guards are untouched; the enduring `TestSoftwareDevProjectionParity` guard is retained
(only the `MissionTypeRepository`-injection half is disposable). The `ResolvedMissionType.template_set` property is
**not** renamed (wide, all-green, no correctness benefit).

**Split off.** The identical persisted-projection pattern for **`action_sequence`** is **not** folded in — it
crosses a categorically different gate (DRG shipped-graph + NFR-002 freshness), a hard non-empty
`validate_action_sequence` invariant, and the eager FSM hot-path — and is filed as a distinct follow-up slice
under #2721.

## References

- `docs/plans/investigations/mission-type-step-model-unification.md` (proposal + full grounding).
- ADR `2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes.md` (Claim 4, S0/S4).
- Merged: #2712 (mission_type DRG node + mission_type→action edges, graph sharding), #2689 (`template_set` slot).
- Deferred edge class: #883 (mission_type→template). Epic: #2652.
