# Agent Path Matrix

Reference: Framework capability matrix for Spec Kitty 2.0.11+

## Skill Roots and Wrapper Roots by Agent

Canonical Spec Kitty doctrine skills are now managed in the user's home
directory and projected into project roots as needed. That means a CLI upgrade
refreshes the canonical pack once under the user home; projects should not need
fresh per-repo snapshots of `spec-kitty-*` skills.

| Agent | Key | Installation Class | Canonical User Root | Project Skill Root(s) | Wrapper Root |
|-------|-----|-------------------|---------------------|-----------------------|--------------|
| Claude Code | `claude` | native-root-required | `~/.claude/skills/` | `.claude/skills/` | `.claude/commands/` |
| GitHub Copilot | `copilot` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.github/skills/` | `.github/prompts/` |
| Gemini CLI | `gemini` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.gemini/skills/` | `.gemini/commands/` |
| LLxprt Code | `llxprt` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.llxprt/skills/` | `.llxprt/commands/` |
| Cursor | `cursor` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.cursor/skills/` | `.cursor/commands/` |
| Qwen Code | `qwen` | native-root-required | `~/.qwen/skills/` | `.qwen/skills/` | `.qwen/commands/` |
| opencode | `opencode` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.opencode/skills/` | `.opencode/command/` |
| Windsurf | `windsurf` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.windsurf/skills/` | `.windsurf/workflows/` |
| Codex CLI | `codex` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/` | _(none; command skills)_ |
| Mistral Vibe | `vibe` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/` | _(none; command skills)_ |
| Pi | `pi` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.pi/skills/` | _(none; command skills)_ |
| Letta Code | `letta` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/` | _(none; command skills)_ |
| Kilo Code | `kilocode` | native-root-required | `~/.kilocode/skills/` | `.kilocode/skills/` | `.kilocode/workflows/` |
| Auggie CLI | `auggie` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.augment/skills/` | `.augment/commands/` |
| Roo Code | `roo` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.roo/skills/` | `.roo/commands/` |
| Amazon Q Developer CLI | `q` | wrapper-only | _(none)_ | _(none)_ | `.amazonq/prompts/` |
| Kiro CLI | `kiro` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.kiro/skills/` | `.kiro/prompts/` |
| Google Antigravity | `antigravity` | shared-root-capable | `~/.agents/skills/` | `.agents/skills/`, `.agent/skills/` | `.agent/workflows/` |

## Installation Classes

### native-root-required

Agents in this class require skills to be placed under their own directory tree.
They do not read from the shared `.agents/skills/` root.

**Agents:** Claude Code, Qwen Code, Kilo Code

### shared-root-capable

Agents in this class can read skills from the shared `.agents/skills/` root in
addition to their agent-specific skill root. When both exist, the agent-specific
root takes precedence.

**Agents:** GitHub Copilot, Gemini CLI, LLxprt Code, Cursor, opencode, Windsurf,
Codex CLI, Mistral Vibe, Pi, Letta Code, Auggie CLI, Roo Code, Kiro CLI, Google Antigravity

(LLxprt Code is the exception on precedence: its workspace `.agents/skills/`
outranks `.llxprt/skills/`.)

### wrapper-only

Agents in this class do not support a skill root directory. Skills are delivered
exclusively through wrapper slash commands in the wrapper root.

**Agents:** Amazon Q Developer CLI

## Notes

- The shared root `.agents/skills/` is created once and referenced by all
  shared-root-capable agents. Files are projected from the canonical managed
  copy in `~/.agents/skills/` as plain copies, never symlinks — an absolute
  symlink dangles when the repo is mounted into a dev-container and is
  unreadable to sandboxed harnesses (#2412). The projection is refreshed on
  every init/upgrade/repair run.
- Managed canonical files under the user home are read-only. If a project replaces
  one of its projected files locally, that is treated as drift and can be repaired.
- Wrapper roots contain slash-command files (e.g., `spec-kitty.implement.md`)
  that agents use for `/spec-kitty.implement` style invocation.
- When verifying an installation, check the skill root(s) first, then the
  wrapper root. A missing wrapper root means slash commands are unavailable
  even if skills are correctly installed.
