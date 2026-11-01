---
title: Mission B (proposed scope) — Charter-mediated doctrine selection
description: "Architect Alphonso's proposed scope (2026-05-17) for Mission B: charter-mediated doctrine selection, framing the problem and candidate boundaries."
doc_status: deprecated
updated: '2026-05-19'
related:
- docs/archive/plans/doctrine/doctrine-artifact-selection-preflight.md
- docs/archive/plans/doctrine/runtime-charter-doctrine-boundary.md
---
# Mission B (proposed scope) — Charter-mediated doctrine selection

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Author:** Architect Alphonso
**Date:** 2026-05-17
**Status:** proposed scope. Does NOT propose implementation. Input for `/spec-kitty.specify` when the HiC decides to start the mission.

**Predecessors:**
- [`doctrine-artifact-selection-preflight.md`](doctrine-artifact-selection-preflight.md) — the user-journey investigation
- [`runtime-charter-doctrine-boundary.md`](runtime-charter-doctrine-boundary.md) — the layered access audit + remediation plan
- `docs/development/layered-doctrine-resolution-design.md` — the original Mission A + Mission B blueprint
- `kitty-specs/layered-doctrine-org-layer-01KRNPEE/` — Mission A
- `kitty-specs/wp-prompt-governance-payload-01KRR8HS/` — interim mission addressing the empirical gap found post-Mission A

**What "Mission B" means here:** the user's intent for the next governance mission is broader than the original blueprint's Mission B. This document folds three workstreams into a single mission proposal — the original Mission B's mission-type profiles, the pre-flight's selection schema work, and the audit's boundary enforcement — because they share contracts and would otherwise have to land in lock-step anyway. The proposal can be split if the HiC prefers smaller deliveries; the dependency graph is sketched at the end.

---

## Purpose

Make the charter the single authority that decides which doctrine artifacts apply, in which contexts, for any given mission run. Doctrine becomes a pure knowledge store; the runtime asks the charter what to load; the charter resolves selections against doctrine packs and returns the activated set. This delivers the two user journeys captured in the pre-flight (a user authors a styleguide; the right agent in the right mission gets the right rule in its prompt) and closes the layered-access gap noted in the boundary audit.

Concrete operator outcomes:

- A user can declare in their project charter: *"this project uses the python-conventions styleguide globally and the caveman-comments styleguide when writing code comments"* — and the implementer agent's prompt reflects both during every WP.
- An organisation can declare the same in `org-charter.yaml` and team members inherit the declaration with no per-project setup.
- A documentation mission and a software-dev mission running on the same project receive different governance even when the charter declares the same artifacts — because the artifacts are scoped per mission_type.
- `spec-kitty doctor doctrine` reports which artifacts are active, where they were resolved from, and which ones were silenced by collisions.
- No production module under `src/specify_cli/` imports `from doctrine.*` directly — all access flows through `from charter.*` facades.

---

## Proposed WP breakdown (7 WPs)

Dependency order. Each WP has explicit ATDD candidates from the pre-flight's flow-test plan; satisfying them is the acceptance gate.

### WP01 — Boundary enforcement (architectural gate, no source migration)

**Owner profile:** python-pedro
**Depends on:** none
**Deliverable:** `tests/architectural/test_runtime_charter_doctrine_boundary.py` — an AST walk over `src/specify_cli/` that fails on any `from doctrine.*` import outside an explicit baseline allowlist and outside `src/specify_cli/doctrine/` (the pack-management subpackage). Baseline captures the 13 files identified in the boundary audit.
**ATDD:** the test itself is the spec — it must pass against the current source, and a single new direct import in any non-allowlisted file must make it fail with the file name + fix recipe.
**Non-goal:** no migration of the 13 existing direct imports happens here. WP02+ does that incrementally; WP01 is the ratchet.

### WP02 — Charter facade modules (re-exports + thin wrappers)

**Owner profile:** python-pedro
**Depends on:** WP01
**Deliverable:** six new charter-layer modules that re-export the doctrine surfaces the runtime currently consumes directly:

- `src/charter/profiles.py` — proxies `AgentProfile`, `AgentProfileRepository`, `Role`, `DEFAULT_ROLE_CAPABILITIES`
- `src/charter/mission_steps.py` — proxies `MissionStepContract`, `MissionStep`, `MissionStepContractRepository`
- `src/charter/drg.py` — proxies `DRGEdge`, `DRGGraph`, `DRGNode`, `Relation`, `NodeKind`, `load_graph`, `merge_layers`, `resolve_context`, `ResolvedContext` (publishes what `charter._drg_helpers` already wraps internally)
- `src/charter/primitives.py` — proxies `PrimitiveExecutionContext`, `execute_with_glossary`
- `src/charter/resolution.py` — proxies `ResolutionResult`, `ResolutionTier`
- `src/charter/versioning.py` — proxies `check_bundle_compatibility`, `get_bundle_schema_version`

