---
title: Runtime-owned Mission Discovery and Loading
description: Gives the runtime sole ownership of Mission discovery and YAML loading, so the CLI stops keeping a second precedence order that resolved custom packs differently.
status: Proposed
doc_status: active
kind: ADR
date: '2026-02-17'
---

## Context and Problem Statement

Mission discovery and loading behavior is currently split between resolver code and legacy mission listing/loading code paths. This creates precedence inconsistencies and non-deterministic mission selection behavior for custom mission packs.

## Decision

1. Mission discovery/loading logic is owned by `spec-kitty-runtime`.
2. `spec-kitty` CLI consumes runtime discovery APIs and does not maintain parallel precedence logic.
3. Mission definition format for V1 is YAML-only.
4. Discovery precedence follows canonical runtime order.

## Decision Drivers

1. Deterministic mission selection.
2. Single source of truth for discovery precedence.
3. Better author experience for mission packs.
4. Reduced maintenance burden from duplicated logic.

## Consequences

### Positive

1. No resolver drift between command paths.
2. Easier documentation and support.
3. Better portability to other execution hosts.

### Negative

1. Runtime package dependency introduced into CLI mission-loading code path.
2. Migration effort for existing mission helper functions.

### Neutral

1. Legacy mission locations stay temporarily supported with deprecation warnings.

## Migration

1. Route mission listing/info commands through runtime discovery API.
2. Keep existing CLI UX while changing backend resolution source.
3. Remove duplicated resolver code after migration window.
