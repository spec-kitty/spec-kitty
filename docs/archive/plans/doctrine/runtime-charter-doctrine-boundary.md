---
title: Runtime → Charter → Doctrine — boundary audit and recommendations
description: Architect Alphonso's audit (2026-05-17) of the runtime to charter to doctrine boundary, with recommendations for tightening the seams.
doc_status: deprecated
updated: '2026-05-19'
related:
- docs/archive/plans/doctrine/doctrine-artifact-selection-preflight.md
---
# Runtime → Charter → Doctrine — boundary audit and recommendations

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Author:** Architect Alphonso
**Date:** 2026-05-17
**Status:** investigation + recommendations. Does NOT propose implementation; outputs are: import audit, classification, ratchet recommendation, and a draft architectural test that pins the boundary going forward.

**Related:** [`doctrine-artifact-selection-preflight.md`](doctrine-artifact-selection-preflight.md) — the user-journey investigation that depends on this boundary being enforced before the selection mission begins.

---

## The intent

The user has stated the layering target:

> **runtime → charter → doctrine**
>
> No direct calls from the runtime to doctrine are allowed; they must pass through the charter proxy. Doctrine acts as a knowledge-retrieval store. Multiple doctrine packs may be added. The charter holds a registry of (doctrine-pack + element) tuples for contexts (mission_type + action, or generic) and defines which agent profiles are accessible — same as before: it combines multiple packs and exposes a subset, resolved through the charter, based on activation context.

This is a tightening of the existing ADR `2026-03-27-1` layer rule:

| Rule | Status today |
|---|---|
| kernel imports nothing | enforced (pytestarch, 8 tests passing) |
| doctrine imports only kernel | enforced |
| charter imports doctrine + kernel (no specify_cli except `specify_cli.runtime`) | enforced |
| **specify_cli (runtime) may import doctrine directly** | currently allowed — **must change** |

The current ADR permits the runtime to call doctrine. The new direction reserves doctrine access to the charter and requires the runtime to go through it. That is the only architectural change required by Cases 1 and 2 of the pre-flight; everything else is additive on top.

---

## Today's surface — audit results

Counted via `rg "^from doctrine|^import doctrine"` against `src/specify_cli/`.

**22 direct imports across 10 files**, in 656 total `.py` files. Manageable scope.

`src/specify_cli/doctrine/` (the pack-management subpackage authored in mission A and extended here) imports zero from `doctrine.*` — it consumes only charter-exposed and locally-owned types. That subpackage is correctly inside the boundary.

### Imports grouped by purpose

| Group | Caller | Imports | Should migrate to |
|---|---|---|---|
| **Agent profiles** | `invocation/registry.py` | `AgentProfile`, `AgentProfileRepository` | `charter.profiles.*` (new facade) |
| | `invocation/router.py` | `DEFAULT_ROLE_CAPABILITIES`, `Role` | Same |
| **Mission step contracts** | `mission_loader/registry.py` | `MissionStepContract`, `MissionStepContractRepository` | `charter.mission_steps.*` (new facade — charter already template-resolves these via `template_resolver.py`) |
| | `mission_loader/contract_synthesis.py` | `MissionStepContract` models | Same |
| | `mission_step_contracts/executor.py` | `MissionStep`, `MissionStepContract`, `MissionStepContractRepository`, `ArtifactKind`, DRG models, DRG query | Same + DRG via charter (below) |
| **DRG (doctrine reference graph)** | `calibration/walker.py` | `DRGEdge`, `DRGGraph`, `DRGNode`, `Relation`, `load_graph`, `merge_layers`, `NodeKind`, `resolve_context` | `charter.drg.*` (new facade — charter already loads DRG via `_drg_helpers.load_validated_graph`) |
| | `glossary/drg_builder.py` | `DRGEdge`, `DRGGraph`, `DRGNode`, `NodeKind`, `Relation` | Same |
| | `mission_step_contracts/executor.py` | `DRGGraph`, `NodeKind`, `ResolvedContext`, `resolve_context` | Same |
| **Primitives** | `missions/__init__.py` | `PrimitiveExecutionContext`, `execute_with_glossary` from `doctrine.missions` | `charter.primitives.*` (new facade) |
| **Resolution types** | `runtime/resolver.py` | `ResolutionResult`, `ResolutionTier` from `doctrine.resolver` | `charter.resolution.*` (charter already wraps this via `template_resolver`) |
| **Shared helpers** | `bulk_edit/occurrence_map.py` | `SchemaUtilities` from `doctrine.shared.schema_utils` | Consider moving `SchemaUtilities` to `kernel` (genuine shared helper) — bypasses the layer question entirely |
| **Versioning** (borderline — charter-cohesive) | `cli/commands/charter.py`, `cli/commands/charter_bundle.py`, `upgrade/migrations/m_3_2_6_charter_bundle_v2.py` | `check_bundle_compatibility`, `get_bundle_schema_version` from `doctrine.versioning` | These are charter-bundle versioning helpers consumed by charter CLI surfaces. Re-export from `charter.versioning` (a thin pass-through) so the runtime sees a charter surface |

