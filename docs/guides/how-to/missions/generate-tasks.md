---
title: How to Generate Work Packages
description: 'How to generate work packages with Spec Kitty 3.2: Use this guide to turn a plan into work packages with /spec-kitty.tasks.'
doc_status: active
updated: '2026-06-06'
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
type: how-to
related:
- guides/how-to/missions/create-plan
- guides/how-to/missions/handle-dependencies
- guides/how-to/missions/implement-work-package
- guides/how-to/missions/keep-main-clean
---
# How to Generate Work Packages

Use this guide to turn a plan into work packages with `/spec-kitty.tasks`.

`/spec-kitty.tasks` translates implementation concerns (IC-## entries) from `plan.md`
into executable work packages. One concern may become multiple WPs; multiple small
concerns may merge into a single WP. Each generated WP should cite the implementation
concern(s) it addresses via `plan_concern_refs` in `wps.yaml`.

## Prerequisites

- `kitty-specs/<feature>/plan.md` exists
- All `[NEEDS CLARIFICATION]` items are resolved
- You are in the repository root checkout
- Task artifacts are committed to the mission's target branch

## The Command

In your agent:

```text
/spec-kitty.tasks
```

## What Gets Created

- `kitty-specs/<feature>/tasks.md` (overview checklist)
- `kitty-specs/<feature>/tasks/WP01-*.md`, `WP02-*.md`, ... (prompt files)

Work packages live in a **flat** `tasks/` directory. Lane status is stored in each prompt file frontmatter via `lane: "planned"`.

## Understanding Work Packages

Each WP file contains:
- A single goal for the agent
- Subtasks and dependencies
- The exact completion command to move the WP to review

## Finalizing Tasks

After reviewing the generated WPs, finalize the task set.

In your terminal:

```bash
spec-kitty agent mission finalize-tasks
```

## Example Output

```
kitty-specs/012-feature/tasks.md
kitty-specs/012-feature/tasks/WP01-auth-backend.md
kitty-specs/012-feature/tasks/WP02-auth-ui.md
kitty-specs/012-feature/tasks/WP03-tests.md
```

## Troubleshooting

- **Missing plan**: Run `/spec-kitty.plan` first.
- **Tasks look incomplete**: Resolve clarifications in `plan.md` and rerun `/spec-kitty.tasks`.
- **Wrong directory**: Run from the repository root checkout.
- **Wrong target branch**: Re-check `spec-kitty agent mission branch-context --json` before regenerating tasks.

---

## Command Reference

- [Slash Commands](../../../api/slash-commands.md) - All `/spec-kitty.*` commands
- [Agent Subcommands](../../../api/agent-subcommands.md) - `finalize-tasks` and more
- [File Structure](../../../api/file-structure.md) - Where tasks are stored

## See Also

- [Create a Plan](create-plan.md) - Required before task generation
- [Keep Main Clean](keep-main-clean.md) - Choose a target branch without changing planning location
- [Implement a work package](implement-work-package.md) - Next step after tasks
- [Handle Dependencies](handle-dependencies.md) - Managing WP dependencies

## Background

- [Kanban Workflow](../../../architecture/kanban-workflow.md) - Lane transitions explained
- [Execution Workspace Model](../../../architecture/execution-lanes.md) - Why modern features use lane worktrees

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
