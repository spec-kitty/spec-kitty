---
title: Supported AI Agents Reference
description: Reference for Spec Kitty supported AI agents. Learn about slash command integrations, global directories, and config-driven agent management.
doc_status: active
updated: '2026-06-15'
related:
- docs/api/cli-commands.md
- docs/api/slash-commands.md
- docs/api/supported-harnesses.md
---
# Supported AI Agents Reference

Spec Kitty currently exposes **17 agent surfaces**: 13 slash-command or prompt-file hosts and 4 project-local command-skill hosts.

Slash-command agents get user-global command directories such as `~/.claude/commands/` or `~/.opencode/command/`. Codex CLI, Vibe, Pi, and Letta Code use shared project-local agent skills under `.agents/skills/spec-kitty.<command>/`.

---

## Agent Overview

### Slash-command and prompt-file agents

| Agent | Global Directory | Commands Subdirectory | Slash Commands |
|-------|------------------|----------------------|----------------|
| Claude Code | `~/.claude/` | `commands/` | `/spec-kitty.*` |
| GitHub Copilot | `~/.github/` | `prompts/` | `/spec-kitty.*` |
| Google Gemini | `~/.gemini/` | `commands/` | `/spec-kitty.*` |
| LLxprt Code | `~/Library/Preferences/llxprt-code/` (macOS) | `commands/` | `/spec-kitty.*` |
| Cursor | `~/.cursor/` | `commands/` | `/spec-kitty.*` |
| Qwen Code | `~/.qwen/` | `commands/` | `/spec-kitty.*` |
| OpenCode | `~/.opencode/` | `command/` | `/spec-kitty.*` |
| Windsurf | `~/.windsurf/` | `workflows/` | `/spec-kitty.*` |
| Google Antigravity | `~/.agent/` | `workflows/` | `/spec-kitty.*` |
| Kilocode | `~/.kilocode/` | `workflows/` | `/spec-kitty.*` |
| Augment Code | `~/.augment/` | `commands/` | `/spec-kitty.*` |
| Amazon Q (legacy) | `~/.amazonq/` | `prompts/` | `/spec-kitty.*` |
| Kiro | `~/.kiro/` | `prompts/` | `/spec-kitty.*` |

### Command-skill agents

| Agent | Agent Key | Project Directory | Invocation Form |
|-------|-----------|-------------------|-----------------|
| Codex CLI | `codex` | `.agents/skills/spec-kitty.<command>/` | `$spec-kitty.<command>` |
| Mistral Vibe | `vibe` | `.agents/skills/spec-kitty.<command>/` via `.vibe/config.toml` | Host skill syntax |
| Pi | `pi` | `.agents/skills/spec-kitty.<command>/` | `/skill:spec-kitty.<command>` |
| Letta Code | `letta` | `.agents/skills/spec-kitty.<command>/` | `/spec-kitty.<command>` |

Command-skill packages share the same `SKILL.md` files. `.kittify/command-skills-manifest.json` records which configured agents own each package so removing one agent does not delete skills still used by another agent.

---

## Managing Active Agents

Spec-kitty supports 16 AI agents (listed above). You can activate or deactivate agents at any time using the `spec-kitty agent config` command family.

To manage which agents are active in your project:
- **View configured agents**: `spec-kitty agent config list`
- **Add agents**: `spec-kitty agent config add <agents>`
- **Remove agents**: `spec-kitty agent config remove <agents>`

See [Managing AI Agents](../guides/how-to/collaboration/manage-agents.md) for complete documentation on agent management workflows.

For per-harness usage guides, see [Codex](../guides/how-to/harnesses/codex.md), [Pi TUI](../guides/how-to/harnesses/pi-tui.md), and [Letta Code](../guides/how-to/harnesses/letta.md).

---

## Agent Details

### Claude Code

**Primary supported agent** — Full feature support and extensive testing.

| Property | Value |
|----------|-------|
| Directory | `.claude/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai claude` |
| Status | Fully supported |

**Features**:
- Full slash command support
- Custom command arguments
- Project-level CLAUDE.md integration
- Best documentation and testing coverage

**Usage**:
```bash
spec-kitty init my-project --ai claude
cd my-project
claude  # Launch Claude Code
/spec-kitty.specify Add user authentication
```

---

### GitHub Copilot

| Property | Value |
|----------|-------|
| Directory | `.github/` |
| Commands subdirectory | `prompts/` |
| CLI flag | `--ai copilot` |
| Status | Supported |

**Usage**:
```bash
spec-kitty init my-project --ai copilot
```

---

### Google Gemini

| Property | Value |
|----------|-------|
| Directory | `.gemini/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai gemini` |
| Status | Supported |

**Usage**:
```bash
spec-kitty init my-project --ai gemini
```

---

### LLxprt Code

| Property | Value |
|----------|-------|
| Directory | `.llxprt/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai llxprt` |
| Status | Supported |

