---
title: '3.2.x Executive Overview'
description: 'Executive/stakeholder synthesis of 3.2.x goals and progress since the 3.2.4 release — from a PO, C-suite, and customer point of view.'
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/external/product-manager-evaluator.md
related:
- docs/changelog/3.2.x.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/archive/plans/3-2-x-open-core-delivery-plan.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/changelog/index.md
---

# 3.2.x Executive Overview

> **Prior cycle (3.2.x), kept as a record.** This is a stakeholder snapshot written
> 2026-07-30 to 2026-09-04. The 3.2.x line closed with 3.2.7 (2026-09-10), and the active cycle
> is 4.0.0; see the [4.0.0 Milestone Roadmap](../../plans/4-0-0-milestone-roadmap.md). Present-tense
> statements below ("in flight", decisions pending) describe that time, not today.

> **Related domain plans (durable throughlines):** SaaS & Hosted Sync (domain plan retired 2026-09-06, Convergence #3881 — surface re-homed upstream) · [Doctrine & Charter](../../plans/domains/doctrine-charter-domain-plan.md). This overview is release-scoped; the domain plans hold the version-spanning strategy and the standing P0/reliability picture behind these outcomes.

*Point-in-time stakeholder synthesis, 2026-07-30. Covers everything since the 3.2.4
release (2026-07-05): the shipped 3.2.5 release and the in-flight 3.2.6 cycle. Reads
the milestone from a PO / C-suite / customer point of view; the durable goal
declaration is [release-goals/3.2.x](../../changelog/3.2.x.md), the operator execution
detail is the [milestone roadmap](../../plans/3-2-x-milestone-roadmap.md), the delivery strategy is
the [open-core delivery plan](3-2-x-open-core-delivery-plan.md), and what actually
shipped is the [changelog](../../changelog/index.md). Status was verified by two read-only
audits on 2026-07-30; the delivery plan carries the evidence and the unverified-item
flags.*

## Addendum 2026-09-04 — the milestone map moved; two decisions now sit with the PO

*Read-only reconciliation against live GitHub milestone state on 2026-09-04. The
[2026-09-03 update](#release-readiness--risk-candid) below correctly reported that 3.2.6's
release-blocking book is now empty; this addendum re-anchors the **milestone taxonomy** the
rest of this overview still speaks, per the roadmap's own
[2026-09-04 re-anchor](../../plans/3-2-x-milestone-roadmap.md#addendum-2026-09-04--milestone-taxonomy-re-anchor-the-delayed-action-r).*

**What changed under the plans.** A release-queue reconciliation on **2026-08-23**
reorganised our release milestones. The single "3.2.x milestone" this overview is written
against was **repurposed into "Product backlog"** (validated work not committed to any
release), and the "3.3.x" milestone everything was "deferred to" was **retired** — its work
re-triaged to **4.0.0** (hosted collaboration + next-generation product) or Product backlog.
We now run three discrete milestones: **3.2.6** (shipped-clean stabilization, code-complete),
**3.2.7** (a tight near-term follow-up: doctrine-term renames, profile-load reliability,
perf-CI, dedups), and **4.0.0** (the hosted product plus the deferred structural work).

**The strategic read is unchanged, but two things a stakeholder should hear plainly:**

1. **The structural "finish the strangler" work this cycle exists for is now committed to
   4.0.0** (operator decision 2026-09-04). The G1/G2 spine (execution-context root,
   degod/unshim, seam-binding, the pack-ecosystem extensibility kinds) had sat unscheduled in
   Product backlog; it now carries milestone 4.0.0. 3.2.7 remains the stabilization tail;
   4.0.0 is the hosted product plus this deferred structural finish. The foundation held (see
   the strategic-position section); the remaining structural push now has a release home.
2. **The one failing quality gate (21 security findings) rides with that structural work —
   now scheduled in 4.0.0.** Our SonarCloud security backlog maps almost 1:1 onto the degod
   slices, so the security debt and the structural remediation land together — with the
   exception of 3 path-traversal blockers that are a called-out ~90-min fix on their own.

**Decision resolved:** the strangler-spine epics are committed to 4.0.0 (2026-09-04), no
longer implicitly "3.2.x-cycle work" off every release. The remaining PO call is release
timing (noted below). The 4.0.0 goals are declared in
[`docs/changelog/4.0.0.md`](../../changelog/4.0.0.md).

## Bottom line

3.2.x is our **stabilization-and-foundations cycle** — no flashy new surface, by design.
Since 3.2.4 we shipped one full release (3.2.5) and have a rich sixth (3.2.6) in flight.
**The hard structural work this cycle exists to do is largely done** — our core data now
has single sources of truth, our governance layer now genuinely drives the product, and
our doctrine is becoming independently shippable. Two honest caveats: **3.2.6 is not yet
releasable** (our release gate is red by policy — see [Risk](#release-readiness--risk-candid)),
and the *remaining* work is small and well-understood rather than open-ended. *(Update
2026-09-03: the first caveat has since cleared — 3.2.6's release-blocking bug book is fully
discharged and the milestone is code-complete; see [Release readiness &
risk](#release-readiness--risk-candid).)*

## What 3.2.x is for (in business terms)

Three goals, each a customer outcome:

- **G1 — Governance drives the product.** Our "doctrine" (the configurable rules for how
  missions, docs, and workflows behave) now actually controls runtime behavior instead
  of being documentation. **This is the foundation of our open-core model:** customers
  can tailor governance without forking our source.
- **G2 — One source of truth for core data.** We have been consolidating the places that
  decide *where mission data lives and how identity/state are derived* down to single
  authorities — the root cause of a whole class of reliability bugs.
- **G3 — Faster, more honest engineering.** CI and quality gates that make G1/G2 safe to
  keep changing.

## Progress since 3.2.4 — what it means for customers

**Customization & open-core (the strategic thread).** Doctrine is now **shippable and
forkable**: organizations can ship their own governance, docs standards, and supporting
files to their repos *without patching our code*. Pack locations are now portable across
machines and CI (no more hardcoded paths breaking teammates). This is the groundwork for
selling and supporting a customizable product on a stable public core.

**Reliability (the bulk of the work).** The changes customers will *feel*:

- Quality gates **stopped emitting confident-but-wrong verdicts**, and approved review
  evidence now survives a merge instead of being silently discarded.
- Work-package state now has **one authoritative record**, closing a class of "the tool
  says X but reality is Y" bugs.
- **Upgrades no longer strand or dirty** parallel work areas; the dashboard now correctly
  shows in-flight work that used to silently disappear.
- Connections to our hosted service **fail safely** instead of silently pointing at the
  wrong server.

**Robustness & automation.** Agent-driven and scripted/CI runs **no longer hang** waiting
for input — increasingly important as customers automate on top of us.

**Velocity & honesty.** CI is meaningfully faster, and regressions are now caught **at
review time rather than at merge**, shrinking the feedback loop.

**One breaking change customers must action:** very old (pre-3.2.x) missions need a
**one-command migration** to keep working. This was a deliberate trade — retiring a
dual-support path that was itself a persistent bug source.

## Strategic position: the open-core pivot is closer than the roadmap showed

A verified re-audit this week found our internal roadmap had **understated our
progress**. The core-data-consolidation work (G2) is substantially *delivered* — it was
simply tracked under the wrong labels. The governance layer (G1) is *already live* in the
product (three mission types run entirely off configurable doctrine today). The remaining
work to reach a clean open-core boundary is **bounded**: the doctrine module is ~90% ready
to stand alone as an independent package, and the last real gap is making our governance
layer the single, stable entry point that external adopters build against.

## Release readiness & risk (candid)

> **Update 2026-09-03 — the release-blocking book is now empty.** The 3.2.6 release
> DAG (tracker #3692) is fully discharged: all twenty release-critical bugs across
> mission-completion, review-verdict, merge/retention, accept-portability,
> commit-boundary, upgrade, charter/doctrine, and diagnostic clusters have landed, and
> #3692 is closed. The milestone stands at 66 closed / 0 remaining work items, and no
> open PR gates the tag. The "not tag-ready / CI red 10+ runs" posture below was written
> 2026-07-30 and is **superseded** on the functional axis — the classification question it
> named resolved in the milestone's favour (see the milestone roadmap's
> [2026-08-12](../../plans/3-2-x-milestone-roadmap.md#addendum-2026-08-12--release-posture-refresh-ci-green-except-the-standing-sonar-backlog)
> and [2026-09-03](../../plans/3-2-x-milestone-roadmap.md#addendum-2026-09-03--326-release-dag-fully-discharged-3692-closed)
> addenda). What remains is the standing SonarCloud maintainability backlog, tracked
> separately as scoped cycle debt, not a release-blocking regression.

*Historical posture (2026-07-30), retained for context:*

- **3.2.6 is not tag-ready.** Our mainline CI has been red for 10+ consecutive runs. This
  is **partly by design** — our policy is that mainline honestly reflects known
  release-blocking bugs rather than hiding them, and CI (not opinion) is the release
  authority. It is a discipline, not a fire.
- **The one open question:** whether *all* of the red reduces to those known, tracked
  blockers, or whether a recent change introduced something new. Resolving that
  classification is the single gating item before any release conversation — an
  hours-not-weeks task.

## What's next & the strategic call for the PO

The plan (see the [open-core delivery plan](3-2-x-open-core-delivery-plan.md)) is an
**open-core breaking-change window**: get the remaining breaking/design changes out **as
fast as possible** to our small set of consenting early-adopter customers, **without ever
stalling bug fixes for them**, and make each change cheap to absorb (automated
migrations + backward-compatible shims + advance notice).
After this window, the external surface
stabilizes and stops disrupting customers.

**Decisions that need product ownership:**

1. How to sequence the remaining breaking changes into releases (the "3.2.6 / 3.2.7"
   numbers are urgency signals, not commitments).
2. Whether to hold the honest-red mainline through the window, or stabilize the baseline
   first.
3. Confirming the named early-adopter customers who receive pre-releases and migration
   notes.

**In one sentence for the board:** *the risky structural rework of 3.2.x is largely
behind us and has de-risked our open-core direction; what remains is a bounded,
well-understood push to lock a stable customer-facing contract — the main open question is
release timing, not whether the foundation holds.*
