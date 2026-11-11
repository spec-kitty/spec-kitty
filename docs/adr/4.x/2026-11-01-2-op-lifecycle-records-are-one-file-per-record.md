---
title: 'ADR: Op lifecycle records are one file per record'
description: 'spec-kitty next writes each lifecycle record to its own kitty-ops/lifecycle/<ulid>.json; the shared lifecycle.jsonl stays readable, never written.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-11-01'
updated: '2026-11-11T00:00:00Z'
---

# Op lifecycle records are one file per record

**Status:** Accepted (2026-11-01). Operator pre-rulings of 2026-11-01 on #7003.

**Date:** 2026-11-01

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #7003: every Mission PR appended to the shared `kitty-ops/lifecycle.jsonl`, so two PRs in the merge
  queue conflicted at its end and the second was dropped (#6804, #6843 and #6892 had to land one at a
  time on 2026-11-01).
- Extends [ADR 2026-11-01-1](2026-11-01-1-pull-requests-touch-no-shared-generated-files-and-land-through-a-merge-queue.md)
  (pull requests touch no shared generated file) to the Op lifecycle log.
- Keeps the interim locked append of [ADR 2026-10-22-1](2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md)
  (#6606) for every write.

## Context and Problem Statement

`spec-kitty next` records a `started` lifecycle record when it issues an action and a paired
`completed` or `failed` record when the agent reports back (`ProfileInvocationRecord`,
`src/specify_cli/invocation/lifecycle.py`). The `doctor` orphan report and the NFR-006 pairing rate
read them. All of them were appended to one tracked file. Any two branches that each ran `next`
edited the end of that file, and git cannot merge two appends at the same place without a conflict.

The interim `kitty-ops/lifecycle.jsonl merge=union` attribute fixed local merges and rebases. It is not
known that GitHub's merge queue honours a merge driver attribute, and a union merge of two logs is
still a shared-file edit that ADR 2026-11-01-1 rules out.

## Considered Options

- **A. One file per record**, `kitty-ops/lifecycle/<ulid>.json`.
- **B. Fold lifecycle records into the per-Op files** `kitty-ops/<op-ulid>.jsonl`, which already never
  conflict.
- **C. Stop tracking the lifecycle log.**
- **D. One file per (Mission, action) group.**

## Decision

**Option A.** Each record is written to its own `kitty-ops/lifecycle/<ulid>.json`, holding the record's
one sorted-key JSON line and a line feed. No other branch writes that file, so two PRs never conflict
on lifecycle records and no merge driver is needed.

- **Name.** A ULID, not the record's `at` (an ISO timestamp holds colons, which Windows refuses in a
  file name). The ULID is issued monotonically within one process, so two records with the same `at`
  keep their write order.
- **Write.** Through the interim locked door (`kernel.event_log_append.append_event_log_lines`), with
  the record directory as the family lock anchor, so lock files do not grow with the number of
  records. The write refuses a final-component symlink and refuses a name that already holds content
  (`LifecycleRecordExistsError`): a record file is created once and never rewritten.
- **Legacy log.** `kitty-ops/lifecycle.jsonl` stays tracked and readable, and is never written again.
  It is not split into record files: that would be a migration commit touching every lifecycle record
  in every project for no reader's benefit.
- **Read order.** `read_lifecycle_records` returns the legacy log's lines in insertion order first, then
  the record files sorted by (`at` as UTC, ulid). A corrupt or unreadable record file is skipped like a
  corrupt line. Pairing, the orphan report and the pairing rate give the same results on the same
  records, whichever layout holds them.
- **Owned checkouts.** The owned `next` commit lists only the record files the checkout has not
  committed yet (`git status` scoped to the record directory), never every record ever written.
- **Retention.** `doctor event-logs` never scans `kitty-ops/`, and its path guard refuses the record
  directory and the legacy log. Committed lifecycle records are never removed.
