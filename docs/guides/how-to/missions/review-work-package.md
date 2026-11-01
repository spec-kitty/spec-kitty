---
title: How to review a work package
description: 'How to review a work package with Spec Kitty 3.2: Use this guide to review a completed work package and update its lane.'
doc_status: active
updated: '2026-09-28'
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
type: how-to
related:
- guides/how-to/missions/accept-and-merge
- guides/how-to/missions/implement-work-package
---
# How to review a work package

Use this guide to review a completed work package and update its lane.

**Terminology note**
- Canonical 2.x model: `Mission Type -> Mission -> Mission Run`
- Review commands use `--mission` as the canonical tracked-mission selector

## Prerequisites

- The WP is in `lane: "for_review"`
- You are in a checkout where the mission can be resolved; `spec-kitty agent action review` will attach to the canonical execution workspace if needed
- In multi-mission repos, you know the mission slug

## Step 1: Discover Reviewable Work Packages

Before claiming a WP for review, check which work packages are waiting:

```bash
spec-kitty agent tasks list-tasks --lane for_review --mission <slug>
```

For machine-readable output:

```bash
spec-kitty agent tasks list-tasks --lane for_review --mission <slug> --json
```

If the `for_review` lane is empty, there is nothing to review. Wait for an
implementing agent to move a WP into that lane.

## Step 2: Load Governance Context

Load the project's review governance context before inspecting any code. This
surfaces charter rules, acceptance criteria templates, and review guidance
from doctrine:

```bash
spec-kitty charter context --action review --json
```

The returned `text` field contains governance context that applies to every
review in this project. If governance files are missing (no charter
configured), the command still works with fallback defaults -- it is not a
blocker.

## Step 3: Claim the work package

### Using the slash command

In your agent:

```text
/spec-kitty.review
```

You can also specify a WP ID:

```text
/spec-kitty.review WP01
```

### Using the CLI directly

```bash
spec-kitty agent action review WP01 --agent <your-name> --mission <slug>
```

Omit `WP01` to auto-select the first WP in the `for_review` lane:

```bash
spec-kitty agent action review --agent <your-name> --mission <slug>
```

The review command:
- Picks the next WP in `for_review` (or the one you specify)
- Moves it to `lane: "doing"` for review
- Prints the path to a generated review prompt file
- Shows the full prompt and the exact commands for passing or requesting changes

## Step 4: Read the Review Prompt

Read the review prompt file whose path was printed in Step 3:

```bash
cat <prompt-file-path>
```

The review prompt contains:

- Acceptance criteria for this specific WP
- Git diff commands with the correct base branch (use those, not hardcoded `main`)
- Dependency warnings if the WP has downstream dependents
- WP isolation rules
- Completion instructions (approve/reject commands)

Follow the review prompt. It is the source of truth for what to check and how
to check it. The review criteria come from doctrine and the WP definition, not
from this guide.

## Step 5: Issue Your Verdict

Take exactly one action -- never "approve with conditions".

### Passing Review

When everything looks good, move the WP to `approved`:

```bash
spec-kitty agent tasks move-task WP01 --to approved --mission <slug> --note "Review passed: <summary>"
```

### Providing Feedback (Rejection)

If changes are required:
1. Write feedback to a temporary file (the review prompt shows a unique suggested path).
2. Move the WP back to `planned` with `--review-feedback-file`.
3. The command writes the feedback into `review-cycle-N.md` next to the WP, commits it, and stores a pointer in the event log and frontmatter `review_feedback`.

Every blocking finding must map to a specific, verifiable remediation action.

When the rejection advertises a path inside the Mission (`kitty-specs/<slug>/tasks/<wp>/review-feedback-N.md`),
that file is a **draft**: the committed `review-cycle-N.md` carries its text verbatim, so the rejection
removes the draft once it has read the committed record back and found the text in it. Otherwise the
draft would be left untracked and the WP's next `move-task --to for_review` would refuse on it.

Only this work package's own `review-feedback-*.md`, directly inside its `tasks/<wp>/` directory, is ever
removed. A different file (`notes.md`, `research.md`, another work package's draft), a scratch note
under `/tmp` (as below), and a symbolic link are never touched. The removal is announced on stderr
(`Removed feedback draft <path> (its text is kept in review-cycle-N.md)`) and reported as
`retired_feedback_draft` in the `--json` output. There is deliberately no opt-out: the text is kept in
the review-cycle record, so nothing is lost.

The draft is **kept** silently when the record is not committed (`--no-auto-commit`) or when you
already committed it. It is kept **with a warning on stderr** when it could not be removed safely: it
is tracked and has uncommitted edits, the committed record does not hold its current text, it could
not be re-read, or the unlink failed.

In your terminal:

```bash
cat > /tmp/spec-kitty-review-feedback-WP01.md <<'EOF'
**Issue 1**: <description and how to fix>
**Issue 2**: <description and how to fix>
EOF

spec-kitty agent tasks move-task WP01 --to planned \
  --mission <slug> \
  --agent <your-agent-name> \
  --review-feedback-file /tmp/spec-kitty-review-feedback-WP01.md \
  --note "Changes requested: <summary>"
```

Rejection is an ordinary move, so it needs no `--force`. Pass your own
`--agent` identity. The implementer then resumes the rework and resubmits with
its own `--agent`, also without `--force`.

## Step 6: Check Downstream Impact

After rejecting a WP, check whether it has downstream dependents:

```bash
spec-kitty agent tasks list-dependents WP01 --mission <slug>
```

For machine-readable output:

```bash
spec-kitty agent tasks list-dependents WP01 --mission <slug> --json
```

If the rejected WP has downstream dependents, those WPs will need a rebase once
the rejection is addressed. Include a rebase warning in your feedback so the
implementing agent and any agents working on dependent WPs are aware.

You can also check the full mission status board for broader context:

```bash
spec-kitty agent tasks status --mission <slug>
```

## Review Precedence Rules

1. **Acceptance criteria are the primary gate** -- a WP meeting all criteria passes even if the reviewer would have done it differently.
2. **The review prompt is the source of truth** -- it contains the specific checks, criteria, and doctrine context for this WP.
3. **One clear verdict per review** -- approve or reject, nothing in between.
4. **The reviewer does not implement fixes** -- feedback must be actionable by the original implementing agent.

## Troubleshooting

- **No WPs found**: Confirm at least one WP is in `for_review` using `spec-kitty agent tasks list-tasks --lane for_review --mission <slug>`.
- **Mission resolution is ambiguous**: Add `--mission <slug>` to the command in repos with more than one tracked mission.
- **Wrong workspace**: Open the WP worktree that contains the implementation.
- **Need more context**: Check the spec and plan for the mission before completing review.
- **Governance context empty**: The charter may not be configured yet. Review can still proceed using the acceptance criteria in the review prompt.

---

## Command Reference

- [Slash Commands](../../../api/slash-commands.md) - All `/spec-kitty.*` commands
- [Agent Subcommands](../../../api/agent-subcommands.md) - Workflow commands

## See Also

- [Implement a work package](implement-work-package.md) - Required before review
- [Accept and Merge](accept-and-merge.md) - After all WPs pass review

## Background

- [Kanban Workflow](../../../architecture/kanban-workflow.md) - Lane transitions explained
- [Multi-Agent Orchestration](../../../architecture/multi-agent-orchestration.md) - Agent handoffs

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
