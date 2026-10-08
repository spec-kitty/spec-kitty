---
title: Use Spec Kitty in GitHub Copilot
description: 'How to use Spec Kitty in GitHub Copilot (supported tier) via the prompt-file mechanism: prerequisites, prompt install, and the Spec Kitty command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in GitHub Copilot

> **Tier:** supported. Prompt-file mechanism.
> **Citation (accessed 2026-05-21):** <https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai copilot
  ```
  *(The configuration key is `copilot`; the on-disk directory is `.github/prompts/`.)*
- **GitHub Copilot enabled in your editor** (VS Code, JetBrains, etc.) and signed in. Follow GitHub's [Copilot customization docs](https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot) for setup.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), GitHub Copilot uses the prompt-file mechanism. Spec Kitty installs:

- **Directory:** `.github/prompts/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside Copilot Chat, prompt files are invoked with the slash-command convention:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

Exact discovery rules depend on your editor and Copilot version. If `/spec-kitty.*` does not autocomplete, consult the host docs at <https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot> for the current prompt-file invocation syntax.

## Worked example

1. Open your project in an editor with Copilot enabled.
2. In Copilot Chat, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` prompts do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.github/prompts/` from the canonical source templates. Reload your editor.

- **Profile not loading.**
  In Copilot Chat, run:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about GitHub Copilot

Authoritative documentation: <https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot> (accessed 2026-05-21).