**ATDD:** existing layer-rule tests continue to pass (8/8); a new test asserts each new module exists and re-exports the named symbols.
**Non-goal:** these are not new abstractions. They are re-exports with optional thin wrapping. The "real" facades that take an activation context and return charter-resolved sets land in WP04.

### WP03 — Runtime migration to charter facades

**Owner profile:** python-pedro
**Depends on:** WP02
**Deliverable:** 10 runtime files migrated from `from doctrine.X import Y` to `from charter.X import Y`; baseline allowlist in `test_runtime_charter_doctrine_boundary.py` shrinks to zero (or to a documented short-list of exceptions, e.g. the bundle-versioning callers if HiC accepts them as legitimately charter-CLI).
**Special case:** `doctrine.shared.schema_utils.SchemaUtilities` consumed by `bulk_edit/occurrence_map.py` — propose moving to `kernel` (where it likely belongs) rather than routing through charter.
**ATDD:** every migrated file's tests continue to pass; allowlist count drops to a documented final value.

### WP04 — Per-artifact selection (global mode)

**Owner profile:** python-pedro
**Depends on:** WP03 (clean boundary so selections route correctly)
**Deliverable:** extend `DoctrineSelectionConfig` (Pydantic) with `selected_styleguides`, `selected_toolguides`, `selected_procedures`, `selected_agent_profiles`, `selected_mission_step_contracts`. Mirror in `OrgCharterPolicy` as `required_styleguides` / etc. Extend `charter sync` extractor to pick them up from charter.md / org-charter.yaml. Extend `apply_org_charter_to_interview` to union the new `required_<kind>` fields. Extend the charter context resolver with `_render_selected_<kind>` × 5 alongside the existing `_render_profile_directives` / `_render_profile_tactics`.
**ATDD candidates (from pre-flight):**
- `tests/integration/test_user_doctrine_artifact_lifecycle.py::test_case_1_project_styleguide_appears_in_implement_prompt`
- `tests/integration/test_user_doctrine_artifact_lifecycle.py::test_case_1_selected_styleguides_field_round_trips`
- `tests/integration/test_org_pack_artifact_lifecycle.py::test_case_2_org_pack_styleguide_appears_in_consumer_prompt`
- `tests/integration/test_org_pack_artifact_lifecycle.py::test_case_2_required_styleguides_in_org_charter_pre_fills`
- `tests/architectural/test_artifact_selection_completeness.py` — every artifact kind exposed by `DoctrineService` is also addressable via `selected_<kind>`

**At the end of WP04**, Case 1 / Case 2 "all code comments in caveman" works as a global activation. The agent gets the styleguide body (or fetch+when-doing stanza on overflow) in every WP prompt.

### WP05 — Activation registry (context-scoped mode)

**Owner profile:** python-pedro
**Depends on:** WP04
**Deliverable:** introduce a charter-level activation registry — schema is a list of `(activation_context, doctrine_pack_id, artifact_id)` tuples, where `activation_context` is `(mission_type, action)` or the special token `generic`. The registry lives at the charter level (not on the artifact itself) so charters from different projects can activate the same shared artifact in different contexts without forking it. The resolver fetches matching entries during context resolution and the prompt renderer emits the appropriate `when you <action> in a <mission_type> mission, fetch <artifact-id>` stanza.

`org-charter.yaml` gains the same registry (`activations:`) so org-defined context-scoped activations propagate to consumer projects.

**ATDD candidates:**
- `tests/integration/test_user_doctrine_artifact_lifecycle.py::test_case_1_styleguide_render_includes_trigger_stanza`
- A new `tests/architectural/test_activation_registry_schema.py` pinning the tuple shape and the `(mission_type, action)` vocabulary

**At the end of WP05**, Case 1 step 5 — *"when writing a code comment, fetch caveman"* — works for software-dev missions. (Mission-type scoping per-se lands in WP06; without WP06 the only `mission_type` token usable is `any` / `generic`.)

### WP06 — Mission-type governance profiles (original Mission B WP01–WP02)

**Owner profile:** python-pedro
**Depends on:** WP05 (the activation registry is the consumer)
**Deliverable:** shipped `*.profile.yaml` per mission type (software-dev, documentation, research, plan) under `src/doctrine/missions/<type>/governance-profile.yaml`. Each profile declares default selections and default activations for that mission type. The charter resolver reads `meta.json mission_type`, picks the matching profile, and unions its declarations into the project + org selections.

No `software-dev-default` fallback for non-software missions — the resolver hard-fails if a mission's `mission_type` has no matching profile and the project hasn't declared its own.

**ATDD candidates:**
- New `tests/missions/test_mission_type_profile_resolution.py` — assert each shipped profile loads, resolver picks the right one based on meta.json, and `mission_type=documentation` does NOT get `software-dev-default` content
- Update existing prompt-governance ATDD to cover the documentation-mission case

### WP07 — Operator UX + observability

