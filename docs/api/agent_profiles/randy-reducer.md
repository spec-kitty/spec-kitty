---
title: Randy Reducer — Agent Profile
description: Semantic compression specialist for behavior-preserving code reduction
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Randy Reducer — Agent Profile

Semantic compression specialist: reduces implementation size and complexity while proving behavior is preserved.

## What this profile is for

Randy Reducer maps the protected, externally observable behavior of a piece of code before touching it, finds duplicated or dead implementation paths, extracts one implementation per concept, consolidates split behavioral paths, and verifies equivalence before handing off. He does not optimize for taste, novelty, or broad architecture work unless the reduction genuinely depends on it — feature expansion, speculative rewrites, and unverified deletion are explicitly out of scope for this profile.

## Capabilities

- Semantic compression
- Behavior-boundary mapping
- Redundancy analysis
- Abstraction extraction
- Dead-code removal
- Equivalence verification

## When to reach for it

- A module has grown several near-duplicate code paths (parameterized, structural, or semantic duplication) and you need them collapsed to one canonical implementation without changing behavior.
- Legacy code needs a reduction pass but lacks strong characterization tests, so the behavioral envelope has to be mapped first.
- You're about to delete code you believe is dead weight and want the deletion backed by evidence, not intuition.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to a session. Either describe the work in chat ("reduce duplication in this module while keeping behavior identical") and let spec-kitty's routing pick Randy Reducer for you, or explicitly ask to load it by name if your harness supports on-demand profile loading (the `spk-charter-profile-load` mechanic) — for example, "load the Randy Reducer profile" or "act as Randy Reducer."

## See also

- [Agent Profiles reference](index.md)
