---
title: 4.0.0 Milestone — Roadmap
description: 'Roadmap for the 4.0.0 cycle, re-synthesized 2026-10-06 against the GA milestone: release posture, what still gates GA, dependency spine, exit criteria and risks.'
doc_status: active
type: explanation
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-06'
related:
- docs/changelog/4.0.0.md
- docs/changelog/index.md
- docs/plans/index.md
- docs/plans/4-x-executive-overview.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/code-quality/index.md
- docs/changelog/release-goals.md
---
# 4.0.0 Milestone — Roadmap

*Planner synthesis, first written 2026-09-14 against the old `4.0.0` milestone (GitHub
milestone 8, since renamed **4.x Work**). **Re-synthesized 2026-10-06** against the GA gate,
the [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11) milestone
(read with `gh api repos/spec-kitty/spec-kitty/milestones/11` and its issue list), the
2026-10-01 direction update below, and the CI debrief of 2026-10-05. The durable "why" is the
declaration of intent, [`4.0.0.md`](../changelog/4.0.0.md). This roadmap is the authority for
the **active** 4.0.0 cycle; the prior [3.2.x milestone roadmap](3-2-x-milestone-roadmap.md)
points here (see its
[Addendum 2026-09-14](3-2-x-milestone-roadmap.md#addendum-2026-09-14--4x-is-now-the-active-cycle-authority-moved)).
A summary for decision owners is in the [4.x Executive Overview](4-x-executive-overview.md).*

## Intent of 4.0.0

4.0.0 was declared on 2026-09-04 as the **hosted-collaboration + structural-finish** cycle:
**G1 hosted collaboration (Team Kitty)**, **G2 next-generation product capabilities**, and
**G3 the open-core structural strangler finish**. Since the 2026-10-01 direction update,
4.0.0 GA is a **local CLI integrity** release: G1 is frozen, and the structural work of G2
and G3 continues on the 4.x line after GA. The four operator-stated goal themes keep their
numbering:

1. **Stability.** The CLI never reports success while it loses, overwrites or strands local
   work. Failures are named, not swallowed.
2. **Maturity.** One canonical local event store, honestly reported; large modules split
   into owned seams.
3. **Extensibility.** A governed front door and a stable, versioned application API, so
   CLI, UI, MCP and SDK consumers build against one surface.
4. **Team Kitty enablers.** Frozen since 2026-10-01 (see below).

Same discipline as the prior cycles: **no new shadow paths**. Route or extract onto an
existing authority; never build a parallel one.

## Direction update (2026-10-01): hosted collaboration is off the critical path

The CEO, CPO and CTO froze Team Kitty / SaaS work and deprioritised it while the commercial
vision is reviewed. This section overrides anything below that treats hosted collaboration,
auth or Zeitgeist as release-gating. Four rules follow for the rest of the 4.x line:

1. **4.0.0 GA is the [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11)
   milestone and nothing else.** No Team Kitty, Zeitgeist or hosted-auth item gates it. The
   hosted-facing epics (#3892 zeitgeist-client auth, and the auth P1 residuals) stay on
   [4.x Work](https://github.com/spec-kitty/spec-kitty/milestone/8) and wait for the freeze to
   lift. The retired sync transport stays retired.
2. **All external interaction flows through the adapter module.** The CLI core writes its
   events and does not know where they go. The status fan-out in
   `src/specify_cli/status/adapters.py` is that seam, and it is the starting point for the
   envisioned publish/subscribe system. Zeitgeist is one possible consumer; a local UI is
   another. No other module talks to an external system directly.
3. **Producing and draining are two separate concerns, each behind its own toggle.**
   Producing an event (writing it to the bus) never depends on whether a drain is enabled,
   and a producer never knows which system a drain feeds. Today the code couples them: the
   fan-out functions check `drain_posture()` before any handler runs, and the hosted-posture
   contract (`kitty-specs/hosted-opt-in-drain-ledger-01M3FFEV/contracts/hosted-posture.md`)
   silences producers when drain is off. Decoupling them amends
   [ADR 2026-09-26-3](../adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md) and needs a 4.x
   ADR of its own.
4. **The charter may ship on its own.** Charter content that tells users to run the CLI is
   acceptable. The only strangler blocker is code coupling: `specify_cli` imports `charter`
   internals directly (129 files at `8a581be1`), and those imports must move onto a stable
   API (#645) before the charter can be packaged separately.

Theme 4 (Team Kitty enablers) is frozen, and the Stability and Maturity themes apply to the
**local** CLI only.

## Release posture

*Read 2026-10-06. Verify live state with `gh issue view <n> --repo spec-kitty/spec-kitty`
before acting; milestones and counts move between release candidates.*

**Five release candidates have shipped; rc6 is open on `main`.** PyPI upload dates: rc1
2026-09-13, rc2 09-14, rc3 09-17, rc4 09-21, rc5 10-02. `main` carries the unreleased
`4.0.0rc6` (`[Unreleased]` in [`CHANGELOG.md`](../../CHANGELOG.md), `version` in
`pyproject.toml`).

**rc5 shipped under a waiver.** The release workflow requires a green nightly on the release
commit (#5034). No nightly has been green since 2026-09-15, so on 2026-10-02 a `skip_nightly`
input was added to manual release runs and rc5 was published with the gate skipped and the
waiver logged. rc5 also carried defects in `consolidate`; their fixes are on `main` and reach
users only with rc6.

**The GA gate, [milestone 11](https://github.com/spec-kitty/spec-kitty/milestone/11):** 14 open,
210 closed (201 issues, 119 of them P0), due **2026-10-16**. Of the 16 issues open on
2026-10-01, every one except #5419 has closed. 58 issues closed on the milestone from
2026-10-01 to 2026-10-06, 29 of them P0.

The 14 open issues, by kind:

| Kind | Issues | Gates GA because |
| --- | --- | --- |
| Nightly | **#5419** (P0, performance suite) | The 2026-10-06 nightly passed 56 of 57 jobs; this is the one red. rc6 needs it green or another waiver. |
| Correctness residuals | #5638 (rollback leaves coordination status files dirty), #5704 (protected `single_branch` create leaves a scaffold without `meta.json`), #5726 (timing-dependent error code when `specify` re-runs) | P2 bugs in the landing and create paths. |
| Agent integration | #702 (P1, Codex `.agents/skills` drift) | The one open P1. |
| Docs | #5428 (P2) | Docs cleanup after the 4.x re-anchor; this re-synthesis is part of it. |
| Structural hygiene | #2560, #2561, #2562 (`runtime_bridge` strangler slices), #3732 (doctrine packs → charter packs rename), #4836 (doctrine→charter drift in operator surfaces), #5538 (residual kind-vocabulary mirror), #5629 (`tasks_move_task.py` split), #5715 (last CLI import in the lanes seam) | P2/P3 debt. Each is a candidate to move to CLI 4.x stable if it does not land by the due date. |

**Not on milestone 11, but raised as GA questions (2026-10-06):**

- **#5780** and **#5758** (P0, no milestone, no owner). `consolidate` and `agent action review`
  read only local branches, so a teammate's pushed rejection of a work package is ignored in a
  multi-clone team.
- **#5722** and **#5603** (P1, no milestone). `orchestrator-api consolidate-mission` has no
  reconciliation gate and no rollback, and it force-deletes the mission or coordination branch.
  Automation that lands work through the API does not get the protections `consolidate` has.

**Milestone routing.** Only milestone 11 gates GA.

- [**4.0.0 release scope**](https://github.com/spec-kitty/spec-kitty/milestone/11) (11): the GA
  gate.
- [**CLI 4.x stable**](https://github.com/spec-kitty/spec-kitty/milestone/12) (12): stable 4.x
  work after GA, including deferrals out of the gate (229 open).
- [**4.x Work**](https://github.com/spec-kitty/spec-kitty/milestone/8) (8): the former `4.0.0`
  milestone; hosted and product work planned beyond the stabilization release, including the
  frozen hosted lane (81 open).
- [**Infra & Enablers 4.x**](https://github.com/spec-kitty/spec-kitty/milestone/15) (15): CI,
  tooling and quality-debt work, including #1928 and the CI follow-ups #5652 and #5624 (76 open).
- [**Live Work NOW (post-launch)**](https://github.com/spec-kitty/spec-kitty/milestone/13) (13):
  five open, including the auth residual #2941.

## Drift since the declaration

The [4.0.0 declaration](../changelog/4.0.0.md) was written on 2026-09-04, two days before the
Convergence (#3881) retired the local sync transport and made this repository a **client** of
`spec-kitty/zeitgeist` and `spec-kitty/saas`
([ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md)),
and four weeks before hosted work was frozen. Every epic it names has since moved:

| Declared advance (2026-09-04) | State (2026-10-06) |
| --- | --- |
| **#1800** SaaS sync & event-envelope hardening | Closed. |
| **#1091** Team Kitty launch gate | Closed 2026-09-13 (milestone 3.2.7). |
| **#3322** CLI auth & token lifecycle | Closed; the client-side successor **#3892** is open on 4.x Work and frozen. |
| **#3549** event-log integrity | Closed; the local successor **#3893** is open on 4.x Work. |
| **#3278** P0 sync false success | Closed as not planned (the sync transport is gone). |
| **#3178** P0 wrong-authority egress | Closed as completed. |
| **#2519** charter authoring & lifecycle | Open on CLI 4.x stable. |
| **#2173** infrastructure-to-logic ports | Closed 2026-09-27 on milestone 11. |
| **#1619** one execution context | Open on CLI 4.x stable (31 of 44 sub-issues closed on 2026-10-01). |
| **#1797** degod / unshim delivery | Closed as not planned. |

Never design against or "re-enable" the old sync path; see
[`docs/context/team-kitty.md`](../context/team-kitty.md).

## The dependency spine

*Re-anchored 2026-10-06.*

```
   LOCAL INTEGRITY (the GA gate, milestone 11)
       green nightly (#5419, 1 of 57 jobs red) ───────────────┐
       landing + create residuals (#5638 #5704 #5726)         ├──▶  4.0.0 GA
       agent integration (#702) · docs (#5428)                │     (red CI == no release)
       structural hygiene (#2560-2 #3732 #4836 #5538 ...)     ┘     due 2026-10-16
       UNDECIDED: pushed-rejection P0s (#5780 #5758),
                  orchestrator-api gate + rollback (#5722 #5603)

   STRANGLER PREP (4.x line, does NOT gate GA)
       #645 stable application API  ──▶  charter imports move onto it  ──▶  charter ships alone
       #645 planned Java charter reads (4.x Work) · #2519 later Java writes (CLI 4.x stable)
       #5530 bundled dashboard removed (done)  ──▶  #5528 Mission Status Read API
         (contract 1.0 and 1.1 shipped)  ──▶  #5532 readers re-point · #5533 routes rehome
       produce / drain decoupling (ADR not yet written)  ──▶  adapter module as pub/sub seam
       #1619 one execution context (CLI 4.x stable)

   FROZEN (4.x Work, waits for the commercial review)
       #3892 zeitgeist-client auth · auth residual #2941 · Team Kitty launch work

   QUALITY DEBT (Infra & Enablers 4.x, OUTSIDE the blocking graph)
       #1928 ──▶ #4304 #4305 #2970 (security and BLOCKER findings still open)
```

**Reading order:**

1. **The nightly closes the release.** Every consolidation-safety and coordination-status P0
   that was open on 2026-10-01 has closed. #5419 is the only P0 left on the gate, and a green
   nightly is also what rc6 needs without a waiver.
2. **Two decisions sit outside the gate.** The pushed-rejection P0s (#5780, #5758) and the
   unguarded API landing path (#5722, #5603) are in the same "says success, did the wrong
   thing" class as the defects the cycle fixed. Either pull them onto milestone 11 or record
   why GA ships without them.
3. **Strangler prep is the 4.x structural work.** #645 is the precondition for shipping the
   charter separately; produce/drain decoupling is the precondition for any external consumer.
   The Mission Status Read API
   ([ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md),
   Proposed) is #645's read facet; the bundled dashboard is already removed (#5530), and the
   contract shipped as versions 1.0 and 1.1. The charter read/write service strangler
   ([ADR 2026-10-03-1](../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md),
   Proposed) starts only after callers move onto #645. None of this gates milestone 11.
4. **Hosted work is frozen, not cancelled.** Nothing on that lane is deleted; it waits.
5. **Quality debt is a standing campsite epic**, outside the blocking graph. It burns down
   per touched file and never gates a release candidate.

## Per-theme progress and scope

*State read 2026-10-06. An issue can serve more than one theme; it is listed under its primary
theme.*

### Theme 1 — Stability (local integrity)

**The bulk of the cycle, and nearly done for GA.** 119 of the 201 closed milestone-11 issues
were P0. The recurring defect was a command that exited 0 while it deleted, overwrote or
dropped something.

- **Landing work (`consolidate`).** Since rc5: canceled work no longer lands through a
  dependent lane (#5569); a resumed run no longer drops a lane (#5571); commits made after
  approval are refused until the work package is approved again (#5668,
  [ADR 2026-10-04-5](../adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md));
  a rollback keeps a teammate's commit (#5666); `--abort` reports what it could not restore
  (#5686); approved code missing from the target fails and rolls back (#5788). Before rc5:
  ignored local files are no longer overwritten or deleted (#5392, #5400) and every exit after
  the first mutation rolls back through one authority (#5385).
- **Workflow and coordination status.** Status and decision events no longer split between
  two checkouts (#5519, #5513, #5440); a work package prompt no longer contradicts
  `move-task` (#3931); a copied project no longer moves the original's cursor (#5390);
  `single_branch` missions have no lanes (#5100).
- **Open on the gate:** #5638, #5704, #5726 (P2).
- **Open off the gate:** #5780, #5758 (P0), #5722, #5603 (P1). See "Release posture".
- **Record:** the sync-era reliability items closed before 2026-09-14 (#3723, #3700, #2736,
  #2665, #2264 and others) belong to the retired transport.

**Progress:** heavy. The new behaviour adds refusals: a mission approved before rc5 stops at
`consolidate` with `APPROVAL_STAMP_MISSING` until each work package is reviewed again or
attested. The rc6 upgrade notes must say so.

### Theme 2 — Maturity (one honest local store, owned seams)

- **Done:** six of the largest modules were split after rc5 (`mission_finalize.py` 5,145 →
  1,454 lines, `consolidation/executor.py` 4,145 → 833, `orchestrator_api/commands.py` 4,097 →
  511, `tasks_move_task.py` 3,786 → 1,887, `cli/commands/implement.py` 2,304 → 443,
  `core/mission_creation.py` 2,173 → 742).
- **Open:** **#3893** (local event-log integrity, 4.x Work), #3887 (`doctor.py` residue, 4.x
  Work), and on the gate #5629 (finish the `tasks_move_task.py` split) and #2560–#2562
  (`runtime_bridge`).
- **Closed as not planned:** #2955 (the Team Kitty envelope producers it would have folded
  are frozen).

### Theme 3 — Extensibility (governed front door + stable API)

- **Open:** **#645** (stable application API, 4.x Work), **#901** (governed front door, 4.x
  Work), **#5528** (Mission Status Read API epic, no milestone), #5532 and #5533 (CLI 4.x
  stable).
- **Done:** the bundled dashboard is removed (#5530); the Mission Status contract shipped as
  versions 1.0 and 1.1, with lint, breaking-change checks and a test against every mission
  in the repository; teams can share agent commands as pack skills
  ([ADR 2026-09-27-1](../adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md));
  org packs carry their own built-in override sanction
  ([ADR 2026-10-05-3](../adr/4.x/2026-10-05-3-org-packs-ship-their-builtin-override-sanction.md)).
- **On the gate:** #3732 and #4836 (the doctrine → charter vocabulary), #5538.

**Progress:** the read facet of #645 has a contract; the API itself and the front door are
4.x-line work.

### Theme 4 — Team Kitty enablers (frozen)

**Frozen 2026-10-01.** Nothing here gates GA.

- **Open:** **#3892** (zeitgeist-client auth, 4.x Work), #2941 (widen bypasses renewable CLI
  auth, Live Work NOW), #4195 (review of the #4121 charter forward-port, 4.x Work).
- **Closed:** #1091, #3322, #3233, #3980, #3277, #1621.
- **Closed as not planned:** #3196, #3197, #3198 (sync consent and identity, retired with the
  transport), #2520 (charter events to SaaS; a hosted charter signal would need a new issue
  built on Zeitgeist).

### Cross-cutting — Sonar / quality debt

Parent **#1928** is on Infra & Enablers 4.x. The finding-class children #4299–#4303 were closed
as not planned (the charter's Sonar standing orders handle them per touched file), and #2969
was fixed.

| Issue | Finding class | State |
| --- | --- | --- |
| **#4304** | S6350 ×17 and other `src/` security findings | Open, P1 |
| **#4305** | S3516 constant-return BLOCKER in `core/file_lock.py` | Open, P1 |
| **#2970** | 4 BLOCKER S2083 path-injection findings (≥1 likely false positive) | Open, P2 |

**Progress:** deliberately post-GA. Adjudicate the security children before remediating, and
record false-positive rulings.

## Exit criteria for 4.0.0

*Re-anchored 2026-10-06.*

1. **Milestone 11 is closed.** Every issue on
   [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11) is closed or
   re-milestoned with a rationale.
2. **The nightly is green on the release commit.** Red CI means no release (charter Standing
   Order 9). A `skip_nightly` waiver is an operator decision, recorded each time; rc5 used one.
3. **The CLI never reports success while losing or stranding local work.** This is what the
   consolidation, status and workflow P0s test. #5780 and #5758 are in this class and need an
   explicit in-or-out decision.
4. **No new shadow path.** Every landing routes onto an existing authority. No re-introduction
   of the retired sync transport, and no module other than the adapter seam talks to an
   external system.
5. **(Post-GA) Strangler prep is dispositioned.** #645 (including the Mission Status Read API,
   #5528), the produce/drain decoupling and #901 land or are re-milestoned on the 4.x line with
   a rationale.
6. **(Post-GA) Security debt adjudicated.** #4304, #4305 and #2970 close or carry recorded
   false-positive rulings.

## Risks / watch items

- **rc5 is the newest release and has known landing defects.** Users get the fixes only with
  rc6. Four rc5 fixes were found not to hold one day after release; the window between a fix
  on `main` and a release is user exposure.
- **The nightly has not been green since 2026-09-15.** The 2026-10-06 run had one red job of
  57. Most reds came from suites only the nightly runs, which fell behind changes that merged
  green; the commit-recipe check now runs per PR (#5708), but the performance, Python 3.13 and
  integration suites have not moved. Tests that no CI job runs (#5652) hide pinned reds.
- **The release gate depends on a token.** It fails closed without
  `RELEASE_NIGHTLY_DISPATCH_TOKEN`; the new dedicated token's scope is not yet written down
  (see `RELEASE_CHECKLIST.md`).
- **The gate refills.** Milestone 11 went from 11 open (2026-09-30) to 16 (2026-10-01) to 14
  (2026-10-06) while 58 issues closed. 159 issues were opened in the four days after rc5
  against 90 closed, 33 of them new open P1s. The due date (2026-10-16) is the cut-off: new
  issues after it go to CLI 4.x stable unless an operator pulls them in.
- **Review depends on one person.** 60 of the 66 PRs merged after rc5 have one author.
- **The API landing path is unguarded.** `orchestrator-api consolidate-mission` lacks the
  reconciliation gate and rollback (#5722, #5603).
- **Client-repo inversion.** Auth and event work for the hosted path is authored upstream in
  `spec-kitty/zeitgeist` and `spec-kitty/saas`. A PR that edits a retired local-sync surface is
  designing against a dead subsystem; flag it.
- **`doctor.py` residue (#3887).** #1623 closed without shrinking the module; keep the
  follow-up tracked.

## Immediate next steps

1. **Green the nightly (#5419)**, then cut rc6 without a waiver.
2. **Decide #5780 and #5758**: on milestone 11, or GA ships without them with the reason
   recorded.
3. **Decide #5722 and #5603**: fix the API landing path for GA, or document that automation
   must use `consolidate` until it is.
4. **Hold the 2026-10-16 due date as the cut-off.** Move any P2/P3 hygiene item still open
   then to CLI 4.x stable with a one-line rationale.
5. **Write the produce/drain ADR** (4.x), amending ADR 2026-09-26-3, then split the toggles in
   `status/adapters.py` and `core/hosted_posture.py`.
6. **Move the `specify_cli` → `charter` imports onto #645** so the charter can ship on its
   own. Per [ADR 2026-09-30-1](../adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md),
   drain them rather than holding them in an allowlist.
7. **Ratify ADRs 2026-10-01-2 and 2026-10-03-1** (both Proposed).
8. **Re-run this synthesis at each rc bump.** Read
   `gh api repos/spec-kitty/spec-kitty/milestones/11` and the milestone's open issues before
   acting.

## Links

- Milestones: [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11) (GA
  gate) · [CLI 4.x stable](https://github.com/spec-kitty/spec-kitty/milestone/12) ·
  [4.x Work](https://github.com/spec-kitty/spec-kitty/milestone/8) ·
  [Infra & Enablers 4.x](https://github.com/spec-kitty/spec-kitty/milestone/15)
- Declaration of intent: [`4.0.0.md`](../changelog/4.0.0.md) · Convention:
  [`release-goals.md`](../changelog/release-goals.md) · Summary:
  [4.x Executive Overview](4-x-executive-overview.md)
- Prior cycle roadmap: [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md)
- Convergence / client-repo inversion:
  [ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md) ·
  hosted context: [`docs/context/team-kitty.md`](../context/team-kitty.md)
- Durable domain plans: [Doctrine & Charter](domains/doctrine-charter-domain-plan.md) ·
  [API & Dashboard](domains/api-dashboard-domain-plan.md)
