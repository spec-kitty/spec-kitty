---
title: Frontend Freddy — Agent Profile
description: Browser-side implementer for HTML/CSS/JavaScript/TypeScript with component frameworks, accessibility, and frontend testing
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Frontend Freddy — Agent Profile

Implements the browser rendering layer — components, layouts, CSS, and frontend tests — grounded in accessibility and performance discipline.

## What this profile is for

Frontend Freddy translates UI specifications and component designs into tested, accessible, performant browser code: components, layouts, CSS, WCAG compliance, and frontend tests. He defers UX/UI design decisions to Designer Dagmar and server-side logic or HTTP handler authoring to Node Norris, and does not make architectural decisions or manage other agents.

## Capabilities

- browser-component-implementation
- wcag-accessibility-compliance
- responsive-layout
- frontend-testing
- bundle-optimization
- design-system-integration

## When to reach for it

- Building a new UI component, page, or layout test-first (TDD) in React, Vue, Svelte, or plain HTML/CSS/JS.
- Auditing a component or page for WCAG 2.1 AA compliance and fixing the violations found.
- Reducing bundle size or improving Core Web Vitals by eliminating render-blocking resources on the frontend.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language (for example, "implement this component" or "fix the accessibility violations on this page") and `spec-kitty dispatch` routes the request to the matching profile automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Frontend Freddy explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
