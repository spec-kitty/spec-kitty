---
title: Use Spec Kitty in Cursor
description: 'How to use Spec Kitty in Cursor (supported tier): prerequisites, command install, and the Spec Kitty slash-command workflow inside the editor.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Cursor

> **Tier:** supported.
> **Citation (accessed 2026-05-21):** <https://cursor.com/docs>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai cursor
  ```
- **Cursor installed and signed in.** Follow the [Cursor documentation](https://cursor.com/docs) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Cursor uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.cursor/commands/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Cursor's agent chat, invoke as:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

## Worked example

1. Open your project in Cursor.
2. Open the agent chat panel and type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` commands do not show in the Cursor command list.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.cursor/commands/` from the canonical source templates. Reload Cursor (`Cmd-Shift-P → Reload Window`) afterwards.

- **Profile not loading.**
  In the chat, run:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Cursor

Authoritative documentation: <https://cursor.com/docs> (accessed 2026-05-21).
