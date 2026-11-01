---
title: 1.x Orchestration and API Boundary
description: Historical Spec Kitty 1.x archive page for 1.x Orchestration and API Boundary; use Spec Kitty 3.2 docs for current projects and upgrades.
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/context/README.md
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/README.md) for current docs.

# 1.x Orchestration and API Boundary

`1.x` uses a host/provider split for automated orchestration:

1. `spec-kitty` owns workflow state and transition validation.
2. External providers run orchestration loops.
3. Providers integrate through `spec-kitty orchestrator-api` only.

## What changed

1. `spec-kitty orchestrate` is not part of the core CLI.
2. `spec-kitty orchestrator-api` is the supported host contract.
3. `spec-kitty-orchestrator` is the reference external provider.

## Recommended operator flow

```bash
spec-kitty orchestrator-api contract-version
spec-kitty-orchestrator orchestrate --mission 034-my-feature --dry-run
spec-kitty-orchestrator orchestrate --mission 034-my-feature
```

## Build-your-own provider

Custom providers should:

1. Read ready work through `list-ready` / `feature-state`.
2. Start work through `start-implementation`.
3. Drive review loops with `transition` and `start-review`.
4. Finalize with `accept-mission` and `merge-mission`.

Do not mutate WP lane frontmatter directly from the provider process.

## References

1. [Run External Orchestrator](../../guides/how-to/collaboration/run-external-orchestrator.md)
2. [Build Custom Orchestrator](../../guides/how-to/collaboration/build-custom-orchestrator.md)
3. [Orchestrator API Reference](../../api/orchestrator-api.md)
