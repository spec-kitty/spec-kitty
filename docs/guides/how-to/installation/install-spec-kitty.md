---
title: Install Spec Kitty — macOS, Linux, and Windows Installation Guide
description: Step-by-step guide to install Spec Kitty on macOS, Linux, and Windows. Set up the CLI, initialize your project, and configure AI coding agents.
doc_status: active
updated: '2026-08-11'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/api/slash-commands.md
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/guides/how-to/collaboration/manage-agents.md
- docs/guides/how-to/installation/install-linux.md
- docs/guides/how-to/installation/install-macos.md
- docs/guides/how-to/installation/install-windows.md
- docs/guides/how-to/installation/non-interactive-init.md
- docs/guides/how-to/monitoring/use-dashboard.md
---
# Installation Guide

> Spec Kitty is inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit). Installation commands below target the spec-kitty distribution while crediting the original project.

> **📖 Looking for the complete workflow?** See the [README: Getting Started guide](https://github.com/spec-kitty/spec-kitty#-getting-started-complete-workflow) for the full lifecycle from CLI installation through feature development and merging.

![Install Spec Kitty — Mission Kitty as a detective with a toolbox and gears](../../../assets/images/install-spec-kitty-mission-kitty.png)

_Stylized splash — decorative only. Platform install paths and CLI steps are in the text below._

> [!TIP]
> Platform-specific notes: [Linux](install-linux.md) · [macOS](install-macos.md) · [Windows](install-windows.md)

## Prerequisites

- **Linux/macOS** (or Windows; PowerShell scripts now supported without WSL)
- AI coding agent: [Claude Code](https://www.anthropic.com/claude-code), [GitHub Copilot](https://code.visualstudio.com/), or [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [pipx](https://pipx.pypa.io/stable/installation/) for the recommended CLI install path
- Optional: [uv](https://docs.astral.sh/uv/) if your team standardizes on uv-managed tools

## Installation

### Install Spec Kitty CLI

#### From PyPI (Recommended - Stable Releases)

**Using pipx (preferred):**
```bash
pipx install spec-kitty-cli
```

`pipx` installs Spec Kitty as an application in an isolated virtual environment
and places the `spec-kitty` command on your PATH. This is the safest default on
modern Python installations because many Linux distributions now block direct
system-wide `pip install` commands with PEP 668
`externally-managed-environment` errors.

If this is your first `pipx` install, make sure its binary directory is on your
PATH:

```bash
pipx ensurepath
```

Then open a new shell and verify:

```bash
spec-kitty --version
```

**Using uv:**
```bash
uv tool install spec-kitty-cli
```

**Using pip in an activated virtual environment or managed CI Python image:**
```bash
python -m pip install spec-kitty-cli
```

Use `pip` when you are already inside a project-specific virtual environment,
CI image, or other Python environment you intentionally manage. Avoid direct
system-wide `pip install spec-kitty-cli` on distro-managed Python installs.

#### From GitHub (Latest Development)

Use the GitHub install path when you need the latest unreleased code from
`main`.

**Using pipx (preferred):**
```bash
pipx install git+https://github.com/spec-kitty/spec-kitty.git
```

**Using uv:**
```bash
uv tool install spec-kitty-cli --from git+https://github.com/spec-kitty/spec-kitty.git
```

**Using pip in an activated virtual environment or managed CI Python image:**
```bash
python -m pip install git+https://github.com/spec-kitty/spec-kitty.git
```

### Initialize a New Project

After installation, initialize a new project:

**If installed with pipx, uv, or an active virtual environment:**
```bash
spec-kitty init <PROJECT_NAME>
```

**One-time usage (without installing):**

**Using pipx:**
```bash
pipx run spec-kitty-cli init <PROJECT_NAME>
```

**Using uvx:**
```bash
uvx spec-kitty-cli init <PROJECT_NAME>
```

### Add to an Existing Project

To add Spec Kitty to an existing repository, run `init` from that repository root:

```bash
cd /path/to/existing-project
spec-kitty init . --ai claude
```

What this does today:
- Creates the `.kittify/` scaffold in the current directory
- Adds the selected agent command directories
- Updates ignore files such as `.gitignore` / `.claudeignore`
- Leaves your Git history untouched; `init` does not initialize Git or create commits

**Best practices for existing projects:**
1. Commit or stash your current work before adding Spec Kitty.
2. Review `.gitignore` after init so agent directories remain untracked.
3. Use `spec-kitty doctor skills --json` if you want a post-install skill health check.
4. Start the workflow with `/spec-kitty.specify`; mission selection happens there, not during `init`.

### Choose AI Agent

You can proactively specify your AI agent during initialization:

```bash
spec-kitty init <project_name> --ai claude
spec-kitty init <project_name> --ai gemini
spec-kitty init <project_name> --ai codex
spec-kitty init <project_name> --ai claude,codex
```

### Managing Agents After Initialization

After running `spec-kitty init`, you can add or remove agents at any time using the `spec-kitty agent config` command family.

To manage agents post-init:
- **Add agents**: `spec-kitty agent config add <agents>`
- **Remove agents**: `spec-kitty agent config remove <agents>`
- **Check status**: `spec-kitty agent config status`

See [Managing AI Agents](../collaboration/manage-agents.md) for complete documentation on agent management workflows.

### Non-Interactive Setup

For CI or scripts, use the non-interactive mode documented by `spec-kitty init --help`:

```bash
spec-kitty init <project_name> --ai claude --non-interactive
```

## Verification

After initialization, you should see the following commands available in your AI agent:
- `/spec-kitty.specify` - Create specifications
- `/spec-kitty.plan` - Generate implementation plans  
- `/spec-kitty.research` - Scaffold mission-specific research artifacts (Phase 0)
- `/spec-kitty.tasks` - Break down into actionable tasks

Those four cover the start of a mission. For everything your agent can now run —
including `/spec-kitty.implement`, `/spec-kitty.review`, `/spec-kitty.accept`, and
`/spec-kitty.merge` — with syntax and prerequisites for each, see the
[slash command reference](../../../api/slash-commands.md).

Run `spec-kitty dashboard --open` if you want the live dashboard immediately after setup.

## Troubleshooting

### `pip install` fails with `externally-managed-environment`

On Ubuntu 24.04, Debian 12, Fedora, and other modern distributions, Python may
refuse direct system-wide `pip install spec-kitty-cli` commands because the OS
owns the system Python environment. Install the CLI with `pipx` instead:

```bash
pipx install spec-kitty-cli
pipx ensurepath
```

If you must use `pip`, create and activate a virtual environment first:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install spec-kitty-cli
```

### Git Credential Manager on Linux

If you're having issues with Git authentication on Linux, you can install Git Credential Manager:

```bash
#!/usr/bin/env bash
set -e
echo "Downloading Git Credential Manager v2.6.1..."
wget https://github.com/git-ecosystem/git-credential-manager/releases/download/v2.6.1/gcm-linux_amd64.2.6.1.deb
echo "Installing Git Credential Manager..."
sudo dpkg -i gcm-linux_amd64.2.6.1.deb
echo "Configuring Git to use GCM..."
git config --global credential.helper manager
echo "Cleaning up..."
rm gcm-linux_amd64.2.6.1.deb
```

## Command Reference

- [`spec-kitty init`](../../../api/cli-commands.md#spec-kitty-init)
- [`spec-kitty upgrade`](../../../api/cli-commands.md#spec-kitty-upgrade)
- [`spec-kitty doctor skills`](../../../api/cli-commands.md)

## See Also

- [Non-Interactive Init](non-interactive-init.md)
- [Upgrade to 0.11.0](install-and-upgrade.md)
- [Use the Dashboard](../monitoring/use-dashboard.md)

## Background

- [Spec-Driven Development](../../../architecture/spec-driven-development.md)
- [Mission System](../../../architecture/mission-system.md)
