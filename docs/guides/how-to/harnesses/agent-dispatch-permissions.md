---
title: Set Agent Dispatch Permissions
description: 'How Spec Kitty dispatches implementer and reviewer agents with their sandbox and approvals on, how to allow the git and spec-kitty commands they need, and what choosing elevated dispatch means.'
doc_status: active
updated: '2026-10-21'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/harnesses/index.md
---
# Set Agent Dispatch Permissions

When the `spec-kitty-implement-review` skill runs a mission, the orchestrating
agent starts other coding agents to implement and review work packages. Each
dispatch command it ships keeps that agent's sandbox or approval prompts on. No
shipped skill tells an agent to turn them off; a gate test
(`tests/architectural/test_no_unsandboxed_agent_dispatch.py`) fails if one does.

## What the dispatched agent may do by default

| Agent | Shipped mode | `git` and `spec-kitty` |
|-------|--------------|------------------------|
| Codex | `--sandbox workspace-write --add-dir <repo-root>` | Run inside the sandbox; writes limited to the workspace and the repository root checkout; network off |
| Gemini | `--approval-mode auto_edit` | Denied in a headless run until you allow them |
| Qwen Code | `--approval-mode auto-edit` | Denied in a headless run until you allow them |
| LLxprt Code | `--approval-mode=auto_edit` | Denied in a headless run until you allow them |
| Copilot | `--allow-tool 'write' --allow-tool 'shell(git:*)' --allow-tool 'shell(spec-kitty:*)'` | Allowed; `git push` denied |
| Cursor | print mode without `--force` | Denied until you allow them |
| Kilocode | no automatic approval | Denied until you allow them |

When a dispatched agent cannot run `spec-kitty agent tasks move-task`, the
orchestrator runs it after the agent finishes, as it does for agents with no
command line. Nothing is lost; the work package just moves one step later.

## Allow only the commands the agent needs

Allow `git` and `spec-kitty`, and nothing broader, in the agent's own
permission settings:

- **Gemini**: a policy file under `~/.gemini/policies/` with one rule per
  command, for example `toolName = "run_shell_command"`,
  `commandPrefix = "git"`, `decision = "allow"`.
- **Cursor**: `.cursor/cli.json` permissions `Shell(git)` and `Shell(spec-kitty)`.
- **Kilocode**: a `bash` permission map in its config that allows `git *` and
  `spec-kitty *` and denies `*`.
- **Qwen Code** and **LLxprt Code**: their allowed-tools setting for the shell
  tool, in the form your installed version documents.

Check the exact syntax against your installed version; these settings change
between releases.

## Elevated dispatch is your decision

Every agent also has a mode that switches its sandbox or approvals off
entirely, for example Codex `--sandbox danger-full-access`, Gemini and Qwen
`--yolo`, Copilot `--allow-all-tools`, Cursor `--force` and Kilocode `--auto`.
In that mode the dispatched agent can change any file you can and reach the
network, without asking.

Spec Kitty never picks that mode for you. If you decide you want it, tell the
orchestrating agent in the session, naming the agent: for example "dispatch
the Codex reviewer with `--sandbox danger-full-access` for this mission". The
skill only follows such an explicit instruction, and records in the work
package note that the agent ran without a sandbox. Spec Kitty's orchestrator
API rejects a dispatch policy that lists the best-known of these flags
(`BANNED_FLAGS`).