**Owner profile:** python-pedro
**Depends on:** WP04 (must have selection schema to scaffold against)
**Deliverable:**
- `spec-kitty doctrine new <kind> <name>` scaffolding command — produces a stub `<name>.<kind>.yaml` in the right location for the active project or pack.
- `spec-kitty doctrine validate <path>` standalone command for project-layer validation (today only `pack validate` exists).
- Extend `spec-kitty doctor doctrine` Collisions section to include selection-level reporting: for each active selection (global + activation registry) name the resolved pack and the resolved artifact ID, so operators can audit "which caveman is in effect".

**ATDD candidates:**
- CLI integration tests for both new commands (`spec-kitty doctrine new` writes a valid YAML the validator accepts; `spec-kitty doctrine validate` exits 0 on a valid file and non-zero on an invalid one)
- Snapshot test on `doctor doctrine` output covering a project with a global + a context-scoped activation

---

## Pre-conditions before specifying the mission

These are not WPs in the mission itself; they are the writing the spec depends on.

1. **Decide whether to fold all 7 WPs into a single mission or split.** Recommended split if HiC prefers tighter delivery:
   - **Mission B1 — Boundary + Global Selection** (WP01, WP02, WP03, WP04, WP07 partial — the `validate` command but not `new`)
   - **Mission B2 — Context-Scoped + Mission-Type** (WP05, WP06, WP07's `new` command)
2. **Decide on the `activation_context` vocabulary.** Mission_type values: `software-dev`, `documentation`, `research`, `plan` (already canonical). Action values: TBD — should match the verbs the prompt builder knows about (`specify`, `plan`, `tasks`, `implement`, `review`, `merge`, `accept`, plus charter verbs). A short table in the spec.
3. **Decide on collision-resolution policy when two activations target the same context.** First-declared wins? Concatenate? Operator override? Recommend documenting both possible policies in the spec and picking one in plan review.
4. **Decide on what happens to the original Mission B's WP03 (`governance_references`) and WP04 (charter write guards).** The pre-flight does not require either. WP03 (`governance_references`) overlaps with the wp-prompt-governance-payload mission's `authority_paths` — likely defer to a separate maintenance mission. WP04 (write guards) is independent and can stay deferred until charter-rewrite tooling lands.

---

## Acceptance criteria (mission-level)

The mission is accepted when:

1. **Boundary enforced:** `test_runtime_charter_doctrine_boundary.py` passes against the production source with a maximum of 2 documented exceptions in the allowlist (charter-bundle versioning callers, if HiC accepts them as charter-CLI surfaces). All 8 layer-rule tests stay green.
2. **Global selection works end-to-end** for both Case 1 (project-layer styleguide) and Case 2 (org-pack styleguide). The four ATDD test files from the pre-flight pass.
3. **Context-scoped activation works** for the `(mission_type, action)` axis with at least one shipped example (e.g. *"when writing code comments in a software-dev mission, fetch the python-conventions styleguide"*).
4. **Mission-type profiles ship** for software-dev, documentation, research, plan. `mission_type=documentation` produces a prompt with documentation-specific governance and NO `software-dev-default` content.
5. **Operator surfaces:** `spec-kitty doctrine new <kind> <name>`, `spec-kitty doctrine validate <path>`, and `spec-kitty doctor doctrine` with the extended Collisions section all work and have test coverage.
6. **No regression** in: ATDD suite `tests/specify_cli/next/test_wp_prompt_governance_contract.py` (23/23); architectural tests (`test_layer_rules`, `test_pytest_marker_convention`, `test_pytest_marker_correctness`, plus the new boundary test); contract tests (237/0).

---

## Non-goals

- **Not adding new doctrine artifact kinds.** The mission extends what's *selectable*, not what *exists*. New kinds are a separate concern.
- **Not changing the doctrine-pack format.** Mission A's pack contract stands.
- **Not rewriting `charter sync`.** The extractor learns to read additional fields; its overall shape is unchanged.
- **Not addressing the user-customisation-preservation concerns from the project charter.** Mission B's deliverables are additive and do not mutate user-authored files.
- **Not building a UI for the activation registry.** The registry is declared in `charter.md` / `org-charter.yaml`; UI is out of scope.
- **Not adding the original Mission B WP04 (charter write guards).** Defer to a separate maintenance mission unless the HiC bundles it here.

---

## Estimated effort

- Mission B (single mission, all 7 WPs): roughly 8–12 developer-days plus review cycles. ATDD discipline means most of the time is in WP04–WP06; WP01–WP03 are mostly mechanical.
- Mission B1 + Mission B2 split: roughly 5–7 days for B1, then 4–6 days for B2 after B1 stabilises.

---

## What this proposed scope does NOT cover

- It does not write the spec — that's the job of `/spec-kitty.specify <mission name>` once the HiC has decided to start.
- It does not decide between the single-mission and split-mission approach.
- It does not pre-resolve the open questions listed in "Pre-conditions" — those are deliberately HiC-facing for plan-time decisions.
- It does not propose the activation-registry YAML syntax in detail. The spec's Domain Language table should pin it during specify-phase.
