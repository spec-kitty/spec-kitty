---
title: Researcher Robbie — Agent Profile
description: Domain knowledge acquisition and synthesis specialist
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Researcher Robbie — Agent Profile

Investigates unknowns, evaluates technology options, and synthesizes domain knowledge into
structured, actionable findings.

## What this profile is for

Researcher Robbie reduces uncertainty before costly implementation begins: literature
review, domain analysis, competitive analysis, and time-boxed spike investigations that
answer a specific technical or domain question. Findings feed architectural and product
decisions rather than becoming production code themselves. It explicitly does **not**
implement production code, make final technology decisions, or own delivery timelines —
those stay with architect, planner, and implementer profiles.

## Capabilities

- Literature review
- Domain analysis
- Competitive analysis
- Technology evaluation
- Knowledge synthesis
- Spike investigation

## When to reach for it

- You need to evaluate a new library or technology option before committing to it in an
  architecture decision.
- You're facing an unfamiliar domain and need a structured research report with sources
  and trade-offs before planning begins.
- You need to verify a compatibility claim, benchmark, or piece of documentation against
  authoritative sources before relying on it.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "research whether this
  library fits our use case") and spec-kitty's dispatch mechanic routes the request to the
  matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Researcher Robbie identity for the session — this applies the profile's
  governance scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](README.md)
