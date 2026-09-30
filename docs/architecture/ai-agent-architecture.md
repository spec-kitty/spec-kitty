---
title: AI Agent Architecture Explained
description: "How Spec Kitty stays agent-agnostic: slash commands and Agent Skills rendered from one shared command-template source, per agent format, driving the same lane workflow."
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/execution-lanes.md
- docs/architecture/kanban-workflow.md
- docs/architecture/mission-system.md
---
# AI Agent Architecture Explained

Spec Kitty supports 17 AI agents (13 slash-command agents and 4 Agent Skills agents), allowing teams to use their preferred tools. This document explains how the multi-agent system works and why it's designed this way.

## How Slash Commands Work

Slash commands (like `/spec-kitty.specify`) are a convention for invoking predefined workflows:

1. **User types** `/spec-kitty.specify` in their AI agent
2. **Agent reads** the corresponding command file (e.g., `.claude/commands/spec-kitty.specify.md`)
3. **Agent executes** the instructions in that file
4. **Agent interacts** with the user and codebase

The command file contains:
- A detailed prompt explaining what to do
- Instructions for user interaction
- References to templates and artifacts

This lets each AI agent execute the same workflow, even though they have different interfaces.

## The Supported Agents

Spec Kitty supports agents in three groups. The canonical lists are `AI_CHOICES` and
`IDE_AGENTS` in `src/specify_cli/core/config.py` and `AGENT_DIRS` in
`src/specify_cli/agent_utils/directories.py`; if this page and those lists disagree,
the code wins.

### CLI slash-command agents

These agents run from the command line and read a per-agent command directory:

| Agent | Directory | Format | CLI Tool |
|-------|-----------|--------|----------|
| Claude Code | `.claude/commands/` | Markdown | `claude` |
| Gemini CLI | `.gemini/commands/` | TOML | `gemini` |
| Qwen Code | `.qwen/commands/` | TOML | `qwen` |
| OpenCode | `.opencode/command/` | Markdown | `opencode` |
| Augment Code (Auggie CLI) | `.augment/commands/` | Markdown | `auggie` |
| Amazon Q Developer CLI (legacy; use Kiro) | `.amazonq/prompts/` | Markdown | `q` |
| Kiro CLI | `.kiro/prompts/` | Markdown | `kiro-cli` |
| LLxprt Code | `.llxprt/commands/` | TOML | `llxprt` |

### IDE slash-command agents

These agents run inside an IDE or editor, so Spec Kitty does not check for a CLI tool:

| Agent | Directory | Format |
|-------|-----------|--------|
| GitHub Copilot | `.github/prompts/` | Markdown |
| Cursor | `.cursor/commands/` | Markdown |
| Windsurf | `.windsurf/workflows/` | Markdown |
| Kilo Code | `.kilocode/workflows/` | Markdown |
| Google Antigravity | `.agent/workflows/` | Markdown |

### Agent Skills agents

These agents share one skills root, `.agents/skills/spec-kitty.<command>/SKILL.md`,
tracked in `.kittify/command-skills-manifest.json`:

| Agent | How commands are invoked |
|-------|--------------------------|
| Codex CLI | `$spec-kitty.<command>` |
| Mistral Vibe | `/spec-kitty.<command>` (via `.vibe/config.toml`) |
| Pi | `/skill:spec-kitty.<command>` |
| Letta Code | Agent Skills |

## Agent-Specific Directories

Each agent has its own directory containing command files:

```
project/
├── .claude/
│   └── commands/
│       ├── spec-kitty.specify.md
│       ├── spec-kitty.plan.md
│       ├── spec-kitty.tasks.md
│       ├── spec-kitty.implement.md
│       ├── spec-kitty.review.md
│       └── spec-kitty.accept.md
│
├── .gemini/
│   └── commands/
│       └── [same commands in TOML format]
│
├── .github/
│   └── prompts/
│       └── [same commands for Copilot]
│
└── ... (the other slash-command agent directories, plus .agents/skills/)
```

Each directory follows the conventions expected by that agent.

## Command Template System

### Shared Logic, Different Formats

All agents execute the same workflow, but their command file formats differ. Spec Kitty maintains a single source of truth:

```
packs/built-in/missions/mission-steps/
└── software-dev/
    ├── specify/prompt.md      # Template content
    ├── plan/prompt.md
    ├── tasks/prompt.md
    └── ...
```

During `spec-kitty init` and `spec-kitty upgrade`, these templates are adapted for each agent:
- **Markdown agents** get `.md` files
- **TOML agents** get `.toml` files with converted syntax
- **Agent Skills agents** get a `SKILL.md` per command under `.agents/skills/`
- **Different arg syntax** (`$ARGUMENTS` vs `{{args}}`) is handled per agent

