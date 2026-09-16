---
title: Configuration Reference
description: Reference for Spec Kitty configurations. Explore parameters for meta.json, work package frontmatter, docfx.json, toc.yml, config.yaml's env_file pointer, and agent settings.
doc_status: active
updated: '2026-08-16'
related:
- docs/api/agent-subcommands.md
- docs/api/cli-commands.md
- docs/api/environment-variables.md
- docs/api/file-structure.md
- docs/api/missions.md
- docs/adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md
---
# Configuration Reference

This document describes all configuration files used by Spec Kitty.

---

## env_file Pointer

`.kittify/config.yaml` carries a single top-level pointer key:

```yaml
env_file: ${SPEC_KITTY_HOME}/.kitty.env
```

This is the **one** place a project registers where its operator env-file lives. It is
resolved **once**, at bootstrap, through the kernel's `${VAR}` expansion seam
(`src/kernel/env_expand.py`) — the default value points at the home-tier
`.kitty.env` (`${SPEC_KITTY_HOME}/.kitty.env`), which is then overridden by the per-repo
tier `<repo>/.kittify/.kitty.env` if that file exists. See [Environment Variables
Reference § The `.kitty.env` file](environment-variables.md#the-kittyenv-file) for the
full loader mechanism (two-tier precedence, fail policy, provisioning), and [ADR: operator
config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
for the design rationale.

**Fields**:

| Key | Type | Description |
|-----|------|-------------|
| `env_file` | string | `${VAR}`-expandable pointer to the home-tier `.kitty.env`. Read via a targeted top-level-key scan (not a full YAML/model load), so it never collides with `doctrine.org`'s `extra="forbid"` schema in the same file. |

There is no separate `CONFIG_HOME`-style variable — the pointer is always anchored on the
existing `SPEC_KITTY_HOME` locator, which itself cannot be redefined from inside the file
it locates.

**Provisioning**: `spec-kitty upgrade` provisions this key (idempotently) for projects that
predate the mechanism, alongside creating the per-repo `.kitty.env` scaffold and the
matching `.gitignore` / `.claudeignore` entries.

---

## meta.json (Feature Metadata)

Each feature has a `meta.json` file in its directory that stores metadata about the feature.

**Location**: `kitty-specs/<feature-slug>/meta.json`

**Fields**:

```json
{
  "feature_number": "014",
  "slug": "014-comprehensive-end-user-documentation",
  "friendly_name": "Comprehensive End-User Documentation",
  "mission": "documentation",
  "vcs": "git",
  "source_description": "Original feature description provided during /spec-kitty.specify",
  "created_at": "2026-01-16T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `feature_number` | string | Three-digit feature number (e.g., "014") |
| `slug` | string | Full feature slug including number |
| `friendly_name` | string | Human-readable feature name |
| `mission` | string | Mission type: `software-dev`, `research`, or `documentation` |
| `vcs` | string | VCS backend: `git` (auto-detected if not specified) |
| `source_description` | string | Original description from `/spec-kitty.specify` |
| `created_at` | string | ISO 8601 timestamp of creation |

> **VCS Lock**: Once a feature is created, its VCS is locked in `meta.json`. All workspaces for that feature use the same VCS backend. This ensures consistency across work packages.

---

## work package frontmatter

Each work package file (`tasks/WP##-*.md`) contains YAML frontmatter that tracks its status.

**Location**: `kitty-specs/<feature-slug>/tasks/WP##-*.md`

**Fields**:

```yaml
---
work_package_id: "WP01"
title: "Setup and Configuration"
lane: "planned"
dependencies: ["WP00"]
subtasks:
  - "T001"
  - "T002"
  - "T003"
phase: "Phase 1 - Foundation"
assignee: ""
agent: ""
shell_pid: ""
review_status: ""
reviewed_by: ""
review_feedback: ""
history:
  - timestamp: "2026-01-16T12:00:00Z"
    lane: "planned"
    agent: "system"
    shell_pid: ""
    action: "Prompt generated via /spec-kitty.tasks"
---
```

| Field | Type | Description |
|-------|------|-------------|
| `work_package_id` | string | WP identifier (e.g., "WP01") |
| `title` | string | work package title |
| `lane` | string | Current lane: `planned`, `claimed`, `in_progress`, `for_review`, `in_review`, `approved`, `done`, `blocked`, `canceled`. Alias: `doing` → `in_progress`. `approved` means review passed and merge pending; `done` means merged/integrated. |
| `dependencies` | list | WP IDs this WP depends on |
| `subtasks` | list | Task IDs belonging to this WP |
| `phase` | string | Development phase |
| `assignee` | string | Human assignee name |
| `agent` | string | AI agent type (e.g., "claude") |
| `shell_pid` | string | Process ID of implementing agent |
| `review_status` | string | Empty, `has_feedback`, or `approved` |
| `reviewed_by` | string | Reviewer name |
| `review_feedback` | string | Feedback pointer to persisted artifact (for example, `feedback://001-feature/WP01/20260227T120000Z-ab12cd34.md`) |
| `history` | list | Activity log entries |

---

## docfx.json (Documentation Build)

DocFX configuration for building the documentation site.

**Location**: `docs/docfx.json`

**Key sections**:

```json
{
  "build": {
    "content": [
      {
        "files": [
          "*.md",
          "tutorials/*.md",
          "how-to/*.md",
          "reference/*.md",
          "explanation/*.md",
          "toc.yml"
        ]
      }
    ],
    "resource": [
      {
        "files": ["assets/**"]
      }
    ],
    "dest": "_site",
    "template": ["default", "modern"],
    "globalMetadata": {
      "_appTitle": "Spec Kitty Documentation",
      "_enableSearch": true
    }
  }
}
```

| Section | Description |
|---------|-------------|
| `content.files` | Markdown files to include |
| `resource.files` | Static assets (images, CSS) |
| `dest` | Output directory (don't commit this) |
| `template` | DocFX templates to use |
| `globalMetadata` | Site-wide settings |

---

## toc.yml (Table of Contents)

Defines the documentation navigation structure.

**Location**: `docs/toc.yml`

**Format**:

```yaml
- name: Home
  href: index.md

- name: Tutorials
  items:
    - name: Getting Started
      href: tutorials/getting-started.md
    - name: Your First Mission
      href: tutorials/your-first-mission.md

- name: How-To Guides
  items:
    - name: Install & Upgrade
      href: how-to/install-spec-kitty.md
```

Each entry has:
- `name`: Display text in navigation
- `href`: Path to markdown file
- `items`: Nested navigation items (optional)

---

## charter.md (Project Principles)

Optional file defining project-wide coding principles and standards.

**Location**: `.kittify/charter/charter.md`

**Purpose**: When present, all slash commands reference these principles. Claude and other agents will follow these guidelines during implementation.

**Example**:

```markdown
# Project Charter

## Code Quality Principles

1. All APIs must have rate limiting
2. All database queries must use parameterized statements
3. All user input must be validated
4. Test coverage must be at least 80%

## Architecture Principles

1. Use dependency injection for testability
2. Separate business logic from infrastructure
3. Document all public APIs
```

**Creating**: Use `/spec-kitty.charter` to interactively create this file.

---

## Mission Configuration (Advanced)

Mission-specific templates and configuration.

**Location**: `.kittify/missions/<mission-key>/`

**Structure**:

```
.kittify/missions/
├── software-dev/
│   └── mission.yaml
├── research/
│   └── mission.yaml
└── documentation/
    └── mission.yaml
```

**mission.yaml fields**:

```yaml
key: software-dev
name: Software Development
domain: Building software features
phases:
  - research
  - design
  - implement
  - test
  - review
artifacts:
  - spec.md
  - plan.md
  - tasks.md
  - data-model.md
```

---

## VCS configuration

Spec Kitty uses Git as the version control backend. Configuration options control VCS detection and behavior.

### Project-Level VCS Settings

Spec Kitty uses git for version control. Once a feature is created, its VCS is locked in `meta.json`:

```json
{
  "slug": "016-documentation",
  "vcs": "git"
}
```

All work packages for that feature use the same VCS backend, ensuring consistency.

### Checking Current VCS

Use `spec-kitty verify-setup --diagnostics` to see which VCS is active:

```bash
$ spec-kitty verify-setup --diagnostics
VCS Backend: git
```

---

## Agent Configuration

Spec Kitty supports AI agents across different platforms. Agent configuration is stored in `.kittify/config.yaml` and can be managed via CLI commands. Slash-command agents use user-global command roots; Codex, Vibe, Pi, and Letta Code use project-local command skills under `.agents/skills/`.

### Supported Agents

| Agent Key | Managed Surface | Platform |
|-----------|-----------------|----------|
| `claude` | `~/.claude/commands/` | Claude (Anthropic) |
| `copilot` | `~/.github/prompts/` | GitHub Copilot |
| `gemini` | `~/.gemini/commands/` | Google Gemini |
| `llxprt` | `~/Library/Preferences/llxprt-code/commands/` (macOS) | LLxprt Code |
| `cursor` | `~/.cursor/commands/` | Cursor AI |
| `qwen` | `~/.qwen/commands/` | Qwen Code |
| `opencode` | `~/.opencode/command/` | OpenCode |
| `windsurf` | `~/.windsurf/workflows/` | Windsurf |
| `codex` | `.agents/skills/spec-kitty.<command>/` | Codex CLI |
| `pi` | `.agents/skills/spec-kitty.<command>/` | Pi |
| `letta` | `.agents/skills/spec-kitty.<command>/` | Letta Code |
| `kilocode` | `~/.kilocode/workflows/` | Kilocode |
| `auggie` | `~/.augment/commands/` | Augment Code |
| `q` | `~/.amazonq/prompts/` | Amazon Q |

> **Roo Cline (`roo`) is deprecated.** Roo Code shut down on 2026-05-15; `spec-kitty init --ai roo` is rejected. Existing `.roo/` directories are preserved and a deprecation notice is shown on `spec-kitty upgrade`. Remove it with `spec-kitty agent config remove roo`.

### Configuration File

Agent configuration is stored in `.kittify/config.yaml`:

```yaml
agents:
  available:
    - opencode
    - claude
```

| Field | Type | Description |
|-------|------|-------------|
| `agents.available` | list | Agents enabled for this project |

### Config-Driven Agent Management

Starting in spec-kitty 0.12.0, agent configuration follows a config-driven model where `.kittify/config.yaml` is the single source of truth for which agents are active in your project.

**Key principles**:
- Active agents are derived from `config.yaml`
- Slash-command files are installed globally at CLI startup
- Codex, Vibe, Pi, and Letta command skills are project-local under `.agents/skills/`
- Migrations respect `config.yaml` - only process configured agents
- Use `spec-kitty agent config` commands to manage agents (not manual editing)

**Schema**:
```yaml
agents:
  available:
    - claude
    - codex
    - opencode
```

**Fields**:
- `available` (list): Agent keys currently active in project

**See**:
- [Managing AI Agents](../guides/how-to/collaboration/manage-agents.md) - Complete guide to agent management commands
- [CLI Reference: spec-kitty agent config](agent-subcommands.md#spec-kitty-agent-config) - Command syntax and options
- [ADR #6: Config-Driven Agent Management](https://github.com/Priivacy-ai/spec-kitty/blob/main/docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md) - Architectural decision rationale

> **Legacy behavior**: Projects without `agents.available` field default to the full slash-command agent set for backward compatibility (currently 13 agent keys in the active CLI surface). To adopt config-driven model, use `spec-kitty agent config remove` to remove unwanted agents.

### Managing Agents

#### List Configured Agents

```bash
spec-kitty agent config list
```

Output:
```
Configured agents:
  ✓ opencode (~/.opencode/command/ (global))
  ✓ claude (~/.claude/commands/ (global))

Available but not configured:
  - codex, copilot, gemini, ...
```

#### Add Agents

```bash
spec-kitty agent config add claude codex
```

This command:
1. Registers slash-command agents against their global command roots
2. Installs project-local command skills for Codex, Vibe, Pi, and Letta
3. Updates `config.yaml` to include new agents

#### Remove Agents

```bash
spec-kitty agent config remove codex gemini
```

This command:
1. Deletes agent directories
2. Updates `config.yaml` to remove agents

**Options:**
- `--keep-config`: Delete directory but keep in config (useful for temporary removal)

#### Check Agent Status

```bash
spec-kitty agent config status
```

Shows a table of all agents with their status:
- **OK**: Configured and managed command surface exists
- **Missing**: Configured but managed command surface doesn't exist
- **Orphaned**: Directory exists but not configured
- **Not used**: Neither configured nor present

Example output:
```
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ Agent Key ┃ Directory           ┃ Configured ┃ Exists ┃ Status   ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│ opencode  │ ~/.opencode/command/ (global)     │ ✓ │ ✓ │ OK       │
│ claude    │ ~/.claude/commands/ (global)      │ ✓ │ ✓ │ OK       │
│ codex     │ .agents/skills/ (project skills)  │ ✗ │ ✓ │ Orphaned │
└───────────┴─────────────────────┴────────────┴────────┴──────────┘

⚠ 1 orphaned directory found (present but not configured)
```

#### Sync Filesystem with Config

```bash
spec-kitty agent config sync
```

Synchronizes filesystem with `config.yaml`:
- By default, removes orphaned directories (present but not configured)
- Use `--create-missing` to check configured managed surfaces and restore supported project-local skill roots
- Use `--keep-orphaned` to keep orphaned directories

**Examples:**

```bash
# Remove orphaned agents (default)
spec-kitty agent config sync

# Create missing directories for configured agents
spec-kitty agent config sync --create-missing

# Keep orphaned directories
spec-kitty agent config sync --keep-orphaned
```

### Agent Selection During Init

When creating a new project, select agents interactively or via CLI:

```bash
# Interactive selection
spec-kitty init myproject

# CLI selection
spec-kitty init myproject --ai opencode,claude

# Single agent
spec-kitty init myproject --ai opencode
```

Selected agents are stored in `config.yaml` and their directories are created automatically.

### Migration Behavior

**Important:** Migrations respect `config.yaml` as the single source of truth.

- **Upgrades only process configured agents** - If you remove an agent, upgrades won't recreate it
- **Deleted agents stay deleted** - Manual deletions are respected
- **Legacy projects fallback gracefully** - Projects without `config.yaml` process the full supported slash-command agent set

This ensures your agent preferences are preserved across upgrades.

### Troubleshooting

**Q: Why did upgrade recreate agents I deleted?**

This was a bug in versions prior to 0.12.0. Upgrade to the latest version and use `spec-kitty agent config remove` instead of manual deletion.

**Q: How do I add an agent I initially skipped?**

```bash
spec-kitty agent config add <agent-key>
```

**Q: Can I use multiple agents in one project?**

Yes! Configure multiple agents in `config.yaml` and they'll be used according to your selection strategy (`preferred` or `random`).

**Q: What if I manually deleted agent directories?**

Use `spec-kitty agent config sync` to clean up the config or `--create-missing` to recreate them.

---

## Legacy Configuration

### .kittify/active-mission (Deprecated)

**Status**: Deprecated in v0.8.0+

Previously stored the project-wide active mission. Now missions are per-feature and stored in `meta.json`.

If you see this file in older projects, it will be ignored. The mission in each feature's `meta.json` takes precedence.

---

## See Also

- [File Structure](file-structure.md) — Directory layout reference
- [Environment Variables](environment-variables.md) — Runtime configuration
- [Missions](missions.md) — Mission types and their artifacts
- [CLI Commands](cli-commands.md) — Command reference including `--vcs` flag

## Getting Started

- [Claude Code Integration](../guides/tutorials/claude-code-integration.md)

## Practical Usage

- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)
- [Upgrade to 0.11.0](../guides/how-to/installation/install-and-upgrade.md)
