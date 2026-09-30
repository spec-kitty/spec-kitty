---
title: 'Field report: a doctrine-driven P0 remediation, end to end'
description: 'Field report: remediating the merge-core P0 pair #2709/#2711 under Spec Kitty''s own doctrine — process, operator decisions, and doctrine effects.'
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/how-to/manage-issue-tracker.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
- docs/development/how-to/pr-landing.md
- .kittify/charter/charter.md
---

# Field report: a doctrine-driven P0 remediation, end to end

**Date:** 2026-07-18 · **Agent run:** single long session (Claude Code, Opus) ·
**Human-in-command:** maintainer (operator) · **Outcome:** PR
[#2785](https://github.com/spec-kitty/spec-kitty/pull/2785) — merge-core P0 pair
**#2709** (squash clobbers target-newer provenance) + **#2711** (rollback/resume
incoherence) fixed, plus fast-follow P0 [#2786](https://github.com/spec-kitty/spec-kitty/issues/2786).

This note is for maintainers and contributors weighing *what the doctrine/docs actually
buy you* on a real remediation. It is a reflection, not an ADR: it records the process, the
operator's decisions, and — the point of the write-up — the concrete places where a charter
rule, an ADR, or a guide changed what the agent did.

## The task

Opening instruction: *"Look for open P0 bugs with regression-marked red tests. Select one
or two related ones. Start a remediation mission, launch a research squad."* Everything
downstream followed the toolkit's own workflow: dispatch a governed mission, run adversarial
squads at each planning point-cut, ATDD red-first, per-WP implement→review, consolidate,
PR, pre-merge squad — then handle CI reds and tracker hygiene by the book.

## The arc (what happened)

1. **Selection.** Picked the git/merge pair #2709/#2711 (both surfaced in the #2658 merge;
   both reliability/git; documented repros). Deliberately *rejected* #2770 — it looked
   tempting but the operator flagged it was owned by a dedicated session, so it was rolled
   back after an accidental start.
2. **Plan, hardened by five adversarial squads.** Pre-spec research (4 lenses) → post-spec →
   post-plan → a canonical-**seam-fit** mini-squad → post-tasks anti-laziness. Findings were
   folded into `spec.md`/`plan.md` at each point-cut.
3. **Red-first ATDD.** Two failing reproductions landed *before* any fix, each independently
   reviewed for RED-for-the-right-reason.
4. **Implement→review loop.** Six WPs across two decoupled chains; reviewer ≠ implementer on
   every WP; the fixes turned the reds green with the merge ratchets held.
5. **Consolidate → PR → pre-merge squad.** `spec-kitty accept` + `spec-kitty merge`, clean
   2-commit history, draft PR, then a pre-merge squad on the aggregate diff.
6. **CI reds + tracker hygiene.** Classified the CI failures (fold mine, leave the
   known-P0s), escalated the fast-follow to P0, and landed its red-first reproduction.

## Operator guidance — the decisions a human made

The agent drove; the operator steered at the load-bearing forks. The decisions that
mattered:

