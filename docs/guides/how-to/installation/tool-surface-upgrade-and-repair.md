---
title: Repair Tool Surfaces After an Upgrade
description: How to understand the Tool vs Agent vs Tool Surface distinction in Spec Kitty 3.2 and repair missing generated surfaces with doctor tool-surfaces --fix after upgrading.
doc_status: active
updated: '2026-06-15'
type: how-to
audience:
- profile: external/project-owner
  guidance_text: Written for the Project Owner reader.
related:
- guides/how-to/installation/diagnose-installation
- guides/how-to/installation/upgrade-project
---
# Repair Tool Surfaces After an Upgrade

When you upgrade Spec Kitty, or clone a project fresh, the per-tool files that
let your coding assistant find Spec Kitty commands and agent profiles can be
missing, partial, or drifted. This guide explains the three terms you will see
in diagnostics — **Tool**, **Agent**, and **Tool Surface** — and shows you how
to repair the generated surfaces with a single command.

## Tool vs Agent vs Tool Surface

These three words look interchangeable but mean different things in Spec Kitty.
Getting them straight makes the diagnostics readable.

- **Tool** — the coding assistant you run Spec Kitty through: Claude Code,
  Codex CLI, Cursor, Copilot, Gemini, and the rest of the supported set. A tool
  is the *integration target*. You choose your tools with
  `spec-kitty agent config add` and list them with `spec-kitty agent config list`.

- **Agent** — a *role/persona* that does work inside a mission, such as an
  implementer, a reviewer, or an architect. Agents are defined by agent-profile
  doctrine, not by your editor. One tool (say, Claude Code) executes many
  different agents over the life of a mission. "Agent" answers *who is acting*;
  "tool" answers *which assistant is running it*.

- **Tool Surface** — a concrete file (or set of files) that Spec Kitty
  *generates for a tool* so that tool can discover commands and agent profiles.
  Examples are the command-skill files a skill-based tool reads and the agent
  profile files a command-based tool reads. Each tool surface is derived from a
  registered path pattern in the Tool Surface Contract, so the diagnostics can
  tell exactly which surface is missing or has drifted.

In short: a **tool** consumes **tool surfaces** in order to run **agents**.

## When you need this guide

Run the repair flow whenever any of these are true:

- You just ran `spec-kitty upgrade` and your assistant stopped seeing Spec Kitty
  commands or skills.
- You cloned a project fresh and the per-tool surfaces were never generated
  locally.
- `spec-kitty doctor` reports missing, stale, or drifted command-skill or
  agent-profile files.

## Step 1 — Diagnose the surfaces

Ask the doctor what is missing before changing anything:

```bash
spec-kitty doctor tool-surfaces --json
```

The report lists, per configured tool, which surfaces are present, which are
missing (gaps), which are stale, and which have drifted from their generated
form. Read the gaps and drift entries first — they tell you whether a repair
will simply regenerate files or whether you have hand-edited a managed file.

To narrow the report to a single kind or a single tool:

```bash
spec-kitty doctor tool-surfaces --kind command-skill --json
spec-kitty doctor tool-surfaces --tool codex --json
```

## Step 2 — Repair the surfaces

When the report shows gaps or stale entries, regenerate them:

```bash
spec-kitty doctor tool-surfaces --fix
```

The `--fix` flag regenerates the missing and stale surfaces for every tool in
your project's agent configuration. It is **safe and conservative**:

- It only touches surfaces that Spec Kitty manages.
- It refuses to overwrite a managed file that you have edited (reported as
  *drift*) — resolve the edit first, then re-run.
- It refuses to act when a managed surface path resolves outside the project
  (reported as *unsafe*).
- It leaves files it does not own alone.

`spec-kitty upgrade` uses the same owner assessments in its finalizer. Inspect
them without writing via `spec-kitty upgrade --plan-json`: `effects` are exact
owned writes, while `dispositions` explain unchanged, preserved,
consent-required, or inapplicable paths. Supporting manifests and parent
directories appear as effects rather than hidden side effects. Global roots are
independent of `--no-worktrees`; that option excludes worktree discovery and
repair only. An incomplete required owner blocks apply instead of becoming an
empty successful plan.

If the report flagged drift or unsafe paths, the repair will decline and tell
you why. Reconcile those entries by hand, then run `--fix` again.

## Step 3 — Confirm the repair

Re-run the diagnostic and confirm the report is clean:

```bash
spec-kitty doctor tool-surfaces --json
```

When `ok` is `true` and there are no gaps, your tools can find Spec Kitty's
commands and agent profiles again.

## Related repair commands

- Command-skill drift only: `spec-kitty doctor skills --fix` targets the
  skill-based tools (Codex, Vibe, Pi, Letta) specifically.
- Whole-installation problems: see
  [Diagnose Installation Problems](diagnose-installation.md).
- Upgrading the project after a CLI upgrade: see
  [Upgrade a Project](upgrade-project.md).

## Notes

- These surfaces are *generated*. Do not hand-edit the per-tool files — edit the
  doctrine sources and regenerate. Hand edits are exactly what the drift guard
  protects you from clobbering, and they will block `--fix` until reconciled.
- The set of tools the repair acts on is your project's configured tool set
  (`spec-kitty agent config list`). Adding or removing a tool changes which
  surfaces are generated.
