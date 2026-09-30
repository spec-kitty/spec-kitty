---
title: Implementation Mapping (living)
description: 'Living implementation mapping (C4 level 4): where each architecture concept lives in the source tree today. A derived view of the enforced module map.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/00_landscape/README.md
- docs/architecture/04_implementation_mapping/code-patterns.md
- docs/architecture/05_ownership_map.md
---
# Implementation Mapping (living)

| Field | Value |
|---|---|
| Status | Living (derived view; the enforced pair wins on conflict) |
| Date | 2026-03-04 |
| Last Updated | 2026-09-30 |
| Scope | Maps C4 architecture views and doctrine stack to current codebase |
| Parent | [System Landscape](../00_landscape/README.md) |
| Related ADRs | `2026-03-25-1-glossary-type-ownership` |

## Purpose

Bridge the gap between the architecture documentation (C4 levels 0–3) and the
actual codebase. This document answers: "Where does each architectural concept
live in the source tree today?"

This is **not** a code inventory — it maps domain responsibilities to modules,
explains the doctrine stack layer model, and identifies where the current
implementation aligns with or diverges from the target architecture.

> **Current package boundaries** — Package inventory is defined by
> [`pyproject.toml`](../../../pyproject.toml) `[tool.hatch.build.targets.wheel].packages`,
> enforced by [`test_pyproject_shape.py`](../../../tests/architectural/test_pyproject_shape.py).
> Import direction is defined and enforced by the `landscape` fixture in
> [`conftest.py`](../../../tests/architectural/conftest.py) and
> [`test_layer_rules.py`](../../../tests/architectural/test_layer_rules.py).
> This implementation mapping is a derived view of those sources.
> [05_ownership_map.md](../05_ownership_map.md) is historical narrative only;
> its former slice assignments and extraction roadmap are not authoritative for
> current package ownership or boundaries.

---

## Level 0 — System Landscape → Codebase Modules

The landscape's domain containers all exist in the current codebase as Python
modules within a single-process CLI application. The main ones map as follows.

| Landscape Container | Primary Codebase Location | Package | Notes |
|---|---|---|---|
| **Control Plane** | `src/specify_cli/cli/` | `specify_cli` | Typer-based CLI. Single user entry point for all commands. |
| **Kitty-core** | `src/specify_cli/core/`, `mission.py`, `mission_v1/`, `missions/`, `template/`, `runtime/` | `specify_cli` | Planning pipeline (specify→plan→tasks). The next-action loop itself lives at `src/runtime/next/_internal_runtime/` (`specify_cli/next` is gone). |
| **Event Store** | `src/specify_cli/status/` | `specify_cli` | JSONL event logs (`store.py`), reducer (`reducer.py`), WP frontmatter, `meta.json`. Filesystem-only today. |
| **Orchestration** | `src/specify_cli/orchestrator_api/`, `consolidation/`, `post_merge/`, `lanes/`, `workspace/`, `tracker/` | `specify_cli` | Lifecycle engine, worktree management, lane consolidation, tracker projection. (The former local `sync/` transport was retired in the convergence; tracker projection now flows from `status/emit.py`.) |
| **Dashboard** | `src/specify_cli/dashboard/` | `specify_cli` | Playwright-based local browser kanban. Read-only against Event Store. |
| **Agent Tool Connectors** | `packs/built-in/missions/mission-steps/*/*/prompt.md` (source) → deployed as `.claude/`, `.codex/`, `.amazonq/`, etc. | `charter` (offering source), `specify_cli` (deployment) | Current connector is a rendered markdown prompt template. One "adapter" per agent. Source templates live under `packs/built-in/missions/`; doctrine code lives at `src/charter/offering/`. |
| **Skills Installer** | `src/specify_cli/skills/` | `specify_cli` | Deployment bridge introduced in mission 055. `SkillRegistry` discovers canonical skills from `src/charter/offering/skills/`; `ManagedSkillManifest` tracks installed files by hash for drift detection; `installer.py` and `verifier.py` deploy skills into agent directories alongside command templates during `spec-kitty init`. |
| **Doctrine** | doctrine code at `src/charter/offering/` (models/repository/validation per kind, `drg/`, `artifact_kinds.py`, `schemas/`) + `src/charter/offering/skills/` (canonical skill packs); pack content at `packs/built-in/` | `charter` (the former standalone `doctrine` package was absorbed here in the convergence) | JSON Schema validation, Pydantic models, repository pattern. Skill packs deployed from `src/charter/offering/skills/`. |
| **Charter** | `src/charter/` | `charter` (standalone package) | Interview flow, compiler, action context resolver with depth semantics and action index intersection. Produces `.kittify/charter/` bundles. Context bootstrap injects governance at every execution boundary. |

