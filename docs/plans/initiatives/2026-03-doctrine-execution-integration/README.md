---
title: 'Initiative: 2026-03 Doctrine-to-Execution Integration'
description: Initiative capturing the assessment and roadmap for wiring the feature-046 doctrine repository layer into the charter resolver and execution path.
doc_status: deprecated
updated: '2026-09-30'
---
# Initiative: 2026-03 Doctrine-to-Execution Integration

> **Historical (2.x-era initiative, retired 2026-09-30).** Kept as a record; not a live working surface. Its wording (for example "feature" for what is now a Mission) is a legacy snapshot. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

This initiative captures the assessment and roadmap for wiring the doctrine
repository layer (delivered in feature 046) into the charter resolver,
mission template system, and execution dispatch chain.

## Context

Feature 046 delivered typed Pydantic models and repository services for all
6 doctrine artifact types (directives, tactics, paradigms, styleguides,
toolguides, agent profiles). These are loadable on-demand through
`DoctrineService` but are not yet consumed by the execution pipeline.

The current execution flow resolves governance through string-based lookups
in `governance.yaml` and injects charter summaries into agent prompts.
Agents receive directive titles but not the enriched content (procedures,
tactic_refs, scope, validation_criteria) that was added in 046.

## Current Execution Flow (As-Is)

```
CLI (spec-kitty implement WP01)
  |
  v
implement.py: create worktree and context
  |
  v
prompt_builder.py: build_prompt()
  |-- Load mission config (software-dev/mission.yaml)
  |-- Load command template (software-dev/command-templates/implement.md)
  |-- Load charter (build_charter_context)
  |     |-- Parse charter.md (first load only)
  |     |-- Resolve governance (directives as strings, paradigms as strings)
  |     +-- Inject summary + references into prompt
  +-- Assemble final prompt with governance context
  |
  v
Rendered markdown prompt -> Agent (12 adapter formats)
```

**Key gap**: The charter resolver uses `governance.yaml` with string-based
directive/paradigm references. It does not call `DoctrineService` to retrieve
the full typed artifacts with procedures, tactic steps, and cross-references.

## Target Execution Flow (To-Be)

```
CLI (spec-kitty implement WP01)
  |
  v
implement.py: create worktree and context
  |
  v
prompt_builder.py: build_prompt()
  |-- Load mission template (via MissionTemplateRepository)
  |-- Load command template (doctrine artifact, not inline markdown)
  |-- Load charter
  |     |-- Resolve governance via DoctrineService
  |     |-- DoctrineService.directives.get(id) -> full Directive with procedures
  |     |-- Resolve tactic_refs -> full Tactic objects with steps
  |     +-- Inject enriched, actionable governance into prompt
  +-- Assemble prompt with on-demand depth loading
  |
  v
Connector interface contract -> Agent adapter (pluggable)
```

## Implementation Status

| Phase | Status | Feature |
|-------|--------|---------|
| Phase 1: Charter Resolver + Mission Template Extraction | ✅ Complete (2026-03-10) | `054-charter-interview-compiler-and-bootstrap` |
| Phase 2: Connector Interface Contract | Planned | TBD |
| Phase 3: Event Store Interface Abstraction | Deferred | TBD |

---

## Roadmap: Three Phases

### Phase 1: Charter Resolver + Mission Template Extraction (single mission)

**Goal**: Wire `DoctrineService` into the charter resolver and extract
inline mission governance into proper doctrine artifacts.

**Scope** (as implemented in feature 054):

1. Replace string-based directive lookups in `charter/resolver.py` with
   `DoctrineService.directives.get(id)` calls. Inject full directive content
   (intent, procedures, tactic_refs, scope) into agent prompts.

2. Resolve `tactic_refs` transitively: when a directive references tactics,
   load the full `Tactic` objects with steps and inject them as actionable
   procedure guidance.

3. Extract inline governance from `software-dev` command templates
   (`specify.md`, `plan.md`, `implement.md`, `review.md`) into per-action
   doctrine files at `src/doctrine/missions/software-dev/actions/<action>/guidelines.md`.
   Templates reference IDs and retrieve content at runtime via `charter context`.

4. Implement action-scoped iterative deepening in `charter context` via `--depth <1|2|3>`:
   - Retrieval is scoped via two-stage intersection: action index (`actions/<action>/index.yaml`) ∩ project selections (`references.yaml`). Prevents cross-action content bleed.
   - Each artifact type fetched via its own dedicated repository service (`DirectiveRepository`, `TacticRepository`, etc.) — no cross-type fetches.
   - Depth 1 (compact): directive titles + tactic IDs for the action scope
   - Depth 2 (bootstrap): full directive procedures + tactic steps via `DoctrineService` for the action scope
   - Depth 3 (explicit): adds styleguide/toolguide details + per-action mission guidelines

5. Charter treated as configuration layer only — `generate` no longer
   materialises content into `.kittify/charter/library/`. All content
   retrieved live from `DoctrineService` on each `context` call.

