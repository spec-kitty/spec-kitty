---
title: 2.x Orchestration and API Boundary
description: Historical Spec Kitty 2.x archive page for 2.x Orchestration and API Boundary; use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03'
related:
- context
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 2.x Orchestration and API Boundary

`2.x` keeps orchestration external while preserving host-owned workflow integrity.

## Boundary model

1. Host: `spec-kitty` manages lane state, dependency checks, and merge/accept semantics.
2. Provider: external orchestration runtime executes agents and calls host API.
3. Contract: `spec-kitty orchestrator-api` JSON envelope and deterministic error codes.

## Operational implications

1. Security-sensitive environments can disable external automation and keep manual flow.
2. Multiple provider strategies can be implemented without changing host internals.
3. Runtime governance remains centralized in the host contract.

## Baseline commands

```bash
spec-kitty orchestrator-api contract-version
spec-kitty orchestrator-api mission-state --mission 034-my-feature
spec-kitty orchestrator-api list-ready --mission 034-my-feature
```

## Reference provider

Use `spec-kitty-orchestrator` for turnkey automation:

```bash
spec-kitty-orchestrator orchestrate --mission 034-my-feature --dry-run
spec-kitty-orchestrator orchestrate --mission 034-my-feature
```

## Custom provider guidance

Implement your orchestration loop against `orchestrator-api`; do not import host internals or write lane state directly.

## References

1. [Run External Orchestrator](../../guides/how-to/collaboration/run-external-orchestrator.md)
2. [Build Custom Orchestrator](../../guides/how-to/collaboration/build-custom-orchestrator.md)
3. [Orchestrator API Reference](../../api/orchestrator-api.md)
