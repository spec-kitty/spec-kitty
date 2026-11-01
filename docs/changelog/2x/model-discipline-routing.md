---
title: 2.x Model Discipline and Cost-Aware Routing (Draft)
description: Historical Spec Kitty 2.x archive page for 2.x Model Discipline and Cost-Aware Routing (Draft); use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03'
related:
- context
- changelog/2x/model-to-task_type
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 2.x Model Discipline and Cost-Aware Routing (Draft)

**Status**: Draft  
**Date**: 2026-02-28  
**Scope**: User journey + implementation research for model-aware task assignment

## Problem Statement

In current 2.x flow, task execution is agent-selected by the operator (`--agent <name>`), with optional static preferences in
`.kittify/config.yaml`. This is simple, but it does not optimize for:

1. Task fit (which model is strongest for this task type)
2. Quality/cost trade-offs
3. Consistent governance when assignment decisions vary by operator

## Current Baseline (What Exists Today)

1. `spec-kitty next` requires `--agent` and does not recommend a model/tool automatically (`src/specify_cli/cli/commands/next_cmd.py`).
2. Tool selection uses the `agents.available` list order with first-available fallback (
   `src/specify_cli/core/tool_config.py`).
3. Agent profiles already support weighted matching by task context, but no model-cost dimension (`src/doctrine/agent_profiles/repository.py`).
4. Doctrine artifacts already provide governance hooks (directives, toolguides) for 2.x (`docs/changelog/2x/doctrine-and-charter.md`).

## Proposed User Journey

### Scenario

A team enables a **Model Discipline** doctrine rule so Spec Kitty can recommend the best available model for each task, balancing quality, cost tier, and known weaknesses, while still allowing explicit operator override.

### Actors

| # | Actor                             | Type     | Role in Journey                                                 |
|---|-----------------------------------|----------|-----------------------------------------------------------------|
| 1 | Project Operator                  | `human`  | Chooses policy level and can override recommendations           |
| 2 | Spec Kitty CLI                    | `system` | Computes task type, recommends tool/model pair, enforces policy |
| 3 | Model Catalog Updater             | `system` | Refreshes capability/cost metadata from configured sources      |
| 4 | Agent Runtime (Claude/Codex/etc.) | `llm`    | Executes the assigned work package                              |

### Preconditions

1. Feature and work packages exist (`kitty-specs/<mission>/tasks/WP*.md`).
2. `.kittify/config.yaml` has available tools configured.
3. Doctrine bundle includes model-discipline directive/toolguide and task-type mapping file.

### Journey Map

| Phase                   | Actor(s)                 | System                                                         | Key Events                                             |
|-------------------------|--------------------------|----------------------------------------------------------------|--------------------------------------------------------|
| 1. Configure Policy     | Operator                 | Enables model-discipline mode in config/charter profile   | `ModelDisciplineConfigured`                            |
| 2. Refresh Catalog      | Model Catalog Updater    | Pulls latest model ranking metadata and pricing snapshots      | `ModelCatalogRefreshed`                                |
| 3. Classify Task        | Spec Kitty CLI           | Determines task type from mission step + WP metadata           | `TaskTypeClassified`                                   |
| 4. Recommend Assignment | Spec Kitty CLI           | Scores candidates by quality/cost/risk and suggests tool+model | `ModelAssignmentRecommended`                           |
| 5. Execute/Override     | Operator + Agent Runtime | Accepts recommendation or overrides with reason                | `ModelAssignmentAccepted`, `ModelAssignmentOverridden` |
| 6. Capture Metrics      | Spec Kitty CLI           | Stores usage/cost/performance outcomes for future tuning       | `ModelExecutionMetricsCaptured`                        |

### Coordination Rules

**Default posture**: Advisory (Phase 1), then Gated (Phase 2+)

1. If policy mode is `advisory`, non-compliant selections warn but do not block.
2. If policy mode is `gated`, non-compliant selections require explicit override reason.
3. If policy mode is `required`, assignment blocks until a compliant model or override waiver is recorded.

## Proposed 2.x Artifact Design

### 1. New Directive

Add a doctrine directive such as:

1. `src/doctrine/directives/020-model-discipline-routing.directive.yaml`

Purpose:

1. Require model-to-task fit checks before assignment.
2. Require cost-tier awareness and explicit override capture.

### 2. New Toolguide

Add a model discipline toolguide:

1. `src/doctrine/toolguides/model-discipline.toolguide.yaml`
2. `src/doctrine/toolguides/MODEL_DISCIPLINE.md`

