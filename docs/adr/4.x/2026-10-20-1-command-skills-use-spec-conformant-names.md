---
title: 'ADR: command skills use spec-conformant spec-kitty-<command> names, and Antigravity gets its commands as skills'
description: 'Command skills are renamed spec-kitty-<command> by one naming authority, Antigravity becomes a command-skill agent, and the home writer is scoped to configured agents.'
status: Accepted
date: '2026-10-20'
updated: '2026-10-21'
---

**Status:** Accepted (2026-10-20).

**Date:** 2026-10-20

**Deciders:** Stijn Dejongh (operator).

**Technical Story:** #6475 (command skills named `spec-kitty.<command>` are dropped by
strict Agent Skills readers), #6470 (Google Antigravity stopped reading `.agent/workflows`
on 2026-10-19). Mission `command-skill-names-and-antigravity-01M5DBWT`. Follow-ups: #6471
(slash-command file names), #3048 (global skills fan-out).

**Reader:** a maintainer working on the command-skill installer, the upgrade migrations, the
home-folder command writer, or adding an agent harness.

**Amends:** ADR [2026-04-07-1](../3.x/2026-04-07-1-global-slash-command-installation.md)
(global slash command installation). Its "all agents at every CLI startup" decision is replaced
by "configured slash-command agents of the current project", and its `antigravity` row
(`~/.agent/workflows/`) is removed. The rest of that ADR stands.

---

## Context and Problem Statement

Spec Kitty delivers its workflow commands to Agent Skills harnesses (Codex, Vibe, Pi, Letta)
as generated skills under the shared project root `.agents/skills/`. Each skill was a folder
named `spec-kitty.<command>` with `name: spec-kitty.<command>` in its `SKILL.md`.

