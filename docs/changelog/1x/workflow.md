---
title: 1.x Workflow
description: Historical Spec Kitty 1.x archive page for 1.x Workflow; use Spec Kitty 3.2 docs for current projects and upgrades.
doc_status: deprecated
updated: '2026-06-03'
related:
- context
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 1.x Workflow

## Canonical Sequence

1. `spec-kitty specify <feature-intent>`
2. `spec-kitty plan`
3. `spec-kitty tasks`
4. `spec-kitty implement`
5. `spec-kitty review`
6. `spec-kitty merge`

## Why This Order Matters

1. `spec.md` defines requirements and acceptance intent.
2. `plan.md` captures architecture and implementation strategy.
3. `tasks.md` materializes executable work packages.
4. `implement` and `review` execute against plan and charter constraints.

## Governance in 1.x

The legacy governance source is `.kittify/memory/charter.md`.  
Workflow prompts and reviews are expected to align to those principles.