Purpose:

1. Define task type taxonomy (`implementation`, `review`, `research`, `refactor`, `doc-authoring`, etc.).
2. Explain scoring dimensions (quality, weakness risk, cost tier, latency tier).
3. Define override rules and audit expectations.

### 3. Model-to-Task Mapping Data

Add a machine-readable mapping file:

1. `src/doctrine/toolguides/model-to-task_type.yml`

Suggested schema sections:

1. `task_types`
2. `models` (strengths, weaknesses, supported tools, cost tier, optional price per 1M tokens)
3. `routing_policy` (weights + thresholds)
4. `sources` (where each metric came from + timestamp)

Recommended follow-up:

1. Add `src/doctrine/schemas/model-to-task_type.schema.yaml` for validation.

## Proposed YAML Schema (v1.0)

Use this schema for validating [`model-to-task_type.yml`](model-to-task_type.md):

## Implementation Approach (Phased)

### Phase 0: Advisory-only research slice

1. Load mapping file and compute recommendations without changing assignment behavior.
2. Expose recommendation in `spec-kitty next --json` payload as additional fields (`recommended_agent`, `recommended_model`, `rationale`).
3. Keep `--agent` mandatory for backwards compatibility.

### Phase 1: Optional auto-selection

1. Add `--agent auto` support in `next` and workflow commands.
2. Resolve `tool+model` from mapping and configured availability.
3. Persist selected model in WP history metadata (or event payload) for traceability.

### Phase 2: Directive enforcement

1. Wire directive checks into execution path (pre-transition validation before moving WP to `doing`).
2. Enforce advisory/gated/required behavior from config.
3. Require override reason when non-compliant choices are used.

### Phase 3: Feedback loop

1. Record observed cost, latency, and acceptance outcomes.
2. Use telemetry to tune weights and reduce static assumptions.
3. Add periodic catalog sync command (e.g., `spec-kitty model sync`).

## Integration Points in Current Code

1. `src/specify_cli/core/tool_config.py`  
   Extend selection config with model-discipline routing dimensions.
2. `src/specify_cli/cli/commands/next_cmd.py`  
   Add optional auto-routing input/output surface.
3. `src/specify_cli/next/runtime_bridge.py`  
   Compute routing recommendation before decision output.
4. `src/specify_cli/cli/commands/agent/workflow.py`  
   Consume resolved agent/model for implement/review handoff.
5. `src/doctrine/agent_profiles/repository.py`  
   Extend weighted scoring with cost/quality dimensions from model catalog.

## Data Source Research Notes

### Arena data

1. Arena’s public docs describe leaderboard evaluation as human preference voting, and publish open datasets monthly.
2. Arena Terms include restrictions on bots/scraping/harvesting without authorization.

Implication:

1. Prefer documented/official data channels (published datasets/APIs) over raw HTML scraping of `arena.ai/leaderboard`.
2. Treat Arena rankings as one quality signal, not a direct task-specialization oracle.

### Cost data

1. Arena leaderboard data does not provide comprehensive pricing metadata.
2. Cost-per-1M token fields should be sourced from provider pricing pages/APIs and versioned with timestamps.

## Risks and Mitigations

1. **Config schema drift**: current save path rewrites `tools.selection` with only two fields.  
   Mitigation: introduce explicit schema version + preserve/round-trip unknown fields during migration.
2. **False confidence from leaderboard rank**: global rank may not match local task quality.  
   Mitigation: include weakness flags and local telemetry feedback.
3. **Operator trust**: opaque routing decisions reduce adoption.  
   Mitigation: always show rationale and allow controlled override.
4. **Rapid model churn**: rankings and prices change frequently.  
   Mitigation: freshness timestamps + configurable staleness thresholds.

## Suggested MVP Decision

Start with **advisory mode** in 2.x:

1. Add directive + toolguide + mapping file.
2. Return recommendation metadata in `next --json`.
3. Do not block current workflows yet.

This gives immediate value (visibility + consistency) with low migration risk.

## External References

1. Arena home/terms: https://lmarena.ai/
2. Arena how-it-works and dataset notes: https://lmarena.ai/howitworks/
3. Arena leaderboard policy: https://lmarena.ai/leaderboard-policy/
4. Arena-rank package (public ranking/data access workflow): https://pypi.org/project/arena-rank/
5. OpenAI API pricing: https://openai.com/api/pricing/
6. Anthropic API pricing: https://www.anthropic.com/pricing
