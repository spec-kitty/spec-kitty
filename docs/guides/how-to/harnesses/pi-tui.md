---
title: Use Spec Kitty in Pi TUI
description: 'How to use Spec Kitty in Pi TUI (partial tier): command-skill packages install in 3.2, but real-session smoke evidence is not yet recorded.'
doc_status: active
updated: '2026-06-03'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Pi TUI

> **Tier:** **partial** — Spec Kitty installs Pi command-skill packages in 3.2, but real-session smoke evidence is not yet recorded.
> **Citation (accessed 2026-05-21):** <https://pi.dev/docs/latest/skills>

## Partial-tier note

Pi TUI is classified `partial` in the 3.2 [support matrix](../../../api/supported-harnesses.md) because:

1. The Spec Kitty installer produces command-skill packages under `.agents/skills/spec-kitty.*/SKILL.md`.
2. Pi's current skills documentation says project `.agents/skills/` directories are discovered, and that skills register as `/skill:<name>` commands.
3. A real-session smoke test for the complete Spec Kitty command set has not yet been recorded, so the row remains `partial` instead of `supported`.

Promotion to `supported` requires at least one documented smoke test against a real Pi session; the full rule is maintained in `docs/development/3-2-harness-research-method.md` §6.

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai pi
  ```
- **Pi installed.** Follow the Pi documentation at <https://pi.dev/docs/latest> for the current install path and authentication flow.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Pi consumes Spec Kitty as agent skills. Spec Kitty installs:

- **Directory:** `.agents/skills/spec-kitty.<command>/`
- **Files:** one `SKILL.md` per command (`spec-kitty.specify/SKILL.md`, `spec-kitty.plan/SKILL.md`, `spec-kitty.tasks/SKILL.md`, `spec-kitty.implement/SKILL.md`, etc.).
- **Manifest:** `.kittify/command-skills-manifest.json` records that Pi references each command-skill package.
- **Runtime ignore entry:** `.pi/` is added to `.gitignore` when Pi is configured.

The shared `.agents/skills/` tree can be co-owned by Codex, Vibe, Pi, and Letta. Do not copy or edit the generated `SKILL.md` files manually; use `spec-kitty agent config sync` or `spec-kitty upgrade` to refresh them.

## Canonical invocation

Pi's skills documentation says skills register as `/skill:<name>` commands. For Spec Kitty command-skill packages, use that form:

```text
/skill:spec-kitty.specify "<one-line mission description>"
/skill:spec-kitty.plan
/skill:spec-kitty.tasks
/skill:spec-kitty.implement WP01
```

## Worked example

Until full smoke evidence lands, treat Pi TUI as a **partial-tier** host and verify command behavior on a low-risk mission first:

1. From your project root, run Pi.
2. At the prompt, type:
   ```text
   /skill:spec-kitty.specify "a hello world page"
   ```
3. Answer the Spec Kitty interview prompts inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

If Pi does not expose the command in your installed version, the artifacts remain harness-agnostic:

1. Drive the mission lifecycle through another configured harness (for example, Claude Code: `/spec-kitty.specify "a hello world page"`).
2. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md` on disk.
3. Open Pi TUI against the same project directory and inspect the `kitty-specs/` tree as plain files.

## Troubleshooting

- **No `/spec-kitty.*` commands inside Pi TUI.**
  Expected — Pi is a skill host, not a slash-command host for Spec Kitty. Use `/skill:spec-kitty.<command>` and confirm `.agents/skills/spec-kitty.*/SKILL.md` exists.

- **Profile not loading.**
  The `/spk-charter-profile-load` workflow assumes a slash-command host. If your Pi build does not expose equivalent profile loading, use the helper from your other configured harness and reuse the same `kitty-specs/<mission>/` tree.

## Where to learn more about Pi TUI

Authoritative documentation: <https://pi.dev/docs/latest/skills> (accessed 2026-05-21). The matrix row in [`docs/api/supported-harnesses.md`](../../../api/supported-harnesses.md) remains the promotion tracker.
