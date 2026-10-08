---
title: Use Spec Kitty in Google Gemini CLI
description: 'How to use Spec Kitty in Google Gemini CLI (supported tier) via TOML commands: prerequisites, command install, and the Spec Kitty workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Google Gemini CLI

> **Tier:** supported.
> **Citation (accessed 2026-05-21):** <https://github.com/google-gemini/gemini-cli>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai gemini
  ```
- **Gemini CLI installed and authenticated.** Follow the [google-gemini/gemini-cli README](https://github.com/google-gemini/gemini-cli) for installation and login.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Gemini CLI uses the slash-command mechanism. Spec Kitty installs:

- **Directory:** `.gemini/commands/`
- **Files:** `spec-kitty.specify.md`, `spec-kitty.plan.md`, `spec-kitty.tasks.md`, `spec-kitty.implement.md`, `spec-kitty.review.md`, `spec-kitty.accept.md`, `spec-kitty.merge.md`, `spec-kitty.status.md`, `spec-kitty.charter.md`, `spec-kitty.analyze.md`, `spec-kitty.research.md`.

## Canonical invocation

Inside the Gemini CLI, slash commands are invoked as:

```
/spec-kitty.specify "<one-line mission description>"
/spec-kitty.plan
/spec-kitty.tasks
/spec-kitty.implement WP01
```

## Worked example

1. From your project root, launch Gemini CLI (`gemini`).
2. At the prompt, type:
   ```
   /spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`/spec-kitty.*` commands do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This rewrites `.gemini/commands/` from the canonical source templates. Restart Gemini CLI.

- **Profile not loading.**
  Run inside Gemini CLI:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id from the work-package frontmatter.

## Where to learn more about Gemini CLI

Authoritative documentation: <https://github.com/google-gemini/gemini-cli> (accessed 2026-05-21).
