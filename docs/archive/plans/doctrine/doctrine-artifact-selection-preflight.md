---
title: Pre-flight investigation — user-authored doctrine artifact selection
description: 'Pre-mission investigation by Architect Alphonso into user-authored doctrine-artifact selection: the design questions and constraints ahead of the mission.'
doc_status: deprecated
updated: '2026-06-15'
related:
- docs/archive/plans/doctrine/runtime-charter-doctrine-boundary.md
---
# Pre-flight investigation — user-authored doctrine artifact selection

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Author:** Architect Alphonso (pre-mission investigation)
**Date:** 2026-05-17
**Status:** preflight — does NOT propose implementation. Outputs are: user-journey support analysis, gap inventory, accommodation options, edge-case checklist, and a flow-test plan for the next mission to consume as ATDD spec.

**Related artifacts:**
- Mission A — `kitty-specs/layered-doctrine-org-layer-01KRNPEE/` (the three-layer doctrine model)
- wp-prompt-governance-payload — `kitty-specs/wp-prompt-governance-payload-01KRR8HS/` (profile-directive surfacing)
- The intended **runtime → charter → doctrine** boundary is in scope of a sibling note (see below)

**Related sibling note:** [`runtime-charter-doctrine-boundary.md`](runtime-charter-doctrine-boundary.md) — audit + recommendations for enforcing the layered access boundary that this pre-flight depends on.

---

## Why this note exists

Two user journeys arrived as in-session questions:

> **Case 1.** A user authors a new doctrine artifact (a `caveman-comments.styleguide.yaml` that says "all code comments should be written as a caveman would"). The user plugs it into spec-kitty, then writes a charter that says "all LLM feedback and code comments are to be written in caveman". During a mission run, the implementation prompt must contain something like *"when writing a code comment or responding to the user, first load the caveman styleguide."*
>
> **Case 2.** Same artifact, but distributed via an organisational charter (org id `very-serious-developers`) that team members add to their `.kittify/config.yaml`. Same expected prompt behaviour.

The intent is concrete: the charter is the **selection authority** that decides which doctrine artifacts apply to which contexts; doctrine is the **knowledge store** that holds the artifacts. Multiple doctrine packs may be configured; the charter (project + org) holds a registry of activations keyed on context (mission type + action, or generic), and the agent profile set is itself a charter-resolved subset.

This note records what the current implementation supports, where the structural gaps are, the accommodation options, the edge cases the next mission must handle, and the flow-test shape that should drive it.

---

## Phase B — what was scoped, what's still pending

Per `docs/development/layered-doctrine-resolution-design.md` "Mission structure", Mission B was four WPs. **None has landed yet.** The work done so far is Mission A (org-doctrine-layer) plus the wp-prompt-governance-payload remediation; both stayed on the infrastructure side.

| WP | Scope | Status |
|---|---|---|
| B-WP01 | Shipped mission-type governance profiles (`software-dev`, `documentation`, `research`, `plan`) as `*.profile.yaml` so governance varies by mission_type | Not started |
| B-WP02 | Mission-type resolution in `charter context`: key off `meta.json mission_type`; no `software-dev-default` fallback for non-software missions | Not started |
| B-WP03 | Charter `governance_references`: schema field, context injection, missing-path warning in `charter status` | Not started — note that wp-prompt-governance-payload's `authority_paths` is adjacent but not the same. `authority_paths` names directories the agent may grep; `governance_references` would name specific external docs whose content the resolver injects |
| B-WP04 | Charter write guards: symlinked `charter.md` detection in `charter generate --force`; legacy-path cleanup | Not started |

Mission B's primitives — especially B-WP01–WP02 (mission-type-scoped activation) and B-WP03 (charter-declared external references) — are the structural enablers for Case 1 step 5 and for any "trigger-aware" prompt fetch.

---

## Case 1 — project-layer caveman, support analysis

