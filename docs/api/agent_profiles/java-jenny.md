---
title: Java Jenny — Agent Profile
description: Java-specialist implementer applying ATDD/TDD discipline, Maven build tooling, and idiomatic Java style enforcement
doc_status: active
updated: '2026-07-21T00:00:00Z'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
kind: Reference
---

# Java Jenny — Agent Profile

Delivers idiomatic, well-tested Java code that passes all Maven quality gates and faithfully implements specifications.

## What this profile is for

Java Jenny is a language-specialist implementer who translates design documents and task
descriptions into clean Java code using ATDD (acceptance-test first) and TDD
(red-green-refactor). It enforces naming conventions, null-safety with `Optional`, and
resource-management discipline (try-with-resources), and runs the full Maven quality gate —
compile, test, checkstyle, spotbugs, jacoco — before handing off. It does **not** make
architectural decisions, deploy infrastructure, work on frontend concerns, or manage other
agents; those stay with the architect and reviewer.

## Capabilities

- Java implementation
- JUnit testing
- Maven build
- Type-safe design
- Refactoring
- Debugging
- Code-review response

## When to reach for it

- You're implementing a Java work package and want acceptance tests written first, then
  driven to green with TDD.
- You're fixing a reported Java bug and need a reproduction test written before the fix.
- You need Maven quality gates (checkstyle, spotbugs, jacoco, Cucumber/Serenity BDD
  scenarios) run and passing before a Java change is handed to review.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to
load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (e.g., "implement this work
  package in Java with TDD") and spec-kitty's dispatch mechanic routes the request to the
  matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly
  to adopt the Java Jenny identity for the session — this applies the profile's governance
  scope and initialization declaration without requiring a running mission.

## See also

- [Agent Profiles index](index.md)
