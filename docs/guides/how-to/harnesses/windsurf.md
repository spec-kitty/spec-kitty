---
title: Use Spec Kitty in Windsurf
description: 'How to use Spec Kitty in Windsurf (supported tier) via the workflow mechanism: prerequisites, workflow install, and the Spec Kitty command flow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Windsurf

> **Tier:** supported. Workflow mechanism.
> **Citation (accessed 2026-05-21):** <https://docs.windsurf.com/windsurf/cascade/workflows>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai windsurf
  ```
- **Windsurf installed and signed in.** Follow the [Windsurf workflow docs](https://docs.windsurf.com/windsurf/cascade/workflows) for installation and configuration.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Windsurf uses the **workflow** mechanism (Cascade workflows). Spec Kitty installs:

- **Directory:** `.windsurf/workflows/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Windsurf Cascade, the workflow files are surfaced as slash commands:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

Cascade's workflow-discovery rules may evolve. If `/spec-kitty.*` does not autocomplete, consult <https://docs.windsurf.com/windsurf/cascade/workflows> for the current invocation syntax.

## Worked example

1. Open your project in Windsurf.
2. In the Cascade chat, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` workflows do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.windsurf/workflows/` from the canonical source templates. Restart Windsurf.

- **Profile not loading.**
  In Cascade chat, run:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Windsurf

Authoritative documentation: <https://docs.windsurf.com/windsurf/cascade/workflows> (accessed 2026-05-21).
