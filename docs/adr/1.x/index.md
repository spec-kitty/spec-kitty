---
title: 1.x ADRs
description: Index and era history for the archived 1.x decisions — workspace provenance, dependency auto-merge, config-driven agents, CLI-first commands, and deterministic CSV schemas.
doc_status: active
updated: '2026-08-10'
type: explanation
audience: docs/context/audience/internal/system-architect.md
---

# 1.x ADRs

Architectural Decision Records for the legacy 1.x track.

## Era history

The 1.x era established Spec Kitty as a **local-first** developer tool: a CLI that
bootstrapped a project's directory structure, templates, and agent integrations, then
drove spec-driven work entirely from the local checkout with no hosted platform in the
loop. The decisions recorded here set the foundations later eras built on:

- **Workspace provenance and context storage** — explicit base-branch tracking and
  centralized, decorator-validated workspace context, so a mission's git topology was
  recorded rather than inferred.
- **Dependency-aware auto-merge** — auto-merging multi-parent dependency work so
  completed prerequisites flowed forward without manual reconciliation.
- **Config-driven agent management** — a single configuration source of truth for which
  AI agents a project supports, rather than hard-coded agent lists.
- **CLI-first command interface** and **deterministic CSV schema enforcement** — a stable,
  scriptable command surface with reproducible tabular outputs.
- **Worktree cleanup at merge, not eagerly**, and **sparse-checkout defense-in-depth** —
  the early worktree lifecycle and isolation posture.

These decisions are **retained as history**. The current track is
[3.x](../3.x/index.md); the intervening architecture is [2.x](../2.x/index.md). Use the
1.x record when working on local-first legacy behavior and maintenance, or when tracing
why a foundational mechanism exists.

## Naming

- `YYYY-MM-DD-N-descriptive-title-with-dashes.md` where `N` increments per ADR landed on a
  given date (1, 2, 3…).

## Source of Truth

This folder is canonical for 1.x decisions.

The `architecture/` tree was removed by the Common Docs structural move (PR #2225).
Existing references using the old `architecture/adrs/` paths should be updated to the new
`docs/adr/` paths.
