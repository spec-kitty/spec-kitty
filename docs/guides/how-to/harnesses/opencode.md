---
title: Use Spec Kitty in OpenCode
description: 'How to use Spec Kitty in OpenCode (supported tier): prerequisites, command install, and the Spec Kitty slash-command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in OpenCode

> **Tier:** supported.
> **Citation (accessed 2026-05-21):** <https://opencode.ai/docs>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai opencode
  ```
- **OpenCode installed and configured.** Follow the [OpenCode documentation](https://opencode.ai/docs) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), OpenCode uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.opencode/command/` *(note: singular `command`, not `commands`)*
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside OpenCode, slash commands are invoked as:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

## Worked example

1. From your project root, launch OpenCode.
2. At the prompt, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` commands do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.opencode/command/` from the canonical source templates. Restart OpenCode.

- **Profile not loading.**
  Run inside OpenCode:
  ```
  /ad-hoc-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about OpenCode

Authoritative documentation: <https://opencode.ai/docs> (accessed 2026-05-21). Consult the host docs for the latest slash-command discovery rules and version notes.
