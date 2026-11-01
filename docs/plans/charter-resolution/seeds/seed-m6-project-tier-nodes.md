---
title: Mission Seed M6 - Project-Tier DRG Node Emission
description: 'Specify-intake seed for the mission closing #3038: emit hand-authored project-tier agent_profile artefacts as DRG nodes reachable by cascade.'
doc_status: active
updated: '2026-08-19T00:00:00Z'
kind: Planning
---

# Mission Seed — M6: Project-Tier DRG Node Emission

> **Status:** seed. Feed to `/spec-kitty.specify` in a fresh session.
> **Part of:** charter-resolution program (see `../program-brief.md`).
> **Closes:** #3038 (agent_profile half). **Asset half deferred behind #3037.**
> **Effort:** L. **Depends on:** after M1 — reuses the single-authority discipline. Carve-out (separate axis from recursion).

## Problem

The project doctrine tier admits only 3 kinds (directive/tactic/styleguide) as DRG nodes, so a hand-authored project-tier `agent_profile` (or `asset`) **loads and validates but never becomes a DRG node** — it is invisible to cascade. This is a different axis from the recursion divergence M1 fixes: it is **kind-admission**, not scanning.

**Already landed — do not redo:** the service/repository half (`PROJECT_KIND_DIRS` is now the single total 12-kind authority in `artifact_kinds.py`; `DoctrineService.assets`/`.agent_profiles` read the project tier). Only the **DRG-node-emission** half remains open.

## Fix approach

Emit hand-authored project-tier `agent_profile` artefacts as DRG nodes. The current synthesizer is **answer-driven, not artefact-driven** — so extending the kind→node-kind map alone reproduces the defect. Needs a **filesystem-walk emission path** into the project overlay graph, plus the map extension. Convert `project_drg._KIND_TO_NODE_KIND` from `dict[str, NodeKind]` to `ArtifactKind`-keyed so the totality gate (extended in M1) covers it.

## Open operator decisions (resolve at this mission's discovery)

1. **Node source:** a new filesystem-walk emitter into the project overlay `graph.yaml`, or is project-tier node presence intended to remain synthesis-answer-driven only? (The issue's two-map extension is insufficient either way.)
2. **`procedure` at project tier:** is a project-tier `procedure` supposed to be a DRG node (readable by the loader but not a synthesizer target today)? Deliberate boundary or the same silent gap?
3. **Asset:** confirm the asset half stays deferred behind #3037 (asset has no resolution/install path — wiring it as a node yields a half-wired artefact).

## Scope

- **In:** project-tier `agent_profile` DRG-node emission (filesystem-walk emitter + map extension + enum-keyed map under the gate).
- **Out:** asset node emission (behind #3037); the recursion/load-path work (that is M1).

## Key seams

- `charter/synthesizer/project_drg.py` (`_KIND_TO_NODE_KIND` at ~:45 — str-keyed, escapes the totality gate; `_node_kind_for`)
- `charter/synthesizer/targets.py` (answer-driven target build — the artefact-driven emission gap)
- `doctrine/artifact_kinds.py` (`PROJECT_KIND_DIRS` — already the single authority)

## Note

Cascade only reads project `graph.yaml` / root-level `*.graph.yaml` — so a project-tier node that never reaches `graph.yaml` stays cascade-invisible even after the map extension. The emitter must actually land the node in the graph the cascade walks.
