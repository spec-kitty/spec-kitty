---
title: Events Contract Parity and Vendored Module Deprecation
description: Names the published events package the only contract authority, schedules the vendored copy for removal, and requires CI parity checks across consuming repos.
status: Proposed
doc_status: active
kind: ADR
date: '2026-02-17'
---

## Context and Problem Statement

Spec Kitty currently contains a vendored events module while also depending on external `spec-kitty-events`. This creates risk of contract drift and ambiguous authority for envelope/reducer semantics.

Additionally, consumer version pins are currently inconsistent across repositories.

## Decision

1. `spec-kitty-events` is the sole contract authority.
2. CLI and SaaS MUST pin the same exact `spec-kitty-events` version.
3. Vendored event module in CLI is deprecated and scheduled for removal after migration gates pass.
4. CI parity checks are required to prevent version drift.
5. Runtime mission-next implementation is gated on mission-next contracts being published in `spec-kitty-events`.
6. Consumers MUST NOT emit local-only mission-next event names outside published contracts.

## Decision Drivers

1. Deterministic cross-repo replay.
2. Single source of truth for event contracts.
3. Reduced semantic ambiguity during incident/debug workflows.
4. Better release discipline across repositories.

## Consequences

### Positive

1. Replay/projection parity becomes enforceable.
2. Event contract evolution is explicit and auditable.
3. Lower chance of hidden drift bugs.

### Negative

1. Requires coordinated release cadence and contract-bump workflow.
2. Migration work to remove vendored compatibility layer.

### Neutral

1. Temporary compatibility shims may be needed during transition.

## Enforcement

1. Add CI checks for exact version parity in consumers.
2. Add CI checks rejecting vendored-only contract extensions.
3. Document contract-bump process in release notes.
4. Add CI checks ensuring runtime mission-next event types map to published `spec-kitty-events` constants/payloads.
