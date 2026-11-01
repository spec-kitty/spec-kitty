---
title: 'Naming Decision: Tool vs Agent'
description: "The canonical naming decision separating tool (the concrete execution product) from agent (the logical collaborator identity and role) across Spec Kitty."
doc_status: active
updated: '2026-07-16'
related:
- context
- context/historical-terms
---
# Naming Decision: Tool vs Agent

**Decision date**: 2026-02-15
**Status**: Agreed and active

## Decision

- **Tool**: concrete execution product (Claude Code, Codex, opencode, etc.)
- **Agent**: logical collaborator identity/role in the workflow

## Why

- Avoids overloaded wording where one term means both product and role
- Makes event payloads and docs easier to interpret
- Improves cross-tool comparisons in workflow audits

## Usage Rule

- Use "tool" for install/config/invocation concerns
- Use "agent" for assignment/handoff/role concerns

## Derived Terms

- **Tool surface**: installable, verifiable, or packageable artifact/configuration exposed to a concrete tool (for example a slash command file, skill directory, hook config, MCP config, custom agent profile file, or plugin manifest)
- **Agent profile**: logical collaborator identity/role guidance projected into a tool-native custom-agent/subagent format when supported

## Compatibility Note

Some existing CLI commands and config keys still use historical names such as `spec-kitty agent config` and `.kittify/config.yaml` `agents.available`. New architecture, docs, and schemas should treat those as compatibility aliases for configured tools, not as permission to use "agent" for install/config concepts.
