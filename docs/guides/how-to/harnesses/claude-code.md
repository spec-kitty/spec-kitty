---
title: Use Spec Kitty in Claude Code
description: 'How to use Spec Kitty in Claude Code, the first-class integration-tested reference harness: prerequisites, command install, and the slash-command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Claude Code

> **Tier:** first_class — reference harness, integration-tested.
> **Citation (accessed 2026-05-21):** <https://docs.claude.com/en/docs/claude-code/overview>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai claude
  ```
- **Claude Code installed and signed in.** Follow the [Claude Code overview](https://docs.claude.com/en/docs/claude-code/overview) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Claude Code uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.claude/commands/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`, plus the `spec-kitty.tasks-*` helpers.

Each file is a Claude Code slash-command definition; the agent surfaces them as `/spec-kitty.<command>` in chat.

## Canonical invocation

Slash-command syntax inside the Claude Code TUI:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

The command name is the filename stem under `.claude/commands/`. Arguments after the command name are forwarded as a single string.

## Worked example

1. From your project root, start Claude Code (`claude`).
2. In the chat, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inside the chat.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md` and the kanban moves the mission into the `planned` lane.

## Troubleshooting

- **`/spec-kitty.*` commands do not show in Claude Code.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.claude/commands/` from the canonical source templates (see `CLAUDE.md`, "Template Source Location"). Restart Claude Code afterwards.

- **Profile not loading (researcher / reviewer roles do not adopt).**
  Inside Claude Code, run:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Replace the profile id with the one named in the work-package frontmatter (`agent_profile:`).

## Where to learn more about Claude Code

Authoritative documentation: <https://docs.claude.com/en/docs/claude-code/overview> (accessed 2026-05-21).
