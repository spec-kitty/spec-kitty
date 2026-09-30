---
title: 16 — Codebase Reassessment (Debbie/Pedro fan-out)
description: 'Codebase reassessment (Phase 2-3 bridge): six parallel investigators validating the sharpened domain hypotheses against the code, for the runtime and state overhaul.'
doc_status: deprecated
updated: '2026-06-03'
---
# 16 — Codebase Reassessment (Debbie/Pedro fan-out)

**Phase:** 2 → 3 bridge · **Date:** 2026-06-03 · **Method:** 6 parallel investigators (Debugger Debbie
×4 forensic, Python Pedro ×2 structural) validating the dialectic's sharpened hypotheses (`15`) against
real code-paths. This is the **evidence base** for the consolidated model and the `06` mapping.

> **Headline: the code confirms all of the dialectic's refutations, and adds five findings that
> change the `06` concretization.** The structural core (Mission≠MissionRun) is real and contained;
> several "domains" are actually *shared kernels / seams*; and two of the proposed homes in CLAUDE.md
> / earlier notes are **stale or non-existent**.

## Verdict table

| H | Hypothesis | Verdict | One-line |
|---|------------|---------|----------|
| H1 | Context = Shared Kernel / OHS, not Execution subdomain | **CONFIRMED** | CQRS split is by I/O-role, not domain; write-side serves status+governance |
| H2 | Status/kanban is a shared bounded context | **CONFIRMED** | 70 consumers (~24 exec / ~27 plan); the integration **seam** — but boundary leaks |
| H3 | Actor is cross-domain | **CONFIRMED + fragmented** | Only LLM-step-executor is execution-bound; **no single Actor type** (3 vocabularies) |
| H4 | Prompt = governed projection, not DTO | **CONFIRMED** | Published Language; **three** distinct projections exist |
| H5 | MissionRun can't name its Mission | **CONFIRMED** | Snapshot stores type+uuid only; `inputs["mission_slug"]` is write-only dead code |
| H6 | Model maps onto the package graph | **MOSTLY — 3 corrections** | runtime↔specify_cli is bidirectional/unenforced; canonical runtime ≠ where notes say |

## Per-hypothesis evidence

### H1 — Context is a Shared Kernel fronted by two OHS facades

Shared Kernel = `core/paths.py` + `workspace/root_resolver.py` + `mission_metadata.resolve_mission_identity`;
OHS facades = `resolve_action_context` (`core/execution_context.py:220`) + `resolve_mission_read_path`
(`missions/_read_path_resolver.py:94`). Consumed by Governance-read (`doctrine.py:98`, `context.py:263`),
Mission Mgmt (kanban/dashboard/tasks), Acceptance, Merge, Runtime, Sync, Orchestrator. The CQRS split is
real (`get_status_read_root` READ vs `get_main_repo_root`/`canonicalize_feature_dir` WRITE) **but
partitioned by I/O role** — the write-side canonicalizer serves `status/emit.py` + charter writes, *not*
execution; `resolve_action_context` fuses `implement`/`review` with `tasks*`/`accept` in one body
(`execution_context.py:23-32`). **→ Context = Shared Kernel + OHS; Execution is a consumer, never owner.**

### H2 — Status/kanban is a shared context (and the integration seam)

70 consumer files, balanced ~24 execution / ~27 planning, on the same five primitives
(`read_events`, `reduce`, `materialize`, `get_wp_lane`, `Lane`/`StatusEvent`). The `runtime.next` loop
imports *nothing* else from the planning side — **the status event log is literally the contract by
which planning and execution communicate WP state.** **New debt finding:** the 060-cleanup public API
(`status/__init__.py` `__all__`) is bypassed — **~245 deep-submodule imports vs 6 facade imports**, many
reaching non-exported internals (`lifecycle_events`, `locking`, `adapters`, `work_package_lifecycle`,
`emit.build_status_event`). The context is conceptually clean but **operationally porous**; an
import-boundary enforcement test (mirroring `tests/architectural/test_shared_package_boundary.py`) is the action item.

### H3 — Actor is cross-domain *and* fragmented

Human/operator effects change in Governance (`charter/interview.py`, `generator.py`, `activation_engine`
→ `config.yaml`) and Mission Mgmt (`merge.py:160` `_resolve_merge_actor`; **RACI `accountable`-must-be-human
P0 invariant** `runtime/next/_internal_runtime/schema.py:78-85`; HiC gate `retrospective/gate.py:305`).
External systems mutate governance via the tracker ACL (`tracker/config.py:39` `doctrine_mode="external_authoritative"`).
The runtime is itself an actor-kind. **Only the LLM-agent-as-step-executor is execution-bound** (and even
that slot is vacated by the `human-in-charge` sentinel). **New finding:** there is **no unified `Actor`
type** — three vocabularies across packages (`human|llm|service` in runtime/decisions; `human|agent|runtime`
in retrospective; free-form `str` in `status/emit`). Any "Actor domain" claim must name which metamodel.

