---
title: 'ADR 1 (2026-04-09): Mission Identity Uses ULID, Not Sequential Prefix'
description: 'Missions get a creation-time ULID as canonical machine identity; the sequential number becomes display metadata no selector or state file may resolve by.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-09'
---

## Context and Problem Statement

Mission creation currently allocates the next mission number by scanning local
`kitty-specs/` and local `.worktrees/` for directory names that begin with a
three-digit prefix, then returning `max(found) + 1`.

That allocator is local-only. It has no shared registry, no reservation step,
no merge-time canonicalization, and no protection against parallel authors who
branch from the same base commit. In a distributed workflow, two independent
clones can both observe the same maximum prefix and both allocate the same next
number for different missions.

This is not a theoretical problem.

* PR #555 was created as `077-planning-artifact-and-query-consistency` while
  `main` independently landed `077-mission-terminology-cleanup`.
* The resulting merge from `origin/main` into that branch produces a real
  collision in `kitty-specs/` and content conflicts in docs, runtime, and test
  files.
* `main` already contains multiple duplicate numeric mission prefixes, proving
  that the sequential prefix is not a globally unique identifier in production
  data.

At the same time, the codebase has already begun migrating to a different model:
downstream runtime and merge-state systems increasingly treat `mission_id` as
the canonical machine-facing identity. The remaining gap is that mission
creation still emits only the sequential prefix and human-readable slug as the
effective primary key.

The architecture decision is therefore not to design a new dense counter that
works under partition. The decision is to finish the migration to a stable,
partition-safe mission identity model.

## Decision Drivers

* Spec Kitty must support concurrent mission creation across independent clones.
* Canonical mission identity must be unique without requiring online
  coordination.
* Existing dense numeric prefixes are already proven non-unique and cannot be
  relied on as machine-facing identifiers.
* The codebase already has partial `mission_id` adoption in runtime and merge
  flows; the architecture should align with that direction instead of adding a
  second identity scheme.
* Human-readable mission labels remain useful, but readability must not come at
  the cost of correctness.

## Considered Options

* Option A: Keep sequential numeric mission prefixes as the canonical identity
* Option B: Keep sequential prefixes, but allow manual or explicit override
* Option C: Add an online reservation or registry for mission numbers
* Option D: Make `mission_id` (ULID) the canonical mission identity and demote
  `mission_number` to display metadata

## Decision Outcome

**Chosen option: Option D — make `mission_id` a creation-time ULID and treat it
as the canonical mission identity for all machine-facing behavior.**

### Decision

1. Every new mission must receive a `mission_id` at creation time.
2. `mission_id` is the canonical machine-facing identity for missions.
3. `mission_number` is not a canonical identifier. It is descriptive,
   human-facing metadata only.
4. Any machine-facing selector, state file, merge primitive, work-package
   reference, status artifact, or synchronization payload must resolve by
   `mission_id` rather than by sequential mission number.
5. Human-facing mission handles such as path names, branch names, and UI labels
   must stop assuming that the three-digit prefix is unique. These handles may
   include a shortened mission-id-derived alias for readability, but the full
   `mission_id` remains authoritative.
6. Dense sequential mission numbers may still exist as display aliases, but
   they are assigned or finalized only in a context that has a single source of
   truth, such as `main`. They must not be used as stable pre-merge identity.

### Consequences

#### Positive

* Mission creation becomes partition-safe without requiring online
  coordination.
* Existing runtime and merge-state code that already prefers `mission_id`
  aligns with the documented architecture.
* Duplicate numeric prefixes no longer threaten correctness because they cease
  to be identity-bearing.
* The architecture cleanly separates stable machine identity from mutable,
  human-facing display labels.

#### Negative

* Existing missions require a backfill migration for `mission_id`.
* Existing duplicate numeric prefixes on `main` must be cleaned up so legacy
  selectors and documentation stop encountering ambiguous mission references.
* Paths, branch names, selectors, and operator habits that currently rely on
  numeric mission prefixes require a staged migration and deprecation window.

#### Neutral

* ULID is chosen for uniqueness and rough chronological ordering. No stronger
  causal ordering primitive is required for mission identity itself.
* This ADR does not lock in an exact short-handle format for paths or branch
  names, only the architectural rule that the sequential prefix is no longer
  canonical identity.

### Confirmation

This ADR is considered implemented when all of the following are true:

1. New missions always write `mission_id` at creation time.
2. A repository audit can report zero missions missing `mission_id`.
3. Runtime and merge flows no longer depend on numeric mission prefixes being
   unique.
4. Duplicate mission prefixes on `main` no longer create selector ambiguity or
   identity ambiguity.
5. `mission_number` is absent from machine-facing contracts that require stable
   identity, or is clearly documented there as display-only metadata.

## Pros and Cons of the Options

### Option A: Keep sequential numeric mission prefixes as the canonical identity

Continue using `max(local prefixes) + 1` and rely on `NNN-slug` for mission
identity.

**Pros:**

* Preserves the current naming model.
* Keeps mission references short and familiar.

**Cons:**

* Cannot survive concurrent offline creation.
* Already disproven by duplicate prefixes on `main`.
* Forces correctness to depend on a dense counter in a distributed system.

**Why Rejected:** The current model is already failing in real repository data.

### Option B: Keep sequential prefixes, but allow manual or explicit override

Permit the caller to supply the number explicitly when collisions are expected.

**Pros:**

* Small local change to current behavior.
* Gives operators a manual escape hatch.

**Cons:**

* Pushes distributed coordination onto humans.
* Does not create a canonical unique machine identity.
* Leaves the underlying race intact.

**Why Rejected:** Manual override is a workaround, not an architecture.

### Option C: Add an online reservation or registry for mission numbers

Reserve the next number through `main` or another shared authority before
creating a mission.

**Pros:**

* Preserves dense numbers as canonical from birth.
* Prevents duplicate allocation while online.

**Cons:**

* Requires coordination at mission creation time.
* Fails the partition-tolerant offline workflow requirement.
* Adds operational complexity around retries, lock ownership, and reservations.

**Why Rejected:** Online reservation solves a different problem than the one
Spec Kitty needs to support.

### Option D: Make `mission_id` (ULID) the canonical mission identity and demote `mission_number` to display metadata

Mint a ULID at mission creation and use it as the stable identity everywhere
that correctness depends on uniqueness.

**Pros:**

* Partition-safe by design.
* Matches the direction already present in runtime and merge-state code.
* Separates stable identity from human-facing display labels.
* Enables a staged migration instead of a single all-or-nothing rewrite.

**Cons:**

* Requires backfill and migration for old missions.
* Requires follow-up work to remove remaining prefix-based assumptions.
* Human-facing handles need a new convention once numeric prefixes stop being
  canonical.

**Why Chosen:** It is the only option that matches Spec Kitty's distributed
workflow model while fitting the repository's partially completed migration
direction.

## More Information

Relevant repository evidence:

* Mission number allocation scans local `kitty-specs/` and `.worktrees/` only:
  `src/specify_cli/core/worktree.py`
* Mission creation currently formats the mission slug from that sequential
  number and does not write `mission_id`:
  `src/specify_cli/core/mission_creation.py`
* Runtime lane manifests already describe `mission_id` as the immutable
  machine-facing identity:
  `src/specify_cli/lanes/models.py`
* Merge state is already scoped by `mission_id`:
  `src/specify_cli/merge/state.py`

Follow-up implementation work is intentionally tracked outside this ADR so the
architectural decision remains stable while the migration plan is executed in
phases.
