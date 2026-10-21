---
title: 'Migration: Command Skills Renamed for the Agent Skills Specification'
description: 'Upgrade to the spec-kitty-<command> skill names: new invocations per harness, kept edited copies, doctor skills remedies and the Antigravity workflows archive.'
doc_status: active
type: how-to
audience: docs/context/audience/external/project-owner.md
updated: '2026-10-21'
related:
- docs/adr/4.x/2026-10-20-1-command-skills-use-spec-conformant-names.md
- docs/api/supported-agents.md
- docs/guides/how-to/installation/upgrade-project.md
- docs/changelog/CHANGELOG.md
---

# Command skills renamed for the Agent Skills specification

Use this page when your project uses Spec Kitty through an Agent Skills harness (Codex CLI,
Mistral Vibe, Pi, Letta Code or Google Antigravity) and you upgrade to a release that names the
command skills `spec-kitty-<command>`.

## What changed

Spec Kitty used to generate its command skills as `.agents/skills/spec-kitty.<command>/`. The
Agent Skills specification allows only lowercase letters, digits and hyphens in a skill name,
so several harnesses that read `.agents/skills/` dropped those skills without a message. The
skills are now `.agents/skills/spec-kitty-<command>/`, and their frontmatter carries only
specification fields.

Google Antigravity stopped reading `.agent/workflows/` on 2026-10-19. Spec Kitty now delivers
Antigravity's commands as the same `.agents/skills/spec-kitty-<command>/` skills.

The 12 slash-command agents (Claude Code, Copilot, Gemini and the others) are not affected:
their command files and `/spec-kitty.<command>` invocations stay as they were.

## How to invoke a command now

| Harness | Before | Now |
| --- | --- | --- |
| Codex CLI | `$spec-kitty.specify` | `$spec-kitty-specify` |
| Pi | `/skill:spec-kitty.specify` | `/skill:spec-kitty-specify` |
| Mistral Vibe, Letta Code | `/spec-kitty.specify` | `/spec-kitty-specify` |
| Google Antigravity | `/spec-kitty.specify` (workflow) | `/spec-kitty-specify` (skill) |

## Upgrade your project

1. Run the upgrade in each clone of the project (the rename is recorded per clone, because
   `.agents/skills/` is not committed):

   ```bash
   spec-kitty upgrade
   ```

   The output lists the new invocation names when the rename did something.

2. Check what was left behind:

   ```bash
   spec-kitty doctor skills
   ```

3. Restart your harness, or refresh its skills, so it picks up the new names.

## What happens to your existing dotted skills

- **Unedited copies** are removed and replaced by the new skills. A folder is removed only when
  it is empty afterwards.
- **Copies you edited** are kept where they are, with a warning. Spec Kitty no longer manages
  them. Copy your edits to wherever you want them, then delete the old folder.
- **Your own folder at a new name** (for example a `spec-kitty-plan/` you wrote yourself) is
  not overwritten. That one command skill is skipped with a warning; the others install.

## `doctor skills` messages and what to do

| Message | Exit code | What to do |
| --- | --- | --- |
| `Legacy dotted command skills (no longer managed): <path> — remove it when you no longer need your edits` | 0 when nothing else is wrong | Keep it as long as you need your edits, then delete the folder. |
| `Legacy dotted command skill (Spec Kitty's unmodified rendering): <path> — run spec-kitty doctor skills --fix to retire it` | 1 | Run `spec-kitty doctor skills --fix`. |
| `Legacy dotted command skill (still recorded by Spec Kitty): <path> — run spec-kitty doctor skills --fix to retire it` | 1 | Run `spec-kitty doctor skills --fix`. An unedited copy is removed; an edited one is kept and then reported as no longer managed. |
| `Your own folder blocks command skill <path> — rename or remove it, then run spec-kitty doctor skills --fix` | 1 | Move your folder, then run `spec-kitty doctor skills --fix`. |

The "still recorded" message means the manifest has not been migrated yet; the check fails
until `spec-kitty doctor skills --fix` (or `spec-kitty upgrade`) retires the entry. `doctor skills` never
deletes a path it lists. `doctor skills --json` reports these paths under the `legacy` and
`collisions` keys.

## Antigravity workflow files

- **In the project.** `spec-kitty upgrade` moves each Spec Kitty-generated
  `.agent/workflows/spec-kitty.<command>.md` file into its own backup folder:

  ```text
  .kittify/backups/antigravity-workflows/.backup-<timestamp>/.agent/workflows/spec-kitty.<command>.md
  ```

  Files Spec Kitty did not generate, and the `.agent/` folders themselves, stay where they are.
  When Antigravity is configured, the same step installs its command skills.
- **In your home folder.** The CLI removes the `~/.agent/workflows/spec-kitty.*.md` files it
  wrote, when they are unedited. Edited files and the folder stay.

## Home-folder command files

The CLI now writes slash-command files into your home folder only for the slash-command agents
configured in the current project. Outside a project it writes nothing.
`spec-kitty agent config add <agent>` writes that agent's files straight away.

## Downgrading

An older Spec Kitty CLI cannot read the command-skill manifest this release writes. If you go
back to an older CLI, or a teammate on an older CLI pulls the manifest where your project commits it, that CLI
refuses the manifest. Upgrade the older CLI instead.

## Known follow-ups

- In a project that combines a slash-command agent with an Agent Skills reader in the same
  harness (for example codex and copilot), each command can show twice. #6471 tracks this.
- The global skills writer still writes skill roots for agents the project does not use. #3048
  tracks this.