### Key structural observation

The governance layer lives in the **`charter` package** (`src/charter/`), which
absorbed the former standalone `doctrine` package at `src/charter/offering/` in
the convergence (`src/doctrine.py` remains only as a deprecation shim). The
documented layer chain is
**`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`**:

- `kernel` — zero-dependency shared primitives; the true root layer
- `charter` — governance/doctrine authority (`charter.offering` holds the
  doctrine code); depends only on `kernel`
- `glossary` — terminology / semantic-integrity pipeline + DRG glossary
  bridge, in `src/glossary/`
- `runtime` — canonical mission control loop, in
  `src/runtime/next/_internal_runtime/`
- `mission_runtime` — artifact-placement seam (`PlacementSeam`, resolver
  port, identity, lifecycle_phase), in `src/mission_runtime/`
- `specify_cli` — control plane, lifecycle, and orchestration; the top adapter
  layer, depends downward on the rest

`kernel`, `charter`, and `glossary` are gate-enforced by `tests/architectural/test_layer_rules.py`
pytestarch `LayerRule`s. `mission_runtime` and `runtime` are gate-enforced by that same suite's
shrink-only outbound-import ledgers (`TestMissionRuntimeBoundary` /
`_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI`, `TestRuntimeSpecifyCliLedger` /
`_RUNTIME_ALLOWED_SPECIFY_CLI`) rather than a clean `LayerRule`, since a strict
"should not access specify_cli" rule would red on existing, working code — new
imports outside the named ledger still red the gate. Only the remaining container boundaries
are module-level conventions enforced by architectural gates and code review.

### Ephemeral status transport (Zeitgeist) and the SaaS client

The convergence retired the local `sync/` transport (daemon, offline queue,
body outbox, transport-attempts) and the `src/specify_cli/saas/` package. Two
live packages carry their surviving responsibilities and were previously
undocumented in this map:

| Package | Role |
|---|---|
| `src/specify_cli/zeitgeist_client/` | The **ephemeral-status successor** to the removed sync transport (transport, subscription, moments, live-frame, outbox-approval, budget, credentials). Mission status is now ephemeral by design and team artifacts render server-side; this client is how the host participates in that ephemeral-status stream. |
| `src/specify_cli/saas_client/` | A **sync-free HTTP client** (`client`, `endpoints`, `auth`, `errors`) for hosted team artifacts. Distinct from the deleted `saas/` readiness/rollout package — readiness re-homed to `tracker/saas_readiness.py` and the SaaS-sync flag to `core/saas_sync_config.py`. |

Both are guarded against silent reintroduction of the retired surfaces by
`tests/architectural/test_no_retired_subsystems.py` and the `pyproject.toml`
TID251 ban block; the surviving `SPEC_KITTY_SYNC_*` / `SPEC_KITTY_*_SAAS_*` env
vars are sanctioned by design.

---

## Level 1 — System Context → Boundary Mapping

| External Actor | Current Boundary Surface | Implementation |
|---|---|---|
| **Human In Charge** | CLI commands, interview prompts | `src/specify_cli/cli/commands/` (Typer command groups) |
| **Human In Charge** (read) | Dashboard kanban | `src/specify_cli/dashboard/server.py` → local browser |
| **Agent Tools** | Command template prompts | `.claude/commands/`, `.codex/prompts/`, etc. (12 agent directories) |
| **External Trackers** | Optional status projection | `src/specify_cli/tracker/` (feature-gated; the local `sync/` transport was retired in the convergence) |
| **Project Repository** | Filesystem read/write | `kitty-specs/`, `.kittify/`, `status.events.jsonl`, WP frontmatter |

### Boundary rule compliance

