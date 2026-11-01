---
title: 1.x Documentation (Legacy Track)
description: Historical Spec Kitty 1.x archive page for 1.x Documentation (Legacy Track); use Spec Kitty 3.2 docs for current projects and upgrades.
doc_status: deprecated
updated: '2026-06-03T00:00:00Z'
related:
- docs/context/index.md
- docs/changelog/1x/artifacts-and-commands.md
- docs/changelog/1x/branches-and-workspaces.md
- docs/changelog/1x/orchestration-and-api.md
- docs/changelog/1x/workflow.md
- docs/index.md
- docs/migrations/index.md
kind: Hub
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 1.x Documentation (Legacy Track)

`1.x` is deprecated overall and now retained only as `1.x-maintenance` for critical maintenance work.
No new `1.x` PyPI releases are planned.

## What 1.x Covers

1. Spec-driven workflow: `specify -> plan -> tasks -> implement -> review -> merge`.
2. Mission-oriented command templates for consistent delivery.
3. Work-package execution with branch/worktree isolation.
4. Local project governance through charter artifacts.

## Core File Layout (1.x)

1. `kitty-specs/<feature>/spec.md`
2. `kitty-specs/<feature>/plan.md`
3. `kitty-specs/<feature>/tasks.md`
4. `.kittify/memory/charter.md` (legacy location in 1.x)

## Start Here

1. [Workflow](workflow.md)
2. [Artifacts and Commands](artifacts-and-commands.md)
3. [Orchestration and API Boundary](orchestration-and-api.md)
4. [Branch and Workspace Model](branches-and-workspaces.md)

## Current replacement

- For new projects: start with [Spec Kitty 3.2 documentation](../../index.md).
- For upgrades: use [Migration to Spec Kitty 3.2](../../migrations/index.md).
- For old behavior lookup: use this 1.x archive only for historical context.
