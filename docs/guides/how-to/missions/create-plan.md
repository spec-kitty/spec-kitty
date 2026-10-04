---
title: How to Create a Technical Plan
description: 'How to create a technical plan with Spec Kitty 3.2: Use this guide to turn a finished spec into a technical plan with /spec-kitty.plan.'
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/missions/create-specification.md
- docs/guides/how-to/missions/generate-tasks.md
- docs/guides/how-to/missions/keep-main-clean.md
---
# How to Create a Technical Plan

Use this guide to turn a finished spec into a technical plan with `/spec-kitty.plan`.

## Prerequisites

- `kitty-specs/<feature>/spec.md` exists
- You are in the repository root checkout
- Planning artifacts stay on the mission's target branch (current branch by default, or an explicit `--target-branch`)

## The Command

In your agent:

```text
/spec-kitty.plan
```

Optionally include your stack or architecture preferences in the same message.

## The Planning Interview

The planner asks architecture and non-functional questions. It pauses with `WAITING_FOR_PLANNING_INPUT` until you answer each one.

## What Gets Created

- `kitty-specs/<feature>/plan.md`
- `kitty-specs/<feature>/research.md` (if research is required)
- `kitty-specs/<feature>/data-model.md` (when data is involved)
- `kitty-specs/<feature>/contracts/` (API contracts when applicable; a Mission that defines no interfaces can waive it, see [When a Mission defines no contracts](accept-and-merge.md#when-a-mission-defines-no-contracts))
- Updated agent context files (based on the plan)

## implementation concern map

When a mission involves multiple distinct architectural areas, `plan.md` includes an
**implementation concern map** — a structured decomposition of intent before tasks are
generated.

Implementation concerns (IC-01, IC-02, …) are plan-level architectural units. They are
**not** work packages and are **not** executable units. Each concern captures:

- **Purpose**: what this area addresses and why it matters
- **Relevant requirements**: FR-### refs from `spec.md`
- **Affected surfaces**: file paths or module names
- **Sequencing/depends-on**: which other concerns this one must follow
- **Risks**: key coordination notes

`/spec-kitty.tasks` translates these concerns into executable work packages. One concern
may become multiple WPs; multiple small concerns may merge into one WP.

## Example

```text
/spec-kitty.plan Use FastAPI + PostgreSQL. Deploy on Fly.io. Use JWTs for auth.
```

## Troubleshooting

- **No plan generated**: Make sure the spec exists and you are running in the repository root checkout.
- **Planner keeps asking questions**: Provide the missing architectural details; the plan will not generate until the interview is complete.
- **Planner is targeting the wrong branch**: Resolve branch intent first with `spec-kitty agent mission branch-context --json` or recreate the mission with the right `--target-branch`.
- **Need to update the plan**: Re-run `/spec-kitty.plan` with the new constraints.

---

## Command Reference

- [Slash Commands](../../../api/slash-commands.md) - All `/spec-kitty.*` commands
- [CLI Commands](../../../api/cli-commands.md) - Full CLI reference
- [File Structure](../../../api/file-structure.md) - Where plans are stored

## See Also

- [Create a Specification](create-specification.md) - Required before planning
- [Keep Main Clean](keep-main-clean.md) - Choose a target branch without changing planning location
- [Generate Tasks](generate-tasks.md) - Next step after planning

## Background

- [Spec-Driven Development](../../../architecture/spec-driven-development.md) - The philosophy
- [Kanban Workflow](../../../architecture/kanban-workflow.md) - How work flows after planning

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