| Boundary Rule | Current State |
|---|---|
| Host-owned authority is non-negotiable | ✅ All state mutations go through `status/emit.py` — agents cannot bypass |
| Agent Tools are external | ✅ Agents receive rendered prompts; they do not call `specify_cli` directly |
| Dashboard is read-only | ✅ `dashboard/` reads frontmatter/events only; no write path exists |
| Tracker integration is optional | ✅ Tracker modules are feature-gated; system works without them |
| Repository is canonical state | ✅ All persistence is filesystem-based; no external state authority |

---

## Level 2 — Container Collaboration → Code Paths

### Loop A: Planning (User → Kitty-core → Event Store)

```
User runs: spec-kitty specify / plan / tasks
  → src/specify_cli/cli/commands/ (Control Plane)
  → src/specify_cli/core/ + mission.py (Kitty-core; the next-action loop is src/runtime/next/_internal_runtime/)
  → src/specify_cli/status/emit.py (Event Store write)
  → kitty-specs/<mission>/ artifacts written to filesystem
```

### Loop B: Execution Coordination (Orchestration ↔ Event Store → Connectors)

```
User runs: spec-kitty implement WP01
  → src/specify_cli/cli/commands/ (Control Plane)
  → src/specify_cli/lanes/ + workspace/ (Orchestration)
  → src/specify_cli/status/store.py (Event Store read — WP state)
  → packs/built-in/missions/mission-steps/software-dev/implement/prompt.md (Connector)
  → Agent executes work (external)
  → src/specify_cli/status/emit.py (Event Store write — lifecycle event)
```

### Loop C: Governance (User → Charter → Doctrine)

```
User runs: spec-kitty charter interview / generate
  → src/specify_cli/cli/commands/ (Control Plane)
  → src/charter/activation/interview.py (Charter interview)
  → src/charter/activation/compiler.py (Charter compiler)
  → src/charter/activation/reference_resolver.py (transitive DFS: directive → tactic → styleguide/toolguide)
  → src/charter/offering/service.py → per-artifact repositories (Doctrine read)
  → .kittify/charter/ (compiled governance bundle)
```

### Loop C': action context bootstrap (Agent → Charter → Doctrine)

```
Agent calls: spec-kitty charter context --action implement
  → src/charter/activation/context.py (Action Context Resolver)
  → Load action index: packs/built-in/missions/software-dev/actions/implement/index.yaml
  → Two-stage intersection: action index ∩ project selections (references.yaml)
  → src/charter/offering/service.py (DoctrineService) → fetch directive/tactic content by depth
  → Load action guidelines: packs/built-in/missions/mission-steps/software-dev/implement/guidelines.md
  → Render CharterContextResult (governance text injected into agent prompt)
  → Persist context-state.json (first-load tracking for depth semantics)
```

This sub-loop runs at every execution boundary (Principle 5). First invocation
returns depth-2 (full bootstrap); subsequent calls return depth-1 (compact).

### Loop D: Visibility (Dashboard ← Event Store)

```
User runs: spec-kitty dashboard
  → src/specify_cli/dashboard/server.py (starts local server)
  → src/specify_cli/dashboard/scanner.py (reads kitty-specs/ frontmatter)
  → Browser renders kanban (read-only)
```

### Loop E: External Projection (Orchestration → Tracker)

```
Orchestration lifecycle event triggers:
  → src/specify_cli/status/emit.py (status projection seam)
  → src/specify_cli/tracker/ (tracker connector gateway)
  → External tracker API (optional, feature-gated)
```

> The local `sync/` transport that formerly coordinated this projection was
> retired in the convergence; projection now flows directly from the status
> emit seam to the tracker gateway.

---

## Level 3 — Components → Modules