- **Merge attribute.** The interim `kitty-ops/lifecycle.jsonl merge=union` line stays in
  `.gitattributes` while open branches still append to the legacy log: `main` no longer writes it,
  but two such branches would otherwise conflict with each other at the end of the file on a rebase
  or local merge. It is removed in a later change once no open branch appends to the legacy log.
  Until then the `docs-lint` guard `scripts/ci/check_legacy_lifecycle_log_untouched.py` refuses a pull request whose net diff modifies the legacy log, so `main`'s copy never changes; the guard and the union attribute are removed together once no open branch appends to it.

### Why not the others

- **B** needs every lifecycle record to carry exactly one Op id when it is issued. It does not:
  `ProfileInvocationRecord` has no Op id, and `next` opens no Op (`docs/context/ops-vs-missions.md`).
- **C** loses the history the `doctor` orphan report and the pairing-rate check read.
- **D** still collides: a `started` record and its completion can land from different branches, and
  both would edit the same group file.

## Consequences

- Two PRs that each ran `next` no longer conflict on lifecycle records, in the merge queue or locally.
- `kitty-ops/lifecycle/` grows by one small file per record. Readers list the directory once per read.
- A branch cut before this change still appends to the legacy log. Without the union attribute, two
  such branches can still conflict there until they are rebased onto a `main` that has this change;
  after the rebase, their next records are files.
- Pairing counts, the orphan count and the pairing rate do not depend on the order. Which `started`
  record of a group the orphan report names can: within the record files it follows `at`, not write
  order, which differs only when the clock steps back between two records of one group; and legacy
  lines always read first, even when an older CLI appended one after record files exist.
- The archive preservation gate keeps admitting a byte-prefix append to the legacy log (an older CLI
  still writes one) and treats every record file like any other `kitty-ops/` file: it may be added,
  never changed.
- `docs/architecture/event-ledger-writers-and-readers.md` still names the legacy path. It is in the
  frozen set of ADR 2026-10-29-1 D-9, so it is corrected in `spec-kitty-events`, not here.

## Amendment 2026-11-10: an abandoned record closes a stale lifecycle record (#7346)

**Reader:** a maintainer who needs to know how a lifecycle record is closed when `spec-kitty next`
never reports a result for it.

