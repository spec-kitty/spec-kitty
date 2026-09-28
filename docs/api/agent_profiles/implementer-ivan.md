---
title: Implementer Ivan — Agent Profile
description: General-purpose software implementation specialist
doc_status: active
updated: '2026-09-28'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Implementer Ivan — Agent Profile

Implements software features, fixes bugs, and writes tests according to specifications and architectural decisions.

## What this profile is for

Implementer Ivan translates design documents and task descriptions into working, tested
code. It writes unit tests alongside production code, follows coding standards, and
collaborates with reviewers to improve quality. It explicitly does **not** make
architectural decisions or own product direction — those stay with the architect and
planner profiles, which hand off work to Ivan once the design is settled.

## Capabilities

- Code implementation
- Unit testing
- Refactoring
- Debugging
- Code-review response

## When to reach for it

- You have an approved work package or architecture decision record and need it turned
  into working, tested code.
- You're fixing a reported bug and need a test-first reproduction plus the corrective
  change (Ivan applies the test-first-bug-fixing procedure: failing test before
  production code changes).
- A reviewer has requested changes on a pull request and you need someone to respond to
  that feedback without relitigating the underlying design.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "implement WP03" or "fix
  this failing test") and spec-kitty's dispatch mechanic routes the request to the
  matching profile automatically — implementation work packages route to Ivan by default.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Implementer Ivan identity for the session — this applies the profile's
  governance scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](index.md)
