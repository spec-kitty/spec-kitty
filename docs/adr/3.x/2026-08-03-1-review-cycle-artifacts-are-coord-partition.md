---
title: 'ADR: Review-Cycle Artifacts Are COORD-Partition Per-WP Bookkeeping'
description: 'Review-cycle artifacts get a `REVIEW_CYCLE` kind in the COORD partition — per-work-package lifecycle evidence, not stable planning output — visible to cross-lane reviewers.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-08-03'
---

**Deciders**: operator (stijn-dejongh), overriding a squad CRITICAL that had recorded
the partition as an unresolved contradiction. The adjudication, verbatim: *"Land them
on COORD in case of a coord topology (this is per-wp bookkeeping, and should be
traced in the shared Coord branch, which is aggregated into the primary branch on
consolidation). In other topologies -> primary. Ensure read and write paths are
consistent."*

**Revision note**: a first draft of this ADR was rejected by a two-lens adversarial
check. Its factual errors are recorded in "What the first draft got wrong" below
rather than silently corrected, because two of them would have produced an
unimplementable change.

## Context

Two authority sources answered the same question in contradictory ways, and the
contradiction was load-bearing rather than cosmetic.

The canonical glossary — [`docs/context/orchestration.md#coord-partition`](../../context/orchestration.md#coord-partition),
an authority path named in the project charter — defines the COORD partition as
holding *"a mission's lifecycle/coordination artifacts — status events, notes,
trace, issue-matrix, acceptance-matrix, **review cycles**, `move-task`"*.

The code says otherwise. There is **no `REVIEW_CYCLE` artifact kind**
(`src/mission_runtime/artifacts.py`). Review-cycle artifacts borrow
`MissionArtifactKind.WORK_PACKAGE_TASK`, a member of `_PRIMARY_ARTIFACT_KINDS`, and
`src/specify_cli/post_merge/review_artifact_consistency.py` asserts in its own
docstring that they are *"`WORK_PACKAGE_TASK`, PRIMARY-partition for **every**
topology"*.

The glossary was also **not unanimous with itself**: its PRIMARY entry, describing
the same COORD set, omitted review cycles and acceptance-matrix. That entry is
corrected in the same change as this ADR, so the two now agree.

### Why this became load-bearing

Mission `review-cycle-verdict-seam-rebuild-01KZ2W7W` makes the status **event**
authoritative for *which* verdict is current while the **artifact** holds *what the
reviewer said*. Under coord topology the event commits to the coordination branch
and the artifact — as `WORK_PACKAGE_TASK` — commits to the primary target branch, so
the two halves of one fact live on two branches. Two concerns in that mission's plan
were found specifying **opposite partitions for the same fact**.

## Decision

**Review-cycle artifacts are COORD-partition per-work-package bookkeeping.** They are
lifecycle evidence about a work package's passage through review, not stable planning
output: written repeatedly during execution, per-WP, and belonging on the shared coord
surface where a reviewer working across lanes can see them.

1. Introduce `MissionArtifactKind.REVIEW_CYCLE`. Review-cycle artifacts stop borrowing
   `WORK_PACKAGE_TASK`.
2. Place `REVIEW_CYCLE` in `_PLACEMENT_ARTIFACT_KINDS` (the COORD set).
3. **The seam projection needs no change; the path classifier does.** Verified by
   probe: `resolve_artifact_surface` already returns PRIMARY for a COORD kind under
   `SINGLE_BRANCH` / `LANES`, so the topology rule falls out of set membership at the
   *read* seam. But the **write** side does not follow, and this is a named
   deliverable, not an implementation detail — see "Required machinery" below.
4. **Read and write paths resolve the same kind.** Every producer and consumer
   resolves through one owner function; a caller-supplied directory is not a
   substitute. Nine of twelve current sites hard-code a PRIMARY assumption and must
   be migrated together — a half-migrated seam is worse than either endpoint.
5. **Conflict rule.** When both surfaces hold a record for the same work package, the
   COORD copy is authoritative under a coordination topology. This inverts
   `test_review_artifact_gate_ignores_stray_artifact_on_coord_husk` (harvested from
   PR #2834), which pins the opposite. That test encodes the *pre-ADR* partition and
   is re-pinned citing this ADR, with a both-present case added. The old polarity was
   correct while review cycles were PRIMARY; it is wrong once they are not.

P-1 is preserved: `REVIEW_CYCLE` joins exactly one set, and `WORK_PACKAGE_TASK` — the
WP task file itself — stays PRIMARY.

### Required machinery

The first draft claimed "no new routing machinery". That was false. Three mechanisms
must change, and each is an acceptance item:

- **Path classifier.** `_artifact_kind_for_path` returns
  `_COORD_RESIDUE_DIRS.get(mission_rel_parts[0])` for *anything* nested under
  `tasks/`, and its file leg is a fixed-basename dict. `review-cycle-<N>.md` has no
  fixed basename, so `REVIEW_CYCLE` **cannot be expressed in the classifier today**.
  It needs a nested-pattern leg. The rule must be **filename-anchored**
  (`review-cycle-*.md`), not directory-anchored: `tasks/<wp>/` also holds
  `baseline-tests.json`, which is deliberately PRIMARY, and `tasks/WP*.md` must stay
  `WORK_PACKAGE_TASK`.
- **Commit router.** `_group_files_by_partition` re-classifies by path and **overrides
  the caller's kind** — its docstring: *"The buckets are ABSOLUTE, not relative to the
  caller."* Without the classifier leg, a `kind=REVIEW_CYCLE` write is re-bucketed to
  PRIMARY, the file is absent from the primary ref, the result is
  `no_op_wrong_surface`, and `_commit_review_cycle_artifact` escalates to a hard error
  **and unlinks the artifact**. Every rejection write would fail.
- **E2 eligibility.** `_E2_CONSOLIDATED_ELIGIBLE_KINDS` currently covers review cycles
  via `WORK_PACKAGE_TASK`. An explicit ruling for `REVIEW_CYCLE` is required, or a
  PUBLISHED mission's write falls through to an unconditional coordination probe.

### Migration: exception absorption, not empty-directory fallback

The first draft said a read finding *nothing* at COORD falls back to PRIMARY. That is
not the failure mode. Measured against this repository:

```
missions w/ review cycles: 102        (418 artifacts)
  declare a coordination_branch: 45
    branch STILL EXISTS in git : 0
    branch DELETED from git    : 45
```

`spec-kitty merge` deletes the mission branch; the coordination branch **is** the
mission branch; nothing clears the `meta.json` key. Every merged coord mission is
permanently in the seam's `DELETED` cell, which is **fail-loud by contract** and
pinned by `test_deleted_coord_branch_raises_fail_loud`. The seam raises
`CoordinationBranchDeleted` *before any read happens*, and the merge gate calls it
unguarded.

So the migration rule is: **`REVIEW_CYCLE` reads absorb `CoordinationBranchDeleted`
and `StatusReadPathNotFound` to the PRIMARY directory**, in one owner function — not
per consumer, and not at the seam, which resolves a directory per kind and never
probes artifact existence. The house precedent is the issue-matrix JSON-first/`.md`
failover, which lives in the artifact's owner module.

## Consequences

**Positive.**

- Glossary and code agree, and the agreement is checkable because the kind exists.
- Verdict authority and verdict record land on the same partition under coord
  topology, so the merge gate stops comparing across a branch boundary.
- The "opposite partitions for the same fact" contradiction dissolves.

**Negative, accepted.**

- **45 existing coord missions** carry review cycles behind a deleted coordination
  branch. They are served by exception absorption, permanently, unless a separate
  `meta.json` flatten migration retires the stale key.
- **`tasks/` becomes two-sided.** It is registered in
  `_NON_DIVERGENT_COORD_RESIDUE_DIRS` on the justification that it is *"authored once
  and never independently edited on the target side"*. The flip falsifies that: WP
  files on target, review cycles on the mission branch. During the migration window a
  coord mission with cycles 1–3 on PRIMARY writes cycle 1 to COORD (`next_cycle_number`
  globs one directory) and `-X theirs` overwrites the target's cycle 1 — the #2804
  clobber shape, in a directory the guard has pre-classified as safe. Either a
  reconcile driver or a documented re-justification is required.
- **The create window splits one WP's artifacts.** The coord worktree materialises
  lazily at the commit boundary, so a coord mission's *first* review cycle is written
  to PRIMARY and later ones to COORD, with `next_cycle_number` counting only one
  surface.
- One more kind, plus rows in `PARTITION_RATIONALE`
  (`tests/architectural/test_write_surface_placement_guard.py`), which is pinned
  exhaustive and will go red on the enum addition alone.

**Neutral.**

- No change to `WORK_PACKAGE_TASK`'s placement, or for `SINGLE_BRANCH` / `LANES`
  missions.
- Lane worktrees need **no** sparse-checkout change. The first draft framed this
  wrongly: a lane is checked out on the lane branch, so COORD content is absent
  regardless of patterns. A lane reaches its review cycles through the seam, which
  anchors on `get_main_repo_root` and is CWD-invariant.

## What the first draft got wrong

Recorded because two of these would have shipped an unimplementable change.

| Claim | Status |
|---|---|
| "No new routing machinery is required" | **False.** True of the read seam only; the classifier and commit router both need work. |
| "A read that finds nothing at COORD falls back to PRIMARY" | **Not the failure mode.** The seam raises first, for all 45 affected missions. |
| The `slice-f` on-disk evidence shows partition drift | **Misattributed.** That mission has `topology: None` — no partition to disagree about. The real cause is `arbiter.py` probing bare `wp_id` while the writer uses `wp_slug`, already diagnosed under the mission's IC-09. The evidence is struck. |
| "The coord branch is aggregated into primary on consolidation" | **True, but not by the assumed mechanism.** Not `bookkeeping_projection.py`, which is basename-whitelisted to two status files. The carry is the mission-branch squash: the coordination branch *is* `kitty/mission-<slug>-<mid8>`, merged by `_phase_mission_to_target` via `git merge --squash -X theirs`. Verified on 94/96 real missions. |
| The glossary "defines" review cycles as COORD | **One-entry read** of a two-entry, self-disagreeing definition. Fixed in the same change. |

## Alternatives considered

**Keep review cycles PRIMARY and have each consumer resolve each fact from its own
home.** This is the alternative that actually competes, and the first draft omitted
it. It is not hypothetical: `review_artifact_consistency.py` already does exactly
this — `_resolve_lane_state_read_dir` + `_resolve_review_cycle_read_dir`, two kinds,
two homes, one caller. Because the gate already re-resolves both partitions from
mission identity, it does **not** require co-location. Rejected on the operator's
adjudication that per-WP review bookkeeping belongs on the shared coord surface as a
matter of where the trace should live, not because the gate cannot cope — the
motivation is reviewer-facing, and this ADR should not be read as claiming the gate
was broken without it.

**Amend the glossary to say PRIMARY.** Rejected. Review cycles borrowed
`WORK_PACKAGE_TASK` because they live under `tasks/`, a *path* coincidence rather
than a partition argument.

**Leave both and let each consumer choose.** Rejected outright — the multi-authority
shape the charter's single-canonical-authority principle exists to prevent.

**Route by topology at each call site rather than by kind.** Rejected. It reproduces
the routing decision at every consumer, which is how the divergence arose.

## Scope note

`notes` and `move-task` also appear in the glossary's COORD list and also have no
`MissionArtifactKind`. This ADR does not address them. Singling out review cycles is
a scoping decision driven by the referencing mission, not a derivation from P-1.

## References

- Glossary: [`docs/context/orchestration.md#coord-partition`](../../context/orchestration.md#coord-partition), [`#primary-partition`](../../context/orchestration.md#primary-partition)
- [ADR 2026-06-24-1 — kind and topology aware artifact placement](./2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
- [ADR 2026-07-19-1 — WP runtime state event-log eviction via InnerStateChanged](./2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md)
- Referencing mission: `kitty-specs/review-cycle-verdict-seam-rebuild-01KZ2W7W/`
- Code: `src/mission_runtime/artifacts.py`, `src/specify_cli/coordination/commit_router.py`, `src/specify_cli/post_merge/review_artifact_consistency.py`, `src/specify_cli/merge/bookkeeping_projection.py`
