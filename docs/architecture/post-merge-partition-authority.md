---
title: Post-Merge Partition Authority
description: One model for post-merge partition authority — the write half (which bytes win per artifact) and the read half (which surface a reader trusts).
doc_status: active
updated: '2026-09-14'
related:
- docs/architecture/artifact-placement-seam.md
- docs/architecture/status-model.md
- docs/context/orchestration.md
- kitty-specs/post-merge-partition-integrity-01M2FQ80/spec.md
- kitty-specs/post-merge-partition-integrity-01M2FQ80/plan.md
---
# Post-Merge Partition Authority

This page is the FR-009 cross-track synthesis for mission
`post-merge-partition-integrity-01M2FQ80`. It maps the two tracks the mission
delivered onto **one** question and records the epic-owner notes and the
shared-vs-disjoint verdict the squad reached.

> **Terminology (per the `primary`/`merge` footgun canon).** "PRIMARY-partition"
> below is the **partition sense** — the stable planning artifacts (`spec.md`,
> `plan.md`, `tasks/WP*.md`, `research/`, `data-model.md`) — never the
> Primary-Branch (`main`) sense. "Surface" is the read-resolution target (coord
> branch vs primary), not a git branch instruction. See
> [`docs/context/orchestration.md`](../context/orchestration.md) `#primary-partition`.

## The one question

After a lane consolidation, **what content is authoritative for each partition artifact,
and on which surface is that content read?** The mission split the question into
two halves that are facets of the same authority model:

