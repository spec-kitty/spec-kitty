---
title: Analysis report transactions
description: Record an analysis report while preserving unrelated work and checking the report commit against its material governance inputs.
doc_status: draft
kind: Reference
updated: '2026-11-05T00:00:00Z'
audience:
- profile: internal/ai-collaboration-agent
  guidance_text: Written for the AI Collaboration Agent reader.
related:
- api/agent-subcommands
- development/reference/issue-matrix-verdicts
---

# Analysis report transactions

Use `--report-only` when you need to record a mission analysis report while
your checkout has other, unrelated uncommitted work. Without it,
`record-analysis` refuses on any dirty worktree. With it, the command commits
only the report and leaves your other changes exactly as they were.

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

In the documented `make sync-packs` layout, a fetched pack tree is an input
whose committed authority is its tracked sibling pin, not an indexed tree.
The [pin-and-fetch ADR](../adr/3.x/2026-08-16-2-open-packs-is-source-of-truth-for-built-in-doctrine.md)
describes this layout. For a registry-declared, in-repository root such as
`packs/internal/`, the transaction exempts ignored, untracked material only when
its sibling `packs/internal.source.yaml` is tracked, clean and not symlinked,
its `subtree` equals that repo-relative resolved root, and the canonical offline
check matches both committed pin digests and refuses in-tree symlinks.
This proves local content equality to the pin, not that its remote commit exists
or contains those bytes. Index/worktree dirt and canonical-charter checks are
never relaxed; a non-ignored, status-visible untracked tree still refuses.

The sibling-root and matching-subtree rules do not generally support registry
aliases, nested `subdir` roots or non-mirroring upstream layouts. These remain
fail-closed; #7194 owns the binding-contract decision. It is not permission to
broaden admission or treat ignored paths as clean. A changed tree, missing or
uncommitted pin, and unrelated ignored material still refuse. Refusals can name
the pin **alongside** pack files; `dirty_paths` can include a pin that fails the
trust check even when its own Git status is clean.

The report hashes the fetched tree's material bytes, not the pin file itself.
A committed pin-only bump with unchanged tree bytes therefore does not by itself
invalidate an already-qualified report, and the report does not identify its
authorizing pin. This is the existing manifest contract, not a new pin-provenance
attestation. Existing HEAD, whole-index, working-byte and material-input rechecks
still detect cooperative changes during the recording transaction.

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
