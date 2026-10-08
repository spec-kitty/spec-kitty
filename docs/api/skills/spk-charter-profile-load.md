---
title: "spk-charter-profile-load"
description: "Load a Spec Kitty agent profile on demand for interactive sessions, outside the mission runtime loop."
doc_status: active
updated: '2026-10-07'
related: [docs/api/skills/index.md]
---

# spk-charter-profile-load

## What it does

Loads a single agent profile — identity, governance scope, boundaries, and
initialization declaration — so your harness session can adopt that role for
the current conversation. It does not touch mission state.

## When to reach for it

Use it when you want your agent to *behave as* a specific role (architect,
reviewer, implementer, curator, and so on) without a mission running, or when
you want to switch roles mid-conversation. If a mission is already running,
`spec-kitty next` assigns profiles automatically — you don't need this skill
for that path.

## Trigger phrase

There is no single fixed invocation string; harnesses route natural-language
requests like "act as the architect," "load the reviewer profile," or
"initialize profile" to this skill (see the [Agent Profiles
reference](../agent_profiles/index.md) for the full profile catalog).

## Flow

1. Identify the requested profile and any active mission context.
2. Load only that profile's initialization declaration and relevant
   boundaries — not the full doctrine catalog.
3. Apply the role for the current session or routed task.
4. Return to the runtime-next skill for mission advancement.

## What it does not do

It does not create new profiles (use the charter synthesize workflow or edit
the profile YAML directly) and it does not drive mission advancement — that's
`spk-run-next`'s job.

## Detailed mechanics

For the detailed step-by-step mechanics (profile resolution, boundary
checks, doctrine pull, handoff conventions), read the skill's
`references/profile-load-mechanics.md`.
