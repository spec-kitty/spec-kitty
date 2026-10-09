---
title: Generic Agent — Agent Profile
description: General-purpose task execution profile. Used as the default when no specialist profile is assigned to a work package.
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Generic Agent — Agent Profile

Execute assigned work packages faithfully and completely, applying efficient local tooling and respecting the project's governance boundaries.

## What this profile is for

Generic Agent is the deliberate catch-all: the baseline identity used when no specialist profile (planner, architect, curator, or one of the other named personas) matches a work package. It implements, fixes, creates, and updates within the boundaries the project charter sets, without claiming any specialist expertise. It explicitly avoids architectural decisions that should be owned by a specialist profile — that boundary is by design, not a gap.

## Capabilities

- general-task-execution
- code-implementation
- documentation

## When to reach for it

- A work package doesn't match any specialist profile's focus (no architecture, review, doctrine, or language-specific work involved) — routing falls through to this baseline.
- Small, self-contained implementation or documentation fixes where a dedicated persona would be overkill.
- Early in a mission, before enough context exists to justify claiming a specialist role.
- An empty or unconfigured charter — `spec-kitty dispatch` on such a project now routes here with a warning rather than hard-failing (see [Troubleshooting Charter Failures](../../guides/how-to/governance/troubleshoot-charter.md#2-missing-doctrine)).

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to attach this profile to your session. Instead:

- **Let routing pick it**: describe what you need in natural language and `spec-kitty dispatch` routes the request to the matching profile — Generic Agent is what you get when nothing more specific applies. Its routing-priority (10) is the lowest of all 18 built-in profiles, so any specialist match is preferred over it.
- **Ask for it by name**: if your harness supports ad-hoc profile loading, request Generic Agent explicitly — see the `spk-charter-profile-load` skill for the mechanic.

## See also

- [Agent Profiles index](index.md)
