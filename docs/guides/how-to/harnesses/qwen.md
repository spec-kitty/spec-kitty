---
title: Use Spec Kitty in Qwen Code
description: 'How to use Spec Kitty in Qwen Code (supported tier) via TOML commands: prerequisites, command install, and the Spec Kitty workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Qwen Code

> **Tier:** supported.
> **Citation (accessed 2026-05-21):** <https://github.com/QwenLM/qwen-code>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai qwen
  ```
- **Qwen Code installed and authenticated.** Follow the [QwenLM/qwen-code README](https://github.com/QwenLM/qwen-code) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Qwen Code uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.qwen/commands/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Qwen Code, slash commands are invoked as:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

## Worked example

1. From your project root, launch Qwen Code.
2. At the prompt, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` commands do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.qwen/commands/` from the canonical source templates. Restart Qwen Code.

- **Profile not loading.**
  Run inside Qwen Code:
  ```
  /ad-hoc-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Qwen Code

Authoritative documentation: <https://github.com/QwenLM/qwen-code> (accessed 2026-05-21).