LLxprt Code is a fork of Gemini CLI, so it reads the same TOML custom-command
schema (`prompt`, optional `description`, `{{args}}` placeholder) from
`.llxprt/commands/` at the project tier. User-global commands live under the
envPaths('llxprt-code') config root — `~/Library/Preferences/llxprt-code/commands/`
on macOS, `~/.config/llxprt-code/commands/` on Linux — overridable with the
`LLXPRT_CONFIG_HOME` environment variable; the legacy `~/.llxprt/` tree is
migrated to that layout at startup and is no longer read. Model profiles are
stored at `<global-config>/profiles/<name>.json`
(`~/Library/Preferences/llxprt-code/profiles/` on macOS)
and loaded with `--profile-load <name>`.

**Skills**: LLxprt Code also discovers `SKILL.md` Agent Skills. It reads the
user-global roots `~/.agents/skills/` (the cross-tool standard) and
`<global-config>/skills/` (`~/Library/Preferences/llxprt-code/skills/` on macOS), plus
the project roots `.llxprt/skills/` and `.agents/skills/`, with `.agents/skills/`
taking highest precedence. Spec Kitty installs its skill pack into the shared
`.agents/skills/` root (the same primary root it uses for Gemini CLI, Kiro and the
other shared-root agents), and keeps the user-global `~/.agents/skills/` copy in
sync as the CLI upgrades. `.llxprt/skills/` is a declared secondary root: LLxprt
reads it and Spec Kitty skill upgrades keep copies found there in sync, but the
installer does not seed it.

**Asking process questions**: LLxprt Code auto-continues an active todo list
whenever a turn ends without a tool call, so a question written as plain text at
the end of a turn is consumed by the continuation loop instead of reaching the
user. Whenever spec-kitty commands run under `llxprt` interactively, an agent
that needs a user process decision (PR-based flow versus direct commit, mission
scope, merge strategy) must call `todo_pause` with the question as the reason
before asking it. Tactical implementation choices do not warrant a pause; the
agent proceeds with its best judgment.

**Usage**:
```bash
spec-kitty init my-project --ai llxprt
```

---

### Cursor

| Property | Value |
|----------|-------|
| Directory | `.cursor/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai cursor` |
| Status | Supported |

**Usage**:
```bash
spec-kitty init my-project --ai cursor
```

---

### Qwen Code

| Property | Value |
|----------|-------|
| Directory | `.qwen/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai qwen` |
| Status | Supported |

**Usage**:
```bash
spec-kitty init my-project --ai qwen
```

---

### OpenCode

| Property | Value |
|----------|-------|
| Directory | `.opencode/` |
| Commands subdirectory | `command/` (note: singular) |
| CLI flag | `--ai opencode` |
| Status | Supported |

**Note**: OpenCode uses `command/` (singular) instead of `commands/` (plural).

**Usage**:
```bash
spec-kitty init my-project --ai opencode
```

---

### Windsurf

| Property | Value |
|----------|-------|
| Directory | `.windsurf/` |
| Commands subdirectory | `workflows/` |
| CLI flag | `--ai windsurf` |
| Status | Supported |

**Note**: Windsurf uses `workflows/` instead of `commands/`.

**Usage**:
```bash
spec-kitty init my-project --ai windsurf
```

---

### GitHub Codex

| Property | Value |
|----------|-------|
| Directory | `.agents/skills/` |
| Commands subdirectory | `spec-kitty.<command>/SKILL.md` |
| CLI flag | `--ai codex` |
| Status | Supported |

Codex uses project-local agent skills. Spec Kitty installs one `SKILL.md`
package per command under `.agents/skills/spec-kitty.<command>/`.

**Usage**:
```bash
spec-kitty init my-project --ai codex
```

---

### Kilocode

| Property | Value |
|----------|-------|
| Directory | `.kilocode/` |
| Commands subdirectory | `workflows/` |
| CLI flag | `--ai kilocode` |
| Status | Supported |

**Note**: Kilocode uses `workflows/` instead of `commands/`.

**Usage**:
```bash
spec-kitty init my-project --ai kilocode
```

---

### Augment Code

| Property | Value |
|----------|-------|
| Directory | `.augment/` |
| Commands subdirectory | `commands/` |
| CLI flag | `--ai auggie` |
| Status | Supported |

**Usage**:
```bash
spec-kitty init my-project --ai auggie
```

---

### Roo Code (deprecated)

> **Roo Code shut down on 2026-05-15 and is no longer supported.**
>
> Existing projects with a `.roo/` directory will receive a deprecation notice
> during `spec-kitty upgrade`. The `.roo/` directory is preserved and will not
> be deleted automatically. To remove it from your project configuration, run:
> ```bash
> spec-kitty agent config remove roo
> ```

---

### Amazon Q (legacy)

| Property | Value |
|----------|-------|
| Directory | `.amazonq/` |
| Commands subdirectory | `prompts/` |
| CLI flag | `--ai q` |
| Status | Legacy — rebranded to Kiro |