### Template Structure

Each command template contains:

```markdown
# /spec-kitty.specify - Create Mission Specification

**Purpose**: [What this command does]

## When to Use
[Guidance on when to run this command]

## Workflow
[Step-by-step instructions for the agent]

## Outputs
[What artifacts will be created]

## Example
[Example usage and expected result]
```

### Keeping Templates in Sync

When you upgrade Spec Kitty (`pipx upgrade spec-kitty-cli`, or the equivalent
command for your installer), migrations update all agent directories:

```python
# Example migration: only the agents configured in .kittify/config.yaml
for agent_root, subdir in get_agent_dirs_for_project(project_path):
    agent_dir = project_path / agent_root / subdir
    if not agent_dir.exists():
        continue  # respect deletions; never mkdir
    update_command_template(agent_dir, "specify.md", new_content)
```

This ensures all agents stay synchronized when the workflow changes.

## Multi-Agent Collaboration

### Different Agents on Different WPs

The execution workspace model enables multi-agent collaboration:

```
Mission: 012-user-auth
├── Lane A (WP01, WP02 sequential) → Agent A (Claude Code) in .worktrees/012-user-auth-lane-a/
├── Lane B (parallel API work)     → Agent B (Gemini) in .worktrees/012-user-auth-lane-b/
└── Lane C (parallel UI work)      → Agent C (Copilot) in .worktrees/012-user-auth-lane-c/
```

Each agent:
- Works in its resolved execution workspace
- Has its own resolved branch
- Uses the same command templates
- Follows the same workflow

### Why This Works

All agents:
1. Read the same WP prompt from `tasks/WP##.md`
2. Follow the same implementation workflow
3. Use the same lane transitions (planned → claimed → in_progress → for_review)
4. Produce compatible output (code + commits)

The only difference is which AI model powers each agent.

### Orchestration

You can run multiple agents simultaneously:

```bash
# Terminal 1 (Claude Code)
cd .worktrees/012-user-auth-lane-a
claude "/spec-kitty.implement WP01"

# Terminal 2 (Gemini)
cd .worktrees/012-user-auth-lane-b
gemini "/spec-kitty.implement WP02"

# Terminal 3 (opencode)
cd .worktrees/012-user-auth-lane-c
opencode "/spec-kitty.implement WP03"
```

All three work in parallel without conflicts.

## Why Agent-Agnostic?

### User Choice

Different users prefer different agents:
- Some teams use Claude Code for its reasoning
- Some prefer Copilot for IDE integration
- Some use Gemini for its context handling

Spec Kitty doesn't force a choice—use what works for you.

### Vendor Independence

AI agents evolve rapidly:
- New agents appear regularly
- Existing agents gain new capabilities
- Pricing and availability change

By supporting multiple agents, Spec Kitty isn't locked to any single vendor.

### Team Flexibility

A team might use different agents for different tasks:
- Claude Code for complex implementation work
- Copilot for quick edits and reviews
- Gemini for research tasks

Spec Kitty's workflows work the same regardless of which agent runs them.

## Adding New Agent Support

When a new AI agent appears, Spec Kitty can add support by:

1. **Adding to `AI_CHOICES` and `AGENT_DIRS`**: Update the canonical lists
2. **Creating directory structure**: `.<agent>/commands/` (or agent-specific path)
3. **Converting templates**: Generate command files in the agent's format
4. **Adding CLI checks**: Verify the agent's CLI tool is installed (if CLI-based)

See [Agent Subcommands](../api/agent-subcommands.md) for the workflow command reference.

## Command Execution Flow

```
User: /spec-kitty.implement WP01

    ↓

Agent reads .claude/commands/spec-kitty.implement.md

    ↓

Agent executes workflow:
1. Read WP01 prompt from tasks/WP01.md
2. Resolve or create the execution workspace
3. Navigate to the printed workspace
4. Implement according to WP requirements
5. Run tests
6. Commit changes
7. Move WP to for_review

    ↓

Result: WP01 implemented in the canonical execution workspace
```

The command file provides all instructions; the agent executes them.

## See Also

- [Execution Workspace Model](execution-lanes.md) - How parallel development enables multi-agent collaboration
- [Kanban Workflow](kanban-workflow.md) - How work moves through lanes regardless of agent
- [Mission System](mission-system.md) - How missions customize commands for different work types

---

*This document explains the multi-agent architecture. For how to use specific agents, see the tutorials and how-to guides.*

## Try It

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)
- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)
- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)

## Reference

- [Supported Agents](../api/supported-agents.md)
- [Agent Subcommands](../api/agent-subcommands.md)
