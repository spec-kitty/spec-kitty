---
title: 'Field report: tactical workarounds for driving a full governed mission end-to-end'
description: 'Six maintainer workarounds surfaced driving a governed mission (mission-type-canonical-source, PR #4821) end-to-end; lane-bound, several superseded by execution-context epic #1619 or already fixed.'
doc_status: draft
updated: '2026-09-21'
related:
- docs/plans/engineering-notes/index.md
- docs/plans/engineering-notes/2026-07-19-migration-contract-step-ownership-field-report.md
- docs/development/reference/known-friction-points.md
- docs/development/how-to/pr-landing.md
- docs/architecture/execution-lanes.md
---

# Field report: tactical workarounds for driving a full governed mission end-to-end

**Date:** 2026-09-21 · **Agent run:** full-mission drive (Claude Code, Opus, single
orchestrator, sequential WPs) · **Human-in-command:** maintainer (operator) · **Mission:**
`mission-type-canonical-source` (#3831 / #4088, PR #4821 — make the mission-type the canonical
source) · **Outcome:** mission driven spec → plan → tasks → implement → review → consolidation.

## Scope and status of this note

These are **tactical mission-driving mechanics, not doctrine.** They are tied to the *current,
in-flux* lane implementation and the per-WP `spec-kitty implement` worktree model. Several are
expected to be reshaped — and possibly obsoleted — by the mission-execution-context epic
**#1619** (and siblings #3129 / #2624) once the lane/worktree model changes; each learning
carries a one-line "still relevant?" note flagging that. (An earlier draft mis-attributed this
to #2652 — that epic retires the mission-type-source tree and does *not* touch the lane model;
corrected via the ticket-mapping pass in "Related tickets" below.) This page is recorded so the team and future agents do not rediscover the same friction.
It is **not** a durable contract: re-verify against the tracker before trusting specifics. Each
learning below has a stable id (`L1`–`L6`) so a downstream ticket-matching pass can map it to an
existing or new issue.

## The learnings

### L1 — Lane-worktree ↔ mid-mission-rebase collision {#l1-lane-worktree-rebase-collision}

- **Symptom:** When driving a full mission via per-WP `spec-kitty implement` lane worktrees and
  upstream advances mid-mission, rebasing onto the new upstream orphans the pinned
  `planning_commit_sha` (finalize "preserves" the now-stale SHA rather than re-pinning it), and
  `implement`'s dependency-lane auto-merge conflicts on the planning files (`tasks/WP*.md`) —
  there is no merge driver for them.
- **Workaround:** Defer the upstream rebase to consolidation (do not rebase mid-mission), **or**
  pivot to implementing directly on the mission branch (see L2).
- **Still relevant?** Covered — remediating tickets exist under execution-context epic **#1619**
  (not #2652): #2273 (first-class "rebase mission onto moved base"), #3936 (dependency-lane
  auto-merge resolution), #2897 / #4178 (stale `planning_commit_sha`).

### L2 — Mission-branch-direct implementation {#l2-mission-branch-direct-implementation}

- **Symptom:** For a single-orchestrator, sequential mission the per-WP lane worktrees add
  lane/venv/PYTHONPATH friction and produce a tangled, non-linear history.
- **Workaround:** Implement directly on the mission branch (repo-root checkout, editable `.venv`)
  to avoid that friction and yield cleaner linear history. Fold already-approved lane commits onto
  the branch via `git cherry-pick`, then remove the lane worktrees.
- **Still relevant?** The underlying friction is superseded once execution-context epic **#1619**
  (P0) / #3129 land (they reconcile main/coord/lane); it is also tracked by #2570 / #3959 / #2803 /
  #1907. The positive "implement-on-mission-branch mode" *tactic itself* is unfiled (a candidate
  gap). Not #2652.

### L3 — Full-mission gate-mechanics sequence (non-obvious, hit in this order) {#l3-gate-mechanics-sequence}

- **Symptom:** A sequence of non-obvious gate mechanics blocks progress, each surfacing only at a
  specific point:
  - `mission create` needs a **repo-root checkout** (not a worktree).
  - A WP's **subtasks must be marked done** before `move-task ... --to for_review`.
  - The **issue-matrix verdict validation fires at the FIRST WP approval** (not at merge): every
    matrix row needs a non-`pending` verdict, and any deferred row needs a `#NNN` / "Follow-up:"
    handle.
  - The **scope guard** needs `owned_files` as a **directory-prefix** for a fixture tree, not a
    single file.
  - `spec-kitty tasks` finalize needs `dependencies` + `requirement_refs` frontmatter (**FR/NFR
    accepted, SC not**), with **every FR mapped to some WP**.
