---
title: Use Spec Kitty in Amazon Q CLI
description: 'How to use Spec Kitty in Amazon Q CLI (supported tier), retained as legacy alongside the Kiro rebrand: prerequisites, prompt install, and the command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Amazon Q CLI

> **Tier:** supported. Retained as legacy alongside the Kiro rebrand per `CLAUDE.md`.
> **Citation (accessed 2026-05-21):** <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai q
  ```
  *(The configuration key is `q`; the on-disk directory is `.amazonq/`.)*
- **Amazon Q Developer CLI installed and signed in.** Follow the [Amazon Q Developer User Guide](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Amazon Q CLI uses the prompt-file mechanism. Spec Kitty installs:

- **Directory:** `.amazonq/prompts/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Amazon Q CLI, the prompt files are surfaced as slash commands:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

If your installed Amazon Q version uses a different prompt-invocation convention, consult the host docs at <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/> for the current syntax.

## Worked example

1. From your project root, launch Amazon Q CLI (`q chat`).
2. At the prompt, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` prompts do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.amazonq/prompts/` from the canonical source templates. Restart Amazon Q CLI.

- **Profile not loading.**
  Run inside Amazon Q:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Amazon Q

Authoritative documentation: <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/> (accessed 2026-05-21).