| Component (from C4 Level 3) | Module(s) | Key Files |
|---|---|---|
| **Command Router** | `cli/` | `cli/__init__.py`, command group registration |
| **Workflow Command Set** | `cli/commands/` | `specify.py`, `plan.py`, `tasks.py`, `implement.py`, `review.py`, `merge.py`. Canon terminology: `--mission-type` is the flag for mission-type selection (renamed from `--mission` in 5 type-selection commands, 2026-03-25; old `--mission` alias raises hard error). `--mission` remains the slug selector on all other commands. `--feature` is a hidden deprecated alias everywhere. |
| **Status Mutation Command Set** | `cli/commands/` | `status.py`, lane transition commands |
| **Governance Command Set** | `cli/commands/` | `charter.py` |
| **Next Loop Coordinator** | `src/runtime/next/` | `_internal_runtime/engine.py` + `planner.py` — per-agent action sequencing (the `src/specify_cli/next/` shim was deleted in `93dcbd7548`, 2026-07-03) |
| **Mission Discovery and Resolution** | `core/`, `mission.py`, `mission_v1/` | Mission context detection, asset loading |
| **Runtime Asset Lifecycle Coordinator** | `runtime/` | Bootstrap, tier selection, compatibility |
| **Tiered Template Resolution Pipeline** | `template/` | Prompt/template resolution by configured precedence |
| **Mission Context Detection** | `core/` | Active mission detection |
| **Event Semantics Reducer** | `status/reducer.py` | Deterministic event→snapshot materialization |
| **Persistence Layer** | `status/store.py` | JSONL append/read, corruption detection |
| **Lifecycle Command Gateway** | `status/emit.py` | `emit_status_transition()` — single entry point for state changes |
| **WP Lifecycle Engine** | `status/transitions.py` | 16-pair transition matrix, guard conditions |
| **Target-Line Router** | `mission_runtime/lifecycle_phase.py`, `core/` | Phase resolution, target branch routing |
| **Tracker Connector Gateway** | `tracker/` | External tracker API adapters (the former `sync/` runtime coordinator was retired in the convergence) |
| **Kanban View** | `dashboard/` | `server.py`, `scanner.py`, `templates/`, `static/` |
| **Doctrine Catalog Loader** | `src/charter/offering/service.py` | `DoctrineService` — lazy aggregation facade |
| **Schema Validation Gate** | `src/charter/offering/*/validation.py`, `src/charter/offering/schemas/` | JSON Schema + Pydantic validation |
| **Glossary Hook Coordinator** | `src/charter/offering/missions/glossary_hook.py`, `src/glossary/` | Glossary checks during mission execution |
| **Charter Interview Flow** | `charter/activation/interview.py` | Guided Q&A for governance capture |
| **Charter Compiler** | `charter/activation/compiler.py` | Doctrine→charter bundle compilation |
| **`Action Context Resolver`** | `charter/activation/context.py`, `charter/activation/resolver.py`, `charter/activation/reference_resolver.py` | Action-scoped governance context with depth semantics (1=compact, 2=bootstrap, 3=extended) and two-stage intersection (action index ∩ project selections) |
| **Action Index** | `packs/built-in/missions/*/actions/*/index.yaml` | Per-action directive/tactic/styleguide/toolguide selection — loaded by `src/charter/offering/missions/action_index.py` |
| **Execution Dispatch** | `packs/built-in/missions/mission-steps/<mission_type>/<step_id>/prompt.md` | Prompt rendering for agent dispatch (source relocated from `specify_cli/missions/` in mission 054; content now ships from `packs/built-in/`, not `src/charter/offering/`) |
| **Agent Adapters** | `.claude/`, `.codex/`, `.amazonq/`, etc. | Per-agent command templates (12 agents) |
| **Path Resolver** | `src/kernel/paths.py` | `get_kittify_home()`, `get_package_asset_root()` — zero-dependency path resolution shared across all packages (moved from `specify_cli.runtime.home` in WP09, 2026-03-25; re-export shim at `specify_cli/runtime/home.py` preserves backward compatibility). **Dependency note (Windows):** `kernel` is stdlib-only on Linux/macOS. On Windows, `platformdirs` is imported lazily in `kernel/paths.py` for platform-appropriate home directory resolution. This is the only sanctioned third-party import in `kernel/`. |
| **Glossary Runner Registry** | `src/kernel/glossary_runner.py` | `GlossaryRunnerProtocol`, `register()`, `get_runner()` — plugin registry allowing `doctrine` to register its runner without creating a `specify_cli` import dependency. Resolves DIV-5 (docs/adr/2.x/2026-03-25-1-glossary-type-ownership.md). |

### Tiered Template Resolution Pipeline

Template resolution uses a 6-tier precedence chain implemented in
`src/specify_cli/runtime/resolver.py`. The resolver checks each tier in order
and returns the first file that exists:

