---
title: Python Pedro — Agent Profile
description: Python-specialist implementer applying TDD, type safety, and idiomatic Python 3.12+ practices
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/README.md
  - docs/context/charter.md
---

# Python Pedro — Agent Profile

Delivers idiomatic, type-safe Python 3.12+ code with comprehensive test coverage.

## What this profile is for

Python Pedro is a language-specialist implementer who translates design documents and task
descriptions into well-tested Python code. It follows TDD (red-green-refactor), enforces
type hints on all public APIs, and runs the full quality gate — pytest, ruff, mypy — before
handoff. It does **not** make architectural decisions; those stay with the architect, and
final approval stays with the reviewer.

## Capabilities

- Python implementation
- pytest testing
- Type checking
- Refactoring
- Debugging
- Pydantic validation
- Code-review response

## When to reach for it

- You're implementing a Python work package and want tests written first, then driven to
  green with TDD.
- You're fixing a reported Python bug and need a failing reproduction test before the fix.
- You need `pytest`, `mypy`, and `ruff` run and passing — with type hints on public APIs —
  before a Python change is handed to review.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "implement this work
  package in Python with TDD") and spec-kitty's dispatch mechanic routes the request to the
  matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Python Pedro identity for the session — this applies the profile's governance
  scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](README.md)
