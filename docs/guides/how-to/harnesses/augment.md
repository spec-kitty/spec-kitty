---
title: Use Spec Kitty in Augment Code (Auggie)
description: 'How to use Spec Kitty in Augment Code (Auggie, supported tier): prerequisites, command install, and the Spec Kitty slash-command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Augment Code (Auggie)

> **Tier:** supported.
> **Citation (accessed 2026-05-21):** <https://docs.augmentcode.com/auggie/overview>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai auggie
  ```
  *(The configuration key is `auggie`; the on-disk directory is `.augment/`.)*
- **Augment Code installed and signed in.** Follow the [Auggie overview](https://docs.augmentcode.com/auggie/overview) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Augment Code uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.augment/commands/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Augment Code's chat, slash commands are invoked as:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

## Worked example

1. Open your project in Augment Code.
2. In the agent chat, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` commands do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.augment/commands/` from the canonical source templates. Restart Augment Code.

- **Profile not loading.**
  Run inside Augment Code:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Augment Code

Authoritative documentation: <https://docs.augmentcode.com/auggie/overview> (accessed 2026-05-21).
