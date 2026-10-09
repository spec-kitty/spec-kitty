---
title: Retrospective Facilitator — Agent Profile
description: Facilitates a structured mission retrospective at terminus
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/agent_profiles/index.md
  - docs/context/charter.md
---

# Retrospective Facilitator — Agent Profile

Captures structured findings, gaps, and governance proposals at mission terminus — not a general-purpose agent.

## What this profile is for

Retrospective Facilitator runs a human-mediated post-mortem at the end of a mission: what helped, what did not help, what governance or context gaps appeared, and what concrete doctrine, DRG, or glossary changes are proposed. It produces a schema-valid `retrospective.yaml` with provenance on every finding. It is explicitly **not** invoked mid-mission — only at mission terminus or via an explicit retrospective marker step in custom missions. Note that the runtime's default retrospective generator (a pure-Python module) already runs automatically at completion; this profile is for richer, operator-initiated retrospectives on top of that.

## Capabilities

- retrospective-facilitation
- findings-capture
- proposal-generation
- governance-analysis

## When to reach for it

- After a mission completes (or is deliberately terminated) and the operator wants a real retrospective, not just the automatic summary — e.g. "walk through what worked and what didn't on this mission."
- When a mission surfaced governance or doctrine gaps worth proposing as changes (new directive, DRG edge, glossary term) and those proposals need provenance back to mission events.
- In autonomous-mode runs, where a retrospective is mandatory and must be produced without a human present to interview.

## How to load it from your harness

You do not run a CLI command to load this profile directly. In practice it is invoked automatically by the runtime's lifecycle terminus hook (built-in missions) or an explicit retrospective marker step (custom missions) — you don't need to request it by name for a normal mission run. If you want to adopt it ad hoc in a chat session (for example, to draft retrospective-style findings outside a mission), use `spk-charter-profile-load` and name the profile explicitly, or describe what you need and let spec-kitty's routing pick it. Findings and proposals it captures are data only — applying proposed doctrine, DRG, or glossary changes is a separate, human-approved step via `agent retrospect synthesize`.

## See also

- [Agent Profiles index](index.md)
