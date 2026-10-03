---
title: 4.0.0 Milestone — Roadmap
description: 'Roadmap for the 4.0.0 cycle: the 2026-10-01 direction update (hosted work off the critical path), dependency spine, exit criteria and watch items.'
doc_status: active
type: explanation
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-03'
related:
- docs/changelog/4.0.0.md
- docs/changelog/index.md
- docs/plans/index.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/plans/code-quality/index.md
- docs/changelog/release-goals.md
---
# 4.0.0 Milestone — Roadmap

*Planner synthesis (planner-priti), 2026-09-14; release posture and milestone routing
refreshed 2026-09-30 (see "Release posture" below). Sources: the then-`4.0.0` milestone
(GitHub milestone 8, since renamed **4.x Work**) census read on 2026-09-14
(`gh issue list --repo spec-kitty/spec-kitty --milestone 4.0.0 --state all` — 88 issues
milestoned, 66 closed / 22 open, ~75% burn), the durable declaration of intent in
[`4.0.0.md`](../changelog/4.0.0.md), the operator-stated goal themes for the cycle, and the
convergence-retirement / client-repo-inversion ADR
[`2026-09-06-1`](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
This roadmap is the authority for the **active** 4.0.0 cycle; the prior
[3.2.x milestone roadmap](3-2-x-milestone-roadmap.md) is re-anchored to point here (see its
[Addendum 2026-09-14](3-2-x-milestone-roadmap.md#addendum-2026-09-14--4x-is-now-the-active-cycle-authority-moved)).*

## Intent of 4.0.0

4.0.0 is the **hosted-collaboration + structural-finish** cycle. Its durable declaration of
intent — [`4.0.0.md`](../changelog/4.0.0.md) — framed two goals: **G1 hosted collaboration
(Team Kitty)** and **G2 next-generation product capabilities**, with **G3 the open-core
structural strangler finish** committed to the cycle by operator decision (2026-09-04). This
roadmap executes that declaration against the **live** tracker, organised around the four
**operator-stated goal themes** for the cycle:

1. **Stability** — the hosted and local paths never report success while state is stranded;
   failures are named, not swallowed; the reliability book burns down.
2. **Maturity** — one canonical event store, honestly reported and delivered without silent
   loss; the post-convergence client surfaces settle onto their authoritative upstreams.
3. **Extensibility** — a governed front door and a stable, versioned application API so the
   CLI/UI/MCP/SDK consumers build against one surface, not four ad-hoc ones.
4. **Team Kitty enablers** — auth that stays authenticated and fails legibly, launch defaults,
   and the consent/identity boundary that make hosted collaboration trustworthy.

Same discipline as the prior cycles: **no new shadow paths** — route or extract onto an
existing authority, never build a parallel one.

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

The goal themes below keep their numbering. Theme 4 (Team Kitty enablers) is frozen, and the
"Stability" and "Maturity" themes now apply to the **local** CLI only.

## Release posture

**4.0.0 is at rc-stage.** Release candidates rc1–rc4 are tagged (rc1 2026-09-13, rc2 09-14,
rc3 09-15, rc4 09-21), and the next rc is open on `main`: see the `[Unreleased]` heading in
[`CHANGELOG.md`](../../CHANGELOG.md) and `version` in `pyproject.toml` for the open rc rather
than trusting a number written here.

**Milestone routing changed after this roadmap was written (read 2026-09-30).** The tracker
now separates the GA gate from the wider 4.x line:

- [**4.0.0 release scope**](https://github.com/spec-kitty/spec-kitty/milestone/11) is the GA
  gate: the issues that must close before a non-rc `4.0.0` ships.
- [**CLI 4.x stable**](https://github.com/spec-kitty/spec-kitty/milestone/12) is stable 4.x
  work after the 4.0.0 launch walkthroughs pass. Post-4.0.0 deferrals land here.
- [**4.x Work**](https://github.com/spec-kitty/spec-kitty/milestone/8) (the former `4.0.0`
  milestone this roadmap was built from) now holds hosted-collaboration and product work
  planned beyond the stabilization release. Being on it does not make an issue a GA blocker.

Two consequences for the rest of this page. First, **#3892 and #3893 are on 4.x Work**, so they
no longer gate GA as the "release-blocking tail" below assumed. Second, the burn-down counts
below are the **2026-09-14** census of the old milestone and are kept as a record; use the live
milestone pages above for current counts. A full re-synthesis against milestone 11 is still
owed (see "Immediate next steps", item 5).

**Snapshot as of 2026-09-14 (kept as a record).** At that point the old milestone was ~76%
burned (66 closed / 22 open of 88 milestoned), and the hosted-collaboration and reliability
body had substantially landed: the bulk of the closed book was the (now-retired)
sync-transport, auth and event reliability cluster (see per-theme progress below).

As of 2026-09-14, what remained open split into two lanes:

- **Release-blocking tail** — a small set of P1 correctness residuals on the hosted/auth
  paths (#3178, #3233, #2941, #3279) plus the two open post-convergence integrity epics
  (#3893, #3892). These gate the rc→GA decision.
- **Post-rc structural / debt tail** — the extensibility epics (#901 governed front door,
  #645 stable application API) and the Sonar / quality debt series (parent #1928; children
  #4299–#4305 plus #2969 and #2970, one per Sonar finding class, listed in the table below). This is the **structural-finish
  half** that rides *behind* the release candidates: it improves the foundation for the 4.x line
  without gating the 4.0.0 GA tag. Frame it as a post-rc tail, not a pre-rc blocker.

> **Verify live state** via `gh issue view <n> --repo spec-kitty/spec-kitty` before acting;
> milestone numbers move between rcs. Where this roadmap and the
> [4.0.0 declaration](../changelog/4.0.0.md) disagree on which epic carries the cycle, the
> **live tracker wins** — the declaration is a 2026-09-04 snapshot written before the
> convergence re-homed several epics (see "Drift since the declaration", below).

## Drift since the declaration (convergence re-homing)

The [4.0.0 declaration](../changelog/4.0.0.md) was written on 2026-09-04, **two days before**
the Convergence (#3881) retired the local sync transport and inverted the hosted surfaces to
consume upstream client repos
([ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md)).
Several declared advances have since moved. Read the declaration for the durable "why"; read
this table for the live "what carries the cycle":

| Declared advance (2026-09-04) | State (2026-09-14; rows re-checked 2026-09-30) | Note |
|---|---|---|
| **#1800** SaaS sync & event-envelope hardening | **CLOSED**, de-milestoned | Delivered; the reliability cluster it parented is closed. |
| **#1091** Team Kitty launch gate | **CLOSED** 2026-09-13 | Launch-gate work landed, milestoned to `3.2.7` (released 2026-09-10, the last 3.x release). |
| **#3322** CLI auth & token-lifecycle reliability | **CLOSED** under 4.0.0 | Superseded client-side by **#3892** (zeitgeist-client auth). |
| **#3549** event-log integrity | **CLOSED** under 4.0.0 | Superseded client-side by **#3893** (local event-log integrity). |
| **#2519** charter authoring & lifecycle | **OPEN**, on **CLI 4.x stable** | Not a GA blocker; stable-4.x work. |
| **#2173** infra-to-logic ports | **CLOSED** 2026-09-27 under **4.0.0 release scope** | All six children closed. |

**The pattern is client-repo inversion.** The original hosted epics (#1800/#1091/#3322/#3549)
were authored when this repo *owned* the sync transport. Post-convergence, this repo is a
**client** of `spec-kitty/zeitgeist` + `spec-kitty/saas`; the residual 4.0.0 work is therefore
the **client-side** integrity that this repo still owns — **#3892** (the CLI stays
authenticated against the zeitgeist client) and **#3893** (one honest local event store) — not
the retired server-side transport. Never design against or "re-enable" the old sync path; see
[`docs/context/team-kitty.md`](../context/team-kitty.md).

## The dependency spine

*Re-anchored 2026-10-01 (see the direction update above). The 2026-09-14 spine named
client auth (#3892) and the auth P1 cluster as the release-blocking tail; under the freeze
they no longer gate GA.*

```
   LOCAL INTEGRITY (the GA gate, milestone 11)
       consolidate data safety (#5392 #5400 #5385 #5440) ──┐
       workflow + coordination-status correctness          ├──▶  4.0.0 GA
         (#3931 #5390 #5409 #5513 #5519)                   │     (red CI == no release)
       green nightly (#5258 #5418 #5419 #5505 #5506 #5507) ┘

   STRANGLER PREP (4.x line, does NOT gate GA)
       #645 stable application API  ──▶  charter imports move onto it  ──▶  charter ships alone
       #645 planned Java charter reads (4.x Work) · #2519 later Java writes (CLI 4.x stable)
       #5530 bundled dashboard removed FIRST  ──▶  #5528 mission status read API  ──▶
         #5532 readers re-point · #5533 routes rehome  (external UI consumes the API)
       produce / drain decoupling    ──▶  adapter module as pub/sub seam ──▶  external UI and
                                                                              other consumers
       #1619 one execution context (CLI 4.x stable)

   FROZEN (4.x Work, waits for the commercial review)
       #3892 zeitgeist-client auth · auth P1 residuals (#3233 #2941) · Team Kitty launch work

   QUALITY DEBT (standing, OUTSIDE the blocking graph — campsite epic)
       #1928 ──▶ #4299–#4305 (+ #2969 #2970)   the Sonar/ruff/mypy backlog
```

**Reading order:**

1. **Local integrity closes the release.** Milestone 11 is all local CLI work: consolidation
   data safety, workflow and coordination-status correctness, and a green nightly. Four of
   the open P0s (#3931, #5440, #5513, #5519) are coordination-topology status bugs, the
   class #1619 exists to remove; watch whether that class keeps refilling the gate.
2. **Strangler prep is the 4.x structural work.** #645 is the precondition for shipping the
   charter separately; produce/drain decoupling is the precondition for any external
   consumer, hosted or local. The Mission Status Read API ([ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md), proposed) is
   #645's read facet. It gives an external UI an overview and a detail view of mission
   status. By operator decision (2026-10-01) the CLI-bundled dashboard is deleted first
   (#5530); the read API (#5528), reader re-pointing (#5532) and route rehoming (#5533)
   continue afterwards as the replacement read path.
   It is a pull over the committed ledger, so it does not wait for produce/drain
   decoupling.
   The separate charter strangler moves production reads to a planned Java service under
   #645 / 4.x Work. It starts only after callers move onto the #645 stable application API,
   because `specify_cli`, `runtime`, and `glossary` import charter internals directly today.
   Java writes move one operation at a time and remain #2519 / CLI 4.x stable.
   Neither gates milestone 11. See
   [ADR 2026-10-03-1](../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md).
3. **Hosted work is frozen, not cancelled.** Nothing on that lane is deleted; it waits.
4. **Quality debt is a standing campsite epic**, deliberately outside the blocking graph
   (same pattern as 3.2.x's #1931). It burns down opportunistically per touched file; it
   never gates a release candidate.

## Per-theme progress and scope

Counts are the 2026-09-14 milestone census. An issue can serve more than one theme; it is
listed under its primary theme.

### Theme 1 — Stability (reliability, honest reporting)

**The largest closed cluster of the cycle.** The reliability book for auth, events and the
(now-retired) sync transport has substantially burned down.

- **Closed (representative; many concern the since-retired sync transport):** #3723 (every
  status line names its failure instead of reporting success while failing), #3700
  (gate-blocked sync no longer exits 0), #3699 (sync-share first
  invocation traceback), #2736 (one invalid event no longer poisons its whole batch), #2665
  (silent daemon death → weeks of halted auto-sync), #2264 (status must not report success blind
  to remote), #3018 (protocol-version handshake), #3714/#3582/#3581/#3329 (import-history
  diagnostics + preflight honesty), #3001/#3000/#2999 (historical-event rejection classes).
- **Open (release-blocking tail, as of 2026-09-14; re-checked 2026-09-30: #3178 closed as
  completed, #3279 closed as not planned, #2941 still open, #3233 to verify):** **#3178** (P1 — decision-widen resolves the destination
  team from env before the per-project auth file; FR-007 not discharged by FR-002),
  **#3233** (token refresh reports "you sent no credential" as an unexplained failure),
  **#2941** (widen bypasses renewable CLI auth), **#3279** (P1 — device authorization gets 401
  after browser approval).
- **Open (non-blocking hygiene):** #4248 (SonarCloud PR scans cannot resolve current PRs),
  #3887 (`doctor.py` still a 1,456-LOC god-module — #1623 closed but the split did not shrink it).

**Progress:** heavy — the P0/P1 reliability spine is closed; a short P1 residual list remains
on the auth/consent boundary.

### Theme 2 — Maturity (one honest event store, post-convergence settle)

- **Closed:** **#3549** (Epic: event-log integrity — one canonical store, honestly reported),
  **#1800** (SaaS sync & event-envelope hardening), #2750 (retire the legacy `queue.db` write
  path so the journal is the sole sink), #617 (MissionAudit / operator-override event families),
  #3021 (resolved-binding fan-out handler registered in production).
- **Open:** **#3893** (Epic: **local** event-log integrity — the client-side successor to the
  retired #3549, one canonical store honestly reported), **#2955** (fold the two live-path Team
  Kitty envelope producers onto the canonical envelope owner — 3× `schema_version`),
  **#2970** (adjudicate the 5 BLOCKER S2083 path-injection findings; ≥1 likely false positive,
  naive fix breaks the git merge-driver contract).

**Progress:** the server-side envelope/store epic (#3549/#1800) is closed; the open work is the
**client-side** re-expression (#3893) plus envelope-owner consolidation (#2955). This is the
convergence-settle lane.

### Theme 3 — Extensibility (governed front door + stable API)

- **Open:** **#645** (Epic: Stable Application API Surface — UI / CLI / MCP / SDK — one
  versioned surface all four consumers build against), **#901** (Epic: Spec Kitty 4.0 central
  `/spec-kitty` governed front door).
- **Direction (2026-10-01):** #645's read facet is the **Mission Status Read API**, which
  has an overview and a detail granularity. The CLI-bundled dashboard is deleted
  first (#5530, operator decision 2026-10-01); the read API (#5528), reader re-pointing
  (#5532) and route rehoming (#5533) follow, and a replacement UI is built in its own
  repository ([ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md), proposed). Removing it also closes the dashboard daemon defects
  (#4520, #4767–#4769).
- **Closed:** #3837 (orchestrator-api design-phase verbs: specify/plan/tasks/analyze +
  decision resolution).

**Progress:** early — both epics are open and both are **post-rc structural tail**, not GA
blockers. They are the 4.x-line foundation; #645 is now on the **4.x Work** milestone. (Of the
former extensibility-adjacent epics, #2519 charter-authoring is on **CLI 4.x stable** and #2173
infra-ports closed on 2026-09-27; see "Drift since the declaration".)

### Theme 4 — Team Kitty enablers (auth, launch, consent/identity)

**Frozen 2026-10-01.** Kept as a record; nothing in this theme gates 4.0.0 GA (see the
direction update above).

- **Closed:** **#1091** (Team Kitty launch gate, closed 2026-09-13), **#3322** (CLI auth &
  token-lifecycle reliability epic), #3980 (launch defaults: flip
  `SPEC_KITTY_ENABLE_SAAS_SYNC` / `SPEC_KITTY_SAAS_URL`), #3277 (non-interactive machine
  authentication for hosted CI, originally filed against the sync transport), #1621 (flip CLI
  workspace launch defaults), #3196/#3197/#3198 (consent + identity resolution: consent writes,
  envelope→project_uuid resolvers, withheld-events bug).
- **Closed as not planned:** #2520 (charter domain events `CharterCreated`/`CharterUpdated` to
  SaaS). It was dropped when the sync transport was torn down, and no charter event is emitted
  today; a hosted charter signal would need a new issue built on Zeitgeist (see #2519).
- **Open:** **#3892** (Epic: zeitgeist-client auth & token-lifecycle reliability — CLI stays
  authenticated, fails legibly), **#4195** (review the #4121 charter/doctrine forward-port for
  convergence fit). The auth P1 residuals #3233/#2941/#3279 (listed under Stability) are also
  Team-Kitty-facing.

