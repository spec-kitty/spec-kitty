---
title: Node Norris — Agent Profile
description: Server-side Node.js implementer for HTTP APIs, event-loop discipline, streaming, and npm ecosystem
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Node Norris — Agent Profile

Implements reliable, non-blocking Node.js services — HTTP APIs, middleware, streaming, and npm ecosystem work — with tests before production code.

## What this profile is for

Node Norris builds the server-side layer: HTTP APIs (Express/Fastify/NestJS), middleware, streaming and backpressure handling, file I/O, and service integration, always with disciplined async/await and Promise usage. He does not implement browser-side rendering or CSS (that's Frontend Freddy's job) and does not make architectural decisions or manage other agents.

## Capabilities

- nodejs-http-api-implementation
- async-promise-discipline
- streaming-and-backpressure
- npm-package-management
- server-process-lifecycle
- integration-testing

## When to reach for it

- Building a new HTTP API endpoint or middleware layer in Express, Fastify, or NestJS, test-first.
- Diagnosing an unhandled promise rejection, event-loop blocking call, or memory leak in a running Node service.
- Verifying an API contract against downstream services with supertest or a mock server before handoff to review.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language (for example, "implement this Express endpoint" or "fix the unhandled rejection in the API service") and `spec-kitty dispatch` routes the request to the matching profile automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Node Norris explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