- **Workaround:** Pre-satisfy each condition in the order above rather than discovering them
  reactively; treat the first-WP-approval matrix validation as the real deadline for verdicts.
- **Still relevant?** Mostly relevant — these are current gate contracts; the matrix and
  scope-guard specifics may drift, so re-verify against the tracker.

### L4 — `xfail(strict)` for red-first repros in a separate WP from the fix {#l4-xfail-strict-red-first}

- **Symptom:** A red-first reproduction test lives in a different WP from its fix, so the
  intermediate commits between repro-WP and fix-WP are red — which breaks the per-commit-green
  requirement of the rebase-merge model.
- **Workaround:** Mark the repro `@pytest.mark.xfail(strict=True)` so every intermediate commit
  stays green; the fix WP removes the marker, and `strict` forces the flip-to-green (a still-red
  test after the fix fails loudly).
- **Still relevant?** Relevant — this is a general per-commit-greenness technique, not tightly
  lane-bound.

### L5 — Worktree-aware testing + charter-write worktree-escape {#l5-worktree-aware-testing-and-charter-write-escape}

- **Symptom:** Running tests from a linked worktree can silently exercise the *primary* checkout's
  `src` rather than the worktree's, and some charter/CLI **write** commands (e.g.
  `doctrine regenerate-graph`) **escape a linked worktree** and resolve to the primary checkout —
  so a write appears to succeed but landed in the wrong tree.
- **Workaround:** Run worktree tests as
  `PYTHONPATH=<worktree>/src <primary>/.venv/bin/python -m pytest <file>` to reflect the worktree's
  `src`. For charter/CLI write commands, run them from a non-worktree checkout, or verify where
  they actually wrote.
- **Still relevant?** The write-escape half is **already fixed** — #4785 (PR #4790, 2026-09-20):
  charter write commands fail closed from a linked worktree via a shared `git_topology`-backed
  resolver. The `PYTHONPATH` testing gotcha is covered by #2803 (epic #2624) and remains a durable
  manual mitigation while that is open.

### L6 — Clean-history consolidation via soft-reset {#l6-clean-history-soft-reset}

- **Symptom:** Consolidated mission history is tangled (interleaved lane commits, merge commits),
  which the rebase-merge model rejects and which reads poorly.
- **Workaround:** `git reset --soft <base> && git reset`, then re-commit in logical groups to
  produce a clean, per-commit-green history for the rebase-merge model. Verify the working tree is
  byte-identical before/after the reset (this must be a pure commit-boundary change, not a content
  change).
- **Still relevant?** Relevant — a general history-hygiene technique for the current rebase-merge
  landing model.

## Related tickets (validated 2026-09-21)

A `planner-priti` pass mapped each learning to the tracker. **Correction:** L1/L2 are *not*
superseded by #2652 (that epic retires the mission-type-source tree); the relevant epic is
**#1619** — unify mission execution context across coord/main/lane.

| Learning | Status | Tickets |
|---|---|---|
| L1 | Covered (remediating) | #2273 (rebase-onto-moved-base), #3936 (dep-lane auto-merge), #2897 / #4178 (stale `planning_commit_sha`) · epic #1619 |
| L2 | Superseded when landed | #1619 (P0), #3129 · friction #2570 / #3959 / #2803 / #1907 |
| L3 | Covered piecemeal | root-checkout #3449 / #3443 / #4252 · subtasks-done #3944 / #3578 · matrix-verdict #4345 / #1742 / #4162 / #4232 / #4243 · scope-guard `owned_files` #2742 / #3468 / #1162 · finalize `requirement_refs` #2991 (exact) / #2066 / #4152 · umbrella #3454 |
| L4 | Gap (doctrine) | no remediating defect; fold into test-quality doctrine #2951 / #1277 |
| L5 | write-escape **fixed** #4785 (PR #4790); testing-half #2803 (epic #2624) | |
| L6 | Gap (doctrine) | no remediating defect; landing-guidance home #2354 |

**Candidate gaps (identified, not filed):** (1) a supported "implement-on-mission-branch mode for
solo sequential missions" (L2's positive tactic); (2) a precise "finalize must re-pin
`planning_commit_sha` on rebase" (L1 — only obliquely in #2897 / #4178); (3) L4 and L6 as
landing/test-hygiene doctrine (homes #2951 / #1277 and #2354). These are surfaced for the operator
to triage; none was opened by this pass.
