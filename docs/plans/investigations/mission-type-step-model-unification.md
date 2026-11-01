---
title: 'Mission-type step-model unification — retire "template" as a discriminator'
description: 'Operator proposal to reserve "template" for doctrine example-artefacts and make recursive steps the mission-type building block; assessment + grounding questions.'
doc_status: deprecated
updated: '2026-08-12'
related:
- architecture/mission-type-resolution
- adr/3.x/2026-07-15-1-doctrine-offers-charter-activates-runtime-consumes
---

> **RETIRED (shipped)** — this investigation's proposal was ratified and delivered:
> formalized in ADR [`2026-07-16-2`](../../adr/3.x/2026-07-16-2-mission-type-step-authority-and-template-vocabulary.md)
> (#2658) and shipped by mission `templates-as-config-01KXMS1G`. Retained for historical
> reference; do not consult for current behavior.

# Mission-type step-model unification

> Status: **investigation / proposal** (not yet a spec or ADR). Captured on the `feat/templates-as-config`
> (#2658) branch to inform where the `template_set` seam should evolve.

## 1. The problem — "template" is an overloaded discriminator

Across the recently-merged doctrine work the word **template** names three disjoint things, and it is being
used as a *structural discriminator* for mission types where it should not be:

1. **`template_set`** (PR #2689 / #2658) — a flat per-mission-type map of semantic keys → *content-scaffold
   filenames* (`spec: spec-template.md`, `plan: plan-template.md`), resolved through the 5-tier filesystem.
2. **`template:` DRG nodes** (PR #2712 / #2680) — 16 graph-modelled *doctrine example artefacts*
   (`template:c4-context-mermaid-template`, `template:glossary-template`, …) referenced by governance; today
   edge-less.
3. **Per-step prompt/WP templates** — `task-prompt-template.md`, per-action prompts under
   `missions/<type>/templates/` — the instructions that drive an agent *through* a step.

These are different populations with different consumers. Using "template" (and `template_set`) as the thing a
mission type is *made of* conflates a content scaffold with the mission-type structure and collides nominally
with the doctrine `template:` artefact kind. (See `docs/investigation`-adjacent analysis and the
mission-type-resolution ADR §"bundle shaped to grow".)

## 2. Operator decision — the canonical vocabulary

**Reserve "template" for doctrine example-artefacts, and make *steps* the building block of mission types.**

### 2a. `template` (narrowed, canonical)

A **template** is a *doctrine artefact that is an example* — referenced *by* tactics, directives, procedures,
etc. (e.g. a C4 context diagram skeleton, a glossary example, an analysis-canvas exemplar). This is exactly the
existing `template:` DRG artefact kind (`NodeKind.TEMPLATE`). "Template" stops being a mission-type structural
term; it is one doctrine artefact kind among directive/tactic/procedure/paradigm/styleguide/toolguide/asset.

### 2b. `step` — the mission-type building block (the unification)

A **mission type is an ordered tree of steps.** Each **step** carries:

| Field | Optional? | Meaning |
|-------|-----------|---------|
| `description` | required | What the step accomplishes. |
| `recommended_role` | optional | The agent profile suited to it (e.g. `python-pedro`, `reviewer-renata`). Advisory. |
| `recommended_model_tier` | optional | The model class suited to it (e.g. `sonnet`, `opus`). Advisory. |
| `prompt` | required | A **parameterizable** prompt — the instruction that drives an agent through the step, with substitution parameters. |
| `template` | optional | A reference to a doctrine **`template:` artefact** (2a) — the example/skeleton the step's output should resemble or fill in. |
| `substeps` | optional | An ordered list of child **steps** (recursion) — a step decomposes into finer steps. |

This one structure subsumes today's scattered concepts:

- **`template_set` (flat filename map)** → becomes the `template` field of the relevant steps (the `specify`
  step's `template` = the spec skeleton; the `plan` step's `template` = the plan skeleton). No separate
  type-level template map.
- **per-step prompt/WP templates** → become each step's `prompt` (parameterizable).
- **WP-frontmatter `agent_profile` / `model`** → become `recommended_role` / `recommended_model_tier` at the
  step grain, authored in doctrine rather than emitted per-mission.
- **`action_sequence` action nodes** → *are* the top-level steps; `substeps` adds the recursion actions lack today.
- **guards** → gate steps (a future concern; no `GUARD` kind exists yet).

## 3. Why this is coherent

- **One discriminator, one vocabulary.** Mission types are made of **steps**; doctrine has example
  **templates**. The nominal collision disappears — "template" always means the artefact kind.
- **Richer + recursive.** Steps gain description/role/model-tier/prompt and, crucially, **substeps** — the
  recursion that lets a coarse step (e.g. `implement`) decompose into finer authored steps, which the current
  flat `action_sequence` cannot express.
- **Config-carried, activation-gated.** A step's `template` reference and `prompt` are doctrine the mission
  type *carries* and the charter *activates* — the same "doctrine offers / charter activates / runtime
  consumes" spine the governing ADR establishes.
- **`template_set` becomes a clean transitional subset.** #2689's flat 2-key map is exactly the `template`
  field of the `specify`/`plan` steps, expressed before the step model existed. It grows *into* this model
  additively (per the ADR's "bundle shaped to grow"), not a throwaway.

## 4. Assessment (orchestrator) — promising, with three things to resolve

**Verdict: architecturally sound and the right direction — it resolves the naming collision at the root and
gives the "steps + guards, each step a template" model a concrete shape. Three items need grounding before it
becomes a spec:**

1. **`template` (step field) vs `template:` (doctrine artefact) must be the SAME population.** The step's
   `template` should be a *reference to a `template:` DRG node*, not another loose filename — otherwise we
   re-introduce a fourth "template." That means the current `spec-template.md`/`plan-template.md` content
   scaffolds must become `template:` doctrine artefacts (minting a `template:spec-skeleton` / `template:plan-skeleton`
   node population and a `step → template` DRG edge), unifying the graph-backed and filesystem notions. This is
   the `mission_type → template` edge class #2712 explicitly *deferred* (#883) — this proposal is its
   motivation and design.
2. **Steps as a first-class recursive DRG population.** Today steps are `action:*` nodes (flat, one grain).
   `substeps` needs either a recursive `action:*/…` URN scheme or a new step model with parent/child edges, plus
   a `step → template` and (future) `step → guard` edge class. How this relates to the existing
   `MISSION_STEP_CONTRACT` NodeKind must be settled (is a step contract the typed I/O of a step in this model?).
3. **Migration + backward-compat surface.** `action_sequence`, `template_set`, action `index.yaml` files, WP
   prompt templates, and WP-frontmatter role/model are all live inputs. The proposal reframes all of them.
   Scope, sequencing, and the fail-closed/legacy paths (#2660) need a real migration plan — this is a
   multi-slice epic (#2652) effort, not a single PR.

## 5. Open questions for the design-and-code grounding squad

- **Design coherence:** does the step tree (description/role/tier/prompt/template/substeps) cleanly subsume
  `template_set` + action nodes + WP-frontmatter role/model + per-step prompts, with no orphan concept? Where
  does `MISSION_STEP_CONTRACT` fit (step I/O)? Where do guards attach (step-level, and via what kind)?
- **Code grounding:** what surfaces does this touch — `mission_types/*.yaml` schema, `action/*/index.yaml`,
  `MissionTypeRepository`, `mission_type_profiles.resolve_mission_type_context`, the DRG generator
  (`extractor.py` node/edge emission), the resolver (`resolve_configured_template`), WP generation
  (`/tasks`), and the runtime loop? Is the model expressible in the current DRG (`NodeKind`/`Relation`) or does
  it need new kinds (`STEP`? `GUARD`?) and edge classes (`step→template`, `step→substep`, `step→guard`)?
- **Conflict / continuity:** does this contradict the just-merged #2712 (mission_type→action edges) and #2689
  (`template_set`), or subsume them as first drafts? Is `action` == top-level `step` (rename), or a distinct
  kind? Confirm the recursion doesn't break the DRG acyclicity/validation invariants.
- **Realism:** is the optional role/model-tier authored-in-doctrine the right place (vs emitted per-mission at
  `/tasks`)? Does a parameterizable `prompt` at the step grain replace the WP prompt template cleanly?
- **Sizing:** is this one ADR + a multi-WP mission under #2652, or does it need to be sliced (steps-as-nodes →
  step-templates-as-edges → substeps → guards)? What is the smallest coherent first slice?

## 6. Grounding squad findings (design + code + adversarial)

Three profile-loaded lenses grounded §5 against the ADR and the live worktree. Consolidated verdict:
**the naming narrowing is a solid, root-level win — adopt it; the *unification* is feasible incrementally but
carries several design decisions and one unfixed bug that must be settled/sliced, not hand-waved.**

- **architect-alphonso (design) → COHERENT.** Realizes ADR Claim 4 *more* fully than the ADR's own S4;
  extends #2712 and subsumes #2689 without contradiction.
- **paula-patterns (code) → FEASIBLE-INCREMENTAL.** ~80 files / ~8 load-bearing seams; shimmable, additive.
- **reviewer-renata (adversarial) → SOUND-WITH-CAVEATS.** Rename correct; unification over-claims on 6 points.

### 6a. The decisive discovery — the step already ships (promote, don't invent)

`src/doctrine/missions/mission-steps/<type>/<step>/step.yaml` already parses into the `MissionStep` model
(`doctrine/missions/models.py:87-125`) and is **live-consumed by the runtime** (`runtime_bridge*`, planner).
It already carries `prompt_template` (= proposal `prompt`), `agent_profile` (= `recommended_role`),
`delegates_to`, `depends_on`. **~70% of the proposed step is already implemented.** The real problem is a
**split-brain**: `mission_types/*.yaml` authors a FLAT `action_sequence` + `template_set`, while the rich
per-step data lives in a SEPARATE `step.yaml` tree — and the DRG extractor reads only the flat list
(`extractor.py:835`), so the graph never sees `step.yaml`. This is *promote the existing step model to
authority + retire the parallel flat surface*, not a greenfield build. Net-new fields are only three:
`recommended_model_tier` (authored nowhere today), `template` (step→`template:` edge), `substeps` (recursion).

### 6b. Decisions the squad settled (fold into the eventual spec)

1. **"step" = the existing `ACTION`/`MissionStep`, ENRICHED — NOT a new `STEP` kind.** Action nodes already
   ARE the steps (24 nodes, 21 `requires` in-edges, 157 `scope` out-edges). A parallel `STEP` kind would
   double-model and orphan 178 edges. The `action→step` rename buys zero modelling value — defer it
   indefinitely. **Substeps are the only structurally new capability.**
2. **`step.template` uses the ONE `template:` NodeKind — the *relation* encodes the lifecycle** (resolving the
   alphonso↔renata split). A step `instantiates` a fill-once *skeleton* template (`Relation.INSTANTIATES`,
   already exists); tactics/directives *reference* a read-only *exemplar* template. Same kind, different
   relation — so there is no "fourth template" (alphonso) AND the two lifecycles stay distinguishable (renata).
   This requires minting the `spec`/`plan`/`task-prompt` scaffolds as `template:` nodes and teaching the
   5-tier resolver to resolve-by-URN (paula's Risk 1 — the filesystem↔URN duality).
3. **`recommended_role`/`recommended_model_tier` are ADVISORY doctrine *offers*, not routing truth.** Routing
   (which agent, which model) is a charter/runtime choice per the ADR spine. Baking a value into shipped
   doctrine freezes operational config in the offer layer (renata). The spec MUST define the override seam and
   the consumer read-source switch — role/model is authored in ≥4 places today (WP frontmatter,
   `MissionStep.agent_profile`, governance-profile, action-index); consolidation is only a win if consumers
   switch to read the step grain, else it becomes a 5th parallel authority (paula's Risk 3).
4. **Substeps need a new `DECOMPOSES_INTO` relation + a new validator acyclicity DFS.** URNs already allow
   nested paths; but the validator only cycle-checks `requires`/`specializes_from` (`validator.py:78,145`), so
   a substep edge is unguarded today — recursion is safe *only* with the new check. Do NOT overload `requires`.
5. **Retain the governing-doctrine `scope` edges (the orphan).** The step schema in §2b has no slot for "which
   directives/tactics/procedures govern this step" — the 157 `scope` out-edges. That population must survive.
6. **`MISSION_STEP_CONTRACT` = the typed I/O of a step** (declared kind, 0 nodes today) — settle whether it's a
   field-bundle on the step or a `step→mission_step_contract` edge (lean: edge, so contracts stay reusable).

### 6c. Two things the unification does NOT fix (state plainly)

- **The #2689 "3-of-4 default types uncreatable" bug is RELOCATED, not fixed.** Swapping `template_set: null`
  for a null `step.template` still fail-closes at `resolver.py:395`. Closing it requires **populating**
  `documentation`/`research`/`plan` with their own step templates — an authoring task the schema change
  neither performs nor forces (`template` is optional). And do NOT assume `specify`/`plan` steps exist for all
  types — `research` is `scoping→methodology→…`, `documentation` is `discover→audit→…`; each type's templates
  hang on ITS OWN step names, not a software-dev shape (renata).
- **Substeps vs the WP/task tree `/tasks` emits** is a second decomposition axis meeting at `implement` with
  no arbiter (renata). The spec must declare the stop-rule: **substeps = doctrine-authored/static; WPs =
  mission-emitted/dynamic** — a substep is authored decomposition, a WP is a runtime work unit; never both.

### 6d. Revised slice roadmap (Risk-1-first — inverts §2/§4's order per paula + alphonso)

- **Slice 1 (smallest coherent; closes #2712/#883): graph-back `template_set` as `step→template` `instantiates`
  edges.** Mint `template:spec-skeleton`/`plan-skeleton`, teach the resolver URN resolution, wire the
  `ResolvedMissionType.template_set` slot to read the edge. **Zero new NodeKind/Relation/validator change** —
  `INSTANTIATES` exists. De-risks the filesystem↔URN duality in isolation. `template_set` stays a read-shim.
- **Slice 2: collapse the split-brain** — make `step.yaml` the authority; derive `action_sequence`/`template_set`
  as projections; add `recommended_model_tier` + `template` to the step schema; **switch consumers to read the
  step grain** (materialize WP role/model as caches). Preserve the `scope` edges.
- **Slice 3: substeps** — `DECOMPOSES_INTO` relation + validator acyclicity DFS + nested URNs + the
  authored-vs-emitted stop-rule.
- **Slice 4 (separate): guards** — new `GUARD` NodeKind + `GATES` relation (net-new artefact modelling).
- **Cross-cutting:** every new NodeKind trips the golden-count + `_ARCH_SHARD_N_FILES` markers (mechanical);
  preserve the #2660 meta-less/fail-closed path at every slice (do NOT reopen software-dev inference).

### 6e. Recommendation

**Split the proposal.** Land the **rename** (template→artefact, step→structure) as the framing win; treat the
**merges** (template-population unification, role/model relocation, substep decomposition, guards) as
separately-justified slices, each with an explicit override/lifecycle answer, sequenced Risk-1-first. This is a
multi-slice epic under **#2652**, warranting its own ADR that pins the slice order and the six decisions in §6b.
It builds additively on the merged #2712 (kept, foundational) and #2689 (transitional read-shim) — no rework of
either.

---

*Captured by the orchestrator for the operator's step-model unification proposal, grounded by a design + code +
adversarial squad (alphonso COHERENT / paula FEASIBLE-INCREMENTAL / renata SOUND-WITH-CAVEATS). Next step is the
operator's call: promote §6 into an ADR + a sliced epic under #2652, or iterate the proposal further.*
