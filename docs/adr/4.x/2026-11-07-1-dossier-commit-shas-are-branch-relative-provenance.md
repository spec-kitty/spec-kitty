---
title: 'ADR: dossier commit SHAs are branch-relative provenance'
description: 'A commit SHA a Mission dossier records names a commit on the branch the work was built on; after a rebase merge it is never repointed, and the archive freeze stays byte-strict.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-07'
---

# Dossier commit SHAs are branch-relative provenance

**Status:** Proposed (2026-11-07). The operator accepts or amends it on the pull request.

**Date:** 2026-11-07

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- #7322: Mission dossiers freeze commit SHAs that a rebase merge invalidates.
- #7313: closing out a Mission after its files reach `main` needs a freeze exception (related; its
  own record gaps are out of scope here).
- #7163: keep accepted issue evidence resolvable after Mission history compaction (related).
- #7203 / PR #7314: the most recent operator-sanctioned freeze exception for stale SHAs, drained the
  same day.
- Operator ruling 2026-11-07: pull requests keep landing by rebase merge.

**Reader:** a maintainer who lands pull requests or reviews a Mission dossier, and an agent doing
either. It assumes you know what a dossier and the archive freeze are.

## Context

A Mission dossier under `kitty-specs/<mission>/` records git commit SHAs as evidence:

- `meta.json`: `merged_commit`, `baseline_merge_commit`, `accept_commit`, `accepted_from_commit`,
  `acceptance_history[]`, and, on the pull-request route, `pr_merge_commit`;
- `lanes.json`: `planning_commit_sha`;
- `status.events.jsonl`: `policy_metadata.lane_head` on every lifecycle transition;
- `tasks/WP*/baseline-tests.json`: `base_commit`;
- `acceptance-matrix.json`: `negative_invariants[].verified_ref`;
- hand-authored evidence: `issue-matrix.json` `evidence_ref`, review evidence, research notes.

Almost all of them are written before the pull request exists: by `consolidate` (local `HEAD`, and
the target tip before consolidation), by `accept`, by the status pipeline (lane tips), by lane
allocation and by the review baseline. Pull requests then land on `main` by rebase merge, which
rewrites every commit, and landing passes rebase or compact the branch before that. The recorded
SHAs therefore name commits that are not in `main`'s history. On 2026-11-07, of the dossiers whose
`meta.json` changed since 2026-10-25, 0 of 143 `accept_commit` values, 2 of 136 `merged_commit`
values and 11 of 136 `baseline_merge_commit` values were ancestors of `main`. Most resolve only
through `refs/pull/<n>/head`, and a commit from an earlier rebase of the same branch not even there.

The archive freeze (`tests/architectural/test_archive_root_byte_identical.py`) byte-freezes every
dossier file once it is on `main`. Landers treated the unreachable SHAs as defects: they repointed
them at "the rebased equivalent" before merge (the values went stale again on merge), and after
merge corrected them only through an operator-sanctioned freeze exception, which was then drained
(#7203 and PR #7314). Some fields had no rebased equivalent and were nulled or approximated.

The real problem is what these values were taken to mean, not the freeze. `status.events.jsonl` is
append-only and its prefix is frozen, so `lane_head` cannot be corrected by any mechanism.
GitHub's rebase merge has no post-merge hook, and CI on `main` cannot push, so a "reconciliation
write" would itself be a follow-up landing pass. Changing what the writers record (a patch-id, the
pull request number) crosses the consolidation and approval-bound gates that read these SHAs before
landing (ADR `2026-10-04-5`, ADR `2026-09-29-1`), where the raw branch SHA is exactly what they need.

## Decision

1. **A commit SHA a dossier records is branch-relative provenance unless it is classified
   `LANDED`.** It names a commit on the branch the Mission was built on, as that branch stood when
   the value was written. After a rebase merge it may resolve only through the pull request's head
   ref, or not at all. That is its defined meaning, not a defect.
2. **Branch-relative values are never repointed.** No landing pass, before or after merge, rewrites
   one to "the rebased equivalent", nulls it, or approximates it. The value as written is correct.
