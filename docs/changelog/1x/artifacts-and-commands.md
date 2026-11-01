---
title: 1.x Artifacts and Commands
description: Historical Spec Kitty 1.x archive page for 1.x Artifacts and Commands; use Spec Kitty 3.2 docs for current projects and upgrades.
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/context/README.md
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/README.md) for current docs.

# 1.x Artifacts and Commands

## Feature Artifacts

For each feature directory under `kitty-specs/`, the minimum artifact set is:

1. `spec.md`
2. `plan.md`
3. `tasks.md`

Optional supporting artifacts (for example `research.md`, `data-model.md`, `quickstart.md`) are feature-dependent.

## Command Groups Used in 1.x

1. Core workflow commands (`specify`, `plan`, `tasks`, `implement`, `review`, `merge`)
2. Agent command family (`spec-kitty agent ...`) for work-package movement and automation
3. Host orchestration contract (`spec-kitty orchestrator-api ...`) for external providers
4. Mission selection/switching commands where mission-specific behavior is required

## Legacy Governance Artifacts

1. `.kittify/memory/charter.md`
2. Mission command templates under project or package template roots
3. Lane/frontmatter state in work package markdown files

## Stability Notes

1.x is maintained as the legacy operating model while 2.x introduces doctrine-backed governance and glossary architecture.
