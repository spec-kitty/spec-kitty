---
title: Getting Started with Spec Kitty
description: Install Spec Kitty 3.2, initialize a project, and create your first mission with a guided beginner workflow.
doc_status: active
updated: '2026-09-14'
audience: docs/context/audience/external/project-owner.md
type: tutorial
related:
- docs/guides/how-to/installation/install-spec-kitty.md
- docs/guides/tutorials/your-first-mission.md
---
# Getting Started with Spec Kitty

**Divio type**: Tutorial

In this tutorial, you'll install Spec Kitty and create your first mission specification.

**Time**: ~30 minutes
**Prerequisites**: Python 3.11+, Git, an AI coding agent (Claude Code, Cursor, Gemini CLI, etc.)

![Getting started with Spec Kitty - Mission Kitty hero](../../assets/images/getting-started-mission-kitty.png)

_Stylized splash — the "GET STARTED" lettering is decorative. Install steps and the rest of this tutorial are in the text below; for a dedicated install guide see [Install Spec Kitty](../how-to/installation/install-spec-kitty.md)._

## Step 1: Install Spec Kitty

Install the CLI with `pipx`:

```bash
pipx install spec-kitty-cli
```

`pipx` is preferred for command-line tools because it creates an isolated
virtual environment for Spec Kitty and avoids the
`externally-managed-environment` errors that modern Linux distributions can
raise for direct `pip install` commands.

Other supported install methods:

```bash
uv tool install spec-kitty-cli
```

```bash
# Inside an activated virtual environment
python -m pip install spec-kitty-cli
```

Verify the CLI is available:

```bash
spec-kitty --version
```

Expected output (abridged):

```
spec-kitty-cli version 3.1.5
```

If this step gives you trouble — a platform not covered above, an
`externally-managed-environment` error, or a Git credential prompt on Linux —
the [installation guide](../how-to/installation/install-spec-kitty.md) has the full per-platform
instructions and troubleshooting.

## Step 2: Initialize a Project

Create a new project directory with the agent you plan to use, then put it under
git:

```bash
spec-kitty init my-spec-project --ai claude
cd my-spec-project
git init -b main
git add -A && git commit -m "Initial commit"
git checkout -b my-first-mission
```

Expected output (abridged):

```
OK Initialized Spec Kitty project
OK Created .kittify/ scaffold
```

>[!IMPORTANT]
>**Complete the git setup before continuing.** The first two commands prepare
>the repository; the working branch allows planning artifacts to be committed:
>
>1. `git init -b main` — `spec-kitty init` creates files and deliberately does
> not touch git. It even prints `Required: run git init here before
> agent/worktree commands`. Without a repository, `specify` stops with
> `SPEC_KITTY_REPO_NOT_INITIALIZED`.
>2. `git commit` — Spec Kitty needs a committed HEAD to create and commit
> its mission scaffold. Without it you get "this checkout has no commits
> yet".
>3. `git checkout -b my-first-mission` — use a working branch so Spec Kitty
> can commit planning artifacts. On a protected branch, mission creation can
> succeed with a warning listing uncommitted files. Continue that existing
> mission after switching branches; do not run `specify` again. The branch
> name is yours to choose.
>
>Already working in an existing git repository with history? Skip the first two
>and just make a working branch before continuing.

>[!TIP]
>Use `spec-kitty init . --ai claude` to initialize the current folder instead of
>creating a new one. The git requirement above applies either way.

## Step 3: Create Your First Specification

Open your AI agent in this repository and run the `specify` command.

In your agent:

```text
/spec-kitty.specify Build a tiny command-line task list app with add, complete, and delete actions.
```

You'll be asked a discovery interview. Answer each question until the command completes.

Expected results:

- One new mission directory under `kitty-specs/`, named `<slug>-<id>` — for
  example `task-list-01M20JM4`. The trailing token is the mission's own
  identifier, so yours will differ.
- `spec.md` inside it (the mission spec)
- Mission creation commits its generated metadata, event log, and task scaffold.
  Your agent then writes the substantive specification and commits it with
  `spec-kitty spec-commit`; the initial `spec.md` scaffold alone is not ready
  for planning.

>[!NOTE]
>Run `specify` **once**. Each run creates a separate mission, so running it
>again gives you two, not an edited one. The next tutorial continues the mission
>you just created rather than making another.

## Step 4: Verify Your Work

Confirm the mission directory exists:

```bash
ls kitty-specs
```

Example output (your identifier will differ):

```
task-list-01M20JM4
```

If the command created a new worktree later in the workflow, it will appear here:

```bash
ls .worktrees
```

## Troubleshooting

- **`spec-kitty: command not found`**: Reopen your shell, run `pipx ensurepath` if you installed with `pipx`, or reinstall via `pipx` or `uv`. Then rerun `spec-kitty --version`.
- **`pip install` fails with `externally-managed-environment`**: Use `pipx install spec-kitty-cli`, or create and activate a virtual environment before using `python -m pip install spec-kitty-cli`.
- **Planning artifacts left uncommitted on a protected branch**: mission creation can succeed while reporting its uncommitted files. Run `git checkout -b my-first-mission`, review and commit those files, and continue the existing mission. Do not run `specify` again.
- **`SPEC_KITTY_REPO_NOT_INITIALIZED` from `specify`**: the project directory is not a git repository. Run `git init -b main`, then `git add -A && git commit -m "Initial commit"`, and retry. `spec-kitty init` does not create the repository for you.
- **"This checkout has no commits yet"**: the repository exists but has no commit, so Spec Kitty cannot commit its mission scaffold. Run `git add -A && git commit -m "Initial commit"` (or `git commit --allow-empty -m "Initial commit"` if there is nothing to stage) and retry.
- **No `/spec-kitty.specify` command available**: Re-run `spec-kitty init . --ai <your-agent>` from the project root, then verify the setup with `spec-kitty verify-setup --diagnostics`.
- **`WAITING_FOR_DISCOVERY_INPUT`**: The command is paused for your answers; provide the requested details and continue.

## What's Next?

Continue with [Your First Mission](your-first-mission.md) for the complete
workflow from specification to merge. It picks up the mission you just created:
its Step 1 is only about confirming you have that mission, so **start at
[Step 2](your-first-mission.md#step-2-create-the-technical-plan) and do not run
`/spec-kitty.specify` again**.

### Related How-To Guides

- [Install and Upgrade](../how-to/installation/install-and-upgrade.md) - Additional installation options
- [Create a Specification](../how-to/missions/create-specification.md) - Deep dive into `/spec-kitty.specify`
- [Non-Interactive Init](../how-to/installation/non-interactive-init.md) - Scripted project setup

### Reference Documentation

- [CLI Commands](../../api/cli-commands.md) - Full command reference
- [Slash Commands](../../api/slash-commands.md) - AI agent slash commands
- [Supported Agents](../../api/supported-agents.md) - Slash-command agents supported by the CLI

### Learn More

- [Spec-Driven Development](../../architecture/spec-driven-development.md) - Why specs matter
- [Mission System](../../architecture/mission-system.md) - How missions shape workflows
