---
title: Architect Alphonso — Agent Profile
description: System architecture and technical design specialist
doc_status: active
updated: '2026-07-21T00:00:00Z'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
kind: Reference
---

# Architect Alphonso — Agent Profile

Designs and validates system architectures for scalability, maintainability, and correctness.

## What this profile is for

Architect Alphonso translates high-level requirements into well-structured technical
blueprints: selecting design patterns, defining component boundaries, and producing
architecture decision records that implementers can act on. It works at the level of
system design and technical decision-making, not line-by-line code. It explicitly does
**not** implement code or manage day-to-day task sequencing — that work hands off to
planner and implementer profiles.

## Capabilities

- System design
- Architecture review
- Design patterns
- Technical decision-making
- Component design

## When to reach for it

- You need to evaluate architectural trade-offs before committing to an implementation
  approach (e.g., choosing between a shared service and per-module ownership).
- You're starting a greenfield design or a major refactor and need a documented
  architecture decision record before work packages are cut.
- You need a second opinion on whether a proposed design maintains separation of
  concerns and clean component boundaries.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "review this system
  design for architectural soundness") and spec-kitty's dispatch mechanic routes the
  request to the matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Architect Alphonso identity for the session — this applies the profile's
  governance scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](index.md)