6. Deploy slimmed templates to all 48 agent copies via migration `m_2_0_2`.

**Entry point**: `src/specify_cli/charter/context.py`, `src/specify_cli/charter/resolver.py`.

**Note on MissionTemplateRepository**: Creation deferred to a follow-on feature.
The `src/doctrine/missions` package is used directly by `context.py` for
action guidelines in this iteration.

**Prerequisite status**: Curation cycle is ongoing. Feature 054 proceeded against
the current 046 artifacts; full curation alignment was not a hard blocker for
Phase 1 mechanics.

**Completion notes** (2026-03-10): All 12 WPs merged. Remaining deployment item:
migration `m_2_0_2` for slimmed agent templates (tracked separately).
`MissionTemplateRepository` creation deferred to follow-on work. See
`2026-03-054-postmortem/README.md` for full review.

### Phase 2: Connector Interface Contract (separate mission)

**Goal**: Formalize the boundary between Orchestration and Agent Tool
Connectors so external execution engines can be plugged in.

**Scope**:

1. Define a formal `ConnectorProtocol` (Python Protocol) that agent adapters
   must implement. Current 12 markdown template adapters become the reference
   implementation.

2. Abstract prompt dispatch from the current render-to-file approach into a
   contract: `dispatch(wp_context, governance_context) -> ExecutionResult`.

3. Create adapter implementations for at least one external tool as proof
   of concept.

**External tool mapping**:

| Tool | Fits As | Role in Architecture |
|------|---------|---------------------|
| Kestra | Orchestration engine | DAG executor for WP dependency graphs. Event-sourced. Replaces in-process WP scheduling. |
| n8n | Orchestration engine (visual) | Visual DAG executor with webhook-driven agent connector triggers. |
| PromptFlow | Agent Tool Connector | Microsoft's prompt chaining structures prompt -> agent -> result with tracing. |
| Semantic Kernel | Agent Tool Connector SDK | Programmatic adapter layer. Plugins map to governance injection point. |
| LangFlow | Agent Tool Connector (visual) | Visual prompt flow builder for doctrine-enriched prompt construction. |

**Key architectural insight**: None of these replace Kitty-core (planning,
doctrine, charter). They replace the execution machinery. Principle 2
(implementation-agnostic boundaries) means the Orchestration container's
interface contract stays the same regardless of backend.

**Integration pattern**:

```
Kitty-core (doctrine + planning)
  |
  v  [interface contract]
Orchestration (Kestra / n8n / in-process)
  |
  v  [connector contract]
Agent adapter (PromptFlow / SK / LangFlow / markdown templates)
```

### Phase 3: Event Store Interface Abstraction

**Goal**: Formalize the Event Store container boundary so alternative backends
(database, remote service) can replace the current filesystem implementation.

**Deferred**: Lower priority than Phases 1-2. The current filesystem-based
event store (JSONL + frontmatter) works for local-first operation.

## Critical Path

```
Curation cycle (interactive review of 046 artifacts)
  |
  v
Phase 1: Charter resolver + mission template extraction
  |
  v
Phase 2: Connector interface contract
  |
  v
Phase 3: Event store abstraction (deferred)
```

Phase 1 is complete. Phase 2 is now the critical path item.

## Curation Prerequisite

Before Phase 1, all 046 doctrine artifacts must be reviewed through an
interactive curation cycle to confirm alignment with project owner intent:

- 26 enriched directives (001-026): intent, procedures, tactic_refs, scope
- 12 shipped tactics: steps, references, operational guidance
- Paradigm extensions: opposed_by tensions, tactic_refs wiring
- 7 new directives (020-026): validate these are the right concepts to formalize

**Method**: Top-to-bottom vertical slices per directive. For each directive,
review intent -> scope -> procedures -> tactic_refs (resolve to full tactics)
-> opposed_by tensions. Confirm or adjust at each layer.

## Feature 055 — Doctrine Stack Init & Profile Integration

### Architectural Assessment (2026-03-20)

Feature 055 fills the remaining gaps between the doctrine repository layer (046)
and runtime execution. It targets three integration surfaces:

1. **Init-time doctrine onboarding** — Embeds charter setup into
   `spec-kitty init` (accept defaults or inline interview). Closes the gap
   where governance activation was a disconnected discovery step.

2. **Profile injection at workflow execution** — The implement workflow resolves
   agent profiles from WP frontmatter and injects identity fragments into the
   prompt. Same injection pattern as charter governance context
   (`_render_charter_context()` in `workflow.py`). This makes profiles
   functional participants in the Execution Coordination behavior loop
   (see `docs/architecture/02_containers/README.md`).

3. **Default fallback identity (`generic-agent`)** — Proposed in `_proposed/`
   with single directive reference. Ensures backward compatibility for projects
   without explicit profile assignments.

### Relationship to Initiative Phases

