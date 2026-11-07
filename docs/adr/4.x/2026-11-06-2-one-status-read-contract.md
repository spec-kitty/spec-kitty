---
title: 'ADR: One status read contract'
description: 'Every status read resolves through one door to one declared source per topology and coordination state; never a lane checkout, a missing path or a silent fallback.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
---

# One status read contract

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it.

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

- **`WRITE_CHECKOUT`** is the working tree of the repository root checkout, or the validated owned
  checkout when `owned` is given. It is never a ref: appends there are not committed yet, so a ref
  read would drop rows.
- **`COORD_WORKTREE`** is the coordination worktree's file. The transaction commits in the same unit
  of work; `status_surface_guard` stays the divergence backstop.
- **`COORD_BRANCH_REF`** is `refs/heads/<coord>:kitty-specs/<dir>/status.events.jsonl`, read with
  `git cat-file --batch`. Owned checkouts of a coordination Mission follow the same rule instead of
  raising (FR-003).
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
