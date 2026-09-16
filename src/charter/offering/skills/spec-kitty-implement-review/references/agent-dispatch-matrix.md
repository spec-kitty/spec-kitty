# Agent Dispatch Matrix

Quick reference for dispatching work to each supported agent.

## Tier 1 -- Full Headless CLI

These agents can be dispatched autonomously. They can run shell commands
including `spec-kitty agent tasks move-task`.

| Agent | Config Key | CLI Template | Notes |
|-------|-----------|--------------|-------|
| Claude Code | `claude` | `claude -p "<prompt>" --output-format json -C <dir>` | Gold standard. Supports `--allowedTools`. |
| GitHub Codex | `codex` | `cat prompt.md \| codex exec --sandbox danger-full-access -C <dir> -` | Stdin only (no positional prompt with `-C`). Use `--add-dir` for read access to the repository root checkout. `move-task` writes git/status locks, so `workspace-write`/`--full-auto` is too narrow. |
| Google Gemini | `gemini` | `gemini -p "<prompt>" --yolo --output-format json -C <dir>` | Large context window (1M tokens). |
| LLxprt Code | `llxprt` | `cd <dir> && llxprt -p "<prompt>" --approval-mode=yolo` | Bun-based Gemini CLI fork. No `-C` and no `--output-format json`; `cd` into the workspace first. Model profiles via `--profile-load <name>`. When a mission step needs a user process decision (PR-based flow vs direct commit, mission scope, merge strategy), call `todo_pause` with the question as the reason *before* asking it: the todo continuation auto-advances any turn that ends without a tool call, so a plain-text question never reaches the user. Do not pause for tactical implementation choices; proceed with best judgment. |
| GitHub Copilot | `copilot` | `copilot -p "<prompt>" --yolo --silent` | Requires GitHub Copilot subscription. |
| OpenCode | `opencode` | `opencode run "<prompt>" --format json -C <dir>` | Multi-provider support. |
| Qwen Code | `qwen` | `qwen -p "<prompt>" --yolo --output-format json -C <dir>` | Fork of Gemini CLI, identical interface. |
| Kilocode | `kilocode` | `kilocode -a --yolo -j "<prompt>" -C <dir>` | Supports `--parallel` for branch isolation. |
| Augment Code | `auggie` | `auggie --acp "<prompt>" -C <dir>` | ACP mode for non-interactive operation. |
| Antigravity | `antigravity` | Google agent framework dispatch | Varies by configuration. |

## Tier 2 -- Workaround Required

| Agent | Config Key | CLI Template | Workaround |
|-------|-----------|--------------|------------|
| Cursor | `cursor` | `timeout 600 cursor agent -p --force --output-format json "<prompt>"` | May hang after completion. Always wrap with `timeout`. Not recommended for review role. |

## Tier 3 -- GUI Only (Manual Dispatch)

These agents have no stable CLI. The orchestrator prints instructions for
the human operator and runs `move-task` on the agent's behalf after completion.

| Agent | Config Key | Limitation |
|-------|-----------|------------|
| Windsurf | `windsurf` | GUI-only, no CLI dispatch |
| Roo Cline | `roo` | No official CLI |
| Amazon Q | `q` | Transitioning, unstable CLI |

## Dispatch Decision Tree

```
Is the agent Tier 1?
  YES --> Dispatch via CLI (fire and forget)
  NO  --> Is it Tier 2?
    YES --> Dispatch with timeout wrapper
    NO  --> Print manual instructions, wait for human, run move-task yourself
```

## Cross-Agent Review (Recommended)

For best results, use a different agent for review than implementation:

```yaml
# .kittify/config.yaml
agents:
  selection:
    preferred_implementer: claude
    preferred_reviewer: codex    # Different agent reduces blind spots
```

When only one agent is available, spec-kitty enables single-agent mode
automatically. A 30-second delay between implementation and self-review
helps reduce context carryover.
