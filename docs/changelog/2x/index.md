---
title: 2.x Documentation (Archive)
description: Historical Spec Kitty 2.x archive page for 2.x Documentation (Archive); use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03'
related:
- context
- changelog/2x/adr-coverage
- changelog/2x/doctrine-and-charter
- changelog/2x/glossary-system
- changelog/2x/orchestration-and-api
- changelog/2x/runtime-and-missions
- ''
- migrations
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 2.x Documentation (Archive)

> **Archive Notice**: This section documents Spec Kitty 2.x behavior. It is preserved
> for historical reference only. For current 3.2 documentation, see
> [Spec Kitty 3.2 current overview](../../context/index.md).

`2.x` was the architecture track centered on doctrine-backed governance, living glossary
semantics, and runtime-owned mission execution. These pages are archived so existing projects and
contributors can understand older behavior; current projects should use the 3.2 docs.

## Key 2.x Shifts

1. Doctrine artifacts are typed and schema-validated under `src/doctrine/`.
2. Charter generation uses interview answers plus doctrine catalog selection.
3. Glossary is context-owned (`docs/context/*.md`) and integrated into mission execution through glossary hooks.
4. Runtime loop and mission discovery are driven by canonical `next` and runtime precedence rules.

## Start Here

1. [Doctrine and Charter](doctrine-and-charter.md)
2. [Glossary System](glossary-system.md)
3. [Runtime and Missions](runtime-and-missions.md)
4. [Orchestration and API Boundary](orchestration-and-api.md)
5. [ADR Coverage](adr-coverage.md)

## Current replacement

- For new projects: start with [Spec Kitty 3.2 documentation](../../index.md).
- For upgrades: use [Migration to Spec Kitty 3.2](../../migrations/index.md).
- For old behavior lookup: use this 2.x archive only for historical context.

## Architecture Repository Layout

- 2.x domain map: `docs/architecture/README-2.x.md#domain-breakdown`
- 2.x C4 docs: `docs/architecture/01_context/`, `docs/architecture/02_containers/`, `docs/architecture/03_components/`
- 2.x ADRs: `docs/adr/2.x/`
- 2.x user journeys: `docs/plans/user_journey/`
- architecture personas: `docs/context/audience/`
