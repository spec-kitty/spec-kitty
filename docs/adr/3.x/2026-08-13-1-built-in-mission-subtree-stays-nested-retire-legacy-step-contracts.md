---
title: 'ADR: The built-in mission subtree stays nested and self-contained; retire the legacy step-contract surface'
description: 'Keeps the nested per-type packs/built-in/missions/ bundle canonical (no flattening) and retires built_in_step_contracts in favour of the unified MissionStep model.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-13'
related:
- architecture/mission-type-resolution
- architecture/doctrine-kinds
- adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion
- adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention
---
# The built-in mission subtree stays nested and self-contained; retire the legacy step-contract surface

**Filename:** `2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md`

**Status:** Accepted

**Date:** 2026-08-13

**Deciders:** Operator (ATDD)

**Technical Story:** Discharges the nested-vs-flat mission-type layout decision that
[ADR 2026-08-05-1](2026-08-05-1-mission-type-availability-before-kind-promotion.md) (§"a
short decision record of its own") explicitly reserved. Completes the FR-011 unified-step
migration begun in mission `charter-doctrine-mission-type-configuration-01KSWJVX`.

---

## Context and Problem Statement

`packs/built-in/missions/` is a **nested subtree**, unlike the flat `<plural>/` content
dirs the other doctrine kinds use. It holds, per grounding research
(`work/doctrine-pack-restructure-research/01-current-structure-and-loaders.md`):

- `mission_types/*.yaml` — the mission-type **identity registry** (`id` + `display_name`).
- `mission-steps/<type>/<step>/{step.yaml,prompt.md,guidelines.md}` — the **unified
  `MissionStep`** model (FR-011), the canonical per-step authority.
- `built_in_step_contracts/*.step-contract.yaml` — the **legacy `MissionStepContract`**
  shape, explicitly "retained as a compatibility surface … until later WPs migrate those
  callers to the unified model" (`src/doctrine/missions/step_contracts.py:1-17`).
- Per-type **self-contained bundles** `<type>/` — `mission.yaml` (state machine),
  `actions/<action>/index.yaml` (delegation map), `templates/`, `mission-runtime.yaml`,
  `expected-artifacts.yaml`, `governance-profile.yaml`.

A restructure was proposed to **flatten** the subtree into two top-level dirs
(`packs/built-in/mission-types/` + `packs/built-in/step-contracts/`, deprecating
`missions/`) so built-in would look like a "normal" pack. Grounding showed this flatten
is expensive and fights existing invariants: it does not account for the unified
`mission-steps/` surface or the per-type runtime bundles (the two-dir target names neither);
it would red the Accepted layout gate in
[ADR 2026-07-26-2](2026-07-26-2-doctrine-artefact-pack-layout-convention.md) that pins step-contracts
at `missions/built_in_step_contracts/`; it collides with kernel-floor path constants; and it
pulls built-in toward a DRG layout that still conflicts with the org-pack `drg/fragment.yaml`
convention (so "one canonical structure" would not actually be achieved). Meanwhile the
nested per-type organisation is already clean: each mission type is a self-contained
directory that offers its own identity, steps, state machine, actions, templates, and
governance.

Two things are therefore in tension and need a recorded decision: **(1)** whether to flatten,
and **(2)** what to do about the two coexisting step surfaces (`built_in_step_contracts/`
legacy vs `mission-steps/` unified), which are a live drift hazard.

## Decision Drivers

- **Single canonical authority** — two step surfaces (`MissionStepContract` vs `MissionStep`)
  for "a mission's steps" violate it and must collapse to one.
- **Self-containment / legibility** — a per-mission-type directory that carries everything
  that type needs is easier to reason about, override, and extend than a flat collapse.
- **Do not break Accepted ADRs or kernel-floor invariants without cause.**
- **Avoid speculative convergence** — matching the org-pack shape is only worthwhile if it is
  actually reached; a half-flatten that still differs from org packs buys nothing.

## Considered Options

- **Option A — Flatten** to top-level `mission-types/` + `step-contracts/`, deprecate
  `missions/`.
- **Option B — Keep the nested subtree canonical; retire the legacy step-contract surface**
  so the remaining structure is unambiguous.
- **Option C — Keep everything as-is**, including both step surfaces (status quo).

## Decision Outcome

**Chosen option: "Option B".** The nested `packs/built-in/missions/` subtree is the canonical
built-in mission layout. It is **not** flattened. The legacy step-contract surface is
**retired in its entirety**.

### Canonical structure (fixed by this ADR)

```
packs/built-in/missions/
├── mission_types/<type>.yaml                     # identity registry (id + display_name)
├── mission-steps/<type>/<step>/                  # UNIFIED MissionStep (sole step authority)
│   ├── step.yaml
│   ├── prompt.md
│   └── guidelines.md
└── <type>/                                        # self-contained per-type bundle
    ├── mission.yaml                               # state machine
    ├── mission-runtime.yaml                       # runtime DAG
    ├── expected-artifacts.yaml                    # dossier manifest
    ├── governance-profile.yaml                    # type-grain governance
    ├── actions/<action>/index.yaml                # action-grain delegation map
    └── templates/                                 # content scaffolds
```

Each mission type is a **self-contained directory**; two flat registries (`mission_types/`,
`mission-steps/`) index identity and steps across types. This is the intended shape and
should not be flattened toward the org-pack `<plural>/` + `drg/fragment.yaml` convention.
Built-in remaining structurally distinct from org packs is **accepted and intentional** — it
is the positionally-anchored base layer, not a registered path-resolved pack.

### The legacy step-contract surface is removed

`built_in_step_contracts/` (the on-disk `*.step-contract.yaml` files, 17 today), the
`MissionStepContract` / `MissionStepContractStep` models and repository/loader
(`src/doctrine/missions/step_contracts.py`), the `src/specify_cli/mission_step_contracts/`
package, the `mission_step_contract` `ArtifactKind` and its DRG fragment
(`packs/built-in/mission_step_contract.graph.yaml`, 34 nodes), and every remaining caller of
that surface are migrated onto the unified `MissionStep` model and then deleted. This
completes FR-011.

### Consequences

#### Positive

- One step model (`MissionStep`), one step surface (`mission-steps/`) — the drift hazard is
  gone.
- The per-type bundle stays legible and self-contained; overrides and new mission types have
  an obvious home.
- No churn against the kernel-floor `missions` leaf, the missions-root authority, or the
  ~23 `default_missions_root()` consumers (nothing moves).

#### Negative

- Removing the legacy surface is a **large, cross-cutting migration** (~45 src files + ~40
  test files reference it; the runtime contract registry, contract synthesis, and review
  gate bindings must move to `MissionStep` first). It is breaking and must land behind the
  unified model being feature-complete for gates.
- Deleting the `mission_step_contract` DRG fragment changes the built-in graph identity
  (node/edge cardinality drops by 34 nodes); the parity fixture/golden must be re-baselined
  in the same change, not silently.

#### Neutral

- Built-in stays asymmetric to org packs by design; the separate pack-meta / README /
  built-in-validator work (see the pack-restructure research) is orthogonal and unaffected.

### Confirmation

Enforced, not aspirational: after migration, no `src/` symbol imports
`MissionStepContract*` and no `*.step-contract.yaml` remains under `packs/built-in/`
(architectural guard); the unified `MissionStep` resolver carries the gate semantics the
contracts previously held (behavioural test); the built-in DRG parity fixture is
re-baselined to the post-removal cardinality; `spec-kitty doctor doctrine --json` reports
healthy.

## More Information

- Grounding research: `work/doctrine-pack-restructure-research/` (`01`–`05`, `99-SYNTHESIS.md`).
- Supersedes point 5 of [ADR 2026-07-26-2](2026-07-26-2-doctrine-artefact-pack-layout-convention.md)
  (which pins step-contracts at `missions/built_in_step_contracts/`) — that path is removed.
- Does not contradict [ADR 2026-05-16-1](2026-05-16-1-doctrine-layer-merge-semantics.md)
  (merge semantics) or the shared-package-boundary ADR (packaging).
