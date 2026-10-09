---
title: Use Spec Kitty in Codex CLI
description: 'How to use Spec Kitty in Codex CLI, the first-class harness with the heaviest agent skills integration: prerequisites, skill install, and the command workflow.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Codex CLI

> **Tier:** first_class — heaviest agent skills integration.
> **Citation (accessed 2026-05-21):** <https://github.com/openai/codex>

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai codex
  ```
- **Codex CLI installed and authenticated.** Follow the [openai/codex README](https://github.com/openai/codex) for installation and login.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Codex CLI consumes Spec Kitty as **agent skills** (not slash commands). Spec Kitty installs:

- **Directory:** `.agents/skills/spec-kitty.<command>/`
- **Files:** one `SKILL.md` per command (`spec-kitty.specify/SKILL.md`, `spec-kitty.plan/SKILL.md`, `spec-kitty.tasks/SKILL.md`, `spec-kitty.implement/SKILL.md`, etc.).
- **Manifest:** `.kittify/command-skills-manifest.json` records which agents reference each skill package.

Codex reads the skill tree directly; the same tree is shared with Mistral Vibe via `.vibe/config.toml` `skill_paths`.

## Canonical invocation

Inside the Codex CLI, skills are invoked with the `$` prefix:

```
$spec-kitty.specify "<one-line mission description>"
$spec-kitty.plan
$spec-kitty.tasks
$spec-kitty.implement WP01
```

This is the key difference from slash-command hosts — do not type `/spec-kitty.*` in Codex; use `$spec-kitty.*`.

## Worked example

1. From your project root, start Codex (`codex`).
2. At the prompt, type:
   ```
   $spec-kitty.specify "a hello world page"
   ```
3. Spec Kitty's interview prompts appear — answer them inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

## Troubleshooting

- **`$spec-kitty.*` skills do not appear.**
  Run `spec-kitty agent config sync` from the repo root. This regenerates `.agents/skills/spec-kitty.*/SKILL.md` from the canonical source templates and re-registers the manifest. Restart Codex.

- **Profile not loading (researcher / reviewer roles do not adopt).**
  At the Codex prompt, run:
  ```
  /spk-charter-profile-load researcher-robbie
  ```
  Use the profile id named in the work-package frontmatter (`agent_profile:`).

## Where to learn more about Codex

Authoritative documentation: <https://github.com/openai/codex> (accessed 2026-05-21). Consult the repository README for the latest agent skills syntax and version notes.
