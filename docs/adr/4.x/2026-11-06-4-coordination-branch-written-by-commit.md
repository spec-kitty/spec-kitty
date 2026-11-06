---
title: 'ADR: a coordination branch is written by commit, not through a coordination worktree'
description: 'Proposed: the coordination branch stays the lifecycle home and the write service commits to it with no coordination worktree; every coordination kind, status.json and migration.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
---

# A coordination branch is written by commit, not through a coordination worktree

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it, together with the other records of the set (below).

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator). The rulings are recorded as resolved Decision Moments in Mission `lane-worktree-model-hardening-01M6QY1M` (`spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M`); ruling 4 is DM `01M6QY371KRY5XXQMDQ4WZR1YE`.

**Technical Story:**

- [#7284](https://github.com/spec-kitty/spec-kitty/issues/7284) (S9): the worktree-free coordination write is decided before it is built. Epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276). Implementation follows write-service migration step 4 ([#6117](https://github.com/spec-kitty/spec-kitty/issues/6117)); this record builds nothing.
- **Discharges** part of the obligation of [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md) D-6 ("each of those needs its own ADR before such an adapter is built"); the mapping is in that record's Amendment 2026-11-06. This record supplies the step that amendment names **4a**.
- **Amends** [ADR 2026-10-27-1](2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md) D-3: `destinationRef` is required for the coordination surface (D-7 below).
- **Amends** ADR 2026-10-22-1 open question 2: write-location resolution for coordination Missions moves into the service at step 4 (its default), and the location it resolves is a ref, not a worktree.
- **Related records of the same set** (all Proposed, accepted together):
  - **C-2** [ADR 2026-11-06-5](2026-11-06-5-gates-over-worktree-less-coordination.md): consolidation gates over a worktree-less coordination branch, and the write fence;
  - **C-3** [ADR 2026-11-06-6](2026-11-06-6-committed-ledger-is-the-coordination-blob.md): the committed ledger of a coordination Mission is the blob on its coordination branch (publication seam, read API, `events tail` cursor);
  - **events ADR-0007** `docs/adr/0007-write-service-commits-coordination-status-by-ref.md` and **events ADR-0008** `docs/adr/0008-read-service-reads-coordination-ledger-from-git-objects.md`, in repository [`spec-kitty/spec-kitty-events`](https://github.com/spec-kitty/spec-kitty-events), branch `issue-7284-coordination-ref-write-adrs`, draft pull request [spec-kitty/spec-kitty-events#215](https://github.com/spec-kitty/spec-kitty-events/pull/215). ADR-0007 decides how the service commits; this record decides what is committed where, and what the CLI retires. ADR-0008 decides how the Java read service reads it.
- **Read side:** [ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) (one status read contract, S1) is the ref read contract this record relies on.
- **Destructive authority:** [ADR 2026-11-06-1](https://github.com/spec-kitty/spec-kitty/pull/7275) (a destructive git operation discharges named proof obligations; on PR #7275, branch `issue-7211-safe-landed-prune`) governs the removal of existing coordination worktrees (D-9).
- **Settlement:** [ADR 2026-11-06-3](2026-11-06-3-topology-is-settled-once-at-first-finalize.md) (topology settled once at first finalize) materializes a coordination worktree today; Consequences say what changes for it at step 4a.

**Reader:** a maintainer building the step-4 write path for coordination Missions, changing the coordination transaction, or retiring the coordination worktree.

**Terms.** "Coordination topology" is `coord` or `lanes_with_coord`. "Coordination branch" is the branch named by `meta.json` `coordination_branch`. "Coordination worktree" is a checkout of it under `.worktrees/<mission>-coord/`. "Repository root checkout" is the main working tree; "PRIMARY partition" is the artifact partition, never the primary branch ([`docs/context/orchestration.md`](../../context/orchestration.md#primary-partition)). "Step 4" and "step 4a" are steps of the migration order of ADR 2026-10-22-1.

---

## Context and Problem Statement

A coordination Mission records its lifecycle on a coordination branch. Today the CLI writes that branch through a coordination worktree. `BookkeepingTransaction` (`src/specify_cli/coordination/transaction.py`) resolves the worktree (`_resolve_coord_worktree_root_for_transaction`), appends the event log there (`append_events`), writes non-event artefacts there (`write_artifact`, `enroll_subprocess_byproducts`), commits with `safe_commit` (`commit`) and cuts the append when the commit fails (`_cut_event_log`, `_rollback`).

The worktree is a second copy of the branch, and each way that copy can be wrong became a refusal code:

| Code | Raised by | Failure |
|---|---|---|
| `COORD_STATUS_SURFACE_DIVERGED` | `coordination/status_surface_guard.py`, `coordination/transaction_errors.py` | the worktree's log lost events its `HEAD` committed |
| `COORD_STATUS_SURFACE_UNREADABLE` | the same | the committed log is malformed, repeats an id or cannot be read |
| `BOOKKEEPING_WORKTREE_MISSING` | `coordination/transaction_errors.py` | the coordination worktree the transaction needs is missing |
| `FALLBACK_COORD_WORKTREE_UNRESOLVED` | `coordination/status_transition.py` | the fallback coordination worktree cannot be resolved |
| `COORDINATION_WORKTREE_UNMATERIALIZED` | `coordination/surface_resolver.py`, `coordination/commit_router.py`, the origin gates | the coordination worktree is declared but not created |

The `mission-write` contract encoded the same worktree: `WriteSurface` `coordination_transaction_append` was "an append inside the coordination transaction, in the coordination worktree", and the five codes above were protocol codes too.

The operator ruled on 2026-11-06 (ruling 4, and rulings 2, 3 and 8 of epic #7276): the coordination branch stays the lifecycle home; the resolved status surface is the only source of truth; lane branches carry no status copies; and the Java write service writes coordination status **without a coordination worktree**. ADRs only; the implementation follows migration step 4.

The coordination transaction writes more than status events. A rule that covers only `status.events.jsonl` would leave notes, trace, issue matrix and decision artefacts still needing a worktree, so the worktree could never be retired. This record covers every coordination-partition kind.

## Decision Drivers

- One source of truth: the committed tree of the coordination branch. A working tree is a second copy that can diverge (ruling 8).
- One writer per ref: the write service (ADR 2026-10-22-1 D-1, D-5: no Python fallback writer).
- Nothing may keep needing a coordination worktree once step 4a ships; a kind without a rule blocks the retirement.
- Existing coordination Missions must keep working through the cut: no release in which their status writes are refused.
- Every destructive step goes through the one destructive authority (ruling 7, `git/destructive_guard.py`).
- The `mission-write` contract must change before its `1.0.0` (ADR 2026-10-27-1: a closed-response change after `1.0.0` is a major).

## Considered Options

1. **The coordination branch is written by commit, through the write service, for every coordination-partition kind** (chosen).
2. **Keep a coordination worktree, owned by the service.**
3. **Retire the coordination branch** and record coordination status on the target or the repository root checkout.

## Decision Outcome

**Chosen option: 1.** Each decision is marked *(ruled)* where it restates an operator ruling and *(derived)* where this record derives it. Choices the rulings leave open are given as options with a **recommendation**; they stay open until the operator accepts this record (Mission assumption A-12).

### D-1: the coordination branch stays the lifecycle home and is written by commit *(ruled)*

- The coordination branch remains where a coordination Mission's lifecycle lives (ruling 2). Nothing moves to the target or to the repository root checkout.
- From step 4a, no coordination worktree is created, for new or existing Missions. Every write to the coordination branch is a commit built from git objects and moved onto `refs/heads/<coord>` by compare-and-swap, by the write service (events ADR-0007 D-1, D-3). No index, working tree or checkout of the repository is touched.
- Lane branches carry no status copies (ruling 3, as restated in [ADR 2026-07-29-1](../3.x/2026-07-29-1-lane-base-recorded-planning-commit.md) Amendment 2026-11-06).

### D-2: this is a new storage adapter in ADR 2026-10-22-1 D-6's sense *(derived)*

Committing into the object store is not "the local file ledger": the file is no longer appended in place, and readers read a blob, not a path. D-6 therefore applies: the coordination ledger may move to git objects only after the records it lists exist. This set (C-1, C-2, C-3, events ADR-0007, events ADR-0008) is those records; ADR 2026-10-22-1 Amendment 2026-11-06 maps each D-6 bullet to one of them.

### D-3: every coordination-partition kind has a rule *(derived; the artefact rule is open with a recommendation)*

| Kind | Writer today (through `BookkeepingTransaction`) | From step 4a |
|---|---|---|
| Status events (`status.events.jsonl`) | `append_events` | the write service, `writeSurface: coordination_ref_commit` (events ADR-0007) |
| `status.json` | the transaction's materialize step | D-4 |
| Notes, trace (`traces/*.md`) | `write_artifact` | the artefact rule below |
| Issue matrix (`issue-matrix.json`) | `write_artifact` (`tasks/issue_matrix.py`) | the artefact rule below |
| Decision artefacts (`decisions/`) | `decisions/service.py` (4 call sites) | the artefact rule below |
| Subprocess byproducts | `enroll_subprocess_byproducts` (`tasks_move_task_gates.py`, `workflow.py`, `implement_planning_commit.py`) | the artefact rule below |

**The artefact rule** (open; it ties to [#7266](https://github.com/spec-kitty/spec-kitty/issues/7266), artefact placement):

- **(a) The service gains an artefact operation on the same surface.** A `coordination_ref_commit` unit may carry artefact blobs (path, bytes) beside its rows, committed in the same compare-and-swap commit. One writer per ref; one commit per unit; the transaction's "rows and artefacts land together" property is kept.
- **(b) The non-status kinds move to the PRIMARY partition** (#7266). The coordination branch then carries only the event log, and the kinds are written where PRIMARY artefacts are written today.
- **(c) The CLI commits the non-status kinds itself**, by plumbing, onto the same ref. Rejected: two writers on one ref race; the compare-and-swap detects it, but every race becomes a refusal on one side, and it breaks "one writer" (ADR 2026-10-22-1 D-1).

**Recommendation:** (a) as the default for every kind, so step 4a does not wait on #7266; #7266 may later move a kind to PRIMARY under (b), and that kind then leaves this surface. Whatever is chosen, it is chosen per kind, before step 4a, and no kind is left without a rule.

**The decision ledger.** [ADR 2026-10-01-3](2026-10-01-3-decision-ledger-primary-partition.md) places the decision ledger on the PRIMARY partition, yet `decisions/service.py` writes through the coordination transaction. **Recommendation:** follow ADR 2026-10-01-3 (option (b) for decision artefacts), and treat the transaction route as the drift to remove; confirm with #7266 before step 4a.

### D-4: `status.json` on the coordination branch *(open with a recommendation)*

- **(a) Not committed on the coordination branch.** It is derived; readers reduce the committed log (`materialize_snapshot`, read-only). The drain commit of D-9 removes the coordination branch's copy. The target's `status.json` is still written by consolidation's own bookkeeping, as today.
- **(b) The service recomputes it in the same commit.** The Java reducer must then produce `status.json` byte for byte as the Python `materialize` does: a new fixture family and a second derived-file writer.
- **(c) The CLI keeps writing it.** Rejected: a second writer on the ref (D-3 (c)).

**Recommendation: (a).** It keeps events ADR-0007's commit at "only the event log path changed", adds no byte-parity surface, and fits the S10 late window as written: a change to `status.json` between the window base and the tip is judged **derived** while the target's committed snapshot is the reduction of its committed log ([ADR 2026-09-19-1](../3.x/2026-09-19-1-terminus-safety-invariant.md) Amendment 2026-11-06, on PR #7274), so the drain commit's removal is not refused.

### D-5: the read contract is "read the ref" *(derived)*

Readers of a coordination Mission read `refs/heads/<coord>`, never a coordination working tree. The contract is [ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) (the `COORD_BRANCH_REF` source, the ref reader's `ABSENT` versus `StatusSurfaceRefUnreadable` split, `CoordinationBranchDeleted` unchanged). At step 4a its `COORD_WORKTREE` row retires: a coordination Mission is always in the "unmaterialized" state, which reads the ref. How a missing ref is answered, and the parity of that answer with the Java read service, is C-3's D-3.

### D-6: the events-side contract this record relies on *(cites events ADR-0007 D-7)*

`mission-write` `1.0.1-SNAPSHOT` (the operator ruled on 2026-11-06 that `1.0.0-SNAPSHOT`, shipped in `service-v0.1.0-rc.1` and `rc.2`, is not rewritten):

- `WriteSurface`: `coordination_transaction_append` is **replaced** by `coordination_ref_commit`; `checkout_append` **narrows** to the repository root checkout only (a lane checkout is never a status surface).
- New refusal codes, provisional while ADR-0007 is Proposed: `COORDINATION_REF_MOVED` (409), `COORDINATION_REF_CHECKED_OUT` (409), `COORDINATION_LEDGER_UNREADABLE` (500).
- Removed protocol codes: the five of the Context table.
- `RequestContext`: for `coordination_ref_commit`, `missionDirectory` is the path in the tree of `destinationRef`, and `destinationRef` is required (D-7).

Core's client (`src/specify_cli/status/write_service_protocol.py`, a core file per [ADR 2026-10-29-1](2026-10-29-1-the-events-domain-and-its-java-services-live-in-spec-kitty-events.md) D-7) follows: its `WriteSurface` and `WriteRefusalCode` enums and `_SURFACE_BY_TARGET` take the new values when core vendors a service pin that serves `1.0.1`.

### D-7: `destinationRef` becomes required for the coordination surface *(derived; amends ADR 2026-10-27-1 D-3)*

ADR 2026-10-27-1 D-3 keeps `destinationRef` null "until placement moves into the service". For `coordination_ref_commit` it is **required and non-empty**, from the first release that serves the surface:

- `transition_unit_from` (`status/write_service_protocol.py`) sets `destinationRef` to the Mission's coordination branch, read from `meta.json` `coordination_branch`, and sets `missionDirectory` to the **tree-relative** path (`kitty-specs/<mission-dir>`), not a path relative to a checkout.
- The service resolves the coordination branch itself and refuses a request whose `destinationRef` differs with `WRITE_LOCATION_UNVERIFIED` (events ADR-0007 D-4).
- `checkout_append` keeps D-3's null `destinationRef` until its own placement moves into the service.

### D-8: the CLI-side codes retire with the worktree, at step 4a, not now *(derived)*

`COORD_STATUS_SURFACE_DIVERGED`, `COORD_STATUS_SURFACE_UNREADABLE`, `BOOKKEEPING_WORKTREE_MISSING`, `FALLBACK_COORD_WORKTREE_UNRESOLVED` and `COORDINATION_WORKTREE_UNMATERIALIZED` retire **in the release that ships step 4a**, with the worktree they describe. Until then they stay live: they guard the worktree that still exists. With no working tree, divergence cannot occur and there is nothing to materialize. A use of `BOOKKEEPING_WORKTREE_MISSING` outside a coordination topology, if any remains at step 4a, is audited then and keeps its own meaning only if it does not name a coordination worktree. The `status_surface_guard` module and its tests retire with them.

### D-9: existing coordination worktrees are drained, then removed under the destructive guard *(derived)*

A one-way, clone-local upgrade migration (`clone_local_effect = True`: worktrees live outside version control; its `apply()` is idempotent), shipped in the step-4a release, visits every coordination worktree of the clone:

1. **Mid-operation refuses.** A worktree with `MERGE_HEAD`, a rebase, a cherry-pick or a bisect in progress is kept and reported; nothing is changed.
2. **Drain.** The worktree's log must hold every event its `HEAD` committed (the guard's own check, run one last time). Uncommitted rows the worktree holds beyond `HEAD` are committed onto the coordination branch by the last use of the old writer, before the cut. Any other uncommitted or untracked path that is not residue refuses, and the worktree is kept and reported with the path list. "Drained" means clean and committed, or refused.
3. **Seed.** A Mission in WP01's pre-seed state (the coordination branch exists, its log path is absent, the write checkout holds rows) gets those rows committed onto the coordination branch, so that from step 4a a readable ref without the path means "no events" (C-3 D-3).
4. **Remove.** The worktree is removed through `git/destructive_guard.py` under the obligations of ADR 2026-11-06-1 that apply to a worktree removal: O1, O2, O5, O7 and O8. The coordination **branch is never deleted** by this migration, so O3, O4 and O6 do not arise. "Probe unavailable means keep and report" applies (O2), as it does for lane cleanup.
5. **Report.** A kept worktree is reported with its code, remedy and command. Until it is resolved, that Mission's status writes refuse with `COORDINATION_REF_CHECKED_OUT`, which is the honest answer: the branch is still checked out.

### D-10: rollout ordering: steps 4 and 4a ship together *(derived from events ADR-0007's precondition; this record owns the ordering)*

`coordination_ref_commit` goes live **only in the same release** as both:

- this record's artefact rule (D-3: notes, trace, issue matrix, decisions, byproducts; #7266), and
- the drain and removal of existing coordination worktrees (D-9).

That is, migration steps 4 and 4a of ADR 2026-10-22-1 land in one release. Otherwise, from step 4 on, the CLI has no coordination status writer (ADR 2026-10-22-1 D-5: no Python fallback writer; step 4 deletes the Python appenders), and every existing coordination Mission is refused with `COORDINATION_REF_CHECKED_OUT` on every transition, because its worktree still checks the branch out (events ADR-0007 D-3).

### D-11: what stays open *(open)*

- Whether `lanes_with_coord` needs a rule of its own beyond `coord` (default: none; both read and write the coordination ref alike).
- The owned-checkout (`--owned-checkout`) interplay: an owned checkout of a coordination Mission is a checkout, not a status surface (default: it follows D-5 for reads and never holds the coordination branch).
- The artefact rule (D-3) and `status.json` (D-4), as above.

### Consequences

#### Positive

- The five worktree failure codes disappear by construction, with their guard.
- A unit of work is atomic on the ref: the branch moves to a commit holding all its rows (and, under D-3 (a), its artefacts), or it does not move.
- Every reader and writer of a coordination Mission sees one copy: the committed tree.
- No coordination worktree to create, materialize, resync, reset or tear down (C-2 lists what consolidation loses).

#### Negative

- No repository hook runs on a status commit (events ADR-0007 runs with an emptied `core.hooksPath`).
- The step-4 release is larger: steps 4 and 4a, the artefact rule and a migration ship together (D-10).
- A coordination worktree the migration has to keep blocks that Mission's status writes until the operator resolves it (D-9 step 5).
- [ADR 2026-11-06-3](2026-11-06-3-topology-is-settled-once-at-first-finalize.md): from step 4a, settlement no longer materializes a coordination worktree; it records the designation only. Its move of the repository root checkout off the topic branch stays needed, now because the service refuses to write a checked-out coordination branch.

#### Neutral

- The coordination branch, its name, its role at consolidation and its retention are unchanged ([ADR 2026-10-13-2](2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md) D-3; C-3 D-5).
- `single_branch` and `lanes` Missions keep `checkout_append` in the repository root checkout.

### Confirmation

Named here, **to be written by the step-4 Mission**; none exists yet:

- `tests/coordination/test_coordination_ref_commit_kinds.py`: every coordination-partition kind of D-3 is written with no coordination worktree on disk, and the commit's parent is the prior tip.
- `tests/status/test_write_service_protocol_coordination_ref_commit.py`: `transition_unit_from` sets a non-empty `destinationRef` and a tree-relative `missionDirectory` for `coordination_ref_commit`, and keeps `destinationRef` null for `checkout_append`.
- `tests/upgrade/test_coordination_worktree_drain_migration.py`: a clean worktree is drained and removed; uncommitted rows are committed first; a dirty non-residue path, a mid-operation worktree and an unavailable process probe each keep and report; the branch survives; a second run is a no-op; a pre-seed Mission's rows are seeded onto the ref.
- `tests/architectural/test_coordination_worktree_retired.py`: no code path creates a coordination worktree, and the five retired codes of D-8 appear nowhere in `src/` (planted-violation self-test).
- `tests/architectural/test_coordination_ref_commit_rollout.py`: the release that serves `coordination_ref_commit` registers the D-9 migration in the order manifest (D-10).
- The events-side tests of events ADR-0007's Confirmation (`command-cli` in `spec-kitty-events`).

## Pros and Cons of the Options

### 1. Written by commit through the service (chosen)

- Good: one copy, one writer, atomic units, lost updates detected; the worktree's failure modes disappear.
- Bad: no hooks on status commits; a larger step-4 release; a migration with a destructive step.

### 2. A coordination worktree owned by the service

- Good: closest to today's code.
- Bad: keeps the second copy and every failure mode the rulings retire; the service would own a checkout's lifecycle.

### 3. Retire the coordination branch

- Good: no coordination ref to fence.
- Bad: contradicts ruling 2; puts in-flight lifecycle on the target, where a protected target refuses it (`PROTECTED_BRANCH_REFUSED`).

## More Information

- Mission discovery map: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/doctrine-and-write-service-adr-map.md` (Part 2).
- Mission research R-10 (`kitty-specs/lane-worktree-model-hardening-01M6QY1M/research.md`).
- The events records: `docs/adr/0007-write-service-commits-coordination-status-by-ref.md` and `docs/adr/0008-read-service-reads-coordination-ledger-from-git-objects.md` in `spec-kitty/spec-kitty-events`, branch `issue-7284-coordination-ref-write-adrs`, PR [#215](https://github.com/spec-kitty/spec-kitty-events/pull/215); the contract change is `contracts/mission-write/CHANGELOG.md` there.