| Half | Track | Authority decided | Failure it fixed |
|---|---|---|---|
| **Write** | A (#3942) | Which *bytes* win per artifact when a merge reconciles divergent `kitty-specs/` files | Older mission-branch planning copy silently clobbered a target-newer copy on squash |
| **Read** | B (#4090) | Which *surface* a post-merge reader trusts for WP lane state | A stale diverged coord husk was read as authoritative because the primary-wins guard was dormant |

Both halves are governed by the same partition classifier —
`mission_runtime.kind_for_mission_file` / `is_primary_artifact_kind`
(`src/mission_runtime/artifacts.py`). Planning artifacts are
PRIMARY-partition-authoritative, so lanes must neither **overwrite** them (write
half) nor be read as their post-merge **home** (read half).

## Track A — the write seam (which bytes win)

**Seam:** `src/specify_cli/lanes/merge.py::_merge_branch_into` (the squash step)
plus the pure three-way recency helper
`src/specify_cli/merge/planning_recency.py::target_newer_primary_artifacts`.

The mission→target squash runs `git merge --squash -X theirs <mission_branch>`.
`-X theirs` makes the **source** (mission branch) win every add/add conflict.
That premise is correct for source-authored code and for the six driver-covered
`kitty-specs/**` bookkeeping classes (reconciled by `_MERGE_DRIVERS`), but it is
**false** for the PRIMARY-partition planning artifacts: those are authored on the
primary/target surface, so the target can legitimately carry a *newer* copy than
the mission branch (#3942).

A git merge driver cannot fix this. A driver sees only three blobs (base / ours /
theirs) and has no history access, so it cannot decide *which side is newer* —
recency is a repository-history question. So the fix sits **outside** the byte-
identical `-X theirs` block: after the squash,
`_preserve_target_newer_planning_artifacts` (in `lanes/merge.py`) calls the pure
helper, restores each target-owned path from the pre-advance `target_branch`
blob, and **amends** the squash commit so the preserved content lands in the
single merge commit the ref-advance fast-forwards to. The preservation is
surfaced to the operator, never silent (FR-002).

**The three-way rule (D-A3).** "Newer" is a base/target/lane comparison, never
mtime: the target wins a path iff the target diverged from
`merge-base(target, source)` while the lane copy is base-or-ancestor (the target
evolved, the lane is stale). When both sides advanced the same path, the tiebreak
is the last-commit committer-date, with the target winning on a strictly-later
date **or a tie** (the conservative "do not clobber the target" default). This is
topology-safe by construction: on `single_branch`/`LANES` (lane ≠ base,
target = base) the lane correctly wins with no special case.

**Note for epic #2907 (classifier-driven conflict taxonomy).** D-A1 drives squash
conflict resolution off `mission_runtime.kind_for_mission_file` — the #2709
"target-newer canonical state is *reconciled*, not *replaced*" principle extended
from meta **fields** (the `_TARGET_AUTHORITATIVE_META_FIELDS` driver) to
primary-artifact-kind **files**. This is the #2709 → #3942 lineage. It also
establishes the disposition of the dead module
`src/specify_cli/merge/conflict_resolver.py` (`ConflictType` /
`classify_conflict` / `resolve_owned_conflicts`): it is a **competing** conflict
taxonomy, reachable only through the `merge/__init__.py` re-export (the live
auto-rebase classifier is the different module `merge/conflict_classifier.py`).
The #3942 fix deliberately did **not** wire into it. It should be **retired** as
part of #2907's taxonomy consolidation, so the classifier authority stays single.

## Track B — the read seam (which surface a reader trusts)

**Seam:** the `merged_at` completion marker, written by
`src/specify_cli/merge/baseline.py::record_baseline_merge_commit`, and consumed by
`src/specify_cli/status/lifecycle.py::is_mission_merged`, which the surface
resolver's primary re-anchor (`coordination/surface_resolver.py`
`_primary_mission_is_completed`) and the runtime bootstrap short-circuit
(`runtime_bridge.py`) gate on.

When a mission merges, a diverged coordination husk can survive. The primary-wins
guard is supposed to re-anchor reads to the PRIMARY surface once the mission is
merged — but it gates on `meta["merged_at"]`, whose production writer had been
deleted in #2258 (`6f46cf6bb6`) and never re-added. The guard was **dormant**, so
the divergence resurfaced: retrospect and doctor (which now share
`resolve_status_surface`) could still read the stale husk.

The fix (D-B1) is **one coupled change**:
1. **Restore the writer** for `meta["merged_at"]` (a UTC ISO datetime; plus
   `merged_commit` for provenance) as a **sibling of** the baseline-commit writer
   in `merge/baseline.py` — the meta-write authority — *not* in
   `done_bookkeeping.py` (which writes nothing to `meta.json`; a write there would
   be a boundary leak). The executor is untouched. The driver's
   `_TARGET_AUTHORITATIVE_META_FIELDS` already declares `merged_at` as *the*
   marker, so this is canonical reuse, not a new authority.
2. **Make the guard reopen-aware.** Because nothing today clears `merged_at` on
   reopen and `is_mission_merged` was presence-only, simply restoring the writer
   would make a *reopened* mission read as merged forever across three consumers.
   So `is_mission_merged` is now event-sourced: a mission is merged iff
   `merged_at` is present **AND** no `MissionReopened` event postdates it (reusing
   the adjacent `_last_reopen_at` machinery — no meta-mutating clearer of its own).
   A re-merge re-stamps a fresh `merged_at` that postdates the re-open, restoring
   `True`.

**Note for epic #2160 (single canonical post-merge authority).** D-B1 chose
**"override the stale husk on primary"** over **"freshen the husk"**. This keeps
the single canonical post-merge authority on the PRIMARY surface — the husk is
never re-blessed as a second read home; the guard re-anchors past it by data.
This is a **coord-authority decision** for the #2160 owner to ratify.

**#4091 disposition (D-B2 — separable, verified-already-fixed).** #4090 is fixed
by the marker alone. #4091 is a *distinct* measure mismatch: `event_count` is by
definition the count of unique `WPStatusChanged` transition events, which is
`< len(status.events.jsonl)` (annotations, lifecycle, and decision events are not
transitions). `_project_status_bookkeeping_to_target`
(`merge/bookkeeping_projection.py`) already unions and re-reduces, and its union
branch runs only under a coord husk. WP05 stood up a **red-first repro on a coord
fixture** and confirmed `event_count` is already correct on HEAD; #4091 is
therefore **verify-and-close**, guarded by a characterization test (building a fix
test on already-green code would be the green-regression trap).

## Shared-vs-disjoint verdict

**Verdict: disjoint code seams, one thematic spine.**

The two tracks are **file-disjoint** and were implemented in parallel:

- Track A writes: `lanes/merge.py` + `merge/planning_recency.py`.
- Track B reads: `merge/baseline.py` + `status/lifecycle.py`.

There is **no single unifying code seam** that both fixes route through — the
squad's finding, borne out by implementation. The write half amends a git commit;
the read half event-sources a lifecycle predicate. They share no call path.

What they **do** share is the **partition doctrine and its classifier**. Both are
answers to "what is authoritative post-merge, and on which surface":

- **Write half** — *which bytes win per artifact*: PRIMARY-partition planning
  files are target-authoritative when the target is newer; driver-covered
  bookkeeping keeps its reconcilers.
- **Read half** — *which surface a reader trusts*: once merged, reads re-anchor to
  the PRIMARY surface; the diverged coord husk is overridden, not trusted.

`mission_runtime.kind_for_mission_file` / `is_primary_artifact_kind` is the
**candidate shared spine**: the same classifier that says a path is
PRIMARY-partition-authoritative is what tells Track A not to overwrite it and
Track B not to read a lane as its post-merge home. The spine is **thematic and
doctrinal**, not a shared runtime seam. Calling the tracks "the same bug" would
overclaim; calling them unrelated would miss that a single partition authority
governs both. They are **genuinely disjoint-but-thematically-shared**, unified by
the classifier + partition doctrine rather than by code.

## Traceability

| Requirement | Delivered by | Seam |
|---|---|---|
| FR-001/FR-002 (write authority + divergence report) | Track A / WP01–WP02 (#3942) | `lanes/merge.py`, `merge/planning_recency.py` |
| FR-003 (preserve driver reconciliation) | Track A (unchanged `_MERGE_DRIVERS`) | driver registry / gate artifacts |
| FR-004+ (read authority) | Track B / WP03–WP04 (#4090) | `merge/baseline.py`, `status/lifecycle.py` |
| #4091 verify-and-close | WP05 (D-B2) | `merge/bookkeeping_projection.py` |
| FR-009 (this synthesis) | WP06 | this document |

Epic advances recorded here: **#2907** (classifier-driven taxonomy; retire dead
`conflict_resolver.py`), **#2160** (husk-override authority note to ratify).
