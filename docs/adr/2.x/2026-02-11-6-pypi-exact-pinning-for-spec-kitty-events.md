---
title: PyPI Exact Pinning for `spec-kitty-events` Across Consumer Repos
description: Forces the CLI and the hosted backend onto the same exact published version of the events contract, banning git refs and committed path overrides that caused drift.
status: Accepted
date: '2026-02-11'
doc_status: active
kind: ADR
updated: '2026-02-11T00:00:00Z'
---

## Context and Problem Statement

`spec-kitty-events` is the canonical contract authority for event envelope fields and reducer semantics used by both:

* `spec-kitty` (CLI)
* `spec-kitty-saas` (server projections)

Before this decision, consumers used mixed sourcing strategies:

* direct git commit references in one repo
* local path overrides in committed config in another repo
* non-normalized pre-release version strings

This created a high risk of semantic drift between development, CI, and production and made cross-repo replay/projection parity less reliable.

## Decision Drivers

* **Determinism:** identical reducer and schema behavior across all environments
* **Contract integrity:** no implicit local-path overrides in committed config
* **Reproducibility:** exact dependency versions, not floating refs
* **Open-source usability:** consumers can install from public package index
* **Diligence readiness:** clear release artifacts and upgrade history

## Considered Options

* **Option 1:** PyPI exact pins (`==`) in all consumer repos (chosen)
* **Option 2:** Git SHA direct references in all consumer repos
* **Option 3:** Local path overrides for active development
* **Option 4:** Version ranges (`>=`, `~=`) with lockfile mediation

## Decision Outcome

**Chosen option:** PyPI exact pinning with strict consumer parity.

### Policy

1. `spec-kitty-events` publishes contract releases to PyPI.
2. `spec-kitty` and `spec-kitty-saas` pin `spec-kitty-events` with exact `==` versions.
3. Committed dependency sources must not use local path overrides for `spec-kitty-events`.
4. Upgrades happen only through coordinated contract-bump changes across consumer repos.
5. Local developer overrides are permitted only in uncommitted/local-only configuration.

### Initial implementation

* `spec-kitty` dependency pin set to `spec-kitty-events==0.4.0a0`.
* `spec-kitty-saas` dependency pin set to `spec-kitty-events==0.4.0a0`.
* committed path source override for `spec-kitty-events` removed from `spec-kitty-saas`.

## Consequences

### Positive

* Eliminates committed local-path drift between repos.
* Aligns CLI and SaaS to the same contract artifact from PyPI.
* Makes upgrades auditable and reproducible.
* Improves external contributor and deployment consistency.

### Negative

* Requires explicit release cadence in `spec-kitty-events`.
* Slows ad-hoc cross-repo changes if release process is bypassed.
* Requires CI policy checks to enforce parity and prevent regressions.

### Neutral

* Local co-development remains possible through local-only overrides, but these are no longer valid committed defaults.

## Confirmation and Enforcement

The decision is considered effective when:

1. both consumer repos pin exact same `spec-kitty-events` version
2. no committed local-path source override for `spec-kitty-events` exists
3. CI includes a contract alignment check that fails on version mismatch
4. contract upgrades follow a documented contract-bump PR flow

## Rollout Notes

Recommended follow-up controls:

1. Add CI checks in both consumers to assert exact version parity.
2. Add CI checks rejecting committed local/path/git source overrides for `spec-kitty-events`.
3. Add a reusable "contract bump" PR template for synchronized version updates.
