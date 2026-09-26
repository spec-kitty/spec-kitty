---
title: Analysis report transactions
description: Record an analysis report while preserving unrelated work and checking the report commit against its material governance inputs.
doc_status: draft
updated: 2026-09-24
---

# Analysis report transactions

`spec-kitty agent mission record-analysis --mission <handle> --input-file <report> --report-only --json`
opts into a report-only transaction. The ordinary command retains its broad
dirty-worktree refusal. The report still belongs to the authoritative primary
planning checkout; invoking from a clean linked lane does not change that owner.

The opt-in transaction requires the checked-out, unprotected planning branch,
clean material inputs and report, supported index entries, and no active Git
operation. It preserves unrelated staged blobs, partial staging, working bytes,
and untracked bytes. The canonical commit router uses `git commit --only`;
the transaction never stashes or resets operator work.

## Material inputs

The shared recording/freshness manifest covers spec, plan, status-normalized
tasks, individual WP definitions, mission metadata and package manifest,
configured charter authority, local declarative mission/template/doctrine
overrides, charter references and authority directories, and bundled authority
content digests. Missing paths are recorded so their later creation invalidates
analysis. WP lane/review fields use the canonical mutable-field vocabulary and
are excluded from definition hashes. Runtime events, context-state and synthesis
bookkeeping are excluded. Symlinks and external mutable org roots are refused.

## Outcomes and recovery

The JSON response distinguishes `failed_before_write`, `written_uncommitted`,
`committed_unqualified`, `committed`, and `unchanged`. Identical semantic report
content, analyzer and current inputs reuse an already-qualified report without
changing its bytes or HEAD. Missing or pending receipts cannot qualify that
no-op; fresh analysis must produce and verify a new report commit instead.
A disk write alone is never success.
Pre/post checks compare HEAD, material inputs, unrelated index entries, dirty
working bytes, report bytes, commit parent and changed paths. These checks detect
cooperative-writer races; they cannot lock out arbitrary external editors. The
net is deliberately broad: because the guard snapshots the entire index and the
full working tree (including untracked files) minus the report path, *any*
unrelated change observed during the transaction window — not only a HEAD or
index race — flips the outcome to `committed_unqualified`. No unrelated work is
lost in that case; the report is simply left freshness-rejected and a rerun
re-qualifies it.

Before writing, the transaction creates a pending receipt in the local Git
directory. Only successful verification qualifies that receipt. Freshness for
an opt-in report requires its receipt, exact report digest and a reachable
verified commit. Thus a process crash or an unrelated concurrent change cannot
unlock the mission merely because the retained report exists.

Receipts are local qualification evidence, not portable attestations. Copying
the report into another clone does not qualify it there. Preserve concurrent
work, inspect retained commits, reconcile and commit material inputs, then rerun
analysis and recording in the destination checkout. No recovery action resets
concurrent work automatically. A failed written report must be reviewed and
committed or removed by its owner before retrying; the dirty-report guard remains.