| Tier | Label | Path Pattern | Semantics |
|---|---|---|---|
| 1 | **Project Override** | `.kittify/overrides/{templates,command-templates}/{name}` | Highest precedence. User's explicit project-level override. |
| 2 | **Legacy** (deprecated) | `.kittify/{templates,command-templates}/{name}` | Pre-migration project files. Emits deprecation warning or one-time "run `spec-kitty migrate`" nudge. Will be removed in next major version. |
| 3 | **Org** | `<org_root>/missions/{mission}/{templates,command-templates}/{name}` | Org-provided doctrine pack roots, checked in declaration order. No-op when no org packs are configured. |
| 4 | **Global Mission-Specific** | `~/.kittify/missions/{mission}/{templates,command-templates}/{name}` | User-global, scoped to a specific mission type. Populated by `spec-kitty migrate` / `ensure_runtime`. |
| 5 | **Global Non-Mission** | `~/.kittify/{templates,command-templates}/{name}` | User-global, cross-mission. |
| 6 | **Package Default** | `packs/built-in/missions/{mission}/{templates,command-templates}/{name}` | Lowest precedence. Bundled pack content (resolved through the `charter.offering` chain). Resolved via `kernel.paths.get_package_asset_root()`. |

**Special cases:**
- `resolve_mission()` uses a 5-tier variant — it skips tier 5 (Global Non-Mission) because missions are inherently mission-scoped.
- Tier 2 (Legacy) shows a one-time stderr nudge when the global runtime is already configured.
- If no tier provides the asset, `FileNotFoundError` is raised.

---

## Doctrine Stack: Layer Model

The Doctrine container is organized as a layered knowledge stack. Each layer
serves a distinct governance purpose, and the reference directions between
layers are strictly defined.

### Artifact Type Layers

| Layer | Artifact Type | Location | Count (shipped) | Purpose |
|---|---|---|---|---|
| **Mental Models** | Paradigm | `packs/built-in/paradigms/` (Python at `src/charter/offering/paradigms/`) | 13 | High-level approaches that frame *how you think about a problem*. Not executable. |
| **Rules** | Directive | `packs/built-in/directives/` (Python at `src/charter/offering/directives/`) | 34 | Enforceable governance rules. `enforcement: required\|advisory`. |
| **Procedures** | Tactic | `packs/built-in/tactics/` (Python at `src/charter/offering/tactics/`) | 124 | Step-by-step execution procedures. Agent-consumable. |
| **Output Shapes** | Styleguide | `packs/built-in/styleguides/` (Python at `src/charter/offering/styleguides/`) | 23 | Define *what output looks like* — formatting, naming, structure. |
| **Tool Contracts** | Toolguide | `packs/built-in/toolguides/` (Python at `src/charter/offering/toolguides/`) | 15 | Define *how tools are used* — config, invocation, constraints. |
| **Execution Identity** | Agent Profile | `packs/built-in/agent_profiles/` (Python at `src/charter/offering/agent_profiles/`; no `shipped/` subdirectory) | 25 | Agent capabilities, constraints, collaboration contracts. Injected by `SkillRegistry` at `init` time. |
| **Deployable Governance Packs** | Skill | `src/charter/offering/skills/` | 55 | Self-contained governance bundles (SKILL.md + optional references/scripts/assets) deployed to agent directories during `spec-kitty init` by `specify_cli/skills/`. |
| **Process Templates** | Mission Template | `packs/built-in/missions/` (Python at `src/charter/offering/missions/`) | 4 types (software-dev, documentation, research, plan) | Define the SDD process stages for different mission types. Also carries per-action governance indexes. |
| **Process Templates** | Expected Artifacts Manifest | `packs/built-in/missions/*/expected-artifacts.yaml` | 4 (software-dev, documentation, research, plan) | Per-step, class-tagged (`input`, `output`, `workflow`, `evidence`), blocking-semantics artifact requirements consumed by dossier `ManifestRegistry` via `MissionRepository.get_expected_artifacts()`. |

### Reference Direction Rules

```
Paradigm ──tactic_refs──→ Tactic       (approach justifies tactics)
Directive ──tactic_refs──→ Tactic      (rule selects procedures)
Tactic ──references──→ Tactic          (step consults related procedure)
Tactic ──references──→ Styleguide      (step consults output shape)
Tactic ──references──→ Toolguide       (step consults tool contract)
Tactic ──references──→ Directive       (step references governing rule)
```