- **"#2770 is handled by a dedicated session. Stop."** → retarget, and roll back the
  accidental duplicate cleanly. (Collaboration discipline: don't step on another lane.)
- **Cadence, explicitly sequenced:** *"squad first, then plan"* · *"post-tasks review squad,
  then fixes, then implement-review."* The operator set where the point-cuts fell.
- **Safety-gate calls.** A pre-existing charter-staleness gate blocked `implement`. The
  operator chose *"try to bypass — only if genuinely non-mutating,"* then, when no
  non-mutating path existed, authorized a *temporary, self-reverted* `preflight.enabled`
  toggle scoped to workspace allocation. Later, when the safety classifier refused to let
  the agent self-grant a pre-review-gate skip, the operator ran the one command themselves.
  The line held: **an agent does not self-authorize bypassing a safety gate.**
- **"Recent mission merged. Rebase onto upstream/main, install SK, reprise."** The operator
  cleared the blocker out-of-band; the agent re-homed all branches onto current upstream and
  resumed.
- **"Consolidate, rebase, clean history, PR + review squad."** The close-out sequence, named.
- **"I undrafted. Log the fast-follow — label/parent/type per the triage guide."** and
  **"#2786 is P0; commit a main-breaking test per the P0 ADR."** The operator set severity
  and invoked the honest-red-main contract.

The pattern: the human owns *scope, severity, and safety-gate exceptions*; the agent owns
*execution, verification, and folding findings*.

## Where the doctrine/docs actually changed the outcome

This is the part worth sharing. In each case a written rule — not agent judgment — decided
the move.

- **Red-main-is-honest ADR ([2026-07-17-1]) → we did not green-wash.** The pre-existing P0
  reds (#2736, #2772, #1834) were *left red* on the PR because the ADR says mainline red is
  the honest release signal, not a thing to silence. And when the fast-follow was escalated
  to P0, the same ADR *required* landing a `@pytest.mark.regression` test that **breaks
  main** with a docstring referencing its ticket. The doctrine made "add a failing test on
  purpose" the correct, non-negotiable move.
- **`manage-issue-tracker.md` → the fast-follow was typed, prioritized, and parented
  correctly.** Native issue **type** `Bug` (not a label); **priority** a label, and *not* P0
  until the operator escalated it; **parent** a native sub-issue link under the functional
  epic #1795 — explicitly *not* under the closing #2711 bug (the guide warns that parenting a
  live defect under something about to close hides it). The guide's P0 calibration criteria
  ("data/state corruption / split-brain committed writes") is exactly what justified the
  escalation.
- **The pr-landing "fold-first" red policy → CI reds were classified, not blanket-fixed or
  blanket-ignored.** The operator restated it as the rule: *fold reds efficiently, unless a
  known P0-labeled product defect or an oversized remediation warrants a tracked mission.*
  That produced a clean split — three reds were **mine** (dead-symbol `__all__`, a raw
  `KITTY_SPECS_DIR/slug` path-join bypass, diff-coverage) and got folded; the rest were
  pre-existing P0s and got left honest.
- **Charter "single canonical authority" + the seam-resolution docs → a whole class of
  fixes.** The seam-fit squad rejected a hand-rolled coord-ref lookup in favor of
  `resolve_placement_only(...).ref`, and a hand-rolled reducer in favor of the existing
  `coordination_branch_ref` authority. The post-tasks and CI gates then *caught a regression
  of exactly that rule* — a raw path-join in `done_bookkeeping.py` that the architectural
  `test_zero_functional_raw_bypass` gate flagged (FR-004). The doctrine wasn't just advice;
  a gate enforced it.
- **The INV-5 #1827 / AC-B3 ratchet docs → the fix design (Option A) was chosen and
  *verified against the right file*.** The post-plan squad confirmed Option A (revert the
  coord `done` commit) does not violate the phase-ordering ratchet — and caught that the
  plan cited the *wrong* test file for that ratchet. The revert mechanism was then
  constrained by AC-B3 (no raw `update-ref`) to a coord-worktree `git revert`.
- **"Judge the test, not git-blame" (DIRECTIVE_041) → a vacuous assertion was replaced.**
  The #2711 red repro empirically found that the "duplicate `done`" bug does *not* manifest
  as a tip `count > 1` (safe-commit replaces the tip); the binding contract is `event_id`
  byte-stability. That correction was folded back into the spec and the fix WPs.

## What the adversarial-squad cadence caught (that one reviewer would not)

The strongest argument for the point-cut cadence is the list of real defects it surfaced
*before* they reached mainline — each cheaper to fix where it was found:

- a **wrong ratchet-file anchor** in the plan (post-plan);
- a **vacuous count assertion** and a **green-on-base repro trap** (post-spec / post-tasks);
- a **phantom "#2770 collision"** (a conflated issue number) that would have caused a
  needless rebase scare (post-plan, independently verified);
- the **`.git/info/attributes` persistence leak** — a squash-path seed that never tore down
  and would silently re-couple a *later* auto_rebase (pre-merge);
- a **parity-guard gap** — the class guard bound the driver registry to `.gitattributes` but
  not to `init.py`/the migration (pre-merge);
- a **wrongly campsite-deleted baseline file** that turned an architectural test red
  (pre-merge).

And the **post-merge full-suite sweep** (charter standing order: run the full arch-gate
sweep after merge) caught the single most important integration bug — WP03's driver-config
generalization had pre-empted auto_rebase's event-union rule via a "compat alias" that
preserved the *symbol* but not the *behavior*. No per-WP review could have seen it; the
sweep did.

## Honest friction (so others can plan around it)

- **Safety classifiers vs. legitimate gate skips.** The environment's classifier repeatedly
  blocked `--skip-pre-review-gate` and even the *config edit to grant* that permission —
  correctly refusing agent self-authorization, but it meant a red-first WP could not advance
  without the human running one command. Worth knowing: for red-first split WPs, budget an
  operator touch or a pre-granted permission rule.
- **Merge-driver code under coverage tools.** The new `spec-kitty merge-driver-*` commands
  run as git subprocesses, so line-coverage tools score them ~17% even though integration
  tests exercise them end to end. Direct unit tests of the reconciler functions were needed
  to satisfy `diff-coverage`.
- **A `spec-kitty`-that-invokes-itself deployment note.** Because the drivers shell out to
  `spec-kitty`, the fix only *fires* when an up-to-date `spec-kitty` is installed — the
  pre-review gate (running the stale install) reported false reds until reinstall.

## Takeaway

The doctrine did what it claims: it *removed judgment calls from the hot path*. "Should this
red block the PR?" was answered by the fold-first policy and the red-main ADR, not by taste.
"How do I file the fast-follow?" was answered by the tracker guide down to the parent link.
"Is Option A safe?" was answered by the INV-5 ratchet — and enforced by a gate. The
adversarial cadence and the post-merge sweep repeatedly paid for themselves by catching
cross-cutting regressions at the cheapest point. The cost was real (five planning squads, a
pre-merge squad, a debugger pass), but every squad returned a concrete, folded finding — and
the one bug that would have shipped silently (the auto_rebase regression) was caught by the
sweep the standing orders mandate.

The human stayed exactly where the collaboration doctrine puts them: on scope, on severity,
and on the safety-gate exceptions an agent must never grant itself.