| Step | Today | What works | What's missing |
|---|---|---|---|
| 1. Author `caveman-comments.styleguide.yaml` | Manual authoring against the schema at `src/doctrine/styleguides/built-in/*.styleguide.yaml` | Schema exists; can be modelled by example | No `spec-kitty doctrine new styleguide <name>` scaffolding; authoring is undiscoverable |
| 2. Plug into spec-kitty | Drop into `.kittify/doctrine/styleguide/` (project layer) OR bundle into a pack | Project-layer drop works (Mission A's three-layer resolver); pack form works (`spec-kitty doctrine pack validate` + `assemble`) | No `spec-kitty doctrine plug <path>` gesture; user must read source docs to learn the destination |
| 3. Charter selects caveman | `DoctrineSelectionConfig` exposes `selected_paradigms`, `selected_directives`, `selected_tactics`, `available_tools`, `template_set` only | Paradigms/directives/tactics can be selected by ID | **Hard blocker.** No `selected_styleguides` field exists — and no per-artifact selection for toolguides, procedures, agent_profiles, mission_step_contracts either. The user cannot declare a styleguide as charter-active. Only workaround: author a wrapper directive whose prose cites the styleguide |
| 4. Charter API loads caveman | `DoctrineService.styleguides.get("caveman-comments")` returns the model | ✓ Mission A wired styleguides into the three-layer resolver | The charter context resolver renders only directives and tactics into the prompt (`_render_profile_directives`, `_render_profile_tactics` in `src/charter/context.py`). Styleguides are accessible programmatically but absent from the rendered governance payload |
| 5. Prompt has "when writing code comment, load caveman" | wp-prompt-governance-payload added fetch+when-doing rules ONLY as token-budget overflow substitution | The fetch-stanza machinery exists (`src/charter/context_renderers/fetch_stanza.py`) | **Hard blocker.** No concept of a *task-conditional* fetch. Current fetch stanzas are emitted only when a section exceeds the token budget, not based on what the agent is about to do |

**Net for Case 1:** today you can get partial coverage by (a) authoring a wrapper directive that says "use caveman style for all code comments" and selecting it in the charter, then (b) relying on the implementer reading the directive body to learn about the styleguide. The direct path — select the styleguide, get a conditional fetch in the prompt — is not supported.

---

## Case 2 — org-layer caveman, support analysis

Same as Case 1 plus org-pack composition:

| Step | Today | Status |
|---|---|---|
| 1–2. Author + pack | Same as Case 1 | Same as Case 1 |
| 3. `org-charter.yaml` declares caveman | Schema is `OrgCharterPolicy` with `interview_defaults`, `required_directives`, `governance_policies` | **Partial blocker.** `required_directives` exists; `required_styleguides` / `required_toolguides` / etc. do not. Same wrapper-directive workaround |
| 4. Team configures pack | `.kittify/config.yaml` `doctrine.org.packs` | ✓ supported (Mission A) |
| 5. Same as Case 1 steps 4–5 | | Same gaps as Case 1 |

**Net for Case 2:** the org plumbing works (the wp-prompt-governance-payload `apply_org_charter_to_interview` runs, pack registry resolves, three-layer merge works). The styleguide-selection gap is identical to Case 1. The org dimension does not add new structural gaps — it inherits the project-level gaps and additionally inherits the org-pack distribution layer's correct behaviour.

---

## Two activation modes — global vs context-scoped

Both modes need first-class support:

- **Global selection**: the charter declares an artifact is always active — *"this project always uses the python-conventions styleguide"*, *"this project always uses the maven-review-checks toolguide"*. Surfaces in every WP prompt regardless of action or mission type.
- **Context-scoped selection**: the charter declares an artifact is active only for a specific context — *"when writing code comments, use caveman styleguide"*. Surfaces in a prompt only when the context matches.

The two modes drive different schema additions:

| Mode | Schema | Resolver behaviour |
|---|---|---|
| Global | `selected_styleguides: [<id>, ...]` (list of artifact IDs, no context) | Render inline in every governance payload |
| Context-scoped | A registry tuple `(activation_context, doctrine_pack_id, artifact_id)` — activation_context is `(mission_type, action)` or `generic` | Render as ID + fetch-command + when-doing rule scoped to the context |

Both are necessary. Global is the simpler 80% case (Case 1 example: *"all code comments in caveman"* is global if every comment in the project must be caveman); the context-scoped registry is the powerful but more involved cousin for *"during `implement`, when you do X, fetch Y"* rules.

---

## Accommodation options

In dependency order. Items 1–3 are the minimum-viable set for global selection (Case 1/2 happy paths); item 4 unlocks context-scoped selection; items 5–7 are quality-of-life.

1. **Extend selection schemas with per-artifact fields (global mode).** Add `selected_styleguides`, `selected_toolguides`, `selected_procedures`, `selected_agent_profiles`, `selected_mission_step_contracts` to `DoctrineSelectionConfig` (Pydantic, additive). Mirror in `OrgCharterPolicy` as `required_styleguides` / etc. `charter sync` extracts them from the charter body; `apply_org_charter_to_interview` unions them into the project selection.
2. **Extend the charter context resolver to render selected artifacts (global mode).** Add `_render_selected_styleguides` (and analogues) alongside the existing `_render_profile_directives` / `_render_profile_tactics`. They emit ID + body (inline) or fetch+when-doing (overflow), reusing the existing mechanism. Output is unconditional — every governance payload carries every globally-selected artifact.
3. **Wire the org-charter union (global mode).** `apply_org_charter_to_interview` unions `required_styleguides` / `required_toolguides` / etc. into the project selection just as it already does for `required_directives`. Non-destructive — existing project selections are preserved.
4. **Activation registry on the charter (context-scoped mode).** Introduce a charter-level registry of `(activation_context, doctrine_pack_id, artifact_id)` tuples. The schema lives on the charter (not on the artifact), so charters from different projects can activate the same shared artifact in different contexts without forking it. Resolver fetches matching entries during context resolution and emits the appropriate fetch+when-doing stanza in the prompt. Without this, *"when writing code comments, use caveman"* (Case 1 step 5) cannot be expressed.
5. **Mission B's mission-type profiles (B-WP01–WP02).** Caveman might apply to `software-dev` but not `documentation`. Without mission-type scoping, even a context-scoped registry leaks across mission types when its `activation_context` is `(any, write_comment)`. With mission-type scoping, `(software-dev, write_comment)` is the precise key.
6. **`spec-kitty doctrine new <kind> <name>` scaffolding command.** Lowers the authoring barrier so step 1 doesn't require reading source code.
7. **`spec-kitty doctrine validate <project_or_pack_path>` standalone command.** The pack-validator surface already exists; expose it for project-layer too so users can verify their styleguide before relying on it.

---

## Edge cases the next mission must pin with tests

1. **ID collision.** Caveman styleguide shares ID with a built-in. Mission A's `DoctrineLayerCollisionWarning` fires. Verify the warning text names the styleguide explicitly and that `spec-kitty doctor doctrine` lists it under Collisions.
2. **Charter selects styleguide that doesn't exist** (typo). Governance resolver must hard-fail with the exact unknown ID, matching `_validate_paradigm_selection` / `_resolve_directives_selection` behaviour. Today's resolver doesn't know about styleguides → would silently no-op.
3. **Org pack declares `required_styleguides: [caveman]` but project hasn't configured the pack.** Today's `apply_org_charter_to_interview` handles `required_directives` only; `required_styleguides` would be silently dropped. Pin the union semantic for the new field.
4. **Pack-N declares caveman, pack-N+1 declares a conflicting caveman.** Per Mission A's declaration-order rule, last wins. Verify the loser is logged (not silently shadowed) — the same `DoctrineLayerCollisionWarning` should fire for org→org collisions, which it does today.
5. **Mission-type mismatch.** Caveman only valid for `software-dev`, mission is `documentation`. With Mission B's mission-type profiles, the resolver should skip caveman for documentation missions. Without Mission B, caveman bleeds into every mission type — wrong but currently the only behaviour.
6. **Trigger registry mismatch.** Artifact declares trigger `write_comment` but no agent action emits that event. The prompt would never include the fetch stanza. Need an architectural test asserting every declared trigger has a corresponding emitter, or downgrade to advisory.
7. **Trigger registry overlap.** Two styleguides both trigger on `write_comment`. Conflict resolution policy needed — concatenate both, or first-declared wins, or escalate to operator.
8. **Token budget overflow when many selected artifacts.** The existing token-budget mechanism would substitute fetches, but the per-trigger fetch stanzas would also need to participate in substitution. Today's policy doesn't differentiate; needs verification under load.
9. **Caveman in `org-charter.yaml` but consumer project lacks the pack on disk.** `doctrine fetch` should pull it (Mission A). If it's not pulled and resolution runs, the styleguide is missing. Pin a clear error message rather than silent fallback.
10. **Author the artifact, plug it in, charter unchanged.** Should be a no-op — the styleguide is available via `DoctrineService` but the charter never selects it. Verify nothing accidentally activates it (no autoselect-by-presence anti-pattern).

---

## Flow tests for the next mission to consume

Four test files, sized as ATDD spec:

```
tests/integration/test_user_doctrine_artifact_lifecycle.py
    test_case_1_project_styleguide_appears_in_implement_prompt
    test_case_1_styleguide_via_charter_directive_wrapper_works_today  # the workaround
    test_case_1_selected_styleguides_field_round_trips             # new schema field
    test_case_1_styleguide_render_includes_trigger_stanza          # new trigger registry

tests/integration/test_org_pack_artifact_lifecycle.py
    test_case_2_org_pack_styleguide_appears_in_consumer_prompt
    test_case_2_required_styleguides_in_org_charter_pre_fills
    test_case_2_org_styleguide_collision_with_builtin_warns
    test_case_2_consumer_without_fetched_pack_fails_loudly

tests/architectural/test_artifact_selection_completeness.py
    # AST test: every doctrine artifact kind must be addressable via
    # `selected_<kind>` in DoctrineSelectionConfig. Today's set is
    # {paradigms, directives, tactics}; the rule asserts parity with
    # the 8 artifact repositories DoctrineService exposes.

tests/architectural/test_trigger_registry_coverage.py
    # AST test: every `triggers:` value in shipped artifacts must
    # appear in a registered emitter (no dead triggers). Counterpart
    # to the prompt-payload contract.
```

The first two are the user-journey acceptance tests; they fail today on the structural gaps and pass once the resolver extensions land. They are the ATDD spec.

The last two are convention / architectural guards that prevent regression once the feature lands — same shape as the marker-presence and marker-correctness guards established this session.

---

## Recommended mission shape

If you want both cases working end-to-end:

1. **First** — write the four integration / architectural tests above as failing-first ATDD spec.
2. **Second (global selection)** — implement schema extensions (`selected_<kind>` × 5 missing kinds; `required_<kind>` for org-charter) and resolver extensions (`_render_selected_<kind>` × 5). At this point Case 1 / Case 2 "all code comments in caveman" works end-to-end as a global activation.
3. **Third (context-scoped selection)** — introduce the activation registry on the charter (`(activation_context, doctrine_pack_id, artifact_id)` tuples), extend the resolver to fetch matching entries per call, and have the prompt renderer emit the fetch+when-doing stanzas. At this point *"when writing comments, use caveman"* (Case 1 step 5) works.
4. **Fourth (long pole, separate mission)** — Mission B's mission-type profiles (B-WP01–WP02), so the `activation_context` key carries mission_type cleanly.

Items 1–3 split naturally into two focused missions: a "global selection" mission (items 1–2) and a "context-scoped activation" mission (item 3). Item 4 is its own mission. The three together get you from *"the user authors caveman; the agent never sees it"* to *"the user authors caveman; the right agent in the right mission gets the right conditional fetch in its prompt"*.

---

## Dependencies on architectural cleanup

The selection-as-charter-API approach assumes one architectural property the codebase does not yet enforce: **the runtime must reach doctrine artifacts only through the charter proxy**. Today there are direct `from doctrine.*` imports inside `src/specify_cli/` runtime modules; those bypass the charter's selection logic and would defeat any per-context activation registry the next mission introduces.

The boundary audit + remediation plan for this is captured in [`runtime-charter-doctrine-boundary.md`](runtime-charter-doctrine-boundary.md). The selection mission described above should not start until at least the boundary contract is pinned by an architectural test (even if the actual import migration is staged), otherwise new direct calls will accrete while the selection plumbing is being built.

---

## What this pre-flight does NOT propose

- It does not propose schema syntax for `triggers:` — the right shape depends on whether triggers live on the artifact (then they apply universally to anyone who selects that artifact) or on the profile (then they are profile-specific). Both are defensible; pick during planning.
- It does not propose how to **prevent autoselect-by-presence** — leaving a styleguide YAML in `.kittify/doctrine/` and expecting it to be active without charter selection is an anti-pattern, but reasonable people could argue for it as a convenience. The selection-via-charter contract makes this an explicit choice.
- It does not propose a UI for `spec-kitty doctrine plug` — typer command shape, interactive prompts, idempotency, etc. are mission-planning concerns, not pre-flight ones.
- It does not propose what happens when a charter selects an artifact from a pack that has not been fetched. Hard error vs warn-and-continue is a policy call — the trade-off is sketched in edge case 9 above but not decided.