Cross-artifact tension/rejection is expressed as first-class DRG edges
(`packs/built-in/*.graph.yaml`), not an inline artifact field — see below.

**Leaf nodes:** Styleguides and Toolguides are terminal — they are referenced
*by* tactics but carry no outward references.

**DAG constraint:** Tactic-to-tactic references must form a directed acyclic
graph. Cycles are detected by `test_tactic_reference_graph_has_no_cycles` in
`tests/doctrine/test_directive_consistency.py`.

**Tension/rejection semantics:** the DRG relations `in_tension_with` (symmetric,
non-transitive — e.g. Directive 024 Locality of Change vs. Directive 025 Boy
Scout Rule), `reconciles_tension` (an active reconciliation artifact bridging
both sides of a tension), and `rejects` (directional, target a marked
`anti_pattern` node) do **not** mean "superseded". All artifacts on either side
of a tension or rejection remain independently valid; the edges document known
tension/rejection so agents and `charter consistency-check` can surface it when
co-activated. These replaced the retired inline contradiction-declaration
field + its shared model (mission doctrine-tension-edges-01KY1WPC).

### Repository Implementation Pattern

Every artifact type follows an identical internal structure, split across a
Python package and a shipped-content directory — the two no longer live
under the same tree:

```
src/charter/offering/<artifact_type>/    # Python package — code only
  ├── __init__.py          # Exports
  ├── models.py            # Pydantic model (e.g., Directive, Tactic, Paradigm)
  ├── repository.py        # Two-source YAML loader (shipped + project)
  └── validation.py        # Schema validation — delegates to SchemaUtilities

packs/built-in/<artifact_type>/          # Shipped content (YAML files)
  ├── 001-xxx.<type>.yaml
  └── ...
```

### Shared Utilities (`src/charter/offering/shared/`)

Cross-cutting infrastructure used by all artifact subpackages:

| Module | Purpose |
|---|---|
| `schema_utils.py` | `SchemaUtilities.load_schema(name)` — single cached schema loader replacing six near-identical per-type functions |
| `exceptions.py` | `DoctrineArtifactLoadError` — fail-open signal for corrupt/unreadable artifact files; `DoctrineResolutionCycleError` — raised when a cycle is detected in the reference graph |

**Why shared utilities matter:** Before `shared/`, each `validation.py` duplicated identical schema-loading logic (importlib.resources lookup + filesystem fallback + LRU cache). The `shared/` module eliminates that duplication and provides a single place to evolve the loading strategy.

**Two-source loading** is the key design pattern:

1. **Shipped artifacts** are bundled as pack content under `packs/built-in/`
   (resolved through the `charter.offering` chain). These are the defaults that
   come with Spec Kitty.
2. **Project artifacts** live in the user's project under the canonical
   `.kittify/charter-packs/` tree (e.g., `.kittify/charter-packs/directives/`);
   the legacy `.kittify/doctrine/` location is still read as a fallback until
   the M3 on-disk data move lands (`src/kernel/doctrine_root.py`,
   `resolve_doctrine_read_root`, CR-07). Project artifacts can override
   shipped artifacts via field-level merge or add entirely new ones. (`.kittify/charter/`
   is a distinct tree — the compiled Charter Bundle output, not the
   project-layer artifact source.)

The `DoctrineService` (`src/charter/offering/service.py`) is the aggregation facade —
it lazily instantiates all per-type repositories and is the single entry point
for all consumers (Charter compiler, Connectors, Kitty-core).

### Schema Validation

Each artifact type has a corresponding JSON Schema file in
`src/charter/offering/schemas/`:

| Schema File | Validates |
|---|---|
| `paradigm.schema.yaml` | Paradigm artifacts (includes `tactic_refs`) |
| `directive.schema.yaml` | Directive artifacts (includes `tactic_refs`) |
| `tactic.schema.yaml` | Tactic artifacts (includes `steps`, `references`) |
| `styleguide.schema.yaml` | Styleguide artifacts |
| `toolguide.schema.yaml` | Toolguide artifacts |
| `agent-profile.schema.yaml` | Agent Profile artifacts (capabilities, constraints) |
| `mission.schema.yaml` | Mission template definition |

