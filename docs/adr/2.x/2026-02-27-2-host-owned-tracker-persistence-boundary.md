---
title: Host-Owned Tracker Persistence Boundary
description: Keeps SQLite caches and checkpoints in the host CLI and leaves the tracker core protocol-only, matching how the sync queue and status store are already owned.
status: Accepted
doc_status: active
kind: ADR
date: '2026-02-27'
---

## Context and Problem Statement

Tracker integration requires local cache and checkpoint persistence. One proposal added durable SQLite stores directly to `spec-kitty-tracker` core. That approach conflicts with existing SpecKitty architecture where persistence is host-owned and context-specific.

Current patterns in CLI:

1. SQLite queue in `sync/queue.py`
2. JSONL state/event store in `status/store.py`
3. Credential storage + locking in `sync/auth.py`

Adding core persistence in `spec-kitty-tracker` would blur boundaries and make connector core responsible for deployment-specific storage concerns.

## Decision Drivers

1. Keep `spec-kitty-tracker` reusable across CLI and SaaS hosts.
2. Preserve existing host-owned persistence architecture.
3. Avoid premature storage coupling in connector core.
4. Keep connector testability simple with in-memory stores.

## Considered Options

1. Add `SqliteIssueStore` and `SqliteCheckpointStore` to `spec-kitty-tracker`.
2. Host-owned durable store implementations (`spec-kitty` CLI and future SaaS adapters), with protocol interfaces in core (chosen).
3. No durable local store in v1.

## Decision Outcome

**Chosen option:** host-owned persistence with protocol-only core.

### Required Behavior

1. `spec-kitty-tracker` defines protocols/contracts and connectors.
2. `spec-kitty-tracker` may include in-memory testing stores only.
3. Durable SQLite tracker store/checkpoint implementations live in `spec-kitty` CLI.
4. SaaS may implement separate durable projections without changing core contracts.

### Consequences

#### Positive

1. Clear architectural boundary and ownership.
2. Reusable connector core with minimal runtime assumptions.
3. Storage technology remains host-selectable.

#### Negative

1. Host implementations duplicate some store wiring logic.
2. Shared migration helpers are deferred.

#### Neutral

1. Core docs must explicitly state persistence responsibility.

### Confirmation

This decision is validated when:

1. No durable store classes are present in `spec-kitty-tracker` core.
2. CLI durable tracker cache/checkpoint persistence exists in `spec-kitty`.
3. Tracker connector tests run using protocol/in-memory store patterns.

## Pros and Cons of the Options

### Option 1: Durable SQLite in core

**Pros:**

1. Single implementation point.

**Cons:**

1. Couples connector core to storage/runtime assumptions.
2. Conflicts with established host-owned pattern.

### Option 2: Host-owned persistence (Chosen)

**Pros:**

1. Architecture consistency with existing SpecKitty patterns.
2. Better portability across hosts.

**Cons:**

1. More host-side implementation effort.

### Option 3: No durable store

**Pros:**

1. Simplifies short-term implementation.

**Cons:**

1. Fails operational requirements for checkpointed sync.

## More Information

1. Existing host persistence references:
   `src/specify_cli/sync/queue.py`
   `src/specify_cli/status/store.py`
   `src/specify_cli/sync/auth.py`
2. CLI tracker store implementation:
   `src/specify_cli/tracker/store.py`
3. Core architecture docs:
   `<spec-kitty-tracker-repo>/docs/ARCHITECTURE.md`
