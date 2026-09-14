---
title: 4.0.0 Milestone — Roadmap
description: 'Roadmap for the active 4.0.0 cycle: four goal themes, the epic dependency spine, per-theme progress and exit criteria, and watch items through the post-rc structural tail.'
doc_status: active
type: explanation
audience: docs/context/audience/internal/maintainer.md
updated: '2026-09-14'
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

*Planner synthesis (planner-priti), 2026-09-14. Sources: the live milestone
[`4.0.0`](https://github.com/spec-kitty/spec-kitty/milestone/8) census read on 2026-09-14
(`gh issue list --repo spec-kitty/spec-kitty --milestone 4.0.0 --state all` — 88 issues
milestoned, 66 closed / 22 open, ~75% burn), the durable declaration of intent in
[`4.0.0.md`](../changelog/4.0.0.md), the operator-stated goal themes for the cycle, and the
convergence-retirement / client-repo-inversion ADR
[`2026-09-06-1`](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
This roadmap is the authority for the **active** 4.0.0 cycle; the prior
[3.2.x milestone roadmap](3-2-x-milestone-roadmap.md) is re-anchored to point here (see its
[Addendum 2026-09-14](3-2-x-milestone-roadmap.md#addendum-2026-09-14--40x-is-now-the-active-cycle-authority-moved)).*

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

## Release posture (2026-09-14)

**4.0.0 is near release.** The cycle is at **rc-stage** — rc2 and rc3 are tagged, and the
`4.0.0rc3` development cycle is open on `main` (commit
[`7e28431798`](https://github.com/spec-kitty/spec-kitty/commit/7e28431798), #4313). The
milestone is **~76% burned** (66 closed / 22 open of 88 milestoned). The **hosted-collaboration
and reliability body has substantially landed** — the bulk of the closed book is the
sync/auth/event reliability cluster (see per-theme progress below).

What remains open splits cleanly into two lanes:

- **Release-blocking tail** — a small set of P1 correctness residuals on the hosted/auth
  paths (#3178, #3233, #2941, #3279) plus the two open post-convergence integrity epics
  (#3893, #3892). These gate the rc→GA decision.
- **Post-rc structural / debt tail** — the extensibility epics (#901, #645) and the Sonar /
  quality debt series (#1928 → #4299–#4305, plus #2969, #2970). This is the **structural-finish
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

| Declared advance (2026-09-04) | Live state (2026-09-14) | Note |
|---|---|---|
| **#1800** SaaS sync & event-envelope hardening | **CLOSED**, de-milestoned | Delivered; the reliability cluster it parented is closed. |
| **#1091** Team Kitty launch gate | **CLOSED**, moved to **3.2.7** | Launch-gate work landed and re-milestoned to the stabilization tail. |
| **#3322** CLI auth & token-lifecycle reliability | **CLOSED** under 4.0.0 | Superseded client-side by **#3892** (zeitgeist-client auth). |
| **#3549** event-log integrity | **CLOSED** under 4.0.0 | Superseded client-side by **#3893** (local event-log integrity). |
| **#2519** charter authoring & lifecycle | **OPEN**, moved to **3.2.7** | No longer a 4.0.0-milestoned advance; tracked on the stabilization tail. |
| **#2173** infra-to-logic ports | **OPEN**, moved to **3.2.7** | Same — the ports work re-homed off 4.0.0. |

**The pattern is client-repo inversion.** The original hosted epics (#1800/#1091/#3322/#3549)
were authored when this repo *owned* the sync transport. Post-convergence, this repo is a
**client** of `spec-kitty/zeitgeist` + `spec-kitty/saas`; the residual 4.0.0 work is therefore
the **client-side** integrity that this repo still owns — **#3892** (the CLI stays
authenticated against the zeitgeist client) and **#3893** (one honest local event store) — not
the retired server-side transport. Never design against or "re-enable" the old sync path; see
[`docs/context/team-kitty.md`](../context/team-kitty.md).

## The dependency spine

The 4.0.0 spine is **shallow and mostly discharged** — unlike the 3.2.x degod spine, most of
the hosted-collaboration blocking work has already landed. What remains is two open integrity
epics feeding the release decision, and two independent extensibility epics that ride the
post-rc tail:

```
   POST-CONVERGENCE CLIENT INTEGRITY (release-blocking tail)
       #3892 zeitgeist-client auth  ──┐
                                       ├──▶  4.0.0 GA readiness decision
       #3893 local event-log integ. ──┘        (auth stays authenticated +
       + P1 residuals #3178/#3233/            one honest event store)
         #2941/#3279

   EXTENSIBILITY (post-rc structural tail — does NOT gate GA)
       #645 stable application API surface  ──▶  the 4.x consumer contract
       #901 governed /spec-kitty front door ──▶  (UI/CLI/MCP/SDK build against one surface)

   QUALITY DEBT (standing, OUTSIDE the blocking graph — campsite epic)
       #1928 ──▶ #4299–#4305 (+ #2969 #2970)   the Sonar/ruff/mypy backlog
```

**Reading order:**

1. **Client integrity closes the release.** #3892 (auth) and #3893 (event-log) are the two
   open epics that carry the Team Kitty and Maturity themes across the GA line, alongside the
   handful of P1 correctness residuals still open on the hosted/auth path (#3178 wrong-authority
   egress, #3233 unexplained refresh failure, #2941 widen-bypasses-auth, #3279 device-auth 401).
2. **Extensibility is deliberately off the GA path.** #645 (stable API surface) and #901
   (governed front door) are net-new product surface, not stabilization; they are the intended
   landing zone for the 4.x line and ride the post-rc tail.
3. **Quality debt is a standing campsite epic**, deliberately outside the blocking graph
   (same pattern as 3.2.x's #1931). It burns down opportunistically per touched file; it never
   gates a release candidate.

## Per-theme progress and scope

Counts are the 2026-09-14 milestone census. An issue can serve more than one theme; it is
listed under its primary theme.

### Theme 1 — Stability (reliability, honest reporting)

**The largest closed cluster of the cycle.** The sync/auth reliability book has substantially
burned down.

- **Closed (representative):** #3723 (every status line names its failure instead of reporting
  success while failing), #3700 (gate-blocked sync no longer exits 0), #3699 (sync-share first
  invocation traceback), #2736 (one invalid event no longer poisons its whole batch), #2665
  (silent daemon death → weeks of halted auto-sync), #2264 (status must not report success blind
  to remote), #3018 (protocol-version handshake), #3714/#3582/#3581/#3329 (import-history
  diagnostics + preflight honesty), #3001/#3000/#2999 (historical-event rejection classes).
- **Open (release-blocking tail):** **#3178** (P1 — decision-widen resolves the destination
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
- **Closed:** #3837 (orchestrator-api design-phase verbs: specify/plan/tasks/analyze +
  decision resolution).

**Progress:** early — both epics are open and both are **post-rc structural tail**, not GA
blockers. They are the 4.x-line foundation. (The former extensibility-adjacent epics #2519
charter-authoring and #2173 infra-ports have re-homed to the **3.2.7** stabilization tail and no
longer carry 4.0.0 — see "Drift since the declaration".)

### Theme 4 — Team Kitty enablers (auth, launch, consent/identity)

- **Closed:** **#1091** (Team Kitty launch gate — re-milestoned to 3.2.7), **#3322** (CLI auth &
  token-lifecycle reliability epic), #3980 (launch defaults: flip
  `SPEC_KITTY_ENABLE_SAAS_SYNC` / `SPEC_KITTY_SAAS_URL`), #3277 (non-interactive machine
  authentication for hosted sync/CI), #1621 (flip CLI workspace launch defaults), #2520 (charter
  domain events `CharterCreated`/`CharterUpdated` to SaaS), #3196/#3197/#3198 (consent + identity
  resolution: consent writes, envelope→project_uuid resolvers, withheld-events bug).
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

Derived from the [declaration's success criteria](../changelog/4.0.0.md#success-criteria-placeholder--refine-when-the-cycle-activates)
and the live epic done-conditions. The GA-blocking criteria (1–4) gate the rc→GA decision; the
structural criteria (5–6) may land in a post-rc emergent patch.

1. **Auth stays authenticated (Team Kitty / Stability).** #3892 discharged: the CLI stays
   authenticated against the zeitgeist client across human (browser-mediated) and machine/CI
   paths; refresh failures are diagnosed by name — the P1 residuals #3233 / #2941 / #3279 are
   closed.
2. **Consent/identity boundary enforced, not instructed (Stability).** #3178 closed — the
   destination team resolves from the per-project auth file, not env-first; no wrong-authority
   egress.
3. **One honest event store (Maturity).** #3893 discharged: a single canonical **local** event
   store, honestly reported, delivered without silent loss; #2955's triple envelope producer
   folded onto the canonical owner.
4. **No new shadow path.** Every landing in the cycle routed onto an existing authority (the
   zeitgeist/saas clients, the canonical event store) — no re-introduction of the retired sync
   transport, no parallel envelope owner.
5. **(Post-rc) Extensibility surface exists or is explicitly re-dispositioned.** #645 (stable
   API) and #901 (governed front door) either land, or are re-milestoned to the 4.x line with
   rationale — no epic left implicitly "cycle work" while off a release (the 3.2.x
   exit-criterion-8 anti-drift lesson).
6. **(Post-rc) Quality-debt series dispositioned.** #1928's 4.0.0 children (#4299–#4305, #2969,
   #2970) are burned down or explicitly re-milestoned; the security children (#4304, #2970)
   close or are adjudicated (false-positive rulings recorded).

## Risks / watch items

- **Declaration ↔ tracker drift is real, not hypothetical.** The
  [4.0.0 declaration](../changelog/4.0.0.md) predates the Convergence by two days and still
  names #1800/#1091/#3322/#3549/#2519/#2173 as live advances; four are closed and two moved to
  3.2.7 (see "Drift since the declaration"). Anchor every status claim to the **live** milestone
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
- **Auth P1 residual cluster is the true GA blocker.** #3178 / #3233 / #2941 / #3279 are small
  but load-bearing — they are the difference between "auth mostly works" and "auth stays
  authenticated and fails legibly" (exit criterion 1). Treat them as one coupled cluster on the
  consent/identity + refresh boundary, not four independent bugs.
- **Sonar security children over-priority vs the rest.** #4304 (S6350 ×17 subprocess +
  path-traversal) and #2970 (5 BLOCKER S2083) dominate the failing quality gate but carry
  false-positive risk (#2970 explicitly notes ≥1 false positive and that a naive fix breaks the
  git merge-driver contract). Adjudicate before remediating; record false-positive rulings so a
  later agent does not re-chase them (charter Sonar standing order).
- **`doctor.py` god-module residual (#3887).** #1623 was closed but the split did not reduce the
  1,456-LOC module — a closed-but-not-delivered pattern. Watch that its re-open is tracked and
  not silently re-absorbed as "done".

## Immediate next steps

1. **Close the auth P1 cluster** (#3178 / #3233 / #2941 / #3279) — the GA-blocking residuals on
   the consent/identity + refresh boundary (exit criteria 1–2).
2. **Land the two client-integrity epics** — #3892 (zeitgeist-client auth) and #3893 (local
   event-log integrity) — the client-side successors that carry the Team Kitty + Maturity themes
   across the GA line (exit criteria 1, 3).
3. **Fold #2955** (triple envelope producer → canonical owner) into the #3893 work rather than
   tracking it as a standalone drift (exit criterion 3).
4. **Hold #645 / #901 and the #1928 debt series on the post-rc tail** — do not let them gate the
   rc→GA decision; disposition them into a 4.0.0 emergent patch or re-milestone to the 4.x line
   with rationale (exit criteria 5–6).
5. **Re-run this synthesis at each rc bump** — milestone numbers move between rcs; verify the
   open book against a fresh `gh issue list --milestone 4.0.0 --state all` before acting.

## Links

- Milestone: https://github.com/spec-kitty/spec-kitty/milestone/8 ·
  Declaration of intent: [`4.0.0.md`](../changelog/4.0.0.md) · Convention:
  [`release-goals.md`](../changelog/release-goals.md)
- Prior cycle roadmap (re-anchored here): [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md)
- Convergence / client-repo inversion:
  [ADR 2026-09-06-1](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md) ·
  hosted context: [`docs/context/team-kitty.md`](../context/team-kitty.md)
- Durable domain plans: [Doctrine & Charter](domains/doctrine-charter-domain-plan.md) ·
  [API & Dashboard](domains/api-dashboard-domain-plan.md)