**Problem.** The only completion writer was `spec-kitty next` reporting a result, which also advances
the Mission. A work package whose agent stopped mid-action left its `started` record open, and the
record shipped open in the pull request (#7340's WP04).

**Decision** (operator rulings, Mission `close-stale-lifecycle-records-01M72B89`).

- The record contract gains a fourth phase, `abandoned`: the record was closed by
  `doctor ops --close-stale`, not by the action's result. It copies the `started` record's canonical
  id, agent, Mission and work package, names the sweep and its threshold in `reason`, and carries
  `metadata.closed_by = doctor_sweep` and `metadata.closes_started_at`, the `at` of the exact
  `started` record it closes, so a later sweep pairs it with that record and never closes another.
- Pairing counts `abandoned` as a completion (`lifecycle.COMPLETION_PHASES`), so the orphan count,
  the pairing rate and `find_latest_unpaired_started` treat the record as closed.
- One record-level pairing authority, `lifecycle.unpaired_started`, decides which `started` records are
  open, for `spec-kitty next`, `doctor invocation-pairing` and the sweep alike. A completion pairs in
  three rounds: an `abandoned` record pairs the exact record it names; any other completion pairs the
  latest record of its own agent and work package started before it; a completion left over pairs the
  oldest remaining record of its own agent, then the oldest of any agent. The per-group counts are
  unchanged. Before this, `next` and the doctor report named the group's latest `started` records as
  open, so they could disagree with the sweep about which record was open (#7505).
- It has one writer, `lifecycle.write_abandoned_completion`, which writes through the same locked
  `append_lifecycle_record`: one new file, never a rewrite. `spec-kitty next` keeps writing only
  `completed` and `failed`.

**Consequences.**

- The store stays append-only; the preservation gate admits the new files as it admits any other.
- A CLI older than this amendment cannot parse an `abandoned` record, skips it, and keeps reporting
  the orphan. The operator accepted this with the phase choice.
- The sweep commits in every checkout that holds a stale record, lane worktrees included. A
  repository-root `kitty-ops/lifecycle/<ULID>.json` file is `consolidate`'s bookkeeping, as a root
  `kitty-ops/<ULID>.jsonl` Op record is (`reconciliation_kernel._KITTY_OPS_ROOT_RECORD`; operator
  ruling, Decision Moment `01M72P4C1S5Z4MG13Q2W1S1KM0`), so a closure committed on an approved lane
  branch is not a commit after the approval and does not trip `LANE_MOVED_AFTER_APPROVAL`.
- The general dirty-state classifier (`coordination.coherence.is_self_bookkeeping_churn`) counts the
  same exact path, `kitty-ops/lifecycle/<ULID>.json`, as bookkeeping, as it counts a
  `kitty-ops/<ULID>.jsonl` Op record (operator ruling of 2026-11-11 by Stijn Dejongh, follow-up to
  #7506; recorded here, because the Mission that holds Decision Moment `01M72P4C1S5Z4MG13Q2W1S1KM0`
  has landed and its history is frozen). A closure the sweep could not commit is no longer dirt in its
  checkout, so it no longer refuses `accept`, the `record-analysis` preflight or the review
  handoff's dirty check, and a staged one no longer refuses `consolidate`'s dirty-tree probe or its
  post-merge working-tree invariant (both skip untracked files already). The destructive guards
  read the same rule through `ResidueContext.is_disposable` (see Residuals). The pattern is the
  record's one definition (`op_commit_policy.LIFECYCLE_RECORDS`). The claim check of `implement`
  already exempted the whole `kitty-ops/` directory and is unchanged.

**Residuals.**

- A `started` record whose `at` cannot be parsed is dropped when the store is read, so neither the
  sweep nor `doctor invocation-pairing` sees it.
- Matching a completion to its `started` record is a heuristic for records `spec-kitty next` wrote
  (same agent and work package, the latest started before it); two retries completed in different
  checkouts can still be told apart wrongly.
- A `started` record whose `at` is in the future (clock skew) counts as stale, so the sweep closes it
  rather than reporting it as fresh on every run. The same rule applies to Op records.
- The record has no schema version. An older CLI drops a record with an unknown phase without a
  warning, when it reads the store (`lifecycle.read_lifecycle_records`).
- The bookkeeping path rule trusts a lifecycle record by its path, not its content: a commit on an
  approved lane that adds only a hand-written `kitty-ops/lifecycle/<ULID>.json` record is not
  refused by the approval bound. It changes pairing data, never code.
- The dirty-state rule matches a record by its exact path. A gate that lists untracked files
  without `--untracked-files=all` sees a wholly untracked `kitty-ops/lifecycle/` as one
  `kitty-ops/lifecycle/` (or `kitty-ops/`) entry, which the rule does not match, so that gate still
  counts it as dirt. The operator ruled the exemption to the exact path, not the directory. The
  checkout guard of `git/ref_advance.py` lists every untracked file, so it sees each record.
- The destructive guards (`git/destructive_guard.py`, through `ResidueContext.is_disposable`) count
  an uncommitted lifecycle record as disposable in every checkout role, as they count an uncommitted
  Op record. `consolidate`'s lane cleanup, the worktree allocator's remove and `reset --hard`, and the
  coordination worktree teardown no longer keep a checkout for one, so they can discard it. This
  covers every phase, not only an `abandoned` closure: a lost `started` record drops out of pairing,
  and a lost `completed` or `failed` record leaves its `started` record open, which the next sweep
  then closes as `abandoned`, so that action's real outcome is lost. Records are left uncommitted
  where the primary branch tracks none (the #6410 skip) or a protected branch refuses the commit.
  `tests/coordination/test_disposable_residue.py` pins this consequence.
- A closure the sweep could not commit (skipped or refused) leaves the command's exit code unchanged,
  as for an Op record. `spec-kitty next` commits any uncommitted lifecycle record with its own
  commit, so such a closure is committed with the next action that `next` reports in that checkout.
