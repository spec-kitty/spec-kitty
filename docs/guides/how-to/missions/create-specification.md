---
title: How to Create a Feature Specification
description: 'How to create a feature specification with Spec Kitty 3.2: Use this guide to capture a new feature specification with /spec-kitty.specify.'
doc_status: active
updated: '2026-06-03'
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
type: how-to
related:
- guides/how-to/missions/create-plan
- guides/how-to/missions/keep-main-clean
- guides/how-to/missions/switch-missions
---
# How to Create a Feature Specification

Use this guide to capture a new feature specification with `/spec-kitty.specify`.

## When to Use

Run this when you are starting a brand-new feature and need a spec before planning or implementation.

## The Command

In your agent:

```text
/spec-kitty.specify <description>
```

Run it from the repository root checkout. Planning artifacts are created in `kitty-specs/` on the mission's target branch, and no worktrees are created during specify. If you do not pass `--target-branch`, Spec Kitty uses the current branch.

When you run the direct CLI form (`spec-kitty specify <description>`), it creates the mission scaffold and marks the result as scaffold-only. Fill `spec.md` with the complete specification before running `spec-kitty plan --mission <mission>`.

## The Discovery Interview

After the command, the CLI interviews you for missing details. You must answer each question before the spec is generated. Expect the agent to respond with `WAITING_FOR_DISCOVERY_INPUT` until the interview is complete.

## What Gets Created

- `kitty-specs/###-feature/spec.md`
- `kitty-specs/###-feature/meta.json`
- `kitty-specs/###-feature/checklists/requirements.md`

## Example

```text
/spec-kitty.specify Build a photo organizer that groups albums by date and supports drag-and-drop reordering.
```

During discovery, answer follow-up questions (roles, constraints, success criteria). Once complete, write the specification content to `kitty-specs/<feature>/spec.md` on the mission's target branch.

## Troubleshooting

- **Stuck on discovery**: Answer the remaining interview questions. The spec will not be created until the interview is complete.
- **Wrong directory**: Run from the repository root checkout, not from a worktree.
- **Wrong landing branch**: Check `spec-kitty agent mission branch-context --json` before creating the mission, or pass `--target-branch <branch>` explicitly.
- **Need to revise the spec**: Re-run `/spec-kitty.specify` with the updated description and follow the interview again.

---

## Command Reference

- [Slash Commands](../../../api/slash-commands.md) - All `/spec-kitty.*` commands
- [CLI Commands](../../../api/cli-commands.md) - Full CLI reference

## See Also

- [Create a Plan](create-plan.md) - Next step after specification
- [Keep Main Clean](keep-main-clean.md) - Choose a target branch without changing planning location
- [Switch Missions](switch-missions.md) - Choose different mission types

## Background

- [Spec-Driven Development](../../../architecture/spec-driven-development.md) - Why specs come first
- [Mission System](../../../architecture/mission-system.md) - How missions affect specifications

## Getting Started

- [Getting Started Tutorial](../../tutorials/getting-started.md) - Hands-on introduction
- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
