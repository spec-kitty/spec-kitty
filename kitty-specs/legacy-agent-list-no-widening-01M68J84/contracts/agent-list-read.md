# Contract — how the agent list read answers "which agents are in play?"

Owner: `get_agent_dirs_for_project()` (`src/specify_cli/agent_utils/directories.py`).
Consumers: the upgrade migration chain, `doctor`'s slash-command audit, shim generation,
`agent_utils.ignore_entries`, `agent config` fallbacks.

The read has exactly four answers. Each is a contract with the consumers, and #6501 made
the third one honest.

| `.kittify/config.yaml` | `available` | Answer | Raises? |
|---|---|---|---|
| absent, no `agents`/`tools` section, or a section without `available` | not stated | **observed set** — the `AGENT_DIRS` entries the project already has (see below) | no, but logs one warning per project per process |
| any | `[claude]` | exactly the stated agents, in `AGENT_DIRS` order | no |
| any | `[]` (stated empty) | no agents (#6494) | no |
| unreadable / invalid YAML / wrong shape / unknown key | — | nothing | `AgentConfigError` naming the remedy (#6494) |

## The observed set

An `AGENT_DIRS` entry `(agent_root, subdir)` is observed when the project has the agent's
own directory — `<agent_root>/` — because those names are agent-specific and a pre-3.1.2
layout holds one without its managed `<subdir>` yet. `.github` is the exception: every
repository with CI has one, so for it the managed surface `.github/prompts/` is the signal.

The probe is project-local by design: no `$HOME`, no user-global command directory, no
filesystem writes. Identical project trees answer identically on any machine.

## What the contract forbids

- **Widening.** A config that states no list never yields an agent the project does not
  have. A project with no agent directory at all yields no agents.
- **Inventing.** The read never creates a directory; a consumer that wants to create a
  surface asks for it explicitly (`agent config add`, `sync --create-missing`).
- **Refusing on upgrade.** The read never raises for a *valid* config without a list. The
  migration chain reads it before any list could be recorded, so a refusal there would
  abort a legacy project's upgrade (ADR `docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md`).

## Related contract that deliberately differs

`ignored_agent_keys()` (`agent_utils/ignore_entries.py`) keeps **every** agent for a config
with no list. Over-ignoring generated files only keeps untracked files out of `git status`;
over-*acting* rewrites a user's files. The asymmetry is intentional and recorded in both
places.
