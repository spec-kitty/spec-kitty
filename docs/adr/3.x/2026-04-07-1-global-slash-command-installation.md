---
title: Global Slash Command Installation
description: 'Slash command files install once into machine-level agent directories at CLI startup; init stops writing them and a migration deletes the per-project copies.'
status: Accepted
date: '2026-04-07'
---

**Amended by:** ADR [2026-10-20-1](../4.x/2026-10-20-1-command-skills-use-spec-conformant-names.md) (home-folder writer scoped to configured agents; `antigravity` row removed).

## Context and Problem Statement

Spec-kitty writes slash command files (e.g., `spec-kitty.plan.md`, `spec-kitty.implement.md`) into each project's agent command directories (`.claude/commands/`, `.gemini/commands/`, etc.) during `spec-kitty init`. This has three consequences:

1. **Per-project friction**: every new repository requires `spec-kitty init` before slash commands are available.
2. **Per-upgrade friction**: every repository requires `spec-kitty upgrade` after each CLI upgrade to get updated command files.
3. **Repository churn**: 13 agents × 16 commands = up to 208 generated files that must be gitignored or tracked in every consumer project.

Skills were already globalized in commit `cea2d8de` using `ensure_global_agent_skills()`, called at every CLI startup — they install to `~/.claude/skills/`, `~/.agents/skills/`, etc. without any per-project action required. Commands must follow the same pattern.

## Decision Drivers

* **Zero-setup experience**: a user who installs `spec-kitty-cli` should have all slash commands available in every project immediately, without running `spec-kitty init`.
* **Automatic upgrades**: upgrading the CLI via `pipx upgrade` must update slash commands everywhere, without per-project `spec-kitty upgrade`.
* **Consistency with skills model**: skills are already global; diverging the commands model creates unnecessary conceptual overhead.
* **No project-level override requirement**: project-level command customization is not a supported use case and does not justify per-project installation.

## Decision

Install all 16 slash command files globally to `~/.<agent-dir>/` at every CLI startup, using the same version-locked bootstrap pattern as skills. Remove command installation from `spec-kitty init` entirely. Provide a migration that removes existing project-level command files from upgraded projects.

## Considered Options

* **Option A: Keep per-project, fix the upgrade friction** — automatic per-project upgrade on each CLI invocation. Rejected: still pollutes project directories with generated files; complex to implement safely in multi-worktree environments.
* **Option B: Global-only installation** ← **Chosen**
* **Option C: Global install + optional project-level override** — allow projects to override individual commands in `.claude/commands/`. Deferred: no current demand; can be added later if needed.

## Decision Outcome

**Option B: Global-only installation**

Commands are installed to the global agent command roots on every CLI startup. The startup hook (`ensure_global_agent_commands()`) mirrors `ensure_global_agent_skills()` exactly: fast-path version check, exclusive lock for writes, version file written last. Project directories no longer contain `spec-kitty.*` command files.

### All 13 Agents and Their Global Command Roots

| Agent key | Tool name | Global command dir | File extension | Arg format |
|---|---|---|---|---|
| `claude` | Claude Code | `~/.claude/commands/` | `.md` | `$ARGUMENTS` |
| `copilot` | GitHub Copilot | `~/.github/prompts/` | `.prompt.md` | `$ARGUMENTS` |
| `gemini` | Gemini CLI | `~/.gemini/commands/` | `.toml` | `{{args}}` |
| `cursor` | Cursor | `~/.cursor/commands/` | `.md` | `$ARGUMENTS` |
| `qwen` | Qwen Code | `~/.qwen/commands/` | `.toml` | `{{args}}` |
| `opencode` | opencode | `~/.opencode/command/` | `.md` | `$ARGUMENTS` |
| `windsurf` | Windsurf | `~/.windsurf/workflows/` | `.md` | `$ARGUMENTS` |
| `codex` | GitHub Codex | `~/.codex/prompts/` | `.md` (hyphens→underscores) | `$ARGUMENTS` |
| `kilocode` | Kilo Code | `~/.kilocode/workflows/` | `.md` | `$ARGUMENTS` |
| `auggie` | Augment Code | `~/.augment/commands/` | `.md` | `$ARGUMENTS` |
| `roo` | Roo Code | `~/.roo/commands/` | `.md` | `$ARGUMENTS` |
| `q` | Amazon Q | `~/.amazonq/prompts/` | `.md` | `$ARGUMENTS` |
| `antigravity` | Google Antigravity | `~/.agent/workflows/` | `.md` | `$ARGUMENTS` |

Global root = `Path.home() / AGENT_COMMAND_CONFIG[agent_key]["dir"]`

### Implementation

1. **`src/specify_cli/runtime/agent_commands.py`** — new module mirroring `agent_skills.py`. `ensure_global_agent_commands()` installs all 16 commands (9 prompt-driven + 7 CLI shims) for all 13 agents. Version lock: `~/.kittify/cache/agent-commands.lock`. Per-agent failures are caught and logged; one agent's failure does not block others.

2. **`src/specify_cli/__init__.py`** — `ensure_global_agent_commands()` called in `main_callback()` after `ensure_global_agent_skills()`.

3. **`src/specify_cli/cli/commands/init.py`** — `generate_agent_assets()` and `generate_all_shims()` calls removed. `init` no longer writes project-level command files.

4. **`src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py`** — migration that removes existing `spec-kitty.*` command files from all configured agent directories in consumer projects on `spec-kitty upgrade`.

### Consequences

#### Positive

* No `spec-kitty init` required for commands — CLI installation is sufficient.
* No per-project `spec-kitty upgrade` required for command updates.
* Consumer projects are not polluted with up to 208 generated files.
* Consistent with the skills globalization model established in `cea2d8de`.

#### Negative

* Commands are no longer project-scoped — they cannot vary per-project without explicit override infrastructure (not currently supported).
* `~/.github/prompts/` (copilot) is written at user-home scope, outside the typical `.github/` project scope. Users who rely on copilot in multiple GitHub accounts on one machine will share one command set.

#### Neutral

* `_resolve_mission_command_templates_dir()` remains in `init.py` for potential future per-project override support but is not called by default.
* The migration is idempotent: a project with no `spec-kitty.*` command files triggers `detect() == False` and is skipped.

## More Information

**Related ADRs:**
* `cea2d8de` commit — skills globalization (the model this decision follows)

**References:**
* `src/specify_cli/runtime/agent_commands.py` — implementation
* `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py` — cleanup migration
* `src/specify_cli/core/config.py` — `AGENT_COMMAND_CONFIG`
* `src/doctrine/skills/spec-kitty-setup-doctor/references/agent-path-matrix.md` — full agent path matrix