1. **The dot is not allowed (#6475).** The Agent Skills specification allows only
   `[a-z0-9-]` in a skill `name`, and the folder name must equal it. VS Code/Copilot, Cursor
   and OpenCode read `.agents/skills/` too, and drop the dotted skills without telling the
   user. The reference validator `skills-ref` rejects them. The generated frontmatter also
   carried Claude-only keys (`user-invocable`, `argument-hint`) at the top level, which strict
   readers reject in a shared root.
2. **Antigravity's surface is dead (#6470).** Spec Kitty wrote Antigravity's commands only as
   workflow files in `.agent/workflows/` (project, before 3.1.2) and `~/.agent/workflows/`
   (home folder, at every CLI start). Antigravity stopped reading that folder on 2026-10-19
   and reads Agent Skills from `.agents/skills/`, so its users had no working command.
3. **The home folder was sprayed.** ADR 2026-04-07-1 writes command files for every
   slash-command agent at every CLI start, configured or not, including outside any project.

## Decision Drivers

- Every command loads in every harness that reads the shared root, with no silent drop.
- No mutating flow deletes or rewrites a file Spec Kitty cannot prove it owns (charter: User
  Customization Preservation).
- One authority per concern, so the name and the frontmatter cannot drift between producers.
- The 12 slash-command agents' command files and their `/spec-kitty.<command>` invocations do
  not change in this decision (#6471 owns that).

## Decision

### 1. The name is `spec-kitty-<command>`, produced by one authority

The canonical command-skill name is `spec-kitty-<command>`, and its path is
`.agents/skills/spec-kitty-<command>/SKILL.md`. `src/specify_cli/skills/command_skill_names.py`
is the only module that composes the name, the path and the invocation tokens; it is a
dependency-free leaf, and `tests/architectural/test_command_skill_name_authority.py` pins that
no other module composes them.

- **Explicit command set, never a prefix.** `spec-kitty-` is shared with shipped charter skills
  (for example `spec-kitty-implement-review`), so a path is recognised only by exact match
  against the canonical command set and the manifest. A user's own `spec-kitty-mine/` skill is
  never reported or touched.
- **Uniqueness is a test-time guarantee.** A test checks every canonical name against the
  shipped charter skills, the built-in pack skills and the retired skill names.
- **Clean break.** No alias folder keeps the dotted names installed. The dotted names are
  recorded once, as legacy, in the naming authority (not in the existing retired-skill sets).

### 2. Invocations are rewritten at render time; slash files are unchanged

Pack sources keep `/spec-kitty.<command>`, which is correct for the slash-command agents. The
command-skill renderer rewrites `/spec-kitty.<command>`, `$spec-kitty.<command>` and
`/skill:spec-kitty.<command>` tokens of canonical commands to the skill name, keeping the sigil.
The rewrite is agent-independent, so one rendered body serves every command-skill agent. File
names (`spec-kitty.plan.md`), URLs and `spec-kitty.ai` are left alone.

How a user invokes a command skill:

| Harness | Invocation |
| --- | --- |
| Codex CLI | `$spec-kitty-<command>` |
| Pi | `/skill:spec-kitty-<command>` |
| Vibe, Letta, Antigravity | `/spec-kitty-<command>` |
| The 12 slash-command agents | `/spec-kitty.<command>` (unchanged) |

A pack skill expansion target `builtin:spec-kitty.<command>` stays accepted as input and
resolves to `spec-kitty-<command>`; error messages list the canonical names.

### 3. Every repair path applies one legacy rule

The installer owns the rule, and every installing path runs it: `init`, `upgrade`,
`agent config add`, `doctor skills --fix` and the tool-surface repair.

- **Recorded dotted entry.** The file is deleted when its bytes equal the recorded hash, or
  equal today's render under the old dotted name. Its folder is removed only when it is then
  empty. Edited bytes, a directory, a link or a symlinked parent are kept with a warning,
  and the manifest entry is dropped.
- **Unrecorded dotted skill (operator ruling 2026-10-21).** A clone can pull an
  already-migrated manifest that no longer records its local dotted folders. An unrecorded
  `spec-kitty.<command>/SKILL.md` that is byte-identical to Spec Kitty's dotted render is
  treated as owned and retired. Anything else is kept with a warning.
- **User content at a canonical path (operator ruling 2026-10-20).** A user file with other
  bytes at `spec-kitty-<command>/SKILL.md`, or a non-empty `spec-kitty-<command>/` folder
  without `SKILL.md`, is skipped with a warning. The rest of the batch installs.
- A remove-only preparation (`agent config remove`) only releases the removed agents from a
  legacy entry; the rule runs when the last owner is removed.

### 4. The rename migration is per clone

`4.0.0rc8_command_skill_hyphen_names` calls the installer once per configured command-skill
agent and deletes nothing itself. It is clone-local (`clone_local_effect = True`): the
`.agents/skills/` files are git-ignored, so a record committed by one clone must not settle
another clone's ledger (ADR [2026-10-17-1](2026-10-17-1-explicit-migration-ledger.md)). Its
`apply()` is idempotent. An unreadable manifest, an unreadable agent configuration and any
installer refusal are a success with a warning that names `spec-kitty doctor skills`, because
a failed record would block later migrations and the upgrade's surface repair retries. Every
dotted path still on disk afterwards is named in a warning. `upgrade` prints the new
invocation names once, when the rename did something.

### 5. `doctor skills` reports leftovers and collisions

`spec-kitty doctor skills` reports read-only and never deletes a path it lists.

- **Kept edited dotted skill** (no longer in the manifest): a warning with the remedy
  "remove it when you no longer need your edits". The exit code stays 0 when nothing else is
  wrong; keeping it is the user's choice.
- **Dotted skill the manifest still records**, or an unrecorded one that is Spec Kitty's exact
  render: a failure (exit 1) with the remedy `spec-kitty doctor skills --fix`, which retires it.
- **Collision at a canonical path**: a failure (exit 1). The command skill is not installed
  until the user renames or removes the folder and runs `spec-kitty doctor skills --fix`.

`doctor skills --json` gains two additive keys, `legacy` and `collisions`; no existing key
changes.

### 6. Antigravity is a command-skill agent

`antigravity` joins `SUPPORTED_AGENTS` in `skills/_agent_roster.py`. Its `AGENT_COMMAND_CONFIG`
row and its `.agent/workflows` entries in `AGENT_DIRS` are removed. `init`, `upgrade` and
`agent config add antigravity` install the 14 command skills into `.agents/skills/`.
`core.config.configured_slash_agents()` is the one filter that splits a configured agent list
into its slash-command half.

### 7. Antigravity workflow files are archived, not deleted

Operator ruling 2026-10-20: archive, never delete.

- **Project.** `4.0.0rc8_retire_antigravity_workflows` (clone-local, ordered after the rename)
  archives a `.agent/workflows/spec-kitty.<command>.md` file only when it is a regular file,
  names a historical Spec Kitty command and carries an exact
  `<!-- spec-kitty-command-version: X -->` line in its first 20 lines. Each proven file is
  copied into its own fresh folder,
  `.kittify/backups/antigravity-workflows/.backup-<timestamp>[-n]/.agent/workflows/<name>`,
  and only then removed. A backup is never overwritten. Other files, unproven `spec-kitty.*`
  names and the `.agent/` folders stay; a symlinked or non-directory path component refuses
  with a warning. When Antigravity is configured, the migration installs its command skills in
  the same step. This migration gates on the configured agents and the hard-coded retired
  path, because `.agent/workflows` is no longer in `AGENT_DIRS` (a recorded deviation from
  the "iterate `get_agent_dirs_for_project()`" rule).
- **Home folder.** The home-folder writer removes a `~/.agent/workflows/spec-kitty.*.md` file
  only when its inventory records it unedited, or, with no record, when it carries the current
  version marker and equals the frozen render byte for byte. A symlinked `~/.agent` or
  `~/.agent/workflows` refuses. The folder itself is never removed.

### 8. The home-folder writer is scoped to configured agents (amends 2026-04-07-1)

At CLI startup, `ensure_global_agent_commands()` writes command files only for the
slash-command agents configured in the current project's `.kittify/config.yaml`. Outside a
project, or with no or an unreadable configuration, it writes nothing. `agent config add`
writes the added slash-command agents' home files at once; a failure there is a warning and
the next CLI run retries.

The freshness stamp is per key (schema 2: `cli_version`, `template_source_signature`,
`healthy_keys`, `retired_surfaces_cleaned`). A call is fresh when every requested key is
healthy at this version and signature, so the warm startup path checks only the configured
agents. A stamp without schema 2 reads as absent, so the first run on new code builds once and
runs the `~/.agent/workflows` cleanup.

### 9. Frontmatter is projected per root

`src/specify_cli/skills/skill_frontmatter.py` is the one frontmatter authority
(`tests/architectural/test_single_frontmatter_authority.py`).

- **Shared roots** (`.agents/skills/` and any root not listed as native) get only the
  specification fields `name`, `description`, `license`, `compatibility`, `metadata` and
  `allowed-tools`. Other keys move under `metadata`.
- **Native roots** (`.claude/skills`, `.qwen/skills`, `.kilocode/skills`) keep
  `user-invocable`, `argument-hint` and `disable-model-invocation` at the top level.
- Pack skill validation and rendering enforce name ≤ 64 and description ≤ 1024 characters at
  load and again at preparation; a refusal names the limit and the length.

### 10. The reference validator runs in CI

The always-on `agent-skills` job in `ci-router.yml` runs `scripts/ci/validate_agent_skills.py`.
It validates every generated and shipped skill in a shared root with `skills-ref==0.1.1`
(through `uvx`) and with the in-repo mirror; native roots are checked by the mirror only. A
violation from either validator fails the job, and validator output that cannot be read is an
environment error, never a pass.

## Consequences

### Positive

- Every command skill is spec-valid and loads in every harness that reads `.agents/skills/`.
- Antigravity users have working commands again.
- Hand-edited dotted skills and user folders survive every path, each with a named remedy.
- A CLI run outside a project no longer writes into the home folder.

### Negative

- **Older CLIs cannot read the new manifest.** The command-skill manifest schema pattern now
  admits the hyphenated form; a CLI from before this release refuses a manifest written by
  this one. That covers a downgrade and a teammate on an older CLI who pulls a committed
  manifest.
- **Commands can appear twice.** A harness that reads both a slash-command file and
  `.agents/skills/` (for example a project configured for codex and copilot) now shows each
  command twice, because the skills load at last. #6471 resolves this.
- The global skills writer still fans out to skill roots of agents a project does not use;
  #3048 tracks that.

### Neutral

- Leftover dotted folders are visible in `doctor skills` until the user removes them.
- Pre-4.x migrations that read the dotted layout are not edited (DIRECTIVE_044); ledger
  selection does not re-run them on a project they settled.

## References

- Mission artifacts: `kitty-specs/command-skill-names-and-antigravity-01M5DBWT/` (spec, plan,
  `traces/design-decisions.md`).
- Code: `src/specify_cli/skills/command_skill_names.py`, `skills/command_installer.py`,
  `skills/skill_frontmatter.py`, `runtime/agent_commands.py`,
  `upgrade/migrations/m_4_0_0rc8_command_skill_hyphen_names.py`,
  `upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py`,
  `scripts/ci/validate_agent_skills.py`.
- Upgrade note: [Command skills renamed for the Agent Skills specification](../../migrations/command-skill-hyphen-names.md).