### H4 — Prompt is a Published Language; there are *three* projections

`_build_wp_prompt` (`prompt_builder.py:142-289`) splices **4 domains** (Mission Mgmt template+WP, Governance
charter+profile directives, Context workspace/branch, Actor identity) into flat text → temp file → returns
only the path. Not a DTO. **The three projections of one governed invocation, previously conflated:**
1. **Executor Prompt** — rendered text (`prompt_builder.py`) → LLM agent. *(Published Language)*
2. **`ActionContext.to_dict()` JSON** (`cli/commands/agent/context.py:111`) → agent-context CLI/shim. *(a real DTO, different consumer)*
3. **`OperationalContext`** (frozen VO, `charter/invocation_context.py:155`) → logged/threaded at the decision boundary, **not passed to the prompt builder**.
**→ Consolidating these three is a design target in its own right.**

### H5 — MissionRun degeneracy (contained fix)

`MissionRunSnapshot` (`schema.py:523-536`) and `MissionRunRef` (`engine.py:92-97`) store `run_id`(uuid) +
`mission_key`(**type**) only — no `mission_id`/`mission_slug`. `start_mission_run` mints `uuid4().hex`
(`engine.py:196`); the only run↔mission link is the external forward index `feature-runs.json`
(slug→run). `inputs["mission_slug"]` is **written but never read** (zero readbacks in `src/`). Fix
blast-radius: 2 schema classes + ~6 in-engine snapshot-copy sites (silent-drop risk) + 2 bridge call
sites + `feature-runs.json` + additive legacy migration — **contained to `runtime/next/`**; the external
`MissionRunStartedPayload` event is out of scope. Separable from #1619.

### H6 — Package-graph corrections (important for `06`)

- **Layer order** (`tests/architectural/test_layer_rules.py`, `conftest.py:33-54`): `kernel ← doctrine ←
  charter ← specify_cli` is the **spine**; **`runtime/` and `glossary/` are siblings at the charter
  level**, not a single chain.
- **`runtime ↔ specify_cli` is bidirectional and unenforced**: `runtime` imports `specify_cli` **56×**;
  the only hard rule forbids `runtime → specify_cli.cli` / `specify_cli.next` (`test_layer_rules.py:200-220`).
  Not a clean downward dependency.
- **Canonical internal runtime = `src/runtime/next/_internal_runtime/`** (engine.py, schema.py, planner.py).
  **`src/specify_cli/next/` is a deprecation shim** (`__deprecated__ = True`, removed in 3.3.0). **The
  CLAUDE.md / earlier-notes reference to `specify_cli/next/_internal_runtime` is STALE** — do not anchor the model there.
- **`MissionStatus` aggregate does not exist** — status is the event-log (`Lane` + `StatusEvent`,
  `status/models.py`). `ActionContext` confirmed at `core/execution_context.py:44`.
- **`mission_runtime/` does not exist** (net-new). A net-new top-level package would **fail the meta-guard**
  `test_no_unregistered_src_packages` until registered in `_DEFINED_LAYERS`.
- Aside: **`dashboard/` is not layer-registered** (would flag the meta-test) — separate follow-up.

## Emergent findings (beyond the original hypotheses)

1. **Status/kanban is a first-class shared context** — surface it explicitly; add import-boundary enforcement (H2). **Filed: [#1664](https://github.com/Priivacy-ai/spec-kitty/issues/1664).**
2. **Actor metamodel is fragmented** across 3 vocabularies — a unification candidate (answers the `12 §7` "shared Actor type?" question) (H3).
3. **Three parallel context projections** (Prompt PL / ActionContext DTO / OperationalContext VO) — consolidation target (H4).
4. **MissionRun→Mission reference gap** — small, contained (H5). **Filed: [#1663](https://github.com/Priivacy-ai/spec-kitty/issues/1663).**
5. **Stale/absent homes**: canonical runtime is `runtime.next` (not `specify_cli.next`); `mission_runtime/`
   and `MissionStatus` are net-new and constrained by the layer meta-guard (H6). **CLAUDE.md stale runtime path: fixed in this branch.**

## Implications for the consolidated model + `06` mapping

- **Confirm**: Mission≠MissionRun; MissionType ∈ Governance(doctrine); the execution spine.
- **Reclassify**: Context → Shared Kernel + OHS; **Status/kanban → its own shared context** (the planning↔execution seam); Actor → cross-domain (+ fragmented); Prompt → Published Language (+ two sibling projections).
- **Re-home**: anchor Execution on `runtime/next/_internal_runtime/`; treat `mission_runtime/` + `MissionStatus` as **net-new** subject to layer registration; respect the bidirectional runtime↔specify_cli reality.
- **Net-new vs existing (for `06`)**: Governance=`charter/`⊕`doctrine/` (exists); Status context=`status/` (exists, needs boundary enforcement); Execution=`runtime/next/_internal_runtime/` (exists); Context=`ActionContext` (exists, to harden); `MissionStatus` aggregate + `mission_runtime/` umbrella (net-new).
