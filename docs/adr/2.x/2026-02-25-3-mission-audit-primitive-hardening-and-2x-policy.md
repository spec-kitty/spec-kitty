---
title: Mission Audit Primitive Hardening and 2.x-Only Policy
description: Implements auditing as a declarable Mission primitive behind compatibility gates, keeping built-in and custom Missions portable across local and hosted projections.
status: Accepted
date: '2026-02-25'
doc_status: active
kind: ADR
updated: '2026-02-25T00:00:00Z'
---

## Context and Problem Statement

Spec Kitty 2.x treats Mission as the central control entity, but primitive hardening is uneven:

1. Built-in missions are not uniformly runtime-template compatible.
2. Primitive context mutability and bridge wiring are functional but not yet uniformly constrained by compatibility gates.
3. New post-merge audit behavior must be mission-declarable, deterministic, and portable across local + SaaS projections.
4. Current built-in mission template baseline is mixed (for example, some missions still rely on legacy `mission.yaml` state-machine shape while others have runtime sidecars).

At the same time, product policy requires no new feature work on 1.x.

## Decision Drivers

1. Make mission primitives reliable enough to be the primary abstraction for future growth.
2. Ensure audit behavior is mission-controlled, not ad hoc command logic.
3. Prevent branch-policy ambiguity between 1.x and 2.x.
4. Enforce fail-fast behavior on invalid mission contracts.

## Considered Options

1. Implement post-merge audit as CLI-only logic outside mission primitive system.
2. Implement audit as mission primitive with hardening gates and 2.x-only policy (chosen).
3. Delay primitive hardening and ship ad hoc audit now.

## Decision Outcome

**Chosen option:** "Implement audit as mission primitive with hardening gates and 2.x-only policy", because this preserves architectural coherence and makes mission primitives a defensible long-term foundation.

### Hardening Contract

1. Audit is a mission primitive declared in mission runtime configuration.
2. Runtime compatibility checks are required for built-in missions used in 2.x rollout.
3. Invalid/partial mission config results in explicit fail-fast behavior.
4. Primitive output schema for audit is typed and deterministic.
5. Mission audit checkpoint decisions integrate with existing decision-required flow.

### Branch Policy

1. All audit primitive and verify repurpose work is 2.x only.
2. 1.x receives no new feature implementation for this initiative.
3. Any compatibility shims in shared code must avoid introducing new 1.x product capability.

### Consequences

#### Positive

1. Mission primitives become stronger as a reusable abstraction for future capabilities.
2. Audit behavior stays composable and policy-driven per mission.
3. Rollout discipline improves through explicit 2.x/1.x separation.

#### Negative

1. Upfront migration effort for mission runtime templates and tests.
2. Potential short-term blocked states while mission compatibility gaps are closed.

#### Neutral

1. Some built-in missions may remain temporarily unsupported until compatibility gates pass.

### Confirmation

This decision is validated when:

1. Built-in mission templates targeted for 2.0 pass runtime compatibility checks.
2. Audit primitive behavior is deterministic across repeated runs.
3. `next`/decision flow can process audit checkpoints end-to-end.
4. No new 1.x feature scope appears in release changelogs for this initiative.

## Pros and Cons of the Options

### Option 1: CLI-only audit, no mission primitive

Attach audit behavior directly to commands.

**Pros:**

1. Fastest path to initial feature.
2. Low immediate runtime dependency.

**Cons:**

1. Weakens mission as central control abstraction.
2. Harder to compose, test, and extend reliably.

### Option 2: Mission-declared audit primitive with hardening gates

Extend runtime contract and enforce compatibility.

**Pros:**

1. Strong architecture alignment and composability.
2. Better long-term maintainability.

**Cons:**

1. Requires template/schema and testing investment.
2. Requires cross-repo sequencing discipline.

### Option 3: Delay hardening and ship ad hoc audit first

Ship quickly, refactor later.

**Pros:**

1. Short-term delivery speed.
2. Defers hard compatibility work.

**Cons:**

1. High refactor risk and technical debt.
2. Increases probability of contract drift across repos.

## More Information

1. PRD reference:
   `<spec-kitty-planning-repo>/product-ideas/mission-collaboration-platform-ddd/prd-mission-post-merge-audit-and-verify-repurpose-v1.md`
2. Existing primitive context model:
   `src/doctrine/missions/primitives.py`
3. Runtime bridge integration point:
   `src/specify_cli/next/runtime_bridge.py`
4. Built-in mission runtime templates:
   `src/doctrine/missions/*/mission-runtime.yaml`
   `src/doctrine/missions/*/mission.yaml`
