---
title: Post-Merge Mission Audit Artifact and Event Emission
description: Emits a canonical audit artifact and lifecycle events once a Mission is integrated, giving a durable, projectable answer to whether delivery matched the spec.
status: Accepted
doc_status: active
kind: ADR
date: '2026-02-25'
---

## Context and Problem Statement

Current merge flow emits WP lifecycle transitions but does not produce a dedicated post-merge audit lifecycle, and does not persist audit status in feature metadata.
At the same time, dossier contracts already exist in `spec-kitty-events` and SaaS dossier projection exists, but current SaaS ingestion is focused on `MissionDossierArtifactIndexed` dispatch and not a post-merge mission-audit lifecycle.

As a result:

1. There is no canonical "did delivered software match spec/plan/tasks" artifact at merge boundary.
2. Event stream consumers cannot reliably project post-merge quality status.
3. Dashboard and dossier views cannot consistently show post-merge audit outcomes.

## Decision Drivers

1. Ensure post-merge quality evaluation is auditable and replayable.
2. Keep local-first execution authority while supporting SaaS projection parity.
3. Provide deterministic artifact/event links for mission dossier materialization.
4. Support human decision checkpoints for low-confidence or ambiguous audit results.

## Considered Options

1. Keep audit as manual command only, no merge integration.
2. Trigger audit on merge when mission policy enables it; emit canonical events + artifact (chosen).
3. Make SaaS perform post-merge audit independently.

## Decision Outcome

**Chosen option:** "Trigger audit on merge when mission policy enables it; emit canonical events + artifact", because it preserves local authority and gives deterministic post-merge evidence.

### Contract Details

1. Merge MUST evaluate mission policy for audit trigger mode.
2. If policy includes post-merge audit:
   - initiate audit run,
   - persist audit metadata in feature state,
   - emit canonical mission-audit lifecycle events,
   - materialize a dossier-indexed audit artifact.
3. If policy does not include post-merge audit:
   - do not run audit,
   - emit explicit skip reason where applicable.
4. Human clarification checkpoints are first-class decision events and appear in decision inbox projections.

### Consequences

#### Positive

1. Merge boundary gains deterministic quality evidence.
2. Dashboard can reliably surface latest post-merge audit state.
3. Dossier and event streams stay aligned for replay/debug.

#### Negative

1. Merge flow complexity increases.
2. Additional contract coordination required across repositories.

#### Neutral

1. Some missions can remain manual-only audit by policy.

### Confirmation

This decision is validated when:

1. Merge-triggered audits produce canonical event sequences and artifact refs.
2. Feature metadata reflects latest audit run/verdict deterministically.
3. SaaS dashboard and dossier show the same audit result as local state.

## Pros and Cons of the Options

### Option 1: Manual-only audit

Post-merge quality checks are user-invoked only.

**Pros:**

1. Simplest implementation.
2. No merge-path latency impact.

**Cons:**

1. Easy to skip accidentally.
2. No reliable merge-boundary evidence.

### Option 2: Merge-triggered policy-aware audit with events/artifact

Run audit from merge when mission policy declares post-merge behavior.

**Pros:**

1. Deterministic post-merge quality traceability.
2. Strong alignment with mission-driven execution.

**Cons:**

1. Requires cross-repo implementation coordination.
2. Must handle blocking/advisory behavior carefully.

### Option 3: SaaS-side independent audit

Perform audit in SaaS materialization layer.

**Pros:**

1. Keeps local merge path simpler.
2. Centralized compute in cloud layer.

**Cons:**

1. Breaks local-first authority model.
2. Risks divergence from canonical local artifacts/events.

## More Information

1. PRD reference:
   `<spec-kitty-planning-repo>/product-ideas/mission-collaboration-platform-ddd/prd-mission-post-merge-audit-and-verify-repurpose-v1.md`
2. Current merge command:
   `src/specify_cli/cli/commands/merge.py`
3. Existing event emitter contracts:
   `src/specify_cli/sync/emitter.py`
4. Existing dossier event/indexer model:
   `src/specify_cli/dossier/events.py`
   `src/specify_cli/dossier/indexer.py`