Validation is enforced in tests (`tests/doctrine/`) and through the
Schema Validation Gate component. Schemas use `additionalProperties: false`
on paradigm and tactic types, meaning any new field requires both a schema
update and a valid fixture update.

---

## Doctrine Stack: As-Is vs. Vision

### What exists and works today

| Capability | Status | Evidence |
|---|---|---|
| All 7 artifact types with Pydantic models, repositories, validation | ✅ Complete | `src/charter/offering/*/models.py`, `repository.py`, `validation.py` |
| JSON Schema validation for all types | ✅ Complete | `src/charter/offering/schemas/*.schema.yaml` |
| Two-source loading (shipped + project override) | ✅ Complete | `repository.py` field-level merge on each type |
| Cross-artifact references (`tactic_refs`, `references[]`) | ✅ Complete | Wired with test coverage across `tests/doctrine/` (185 test files, 3,017 collected tests as of 2026-09-07 — this figure grows over time, not a ceiling) |
| Tension/rejection modeling (`in_tension_with`/`reconciles_tension`/`rejects` DRG edges) | ✅ Complete | Hand-authored edges in `packs/built-in/*.graph.yaml`; validated via `assert_valid` |
| DAG cycle detection — shipped artifacts | ✅ Complete | `test_tactic_reference_graph_has_no_cycles` in `tests/doctrine/test_directive_consistency.py` |
| Cycle detection at resolution boundary | 🟡 Partial | Moved into the DRG validator: `src/charter/offering/drg/validator.py` rejects `requires` cycles (`_validate_requires_cycles`) and `specializes_from` lineage cycles at load time. The former `reference_resolver._Walker` boundary check is gone, and `DoctrineResolutionCycleError` is defined (`offering/shared/exceptions.py`, covered by `tests/doctrine/shared/test_exceptions.py`) but no longer raised anywhere in `src/`. |
| Shared schema loading (`SchemaUtilities`) | ✅ Complete | `src/charter/offering/shared/schema_utils.py`; replaces 6 duplicated per-type loaders |
| Domain exceptions (`DoctrineArtifactLoadError`, `DoctrineResolutionCycleError`) | ✅ Complete | `src/charter/offering/shared/exceptions.py` |
| `DoctrineService` aggregation facade | ✅ Complete | `src/charter/offering/service.py` |
| Charter compiler consumes Doctrine | ✅ Complete | `src/charter/activation/compiler.py` |
| Command templates as connector implementation | ✅ Complete | 12-agent template system via migrations |
| Transitive reference resolution (directive → tactic → styleguide/toolguide) | ✅ Complete | `src/charter/activation/reference_resolver.py` (mission 054) |
| Action-scoped governance injection with depth semantics | ✅ Complete | `src/charter/activation/context.py` + `packs/built-in/missions/*/actions/*/index.yaml` (mission 054) |
| Per-action guidelines extraction from templates | ✅ Complete | `packs/built-in/missions/mission-steps/*/*/guidelines.md` (mission 054; single owner since #5202) |
| ArtifactKind canonical enum | ✅ Complete | `src/charter/offering/artifact_kinds.py` (mission 054, WP09-WP10) |
| MissionRepository package relocation | ✅ Complete | `packs/built-in/missions/` is the authoritative source for all shipped mission assets (YAML, mission-step prompt templates, content templates, expected-artifacts); `src/charter/offering/missions/` holds only the Python repository/loader code that reads them. `src/specify_cli/missions/` survives only as a stale legacy asset tree the resolver deliberately no longer falls back to (`src/kernel/paths.py`, DR-2); its Python mission code moved to `src/charter/offering/missions/` (`primitives.py`, `glossary_hook.py`). |
| Skills Pack canonical distribution | ✅ Complete | `src/specify_cli/skills/` — `SkillRegistry`, `ManagedSkillManifest`, installer, verifier. 55 canonical skill packs in `src/charter/offering/skills/`. Deployed to agent directories during `spec-kitty init` (mission 055). |
| Agent Profile shaping connector behavior | ✅ Complete | Models, repository, schema, profile-aware resolution wired in `resolver.py`; workflow profile injection at execution boundary enabled (mission 055). |
| `kernel` zero-dependency floor (`paths`, `glossary_runner`, `glossary_types`) | ✅ Complete | `src/kernel/` — `paths.py`, `glossary_runner.py`, `glossary_types.py`. Backward-compat re-export shim at `specify_cli/runtime/home.py`. DIV-5 (glossary runner boundary) resolved. ADR: `2026-03-25-1-glossary-type-ownership`. |
| `--mission-type` flag on type-selection commands | ✅ Complete | 5 commands renamed from `--mission` to `--mission-type` (2026-03-25). Old `--mission` alias on those commands raises `typer.Exit(1)`. `--mission` (slug selector) and `--feature` (hidden deprecated alias) unchanged on all other commands. |

### What is emerging or aspirational

| Capability | Status | Gap Description |
|---|---|---|
| Glossary integration at execution boundary | 🟡 Partial | `glossary_hook.py` exists; full Glossary Hook Coordinator loop is early-stage |
| Slimmed agent templates (governance-free) | 🟡 Partial | Bootstrap section added to templates. Residual inline governance prose not yet stripped. Migration `m_2_0_2` pending. |
| Mission templates as first-class doctrine artifacts | 🟡 Partial | Templates relocated to `packs/built-in/missions/` (mission 054; loader code at `src/charter/offering/missions/`). Action indexes operational. Formal `MissionTemplateRepository` deferred. |
| Explicit per-agent connector adapters | 🟡 Partial | 12-agent command template system is the seed. Architecture envisions SDK/shell/remote adapters (Phase 2). |
| Non-software-dev mission parity | 🟡 Partial | `documentation`, `plan`, `research` missions have action directories but thinner indexes than `software-dev`. |
| Event Store behind interface contract | 🟡 Partial | `store.py`/`reducer.py` provide the interface pattern. Not yet formally abstracted for alternative backends (Phase 3). |
| Control Plane as swappable surface | 🔴 Conceptual | CLI is tightly coupled. No interface abstraction exists yet for TUI/web alternatives |
| Dashboard as independent read surface | 🟡 Partial | Functionally independent. Reads filesystem directly rather than through Event Store interface |

---

## Divergence Notes

Areas where the current implementation does not yet match the target
architecture:

1. **CLI mixes Control Plane and Orchestration:** Some CLI commands directly
   invoke lifecycle mutations rather than routing through a clean Control Plane →
   Orchestration interface. The boundary is module-level convention, not enforced
   by an interface contract.

2. **Kitty-core and Orchestration share filesystem paths:** Both can write
   to `kitty-specs/` directly. The landscape says they should both go through
   the Event Store interface contract.

3. **Connector concept is implicit:** The current "adapter" is a rendered
   markdown template. There is no formal `Connector` interface that alternative
   dispatch mechanisms (SDK, shell, remote API) could implement.

4. **Dashboard reads filesystem directly:** Rather than querying through
   the Event Store interface, `dashboard/scanner.py` reads WP frontmatter files
   directly. This works but bypasses the Event Store abstraction.

These are not bugs — they reflect the natural state of a system evolving toward
its target architecture. The landscape document establishes where the boundaries
*should* be, and the gap between as-is and target architecture guides future
refactoring priorities.

---

## Core Code Patterns

The companion document [code-patterns.md](code-patterns.md) catalogs the
recurring code patterns applied across the codebase: rule-based pipelines
(chain-of-responsibility), append-only event log + reducer, two-source
doctrine repository, preflight validation with structured results, and the
pure-function finding shape. Each entry links to its doctrine tactic and
points at canonical implementations in the tree. Reach for it when picking
up an unfamiliar module — the patterns it documents are the codebase's
expected shapes.

## Traceability

- System Landscape: `../00_landscape/README.md`
- Architectural Principles: `../00_landscape/README.md#architectural-principles`
- System Context (living): [`../diagrams/01_context/README.md`](../diagrams/01_context/README.md)
- Container View (living): [`../diagrams/02_containers/README.md`](../diagrams/02_containers/README.md)
- Component View (living): [`../diagrams/03_components/README.md`](../diagrams/03_components/README.md)
- Frozen 2.x C4 snapshot: `../01_context/`, `../02_containers/`, `../03_components/`
- Code Patterns Catalog: [code-patterns.md](code-patterns.md)
- Doctrine governance ADR: [`docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`](../../adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md)
