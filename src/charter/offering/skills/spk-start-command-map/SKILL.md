---
name: spk-start-command-map
description: "Map Spec Kitty slash commands and CLI entry points to spk skills. Use when choosing /spec-kitty.* commands or explaining command-skill boundaries."
---

# spk-start-command-map

Route command questions without conflating command wrappers and operating
skills.

## Flow

1. Read `references/command-map.md`.
2. Choose the command for execution and the `spk-*` skill for operating
   guidance.
3. If the user asks for discovery rather than a command, route to
   `spk-meta-skill-map`.

## Boundary

`/spec-kitty.<command>` files are generated slash-command or prompt-command
surfaces. `spec-kitty-<command>` command skills are generated under
`.agents/skills/` for skill hosts (`$spec-kitty-<command>` in Codex,
`/skill:spec-kitty-<command>` in Pi, `/spec-kitty-<command>` in Vibe, Letta and
Antigravity). `spk-*` skills are user-facing operating guides. Keep the surfaces
distinct: `spec-kitty.<command>` slash commands and `spec-kitty-<command>`
command skills are executable command surfaces; hierarchical `spk-*` names are
operating guidance.
