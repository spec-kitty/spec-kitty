---
title: spec-kitty init lifecycle
description: Reference for the spec-kitty init command lifecycle. Understand what files are created, ignored, and how options behave in non-interactive environments.
doc_status: active
updated: '2026-06-15'
type: reference
related:
- docs/api/cli-commands.md
- docs/api/supported-agents.md
- docs/api/upgrade-lifecycle.md
audience: end-users
---
# `spec-kitty init` lifecycle

Reference description of what `spec-kitty init` creates, in what order, and how its options interact. For installation, see [Install on macOS / Linux / Windows](../guides/how-to/installation/install-macos.md).

## Synopsis

```text
spec-kitty init [PROJECT_NAME] [OPTIONS]
```

| Argument | Description |
|---|---|
| `PROJECT_NAME` | Name of a new directory to create. Omit to initialize the current directory. |

| Option | Description |
|---|---|
| `--ai <keys>` | Comma-separated agent keys (`claude`, `codex`, `gemini`, `cursor`, `qwen`, `opencode`, `windsurf`, `kilocode`, `auggie`, `copilot`, `q`, `kiro`, `antigravity`, `vibe`, `pi`, `letta`). Required in non-interactive mode. (`roo` is deprecated and rejected — Roo Code shut down 2026-05-15.) |
| `--non-interactive` / `--yes` / `-y` | Skip all prompts. Equivalent to setting `SPEC_KITTY_NON_INTERACTIVE=1`. |
| `--help` | Show full help (this page is a curated summary). |

> Note: `init` never touches git. It does not run `git init`, does not stage files, and does not create commits. Manage version control yourself.

## What gets created

`spec-kitty init` materializes the following layout. Existing files are preserved; the command is idempotent and can be re-run safely.

### `.kittify/` — project scaffold

Holds spec-kitty's per-project configuration and runtime state. Key contents:

| Path | Purpose |
|---|---|
| `.kittify/config.yaml` | Single source of truth for configured agents and feature flags. |
| `.kittify/metadata.yaml` | Project schema version, used by the upgrade gate. |
| `.kittify/memory/` | Long-lived memory used by the runtime. |
| `.kittify/command-skills-manifest.json` | Tracks which agents reference each command-skill package (Codex/Vibe/Pi/Letta). |

### `kitty-specs/` — mission artifacts

Empty at init time. Populated by `/spec-kitty.specify`, `/spec-kitty.plan`, and `/spec-kitty.tasks`. Each mission becomes a subdirectory.

### Agent command directories

One directory per agent selected via `--ai`. Spec Kitty supports 17 agents total — 13 command-surface agents and 4 command-skill agents. (Roo Code shut down on 2026-05-15 and can no longer be selected; existing `.roo/` directories are preserved on upgrade.)

| Agent key | Directory created | Command surface |
|---|---|---|
| `claude` | `.claude/commands/` | `/spec-kitty.*` |
| `copilot` | `.github/prompts/` | `/spec-kitty.*` |
| `gemini` | `.gemini/commands/` | `/spec-kitty.*` |
| `cursor` | `.cursor/commands/` | `/spec-kitty.*` |
| `qwen` | `.qwen/commands/` | `/spec-kitty.*` |
| `opencode` | `.opencode/command/` | `/spec-kitty.*` |
| `windsurf` | `.windsurf/workflows/` | `/spec-kitty.*` |
| `kilocode` | `.kilocode/workflows/` | `/spec-kitty.*` |
| `auggie` | `.augment/commands/` | `/spec-kitty.*` |
| `q` | `.amazonq/prompts/` | `/spec-kitty.*` |
| `kiro` | `.kiro/prompts/` | `/spec-kitty.*` |
| `antigravity` | `.agent/workflows/` | `/spec-kitty.*` |
| `llxprt` | `.llxprt/commands/` | `/spec-kitty.*` |
| `codex` | `.agents/skills/spec-kitty.*/` | `$spec-kitty.<command>` |
| `vibe` | `.agents/skills/spec-kitty.*/` plus `.vibe/config.toml` | `/spec-kitty.<command>` |
| `pi` | `.agents/skills/spec-kitty.*/` | `/skill:spec-kitty.<command>` |
| `letta` | `.agents/skills/spec-kitty.*/` | agent skills |

Codex, Vibe, Pi, and Letta share a single installation tree under `.agents/skills/`; Vibe also gets a `.vibe/config.toml` `skill_paths` entry pointing at that tree. Only the agents you list in `--ai` get directories.

### Ignore files

- `.gitignore` is created or appended to with a `# spec-kitty` block that excludes execution worktrees and ephemeral runtime files.
- `.claudeignore` (and equivalent for other agents) gets matching entries so agents do not crawl generated state.

## Idempotent behavior

`spec-kitty init` is safe to re-run:

- Existing files are not overwritten.
- Missing files for **configured** agents are recreated.
- Agents that are not in `config.yaml` are left untouched — `init` will not recreate a directory you removed via `spec-kitty agent config remove`.
- Re-running with a different `--ai` list **adds** the new agents but does not remove the old ones. To remove agents, use:

  ```bash
  spec-kitty agent config remove <key>
  spec-kitty agent config sync
  ```

## Non-interactive mode

Non-interactive mode is triggered by any of:

- The `--non-interactive` flag.
- The `--yes` / `-y` flag.
- The `SPEC_KITTY_NON_INTERACTIVE=1` environment variable.
- Running in a non-TTY context (CI, scripts).

In non-interactive mode, `--ai` is **required**. Example:

```bash
spec-kitty init my-project --ai claude,codex --non-interactive
```

## Host selection

The set of installed agent directories is driven by `--ai`. Validate the keys you pass — invalid keys cause `init` to exit non-zero before touching the filesystem.

```bash
# Install only the Claude Code surface
spec-kitty init . --ai claude

# Install Claude + Codex + Cursor
spec-kitty init . --ai claude,codex,cursor
```

You can change the agent set later without re-running `init`:

```bash
spec-kitty agent config add gemini
spec-kitty agent config remove cursor
spec-kitty agent config sync
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Init succeeded (created or already-current). |
| 1 | General error (filesystem permission, invalid agent key, etc.). |
| 2 | Usage error (missing required arg, invalid flag combination). |

## What `init` does not do

- It does not initialize a git repository.
- It does not create any commits.
- It does not run `pipx ensurepath` or modify your shell PATH.
- It does not contact PyPI or any other network resource.
- It does not run migrations — that is the job of `spec-kitty upgrade`.

## Examples

```bash
# Interactive init in current directory
spec-kitty init

# New project directory with Claude
spec-kitty init my-app --ai claude

# Multiple agents, non-interactive (CI)
spec-kitty init . --ai claude,codex --non-interactive

# Add Spec Kitty to an existing repo without polluting it
cd /path/to/existing-repo
spec-kitty init . --ai claude --non-interactive
```

## See also

- [Install on macOS](../guides/how-to/installation/install-macos.md)
- [Upgrade lifecycle](upgrade-lifecycle.md)
- [Non-interactive init](../guides/how-to/installation/non-interactive-init.md)
- [CLI commands reference](cli-commands.md)
- [Supported agents](supported-agents.md)
