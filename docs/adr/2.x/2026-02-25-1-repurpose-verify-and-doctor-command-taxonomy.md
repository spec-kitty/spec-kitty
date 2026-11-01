---
title: Repurpose `verify` and Move Setup Checks Under `doctor`
description: Reassigns verify to checking delivered implementation against artifacts and relocates setup diagnostics under doctor setup, matching what users expect each verb to mean.
status: Accepted
date: '2026-02-25'
doc_status: active
kind: ADR
updated: '2026-02-25T00:00:00Z'
---

## Context and Problem Statement

In current CLI behavior, `spec-kitty verify-setup` is the setup diagnostics entrypoint and the root command function name (`verify_setup`) maps to `spec-kitty verify-setup`.
Current command registration still binds `verify_setup` at top level, and the only existing `doctor` surface is nested under `spec-kitty agent status doctor`.

For 2.x, product intent is that `verify` should represent implementation-vs-artifact validation (post-merge mission audit), not environment diagnostics.

This creates a namespace and semantic conflict that blocks a clean audit UX.

## Decision Drivers

1. Align command semantics with mission-oriented 2.x behavior.
2. Keep top-level command names intuitive for humans and agents.
3. Minimize migration pain for existing users and automation.
4. Preserve deterministic CLI contracts during rollout.

## Considered Options

1. Keep `verify-setup` as-is and introduce `audit` as a separate command.
2. Repurpose `verify` for mission audit and move diagnostics to `doctor setup` (chosen).
3. Keep `verify` for diagnostics and introduce a new audit-only name.

## Decision Outcome

**Chosen option:** "Repurpose `verify` for mission audit and move diagnostics to `doctor setup`", because it best matches user expectation and 2.x mission verification direction.

### Command Contract

1. `spec-kitty verify` runs mission audit for the selected/current feature context.
2. `spec-kitty doctor setup` runs environment/setup diagnostics.
3. `spec-kitty verify-setup` remains as a compatibility alias to `doctor setup` with deprecation warning.
4. Deprecation period is explicit and versioned in release notes.

### Consequences

#### Positive

1. Command names match user mental model (`verify` = validation, `doctor` = diagnostics).
2. Clean base for mission-native audit UX.
3. Reduced ambiguity in prompt templates and agent instructions.

#### Negative

1. Existing scripts using `verify-setup` must migrate.
2. Requires docs, onboarding, and template updates.

#### Neutral

1. Short-term alias support adds temporary command redundancy.

### Confirmation

This decision is correct when:

1. `verify` and `doctor setup` both operate with stable CLI behavior.
2. New user guidance references `verify` for post-merge audit without confusion.
3. Alias usage trends downward across release telemetry.

## Pros and Cons of the Options

### Option 1: Keep `verify-setup`, add separate `audit`

Use a new command family while leaving diagnostics untouched.

**Pros:**

1. Minimal immediate migration work.
2. Lower risk of breaking old scripts.

**Cons:**

1. Preserves semantic confusion around `verify` naming.
2. Increases command-surface complexity.

### Option 2: Repurpose `verify`, move diagnostics to `doctor setup`

Adopt clear command taxonomy with explicit diagnostics namespace.

**Pros:**

1. Strong semantic alignment.
2. Better long-term command design.

**Cons:**

1. Requires migration and deprecation handling.
2. Requires broad docs/template updates.

### Option 3: Keep `verify` for diagnostics, create new audit-only verb

Retain old behavior and avoid touching existing verify paths.

**Pros:**

1. Least churn for legacy CLI behavior.
2. Straightforward short-term implementation.

**Cons:**

1. Conflicts with product expectation that verification means artifact validation.
2. Leaves 2.x mission audit UX less discoverable.

## More Information

1. PRD reference:
   `<spec-kitty-planning-repo>/product-ideas/mission-collaboration-platform-ddd/prd-mission-post-merge-audit-and-verify-repurpose-v1.md`
2. Existing command registration:
   `src/specify_cli/cli/commands/__init__.py`
3. Existing diagnostics command implementation:
   `src/specify_cli/cli/commands/verify.py`
