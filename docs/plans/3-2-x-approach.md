---
title: '3.2.x Delivery Approach — Operator Plan, Dialectically Challenged'
description: 'The operator''s 3.2.x sequencing (doctrine-swap first, cleanup next, hold non-critical PRs), stress-tested by a two-round dialectic squad into a fact-checked plan.'
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/how-to/manage-issue-tracker.md
- docs/guides/how-to/missions/keep-main-clean.md
- docs/plans/domains/doctrine-charter-domain-plan.md
---

> **Superseded (2026-09-06, Convergence #3881).** This plan describes the pre-convergence
> line, including the since-removed local sync daemon / delivery / import-history surface.
> It is kept as a historical record. The active-cycle plan of record is the
> [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md); the
> [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md) is the prior-cycle record.

# 3.2.x Delivery Approach — Operator Plan, Dialectically Challenged

## Status & method

This document records the operator's stated 3.2.x sequencing intent and the result
of putting it through a **two-round dialectic squad**:

- **Round 1 (thesis)** — three profile-loaded reviewers independently read the plan
  through their lens: **architect-alphonso** (architecture), **planner-priti**
  (delivery/sequencing), **paula-patterns** (recurring-boundary / whack-a-field).
- **Round 2 (antithesis)** — the same three adversarially challenged the round-1
  synthesis, each instructed to argue that round 1 *over-corrected* — including
  turning their own round-1 findings against themselves.
- **Synthesis (this doc)** — the orchestrator reconciled thesis and antithesis and
  fact-checked every load-bearing claim against the live tracker and code.

All reviewer claims that drive a recommendation were verified; the corrections are
called out inline (see [Fact-check corrections](#fact-check-corrections)).

---

## Related domain plans (durable throughlines)

This document is **release-scoped** 3.2.x sequencing intent and follows the
distil-then-retire lifecycle. The durable, version-spanning strategy for each domain
lives in its **domain plan** — cross-reference those rather than duplicating them:

- **Doctrine & charter** — [Doctrine & Charter — Domain Plan](domains/doctrine-charter-domain-plan.md)
  (companions: the [3.2.x Open-Core Delivery Plan](3-2-x-open-core-delivery-plan.md) and the
  [Glossary Doctrine Overhaul — Program Plan](glossary-doctrine-overhaul-program.md)).
- **SaaS & hosted sync** — domain plan retired 2026-09-06 (Convergence #3881): the hosted-sync surface re-homed to the authoritative upstream repos; see the convergence-retirement ADR
  (`docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`).
- **Packs extraction** — *(planned domain plan)*.
- **API & dashboard** — *(planned domain plan)*.

Where this release plan and a domain plan disagree on *domain scope*, the domain plan
is canonical; where they disagree on *what ships in a given tag*, this plan and the
milestone roadmap win.

---

## 1. The operator's plan, as stated

> - Handle **doctrine swap-over epics** with highest priority.
> - **Reprise code cleanup** (degodding, dead-code removal, duplication fixes) next.
> - **Only merge in high-priority community PRs** on other surfaces until the
>   "brain-surgery runs" are complete.

Mapped to the tracker:

- **Band 1 — doctrine swap-over ("brain surgery"):** `#2652` (specify_cli/missions
  retirement), `#2721` (mission-type step-model unification), `#2519` (charter
  authoring & lifecycle robustness), `#2737` (charter-lint governs-edges).
- **Band 2 — code cleanup:** degodding (`#2160` coord-authority trio, `#2026`
  merge.py), dead-code (`#1797`), duplication consolidation, ruff/mypy/sonar debt
  (`#1932`/`#1928`).
- **Band 3 — hold:** only high-priority community PRs on unrelated surfaces merged
  until Band 1 completes.

---

## 2. Verdict in one line

**The priority is right; the *rigidity* is wrong.** All six reviews endorse
doctrine-first. Both antithesis rounds then dismantled the round-1 machinery that
tried to formalise it — a "Band-0" prerequisite, a moving frozen-surface gate, and a
70/20/10 capacity split — as over-engineering for a small-maintainer repo. The plan
that survives challenge is **the operator's original lightweight intent plus a short
list of real dependency orderings and one merge-hygiene gate** — not a governance
tier system.

---

## 3. What the dialectic *confirmed* (survives both rounds)

1. **Doctrine-first is architecturally sound.** The doctrine layer
   (mission-type / step-model / DRG resolution) is *upstream* of the runtime that
   consumes it, and doctrine is **authored on the primary/root partition** (spec →
   plan → tasks run from the repo root, no worktree). Cleaning the runtime first is
   not a correctness prerequisite for authoring doctrine. *(Alphonso, both rounds.)*

2. **Protecting the doctrine surface from concurrent unrelated churn is the correct
   instinct.** The doctrine epics are a tightly coupled cluster; landing unrelated
   PRs through the same window multiplies rebase/conflict cost. The disagreement was
   only ever about the *mechanism*, never the goal. *(Priti, both rounds.)*

3. **`_read_path_resolver` is a genuine god-module** (1629 LOC, reached from dozens
   of sites) whose coord-vs-primary topology logic is the recurring source of
   `StatusReadPathNotFound` / coord-shadow defects. Real debt — but its fix is an
   *independent scoped degod mission*, not a rider on the doctrine work. *(Paula,
   both rounds.)*

---

## 4. What the dialectic *amended* (the real deltas to adopt)

Each amendment below survived the antithesis round — i.e. it is a dependency or
hygiene fact, not process overhead.

### A. Doctrine-first is a **priority, not a hard wall**; invariant-adjacent cleanup runs **concurrently and gates the merge, not the start**

The decisive correction (Alphonso, round 2): the coordination split-brain tail of
`#2160` blocks **merging** Band-1 work, not **building** it — because the split-brain
lives on the *status/lifecycle* surfaces (`emit_status_transition`, `safe_commit`,
coord R/W authority), while doctrine artifacts are single-sourced on the primary
partition. Therefore:

- The `#2160` P0 authority tail runs as a **concurrent lane**, and must be
  coord-clean **before the first Band-1 merge lands** — enforced by the *existing*
  merge preflight (`spec-kitty merge --dry-run` / `merge/forecast.py`), **not** a new
  band.
- Broad cleanup (`#1797` / `#1932` / `#1928`) is genuinely later and stays deferred.

This is the honest reading of "cleanup next": the *invariant-adjacent* degod is
concurrent-and-merge-gating; the *cosmetic* debt is deferred.

### B. Explicit dependency orderings inside the doctrine work

- **`#2519` activation-reconciler *soft-precedes* `#2652` enumeration.** `#2652`
  pins availability to `charter.activated_mission_types`; `#2519`'s root defect is
  that the activation ledgers (`config.activated_*` vs `answers.selected_*`) are
  disjoint with no reconciler (drift already bit a prior PR). Enumeration must
  consume reconciled state. This is a **data dependency, not a strict serial chain** —
  `#2721` (steps) and `#2737` can proceed in parallel. *(Alphonso corrected round 1's
  over-serialised framing.)*
- **`#2737` is P3 and near-trivial** — fold it into the `#2652`/`#2721` DRG work
  (it is already a child of `#2721`); **do not gate the Band-3 unblock on it.**
- **`#2721` S-C is a regression hotfix wearing an epic's clothes** — it closes a live
  fail-closed regression (documentation / research / plan mission types uncreatable).
  Pull it forward on its own P0 merits, independent of banding.

### C. The merge-hold is a **short, hard, time-boxed freeze** — not a moving gate, not a capacity split

Both antithesis reviewers converged here (Priti decisively):

- **Freeze the doctrine surface** for the duration of the coupled Band-1 critical
  path. Non-intersecting community PRs (docs, isolated CLI ergonomics, dashboard,
  test-only) **merge as normal maintainer triage** — the conflict-forecast preflight
  already tells you whether a PR touches the frozen surface.
- Held contributors do **one clean rebase at the end**, against a now-stable surface —
  respectful and cheap — instead of repeated "rebase-forward" pings as a recomputed
  frozen set shifts under them.
- **No 70/20/10 capacity split.** That models a team; on a solo/small-maintainer repo
  the honest rule is *"doctrine critical path first; touch community PRs only when
  blocked or waiting on CI."*

### D. One cheap in-mission gate: don't spawn an N-th step-binding site

Paula's single surviving concern: `#2652`/`#2721` must route through the **existing**
`runtime/next` `_composition` step-binding delegation rather than adding a new
`_resolve_step_*` copy. Enforce with an **ownership / conflict-surface check at
review** (campsite-first), and do the bulk resolver-site re-point **last, inside the
mission, via a scoped `occurrence_map.yaml`** — the pattern already proven by the
`single-mission-surface-resolver-01KVGCE8` WP07 shim retirement. This is *not* a
Band-0 pre-step.

### E. Add a downstream-consumer verification step to the retirement

`#2661` deletes the `specify_cli/missions/<type>/` tree and the doctrine→`.kittify`
copy step; doctrine ships to 12+ agent dirs and external org packs via
`spec-kitty upgrade`. Add an explicit **downstream-consumer verification WP** so the
tree deletion cannot land without checking `upgrade` behaviour for pre-activation
projects and external packs.

---

## 5. What the dialectic *rejected* (round-1 over-corrections)

| Rejected | Why it fell |
|---|---|
| **"Band-0" as a prerequisite before doctrine** | Category error: it hoists a *merge-time* invariant to the front of the *authoring* critical path. Doctrine is authored on primary/root; the coord split-brain gates the merge, not the build. *(Alphonso r2)* |
| **Consolidate `_read_path_resolver` onto the identity port before doctrine** | The seam is *downstream* of the enumeration contract the doctrine epics rewrite → consolidating first is rework by construction. And the two "seams" are distinct concerns; the identity port is *already* wired into the read-path resolver. The "112 sites edited twice" risk is mostly fictional (different function families). *(Paula r2, Alphonso r2)* |
| **Moving frozen-surface governance tier** | A recomputed set that changes on every Band-1 merge → O(open_PRs × merges) rebase events. Precise-looking, not cheaper than a human judgement call. Replace with a hard freeze + preflight conflict forecast. *(Priti r2)* |
| **70/20/10 capacity split** | Team-scale allocation theatre on a solo repo; won't be measured, invites the exact context-switching the coupled cluster punishes. *(Priti r2)* |
| **Strict serial Band-1 chain** | Over-couples independent work; `#2519`→`#2652` is a soft data dependency, but `#2721`/`#2737` parallelise safely. *(Alphonso r2)* |

---

## 6. The synthesised approach (actionable)

1. **Doctrine-swap epics are the P0 focus** (`#2652`, `#2721`, `#2519`, `#2737`),
   authored on the primary partition. This is the "brain-surgery run."
2. **Inside that work, honour the orderings:** `#2519` activation-reconciler lands
   before `#2652` enumeration; `#2721` S-C regression hotfix is pulled forward;
   `#2721`/`#2737` run in parallel; `#2737` folds into the DRG work.
3. **Run the `#2160` P0 coord-authority tail as a concurrent lane** that must be
   coord-clean before the *first* doctrine merge — enforced by the existing merge
   preflight, not a new band. Broad cleanup (`#1797`/`#1932`/`#1928`) stays deferred.
4. **Merge-hold = short hard freeze on the doctrine surface.** Everything that does
   not touch that surface merges via normal triage (the conflict forecast decides);
   held PRs rebase once, cleanly, at the end. No capacity split.
5. **Guard the rewrite in review:** `#2652`/`#2721` route through the existing
   `_composition` step-binding delegation; bulk site re-point is a scoped-occurrence
   WP done last, inside the mission.
6. **Gate the tree deletion (`#2661`) on a downstream-consumer verification WP.**

**Exit criterion for lifting the freeze:** the doctrine surface is stable — a single
canonical mission-type source is live, the step-model is unified, charter-lint
governs-edges are green (which closes `#2737` by construction), and the DRG +
architectural suite are green on main. *Not* "all PRs merged."

---

## 7. Open decisions for the operator

- **Freeze scope & duration.** Which exact paths are "the doctrine surface," and
  what's the intended time-box? (Suggested surface: `src/doctrine/`,
  `src/specify_cli/missions/`, mission-steps, `graph.yaml`, charter authoring,
  mission-type resolvers.)
- **`#2519` foundation slice.** Confirm the activation-reconciler slice is scoped and
  sequenced ahead of `#2652`'s enumeration slice.
- **`_read_path_resolver` degod.** Spec it as an independent mission now, or leave it
  parked behind the doctrine work? (Reviewers: independent mission, not a rider.)
- **Community-PR communication.** A single "held until \<epic/date\>" note to the
  affected external contributors (MOES-Media, rayjohnson, zohar, wonderu, …) beats
  silent staleness.

---

## Fact-check corrections

The squad ran against a live but imperfect memory of the tracker. Corrected here:

- **`#2689` is already MERGED** (activated-config template resolution shipped) — it
  was cited in round 1 as an "open PR to land first." That prerequisite is already
  satisfied and further de-risks `#2721`/`#2652`.
- **`#2531` is CLOSED** (runtime_bridge decomposed) — it was listed under Band 2.
  Its completion *de-risks* Band 1: the runtime consumer seam is now a small pure
  core to update, not a 4k-LOC god-module. Removed from the cleanup band.
- **`#2737` is P3** (confirmed) — hence "fold, don't gate."
- **`#2721` depends on `#2652`** (confirmed native parent) — the mission-type spine
  is the real coupling.
- Site counts for `_read_path_resolver` are reported qualitatively ("dozens of
  sites"); reviewers' precise figures (112 / 132) were counting-method dependent and
  are not load-bearing.

---

## Appendix: method & participants

- **Squad shape:** 2 rounds × 3 profile-loaded reviewers (thesis → antithesis),
  each reviewer grounded independently in the repo and tracker; no reviewer saw
  another's round-1 output until the antithesis brief.
- **Reviewers:** architect-alphonso (architecture), planner-priti
  (delivery/sequencing), paula-patterns (recurring-boundary / whack-a-field).
- **Reconciliation & fact-check:** orchestrator, against the live
  `Priivacy-ai/spec-kitty` tracker and working tree on 2026-07-17.
