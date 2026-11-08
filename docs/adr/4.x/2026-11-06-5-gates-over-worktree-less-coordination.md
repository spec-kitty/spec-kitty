---
title: 'ADR: consolidation gates hold over a coordination branch with no worktree'
description: 'Proposed: ref-reading gates are unchanged, the late window reads a pinned ref, the write fence is the compare-and-swap, and resume and rollback lose the coordination checkout role.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
updated: '2026-11-06T00:00:00Z'
---

# Consolidation gates hold over a coordination branch with no worktree

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it, together with the other records of the set.

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator). Ruling 4 of epic #7276 is DM `01M6QY371KRY5XXQMDQ4WZR1YE` in Mission `lane-worktree-model-hardening-01M6QY1M`.

**Technical Story:**

- [#7284](https://github.com/spec-kitty/spec-kitty/issues/7284) (S9), epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276). ADRs only; the implementation follows migration step 4 ([#6117](https://github.com/spec-kitty/spec-kitty/issues/6117)).
- **Discharges** the D-6 bullets of [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md) on merge semantics and on the consolidation gates (mapping in that record's Amendment 2026-11-06).
- **Cites, does not re-decide:** the S10 late-window pass, [#7265](https://github.com/spec-kitty/spec-kitty/issues/7265), recorded as Amendment 2026-11-06 of [ADR 2026-09-19-1](../3.x/2026-09-19-1-terminus-safety-invariant.md) on PR [#7274](https://github.com/spec-kitty/spec-kitty/pull/7274) (branch `issue-7198-late-window-one-pass`). Mission constraint C-005.
- **Related records of the same set:** **C-1** [ADR 2026-11-06-4](2026-11-06-4-coordination-branch-written-by-commit.md) (the coordination branch is written by commit), **C-3** [ADR 2026-11-06-6](2026-11-06-6-committed-ledger-is-the-coordination-blob.md) (the committed ledger is the coordination blob), **events ADR-0007** `docs/adr/0007-write-service-commits-coordination-status-by-ref.md` and **events ADR-0008** `docs/adr/0008-read-service-reads-coordination-ledger-from-git-objects.md` in [`spec-kitty/spec-kitty-events`](https://github.com/spec-kitty/spec-kitty-events), branch `main` (merged from `issue-7284-coordination-ref-write-adrs`), PR [spec-kitty/spec-kitty-events#215](https://github.com/spec-kitty/spec-kitty-events/pull/215).
- Builds on [ADR 2026-10-04-5](2026-10-04-5-approval-stamp-bounds-the-approved-claim.md) (approval stamp bounds the claim) and [ADR 2026-02-09-3](../2.x/2026-02-09-3-event-log-merge-semantics.md) (event log merge semantics), both unchanged.

**Reader:** a maintainer changing consolidation (claim, gate, late window, teardown, rollback, resume) for coordination Missions once the coordination worktree is retired (C-1 step 4a).

---

## Context and Problem Statement

C-1 retires the coordination worktree: from step 4a the write service commits coordination status straight onto `refs/heads/<coord>`. Consolidation reads and moves that branch today, and some of its steps use the worktree:

- **Gates that read refs** (the approval bound `consolidation/approved_bound.py::check_lane`, the claim build `reconciliation.build_approved_wp_set`, the attribution axes `wp_attribution`, `line_attribution` and the blob axis, owned-file evidence `wp_evidence`, and the `lane_head` stamps of `status/lane_head.py`) never needed a checkout.
- **The late projection window** folds the coordination worktree's working-tree log into the status union; S10's pass names that as its one exception to "read `T`, never the live branch".
- **Rollback and resume** resync the coordination checkout (`git/ref_advance.py::resync_checkouts_to_tip`, called by `consolidation/rollback.py`) and recover it in place with `reset --hard` (one of the four checkout roles of `consolidation/resume_recovery.py`).
- **Teardown** destroys the coordination triple (branch, worktree, marker) behind `coordination/teardown.py::ProjectionTeardownGate`.

Two writers then move the coordination branch: the Java service (status units) and consolidation (its teardown delete). Something must keep them from losing each other's updates.

## Decision Drivers

- No gate weakens (Mission constraint; ADR 2026-10-04-5 and ADR 2026-09-19-1 unchanged in what they prove).
- S10's pass is consumed, not redesigned (C-005).
- A lost update on the coordination branch must be impossible, not unlikely.
- The fewest new cross-language couplings between the Java service and consolidation's Python state.

## Considered Options

For the write fence (D-4), the open choice of this record:

1. **The compare-and-swap alone** (recommended).
2. **The service refuses coordination writes while a consolidation record holds the Mission.**
3. **Consolidation writes its coordination bookkeeping through the service.**

## Decision Outcome

Each decision is marked *(ruled)*, *(derived)* or *(open)*; open choices carry a recommendation (Mission assumption A-12).

### D-1: ref-reading gates are unchanged *(derived)*

The approval bound, the claim build, the attribution axes, owned-file evidence and the `for_review` gate on the lane branch (S2, Mission WP08) read refs and `lane_head` stamps. They read the status log through the one read door ([ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md)), which for a coordination Mission reads `refs/heads/<coord>` (C-1 D-5). They never needed a checkout and change in nothing: not in their inputs, verdicts, codes or exits.

### D-2: the `lane_head` stamp keeps its meaning *(derived)*

At step 4 the service stamps `policy_metadata.lane_head` from `refs/heads/<lane>` in the command form ([ADR 2026-10-27-1](2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md) D-3; events ADR-0007 D-4). The stamp still means "the lane branch head when the transition was recorded". ADR 2026-10-04-5's bound and the S8 approval windows read it unchanged.

### D-3: the late window reads a pinned ref *(derived; cites S10)*

S10's pass ([ADR 2026-09-19-1](../3.x/2026-09-19-1-terminus-safety-invariant.md) Amendment 2026-11-06, PR #7274) decides what the late window proves and on which tip: the tip `T` is read once; the base is `coord_tip_after_projection` on a first run and `pre_mutation_coord_sha` on a resume; the proof runs over the tree delta `B -> T` against the target ref's committed blobs; only a fully proven `T` is approved, by compare-and-swap. This record changes none of that.

It changes one input. S10 names one exception to "read `T`": the status union folds the coordination worktree's working-tree log. From step 4a there is no such log. **The union reads the event log blob at `T`**, like every other path of the window. Events committed after `T` are therefore outside the window, exactly as S10 already treats every other path. The exception closes by construction, not by a patch.

The merge rules of ADR 2026-02-09-3 (concatenate, deduplicate by event id, refuse one id with two payloads, the wall-clock reduce with the #4990 and #4941 rules) are unchanged; only where their inputs are read changes. ADR 2026-02-09-3 needs no amendment; at most a factual note when step 4a ships.

### D-4: the write fence is the compare-and-swap *(open; recommendation: option 1)*

**Option 1, the compare-and-swap alone (recommended).** Both writers move the coordination ref only by compare-and-swap, and each treats a lost swap as a refusal, never a retry.

- **Service side** (events ADR-0007 D-1, D-3): `update-ref <coord> <new> <T>`, with every git call run under an emptied `core.hooksPath`. After a failed swap the service re-reads the ref: still at `T` (a held ref lock) is `SERVICE_BUSY`; missing is `COORDINATION_BRANCH_DELETED`; any other value is `COORDINATION_REF_MOVED`. Nothing is written.
- **Consolidation side** (unchanged): the late window approves `T` only while the live ref equals `T` (S10); the teardown gate and the compare-and-swap branch delete anchor on that approved tip (`ProjectionTeardownGate`, `git/ref_advance.py`).
- **The races, and what each yields:**
  - a service write between the late window's read of `T` and the teardown delete: the delete's swap fails, teardown keeps the branch and marker and raises `CoordMovedAfterLanding` (`COORD_MOVED_AFTER_LANDING`, exit 75); the next `consolidate --resume` proves the new events (S10);
  - a consolidation move of the ref between the service's read of `T` and its swap: the service refuses with `COORDINATION_REF_MOVED`; the caller re-reads and decides;
  - the branch deleted by teardown before a service write: `COORDINATION_BRANCH_DELETED`; the Mission has landed, and the read door reads the target ([ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) `CONSOLIDATED_TARGET`).
- No update is lost on either side. The cost is a refusal on the slower side of a race, which is rare: a status write during the consolidation of the same Mission.
- It needs nothing new: no code, no shared state between the service and consolidation's record, and it covers `orchestrator-api consolidate-mission` (which has no rollback door) and `consolidate --dry-run` without a fence of their own.

**Option 2, refuse writes while a consolidation record holds the Mission** (a new code, for example `CONSOLIDATION_IN_PROGRESS`). Considered: it turns the exit-75 race into an up-front refusal. Not recommended: the Java service would read consolidation's Python state file (`.kittify/runtime/merge/<mission_id>/state.json`), a new cross-language coupling to an internal format; a record left by a crash blocks every status write until `consolidate --abort`; and the compare-and-swap is still needed for the user and the strangler-period CLI.

**Option 3, consolidation writes its coordination bookkeeping through the service.** Considered: one writer of the ref in every case. Not recommended now: it is migration step 5 of ADR 2026-10-22-1 ("then the consolidation bookkeeping writes") and needs the service to speak consolidation's projection writes. It remains compatible with option 1 and can follow at step 5.

### D-5: resume and rollback lose the coordination checkout role *(derived)*

- **`resync_checkouts_to_tip`** (`git/ref_advance.py`): rollback no longer brings a coordination checkout back to the coordination branch's tip (#5638); there is none. Rollback restores the coordination ref by compare-and-swap only, through the single rollback authority (`consolidation/rollback.py::rollback_to_snapshot`, unchanged). The resync stays for the target and Mission-branch checkouts.
- **`pre_mutation_coord_sha`** (and `pre_mutation_coord_ref`, `pre_interrupt_lane_tips`) stay **ref anchors**: S10's resume base, and the #6770 re-baseline that keeps them on a coordination topology, are unchanged.
- **Resume recovery** (`consolidation/resume_recovery.py`): the in-place `reset --hard HEAD` recovery covers three checkout roles instead of four (repository root checkout, Mission worktree, lane worktree); the coordination worktree role and its `pre_mutation_refs` entry go away.
- **The status-surface guard**, which rollback's resync made a backstop, retires with C-1 D-8.
- **Teardown**: the coordination triple becomes a pair (branch, marker). The gate and the compare-and-swap branch delete are unchanged; the worktree leg is removed. Lane cleanup still runs last, after it (ruling 6; Mission S5).

### D-6: what stays open *(open)*

- Whether `consolidate --dry-run` reads the same once-read tip as a real run (default: yes; its forecast reads `T` once).
- The fence choice of D-4.

### Consequences

#### Positive

- The #7198 class (the late window reading a working-tree log that moved) closes by construction.
- Every gate reads committed git state only; none depends on a checkout existing.
- No new error code and no new shared state between the Java service and consolidation (under option 1).

#### Negative

- Under option 1, a status write that races the consolidation of the same Mission ends one side with a refusal (`COORD_MOVED_AFTER_LANDING`, exit 75, or `COORDINATION_REF_MOVED`); the operator re-runs.
- The resume and rollback code loses a role; tests that pin four roles change at step 4a.

#### Neutral

- The approval bound, claim, attribution, evidence and `for_review` gates are untouched.
- ADR 2026-02-09-3's merge semantics are untouched.

### Confirmation

Existing tests that must stay green, unchanged, at step 4a (D-1, D-2):

- `tests/consolidation/test_approved_bound.py`, `tests/consolidation/test_approved_bound_residuals.py`, `tests/consolidation/test_wp_attribution.py`, `tests/consolidation/test_wp_evidence.py`, `tests/consolidation/test_claim_integrity_refusal.py`;
- `tests/specify_cli/lanes/test_for_review_gate_parity.py` (S2, Mission WP08);
- S10's `tests/coordination/test_projection_teardown.py` and `tests/consolidation/test_late_teardown_projection.py` (PR #7274), with the working-tree-log fixtures replaced by a ref-only coordination branch.

Named here, **to be written by the step-4 Mission**:

- `tests/consolidation/test_late_window_reads_pinned_ref.py`: with no coordination worktree, the union reads the log blob at `T`; an event committed after `T` is not unioned and is proven on the next resume.
- `tests/consolidation/test_coordination_write_fence.py`: a service write between `T` and the teardown delete yields `COORD_MOVED_AFTER_LANDING` (exit 75) with the branch and marker kept; a consolidation move before the service's swap yields `COORDINATION_REF_MOVED`; no event is lost in either case.
- `tests/consolidation/test_rollback_without_coordination_checkout.py`: rollback restores the coordination ref by compare-and-swap and calls no resync for it.
- `tests/consolidation/test_resume_recovery_roles.py`: resume recovery covers exactly three checkout roles.

## Pros and Cons of the Options

### 1. The compare-and-swap alone (recommended)

- Good: no new code or coupling; covers every caller, `orchestrator-api` included; no lost update.
- Bad: a race ends in a refusal on one side.

### 2. Refuse writes while a consolidation record holds the Mission

- Good: the race becomes an up-front refusal with a clear reason.
- Bad: the Java service reads a Python-internal state file; a stale record blocks writes; the swap is still needed.

### 3. Consolidation writes through the service

- Good: one writer of the ref, always.
- Bad: a large contract growth, already scheduled as migration step 5.

## More Information

- Mission discovery map: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/doctrine-and-write-service-adr-map.md` (Part 2, C-2; risk 8).
- S10 design issue [#7265](https://github.com/spec-kitty/spec-kitty/issues/7265) and its residuals (#7271, #7121, #5460), unchanged by this record.