### Charter's existing doctrine surface (the proxy as it stands today)

For reference, `src/charter/` has 20 doctrine imports — these are the legitimate proxy surface. They already cover most of the territory the runtime needs:

- Agent profiles (`charter.context` imports `doctrine.agent_profiles`)
- DRG loading + validation (`charter._drg_helpers`, `charter.synthesizer.*`, `charter.reference_resolver`)
- Template / mission resolution (`charter.template_resolver` imports `doctrine.missions.repository`, `doctrine.resolver`)
- Versioning (`charter.extractor` imports `doctrine.versioning`)
- Shared scoping helpers (`charter.catalog`, `charter.language_scope` import `doctrine.shared.scoping`)
- SPDD reasons (`charter.context` imports `doctrine.spdd_reasons`)

The charter is *almost* already the proxy. The runtime's 22 direct imports largely duplicate access paths the charter already has internally; the migration is a re-routing exercise more than a build-from-scratch exercise.

---

## Recommended approach — three phases, smallest viable scope per phase

### Phase 1 — Pin the boundary contract with an architectural test (no source migration)

Land an architectural test that **asserts the boundary** and **captures the current 22 violations as a baseline allowlist**. Future PRs that add new `specify_cli → doctrine` imports outside the allowlist fail loud. The allowlist shrinks over time as phases 2–3 land.

This is the cheapest first step (≈ 100 lines of test code, zero source change) and it stops the drift while the larger work is being planned.

Draft sketch:

```python
# tests/architectural/test_runtime_charter_doctrine_boundary.py
"""Runtime (`src/specify_cli/`) must reach doctrine artifacts via the charter
proxy. Direct `from doctrine.*` / `import doctrine` is reserved for the
charter layer and for `src/specify_cli/doctrine/` (the pack-management
subpackage explicitly designed as the doctrine-management surface)."""

_ALLOWLIST_BASELINE: set[str] = frozenset({
    "src/specify_cli/bulk_edit/occurrence_map.py",
    "src/specify_cli/calibration/walker.py",
    "src/specify_cli/cli/commands/charter.py",
    "src/specify_cli/cli/commands/charter_bundle.py",
    "src/specify_cli/glossary/drg_builder.py",
    "src/specify_cli/invocation/registry.py",
    "src/specify_cli/invocation/router.py",
    "src/specify_cli/mission_loader/contract_synthesis.py",
    "src/specify_cli/mission_loader/registry.py",
    "src/specify_cli/mission_step_contracts/executor.py",
    "src/specify_cli/missions/__init__.py",
    "src/specify_cli/runtime/resolver.py",
    "src/specify_cli/upgrade/migrations/m_3_2_6_charter_bundle_v2.py",
})
```

The test walks AST per file under `src/specify_cli/`, flags every direct `from doctrine.*` / `import doctrine`, exempts the `src/specify_cli/doctrine/` subpackage, exempts allowlisted files, fails on any new entry. As phases 2–3 land and migrate callers, the allowlist shrinks (the failure message tells the maintainer to remove the entry when they migrate).

### Phase 2 — Build charter facades for the migration targets

Add the following surfaces to the charter layer:

1. `charter.profiles.resolve(...)` — proxies `doctrine.agent_profiles.AgentProfileRepository` lookups; takes an activation context (mission_type, action) and returns the resolved profile + its accessible doctrine artifact set per the charter's selection.
2. `charter.mission_steps.resolve(...)` — proxies `doctrine.mission_step_contracts.repository.MissionStepContractRepository`; the charter already template-resolves mission steps in `charter.template_resolver`, so this is a thin re-export.
3. `charter.drg.load_for(...)` — proxies `doctrine.drg.loader.load_graph` + `merge_layers` per context; charter already does this in `_drg_helpers.load_validated_graph` — make it public.
4. `charter.primitives.execute(...)` — proxies `doctrine.missions.execute_with_glossary`.
5. `charter.resolution.{ResolutionResult, ResolutionTier}` — re-export the types from `doctrine.resolver` so callers can keep their type annotations.
6. `charter.versioning.{check_bundle_compatibility, get_bundle_schema_version}` — thin pass-through to `doctrine.versioning`.

