---
title: Managing AI Agents
description: How to add, remove, and manage AI agents in a spec-kitty project after initialization, across the supported slash-command and Agent-Skills harnesses.
doc_status: active
updated: '2026-06-15'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/guides/how-to/installation/install-spec-kitty.md
---
# Managing AI Agents

Learn how to add, remove, and manage AI agents in your spec-kitty project after initialization.

## Overview

Spec-kitty supports slash-command agents such as Claude Code, Gemini CLI, LLxprt Code, Cursor, Qwen Code, OpenCode, Windsurf, GitHub Copilot, Kilo Code, Auggie CLI, Kiro CLI, legacy Amazon Q, and Google Antigravity. It also supports command-skill agents such as Codex CLI, Mistral Vibe, Pi, and Letta Code. (Roo Code shut down on 2026-05-15 and is no longer supported.)

This guide applies after you've run `spec-kitty init` and want to change which agents are active in your project. For initial setup, see the [Getting Started](../../tutorials/getting-started.md) guide.

Agent configuration is managed through `.kittify/config.yaml` and the `spec-kitty agent config` command family. The config file acts as the single source of truth for which agents are active in the project. Slash-command agents use user-global command roots such as `~/.opencode/command/`; Codex, Vibe, Pi, and Letta use project-local command skills under `.agents/skills/`.

This guide shows you how to add agents to enable multi-agent workflows, remove agents you don't use, list configured agents, check sync status, and synchronize your filesystem with the config file.

The five core commands covered in this guide are:
- `list` - View configured agents and available options
- `add` - Add one or more agents to your project
- `remove` - Remove agents you no longer need
- `status` - Audit configuration sync status across all agents
- `sync` - Synchronize filesystem with config.yaml

## Prerequisites

Before using agent config commands, ensure:

- You have initialized a spec-kitty project (`spec-kitty init`)
- You are in the project root directory (where `.kittify/` exists)
- You have write permissions to the project directory

---

