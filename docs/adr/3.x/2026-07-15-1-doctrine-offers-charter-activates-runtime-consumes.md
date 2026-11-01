---
title: 'ADR: Doctrine Offers, Charter Activates, Runtime Consumes Only Activated (default-charter provisioning)'
description: 'Doctrine packs stay pure catalogues, charter activation becomes one mechanism covering mission types, gates and assets, and the loop consumes only activated artefacts.'
status: Proposed
date: '2026-07-15'
doc_status: active
kind: ADR
updated: '2026-07-15T00:00:00Z'
---

## Context and Problem Statement

[ADR 2026-07-14-2](2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md)
(shipped as #883 slice 1) made the doctrine `MissionType` artefact load-bearing
for **governance** through one charter-mediated seam. This ADR states the
**general governing rule** that seam is an instance of, and closes the places it
is not yet true.

The operator-stated mechanism (binding):

1. **Doctrine (packs) OFFER** a catalogue — mission types, step contracts, gates,
   and (when supported) explicit checks / `assets`. Doctrine only offers; it does
   not decide what is active.
2. **A charter ACTIVATES** doctrine elements. The charter may be user-level or
   predefined from a higher tier (org / project / team). Activation is the **same
   mechanism for every artefact kind**.
3. **The runtime execution loop consumes ONLY activated elements.** It holds no
   hardcoded per-type knowledge; unactivated doctrine is invisible to the loop.
4. **Prompt and WP templates are PART OF a mission type** — configuration
   elements carried by doctrine, not core parts of the Spec Kitty engine.
5. **"What is active by default?" must be revised.** Pinning the default to "all
   built-in doctrine" is no longer viable. There must be a **default charter**,
   provisioned when the customer/user has not created one.

A three-lens grounding pass (architecture, availability-split-brain, doctrine
mechanism) on `design/mission-type-activation-coherence` (post-#883) found that
the rule **holds for the eight DRG-backed artifact kinds but breaks for mission
types and templates**, and that "active by default" is a fail-open code constant.

### Grounded status of the five claims

| # | Claim | Status | Root evidence (file:line) |
|---|-------|--------|---------------------------|
| 1 | Doctrine OFFERS | **Holds for 8 kinds; asymmetric** | DRG node census of `src/doctrine/graph.yaml`: `mission_type`, `mission_step_contract`, `gate`, `asset` have **0 nodes**. Only the 8 kinds are truly offer→activate→consume through the graph. |
| 2 | Charter ACTIVATES uniformly | **Holds** | One `YAML_KEY_MAP` (`pack_manager.py:120-122`, mission-type first-class), one plan/commit engine (`activation_engine.py:194-282`), one consume-side filter (`drg.py:256-343`). Two narrow special-cases: cascade is a no-op for mission-type (no DRG node → `activate.py:88-90,319-321`); one warning branch (`activate.py:134`). |
| 3 | Runtime consumes ONLY activated | **Breaks** | `_dn_bootstrap` (`runtime_bridge.py:1199`) → `get_or_start_run` (`runtime_bridge_io.py:469`) → `_runtime_template_key` (`io.py:322-360`) resolve `mission.yaml`/templates by **filesystem discovery tiers with no activation consultation**. The activated `action_sequence` is only an advisory routing predicate and **degrades on exception** (`runtime_bridge_composition.py:180-195,316-327`). An unactivated type whose `mission.yaml` is on disk is fully runnable. |
| 4 | Templates are config | **Partial (~80%)** | `template_set` fields exist on all four `mission_types/*.yaml`; templates are DRG nodes (16) and pack-carried. But the `ResolvedMissionType.template_set` slot is **unwired** (`mission_type_profiles.py:470` hardcodes `None`), and the mission_type→template link is an unbacked filename string because mission_type is not a DRG node. |
| 5 | Default charter | **Breaks at init; fail-open** | Absent config → `_load_config` returns `{}` (`pack_context.py:230-231`) → hardcoded `_BUILTIN_*` constants activate **everything** (`pack_context.py:253-271`). A real default charter ships (`src/charter/packs/default.yaml` + `load_default_pack_activation_ids` + `merge_defaults` `pack_manager.py:703`), but **`init` never provisions it** and **no read-time fallback consumes it** — it reaches config only via a version-guarded migration. The default is **triple-sourced** (constants, `default.yaml`, `merge_defaults`). |

### The two disconnected availability authorities

Availability of mission types is answered by **two parallel authorities**:

- **Activation authority (intended):** `PackContext.activated_mission_types` →
  `existing_mission_types()` (`mission_type_profiles.py:362-398`, self-declared
  FR-018 single source) → `resolve_mission_type_context`, and the DRG filter
  `filter_graph_by_activation`.
- **Filesystem-glob authority (activation-blind):** `list_available_missions`
  (`mission.py:489-509`), `discover_missions` (`mission.py:806-842`),
  `_packaged_missions_dir` (`mission.py:70`), and the runtime discovery in
  `runtime_bridge_io.py:302-360` / `_internal_runtime/discovery.py:139-176`.

On top of this, the **identity of the four built-ins is hardcoded in ~9
independent lists, two of which have already drifted**
(`runtime/show_origin.py:72` is missing `plan`; migration `m_0_6_7:29` lists only
two). And there are **two physical mission trees** (`src/specify_cli/missions/`
v0-schema copies vs `src/doctrine/missions/`), reachable from either side because
`get_package_asset_root` (`kernel/paths.py:88-95`) lists both as candidates.

## Decision

**Adopt the operator's rule as binding, and make it true end-to-end by structural
change rather than assertion.**

1. **Doctrine packs stay pure catalogues** — no activation state (already true;
   preserved by the C-001 layer ratchet).
2. **Activation is one mechanism for every kind.** Extend it to `mission_type`,
   `mission_step_contract`, `gate`, and `asset` by giving them **first-class DRG
   nodes**, so their availability runs through `filter_graph_by_activation` like
   every other kind. This also fixes the cascade no-op for mission-type.
3. **The runtime loop resolves mission-type context, action-sequence, AND
   template/DAG selection through the activation-gated `resolve_mission_type_context`
   seam.** The `_runtime_template_key` / `get_or_start_run` filesystem path is
   **subordinated to (gated by)** the activation set, not run in parallel to it.
   Deactivation must make a type unrunnable, not merely governance-silent.
4. **Prompt/WP templates become activation-scoped mission-type config.** Wire the
   `ResolvedMissionType.template_set` slot to select template files; retire the
   parallel discovery-tier template resolution and the `software-dev-default`
   template magic. Templates are configuration carried by the mission type, not
   engine-baked knowledge.
5. **Retire "active by default = all built-in doctrine" as a code constant.** The
   shipped `src/charter/packs/default.yaml` becomes the **single default-activation
   authority**:
   - **(a) Read-time fallback:** `PackContext.from_config` resolves an absent
     activation key from `load_default_pack_activation_ids()` (data, not the
     `_BUILTIN_*` constants).
   - **(b) Provision at init:** `spec-kitty init` writes the explicit activation
     set from `default.yaml` via `merge_defaults`, so a fresh project's config is
     self-describing and auditable.
   - **(c) Layer-0 tier:** `default.yaml` is the lowest charter tier; org /
     project / team charters overlay it through the existing `pack_roots` overlay
     (`DoctrineLayerCollisionWarning`, [ADR 2026-05-16-1](2026-05-16-1-doctrine-layer-merge-semantics.md)).
   - Delete `_BUILTIN_MISSION_TYPE_IDS` / `_BUILTIN_ARTIFACT_KINDS` as a *fallback
     source* (keep only as a derived or drift-checked cross-reference).

### Fail policy (made explicit)

- **Absent activation key** → resolve the default charter pack. The pack's
  content is permissive today (it enumerates all built-ins), but availability is
  now **data, versioned, and layerable** — an org can ship a restrictive default.
  The permissiveness is a property of the pack's content, not hardcoded behaviour.
- **Explicit empty list** → fail-closed `frozenset()`; never re-expand to the
  default (otherwise deactivation is meaningless). Honoured today at
  `pack_context.py:268-271` — preserved.
- **Absent config file** → resolve the default charter pack (backward-compat for
  legacy / newly-`init`ed projects).
- **Corrupt/malformed config** → hard error. The existing fail-closed contract
  (`pack_context.py:223-241`, "activation filters must not fail open") is preserved.

## Decision Drivers

- **Backward compatibility** — legacy projects with no activation keys must keep
  working (default-pack fallback preserves this; the upgrade migration already
  materialises the same keys).
- **Fail-closed, not fail-open** — the default-pack fallback is a narrow exception
  scoped to *absent key / absent file*, never to *corrupt config* or *explicit
  deactivation*.
- **Single source of truth** — collapse the triple-sourced default and the ~9
  hardcoded built-in lists onto the doctrine registry + `default.yaml`.
- **Deactivation must bite** — the rule is worthless if the ungated runtime path
  still runs a deactivated type (Claim 3).
- **Hot-path budget (NFR-001, 100ms)** — cache the default-pack load; keep
  `template_set` resolution lazy like `expected_artifacts` / `step_contracts`.

## Consequences

**Positive:** one availability authority; deactivation actually removes a type
from the runtime; templates become uniform activation-scoped config; the default
becomes explicit, versioned, and overridable per org/project; the ~9 drift-prone
hardcoded lists collapse to the registry.

**Negative / cost:** modelling `mission_type` / `step_contract` / `gate` / `asset`
as DRG nodes is non-trivial (gates are currently engine-baked condition strings,
assets have no offer surface); gating the runtime template path touches the hot
`next` loop and must not regress NFR-001; the work spans several dependent slices
(below) and cannot land atomically.

## Implementation slices (sequenced by dependency)

- **S0 — mission_type (+ mission_step_contract) as first-class DRG nodes.**
  Unblocks cascade and graph-based gating for S3/S4. *(Belongs with #2651/#2652.)*
- **S1 — `init` provisions the default charter** via `merge_defaults`. Smallest;
  independent of #2652; ships first. *(New default-charter issue.)*
- **S2 — collapse the read-time fallback** onto `default.yaml` via
  `load_default_pack_activation_ids`; delete the `_BUILTIN_*` default source;
  reconcile the kind-count (8 vs 10) into the existing triple-guard. *(Same issue.)*
- **S3 — gate `_runtime_template_key` / `get_or_start_run`** through the activation
  seam so the runtime consumes only activated types. *(After #2652 canonicalises
  enumeration; closes Claim 3.)*
- **S4 — wire the `template_set` slot** so templates are activation-scoped config;
  retire the discovery-tier template path. *(After S3; closes Claim 4.)*
- **Later / separate epics** — gates-as-DRG-artefacts; an assets offer surface.
  Both are net-new artefact modelling, out of scope for the #2651/#2652 chain.

### Guards to land with the work

- **G1** — single availability seam (`existing_mission_types()`); architectural
  test forbids a filesystem glob answering "available" outside it.
- **G2** — the built-in ID list is **derived** from `MissionTypeRepository.default()`;
  a drift test catches the `show_origin.py:72` / `m_0_6_7` divergence.
- **G3** — the default charter is one artefact; the "key absent → all" branches are
  deleted; a test asserts an empty repo resolves exactly the default-pack set.
- **G4** — retire the `src/specify_cli/missions/` type-dir dark copy; collapse
  `get_package_asset_root` to the doctrine tree only. *(This is #2652.)*
- **G5** — move the `runtime_bridge_io.py:347-350` `software-dev` tier special-case
  into `MissionType.template_set` config.
- **G6** — extend the kind-count triple-guard to include `packs/default.yaml`.

## Related

- [ADR 2026-07-14-2 — Doctrine → Charter → Core Mission-Type Resolution Unification](2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md) (#883 slice 1)
- [ADR 2026-05-16-1 — Doctrine Layer Merge Semantics](2026-05-16-1-doctrine-layer-merge-semantics.md)
- Issues: #883, #461, #901, #2651, #2652, and the new default-charter provisioning issue (S1/S2).
