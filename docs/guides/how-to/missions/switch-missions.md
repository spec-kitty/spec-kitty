---
title: How to Switch Missions
description: Choose and change missions to match software, research, or documentation workflows.
doc_status: active
updated: '2026-06-03'
type: how-to
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
related:
- guides/how-to/missions/create-specification
- guides/how-to/installation/install-and-upgrade
---
# How to Switch Missions

Missions shape the prompts, artifacts, and workflows Spec Kitty uses for each feature. Each feature selects one mission during `/spec-kitty.specify`, and you can inspect or start new features with a different mission at any time.

## Understanding Per-Feature Missions

- Missions are scoped per feature folder under `kitty-specs/`.
- The mission defines the workflow steps — each with its own templates — and the artifacts created.
- Switching missions means creating a new feature with a different mission, not mutating an existing feature's mission.

## Mission Selection

During specification, Spec Kitty infers the mission from your prompt or lets you choose explicitly.

```bash
/spec-kitty.specify "Research market viability"
# -> Infers "research" mission
```

## Listing Available Missions

```bash
spec-kitty mission list
```

This shows all missions and highlights the active mission for the current feature.

## Getting Mission Info

```bash
spec-kitty mission info research
```

Use this to review the steps, their templates, and expected artifacts before you start.

## Working with Different Missions

### Software Dev Mission

Use this for product and engineering delivery.

Workflow:
- Specify -> Plan -> Tasks -> Implement -> Review

Key artifacts:
- `spec.md`, `plan.md`, `tasks/`, execution workspaces

### Research Mission

Use this for investigations, experiments, or feasibility work.

Workflow:
- Question -> Methodology -> Gather -> Analyze -> Synthesize

Key artifacts:
- Research prompts, findings, and summary reports

### Documentation Mission

Use this when your goal is documentation coverage or quality.

Workflow:
- Audit -> Design -> Generate -> Validate

Key artifacts:
- Coverage matrix, doc plan, generated doc sets

---

## Command Reference

- [Missions](../../../api/missions.md) - All available missions
- [CLI Commands](../../../api/cli-commands.md) - Mission CLI commands

## See Also

- [Create a Specification](create-specification.md) - Start with any mission
- [Install and Upgrade](../installation/install-and-upgrade.md) - Initial setup options

## Background

- [Mission System](../../../architecture/mission-system.md) - How missions work internally
- [Documentation Mission](../../../architecture/documentation-mission.md) - Divio documentation workflow

## Getting Started

- [Missions Overview](../../tutorials/missions-overview.md) - Tutorial walkthrough