Amazon Q Developer CLI has been [rebranded to Kiro CLI](https://kiro.dev/docs/cli/migrating-from-q/). Existing projects using `--ai q` continue to work; new projects should select `--ai kiro`. The Kiro installer automatically copies `~/.aws/amazonq/` to `~/.kiro/` at the user level.

**Usage**:
```bash
spec-kitty init my-project --ai q  # legacy
```

---

### Kiro

| Property | Value |
|----------|-------|
| Directory | `.kiro/` |
| Commands subdirectory | `prompts/` |
| CLI flag | `--ai kiro` |
| Binary | `kiro-cli` |
| Status | Supported |

Kiro CLI (formerly Amazon Q Developer CLI) supports slash-command arguments via `$ARGUMENTS`, but the full invocation must be shell-quoted for arguments to pass through. See [kirodotdev/Kiro#4141](https://github.com/kirodotdev/Kiro/issues/4141).

```bash
# Correct — arguments reach $ARGUMENTS
kiro '@speckit.specify my feature description'

# Incorrect — arguments are swallowed
kiro @speckit.specify my feature description
```

**Usage**:
```bash
spec-kitty init my-project --ai kiro
```

---

## Multi-Agent Setup

You can initialize a project with multiple agents:

```bash
# Initialize with Claude and Pi
spec-kitty init my-project --ai claude,pi

# Initialize with all agents
spec-kitty init my-project --ai claude,copilot,gemini,cursor,qwen,opencode,windsurf,codex,kilocode,auggie,q,kiro,antigravity,vibe,pi,letta,llxprt
```

This registers all specified agents, allowing team members to use their preferred tool. Slash-command files are installed in user-global agent roots at CLI startup; Codex, Vibe, Pi, and Letta command skills are installed project-locally under `.agents/skills/`.

---

## Adding Agents Later

To add agent support to an existing project:

```bash
spec-kitty agent config add pi letta
```

For project configuration, use `spec-kitty agent config add <agent>` rather than manually copying command files. After upgrading an older project, `spec-kitty upgrade` refreshes missing `.pi/`, `.letta/`, and `.agents/skills/` backfill state for configured Pi and Letta projects.

---

## Slash Commands

All agents support the same 13 slash commands:

| Command | Purpose |
|---------|---------|
| `/spec-kitty.specify` | Create feature specification |
| `/spec-kitty.plan` | Create implementation plan |
| `/spec-kitty.tasks` | Generate work packages |
| `/spec-kitty.implement` | Start WP implementation |
| `/spec-kitty.review` | Review completed work |
| `/spec-kitty.accept` | Validate an approved mission before merge |
| `/spec-kitty.merge` | Merge an accepted mission to its target branch |
| `/spec-kitty.status` | Show kanban status |
| `/spec-kitty.dashboard` | Open web dashboard |
| `/spec-kitty.charter` | Create project principles |
| `/spec-kitty.research` | Conduct research |
| `/spec-kitty.analyze` | Analyze codebase |

See [Slash Commands](slash-commands.md) for complete documentation.

Command-skill hosts use the same Spec Kitty workflow commands but expose them through their host-specific skill invocation syntax. See [Supported Harnesses](supported-harnesses.md) for current tier status and per-harness links.

---

## Agent Selection Guidelines

| Scenario | Recommended Agent |
|----------|-------------------|
| Best overall experience | Claude Code |
| VS Code integration | Cursor, GitHub Copilot |
| JetBrains IDEs | Cursor |
| AWS environment | Kiro (formerly Amazon Q) |
| Open source preference | OpenCode, Qwen |
| Enterprise/air-gapped | Any (local templates available) |

---

## Troubleshooting

### Slash commands not appearing

1. Verify the global agent directory exists:
   ```bash
   ls -la ~/.claude/commands/
   ```

2. Regenerate commands:
   ```bash
   spec-kitty upgrade
   ```

3. Restart your AI agent

### Agent-specific issues

**Kiro / Amazon Q**: Slash-command arguments only pass through when the full invocation is shell-quoted (e.g. `kiro '@speckit.specify <description>'`). Without quoting, the trailing text is not forwarded to `$ARGUMENTS`. See [kirodotdev/Kiro#4141](https://github.com/kirodotdev/Kiro/issues/4141).

**Codex**: Confirm project-local agent skills exist:
```bash
ls .agents/skills/spec-kitty.specify/SKILL.md
spec-kitty agent config sync
```

---

## See Also

- [Slash Commands](slash-commands.md) — Complete command reference
- [Supported Harnesses](supported-harnesses.md) — Support matrix for every agent surface
- [CLI Commands](cli-commands.md) — `spec-kitty` command reference
- [Install & Upgrade](../guides/how-to/installation/install-spec-kitty.md) — Installation guide

## Getting Started

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)

## Practical Usage

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)
- [Use the Dashboard](../guides/how-to/monitoring/use-dashboard.md)

## Background

- [AI Agent Architecture](../architecture/ai-agent-architecture.md)