3. **One registry classifies every SHA field of a tool-written dossier file.** It is
   `DOSSIER_SHA_FIELDS` in `tests/architectural/test_dossier_sha_provenance.py`, covering
   `meta.json`, `lanes.json`, `status.json`, `status.events.jsonl`, `tasks/WP*/baseline-tests.json`
   and `acceptance-matrix.json`.
   The gate there fails when one of those files records a full SHA under an unclassified key path, so
   a writer that starts recording a new SHA field classifies it in the same change. Today every entry
   is `BRANCH_RELATIVE` except `pr_merge_commit`, which is `LANDED`. `baseline_merge_commit` is mixed
   provenance (on the pull request route it is the landing commit's first parent, on the target), so it
   stays `BRANCH_RELATIVE`, the class that promises nothing.
4. **`LANDED` is the only class that promises ancestry of the target.** A `LANDED` field is written
   only after landing, by a writer that verifies the commit is on the target branch before it records
   it (`verify_pr_merge_evidence` for `pr_merge_commit`, reached through
   `spec-kitty accept --mode pr --merge-commit` and `spec-kitty migrate backfill-merge-commit`). A
   field moves to `LANDED` only together with such a writer.
5. **SHAs in hand-authored evidence are branch-relative by rule.** This covers `issue-matrix.json`
   `evidence_ref` prose, review evidence, research notes and the hand-added `evidence_provenance`
   block of older `acceptance-matrix.json` files. They are not in the registry, and a lander never
   edits them to repoint a cited commit.
6. **The archive freeze stays byte-strict.** No SHA-field mask, no key-level exemption, and no
   freeze exception for a branch-relative SHA a rebase merge left unreachable: such a value is
   neither corrupt nor stale. `_OPERATOR_SANCTIONED_CORRECTIONS` remains for genuinely corrupt files.
7. **The decision applies to every dossier already on `main`.** The dossiers landed on 2026-11-07
   (#7273, #7101, #7287, #7317, #6883, #7094) and every earlier one are reconciled by this definition:
   their SHAs keep their recorded values, and none is edited. Pull requests still open (#7231, #7234)
   drop any repointing commits rather than land them.

## Consequences

- No landing pass hand-repoints dossier SHAs, and stale-SHA freeze exceptions stop.
- A reader cannot use `merged_commit`, `accept_commit` or `lane_head` to find the landed code on
  `main`. To find it, use `pr_merge_commit` where it was recorded, the pull request's own history,
  or the `(#<n>)` pull request number in the landed commit's subject.
- The post-merge review dead-code scan diffs from `baseline_merge_commit`
  (`review/_dead_code.py`); when that commit is not on `main`, the scan cannot run. Recording
  `pr_merge_commit` after landing is the supported route. It writes a frozen `meta.json`, so it meets
  the same freeze boundary as #7313; deciding that boundary is #7313's scope.
- The gate does not prove that a branch-relative SHA ever existed: that evidence goes when GitHub
  prunes a pull request's refs.
- The gate checks that a key is classified, not that its class is honest: moving a field to `LANDED`
  stays green without an ancestry-checking writer, so review owns that rule (Decision 4). It also
  sees only full 40-hex values (a SHA inside a composite value such as `review:WP06:<sha>` is not
  matched) and runs on `kitty-specs/**` changes, so a new writer field is caught when the first
  dossier carrying it lands, not when the writer changes.
- Abbreviated SHAs are not scanned (short hex runs collide with ordinary values); every tool writer
  records the full id.

## Alternatives considered

- **Repoint patch-equivalent SHAs after merge through a freeze tolerance.** Rejected: it keeps the
  landing passes the issue removes, needs a follow-up pull request per Mission, and cannot reach
  `lane_head` in the append-only event log.
- **One post-merge reconciliation write per Mission.** Rejected for branch-relative fields for the same
  reasons. For a `LANDED` field such as `pr_merge_commit` it remains the right shape; the freeze
  boundary for it is #7313's decision.
- **Exempt SHA-bearing keys from the byte freeze.** Rejected: values behind the exemption could then
  change freely, and it widens an allowlist where the charter prefers an empty one.
- **Record a patch-id or the pull request number instead of the SHA.** Deferred: the pre-landing
  readers need the raw branch SHA, and a read-side mapping from a branch SHA to its landed commit can
  be added later without a write.
