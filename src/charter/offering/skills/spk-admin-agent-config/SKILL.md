---
name: spk-admin-agent-config
description: "Configure Spec Kitty agent profiles, host-specific paths, command installation, and model/tool routing."
---

# spk-admin-agent-config

Use this skill when the user needs to configure Codex, Claude, OpenCode, or
another agent for Spec Kitty.

## Flow

1. Identify the active host and project root.
2. Verify skill and command install locations for that host.
3. Confirm the agent name used by `spec-kitty next --agent <name>`.
4. Load profile doctrine through `spk-charter-profile-load` when needed.
5. Use `spk-start-agent-surface` for host capability differences.

## Rule

Keep host configuration separate from mission content.