**Quick Navigation**: [Listing Agents](#listing-agents) | [Adding Agents](#adding-agents) | [Removing Agents](#removing-agents) | [Checking Status](#checking-agent-status) | [Synchronizing](#synchronizing-filesystem) | [Troubleshooting](#troubleshooting) | [See Also](#see-also)

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `spec-kitty agent config list` | View configured agents and available options |
| `spec-kitty agent config add <agents>` | Add agents to your project |
| `spec-kitty agent config remove <agents>` | Remove agents from your project |
| `spec-kitty agent config status` | Audit agent configuration sync status |
| `spec-kitty agent config sync` | Synchronize filesystem with config.yaml |

## Understanding Agent Configuration

`.kittify/config.yaml` is the single source of truth for agent configuration. All agent management commands read from and write to this file, and the filesystem is automatically synchronized to match it.

This means the config records active agents, while the command surface depends on the agent class. For slash-command agents such as Claude, Gemini, OpenCode, and Kiro, commands are installed globally at CLI startup. When you add one of these agents using `spec-kitty agent config add`, the command updates the config and points at the global command root. For Codex, Vibe, Pi, and Letta, Spec Kitty writes project-local command skills under `.agents/skills/`.

Do not manually edit agent directories or config.yaml directly - use the `spec-kitty agent config` commands instead. This ensures consistency and prevents sync issues.

The key benefit of this config-driven model is that spec-kitty migrations respect your choices. In version 0.11.x and earlier, users could manually delete agent directories, but migrations would recreate them on upgrade. Starting in version 0.12.0, migrations only process agents listed in your config file - if an agent isn't configured, its directory stays deleted.

Here's the structure of `.kittify/config.yaml` for agent configuration:

```yaml
agents:
  available:
    - claude
    - codex
    - opencode
```

The `available` field contains a list of active agent keys. Each key corresponds to a managed command surface:
- `claude` → `~/.claude/commands/` (global)
- `codex` → `.agents/skills/spec-kitty.<command>/` (project-local agent skills)
- `opencode` → `~/.opencode/command/` (global)

When you run `spec-kitty agent config add` or `remove`, this list is automatically updated. Global slash-command files are refreshed by normal CLI startup; Codex, Vibe, Pi, and Letta command skills are managed inside the project.

Managed command surfaces are created and refreshed by CLI commands. You should never need to manually create or delete them.

> **Why This Matters**: In spec-kitty 0.11.x and earlier, users could manually delete agent directories, but migrations would recreate them. Starting in 0.12.0, migrations respect `config.yaml` - if an agent is not listed in `available`, its directory stays deleted. See [Upgrading to 0.12.0](../installation/install-and-upgrade.md) for details.

For architectural details, see [ADR #6: Config-Driven Agent Management](https://github.com/Priivacy-ai/spec-kitty/blob/main/docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md).

## Listing Agents

### View Configured Agents

To see which agents are currently configured in your project:

```bash
spec-kitty agent config list
```

The output shows two sections: configured agents and available agents you can add.

Configured agents display a status indicator:
- ✓ = Managed command surface exists
- ⚠ = Configured in config.yaml but the managed command surface is missing

Available agents show which agents you can add to your project.

Example output:

```
Configured agents:
  ✓ opencode (~/.opencode/command/ (global))
  ✓ claude (~/.claude/commands/ (global))

Available but not configured:
  - codex
  - gemini
  - cursor
  - qwen
  - windsurf
  - kilocode
  - copilot
  - auggie
  - q
```

Use `list` to:
- See which agents are active in your project
- Check if configured agents have their managed command surfaces
- Discover available agents you can add

**Troubleshooting**: If you see ⚠ next to a configured slash-command agent, run any `spec-kitty` command to refresh global commands. For Codex or Vibe, run `spec-kitty agent config add <agent>` again or `spec-kitty upgrade`.

## Adding Agents

### Add One or More Agents

To add agents to your project after initialization:

```bash
spec-kitty agent config add <agent1> <agent2> ...
```

Examples:

```bash
# Add a single agent
spec-kitty agent config add claude

# Add multiple agents at once
spec-kitty agent config add codex gemini cursor
```

When you add an agent, spec-kitty:
1. Registers slash-command agents against their global command root
2. Installs project-local command skills for Codex, Vibe, Pi, and Letta
3. Adds the agent key to `.kittify/config.yaml` under `agents.available`
4. Displays success message for each agent added

Example output:

```
✓ Registered claude (global commands at ~/.claude/commands/)
✓ Registered codex (11 command skills in .agents/skills/)
Updated .kittify/config.yaml
```

### Error Handling

**Invalid agent key**: If you provide an invalid agent key, you'll see an error with the list of valid agents:

```bash
spec-kitty agent config add cluade
```

Output:

```
Error: Invalid agent keys: cluade

Valid agent keys:
  claude, codex, gemini, cursor, qwen, opencode,
  windsurf, kilocode, copilot, auggie, q, kiro,
  antigravity, vibe, pi, letta, llxprt
```

**Already configured**: If an agent is already configured, it's skipped with a message:

```
Already configured: claude
```

### Common Scenarios

**Starting with one agent, adding more later**:

```bash
# Initialized with opencode only
spec-kitty agent config add claude codex
# Now you have 3 agents for multi-agent workflows
```

**Enabling cross-review**:

```bash
# Add a reviewer agent to use alongside your implementer
spec-kitty agent config add codex
```

## Removing Agents

### Remove One or More Agents

To remove agents you no longer use:

```bash
spec-kitty agent config remove <agent1> <agent2> ...
```

Examples:

```bash
# Remove a single agent
spec-kitty agent config remove gemini

# Remove multiple agents at once
spec-kitty agent config remove cursor qwen windsurf
```

When you remove an agent, spec-kitty:
1. Deletes the agent directory (e.g., `.gemini/` and all contents)
2. Removes the agent key from `.kittify/config.yaml`
3. Displays success message for each agent removed

Example output:

```
✓ Removed .gemini/
✓ Removed .cursor/
Updated .kittify/config.yaml
```

### Keep in Configuration but Remove Directory

To remove an agent's directory but keep it in `config.yaml` (for temporary cleanup):

```bash
spec-kitty agent config remove gemini --keep-config
```

**What this does**:
- Deletes `.gemini/` directory
- Leaves `gemini` in `config.yaml` under `available`
- Useful for temporary cleanup without losing configuration

**Restore later**: Run `spec-kitty agent config sync --create-missing` to restore the directory.

### Error Handling

**Invalid agent key**: Same error as `add` command - shows list of valid agents.

**Already removed**: If agent is already removed, you'll see:

```
• .gemini/ already removed
```

This is informational, not an error - command continues processing other agents.

> **Warning**: Removing an agent deletes its entire directory and all slash command templates. This is safe if you're not using the agent, but ensure you don't have custom modifications in those template files before removing.

### Common Scenarios

**Simplifying multi-agent setup**:

```bash
# Started with many agents, narrowing to preferred ones
spec-kitty agent config remove windsurf kilocode qwen
# Keep only the agents you actively use
```

**Preparing for upgrade** (0.11.x → 0.12.0):

```bash
# Before upgrading, remove unwanted agents properly
spec-kitty agent config remove gemini cursor qwen
# Migrations will now respect your choices
```

## Checking Agent Status

### Audit Configuration Sync

To see a comprehensive view of all agents and their sync status:

```bash
spec-kitty agent config status
```

The output displays a rich table with five columns:
- **Agent Key** (cyan) - The agent identifier used in commands
- **Directory** (dim) - The filesystem path
- **Configured** (✓/✗) - Whether the agent is in config.yaml
- **Exists** (✓/✗) - Whether the directory exists on filesystem
- **Status** (colored) - Combined sync status

**Status values**:
- **OK** (green): Agent is configured and directory exists - normal state
- **Missing** (yellow): Agent is configured but directory doesn't exist - needs sync
- **Orphaned** (red): Agent directory exists but not configured - should be cleaned up
- **Not used** (dim): Agent is neither configured nor present - available to add

Example output:

```
Agent Key  Directory                Configured  Exists  Status
──────────────────────────────────────────────────────────────────
claude     ~/.claude/commands/ (global)      ✓  ✓  OK
codex      .agents/skills/ (project skills)  ✗  ✓  Orphaned
gemini     ~/.gemini/commands/ (global)      ✓  ✗  Missing
cursor     ~/.cursor/commands/ (global)      ✗  ✗  Not used
opencode   ~/.opencode/command/ (global)     ✓  ✓  OK

⚠ Found 1 orphaned directory
Run 'spec-kitty agent config sync --remove-orphaned' to clean up
```

Use `status` to:
- Audit your agent configuration for inconsistencies
- Detect orphaned directories (present but not configured)
- Identify missing directories (configured but not present)
- See all 13 slash-command agents at a glance

### Taking Action Based on Status

**Orphaned directories** (red "Orphaned" status):

```bash
# Remove orphaned directories automatically
spec-kitty agent config sync --remove-orphaned
```

**Missing managed surfaces** (yellow "Missing" status):

```bash
# Re-check global command roots and restore supported project-local skill roots
spec-kitty agent config sync --create-missing
```

**Not used** (dim "Not used" status):

```bash
# Add to your project if you want to use them
spec-kitty agent config add <agent>
```

## Synchronizing Filesystem

### Auto-Sync Agents with Configuration

The `sync` command automatically aligns your filesystem with `.kittify/config.yaml`:

```bash
spec-kitty agent config sync
```

**Default behavior** (no flags):
- Removes orphaned directories (present but not configured)
- Does NOT create missing directories
- Reports actions taken or "No changes needed"

### Check Missing Configured Agents

To check configured agents whose managed command surface is missing:

```bash
spec-kitty agent config sync --create-missing
```

**What this does**:
- Reports global command roots for slash-command agents
- Creates/restores supported project-local skill roots where applicable
- Also removes orphaned directories (default behavior)

**Example output**:

```
✓ Global commands present for claude at ~/.claude/commands/
✓ Removed orphaned .gemini/
```

### Keep Orphaned Directories

To prevent deletion of orphaned directories:

```bash
spec-kitty agent config sync --keep-orphaned
```

**What this does**:
- Does NOT remove orphaned directories
- Still checks missing managed surfaces if `--create-missing` is used

**Use case**: You have agent directories not in config.yaml but want to keep them (rare).

### Explicitly Remove Orphaned Directories

The default behavior removes orphaned directories, but you can be explicit:

```bash
spec-kitty agent config sync --remove-orphaned
```

This is equivalent to running `sync` with no flags.

### Complete Sync (Both Directions)

To fully sync filesystem with config (create missing AND remove orphaned):

```bash
spec-kitty agent config sync --create-missing --remove-orphaned
```

This removes orphaned project-local command directories and verifies configured managed surfaces.

### When Filesystem Matches Config

If your filesystem already matches `config.yaml`:

```
No changes needed - filesystem matches config
```

### Common Scenarios

**After manual directory deletion** (not recommended, but happens):

```bash
# The global command root for gemini is missing
spec-kitty agent config status
# Shows "Missing" status for gemini

# Option 1: Re-run any spec-kitty command to refresh global commands, then check again
spec-kitty agent config sync --create-missing

# Option 2: Remove from config properly
spec-kitty agent config remove gemini
```

**After git checkout** (switched branches with different agent configs):

```bash
# Branch A has claude, Branch B has codex
git checkout branch-b

# Sync filesystem to match branch-b's config
spec-kitty agent config sync --create-missing --remove-orphaned
```

**Cleanup after testing** (removed agents manually):

```bash
# Default sync removes orphaned directories
spec-kitty agent config sync
```

## Troubleshooting

This section covers common issues you may encounter when managing agents.

### Orphaned Agent Directories

**Problem**: You see directories like `.gemini/` on filesystem, but the agent is not configured in `.kittify/config.yaml`.

**Cause**: Agent was manually deleted from config.yaml, or directory was created manually.

**Solution**:

```bash
# Option 1: Remove orphaned directory
spec-kitty agent config sync --remove-orphaned

# Option 2: Add to configuration to keep it
spec-kitty agent config add gemini
```

**Detection**: Run `spec-kitty agent config status` - orphaned agents show red "Orphaned" status.

### Missing Configured Agent Directories

**Problem**: Agent is listed in `.kittify/config.yaml` but directory doesn't exist.

**Cause**: Directory was manually deleted, or filesystem corruption.

**Solution**:

```bash
# Option 1: Restore missing directory
spec-kitty agent config sync --create-missing

# Option 2: Remove from configuration if you don't use it
spec-kitty agent config remove gemini
```

**Detection**: Run `spec-kitty agent config status` - missing agents show yellow "Missing" status.

### Corrupt or Missing config.yaml

**Problem**: `.kittify/config.yaml` is missing, unreadable, or has invalid YAML syntax.

**Symptoms**: If config.yaml is missing or has no agents section, commands report "No agents configured." If config.yaml has invalid YAML syntax, commands fail with a parsing error.

**Solution**:

```bash
# Check current config structure
cat .kittify/config.yaml

# If corrupt or missing, recreate with desired agents
spec-kitty agent config add claude codex opencode
# This recreates config.yaml with only specified agents
```

**Prevention**: Don't manually edit `.kittify/config.yaml` - use `spec-kitty agent config` commands instead.

### "spec-kitty: command not found"

**Problem**: Terminal doesn't recognize `spec-kitty` command.

**Cause**: spec-kitty is not installed or not in PATH.

**Solution**: Install Spec Kitty with `pipx install spec-kitty-cli`, then run
`pipx ensurepath` and open a new shell. If your team uses `uv`, `uv tool
install spec-kitty-cli` is also supported. Use `python -m pip install
spec-kitty-cli` only inside an activated virtual environment or another Python
environment you intentionally manage.

**Not a configuration issue**: This is an installation problem. See [Installation Guide](../installation/install-spec-kitty.md).

### "Invalid agent keys" Error

**Problem**: You get an error like "Invalid agent keys: cluade" when running `add` or `remove`.

**Cause**: Typo in agent key name.

**Solution**: Check the error message for the list of valid agent keys, and correct your command:

```bash
# Error message shows:
# Valid agent keys:
#   claude, codex, gemini, cursor, qwen, opencode,
#   windsurf, kilocode, copilot, auggie, q, kiro,
#   antigravity, vibe, pi, letta, llxprt

# Fix typo and retry
spec-kitty agent config add claude  # Not "cluade"
```

**Reference**: See the valid agent keys listed in the error message above, or run `spec-kitty agent config list` to see available agents.

### Still Stuck?

If your issue isn't covered here:

1. Check [Supported AI Agents](../../../api/supported-agents.md) for agent-specific requirements
2. Review [Configuration Reference](../../../api/configuration.md) for config.yaml schema
3. Consult [CLI Commands Reference](../../../api/agent-subcommands.md#spec-kitty-agent-config) for detailed command syntax
4. Report bugs at [spec-kitty GitHub Issues](https://github.com/Priivacy-ai/spec-kitty/issues)

## See Also

For more information on agent management and related topics:

### Command Reference

- [CLI Commands: spec-kitty agent config](../../../api/agent-subcommands.md#spec-kitty-agent-config) - Detailed command syntax, flags, and options for all agent config subcommands

### Supported Agents

- [Supported AI Agents](../../../api/supported-agents.md) - Complete list of slash-command agents with capabilities, installation requirements, and usage notes

### Configuration

- [Configuration Reference](../../../api/configuration.md) - Complete `.kittify/config.yaml` schema for agent availability and preferred roles

### Architecture

- [ADR #6: Config-Driven Agent Management](https://github.com/Priivacy-ai/spec-kitty/blob/main/docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md) - Architectural decision record explaining why migrations now respect `config.yaml` and the config-driven model rationale

### Migration Guides

- [Upgrading to 0.12.0](../installation/install-and-upgrade.md) - Migration guide for 0.11.x users transitioning to config-driven agent management

### Initial Setup

- [Installing spec-kitty](../installation/install-spec-kitty.md) - Initial agent selection during `spec-kitty init`
