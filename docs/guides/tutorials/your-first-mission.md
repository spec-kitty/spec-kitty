---
title: 'Your First Mission: Complete Workflow'
description: Walk through a complete Spec Kitty 3.2 mission from specification through plan, tasks, implementation, review, and merge.
doc_status: active
updated: '2026-09-14'
audience: docs/context/audience/external/project-owner.md
type: tutorial
related:
- docs/guides/tutorials/getting-started.md
- docs/guides/tutorials/multi-agent-workflow.md
---
# Your First Mission: Complete Workflow

**Divio type**: Tutorial

This tutorial walks you through the entire Spec Kitty workflow from specification to merge.

Except for the one-time CLI install, everything below happens inside your AI agent's chat interface — Claude Code, Codex CLI, or another configured harness. When a step says "in your agent," open that chat and type the command there; it is not a bare-terminal instruction.

**Time**: ~2 hours
**Prerequisites**: Completed [Getting Started](getting-started.md) — including its
mission, which this tutorial continues rather than re-creating (see Step 1)

![Your first Spec Kitty mission - Mission Kitty briefing](../../assets/images/your-first-mission-mission-kitty.png)

_Stylized splash — the cards are decorative. The full workflow is specify, plan, tasks, analyze, implement, review, accept, merge, laid out in the Overview below._

>[!NOTE]
>This tutorial uses git for version control. Spec Kitty abstracts the VCS operations into simple commands.

## Overview

Workflow path:

```
/spec-kitty.specify → /spec-kitty.plan → /spec-kitty.tasks → /spec-kitty.analyze → spec-kitty next → /spec-kitty.accept → /spec-kitty.merge
```

You will build a tiny "task list" feature as the concrete example.

## Step 1: Have a Mission to Work In

This step has two paths, and **only one of them runs `specify`**. Pick yours
before typing anything.

### If you came from Getting Started — you already have the mission