**Progress:** heavy — launch-gate, machine-auth, launch-defaults, and the consent/identity
boundary are closed; the open epic is the post-convergence **client** auth-lifecycle (#3892).

### Cross-cutting — Sonar / quality debt (standing campsite epic)

Parent **#1928** (in Product backlog); its **4.0.0-milestoned children** are the live series:

| Issue | Finding class | Priority |
|---|---|---|
| **#4299** | S3776 cognitive complexity >15 across 412 `src/` functions | P2 |
| **#4300** | S1192 hoist 141 duplicated literals to named constants | P2 |
| **#4301** | S5713 / S8572 exception & logging hygiene | P2 |
| **#4302** | S7632 / S5886 suppression-comment & type-hint correctness | P2 |
| **#4303** | S1172 / S3358 / S107 / S1135 / S117 / S1481 structural & signature smells | P3 |
| **#4304** | S6350 ×17 + S2612/S5443/S5145/S6418 `src/` security findings | P1 |
| **#4305** | S3516 / S5863 / JS S2871 BUG-type findings (one BLOCKER) | P1 |
| **#2969** | four production asserts swallowed by their own try/except (S5779) | P2 |
| **#2970** | 5 BLOCKER S2083 path-injection (≥1 likely false positive) | P2 |

**Progress:** early and deliberately **post-rc**. Treat these as code-shaping constraints during
touched-file work (per the charter's Sonar standing orders), not a release gate. The security
children (#4304, #2970) are the highest-value slices and can land independent of any theme.

## Exit criteria for 4.0.0

*Re-anchored 2026-10-01. The 2026-09-14 criteria for hosted auth (#3892 and the P1 cluster)
and the consent/identity boundary are no longer GA criteria; they move with Theme 4 to the
frozen hosted lane.*

1. **Milestone 11 is closed.** Every issue on
   [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11) is closed or
   explicitly re-milestoned with a rationale.
2. **Main and the nightly are green.** Red CI means no release (charter Standing Order 9).
3. **The CLI never reports success while losing or stranding local work.** This is what the
   consolidation, status and workflow P0s on milestone 11 test.
4. **No new shadow path.** Every landing routes onto an existing authority. No
   re-introduction of the retired sync transport, and no module other than the adapter seam
   talks to an external system.
5. **(Post-rc) Strangler prep is dispositioned.** #645 (stable API, including the Mission
   Status Read API, #5528, which follows the already-first dashboard removal, #5530), the produce/drain decoupling, and #901
   (governed front door) either land or are re-milestoned to the 4.x line with rationale.
6. **(Post-rc) Quality-debt series dispositioned.** #1928's 4.0.0 children (#4299–#4305, #2969,
   #2970) are burned down or explicitly re-milestoned; the security children (#4304, #2970)
   close or are adjudicated (false-positive rulings recorded).

## Risks / watch items

- **Declaration ↔ tracker drift is real, not hypothetical.** The
  [4.0.0 declaration](../changelog/4.0.0.md) predates the Convergence by two days and still
  names #1800/#1091/#3322/#3549/#2519/#2173 as live advances; as of 2026-09-30 five are closed
  and #2519 is on CLI 4.x stable (see "Drift since the declaration"). Anchor every status claim to the **live** milestone
  read and the client-side successor epics (#3892, #3893), never to the declaration's committed-
  scope table.
- **Client-repo inversion changes where auth/event work lands.** Post-convergence this repo is a
  **consumer** of `spec-kitty/zeitgeist` + `spec-kitty/saas`. #3892/#3893 are the *client-side*
  residuals; the *server/transport* side is authored **upstream**, not here. A PR that tries to
  fix the hosted path by editing a retired local-sync surface is designing against a dead
  subsystem — flag it. See [`docs/context/team-kitty.md`](../context/team-kitty.md) and
  [ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
- **rc-tail scope discipline.** The structural/debt half (#645, #901, #1928 children) is
  explicitly a **post-rc tail**. The risk is scope-creeping it into the GA gate and delaying a
  release that is otherwise ready. Keep the GA criteria (1–4) separate from the structural
  criteria (5–6); a post-rc emergent patch is the right vehicle for the tail
  ([emergent-milestone model](../changelog/release-goals.md)).
- **The GA gate refills.** Milestone 11 went from 11 open (2026-09-30) to 16 open
  (2026-10-01), mostly new coordination-status and nightly P0s. Set a dated cut-off, and
  decide whether the coordination-topology class is fixed bug by bug or by pulling #1619
  forward.
- **The auth P1 cluster is frozen, not fixed.** #3233 / #2941 (and #3279, closed as not
  planned) were the 2026-09-14 GA blockers. They no longer gate GA, but they return as a
  coupled cluster on the consent/identity and refresh boundary when hosted work restarts.
- **Sonar security children over-priority vs the rest.** #4304 (S6350 ×17 subprocess +
  path-traversal) and #2970 (5 BLOCKER S2083) dominate the failing quality gate but carry
  false-positive risk (#2970 explicitly notes ≥1 false positive and that a naive fix breaks the
  git merge-driver contract). Adjudicate before remediating; record false-positive rulings so a
  later agent does not re-chase them (charter Sonar standing order).
- **`doctor.py` god-module residual (#3887).** #1623 was closed but the split did not reduce the
  1,456-LOC module — a closed-but-not-delivered pattern. Watch that its re-open is tracked and
  not silently re-absorbed as "done".

## Immediate next steps

1. **Burn down milestone 11** — consolidation data safety, workflow and coordination-status
   correctness, and the nightly reds (exit criteria 1–3).
2. **Set a dated cut-off for milestone 11**, so new P0s after it go to CLI 4.x stable unless
   an operator pulls them in.
3. **Write the produce/drain ADR** (4.x), amending ADR 2026-09-26-3, then split the toggles in
   `status/adapters.py` and `core/hosted_posture.py`.
4. **Inventory the `specify_cli` → `charter` imports** against #645 and set a shrink-only
   ratchet on them, so the charter can ship on its own.
5. **Ratify [ADR 2026-10-01-2](../adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md)** (name, transport, order of work). The dashboard is deleted first
   (#5530); the read API (#5528), reader re-pointing (#5532) and route rehoming (#5533)
   are filed under #645 and follow it. The deletion moots the interim mitigation for #4767
   and #4769. None of this gates GA.
6. **Hold #901 and the #1928 debt series on the post-rc tail.**
7. **Re-run this synthesis at each rc bump** — verify the open book against a fresh
   `gh issue list --repo spec-kitty/spec-kitty --milestone "4.0.0 release scope" --state all`
   before acting.

## Links

- Milestones: [4.0.0 release scope](https://github.com/spec-kitty/spec-kitty/milestone/11) (GA
  gate) · [CLI 4.x stable](https://github.com/spec-kitty/spec-kitty/milestone/12) ·
  [4.x Work](https://github.com/spec-kitty/spec-kitty/milestone/8) ·
  Declaration of intent: [`4.0.0.md`](../changelog/4.0.0.md) · Convention:
  [`release-goals.md`](../changelog/release-goals.md)
- Prior cycle roadmap (re-anchored here): [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md)
- Convergence / client-repo inversion:
  [ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md) ·
  hosted context: [`docs/context/team-kitty.md`](../context/team-kitty.md)
- Durable domain plans: [Doctrine & Charter](domains/doctrine-charter-domain-plan.md) ·
  [API & Dashboard](domains/api-dashboard-domain-plan.md)