Each facade is a 5–10 line module. They do not move code; they re-export. The doctrine implementations stay where they are.

### Phase 3 — Migrate the 10 runtime files

One-file-per-PR (or one consolidated PR, depending on how much you want to land at once). Each PR:

- Replaces `from doctrine.<x> import Y` with `from charter.<facade> import Y` in the runtime caller
- Removes the file from the allowlist in the architectural test
- Runs the relevant integration / contract / architectural tests

Estimated effort: 10 PRs × small mechanical change each, or a single 1-day sweep. The mechanical-substitution side is small; the careful side is reviewing whether any caller was depending on a now-non-public detail of the doctrine subpackage. Charter's surface only re-exports the public symbols, so callers depending on internals would need refactoring.

The `SchemaUtilities` case at `bulk_edit/occurrence_map.py` deserves its own decision: move it to `kernel` (where it likely belongs anyway, given it's a generic helper) instead of routing through charter.

The migration of `versioning` to a charter facade is borderline — the three callers (`cli/commands/charter.py`, `cli/commands/charter_bundle.py`, the migration) are themselves charter-CLI surfaces, so importing the doctrine versioning module directly is arguably fine. Document the decision either way.

### Estimated total effort

- Phase 1: 0.5 day (test + baseline + commit). Stops the drift immediately.
- Phase 2: 1 day (write the facades; they're mostly re-exports).
- Phase 3: 1 day (migrate the 10 files).

About 2.5 days of focused work to fully enforce `runtime → charter → doctrine`. Phase 1 alone is the must-have.

---

## What this audit does NOT cover

- It does not propose where the activation registry (the `(activation_context, doctrine_pack_id, artifact_id)` tuple registry from the pre-flight) lives in the charter — that's a selection-mission concern.
- It does not propose how the charter facade methods should be named or what their argument shapes should look like — that's design work for phase 2.
- It does not audit `tests/` for direct doctrine imports — tests legitimately reach into doctrine to construct fixtures; that's a separate scope.
- It does not audit the agent CLI command surface (`spec-kitty agent <verb>`) for doctrine bypasses — agent commands are themselves runtime; if they import doctrine directly they'd show up in this audit. They don't.

---

## Recommendation in one paragraph

The runtime → charter → doctrine boundary is desirable, it matches the user's stated intent, and the current state is *close enough* that enforcing it is a 2–3 day project rather than a 2–3 month one. **Land Phase 1 (the architectural test with the 13-entry baseline allowlist) before starting the doctrine-artifact-selection mission described in the pre-flight.** That single move (a) pins the boundary so the selection mission doesn't accrete new direct imports while it's being built, and (b) makes the remaining migration a ratcheting exercise rather than a one-shot sweep. Phases 2–3 can land before, alongside, or after the selection mission — they're independent so long as Phase 1 prevents regression.

---

## Appendix — raw import inventory (snapshot 2026-05-17)

```
src/specify_cli/bulk_edit/occurrence_map.py        -> doctrine.shared.schema_utils
src/specify_cli/calibration/walker.py              -> doctrine.drg, doctrine.drg.models, doctrine.drg.query
src/specify_cli/cli/commands/charter.py            -> doctrine.versioning
src/specify_cli/cli/commands/charter_bundle.py     -> doctrine.versioning
src/specify_cli/glossary/drg_builder.py            -> doctrine.drg.models
src/specify_cli/invocation/registry.py             -> doctrine.agent_profiles.{profile,repository}
src/specify_cli/invocation/router.py               -> doctrine.agent_profiles.{capabilities,profile}
src/specify_cli/mission_loader/contract_synthesis.py -> doctrine.mission_step_contracts.models
src/specify_cli/mission_loader/registry.py         -> doctrine.mission_step_contracts.{models,repository}
src/specify_cli/mission_step_contracts/executor.py -> doctrine.artifact_kinds, doctrine.drg.{models,query},
                                                       doctrine.mission_step_contracts.{models,repository}
src/specify_cli/missions/__init__.py               -> doctrine.missions
src/specify_cli/runtime/resolver.py                -> doctrine.resolver
src/specify_cli/upgrade/migrations/m_3_2_6_charter_bundle_v2.py -> doctrine.versioning
```

22 imports, 10 files. Snapshot for the architectural test's baseline allowlist.
