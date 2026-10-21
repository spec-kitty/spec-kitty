---
title: Use Spec Kitty in Letta Code
description: 'How to use Spec Kitty in Letta Code (partial tier): command-skill packages install in 3.2, but real-session smoke evidence is not yet recorded.'
doc_status: active
updated: '2026-10-21'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Use Spec Kitty in Letta Code

> **Tier:** **partial** — Spec Kitty installs Letta Code command-skill packages in 3.2, but real-session smoke evidence is not yet recorded.
> **Citation (accessed 2026-06-02):** <https://docs.letta.com/letta-code/skills/>

## Partial-tier note

Letta Code is classified `partial` in the 3.2 [support matrix](../../../api/supported-harnesses.md) because:

1. The Spec Kitty installer produces command-skill packages under `.agents/skills/spec-kitty-*/SKILL.md`.
2. Letta Code's skills documentation says `.agents/skills/` is the preferred project-scoped skills location.
3. A real-session smoke test for the complete Spec Kitty command set has not yet been recorded, so the row remains `partial` instead of `supported`.

Promotion to `supported` requires at least one documented smoke test against a real Letta Code session; the full rule is maintained in `docs/development/3-2-harness-research-method.md` §6.

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai letta
  ```
- **Letta Code installed and authenticated.** Follow the Letta Code documentation at <https://docs.letta.com/letta-code> for the current install path and authentication flow.

## Where Spec Kitty installs files

Per the [supported-harnesses matrix](../../../api/supported-harnesses.md), Letta Code consumes Spec Kitty as agent skills. Spec Kitty installs:

- **Directory:** `.agents/skills/spec-kitty-<command>/`
- **Files:** one `SKILL.md` per command (`spec-kitty-specify/SKILL.md`, `spec-kitty-plan/SKILL.md`, `spec-kitty-tasks/SKILL.md`, `spec-kitty-implement/SKILL.md`, etc.).
- **Manifest:** `.kittify/command-skills-manifest.json` records that Letta references each command-skill package.
- **Runtime ignore entry:** `.letta/` is added to `.gitignore` when Letta is configured.

The shared `.agents/skills/` tree can be co-owned by Codex, Vibe, Pi, Letta, and Antigravity. Do not copy or edit the generated `SKILL.md` files manually; use `spec-kitty agent config sync` or `spec-kitty upgrade` to refresh them.

Before the 4.0.0rc8 release these folders were named `spec-kitty.<command>`. The Agent Skills specification does not allow a dot in a skill name, so `spec-kitty upgrade` renames them; see [Command skills renamed for the Agent Skills specification](../../../migrations/command-skill-hyphen-names.md).

## Canonical invocation

Letta Code can load a skill directly with slash syntax. For Spec Kitty command-skill packages, use the skill name as the slash command:

```text
/spec-kitty-specify "a hello world page"
/spec-kitty-plan
/spec-kitty-tasks
/spec-kitty-implement WP01
```

Use `/skills` inside Letta Code to browse discovered skills. If the Spec Kitty skills do not appear after changing files, ask Letta to refresh skills or restart the session.

## Worked example

Until full smoke evidence lands, treat Letta Code as a **partial-tier** host and verify command behavior on a low-risk mission first:

1. From your project root, run Letta Code.
2. At the prompt, type:
   ```text
   /spec-kitty-specify "a hello world page"
   ```
3. Answer the Spec Kitty interview prompts inline.
4. When asked for a kebab-case slug, supply something short, e.g. `hello-world-page`.
5. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md`.

If Letta does not expose the command in your installed version, the artifacts remain harness-agnostic:

1. Drive the mission lifecycle through another configured harness.
2. The mission spec lands at `kitty-specs/hello-world-page-<mid8>/spec.md` on disk.
3. Open Letta Code against the same project directory and inspect the `kitty-specs/` tree as plain files.

## Troubleshooting

- **No `/spec-kitty-*` skills inside Letta Code.**
  Confirm `.agents/skills/spec-kitty-*/SKILL.md` exists, run `spec-kitty agent config sync`, then restart Letta Code or refresh skills.

- **Skill list shows stale content.**
  Letta caches the discovered skill list in session memory. Refresh skills or restart the session after running `spec-kitty upgrade`.

- **Slash-command hosts work but Letta does not.**
  Letta is a skill host for Spec Kitty. It reads project-local skills from `.agents/skills/`; it does not use the user-global slash-command directories such as `~/.claude/commands/`.

## Where to learn more about Letta Code

Authoritative documentation: <https://docs.letta.com/letta-code/skills/> (accessed 2026-06-02). The matrix row in [`docs/api/supported-harnesses.md`](../../../api/supported-harnesses.md) remains the promotion tracker.
