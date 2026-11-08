---
title: 'ADR: the committed ledger of a coordination Mission is the blob on its coordination branch'
description: 'Proposed: for coordination Missions the publication seam and the read API pull read the event log blob at the coordination ref; events tail cursors name their commit.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-06'
updated: '2026-11-06T00:00:00Z'
---

# The committed ledger of a coordination Mission is the blob on its coordination branch

**Status:** Proposed (2026-11-06). The operator accepts it by merging the pull request that carries it, together with the other records of the set.

**Date:** 2026-11-06

**Deciders:** Stijn Dejongh (operator). Ruling 4 of epic #7276 is DM `01M6QY371KRY5XXQMDQ4WZR1YE` in Mission `lane-worktree-model-hardening-01M6QY1M`.

**Technical Story:**

- [#7284](https://github.com/spec-kitty/spec-kitty/issues/7284) (S9), epic [#7276](https://github.com/spec-kitty/spec-kitty/issues/7276). ADRs only; the implementation follows migration step 4 ([#6117](https://github.com/spec-kitty/spec-kitty/issues/6117)).
- **Discharges** the D-6 bullet of [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md) on the publication seam (mapping in that record's Amendment 2026-11-06).
- **Amends** [ADR 2026-10-13-2](2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md) D-2 (the ledger is the publication seam) for coordination Missions, and [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) D-3 and D-6 (the read API composes existing read models; it is a pull over the committed ledger).
- **Related records of the same set:** **C-1** [ADR 2026-11-06-4](2026-11-06-4-coordination-branch-written-by-commit.md), **C-2** [ADR 2026-11-06-5](2026-11-06-5-gates-over-worktree-less-coordination.md), **events ADR-0007** `docs/adr/0007-write-service-commits-coordination-status-by-ref.md` and **events ADR-0008** `docs/adr/0008-read-service-reads-coordination-ledger-from-git-objects.md` in [`spec-kitty/spec-kitty-events`](https://github.com/spec-kitty/spec-kitty-events), branch `main` (merged from `issue-7284-coordination-ref-write-adrs`), PR [spec-kitty/spec-kitty-events#215](https://github.com/spec-kitty/spec-kitty-events/pull/215). ADR-0008 decides how the Java read service reads the blob; this record decides what the committed ledger is and what the CLI's cursor names.
- **Read contract:** [ADR 2026-11-06-2](2026-11-06-2-one-status-read-contract.md) (one status read contract, S1).

**Reader:** a maintainer of `spec-kitty events tail`, the Mission Status Read API, or a subscriber such as `spec-kitty/event-router`.

---

## Context and Problem Statement

ADR 2026-10-13-2 D-2 makes the ledger the publication seam: a subscriber learns about events by reading the committed `status.events.jsonl`, through `spec-kitty events tail` (`status/tail_reader.py::TailCursor`) or the Mission Status Read API (ADR 2026-10-01-2), never by being called. Both read a file at a path.

From C-1's step 4a, a coordination Mission has no coordination worktree: the committed tree of `refs/heads/<coord>` is the only copy of its ledger. A reader that reads a path would read nothing or a stale husk. Two further facts follow:

- `TailCursor(offset, content_invariant)` is a byte offset into one file. A cursor taken on the coordination branch's blob does not carry over to the target's blob after consolidation, because the union at projection may reorder or deduplicate lines (ADR 2026-02-09-3), and its `ResumeRefused` reasons (`negative`, `out_of_range`, `misaligned`, `content_mismatch`) cannot say why.
- Today's read oracle answers an unmaterialized coordination Mission by falling back to the primary directory (`probe_coord_state` returns `UNMATERIALIZED`; `src/specify_cli/missions/_read_path_resolver.py`). Events ADR-0008 D-1 makes the Java read service follow whatever the oracle answers; the two must agree when the ref is missing.

## Decision Drivers

- One committed ledger for every consumer: the writer's commit (ruling 8).
- The read API's guarantees (ADR 2026-10-01-2 D-6): read-only, no lock, independent of drain.
- Python and Java answer the same Mission the same way (ADR 2026-10-29-1 D-6, D-7).
- A cursor never silently skips or repeats events.

## Considered Options

For the cursor (D-4), the open choice of this record:

1. **The cursor names the commit it was taken at** (recommended).
2. **The cursor names the blob it was taken in.**
3. **No change**: the offset and content invariant only.

## Decision Outcome

Each decision is marked *(derived)* or *(open)*; open choices carry a recommendation (Mission assumption A-12).

### D-1: the publication seam of a coordination Mission is the blob at its ref *(derived; amends ADR 2026-10-13-2 D-2)*

For a coordination topology (`coord`, `lanes_with_coord`), the committed ledger is the `status.events.jsonl` blob at `refs/heads/<coord>`, at `kitty-specs/<mission-dir>/status.events.jsonl`. After consolidation it is the target's committed copy. "Committed" means reachable from that ref, never a working-tree file. For `single_branch` and `lanes` Missions, D-2 of ADR 2026-10-13-2 is unchanged. No new read path, toggle or daemon is added; publication stays on by default.

### D-2: the read API's pull reads git objects for coordination Missions *(derived; amends ADR 2026-10-01-2 D-3, D-6)*

- The read API's pull, for a coordination Mission, reads the blob of D-1. It stays read-only, takes no lock and is independent of drain (D-6 unchanged in meaning).
- **Python side:** every read goes through the one read door of ADR 2026-11-06-2, whose `COORD_BRANCH_REF` source reads the ref with `git cat-file --batch` (one batched subprocess per Mission per command). The door replaces D-3's "`_read_path_resolver` and `MissionStatus.load` path" as the coordination-aware read surface; the read models D-3 composes (`materialize_snapshot`, `reconstruct_wp_view`, `TailCursor`) take their bytes from it.
- **Java side:** events ADR-0008 (an in-process git-object adapter of `MissionEventSource`; `ReadDirResolver`'s coordination case reads the ref).
- One read pins one tip: every coordination-branch file of one answer comes from the same commit.

### D-3: a missing ref is a typed error, in both languages *(derived; oracle fallback parity)*

The oracle's fallback changes so that Java and Python agree on a missing ref (events ADR-0008 D-1). It follows ADR 2026-11-06-2's read contract:

- **Unmaterialized** (the branch exists, no worktree; from step 4a, every coordination Mission): read the ref, never the primary directory.
- **Missing ref:** `CoordinationBranchDeleted` when the probe classifies the declared branch as deleted; `StatusSurfaceRefUnreadable` (`STATUS_SURFACE_REF_UNREADABLE`) for an unreadable ref, a missing object or a git failure. Never a primary-directory read.
- **Readable ref, absent path:** `ABSENT`, an empty history.
- **The pre-seed fallback** of ADR 2026-11-06-2 (branch exists, no log yet, the write checkout read with `fallback_reason` stamped) is open:
  - **(a) keep it in both languages** (the Java service already reads `meta.json` from the primary directory, so it could read the write checkout's log too);
  - **(b) retire it at step 4a**: C-1 D-9 seeds the coordination branch from the write checkout during the drain, and from step 4a the service's first coordination write creates the path (events ADR-0007 D-1, `update-index --add`), so a readable ref without the path truly means "no events".
  - **Recommendation: (b).** It leaves Java with one rule and no working-tree read; until step 4a the Python door keeps the declared fallback and `ReadDirResolver` is unchanged (events ADR-0008 D-1, "until migration step 4").
- **Conformance:** the corpus compares only shapes both sides read the same way. The unmaterialized-coordination cell joins the comparison when ADR-0008's adapter ships, with the no-worktree fixture of ADR-0008 D-3.

### D-4: the `events tail` cursor names its source *(open; recommendation: option 1)*

**Option 1, the commit (recommended):** `TailCursor(offset, content_invariant, source_ref, commit)`.

- `source_ref` is the ref the blob was read from (`refs/heads/<coord>`, or the target after consolidation); `commit` is the commit it was read at.
- **Resume on the same ref:** when `commit` is an ancestor of the ref's current tip and the blob at `commit` is a byte prefix of the current blob (the existing content invariant), resume by offset. A coordination log only grows by append (events ADR-0007 D-2), so this is the normal case.
- **Resume after the source moved** (the coordination branch was consolidated onto the target and deleted, or the prefix no longer holds): refuse with a new `ResumeRefused` reason, **`source_moved`**, naming the new source and the last event id the cursor had passed. The consumer resumes from that event id. The CLI does not remap offsets by event id itself.
- Polling is a cheap `git rev-parse` of `source_ref`.
- A cursor with no source (taken before this change, or on a `single_branch` or `lanes` Mission) keeps today's meaning: an offset into the write checkout's file.

**Option 2, the blob id:** `TailCursor(offset, content_invariant, blob)`. Considered: it detects that the bytes changed, which the content invariant already does, but cannot tell an append from a consolidation, and gives no ancestry to reason with.

**Option 3, no change.** Rejected: after consolidation a coordination cursor is refused with `content_mismatch` or, worse, lands on a misaligned but valid line boundary of the reordered target log.

**Remap by event id inside the CLI** (on `source_moved`) was considered and left out: it makes the CLI own a second ordering of the same events; the consumer already holds the event ids.

The cursor change is consumer-visible (`spec-kitty/event-router`). If it is taken, the `mission-status` contract's stream cursor changes before that contract's `1.0.0` (events ADR-0008 D-4), and `events tail` documents the new reason.

### D-5: retention is unchanged *(derived)*

ADR 2026-10-13-2 D-3 stands: the coordination branch's history is git's to keep until consolidation, and the teardown's branch delete is its only removal, under the destructive authority (ruling 7, `git/destructive_guard.py`; ADR 2026-11-06-1 on PR #7275).

### D-6: JGit or a subprocess *(open; not ruled here)*

How each side reads git objects stays open in core (A-12). The options are an in-process reader (pinned JGit, or a minimal reader of loose objects, packs and refs), or a `git` subprocess (`cat-file --batch`). **Recommendation:** core rules nothing for Java; it follows events ADR-0007 D-5 (a `git` subprocess for writes) and events ADR-0008 D-2 (in process for reads, with a named source fault for an unsupported ref backend). The Python CLI keeps its batched `git cat-file --batch` subprocess (Mission research R-12: no Python git library).

### D-7: what stays open *(open)*

- Whether the read API's overview cursor becomes a commit id (default: it follows D-4 if option 1 is taken).
- Whether `events tail` polls the ref or watches the reflog (default: polls, `rev-parse`).
- The pre-seed fallback (D-3) and the cursor (D-4), as above.

### Consequences

#### Positive

- Every consumer reads exactly what the writer committed; the husk ambiguity of a stale coordination directory disappears.
- Java and Python give the same answer for a missing coordination ref.
- A consumer can tell an append from a consolidation, and is never resumed into a reordered log.

#### Negative

- A new `ResumeRefused` reason and a cursor shape change, visible to consumers.
- The read path of a coordination Mission costs a git subprocess on the Python side.

#### Neutral

- `single_branch` and `lanes` Missions read as today.
- Retention, drain and the produce seam (`status/adapters.py`) are unchanged.

### Confirmation

Named here, **to be written by the step-4 Mission** (the Java side by its own Confirmation in events ADR-0008):

- `tests/status/test_events_tail_coordination_ref.py`: `events tail` on a coordination Mission with no coordination worktree reads the blob at the ref and emits every committed event once.
- `tests/status/test_tail_cursor_source_ref.py`: a cursor resumes by offset after appends on the same ref; after consolidation and branch deletion it refuses with `source_moved`, naming the target and the last event id; a sourceless cursor keeps today's behaviour.
- `tests/status/test_read_door_missing_ref_parity.py`: a deleted coordination branch raises `CoordinationBranchDeleted`, an unreadable ref raises `StatusSurfaceRefUnreadable`, an absent path reads empty, and no case reads the primary directory.
- The no-worktree corpus fixture of events ADR-0008 D-3, compared against the Python oracle.

## Pros and Cons of the Options

### 1. The cursor names the commit (recommended)

- Good: ancestry tells append from consolidation; cheap polling; exact snapshot re-read.
- Bad: a cursor shape change and a new refusal reason.

### 2. The cursor names the blob

- Good: a smaller change.
- Bad: duplicates the content invariant; no way to tell why the bytes changed.

### 3. No change

- Good: nothing to build.
- Bad: wrong or confusing answers after every consolidation of a coordination Mission.

## More Information

- Mission discovery map: `kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/doctrine-and-write-service-adr-map.md` (Part 2, C-3; risk 9).
- Current cursor: `src/specify_cli/status/tail_reader.py` (`TailCursor`, `ResumeRefused`).
