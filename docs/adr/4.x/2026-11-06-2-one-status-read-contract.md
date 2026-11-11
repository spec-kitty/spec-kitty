---
title: 'ADR: One status read contract'
description: 'Every status read resolves through one door to one declared source per topology and coordination state; never a lane checkout, a missing path or a silent fallback.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
updated: '2026-11-11T00:00:00Z'
---

# One status read contract

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it. Amended 2026-11-08 (below).

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- [#7277](https://github.com/spec-kitty/spec-kitty/issues/7277) (S1 of epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276)): one read contract for Mission status.
- [#6466](https://github.com/spec-kitty/spec-kitty/issues/6466) and [#7198](https://github.com/spec-kitty/spec-kitty/issues/7198): commands report different WP states for one Mission.
- PR [#6884](https://github.com/spec-kitty/spec-kitty/pull/6884) (branch `issue-6466-lane-status-shadow`): a lane root is never a status surface. Its contract is `kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/contracts/status-read-root.md` on that branch.
- Mission `lane-worktree-model-hardening-01M6QY1M`: FR-001 to FR-007, FR-043, FR-061, NFR-001, Rules and Invariants 1 and 2.

> **What was ruled and what is derived.**
> - **Ruled by the operator (2026-11-06, Decision Moments of the Mission).**
>   - Ruling 8 (DM `01M6QY3S1H6G5N853PJAPJS7CE`): "The resolved status surface is the only source of truth; a lane worktree's own status files never count (#6466, #6884)."
>   - Ruling 3 restated (DM `01M6QY3XQJ5NAYVF3GMZ7ZPPRE`): readers never read lane status files. This ADR carries the reader half; the checkout and writer halves are in the amendment of [ADR 2026-07-29-1](../3.x/2026-07-29-1-lane-base-recorded-planning-commit.md).
>   - PRIMARY placement of a default Mission (DM `01M6R0QJVPVZG2QT8MWQD4NXJR`): "Topic branch until consolidate ... explicit --topology Missions keep today's placement ... one read door (S1) carries it."
> - **Derived** (plan and research R-1, R-2, R-4): the source names, the ref reader's result type, fail-closed root normalization, and the precedence of the consolidated state over the coordination probe. Points the rulings leave open are listed under "Open points" with a recommendation.

## Context and Problem Statement

A Mission's status lives in `status.events.jsonl` (with the derived `status.json`). Where that file is
read from depends on the topology and on the state of the coordination worktree. Nine adapters make
that choice today, and for one state, an unmaterialized coordination worktree, they give four answers
(research R-1):

- the write side (`status_transition._read_contract_from_transaction_target`) reads the committed
  coordination branch;
- the surface resolver's loud fallback reads the repository root checkout's stale copy
  ([ADR 2026-06-19-1](../3.x/2026-06-19-1-coord-empty-surface-fallback.md), amendment of 2026-06-21);
- the placement seam raises `CoordinationWorktreeUnmaterialized`
  ([ADR 2026-09-24-2](../3.x/2026-09-24-2-coord-read-fail-closed.md));
- `read_event_log(COORDINATION_BRANCH_REF)` returns `[]` on any `git show` failure, so a broken ref
  reads as genesis.

A command run from inside a lane checkout can also read that lane's inherited copy, which is #6466.
The result is wrong verdicts at exit 0: `agent tasks status`, `next`, `consolidate` and
`orchestrator-api` can disagree about the same WP.

The unmaterialized state is about to become normal, not rare. Lane checkouts become short-lived
(ruling 5, the S3 records) and the S9 write service commits to the coordination branch without a
worktree (C-1, below). A contract that breaks or reads stale data when no coordination worktree is on
disk breaks every reader.

## Decision Drivers

- Ruling 8: one source of truth, and a lane copy never counts.
- Rule 1: a read has exactly one declared source; it is never a lane checkout, never a path that does
  not exist, and never a silent fallback.
- Liveness without a coordination worktree on disk (ruling 5, S9).
- A broken ref must never read as an empty history (FR-004).
- Cost: reading from a ref must stay cheap (NFR-001).

## Considered Options

- **A. One door with a declared source per topology and state; an empty or unmaterialized coordination
  worktree reads the committed coordination branch.**
- **B. Keep the loud repository-root fallback for an empty coordination worktree** (the 2026-06-21
  amendment of ADR 2026-06-19-1, kept by `coord-artifact-single-home-01M3V4BE` C-002).
- **C. Materialize the coordination worktree on read.**
- **D. Raise on an unmaterialized coordination worktree** (the placement seam today).

## Decision Outcome

**Chosen option: A.** It adopts the one adapter that is already right (the write side reads the ref in
that state) and makes every other reader use it.

### The door

`resolve_status_read(repo_root, mission, *, owned=None) -> StatusReadSurface` is the only way a
status read finds its source (FR-001, FR-005). The surface carries `topology`, `source`,
`mission_dir_name`, `path`, `repo_root` (normalized), `ref` and `fallback_reason` (data model §2).
Readers consume a surface through `read_status_events`, `read_status_stream` and `materialize_status`;
writers keep the write seam.

### Sources

| Topology | Coordination state | Source |
|---|---|---|
| any | the Mission has landed on its target (the "landed" signal below) | `CONSOLIDATED_TARGET` |
| `single_branch` (owned checkout included), `lanes`, provisional (`topology_source: default`, not settled) | not applicable | `WRITE_CHECKOUT` |
| `coord`, `lanes_with_coord` | materialized | `COORD_WORKTREE` |
| `coord`, `lanes_with_coord` | empty (worktree root present, Mission directory absent) | `COORD_BRANCH_REF` |
| `coord`, `lanes_with_coord` | unmaterialized (branch exists, no worktree) | `COORD_BRANCH_REF` |
| `coord`, `lanes_with_coord` | branch exists but holds no log yet (pre-seed) | `WRITE_CHECKOUT`, `fallback_reason` set |
| `coord`, `lanes_with_coord` | deleted | raise `CoordinationBranchDeleted` (unchanged) |
| provisional or settled default Mission (`topology_source: default`) | no usable checkout holds the topic branch | `MISSION_BRANCH_REF` |

- **`WRITE_CHECKOUT`** is the working tree of the repository root checkout, or the validated owned
  checkout when `owned` is given. It is never a ref: appends there are not committed yet, so a ref
  read would drop rows.
- **`COORD_WORKTREE`** is the coordination worktree's file. The transaction commits in the same unit
  of work; `status_surface_guard` stays the divergence backstop.
- **`COORD_BRANCH_REF`** is `refs/heads/<coord>:kitty-specs/<dir>/status.events.jsonl`, read with
  `git cat-file --batch`. Owned checkouts of a coordination Mission follow the same rule instead of
  raising (FR-003).
- **`MISSION_BRANCH_REF`** is `refs/heads/<mission_branch>:kitty-specs/<dir>/status.events.jsonl`, for a
  `topology_source: default` Mission whose topic branch no usable checkout holds (for example the
  repository root checkout was switched to another branch). When a checkout does hold the topic
  branch, that checkout is the `WRITE_CHECKOUT` instead. Read like `COORD_BRANCH_REF`; a command that
  needs a file refuses with the door's remedy (`status_surface_on_ref`).
- **Pre-seed fallback.** When the coordination branch exists but carries no log at that path, the door
  returns `WRITE_CHECKOUT` with `fallback_reason` set. The rule is declared, scoped to coordination
  topologies, and visible on the surface, so it is not silent. It covers the explicit-topology create
  window. A default Mission settled to `lanes_with_coord` does not reach it: its coordination branch
  is the topic branch, which already holds the log written before settlement.
- **`CONSOLIDATED_TARGET`** is the target's copy in the repository root checkout (FR-001). The landed
  check runs before any coordination probe, so a coordination branch torn down by consolidation never
  raises `CoordinationBranchDeleted`. `CoordinationBranchDeleted` keeps meaning "deleted without
  landing", which is data loss and fails closed.

**The "landed" signal is not defined here.** The door asks the placement seam whether the Mission has
landed; it uses the same signal that switches a default Mission's PRIMARY partition from the topic
branch to `target_branch` (see "PRIMARY placement" below). That signal is defined by
[ADR 2026-11-06-3](2026-11-06-3-topology-is-settled-once-at-first-finalize.md) and owned by the
placement seam (Mission WP14), which fixes the record consolidate writes for it. The nearest existing
signal is the lifecycle phase that `mission_runtime.lifecycle_phase.resolve_lifecycle_phase` derives
from `baseline_merge_commit`, which already routes a published Mission's status reads to the PRIMARY
Mission directory. This ADR adds no second signal.

### Root normalization

Every input root is normalized first (FR-002). A lane root re-anchors to the main repository root
through the #6884 worktree registry classifier; a repository root input is returned unchanged.
**A worktree registry that cannot be read fails closed with a typed error**, for every caller,
repository root callers included: without the registry the door cannot tell a lane root from the
repository root, and Rule 1 forbids reading a lane copy by mistake. This deliberately tightens #6884,
which keeps the caller's root when the registry is unreadable (its
`test_an_unreadable_worktree_registry_keeps_the_callers_root` is flipped on purpose in Mission WP04).
WP04 names the error, reusing an existing typed resolver error when one fits.

### Ref reader

The ref reader returns `RefRead.ABSENT` or `RefRead.PRESENT(bytes)` (FR-004, research R-2):

- an absent file on a readable ref is `ABSENT`, which callers read as an empty history (the door
  first applies the pre-seed rule above);
- a missing or unreadable ref, a missing object or any git failure raises
  `StatusSurfaceRefUnreadable` (`STATUS_SURFACE_REF_UNREADABLE`), and the command exits non-zero;
- where the coordination probe already classifies the branch as deleted, `CoordinationBranchDeleted`
  is raised as today.

A read served from a ref spawns at most one batched object-read subprocess per Mission per command
(NFR-001).

### Invariants

1. The door never returns a path inside a registered lane checkout (ruling 8, FR-043).
2. The door never returns a path that does not exist; exactly one of `path` and `ref` drives a read.
3. Every fallback is declared and stamped; there is no silent fallback.
4. No status read runs outside the door (FR-005); an architectural gate with an empty allowlist
   enforces it (FR-006).

### Reverses

This ADR reverses two requirements of Mission `coord-artifact-single-home-01M3V4BE`, cited by
reference:

- `coord-artifact-single-home-01M3V4BE#C-002` ("Keep the read-side fallback": an empty coordination
  surface reads the repository root checkout, with a warning);
- `coord-artifact-single-home-01M3V4BE#FR-017`, in the part that documents "the retained read-side
  fallback" in ADR 2026-06-19-1.

New behaviour: an empty or unmaterialized coordination worktree reads the committed coordination
branch, never the repository root checkout's copy. The 2026-06-21 loud fallback of ADR 2026-06-19-1 is
superseded for status reads; that ADR carries an amendment pointing here. For the status kind
(`STATUS_STATE`) the door also replaces the raise of ADR 2026-09-24-2 on an unmaterialized
coordination worktree; other COORD-partition kinds keep that ADR's rule until the S9 records (C-3)
decide them. The write side of ADR 2026-06-19-1 (single home, `write_dir`) is unchanged.

### PRIMARY placement for default Missions

This is a placement contract change (FR-061, DM `01M6R0QJVPVZG2QT8MWQD4NXJR`), carried by the read
door (Mission WP05) and the placement seam (Mission WP14) as one change.

- **PRIMARY partition kinds** are the members of `_PRIMARY_ARTIFACT_KINDS`
  (`src/mission_runtime/artifacts.py`): spec, plan, research, data model, contracts, tasks, WP files,
  `lanes.json`, `meta.json`, and the other members that frozenset lists. The frozenset is the
  authority, not this list.
- **`topology_source: default`.** Reads and writes of PRIMARY kinds resolve to `meta.mission_branch`,
  the Mission topic branch (after a multi-lane settlement also the coordination branch), before and
  after settlement, until `consolidate` lands it on `target_branch`. Once the "landed" signal is
  recorded, the placement seam resolves the PRIMARY partition to `target_branch`. `target_branch`
  stays the landing branch throughout.
- **Explicit `--topology` (and `--owned-checkout`) Missions** keep PRIMARY on `target_branch`, as today.
- **Consequence.** After settlement the repository root checkout no longer shows the planning files
  (it returns to its create-time branch). Readers find them through the read door or the placement
  seam, never through a path in the repository root checkout. `spec-kitty agent context resolve
  --json` (`mission_dir`) and `check-prerequisites --paths-only` report the PRIMARY-partition
  location; WP05 and WP14 confirm both with tests.

### Consequences

#### Positive

- Every status-reading command reports the same WP states, from any working directory and in every
  coordination state (SC-001).
- Short-lived checkouts and a worktree-free coordination write stop breaking readers.
- A broken ref is a typed error, never an empty history.

#### Negative

- An unreadable worktree registry now stops every status read, where #6884 kept going.
- A ref read costs one git subprocess per Mission per command.
- After settlement, tools or people that open `kitty-specs/<dir>/` in the repository root checkout
  of a default Mission find nothing there until consolidation lands it.

#### Neutral

- `CoordinationBranchDeleted` and the write seam are unchanged.
- The pre-seed fallback stays, but is declared and visible.

### Confirmation

- `tests/status/test_read_surface_door.py` (Mission WP05): the topology by coordination state matrix,
  one source per cell, the pre-seed fallback stamp, the ref reader's ABSENT versus unreadable split,
  the subprocess count (NFR-001), and the FR-061 placement with its explicit-topology control.
- `tests/status/test_status_readers_cross_cwd_parity.py` (Mission WP06): every reader agrees from the
  repository root checkout, a lane checkout and the coordination path, with the coordination worktree
  present, empty and absent.
- `tests/architectural/test_status_read_single_door.py` (Mission WP07): the empty-allowlist call-site
  gate with planted violations (FR-006).
- `tests/lanes/test_lane_checkout_helper.py` (Mission WP09): every lane-checkout route excludes the
  status files (the checkout half of ruling 3).
- WP04's flipped `test_registry_unreadable_fails_closed` and its repository-root-caller control.

## Pros and Cons of the Options

### B. Keep the loud repository-root fallback

**Pros:** no change for readers today; liveness without a worktree.

**Cons:** it reads a stale copy as truth, which is the root cause of #6466 and #7198. A warning does
not make the answer right.

### C. Materialize the coordination worktree on read

**Pros:** every read sees a file.

**Cons:** a read writes; it fights ruling 5 and the S9 write service, which remove the worktree.

### D. Raise on an unmaterialized coordination worktree

**Pros:** never stale.

**Cons:** with short-lived checkouts every reader breaks in the normal state.

## Open points

- **Target not checked out.** `CONSOLIDATED_TARGET` reads the target's copy in the repository root
  checkout, as FR-001 says. When the repository root checkout is on another branch that lacks the
  Mission, the door must not return a missing path (invariant 2). Recommendation: read the target ref
  through the same ref reader. WP05 decides with a test.

## More Information

- [ADR 2026-06-19-1](../3.x/2026-06-19-1-coord-empty-surface-fallback.md): superseded for status
  reads (amendment of 2026-11-06).
- [ADR 2026-07-29-1](../3.x/2026-07-29-1-lane-base-recorded-planning-commit.md): amendment of
  2026-11-06, lane checkouts carry no live status; Assert A' kept.
- [ADR 2026-09-24-2](../3.x/2026-09-24-2-coord-read-fail-closed.md): its unmaterialized raise no
  longer applies to status reads.
- [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md): the Mission
  Status Read API reads through this contract.
- [ADR 2026-11-06-3](2026-11-06-3-topology-is-settled-once-at-first-finalize.md) (forward reference):
  topology settlement and the "landed" signal.
- [ADR 2026-11-06-4](2026-11-06-4-coordination-branch-written-by-commit.md) (C-1, forward reference)
  and [ADR 2026-11-06-6](2026-11-06-6-committed-ledger-is-the-coordination-blob.md) (C-3, forward
  reference): the worktree-free coordination write; C-3 ties the oracle fallback to this contract (a
  missing ref is a typed error, not a read of the repository root checkout).
- PR #6884 and its contract `status-read-root.md`.

## Amendment 2026-11-08 (Proposed): the call-site gate lands with a priced allowlist, and "landed" has one signal

**Deciders:** Stijn Dejongh (operator). Accepted by merging the pull request that carries it.
**Technical Story:** [#7408](https://github.com/spec-kitty/spec-kitty/issues/7408) (S5 of epic
[#3893](https://github.com/spec-kitty/spec-kitty/issues/3893)),
[#7310](https://github.com/spec-kitty/spec-kitty/issues/7310) (the deferred FR-005/FR-006 of Mission
`lane-worktree-model-hardening-01M6QY1M`), [#7335](https://github.com/spec-kitty/spec-kitty/issues/7335).
The body above is kept as written.

### The gate (invariant 4, FR-006)

`tests/architectural/test_status_read_single_door.py` scans `src/` (AST) for the legacy ways of
finding a status source: `resolve_status_surface` and `resolve_status_surface_with_anchor` (a
`for_write=True` call is the write seam and is not scanned), `read_event_log` and
`read_event_stream_log`, `resolve_surface_dir_or_typed_error`, and every `STATUS_STATE` read off the
placement seam (`read_dir`, `resolve_partition_read_dir`, `resolve_artifact_surface`, and
`ctx.artifact(STATUS_STATE)` unless only its `write_dir` or `commit_target` is used). A call
through an import alias is matched by the name it imports. Planted violations keep it non-vacuous.

Invariant 4 asks for an empty allowlist. The gate lands with a **transient, shrink-only allowlist**
instead, because about 45 readers remain and draining them all exceeds one reviewable change. Per
charter Standing Order #5 and ADR [2026-09-30-1](2026-09-30-1-allowlist-ratchets-are-priced-debt.md)
the allowlist is priced debt: issue #7310 owns it, the follow-up Mission of #7310 drains it, and the
drain date is the gate's `ALLOWLIST_DRAIN_BY` (2026-12-31, operator-confirmed; moving it is recorded on #7310).
A new bypass fails, and an entry that no longer matches a reader fails too, so a migrated reader
leaves the allowlist in the same change. The allowlist size is registered in
`tests/architectural/_baselines.yaml` (`test_status_read_single_door.legacy_read_allowlist`), so
adding an entry also fails `test_ratchet_baselines.py` unless the baseline grows with a
justification. An entry is keyed by enclosing function and form, not by call: a second legacy read
of the same form inside an already-listed function is not caught. Invariant 4 is reached when the
allowlist is empty.

A second check pins the modules already moved onto the door (`DOOR_ONLY_MODULES`, grow-only): they may
not call a legacy source finder or a path-typed log reader (`read_events`, `read_event_stream`,
`wp_snapshot_state`, `reconstruct_wp_view`, `has_event_log`, `get_wp_lane`, `get_all_wp_lanes`,
`event_sourced_review_result`, `get_arbiter_overrides_for_wp`).

**Not scanned (named limits).** A path-typed log read handed a directory that did not come from a
legacy finder (the census counted `get_wp_lane` 52, `has_event_log` 26, `WorkPackage.status_dir` 20
and `reconstruct_wp_view` 15 call sites), and `resolve_handle_to_read_path`, which also serves
non-status reads. Modules leave that blind spot by joining `DOOR_ONLY_MODULES`.

**Known blind spots of the call-site scan.** Each is a way a legacy read passes the gate unseen:

- the allowlist is keyed `path::function::form`, so a second legacy call of the same form inside a
  function already listed passes;
- `MissionArtifactKind.STATUS_STATE` bound to a variable first and read through that alias;
- a rebound `read_event_log` (`r = read_event_log; r(d)`);
- `getattr(x, "read_event_log")`;
- a direct read of a `status.events.jsonl` path;
- `for_write=True` is a syntactic exemption: a call passing it is skipped whatever it reads.

### Census at landing (45 entries)

| Reason | Entries | What has to happen |
|---|---|---|
| Path-typed consumer (`get_wp_lane` / `read_events` / `has_event_log` on a dir) | 13 | read a surface instead |
| Runtime decision path (`ctx.artifact(STATUS_STATE)` in `runtime/next`) | 6 | move with the runtime bridge readers |
| Existence or fail-closed probe relying on `CoordinationWorktreeUnmaterialized` | 6 | a door-level probe |
| Write-side transaction reading its own target (`status_transition`) | 4 | the writer cut-over (#6195, #6608) |
| Handed-dir partition authority (#5180) | 3 | surface-typed verdict and feedback reads |
| Legacy Path projection (`resolve_status_surface`, `resolve_surface_dir_or_typed_error`) | 2 | deleted with their callers |
| Finalize planning pin (#5702 decides its fail-open polarity first) | 2 | #5702 |
| `WorkPackage.status_dir` / `locate_work_package` | 2 | a surface-typed WorkPackage read |
| Placement seam `STATUS_STATE` arm, aggregate create-window gate, `tasks_are_finalized` drift check, lane-destroyed guard, committed-ref strand authority, owned identity check, review override written through a read path | 1 each (7) | per entry |

### One landed signal

`runtime.next.committed_authority` decided "merged" from `meta.mission_number`, which a reopen keeps,
while this door decides `CONSOLIDATED_TARGET` from `mission_runtime.mission_has_landed` (the
reopen-aware `merged_at` marker). Both now ask `mission_has_landed`; `mission_number` is display-only
and is no landed signal. `committed_status_dir`, the status board's own committed-source probe, is
removed: the board reads the door, which already answers `CONSOLIDATED_TARGET` for a landed Mission.
A Mission merged before `merged_at` was written again (#4090) has no `merged_at` (264 of the 819
Missions in this repository's `kitty-specs/` carry `mission_number` without it, which counts some
that never landed, see below). The door already treated such a Mission as not landed, and now `next` does too; a coordination-topology one,
whose coordination branch consolidation removed, refuses with `COORDINATION_BRANCH_DELETED` in both.
Reintroducing `mission_number` as a second landed signal was rejected (operator ruling 2026-11-08):
`doctor mission-state --fix` assigns it to Missions that never landed (#5471), so it is no evidence
of a landing either.

Instead the upgrade migration `4.0.0rc8_backfill_merged_at` (#7433) stamps `merged_at` once, from
the committed status log only (operator rulings 2026-11-08). The rule lives in one place,
`specify_cli.status.landing_evidence`:

- **Evidence.** Every work package in the Mission's status log is terminal (`done` or `canceled`),
  at least one is `done`, and the log records no `MissionReopened` event. The log is read through
  this door: `resolve_landing_evidence_read` takes the door's own decision (the coordination
  branch or worktree while it exists, the write checkout for a coordination-less Mission), with
  one declared exception: when the door refuses with `CoordinationBranchDeleted`, the evidence is
  the target's copy (`resolve_consolidated_target_read`), the only committed log left once
  consolidation removed the coordination branch.
- **Date.** The `at` of the latest transition to `done` in that log, normalized to aware UTC
  (a naive stamp is read as UTC). No git history is read: neither `baseline_merge_commit` (the
  target tip before the landing, a lower bound) nor the commit that set `mission_number` (often a
  bulk `meta.json` rewrite) dates a landing.
  A `done` written by a migration actor (`migration:*`, e.g. the #5579 `backfill_wp_status` seed,
  which restates history near the Mission's creation) supplies the date only when the log has no
  other `done` event (operator ruling 2026-11-08); otherwise the latest non-migration `done` wins.
  When the coordination branch is gone, the target's copy (the file `CONSOLIDATED_TARGET` reads) is
  the evidence; the operator signed off this exception on 2026-11-08.
- **Skipped and reported.** A Mission without that evidence (unfinished work packages, all
  canceled, reopened, no log, an unreadable log) is never stamped; the migration names it in a
  warning, one per reason. So is a Mission with a consolidation in progress (its
  `.kittify/runtime/merge/<mission_id>/state.json` exists), whatever its log shows: consolidation
  bakes `done` before it stamps `merged_at`, so an interrupted run meets the evidence, and stamping
  it would point `consolidate --resume` at the target's copy, which has no log yet.

It writes `merged_at` only, through the canonical meta writer, records in the tracked ledger
partition (`meta.json` travels with the commit), declares `requires_git_repository` (the door reads
the worktree registry and coordination refs), and is idempotent. A dry run on this repository's
`kitty-specs/` (533 Missions without `merged_at`) would stamp 341 and skip 192: 172 with unfinished
work packages, 15 whose log records no work package and 5 with no log.

The `COORDINATION_BRANCH_DELETED` remedy asks the same predicate of the target's copy: when it
holds, the remedy is `spec-kitty upgrade` (and names the latest done date), not flattening the
Mission; otherwise the flatten remedy stands. `mission_number` plays no part in that choice, and
the check only picks the remedy text; the landed verdict stays `mission_has_landed` alone.

**Residual.** A Mission whose work packages are all `done` but which was never consolidated (a
manual `move-task --to done`) also satisfies the evidence and is stamped. `done` is ordinarily
written by consolidation itself, and the operator accepted this residual with the ruling.

**Residual.** The backfill settles even when a Mission's status log is unreadable; once that log is
repaired, `spec-kitty upgrade` no longer re-selects it and the `COORDINATION_BRANCH_DELETED` remedy
is inert until a re-run path exists (#7449).

### Moved onto the door in this change

`agent tasks status` (one surface read; every row field from it; a log that cannot be read fails the
command closed instead of rendering an empty board), the canceled-set read of
`git/origin_freshness`, the lane-tip terminal hook of `lanes/claim_base` and the review dependents
warning of `workflow_executor`. `tests/status/test_status_readers_cross_cwd_parity.py` carries
`agent tasks status` in its matrix.

## Amendment 2026-11-11: owned coordination checkouts, read vs dispatch

**Deciders:** Stijn Dejongh (operator). Accepted by merging the pull request that carries it.
**Technical Story:** Mission `runtime-status-read-door-01M73HHB` (FR-007, FR-012), Decision Moment
`01M73HKG7WSR4VDRFXG9JWTGM8` (DM-1). The body and the 2026-11-08 amendment above are kept as written.

**Finding the Mission.** For an owned checkout of a `coord` or `lanes_with_coord` Mission, the door
locates the Mission through the owned checkout, not the repository root checkout. The owned
checkout's Mission directory gives `meta.json`, the landed check and the pre-seed fallback. The
coordination state (materialized, empty, unmaterialized, deleted) is still probed under the
repository root, because the coordination worktree and branch are registered there. A Mission that
exists only in the owned checkout therefore resolves. Owned `single_branch` and `lanes` Missions are
unchanged: they read the owned checkout's Mission directory.

**Reading.** Query and progress of an owned coordination Mission read the committed coordination
branch when its worktree is empty or unmaterialized, as §2 already says for every coordination
Mission.

**Dispatching.** An advancing dispatch of that Mission (one that would send an agent to work in the
coordination workspace) refuses with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` when that workspace
is empty. An unmaterialized workspace is not refused: the bootstrap's decision-log write
materializes the coordination worktree before the dispatch is decided, the dispatch proceeds, and
the decision reports the materialization in `Decision.remediation`. This keeps the operator's
ruling in DM-1: an agent must not be sent into a missing workspace, and a workspace the bootstrap
has just materialized is not missing. It is a dispatch rule, not a read rule; the door itself never
refuses for it.