| Initiative Phase | 055 Contribution |
|------------------|------------------|
| Phase 1 (Charter Resolver) | Extends: init-time charter generation from defaults or interview answers |
| Phase 2 (Connector Interface) | Prepares: profile identity fragments become part of the governance context payload that connectors must carry |
| Curation Prerequisite | Respects: `generic-agent` profile + directive start in `_proposed/`, require HIC review before promotion |

### Scope Boundaries

055 does **not** address:
- Profile injection for non-implement workflows (review, accept). Natural follow-on.
- Profile inheritance resolution (045-WP15). `generic-agent` is standalone.
- Connector protocol formalization (Phase 2). 055 uses the current render-to-file path.
- Modular code refactoring (004). Orthogonal file sets, no functional dependency.

### Pre-work Included

- **`--feature` → `--mission` rename** (issue #241): Boy Scout cleanup of
  terminology drift. Introduces `--mission` as canonical flag, preserves
  `--feature` as deprecated alias with warning. Scoped as pre-work to avoid
  introducing new `--feature` references in 055's init and workflow changes.

### Architectural Dependencies

- `AgentProfileRepository` (045-WP02): shipped, provides two-source profile resolution
- `DoctrineService` (046): shipped, provides typed artifact access
- Charter resolver (054): shipped, provides action-scoped context injection
- Profile CLI (`agent profile show/list`): shipped (045-WP07), used by `profile-context` template

### Gap Analysis: Issue #284 (Customizable Git Strategy)

This direction is now obsolete. Later runtime work standardized on mandatory
execution lanes and removed configurable git-topology branches from the active
system.

What 055 still proves is narrower and still valid:
- doctrine artifacts can be resolved at runtime and injected into execution
  context
- profile defaults can be overridden by project-level selections

What 055 does **not** imply anymore:
1. Git execution topology should be doctrine-configurable
2. The orchestrator should become strategy-polymorphic
3. The charter should decide between multiple workspace/branching models

Current position:
- doctrine influences behavior inside the lane-only runtime
- doctrine does not select between competing git execution strategies
- `lanes.json` and the lane allocator are the only source of workspace topology

## Observation: Agent Hook-Based Enforcement

Some agentic tooling providers support **pre-tool-use hooks** — shell scripts
that intercept and rewrite tool calls before execution. Claude Code's
`PreToolUse` hook is the reference implementation: it can transparently rewrite
`git status` → `rtk git status` without requiring the agent to be aware of the
proxy, providing deterministic enforcement of tooling guidance like DIRECTIVE_028.

### Architectural implications

Hook-based enforcement sits at a **different layer** than doctrine injection:

```
Doctrine (directives, toolguides)        ← guidance layer (all agents)
  |
  v
Charter context injection           ← prompt layer (all agents)
  |
  v
Agent hook rewrite (PreToolUse)           ← enforcement layer (select agents only)
```

The guidance and prompt layers are universal — every agent receives tooling
directives through the charter context pipeline. The hook layer is an
**optional acceleration** that provides deterministic enforcement for agents
whose host environment supports it.

### Provider support matrix (known)

| Provider | Hook support | Enforcement path |
|----------|-------------|------------------|
| Claude Code | Yes (`PreToolUse`, `PostToolUse`) | Shell script intercepts and rewrites Bash tool calls |
| GitHub Copilot | No | Directive-only (prompt layer) |
| Cursor | No | Directive-only (prompt layer) |
| Windsurf | No | Directive-only (prompt layer) |
| Others | Unknown | Assume directive-only until verified |

### Design rule

**Hooks must not be the sole mechanism for enforcing tooling behavior.** The
doctrine stack (directive + toolguide + charter context) is the primary
guidance layer and must be sufficient on its own. Hooks are a deterministic
accelerator when available — they reduce token waste and eliminate agent
decision overhead — but the system must degrade gracefully to directive-only
guidance when hooks are not supported.

This means:
1. Directives and toolguides must contain complete guidance (not "use the hook")
2. Charter context injection must surface tooling preferences in prompts
3. Hooks are additive enforcement, not a replacement for prompt-layer governance
4. Agent-specific hook configurations belong in the agent's environment
   (e.g., `.claude/settings.json`), not in doctrine artifacts

## Related Artifacts

- Feature 046 spec: `kitty-specs/046-doctrine-artifact-domain-models/spec.md`
- System Landscape: `docs/architecture/00_landscape/README.md`
- Implementation Mapping: `docs/architecture/04_implementation_mapping/README.md`
- Current resolver: `src/specify_cli/charter/resolver.py`
- Current prompt builder: `src/specify_cli/next/prompt_builder.py`
- Mission schema: `src/doctrine/schemas/mission.schema.yaml`
- DoctrineService: `src/doctrine/service.py`
- Feature 055 spec: `kitty-specs/055-doctrine-stack-init-and-profile-integration/spec.md`
- Issue #284: Hardened and customizable git usage
- Issue #241: Rename `--feature` flag to `--mission`
