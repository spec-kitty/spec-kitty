---
title: 1.x Branch and Workspace Model
description: Historical Spec Kitty 1.x archive page for 1.x Branch and Workspace Model; use Spec Kitty 3.2 docs for current projects and upgrades.
doc_status: deprecated
updated: '2026-06-03T00:00:00Z'
related:
- docs/context/index.md
kind: Changelog
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 1.x Branch and Workspace Model

## Feature-Centric Branching

1. Each feature is tracked as a branch-scoped workspace.
2. Work packages are executed in isolated working directories.
3. Merge operations close the feature workflow by integrating approved work.

## Execution Discipline

1. Work packages should move through lane states in order.
2. Planning artifacts are the contract for implementation and review.
3. Charter principles are applied before final acceptance.

## Typical 1.x Paths

1. Feature artifacts: `kitty-specs/<feature>/...`
2. Runtime/project state: `.kittify/...`
3. Command templates and mission defaults from packaged mission/template roots (`src/specify_cli/missions/**`, `src/specify_cli/templates/**`) and project overrides.