You created it in that tutorial's Step 3. **Do not run `specify` again: go
straight to [Step 2](#step-2-create-the-technical-plan).** Running it a second
time does not edit or replace the mission you have; it creates a second one,
and you would spend the rest of this tutorial with two task-list missions and
no indication of which one you are working in.

Confirm what you already have:

```bash
ls kitty-specs
```

One directory is what you want. Its specification must also be populated and
committed before planning — Step 2 opens with how to check that.

### If you are starting fresh — create the mission now

From the project root, in your agent:

```text
/spec-kitty.specify Build a tiny command-line task list app with add, complete, and delete actions.
```

Answer the discovery interview until it completes. This runs inside your agent's interactive chat — Claude Code, Codex CLI, or any other configured harness — the agent asks a discovery interview before writing anything; keep answering until it says the interview is complete.

Expected results:

- One new mission directory under `kitty-specs/`, named `<slug>-<id>` — for
  example `task-list-01M20JM4`. The trailing token is the mission's own
  identifier, so yours will differ.
- `spec.md` inside it

**Starting from an upstream brief instead?** If your brief was exported by
another requirements tool and carries YAML frontmatter with
`handoff_packet: 1`, `spec-kitty intake --auto` (which also scans
`.handoff/*.md` at the project root) picks it up automatically, and
`/spec-kitty.specify` adopts its FR/AC ids instead of re-inventing them. This
is optional and safe — a brief without that frontmatter behaves exactly like
the plain-prose flow above, and the discovery interview still runs. See
[Handoff Packet v1](../../contracts/handoff-packet-v1.md).

## Step 2: Create the Technical Plan

Stay in the repository root checkout. Planning happens there, but the mission target branch can be the current branch or an explicit branch you chose before creation.

In your terminal, capture the exact directory name from Getting Started. The
commands below use this handle throughout; repeat this assignment if you open a
new terminal:

```bash
ls kitty-specs
printf 'Paste your mission directory name: '
read -r MISSION
test -f "kitty-specs/$MISSION/spec.md"
MISSION_ID=$(jq -r .mission_id "kitty-specs/$MISSION/meta.json")
```

Finish the specification with your agent before planning: it must contain real
Functional Requirements and be committed. Mission creation commits the generated
metadata and task scaffold, but leaves the initial `spec.md` uncommitted for your
agent to populate. The agent's `specify` workflow uses `spec-kitty spec-commit`
after authoring and reviewing the specification. If you edited the spec yourself,
commit it from the same planning branch:

```bash
spec-kitty spec-commit --mission "$MISSION" --message "Add task list specification" \
  "kitty-specs/$MISSION/spec.md"
```

An unedited scaffold or an uncommitted specification blocks planning. Complete
that work before continuing.

In your agent:

```text
/spec-kitty.plan Use Python 3.11, SQLite, and a minimal CLI interface.
```

Answer the planning questions and confirm the Engineering Alignment summary.

Expected results:

- `kitty-specs/$MISSION/plan.md`
- Updated planning artifacts in the repository root checkout

## Step 3: Generate Work Packages

In your agent:

```text
/spec-kitty.tasks
```

This generates `tasks.md` and individual work package files under:

```
kitty-specs/$MISSION/tasks/
```

Each WP file includes frontmatter with its `lane` and dependencies.

## Step 4: Check Consistency Before Implementing

Before any code gets written, run the analyze step. It cross-checks your spec, plan, and tasks.md for gaps, contradictions, and missing coverage — catching drift while it is still cheap to fix. In your agent:

```text
/spec-kitty.analyze
```

This step is read-only — it reports findings, it does not modify your artifacts or touch code. Resolve anything it flags (usually a quick edit to spec.md, plan.md, or a task file) before moving on.

## Step 5: Enter the Runtime Loop

Most harness users don't drive this loop manually. Instead, invoke
`spk-run-implement-review` (also usable by its detailed legacy alias
`spec-kitty-implement-review`) and let it drive the whole loop — it
orchestrates claim, implement, and review across every WP in the mission on
your behalf. This is the recommended path for interactive harness use,
including a full-mission sprint across WP01 through WP_N. See the
[spk-run-implement-review skill reference](../../api/skills/spk-run-implement-review.md)
for what it does step by step.

### Under the hood: the manual runtime loop

The skill above is doing the following on your behalf. Use this manual form
directly only when scripting, running non-interactively, or debugging.

Start the mission loop from your terminal:

```bash
spec-kitty next --agent claude --mission "$MISSION" --json
```

The runtime returns the next action to take. During implementation you will usually see an `implement` decision for a specific WP.

Execute that action with the lower-level command the runtime expects:

```bash
spec-kitty agent action implement WP01 --agent claude
```

That command allocates or reuses the correct lane workspace. Make your code changes there, run the relevant tests, then report the result back to the runtime:

```bash
spec-kitty next --agent claude --mission "$MISSION" --result success --json
```

Repeat the loop until the runtime starts issuing review work instead of implementation work.

In practice, once the runtime hands you an `implement` decision for a WP, you do not type raw CLI mid-conversation — you `cd` into (or open) the execution workspace the command just allocated and type the matching slash command in your agent's chat:

```text
/spec-kitty.implement
```

or run the CLI form shown above directly — useful for scripting or a non-interactive harness. Both resolve to the same prompt file.

#### Same loop, another harness

```bash
spec-kitty next --agent codex --mission "$MISSION" --json
spec-kitty agent action implement WP01 --agent codex
spec-kitty next --agent codex --mission "$MISSION" --result success --json
```

The loop is identical for every supported harness — only the `--agent` value changes.

## Step 6: Review the work package

When the runtime points you at review work, run the matching action:

```bash
spec-kitty agent action review WP01 --agent claude
```

Address any review feedback, then continue the `spec-kitty next` loop until the mission is ready for acceptance.

**If review sends work back**: A review verdict of `changes_requested` sends the WP back to `in_progress` (small fixes, same agent keeps working) or `planned` (needs more substantial rework) — it never leaves the WP silently stuck in review. Keep following the `spec-kitty next` loop; it hands you the WP again once it's ready.

## Step 7: Accept and Merge

Once review passes, validate and accept.

In your agent:

```text
/spec-kitty.accept
```

Or via CLI:

```bash
spec-kitty accept
```

Then merge the mission's work package branches.

In your agent:

```text
/spec-kitty.merge
```

Or via CLI:

```bash
spec-kitty merge
```

You should see the mission's work merged into the target branch and the worktrees cleaned up.

Before you move on, complete the three post-merge steps:

1. **Mission review** — run `/spec-kitty-mission-review` in your agent to verify spec→code
   fidelity.
2. **Verify the retrospective** — under default policy Spec Kitty already wrote a
   `retrospective.yaml` during merge. Find it at:
   ```bash
   cat ".kittify/missions/$MISSION_ID/retrospective.yaml"
   ```
   If the file is absent, author it: `spec-kitty retrospect create --mission "$MISSION_ID"`.
3. **Surface findings** — review the record's proposals:
   ```bash
   spec-kitty retrospect summary                              # cross-mission aggregation (read-only)
   spec-kitty agent retrospect synthesize --mission <slug>  # inspect proposals (dry-run by default)
   ```

For the full retrospective workflow, see
[How to Use Retrospective Learning](../how-to/governance/use-retrospective-learning.md).

## Troubleshooting

- **"Planning created a worktree"**: Planning stays in the repository root checkout in the current 3.2 workflow. If you see an unexpected planning worktree, upgrade with `spec-kitty upgrade`.
- **"I want to plan from here but not land on `main`"**: Stay in the repository root checkout and choose the right target branch first. See [How to Keep Main Clean](../how-to/missions/keep-main-clean.md).
- **"WP has dependencies"**: Keep following the `spec-kitty next` decisions; the runtime will only issue implementation work when its dependencies are satisfied.
- **Review fails validation**: Run `spec-kitty validate-tasks --fix` and re-run `/spec-kitty.review`.

## What's Next?

Continue with [Multi-Agent Workflow](multi-agent-workflow.md) to learn parallel development with multiple agents.

### Related How-To Guides

- [Create a Plan](../how-to/missions/create-plan.md) - Detailed planning guidance
- [Keep Main Clean](../how-to/missions/keep-main-clean.md) - Choose a target branch without changing planning location
- [Generate Tasks](../how-to/missions/generate-tasks.md) - work package generation
- [Implement a work package](../how-to/missions/implement-work-package.md) - Implementation details
- [Review a work package](../how-to/missions/review-work-package.md) - Review process
- [Accept and Merge](../how-to/missions/accept-and-merge.md) - Final merge workflow

### Reference Documentation

- [CLI Commands](../../api/cli-commands.md) - Full command reference
- [Slash Commands](../../api/slash-commands.md) - Agent slash commands
- [File Structure](../../api/file-structure.md) - Project layout explained

### Learn More

- [Execution Workspace Model](../../architecture/execution-lanes.md) - Why modern missions use lane worktrees
- [Kanban Workflow](../../architecture/kanban-workflow.md) - Lane transitions
- [Spec-Driven Development](../../architecture/spec-driven-development.md) - The philosophy
