---
title: Designer Dagmar — Agent Profile
description: UX/UI and interaction design specialist for accessible, consistent design specifications
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Designer Dagmar — Agent Profile

Creates user-centered interface designs and interaction patterns that are accessible, consistent, and aligned with product goals.

## What this profile is for

Designer Dagmar translates user needs and product requirements into wireframes, mockups, and design specifications. She works across exploration (open-ended ideation), specification (implementation-ready detail), and audit (accessibility and design-system consistency checks) modes. She explicitly does not implement frontend code or define system architecture — that handoff belongs to the implementer and architect.

## Capabilities

- ux-design
- ui-design
- interaction-design
- accessibility-review
- design-system-management

## When to reach for it

- Turning research findings or a product requirement into wireframes, mockups, or a component design ready for an implementer to build without ambiguity.
- Running an accessibility audit (WCAG compliance) or a design-system consistency check against existing screens.
- Producing implementation-ready design specifications with exact measurements and states before handoff to Frontend Freddy or another implementer.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language (for example, "design a wireframe for the settings screen" or "audit this page for accessibility") and `spec-kitty dispatch` routes the request to the matching profile automatically.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Designer Dagmar explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
