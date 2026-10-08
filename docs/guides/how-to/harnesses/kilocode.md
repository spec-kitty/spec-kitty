---
title: Use Spec Kitty in Kilo Code
description: 'How to use Spec Kitty in Kilo Code (supported tier) via the workflow mechanism: prerequisites, workflow install, and the Spec Kitty command flow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Kilo Code

> **Tier:** supported. Workflow mechanism.
> **Citation (accessed 2026-05-21):** <https://kilocode.ai/docs>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai kilocode
  ```
- **Kilo Code installed and configured.** Follow the [Kilo Code documentation](https://kilocode.ai/docs) for installation and authentication.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Kilo Code uses the **workflow** mechanism. Spec Kitty installs:

- **Directory:** `.kilocode/workflows/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Kilo Code, the workflow files are surfaced as slash commands:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

If your installed Kilo Code version uses a different workflow-invocation convention, consult the host docs at <https://kilocode.ai/docs> for the current syntax.

## Worked example

1. Open your project in Kilo Code.
2. At the agent prompt, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` workflows do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.kilocode/workflows/` from the canonical source templates. Restart Kilo Code.

- **Profile not loading.**
  Run inside Kilo Code:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Kilo Code

Authoritative documentation: <https://kilocode.ai/docs> (accessed 2026-05-21).
