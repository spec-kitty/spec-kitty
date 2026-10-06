---
title: "spk-start-here"
description: "Start here for Spec Kitty. Orient CLI users and supported agent-harness users; choose the right command, skill family, and recovery path."
doc_status: active
updated: '2026-10-06'
related: [docs/api/skills/index.md]
---

# spk-start-here

## What it does

Orients you by *where you're working* — command line or a supported agent
harness — then routes to the smallest useful workflow. It names Spec Kitty's
three visible layers (commands, skills, doctrine) and points at the right
entry-point skill for your situation instead of walking you through a full
tutorial.

## When to reach for it

Use it as your first stop in a new session: new project, broken install,
starting a mission from scratch, unsure whether a command exists as a slash
command or a skill, or unsure which `spk-*` skill applies to what you're
trying to do.

## Trigger phrase

There is no single fixed invocation string. Harnesses route natural-language
intent — "where do I start," "how do I use Spec Kitty," "what should I run
first" — to this skill, or you invoke it directly by name (`spk-start-here`)
using your harness's own skill syntax. It is distinct from CLI use: `spk-*`
skills are agent-harness operating guides, not `spec-kitty` CLI commands.

## First-route table

- New project or broken install → `spk-admin-setup-doctor`
- New mission from scratch → `spk-start-first-feature`
- Want a command list → `spk-start-command-map`
- "Will this work in Codex or Claude?" → `spk-start-agent-surface`
- Existing mission needs advancement → `spk-run-next`
- Multi-mission or multi-repo program → `spk-run-program-orchestrate`
- Review or approval work → `spk-run-review-wp`, then `spk-gate-accept`
- Doctrine or governance concern → the `spk-doctrine-*` family
- Unsure which skill applies → `spk-meta-skill-map`

## What it does not do

It does not turn into a full tutorial and does not do the routed work itself —
it states the route, loads the one skill that matches, and stops.
