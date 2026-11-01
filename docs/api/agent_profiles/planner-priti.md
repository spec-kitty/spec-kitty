---
title: Planner Priti — Agent Profile
description: Work decomposition and delivery sequencing specialist
doc_status: active
updated: '2026-07-21'
related:
- api/agent_profiles
- context/charter
---

# Planner Priti — Agent Profile

Decomposes missions into sequenced, dependency-correct work packages.

## What this profile is for

Planner Priti turns architect designs and product intent into executable task plans:
breaking a mission down into granular work packages, mapping dependencies, and
sequencing delivery for parallel or serial execution. It identifies risks and blockers
early and prioritises using the Eisenhower matrix (urgency vs. importance). It
explicitly does **not** implement code, make architectural decisions, or own product
direction — those hand off to architect and implementer profiles.

## Capabilities

- Work decomposition
- Dependency mapping
- Sprint planning
- Risk identification
- Task sequencing
- Priority assessment

## When to reach for it

- You've finished architecture and requirements and need the mission broken into
  estimable, dependency-correct work packages before implementation starts.
- You're sprint planning or release planning and need work ordered by critical path and
  parallelization opportunity.
- You need a risk register or a call on what needs a spike/research pass before
  implementation can safely begin.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "break this mission
  into a dependency-ordered work breakdown") and spec-kitty's dispatch mechanic routes
  the request to the matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Planner Priti identity for the session — this applies the profile's
  governance scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](index.md)
