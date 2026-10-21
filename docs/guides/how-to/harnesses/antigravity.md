---
title: Use Spec Kitty in Google Antigravity
description: 'Use Spec Kitty in Google Antigravity through the shared .agents/skills/ command skills: install, invocation, partial-tier status and the archived workflow files.'
doc_status: active
updated: '2026-10-21'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/installation/install-spec-kitty.md
- docs/migrations/command-skill-hyphen-names.md
---
# Use Spec Kitty in Google Antigravity

> **Tier:** **partial** — Spec Kitty installs Antigravity's commands as Agent Skills, but
> loading them in a live Antigravity session has not been smoke-tested end-to-end.

## Prerequisites

- **Spec Kitty CLI installed.** See [Install Spec Kitty](../installation/install-spec-kitty.md).
- **Project initialized for this harness:**
  ```bash
  spec-kitty init --ai antigravity
  ```
  To add Antigravity to an existing project, run `spec-kitty agent config add antigravity`.
- **Google Antigravity installed and configured.** Follow the official
  [Antigravity documentation](https://www.antigravity.google/docs/overview).

## Where Spec Kitty installs files

Google Antigravity stopped reading `.agent/workflows/` on 2026-10-19 and reads Agent Skills
from the shared `.agents/skills/` root. Spec Kitty installs:

- **Directory:** `.agents/skills/spec-kitty-<command>/`
- **Files:** one `SKILL.md` per command (`spec-kitty-specify/SKILL.md`,
  `spec-kitty-plan/SKILL.md`, `spec-kitty-tasks/SKILL.md`, `spec-kitty-implement/SKILL.md`,
  etc.).
- **Manifest:** `.kittify/command-skills-manifest.json` records that Antigravity references each
  command-skill package.

The shared `.agents/skills/` tree can be co-owned by Codex, Vibe, Pi, Letta, and Antigravity.
Do not copy or edit the generated `SKILL.md` files manually; use `spec-kitty agent config sync`
or `spec-kitty upgrade` to refresh them.

Spec Kitty no longer writes any file into `.agent/workflows/`, in the project or in your home
folder.

## Canonical invocation

Invoke a command skill by its name:

```text
/spec-kitty-specify "<one-line mission description>"
/spec-kitty-plan
/spec-kitty-tasks
/spec-kitty-implement WP01
```

This invocation remains provisional until a live Antigravity smoke test is recorded.

## Upgrading from the workflow files

`spec-kitty upgrade` moves each Spec Kitty-generated `.agent/workflows/spec-kitty.<command>.md`
file into its own backup folder and installs the command skills:

```text
.kittify/backups/antigravity-workflows/.backup-<timestamp>/.agent/workflows/spec-kitty.<command>.md
```

Files Spec Kitty did not generate, and the `.agent/` folders, stay where they are. The CLI also
removes the unedited `spec-kitty.*.md` files it once wrote into `~/.agent/workflows/`. See
[Command skills renamed for the Agent Skills specification](../../../migrations/command-skill-hyphen-names.md).

## Verification status

Do not promote Antigravity to `supported` until a maintainer with Antigravity installed
records:

- The Antigravity version used.
- That Antigravity lists the `spec-kitty-*` skills from `.agents/skills/`.
- Successful launch of at least one `spec-kitty-<command>` skill from a real Antigravity
  session.

## Troubleshooting

- **The `spec-kitty-*` skills do not appear.**
  Confirm `.agents/skills/spec-kitty-specify/SKILL.md` exists, run
  `spec-kitty agent config sync` from the repo root, then restart Antigravity.

- **`spec-kitty doctor skills` names a folder that blocks a command skill.**
  Your own folder sits at a `spec-kitty-<command>/` path. Rename or remove it, then run
  `spec-kitty doctor skills --fix`.

- **The `agent` command is present but help mentions Cursor.**
  That is not Antigravity. Install or locate Antigravity before recording verification
  evidence.
