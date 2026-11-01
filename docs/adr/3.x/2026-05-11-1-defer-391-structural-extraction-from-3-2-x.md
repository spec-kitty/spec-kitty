---
title: 'Defer #391 still-open structural extraction sub-tickets from the 3.2.x stabilization
  scope'
description: 'Keeps three open structural-extraction tickets out of the 3.2.x stabilization scope, since refactors with no release-blocking symptom inflate regression risk.'
status: Accepted
date: '2026-05-11'
doc_status: active
kind: ADR
updated: '2026-05-11T00:00:00Z'
---

- Epic [#822](https://github.com/Priivacy-ai/spec-kitty/issues/822) — 3.2.0 stabilization and release readiness
- Epic [#992](https://github.com/Priivacy-ai/spec-kitty/issues/992) — drain the bug queue by repairing domain boundaries
- Epic [#391](https://github.com/Priivacy-ai/spec-kitty/issues/391) — Tech/Functional Debt Remediation
- Still-open #391 sub-tickets: #612, #613, #614

---

## Context and Problem Statement

The 3.2.x stabilization mission (canonical: `kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/`) was scoped during planner intake to cover the remaining P1 bugs that have no active PR (#985, #987, #986, #983, #984), plus a narrowed slice of the encoding chokepoint work (#644). The original `kitty-specs/_drafts/` scratch was removed after the canonical mission absorbed all its content.

During scope review, the question arose whether the still-open sub-tickets of #391 — namely #612 (extract runtime/mission decisioning boundary), #613 (glossary as a functional module), and #614 (separate integration boundaries inside `src/specify_cli`) — should also be folded into the same mission.

This decision matters because epic #822 explicitly defines anti-scope for the 3.2.x stable release:

> *"This epic is scoped to release blockers, workflow correctness, and low-risk stabilization. It should not absorb speculative product expansion."*

And:

> *"No silent state-transition loss, no contaminated review prompts, no misleading success/failure output after local state changes, no merge result that is locally 'done' but not shippable …"*

The still-open #391 children are **structural module-extraction refactors**, not bug fixes for any of those release-blocking symptoms.

## Decision Drivers

- **Release-scope discipline.** #822 anti-scope is explicit: stabilization missions must not absorb structural work without a current release-blocking repro tying the refactor to a symptom on the blocker list.
- **Regression-confidence isolation.** Co-resident P1 bug fixes and large module moves inflate the diff surface and weaken bisection / review confidence for the bug fixes specifically.
- **Precedent.** The shared-package-boundary cutover mission (`shared-package-boundary-cutover-01KQ22DS`, 2026-04-25) established the pattern of doing module-boundary work as a discrete mission with its own architectural-enforcement tests — not as a side WP of a bug-fix mission.
- **Partial supersession.** The shared-package-boundary cutover already enforces the runtime/events/tracker boundary architecturally (see `tests/architectural/test_shared_package_boundary.py`), which means #612 is at minimum partially superseded; its remaining scope needs re-evaluation before it can be planned, not bundled.
- **No current repro on the bug queue.** None of #612 / #613 / #614 appears on any current open `bug` issue's repro chain as a contributing cause.

## Considered Options

- **(A) Defer all three** to a post-3.2 boundary-cleanup mission.
- **(B) Accept a narrowed subset** with a current repro tying it to a release blocker — that subset would still need its own mission, not co-resident WPs.
- **(C) Fold all three into the 3.2.x review/merge gate-hardening mission as additional WPs.**

## Decision Outcome

**Chosen option: (A) Defer all three**, because the still-open #391 sub-tickets are structural refactors without a current release-blocking symptom, and folding them into a stabilization mission would directly violate #822's anti-scope while inflating regression risk on the P1 bug fixes the mission is meant to ship.

### Consequences

#### Positive

- The 3.2.x mission keeps a tight bug-fix surface (WP01–WP06) with clean per-WP regression isolation.
- Mission review can attest to release-blocker closure without entangled module-move review.
- #612 in particular gets re-scoped *after* the shared-package-boundary cutover's enforcement tests, which is a cleaner planning input than the original 2026-04 framing.
- Future operators reading #391 see an explicit deferral record rather than silent omission.

#### Negative

- The #391 epic remains formally open and continues to accrue staleness signal until the post-3.2 boundary-cleanup mission is scheduled.
- Operators expecting "just one more cleanup pass" will see the deferral and may push to revisit — owner needs a short answer ready ("post-3.2, separate mission, see ADR 2026-05-11-1").

#### Neutral

- No code is modified by this decision.
- The deferred tickets remain in the GitHub backlog with their existing labels.

### Confirmation

This decision is correct if, after the 3.2.x review/merge gate-hardening mission lands:

- No P1 bug closed by the mission relies on logic the deferred refactors would have moved.
- The 3.2.x mission's review report (per WP03's new contract) does not record any structural-extraction findings as deferred risk.
- A follow-up planning pass against #391 can re-scope #612/#613/#614 on top of the now-enforced shared-package boundary without rework against this mission's diff.

If those signals hold, the deferral preserved release velocity without losing the underlying debt.

## Pros and Cons of the Options

### (A) Defer all three

Push #612, #613, #614 to a post-3.2 boundary-cleanup mission with its own decomposition pass.

**Pros:**

- Aligns with #822 anti-scope literally.
- Preserves bisection confidence on the P1 bug fixes.
- Allows #612 to be re-framed after the already-enforced shared-package boundary.

**Cons:**

- Leaves #391 open for at least one more release cycle.

### (B) Accept narrowed subset

Pull only the sub-ticket(s) with a current release-blocking repro into a *separate* mission running alongside (not inside) the 3.2.x bug-fix mission.

**Pros:**

- Honors the "if it blocks the release, ship the cleanup" principle.

**Cons:**

- No current repro qualifies any of #612/#613/#614 today; the option is hypothetical at best.
- Running two missions in parallel adds coordination cost (worktree contention, merge ordering) for no observed benefit.

### (C) Fold all three into the 3.2.x mission

Add #612/#613/#614 as additional WPs on the current branch.

**Pros:**

- One mission closes one more epic.

**Cons:**

- Directly violates #822 anti-scope.
- Inflates diff surface; weakens regression confidence on WP01–WP06.
- Mixes two reviewer skill sets (bug-fix review vs. structural-extraction review) in one approval gate.
- Increases merge-conflict risk in `src/specify_cli/`.

## More Information

- Canonical mission this ADR is attached to: `kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/spec.md`
- Precedent for discrete module-boundary missions: [`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`](2026-04-25-1-shared-package-boundary.md)
- Architectural enforcement tests that partially supersede #612: `tests/architectural/test_shared_package_boundary.py`
