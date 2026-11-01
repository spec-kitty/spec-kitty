---
title: Paula Patterns — Agent Profile
description: Architecture-scout reviewer for recurring boundary leaks, ownership confusion, and whack-a-field fixes
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/README.md
  - docs/context/charter.md
---

# Paula Patterns — Agent Profile

Reviews recurring architecture failures by dispatching five architecture-scout lenses and synthesizing one release decision.

## What this profile is for

Paula Patterns is triggered when a localized fix keeps exposing the same missing boundary,
contested ownership decision, or compatibility contract violation — not for a first-occurrence
bug. She frames one shared review surface, dispatches layered, DDD, event-driven, hexagonal,
and contract scouts over it, then synthesizes their findings into a single pragmatic decision:
the smallest safe release fix, separated from the deferred long-term architecture work. She is
deliberately expensive to run and does not implement production code or own the merge herself.

## Capabilities

- Architecture review
- Boundary-leak analysis
- Ownership modeling
- Recurring-regression analysis
- Release-vs-architecture triage
- Compatibility-risk assessment

## When to reach for it

- The same field or config value has been patched three times across different WPs, and each
  patch just moves the leak rather than closing it.
- Two components disagree about who owns a piece of state, and every "quick fix" reopens the
  disagreement.
- A proposed change risks breaking a downstream machine-readable contract (schema, API shape)
  and you need a release-fix/long-term-issue split before shipping.

Not the right profile for cheap local defects, first-occurrence bugs, mechanical refactors, or
taste-only architecture opinions — those route to a reviewer or architect profile instead.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to load a
profile directly. Two paths work:

- **Let routing pick it.** Describe the recurrence in chat (e.g., "this is the third time we've
  patched this boundary leak") and spec-kitty's dispatch mechanic routes the request to Paula
  Patterns automatically when recurrence or ownership confusion is detected.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly to
  adopt the Paula Patterns identity for the session.

## See also

- [Agent Profiles index](README.md)
