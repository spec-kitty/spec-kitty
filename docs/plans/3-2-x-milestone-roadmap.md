---
title: 3.2.x Milestone — Roadmap
description: 'Operator-facing roadmap for the 3.2.x milestone: the epic dependency spine, degod/unshim wave status, milestone census, exit criteria, and watch items.'
doc_status: active
updated: '2026-09-14'
related:
- docs/plans/4-0-0-milestone-roadmap.md
- docs/changelog/index.md
- docs/plans/index.md
- docs/plans/code-quality/index.md
- docs/plans/testing/qa-tidy-first-sequencing.md
- docs/plans/doctrine/manifesto-program-delivery-sequence.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/changelog/release-goals.md
---
# 3.2.x Milestone — Roadmap

*Planner synthesis (planner-priti), 2026-07-04. Sources: milestone #4 census, the native epic dependency graph encoded in the tracker on 2026-07-04, [`degod-unshim-roadmap.md`](refactor/degod-unshim-roadmap.md), and the epic bodies of #1619 / #1797 / #2071 / #1868 / #2173 / #1746. Addendum, 2026-07-10: #2519 hot-list entry from epic #2519, member issues #2520/#2521/#2522/#2526, and current tracker metadata. Addendum, 2026-07-13: CI test-topology-performance mission shipped (PR #2609, under #1931); #1797 ↔ #2071 tidy-first intra-pair sequencing ruling recorded in Watch items + [`qa-tidy-first-sequencing.md`](testing/qa-tidy-first-sequencing.md). Addendum, 2026-07-26: doctrine canonical-structure remediation programme recorded — one mission specced then split into five sequenced missions (#2948–#2952) by operator ruling; see the dedicated section below.* **Addendum, 2026-07-30: verified status re-read + spine re-anchoring — the body below (2026-07-04 vintage) predates the work that delivered the milestone's goals and mis-reads it as idle; see [Addendum 2026-07-30](#addendum-2026-07-30--verified-status-re-read--spine-re-anchoring) immediately below, and the PO-facing [3.2.x Open-Core Delivery Plan](3-2-x-open-core-delivery-plan.md) which supersedes the "G2-is-the-blocking-spine / G1-is-off-spine" framing.**

## Intent of 3.2.x

3.2.x is the **stabilization + structural debt paydown** cycle: (G1) deepen Doctrine/Charter/DRG impact on runtime execution, (G2) strangle the core domains — naming, identity, read/write paths — onto canonical SSOTs by *adopting* the existing execution-context machinery rather than building new construction, and (G3) land the DevEx enablers that make (G1)/(G2) enforceable. No new shadow paths. The milestone stays open until all three goals hold (full declaration: [`docs/release-goals/3.2.x.md`](../changelog/3.2.x.md)). Everything experience-shaped — UX, dashboard, SaaS tie-in — is deliberately deferred to 3.3.x, which builds on the SSOTs this cycle establishes. The SaaS deferral covers the hosted *product launch* (the #1800 / #1091 / #3322 epics, all milestone 3.3.x), **not** the core **sync and consent integrity P0s** (#3178 / #3278 / #3307), which are in-cycle 3.2.x stabilization work; the SaaS & Hosted Sync domain plan was the domain's canonical map of that split (retired 2026-09-06 (Convergence #3881): the hosted-sync surface re-homed to the authoritative upstream repos; see the convergence-retirement ADR).

## Addendum 2026-09-14 — 4.0.x is now the active cycle (authority moved)

*Read-only reconciliation against live GitHub milestone/issue state on 2026-09-14
(`gh issue list --repo spec-kitty/spec-kitty --milestone 4.0.0 --state all`, `GITHUB_TOKEN`
unset). This addendum records only the **4.0.0 status change** and hands the active-cycle
authority to a dedicated roadmap; it does **not** rewrite the historical body below.*

The [2026-09-04 addendum](#addendum-2026-09-04--milestone-taxonomy-re-anchor-the-delayed-action-r)
recorded 4.0.0 as **declared, not yet active, 80 open**. That snapshot is now **stale**:

- **4.0.0 is the active cycle.** It is at **rc-stage** — **rc2 and rc3 are tagged**, and the
  `4.0.0rc3` development cycle is open on `main` (#4313).
- **The milestone is ~76% burned** — **66 closed / 22 open of 88 milestoned** (down from the
  80-open 2026-09-04 snapshot). The hosted-collaboration and reliability body has substantially
  landed; what remains is a short auth/consent P1 residual cluster plus the two open
  post-convergence client-integrity epics (**#3892** zeitgeist-client auth, **#3893** local
  event-log integrity), with the extensibility (#645, #901) and Sonar-debt (#1928 → #4299–#4305)
  work riding a **post-rc structural tail**.
- **Several declared 4.0.0 advances re-homed after the Convergence** (#3881, 2026-09-06): #1800
  and #3549/#3322 **closed** (the last two superseded client-side by #3893/#3892), #1091 closed
  and moved to **3.2.7**, and #2519 / #2173 moved to **3.2.7** — no longer 4.0.0 advances.

**Authority for the active cycle now lives in a dedicated roadmap:
[4.0.0 Milestone — Roadmap](4-0-0-milestone-roadmap.md).** It carries the four operator goal
themes (stability, maturity, extensibility, Team Kitty enablers), the current epic spine,
per-theme progress, exit criteria, and watch items. Everything below this addendum is the
**3.2.x historical record** and is preserved unchanged.

## Addendum 2026-09-04 — milestone-taxonomy re-anchor (the delayed Action R)

*Read-only reconciliation against live GitHub milestone/issue state on 2026-09-04
(`gh api repos/Priivacy-ai/spec-kitty` with `GITHUB_TOKEN` unset). This addendum
executes the taxonomy half of the [2026-07-30 Action R](#addendum-2026-07-30--verified-status-re-read--spine-re-anchoring)
(re-anchor the tracker) that was filed but never run, and folds in the findings of the
`work/3-2-x-checkup-2026-09-04/` roadmap checkup. The [2026-09-03 addendum](#addendum-2026-09-03--326-release-dag-fully-discharged-3692-closed)
below correctly recorded the 3.2.6 DAG discharge but patched only that axis; the
milestone map, the exit criteria, and the 2026-07-30 code claims were left stale. This
addendum re-keys them. It does **not** rewrite the historical body — read the
2026-07-04 spine, the 07-30 corrections, and every dated addendum through the milestone
translation table below.*

### 1. The milestone taxonomy the body speaks no longer exists

A **release-queue reconciliation on 2026-08-23** reorganised the milestones. The entire
corpus below (2026-07-04 body + the 07/08 addenda) is written in the *pre-reconciliation*
dialect — "the 3.2.x milestone", "deferred to 3.3.x" — which is now obsolete. Live state:

| # | Title | State | Open / Closed | What the body calls it |
|---|---|---|---|---|
| 4 | **Product backlog** | open | 552 / 468 | *"the 3.2.x milestone"* — repurposed; **validated but on no committed release** |
| 5 | **3.3.x** | **closed** | 0 / 12 | *"deferred to 3.3.x"* — **retired 2026-08-23; work re-triaged to 4.0.0 or Product backlog** |
| 7 | **3.2.6** | open | 0 / 67 | (post-body) stabilization — **code-complete, shipped-clean posture** |
| 9 | **3.2.7** | open | 32 / 0 | (post-body) post-reconciliation follow-ups — doctrine-term renames, profile-load consolidation, perf CI, dedups (decision D10 / epic #830) |
| 8 | **4.0.0** | open | 80 / 6 | (post-body) hosted collaboration + next-generation product |

Milestone #5's own description is the citation: *"Retired after release-queue
reconciliation on 2026-08-23. Open work was re-triaged into 4.0.0 or Product backlog."*

**Translation table — read the body through this:**

- Every *"3.2.x milestone"* / `milestone/4` link in the body now points at **Product
  backlog** — a validated-but-uncommitted bucket, **not** a release. It is no longer the
  cycle's burndown surface.
- Every *"deferred to 3.3.x"* / `milestone/5` reference is stale — the 3.3.x milestone is
  **closed/retired**; that work is now **4.0.0** (hosted product + deferred structural
  epics) or **Product backlog** (uncommitted).
- The clean GitHub boundary the plans never describe: **3.2.7** = finish the stabilization
  tail cleanly (renames / profile-load / perf-CI / dedups); **4.0.0** = the hosted product
  plus the deferred structural epics. The 4.0.0 declaration-of-intent is now written at
  [`docs/changelog/4.0.0.md`](../changelog/4.0.0.md).

### 2. Resolved-but-unstruck items in this doc and its siblings

The following are asserted open in the body/exit-criteria but are demonstrably closed
(verified 2026-09-04):

- **Exit criterion 4 (`#2071` test-QA) cites an open blocker; #2071 CLOSED 2026-08-02.**
  Read exit criterion 4 as satisfied-by-closure, not pending.
- **The doctrine domain plan's §3.5 (meta.json fail-closed) lists #3230 / #3229 / #3228 /
  #3240 as open children of epic #3259 — all five are CLOSED** (the children 2026-08-11,
  the epic #3259 itself CLOSED). That whole sub-area is done; see the doctrine plan's own
  2026-09-04 addendum.
- **#3176** (the sole-door residual named in [Addendum 2026-08-04](#addendum-2026-08-04--charter-sole-door-bypass-closure-substantially-landed) item 3) is **CLOSED**.
- **#2657 / #3183 / #2262** (doctrine arc / activation-availability) are **CLOSED**
  (Aug 7 / — / Jul 26); the arc diagram and doctrine §3.3 still present them as pending.
- **#3282 / #3307** (the P0s the exec overview and SaaS plan carried as open) are **CLOSED**
  (#3282 under 3.2.6; #3307 discharged).

### 3. G1 / G2 code claims are unrefreshed 2026-07-30 vintage

The [2026-07-30 addendum](#addendum-2026-07-30--verified-status-re-read--spine-re-anchoring)
G2 claims (`workflow.py`/`review.py` → 0 LOC, `core/execution_context.py` deleted, shim
registry `shims: []`, only `_read_path_resolver` parked) are a **2026-07-30 audit that
predates the entire 3.2.6 stabilization release** and has never been re-read against
`3.2.7rc1` HEAD. They remain **unverified-as-of-current** here (a code re-audit is out of
this doc-only pass's scope). Worse, they **contradict this roadmap's own Wave status
board**: the [Wave board](#wave-status-board-degodunshim-roadmap) marks the coord-authority
trio degod as `PARTIALLY QUEUED` (#2160 OPEN) while the 07-30 delivery claims it done.
Two active documents disagree and neither carries a post-August read — the tie needs a
single current code read before either claim drives a decision.

### 4. Disposition — spine epics committed to 4.0.0 (operator decision 2026-09-04)

The G1/G2 strangler spine the cycle exists to finish is **committed to 4.0.0 by operator
decision (2026-09-04)**. It had sat in **Product backlog** (validated, on no active release —
exit criterion 8's anti-drift guard, "nothing rides into 3.3.x silently," fired in a blind
spot as the work rode into Product backlog silently instead). The epics below now carry
milestone 4.0.0 on the live tracker; full 4.0.0 scoping: [`docs/changelog/4.0.0.md`](../changelog/4.0.0.md):

| Epic | Role | Milestone |
|---|---|---|
| **#1619** | mission-execution-context root (P0) | 4.0.0 |
| **#1797** | degod / unshim delivery | 4.0.0 |
| **#1868** | seam-binding enabler (WS4/WS6) | 4.0.0 |
| **#1746** | Mission Clarity Layer (P1, first functional pickup) | 4.0.0 |
| **#2160** | coord-artifact authority (P0, Wave 2 anchor) | 4.0.0 |
| **#1676** | deterministic structured authoring (P0, off-spine) | 4.0.0 |
| **#2466 / #2467 / #2468** | pack ecosystem + extensibility kinds (the declared G1 exit condition) | 4.0.0 |
| **#2539** | pack trust / verified distribution | 4.0.0 |
| **#3179 / #645** | stable public API surface | 4.0.0 |

Also on **4.0.0** from the reconciliation: **#2173** (runtime ports) and **#2519** (charter
authoring & lifecycle).

**Security-debt coupling:** the 21 SonarCloud vulnerabilities (the sole failing gate —
17 `S6350` subprocess + 3 `S2083` path-traversal, all pre-dating any current rc) are
mapped by the [08-12 addendum](#addendum-2026-08-12--release-posture-refresh-ci-green-except-the-standing-sonar-backlog)
onto the Wave 2/Wave 4 degod slices — precisely the spine epics above — so the security
backlog rides with the structural remediation, now both scheduled in 4.0.0. The 3 `S2083`
blockers remain a called-out ~90-min targeted fix that can land independent of any wave.

> **Doc-tooling note:** this re-anchor adds a new page, [`docs/changelog/4.0.0.md`](../changelog/4.0.0.md).
> The docs retrieval index and page inventory will need regenerating so it is discoverable.

## Addendum 2026-09-03 — 3.2.6 release DAG fully discharged (#3692 closed)

*Read-only reconciliation against live GitHub state on 2026-09-03. Supersedes the
"Ownership gap / ~19 unowned issues" red flag that the 3.2.6 execution DAG (#3692)
carried through its 2026-08-26 regeneration.*

**Every node in the 3.2.6 release DAG is now CLOSED.** The tracker issue #3692
("3.2.6 release DAG and execution order") enumerated the milestone's release-blocking
book across seven clusters — all twenty issues are discharged:

- mission-completion / lane integrity — #3590, #2945, #3281, #2947
- review-verdict integrity — #3235
- merge recovery & retention — #3579, #3131
- accept portability — #3016
- commit-boundary completeness — #2693, #3716, #2739
- upgrade missions — #3282, #2265, #2316
- charter / doctrine integrity — #3702, #3704, #3705, #3728, #2940
- diagnostic cleanliness — #3435

**Milestone posture:** 3.2.6 stands at 66 closed / 0 remaining work items; the only
issue that was still "open" on the milestone was the #3692 tracker itself, now closed.
No open PR gates the tag — the current open PRs carry the 3.2.7 milestone or none, and
none close a 3.2.6 DAG node. The 08-12 addendum below judged an rc cuttable on
code-health grounds; that judgement now extends to the final tag on the functional
axis: the release-blocking bug book is empty. Sonar's standing backlog (below) and the
broader 3.2.x cycle exit criteria remain their own, separately-tracked concerns.

## Addendum 2026-08-12 — release-posture refresh (CI green except the standing Sonar backlog)

*Read-only observation grounded in the 2026-08-12 CI Quality run (`workflow_dispatch`
on `main`, commit `f6b90d34e`) and the live SonarCloud project. It updates the release
posture the [2026-07-30 addendum](#addendum-2026-07-30--verified-status-re-read--spine-re-anchoring)
recorded ("`main` NOT tag-ready, CI red 10+ consecutive runs"), which has since gone
stale in the milestone's favour.*

**Health signal has converged toward the stabilization goal.** Since the 07-30 note:
coverage recovered **47% -> 84.1%** (a project high), reliability bugs cleared
**34 -> 0** (2026-08-11), duplication holds at **0.5%**, and CI Quality on normal `main`
pushes is **green**. The dedicated Playwright `ui-e2e` and `ci-windows` workflows are
green on the head commit. Full measurement and cluster analysis:
[Code Quality — Working Collection](code-quality/index.md).

**The one red is honest, not a regression.** The `workflow_dispatch` CI Quality run
fails only on the SonarCloud quality gate, and only on `new_security_rating = C`. All
21 vulnerabilities predate any current release candidate (created 2026-06-24 ->
2026-07-30); the head commit contributed none. Sonar runs only on
`workflow_dispatch`/`schedule`, so it surfaces the accumulated backlog rather than a
change — an honest standing red per
[ADR 2026-07-17-1](../adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md).

**The debt is the roadmap's own scoped paydown.** The security backlog (17 `S6350`
subprocess findings) and the worst complexity files map almost 1:1 onto the
**QUEUED** Wave 2 (coord-authority) and Wave 4 (sync adapters) degod slices — see the
[debt -> wave mapping](code-quality/index.md#how-the-debt-maps-onto-the-roadmap). The 3
`S2083` BLOCKER path-traversal vulns (`merge/bookkeeping_projection.py`,
`skills/verifier.py`) are **not** on a wave and are a ~90-min targeted fix.

**Implication for tagging.** A patch **release candidate** (e.g. `3.2.6-rc1`) is
cuttable on code-health grounds: every functional gate — all test suites,
`e2e-cross-cutting`, blocking regression, `ui-e2e`, Windows — is green, and the Sonar
gate is a known standing backlog, not a candidate regression. This does **not** close
the 3.2.x milestone: the degod spine (Waves 2-4) and the P0 book (#2160, #1619) remain
open per the exit criteria below. Cutting an rc is a checkpoint inside the cycle, not
its completion. Recommended before the *final* 3.2.6 tag: triage the 3 `S2083` blockers
and note the remaining Sonar backlog as known/deferred in the release notes.

## Addendum 2026-07-30 — verified status re-read + spine re-anchoring

*Two read-only audits (G1 doctrine/charter; G2/G3 + release posture) grounded in the
code and the live tracker on 2026-07-30 found the body below has drifted from reality.
The corrections, in brief — full PO-facing detail in the
[3.2.x Open-Core Delivery Plan](3-2-x-open-core-delivery-plan.md):*

1. **The G2 "spine" is substantially DELIVERED, not idle — filed under new numbers.**
   The placement-seam swarm is the delivery of the named spine, and burn-down keys on
   the wrong anchors:
   - #2906 (read) / #2841 (write) / #2917 (birth-cutover) **deliver #1619** exec-context
     unification (old `core/execution_context.py` deleted, not shimmed; SSOT in
     `src/mission_runtime/`).
   - #2884 / #2262 / the MissionResolver port **deliver #2173** infra-port binding.
   - the coord-authority trio degod (`workflow.py` / `review.py` → 0 LOC) +
     `runtime_bridge` decomposition **deliver #1797** (shim registry drained to
     `shims: []`). Only `_read_path_resolver` (~1677 LOC) is parked.
   **Action R (re-anchor):** adopt the swarm as executing children of #1619/#2173/#1797
   and re-score the milestone against real coverage. The spine is not idle; its anchors
   went stale — the inverse of this doc's own "anchor to issue numbers" watch item.

2. **G1 mission-types-as-doctrine is BUILT and ACTIVE, not an unbuilt keystone.** The
   three types (+`plan`) resolve through charter → mission-type-profile → runtime; the
   data plane is 100% doctrine-sourced (profiles, step contracts, action indices,
   templates, prompts). Only the execution engine is code. **G1's done-signal is
   demonstrated doctrine→runtime governance (already true), not pack-split completion.**
   The real open G1 work is a bounded ~22-door list to make the **charter the sole
   access path** to provisioned assets (it gates only ~3 of ~10 kinds today).
   **Superseded, 2026-08-04:** the scoping pass this line asked for ran, corrected the
   count to ~20, and closed the enumerated set — see
   [Addendum 2026-08-04](#addendum-2026-08-04--charter-sole-door-bypass-closure-substantially-landed)
   below and the delivery plan's §1.1 for the closed/residual breakdown.

3. **The cycle's organizing frame is an open-core breaking-change window**, not a
   feature-completeness sprint: draw + version the consumer seam, extract built-in
   doctrine into the already-declared `spec-kitty-doctrine` module (~90% done
   structurally; one import-cycle blocker), and ship the still-design-only schema
   (Creed / Values / the ADR-accepted `impacts` relation) behind migration rails +
   deprecation shims to a small consenting consumer set. No hard freeze. See the
   delivery plan and [3.2.x Delivery Approach](3-2-x-approach.md) (doctrine-first,
   confirmed).

4. **Release posture: `main` is NOT tag-ready** — CI red 10+ consecutive runs
   (2026-07-28→07-30), 9 failing jobs incl. `regression tests (blocking)`. Partly the
   red-main-is-honest baseline P0 pins (#2736/#2772/#1834); **unverified** whether a
   fresh write-side-seam regression is mixed in. Resolve that classification before any
   tag conversation.

*The dependency-spine section below is retained as the historical 2026-07-04 encoding;
read it through the corrections above.*

## Addendum 2026-08-01 — write-path topology scoping gap (design-spike #3129)

*A maintainer observation ("the read vs write paths topology issues keep rearing their heads, and
we're chopping them off as they spawn") prompted an investigation by LynnColeArt, filed as
[#3129](https://github.com/Priivacy-ai/spec-kitty/issues/3129). A dialectic squad (architecture,
governance, skeptic, advocate lenses + synthesis) independently corroborated or disproved the
claim before any tracker action was taken; findings below.*

1. **The technical diagnosis is corroborated.** Lane worktrees, the coordination worktree, and the
   primary checkout share one git object store and one ref namespace (confirmed against
   `docs/architecture/git-worktrees.md`); no code path today compares the invoking checkout against
   a mission's declared workspace before allowing a write. G2's committed scope this cycle
   (`#1878` — placement-routing + commit/protected-branch durability) **presupposes a write already
   originates inside a valid mission workspace**; it decides which partition the write lands on, not
   whether the invoking checkout belongs to the mission at all. That precondition gap is exactly what
   the 2026-07-31 `spec-kitty-saas` incident exposed (a compacted Codex agent resumed in the wrong
   checkout and wrote artifacts into it, undetected, next to a second agent's uncommitted edits) —
   G2 as scoped would not have caught it.
2. **The proposed remedy scale is not corroborated to the same degree.** The cheap, additive fix —
   [#3128](https://github.com/Priivacy-ai/spec-kitty/issues/3128), a fail-closed comparison of the
   invoking checkout against already-computed mission/lane metadata — would independently have
   caught the actual incident with no topology change, and its own author (Lynn) ranks it "the cheap
   first mitigation regardless" of any later ThickTicket/SugarFang shadow-workspace decision. The
   full shadow-workspace redesign remains an open, ungated design-spike, not a demonstrated
   necessity for 3.2.x.
3. **A batch reparent into a new P0 "Topology / Isolation breaches" epic was considered and
   rejected as the wrong process move.** 11 of the 14 issues #3129 names already have working
   functional-epic homes (`#2624`, `#2160`, `#1619`, `#1795`, `#2017`) — reparenting them would
   discard organizing work already done, against this repo's own narrow-consolidation precedent
   (`#2392`: fold a shared-mechanism bug cluster into one seam, but do not over-broaden past a
   confirmed mechanism). `#1878` — the closest existing umbrella — carries an on-record maintainer
   non-goal: *"No topology redesign — the coordination-branch/worktree topology stays as-is."* And
   Lynn's own issue states *"Not urgent relative to MVP,"* which directly contradicts a P0
   (release-blocker) label under this repo's own priority definitions
   ([`HOW_TO_MAINTAIN.md`](../operations/how-to-maintain.md)).
4. **Process learning for future cross-cutting findings of this shape:** a design-spike naming N
   related bugs as "one shared root" is diagnostic evidence, not by itself license to reparent an
   existing, working epic-triage structure. Default to reference/cross-link plus targeted placement
   of only the currently-unparented members, and treat scope/priority escalation (especially
   anything that reverses an on-record non-goal) as an operator call — not something a planning
   pass resolves unilaterally.
5. **Recommended concrete action (pending operator confirmation, not yet applied):** fold `#3128`
   into `#1878`/G2's active scope now as a minimal precondition fix; park the 4 currently-unparented
   issues (`#3124`, `#3049`, `#3128`, `#3129` itself) under the existing `#1878` umbrella with an
   explicit flag on the non-goal tension, rather than minting a new epic; keep `#3129`'s
   shadow-workspace proposal gated — escalate only if the same undetected-out-of-context-write
   shape keeps recurring after `#3128` and the `#1878` strangler land.

<a id="addendum-2026-08-02-charter-as-sole-door-boundary-usage-pair-landed-mission-1-mission-2"></a>

## Addendum 2026-08-02 — charter-as-sole-door boundary/usage pair landed (Mission 1 + Mission 2)

*The two-mission sequence scoped to close out the [open-core delivery plan](3-2-x-open-core-delivery-plan.md)
§3 item 1 (boundary extraction) and make progress on item 2 (charter-as-sole-door) has landed on main.*

1. **Mission 1 — `doctrine-built-in-seam-consolidation` — landed.** Consolidated built-in doctrine
   onto one fail-closed location seam and completed the `packs/built-in` relocation (the G1 arc's
   keystone `#2467` split, see below), and derived the activation-key vocabularies from a single
   authority (restoring `activated_glossary_packs`).
2. **Mission 2 — `charter-pack-usage-journey` — landed.** Makes `spec-kitty charter pack apply`
   actually deliver usable governance instead of a dead end: applying a pack (without compiling) no
   longer disables the safe generic-agent dispatch fallback (`#3104` — the P1 regression where the
   documented "get started" remedy broke the thing it was meant to help), keeps that dispatch-net
   check single-load on the hot path (`#3118`), and an opt-in `--compile` chains the existing
   compile seam so `charter context`/`charter status` read the compiled `charter.yaml` as the
   governance authority and survive `charter.md` deletion (`#3105`) — with `resolve_project_governance`
   now reporting the *activated* directive set rather than a catalog-fallback of all built-ins.
   Folded in per operator direction: the advertised `charter context --include section:…` selectors
   no longer dead-end (`#3095`/`#3094`/`#2552`), the documented `spec-kitty analyze` surface now
   agrees with the CLI (`#3096`), and a path-filtered CI workflow gives `src/doctrine/**` /
   `src/charter/**` changes isolated, fast feedback (`#3102`) — plus the journey-doc fold-in
   (`#3107`). Closes `#3104`, `#3105`, `#3118`, `#3095`, `#3094`, `#2552`, `#3096`, `#3102`, `#3107`.
   One deliberate, recorded behaviour change (NFR-004): "empty" for the dispatch net now means the
   compiled bundle is **absent**, which narrows and reverses the `#3064` glossary-dimension case of
   the wider composite-activation check that mission introduced — a benign, tested contraction, not
   a silent regression.
3. **Relation to the delivery plan's remaining-work sequence:** Mission 1 completes item 1
   (boundary extraction / built-in → packs). Mission 2 hardens the *existing* charter door
   (dispatch-net safety, `charter.yaml` as the sole read authority, one directive authority) but
   does **not** close the ~22 bypass-door list item 2 names — that count is unaffected and remains
   open work. **Superseded, 2026-08-04:** item 2 itself was closed by a third mission — see
   [Addendum 2026-08-04](#addendum-2026-08-04--charter-sole-door-bypass-closure-substantially-landed)
   below.

## Addendum 2026-08-04 — charter-sole-door-bypass-closure substantially landed

*The delivery plan's item 2 ([§3](3-2-x-open-core-delivery-plan.md#3-remaining-work-sequenced)) —
closing the charter-as-sole-door bypass list — landed as its own mission, following the boundary
(Mission 1) and existing-door-hardening (Mission 2) pair above.*

1. **Mission 3 — `charter-sole-door-bypass-closure-01KZ3WAA` — landed 2026-08-04.** Ran the
   scoping pass item 2's own caveat asked for and corrected the door count from this roadmap's
   ~22 grep estimate to a confirmed **~20** (the mission's `spec.md` and the CHANGELOG both cite
   ~20). Closed every enumerated direct `AgentProfileRepository(...)`/raw
   `doctrine.service.DoctrineService(...)` construction site and `._inner` attribute
   reach-around around the charter's `DoctrineService` factory; unified the two divergent
   "canonical" builder functions onto one
   (`charter.doctrine_service_builder.build_activation_aware_doctrine_service`); extended
   activation gating from 3 of 10 doctrine-artifact kinds to all 9 charter-activatable kinds plus
   the `mission-type` token (`mission-type` gating itself pre-existed — this mission verified it
   and added regression coverage, not new construction); consolidated a triplicated
   missions-root hardcode onto `MissionTemplateRepository.default_missions_root()`; and shipped
   five zero-tolerance AST/qualname architectural gates, widened during landing with 35
   injection tests.
2. **What "closed" proves, precisely:** the enforceable invariant is **Policy A** — a raw
   service never escapes its acquisition site unwrapped, zero exclusions, covering builder
   *calls* as well as constructions — not the stronger **Policy B** (one single constructor),
   which still carries named locality exclusions. Do not read this as "the sole-door claim is
   now unconditional."
3. **Residual, not the full door list:** `doctrine.template_catalog.resolve_template_by_id` (5
   importers), `specify_cli/runtime/resolver.py`'s tier-1–4 reimplementation,
   `runtime/home.py`'s `importlib.resources` root lookup, three root-relative missions-root
   duplicates, and one escalated `AgentProfileRepository` site
   (`tool_surface/profiles/projection.py`) remain open, sequenced as `#3176`/`#3091`/`#3022`/`#3101`.
4. **SC-008 stayed unmet, honestly.** The mission's own acceptance record carries SC-008
   (pre-migration p95 baseline captured before any FR-001 site was migrated) as `fail` — the
   baseline was never persisted and cannot be reconstructed retroactively. The performance
   *outcome* NFR-005 actually cares about passes (a fresh landing-time A/B measured -2.60% p95,
   i.e. faster, well inside the ±10% budget) — the two are distinct claims; this mission does not
   claim SC-008 passed.

## The dependency spine

The epic graph is now encoded **natively in the tracker** as blocked-by edges (2026-07-04):

```
        #1868 seam-binding   #2173 runtime ports      (peer enablers)
                 \               /
                  ▼             ▼
              #1797 degod / unshim DELIVERY        #2071 test-QA friction
                  │       \                          /        │
                  ▼        ▼                        ▼         │
   #1619 runtime/state ROOT (P0)          #1746 Mission Clarity Layer (P1)
                                          — first FUNCTIONAL pickup

   #1931 test hygiene — standing campsite epic, deliberately OUTSIDE the blocking graph
   #2392 upgrade-worktree coherence — #1619 child epic, consolidation-only (see Watch items)
   #2400 metadata & profile authority (P1) — #1799 sub-epic, consolidation-only (see Watch items)
```

**Reading order — enablers → delivery → functional pickup:**

1. **Enablers first.** #1868 binds *what a seam is and refuses bypass* (layer rules, identity value-object, guard capability, CI suite map, contract versions); #2173 binds *how infra is supplied without coupling* (ports + default-param DI). They share mechanism and run as peers.
2. **Delivery next.** #1797 (degod/unshim) is *blocked by* #1868 and #2173: every shim deletion is only safe once the seam it held is bound, and every god-object extraction only pays off once its pure core is stub-testable through a port.
3. **Root closes on delivery + QA.** #1619 (unify mission execution context — the program root) is *blocked by* #1797 and #2071: the `MissionExecutionContext`/`ResolvedMission` adoption cannot complete while god-objects re-derive context per call site and while the suite's accidental-pass/duplicate-knowledge debt makes structural change hazardous.
4. **First functional pickup.** #1746 (Mission Clarity Layer, P1) is *blocked by* #1797 and #2071 — queued as the first functional mission once the debt cluster lands, co-designed with #1666's communication-artefact contract.
5. **#1931** (test quality & suite hygiene) runs as a standing campsite epic: folded opportunistically into missions, never a blocker.
6. **#2392** (upgrade-worktree coherence, child of #1619) is the same kind of standing consolidation epic as #1931, not a blocking node — it exists to fold a git-state bug cluster (#2385, #1873, #2105, and the partly-fenced #2367) into **one** canonical fix seam instead of letting each land as an independent partial patch. Alphonso's design: a canonical invariant (*every write in every checkout the upgrade run touches ends in exactly one auto-commit — derived from real `git status --porcelain`, not a hardcoded list — or is intentionally reverted*), landed via a single `commit_touched_checkout` helper extracted from `_auto_commit_upgrade_changes` (`upgrade.py`) and applied symmetrically across main + every `.worktrees/*` enumerated by `runner.py`. #2367 is flagged as one-invariant-three-seams and kept OUT of this helper (see Watch items).
7. **#2400** (metadata & profile authority, **P1**, sub-epic of #1799) is a second standing consolidation epic of the same shape as #1931/#2392, not a blocking node — it exists to fold the "instructed, not enforced" defect class (the same class as #2364's dispatch-time model-discipline rule) into one canonical resolver/event-log authority instead of leaving it as prompt instructions or drifting hardcoded frontmatter. Members: **#2399** (structurally enforce agent-profile loading across all four invocation contexts — ops/ad-hoc/dispatch/mission-WP) and **#2093** (WP-metadata authority split: static design-intent stays frontmatter-canonical; dynamic runtime state — `agent`/`shell_pid`/`history`/reviews — retires to event-log/invocation authority, generalizing the `lane` retirement; architect-alphonso's DECISION already rules this REWORK-staged). Related but not reparented: #1841 (WP-claim Python profile-load) and #1840 (skills subagent-delegation preamble). Mutual coupling: splitting `agent_profile` (intent vs. resolved-binding, #2093) is the **precondition** for #2399's enforcement seam; #2399's resolve→materialize→record mechanism is the **mechanism** that makes #2093's dynamic half real — sequence the pair together (see Watch items).

   *Addendum, 2026-07-16 (WP/Op schema arc):* #2400 is **no longer consolidation-only** — it now also carries a **functional build mission**. **#2684** (evict runtime-mutable WP state — `shell_pid`/`history`/subtask-checkbox/review-cycle/activity-log/`agent`/`assignee` — off `tasks/WP##.md` into the event log; native sub-issue of #2093, its **execution vehicle**) is real construction with its own AC set and a migration contract, not re-homing of existing behavior; it delivers the content-hash-churn fix as its **AC-5** and generalizes the shipped `lane` retirement. Alongside it: the **independent, ships-now** slice **#2685** (required-on-close structured Op debrief — optional `OpDebrief` on `OpCompletedEvent` for read-back safety + required-presence/graduated-depth enforced at `executor.complete_invocation`; sibling of #2399), and its follow-up **#2686** (semantic-only WP content-hash, largely subsumed by #2684's AC-5, `blocked_by` #2684). #2684 is **co-sequenced with #2160** on the shared `shell_pid` writers (see Watch items). The full **YAML-authoritative / markdown-derived WP-prompt flip is 3.3.x** — gated on **#1619** (the mid-revision WP/Mission aggregate), **#1676** (deterministic structured authoring), and **re-ratification of #2093's static-stays-in-file ruling by the #2400 owner**; #2684 deliberately stops at "file holds only static intent," not "file is derived."

## The G1 doctrine & charter arc (off-spine)

The dependency spine above is the **G2/G3** program — strangling the core domains onto SSOTs and the DevEx enablers that make it enforceable. But 3.2.x's *first* stated goal is **G1: deepen Doctrine/Charter/DRG impact on runtime execution**, and that goal has its own epic arc which sits **outside the blocking spine by design** — it is depth, not a blocker of the mission-execution root #1619. This section makes the arc visible so the roadmap reflects the whole milestone, not just the strangler.

*Added 2026-07-14 after an epic-graph audit found this arc unmodeled here and several of its epics unprioritized. Priority/milestone fixes applied in the same pass: #2466→P1, #1799→P1; the two P1 Glossary-as-doctrine epics #1629/#1418 pulled into 3.2.x. The doctrine arc's internal edges were audited and found already modeled at the right granularity (keystone-child, not coarse parent) — no new blocked-by edges were warranted.*

**The arc has four roots and one internal keystone:**

```
#2466 pack ecosystem (P1) ──[keystone #2467: split built-in → packs ✅ LANDED]──┐
   ├─ #2468 mission-types + step-contracts as doctrine kinds           │ #2467 blocks:
   ├─ #2469 loose-contract ASSET kind ✅ · #2495 templates as DRG ✅    │  #2468 #2470 #2471 #2216
   ├─ #2470 shortcodes-as-doctrine · #2471 pack-validator CI · #2472 procedure-kind fate
   ├─ #2473 model-discipline currency · #2537 DRG at_tension_with edge (CLOSED — superseded
   │        by ADR 2026-07-26-3 / mission B1 #2949, see the remediation programme below)
   ├─ #2948/#2949/#2950 doctrine canonical-structure remediation missions A/B1/B2 (see below)
   ├─ #2535 doctrine-controlled transition gates (P1) — sub-epic, needs #2468/#2469
   │     └─ #2595 ScopeSource port · #2596 pre-review handler · #2597 gate-binding schema
   │        #2598 invert move-task hook · #2599 executable ASSET handlers · #2540 trust baseline
   └─ #2539 pack trust / verifiability (→ 3.3.x) — sub-epic, verified distribution

#1799 charter & doctrine governance (P1)
   ├─ #2216 governance tiers (P2) — blocked_by #2467 — component-type immutability
   │     └─ #2591 schema · #2592 merge-time enforcement · #2593 AUTHORITATIVE master-switch · #2594 migrate replaceable-builtins
   └─ #2400 metadata & profile authority (P1) — consolidation sub-epic (see spine reading-order #7)

#2519 charter authoring & lifecycle robustness (P1)
   └─ #2526 foundation ✅ → #2522 authoring scaffold → #2521 init-freshness preflight → #2520 charter domain events   (see Hot list)

#2314 docsite (P2) + doctrine-docs #2053 / #2302 (codify docs-as-doctrine) / #2352
Glossary-as-doctrine: #1629 + #1418 (P1, now 3.2.x) — first-order glossary artifact / packs
   └─ Glossary Doctrine Overhaul program (2026-07-21): #1418 → #2599 → #2822/#2830/#2823 → #2727
```

**Reading order within the arc:**

1. **#2467 is the keystone — LANDED (see [Addendum 2026-08-02](#addendum-2026-08-02-charter-as-sole-door-boundary-usage-pair-landed-mission-1-mission-2)).** Splitting built-in doctrine into packs (built-in → org → project, `depends_on` DAG) is the substrate everything downstream builds against; it already blocks #2468/#2470/#2471/#2216. Delivered by mission `doctrine-built-in-seam-consolidation` (Mission 1 of the boundary/usage pair); the follow-on `charter-pack-usage-journey` (Mission 2) then made the resulting pack-apply path actually deliver working governance — it does not itself close #2468/#2470/#2471/#2216, which stay open.
2. **Extensibility kinds next.** #2468 (mission-types + step-contracts as doctrine kinds) and the closed #2469 (ASSET kind) are the prerequisites the **gates** sub-epic #2535 makes executable at a transition boundary.
3. **Governance semantics.** #2216 (component-type immutability + AUTHORITATIVE charters) rides on the pack tiers from #2467 — the edge exists at keystone-child granularity (#2216 blocked_by #2467), not a coarse parent edge.
4. **Authoring robustness.** #2519 runs its own #2526→#2522→#2521→#2520 sequence (foundation shipped); it is a sibling root, not gated by #2466.
5. **Trust / distribution (#2539) is 3.3.x** — the verified-pack story builds on this cycle's pack model but ships next milestone.
6. **Glossary-as-doctrine is now a sequenced four-mission program** (operator-decided 2026-07-21; ADR [2026-07-21-1](../adr/3.x/2026-07-21-2-glossary-first-order-doctrine-artefact.md), plan [glossary-doctrine-overhaul-program.md](glossary-doctrine-overhaul-program.md)). Keystone **#1418** builds the first-order `GLOSSARY_PACK` kind; then **#2599** lands the executable ASSET gate (phased trust model — built-in provenance only for now); then enforcement + terminology cleanup (**#2822/#2830/#2823**) ships adherence *as* a built-in ASSET gate; then the dead runtime `src/glossary/` is retired (**#2727**). Research resolved the #1418↔#2727 seed-into-runtime contradiction (do not seed into the dying package; migrate the 104 terms + repoint the casing gate, then delete).

**Exit-criteria implication:** the milestone's G1 goal is not satisfied merely because the spine closes. At minimum the arc's **keystone #2467** and the extensibility kinds it unblocks (#2468 and #2535's declarative-gate half) must land for G1 to have "deepened Doctrine/Charter/DRG impact on runtime execution" as declared. The governance-tier tail (#2216) and trust/distribution (#2539) may legitimately carry into 3.3.x — but as an **explicit re-milestone decision, not silent drift** (the same standing counter-measure as the milestone-drift watch item below).

## Doctrine canonical-structure remediation programme (2026-07-26)

While closing P0 #2934 and researching the test-quality doctrine series (#2935), one root cause turned up behind four unrelated-looking symptoms: **the doctrine layer — the YAML rules and relationships that drive charter/DRG behavior — predates its own canonical model, and nothing enforces the model that replaced it.** Concretely: a schema correctly refusing a new artefact kind was mistaken for a bug; an error message tells operators to edit a file deleted years ago; nine doctrine files sit in directories nothing ever loads (two of them stale duplicates of the real file); and a directory layer named in documentation has never existed on disk. In every case the failure was silent — a misplaced or orphaned file just stops mattering instead of raising an error.

This was specced as one mission, `doctrine-canonical-structure-remediation-01KYEYSD` (spec: `kitty-specs/doctrine-canonical-structure-remediation-01KYEYSD/spec.md`, the requirements authority and full FR→mission routing table; plan: `.../plan.md`, the cost and Phase 0 findings; governing ADRs [2026-07-26-1](../adr/3.x/2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md), [-2](../adr/3.x/2026-07-26-2-doctrine-artefact-pack-layout-convention.md), [-3](../adr/3.x/2026-07-26-3-impacts-edge-subsumes-in-tension-with.md)). Once priced at an estimated 28–43 agent-days and ~555–665 file touches, the operator ruled it too large for one pull request and split it into five sequenced missions. The original spec mission does not implement anything itself — it stays the programme record.

| # | Mission | What it delivers | Agent-days | Files | Tracker issue |
| --- | --- | --- | --- | --- | --- |
| A | `doctrine-silence-guards-01KYFV7Q` | The guard rails: a lint that fails if a doctrine field exists but nothing produces or reads it; closes four sites that silently drop an unrecognized artefact kind; makes an unrecognized field on the core doctrine models a load error instead of silent data loss; fixes the stale migration hint, the phantom `shipped/` directory references, and the org→DRG bridge's silent edge drop. | 4–6 | ~55–70 | #2948 |
| B1 | `drg-relation-impacts-vocabulary-01KYFV87` | A new signed `impacts` relationship (replacing the old yes/no `in_tension_with` flag) plus an `is_symmetric` shorthand, per ADR 2026-07-26-3. | 3–5 | ~45–60 | #2949 |
| B2 | `drg-edge-migration-extractor-retirement-01KYFV8C` | The largest mission: moves all 774 doctrine relationships from "computed by a script each time" to "written down once, checked in." Deletes the two Python modules that used to compute them. Same-surface bulk edit; carries its own occurrence map. | 11–14 | ~365–390 | #2950 |
| C | `test-quality-doctrine-series-01KYFV8H` | The original #2935 deliverable: turns the over-mocking failure behind P0 #2934 into a citable doctrine rule (new paradigm, directive, procedure, anti-patterns), plus curator-profile and CLI-validator fixes. | 3–5 | ~30–45 | #2951 |
| D | `foundational-values-creed-band-01KYFV8N` | The reachable slice of a separate creed-scoring design (see [`manifesto-program-delivery-sequence.md`](doctrine/manifesto-program-delivery-sequence.md)): definition unification, accreditation, a couple of structural fixes, an advisory-terminology unification, and the ranking-function arithmetic (see scope change below). | 7–13 | ~60–100 | #2952 |
| **Total** | | | **28–43** | **~555–665** | |

Operator review/decision time across the five draft PRs is estimated separately at 25–40 hours.

### Why the order is fixed, not a preference

The missions must land **A → B1 → B2 → C**, with **D depending only on A**:

- **A must go first.** Mission A adds a lint that fails if a new doctrine field is declared but nothing in the codebase actually reads or writes it. Without that landing first, any field B1 adds would ship silently unused behind a green test suite — this exact failure has already happened three times in this repository, one of them for 162 days before anyone noticed.
- **A must land before B1 specifically.** Two code sites (`extractor.py:133-145` and `:1210-1229`) currently drop unrecognized data silently instead of erroring. If B1's new `impacts`/`is_symmetric` fields exist before those two sites are fixed, the fields get silently deleted every time the doctrine graph is regenerated — again, behind green tests. Mission A fixes those sites.
- **B1 must land before B2.** B1 retires the old `in_tension_with` flag in favor of the new `impacts` field. If B2 (which moves all 774 relationships into checked-in files) ran first, the two currently-existing tension relationships would be migrated once under the old scheme, then have to be migrated again once B1 lands — the same data touched twice for no reason.
- **C must land after B2.** Mission C authors new doctrine content, and the whole point of B2 is that relationships are now written down directly instead of computed. C's new content needs to be written the new way from day one, which only works once B2's checked-in format exists.
- **D only needs A.** D's work doesn't touch the relationship-migration machinery B1/B2 own, so it only needs A's guard rails, not the migration.

### Two scope changes since the spec was written

1. **The #2538 experiment does not exist in this repository.** The spec assumed an experiment rig (issue #2538, "does missing tension-modeling cause bad deferment at depth?") existed to test whether new numeric "value" fields (I14) and their supporting interview instrument (I17) are worth building. An exhaustive search — code, tests, git history, branches — found no trace of that rig ever having been built or committed. Because that gate can't be cleared, **I14 and I17 are now closed, not deferred** — removing the programme's entire unquantified authoring tail, estimated at 1,372–1,596 hand-authored data cells. *Caveat: this only proves the rig isn't in this repository — if it exists in the operator's own environment, the conclusion reverses.* Issue #2538 itself stays open (it's milestone-3.3.x work) and is untouched by this finding — it is neither closed nor reopened here.
2. **The ranking-function design decision landed on "arithmetic."** One of the open design decisions in the FoundationalValues/creed programme (D-3: should the creed ranking be computed arithmetically, or read as prose?) was ruled by the operator. The answer is arithmetic, which un-parks increment I10 (the ranking function itself) into mission D.

### How this relates to existing tracker items

This programme does not duplicate open work — it feeds it or is fed by it:

- **#2466** (pack ecosystem epic, P1) is the parent epic for missions A/B1/B2's tracker issues (#2948, #2949, #2950 — see the arc diagram above).
- **#2591** (component-type schema) and **#2538** (the value-fields experiment) are untouched — both stay exactly where they were, at their existing milestones.
- **#2468**, **#2847**, **#2862**, **#2829** are all blocked by mission A's silent-kind-drop fix — cross-linked as `blocked by #2948`.
- **#2532** (decompose `charter/context.py`) touches the same code mission A must fix (a missing `else` branch) — cross-referenced so neither drops the fix.
- **#2537** (closed) is superseded by ADR 2026-07-26-3 / mission B1's `impacts` relation — noted in the arc diagram above and on the closed issue; not reopened.
- **#2935** is the doctrine-authoring backlog item mission C delivers (C is filed as its sub-issue, #2951).
- **#2934** is the P0 already closed by PR #2936, which also delivered FR-000/001/002/012 and the layout gate's first non-vacuity proof — this programme's five missions pick up everything else.

## Wave status board (degod/unshim roadmap)

| Wave | Deliverable | Status | Anchors |
| --- | --- | --- | --- |
| **0** (S) | Bind CI suite map — marker→job authority; `-m unit`/`-m contract` select a job; fails closed | **SHIPPED** — PR #2368 (merged 2026-07-04, commit `6db60d367`; mission `ci-suite-map-bind-01KWNPMP`), marker→job authority bound — the substrate the ci-topology-shrink mission (below) builds on | #2297, #2296, #2034, #2333 CLOSED; **#2283 now CLOSED** (Phase 3 landed via PR #2442, 2026-07-07 — local pre-PR CI parity + factor-(a) verify; the factor-(c) *dynamic* half of the review-time boundary is realized by #2438's `pre_review_gate`, and the still-unmodeled contract-ownership half is filed as #2441 — see Watch items) |
| **1** (D) | tasks.py degod — body-thinning via ports, golden-CLI test first | **SHIPPED** — PR #2308 (tasks.py 4569→1206 LOC, 10/10 WPs) | #2116 CLOSED (+#2305/#2306/#2307) |
| **1∥** (U) | category_4 removable-now shim sweep (8→0) + orphan cleanup | **SHIPPED** — PR #2325 (unshim wave 1) | #2289, #2292, #2258 CLOSED |
| **2** (D+S) | coord-authority trio degod (workflow.py / implement.py / acceptance) + canonicalizer gate | **PARTIALLY QUEUED** — the #2164 Phase-1 canonicalizer gate is CLOSED; the trio degod itself is the next degod slice | #2164 CLOSED; #2160 OPEN (P0) |
| **2∥** (U+S) | `specify_cli.next` + `glossary` + charter shim deletions; WS1 layer rule bound | **SHIPPED** — PR #2328 (unshim wave 2, 9/9 WPs); shim registry drained to `shims: []` | #2291, #2290, #2326, #2327 CLOSED |
| **3** (D+S) | orchestrator_api degod + WS4 daemon-identity bind | **QUEUED** (category_7 orphan triage already executed in PR #2325; PR #2338 advanced the orchestrator-api contract to 1.2.0) | WS4 OPEN |
| **4** (D+S+U) | sync adapter cluster + WS6 contract-policy ADR + `category_b` burn-down (baseline 215) | **QUEUED** — safe last; adapter-shaped | WS6 in-progress |

Seam state carried from the wave plan: WS1/WS2/WS3 **DONE**, WS5 (CI suite map) **DONE — shipped with Wave 0 (PR #2368)**, WS4 open and WS6 in-progress (pinning bound; policy ADR missing) — they gate Waves 3 and 4 respectively.

## Milestone census (2026-07-04)

**271 issues milestoned: 141 open / 130 closed** (48% burn — the count *grew* by 40 on 2026-07-04 when the sub-issue milestone-consistency sweep pulled the spine's unmilestoned children, the critical-path P1s, and #1716 (folding the retired 3.2.1 milestone) into 3.2.x; the burn percentage dropped for honest reasons: previously-invisible scope now counts). Recent landings: PRs #2332 (dashboard identity fix), #2336 (move-task `for_review` recovery), #2338 (orchestrator-api resolve-workspace + contract 1.2.0 + changelog-symlink cutover + `predict_lane_worktree` SSOT seam); the 2026-07-04 backlog revitalization closed 24 stale issues.

**Since census (2026-07-05): mission `ci-topology-shrink-01KWQAVX` SHIPPED (all 6 WPs done)** — a concrete instance of #1931's standing campsite epic folding into a mission (see dependency spine, above), and built directly on the Wave 0 marker→job substrate (PR #2368, above). It delivers **all three #1931 pillars in one pass**: **shrink** (**#1933** — the 32 previously-unmapped `src/specify_cli` dirs folded into six named composite `dorny/paths-filter` groups: `auth_audit_git`, `lifecycle`, `agent_surface`, `closeout`, `governance`, `platform`), **split** (**#2378** — `fast-tests-core-misc` divided into two disjoint matrix shards), and **un-blind** (**#2383** — the `arch-adversarial` guard de-serialized off the `fast-tests-core-misc` critical path: `if: always()` (100% of `src/`, no filter-group gating) plus a dropped `needs` edge — path collapses `sum`→`max` toward the ≤13.6-min ceiling). Also fixed in-flight: the pre-existing `mission-loader-coverage` C-005 coverage-drop (silently absent from `sonarcloud.needs`). Gate-coverage ratchet refreshed: `total_tests` 28573→28709, `duplicate_test_count` 3550→707, `orphan_test_count` 0. Closes #2378, #1933, #2383 under #1931. **SHIPPED — merged as PR #2391 (2026-07-05); #2378/#1933/#2383 CLOSED.** A follow-up LOC-insensitive census-freshness gate landed via PR #2425 (#2416, 2026-07-06) so the topology census can't red on unrelated LOC churn.

  *Discoveries worth carrying into future #1931 slices:* (a) a freshness/coverage invariant that derives its expected set from the **live**, mission-mutated tree is self-emptying once the mission's own change lands — WP01 hit exactly this (the worklist-vs-mapped-dirs check became mutually unsatisfiable post-WP03) and the fix is to derive against a **frozen pre-mission baseline** instead; (b) the mandatory full `tests/architectural/` sweep at closeout caught 4 stale sibling contract tests (`test_ci_quality_path_filters.py`, `test_ci_architectural_gate_coverage.py`) still asserting the pre-mission CI topology — per-WP review suites never ran them and would have missed the regression; (c) `if: always()` alone only un-blinds a job, it does **not** de-serialize it — de-serialization needs the `needs` edge dropped separately, and this mission required both moves together to hit the wallclock ceiling; (d) a completeness guard must **derive its scan scope from the surface it protects** — the docs-only trim's first guard hardcoded 2 of the pole's 4 `matrix.paths` roots and ran green while blind to a docs-scanning test in an uncovered root, a false-green caught only by independent review; the fix parses the pole's live roots so the guard can't drift.

  *Backfilled in-PR (both prior residual items now RESOLVED):* the timings artifact carries the live measurement from PR #2391 ci-quality run `28731385584` — measured core-misc critical path **14.4 min** (arch-adversarial pole), a **51% cut** from 29.4; and the escape-hatch honesty-note wording is corrected. The measurement met NFR-001's binding 55% bound (14.4 ≤ 16.17) but the arch pole came in heavier than projected (14.4 vs ~12.3), so it sits just over the aspirational ~13.6-min next-lane sub-target.
  *Follow-up (P1, #2397 — under #1931): **RESOLVED.*** Matrix-sharding the `arch-adversarial` pole — post-de-serialization the single un-sharded critical-path bottleneck on every code PR — **landed via PR #2405 (2026-07-05, closes #2397)**, bundled with a charter-path CI hotfix. This applied the `fast-tests-core-misc` sharding pattern to the arch pole, the remaining lever to bring the path under the ~13.6-min next-lane sub-target. Same invariant surface (`always_on_arch_present`/`differential_arch_matrix`, `test_arch_pole_deserialized`, FR-006).
  *Also landed in #2391:* a **docs-only trim** on the always-on pole — a docs-only PR runs only the docs-relevant arch guards (`-m docs_scoped`, seconds) instead of the full ~14.4-min suite, while preserving doc-terminology/doc-scanning coverage (the terminology guard scans `docs/`).

**Landings since 2026-07-05 (verified merged to `main`):** a DevEx/CI-hygiene batch landed on 2026-07-07 on top of the ci-topology/arch-shard work above — **PR #2444** (SonarCloud QA config: `projectVersion` + coverage-scope alignment + read-only token; closes **#2421/#2422** under the Sonar-debt epic **#1928**), **PR #2438** (auto-scoped review-time regression gate at `move-task --to for_review`; closes **#572** — this is the factor-(c) *dynamic* half of the review-time boundary), **PR #2442** (local pre-PR CI parity + factor-(a) verify; closes **#2283** Phase 3), **PR #2429** + **PR #2433** (session-scoped test reaper + per-mission `/tmp` prompt namespace + workspace-context tombstone, and timing-isolation of the WP-prompt latency NFR; close **#1842/#2032** under **#1931**), **PR #2449** (review-prompt retention #2439 + coverage-allowlist repoint #2443; both CLOSED, epic #1931), and **PR #2452** (changelog backfill). The finalize-tasks glob-`owned_files` fix (**#2446**) is landing via **PR #2454** (still OPEN as of 2026-07-08). Two boundary tickets were newly filed in the process and remain OPEN: **#2441** (contract-ownership boundary — shared contracts + their retirement are not a modeled, owned artifact) and **#2447** (phantom `core/mission_detection.py::_detect_from_branch()` still referenced in shipped doctrine) — see Watch items.

**Hot list:**

- **P0 (4 open in milestone as of 2026-07-08; #2346 CLOSED 2026-07-04):** #2160 (coord artifact authority — the class the Wave 2 trio closes), #2071 (test-QA epic), #1676 (deterministic structured authoring — verified 2026-07-04: carries **zero native dependency edges**, so it sits entirely outside the spine; it needs an explicit scheduling decision, see exit criterion 7), #1619 (the program root). The former fifth, #2346 (move-task subtask-guard regex leak — launch-blocker), was closed as the post-mission op.
- **P1s from the 2026-07-04 sweep — pulled into 3.2.x (operator critical-path ruling, 2026-07-04):** #1239 (retrospect synthesize rejects its own create records), #1231 (stale-WP indicator: shell_pid liveness), #1734 (in_review→approved guard forces `--force` on standard review flows), #825 (restore push-time SonarCloud — CI hygiene).
- **Clusters (open-issue labels):** workflow 54 · reliability 50 · tech-debt 45 · bug 40 — consistent with a stabilization cycle: two-thirds of the open book is reliability/workflow/debt, not new surface.
- **#2392 (new, P1, child of #1619)** — "upgrade-worktree coherence" consolidation epic: one canonical fix for state/gitignore propagation across coord/lane/main, replacing what was trending toward N single-path partial fixes. Members: #2385 (`_auto_commit_upgrade_changes` main-only scope leaves sibling worktrees dirty, tripping the merge NFR-002 guard), #1873 (`_upgrade_worktrees` skips saving synthesized metadata when detected version == target), #2105 (main-checkout commit-set completeness — largely STALE per the design, since the git-status-derived commit-set is already implemented for main; residual is scope-only). #2367 is fenced as partly separate — one invariant at three seams, not one code fix: #2367-A (vcs-lock) was a deliberate stop-gap for a race (#2222/C-003; committing it would reverse that call) and #2367-B (rollback stale status) lives in the merge-snapshot path, not the upgrade helper.
- **#2400 (new, P1, sub-epic of #1799)** — "metadata & profile authority" consolidation epic: single canonical source, *structurally enforced*, across WP frontmatter, the event log, and invocation-time profile loading — same defect class as #2364 (model-discipline rule bound only as a dispatch-time prompt instruction). Members: #2399 (structurally enforce agent-profile loading across all four invocation contexts — ops/ad-hoc/dispatch/mission-WP) and #2093 (WP-metadata authority split — static design-intent stays frontmatter-canonical; dynamic runtime state, incl. `agent`/`shell_pid`/`history`/reviews, retires to event-log/invocation authority, generalizing the `lane` retirement; architect DECISION already rules it REWORK-staged). Related slices, not reparented: #1841 (WP-claim Python profile-load), #1840 (skills subagent-delegation). Mutual coupling: splitting `agent_profile` (#2093) is the precondition for #2399's enforcement; #2399's resolve→materialize→record seam is the mechanism for #2093's dynamic side — sequence together.
- **#2519 (new, P1, G1 charter/doctrine)** — "charter authoring & lifecycle robustness" epic: the consume-and-govern paths for charter/doctrine are solid; the **author, observe, and reproduce** paths are thin. Surfaced while authoring the `mission-wrap-up-sequence` procedure + `DIRECTIVE_046` directly against `src/doctrine/`. Sibling to #2466 (extensibility/packs) from the first-party/maintainer side; **outside the blocking spine** (a G1-depth epic, not a #1619/#1797 dependency). A pre-spec research squad (2026-07-10) found the three original children collide on one un-owned defect — the activation surfaces (`config.activated_*` ↔ `answers.selected_*` → `references.yaml`/`graph.yaml`) are disjoint ledgers with no reconciler — so a **foundation slice #2526** is carved out as the prerequisite. Members: #2526 (**Slice 0 · foundation, prerequisite** — reconcile `config.activated_*` ↔ `answers.selected_*`, make `activate`/`deactivate` write-through or `--resynthesize`, extend `consistency_check` to config↔answers↔references parity; unblocks + de-conflicts B and C; the divergence bit PR #2524), #2520 (charter **domain events** `CharterCreated`/`CharterUpdated`, open payload, through the existing CLI sync/SaaS event path — no charter lifecycle event exists today; spans repo-local emit wiring + external `spec_kitty_events` contract + SaaS consumer; SaaS-emit sibling of #2518), #2521 (charter-init **harness-freshness preflight** + deterministic intake inputs — notes a future `charter discovery/update` custom mission type as the long-term vehicle), #2522 (**doctrine-authoring surface** — a `charter author` scaffold + maintainer how-to for the edit-built-in → regenerate `graph.yaml` → freshness-gate loop, currently reverse-engineered). Shared seams: `charter.activation_engine.commit_plan`/`_save_config`, `src/doctrine/graph.yaml` generation, the charter-init/intake flow — sequence **#2526 → #2522 (C) → #2521 (B) → #2520 (A)** (A∥B safe-parallel; A∥C and B∥C must sequence on the shared activation/derivation surfaces). Member issues milestoned 3.2.x + P1 (2026-07-10); full declaration entry in [`docs/release-goals/3.2.x.md`](../changelog/3.2.x.md) under G1.

## Exit criteria for 3.2.x

Derived from the epics' own done-conditions; the milestone closes when all hold:

1. **#1868** — all six seams bound to a type/owner: WS1–WS3 done; **WS5 done — landed with Wave 0** (marker→job authority, fails closed, PR #2368); WS4 daemon identity and WS6 versioned-contract ADR complete via Waves 3–4.
2. **#2173** — Phase-1 canonicalizer gate ✅ (#2164 closed); **Phase-2 `MissionResolver` port** owning the single `kitty-specs/` walk lands; Clock consolidation and `InstalledVersion` routing complete. No over-injection; frozen `MissionExecutionContext` never carries adapters.
3. **#1797** — shim registry stays `shims: []`; `category_b` honest baseline (215) burned down per Wave 4; the filed unshim children (category sweeps, orphan triage) all closed.
4. **#2071** — audit children (CT1 #2072, CT2 #2073, CT3 #2074, CT4 …) remediated; test-hygiene directive + ratchet in force so the suite is scaffold again (CT8/CT9 already shipped via gate-substrate PR #2317).
5. **#1619** — one canonical `ResolvedMission`/`MissionExecutionContext` minted per invocation and consumed by claim/implement/review/finalize/status/runtime/orchestrator; the dual `target_branch` readers, mid8 fabrications, and S8 silent glob deleted; ambiguity always structured, never silent.
6. **#1746** — Mission Clarity Layer delivered (SI-01…SI-10: mission-card.json, README generation, EMI header injection) as the cycle's functional capstone.
7. **P0 book empty** — #2346 fixed; #2160's class closed by the Wave 2 trio; #1676 resolved or explicitly re-milestoned with rationale.
8. **Non-spine open book dispositioned** — the remaining milestoned issues outside the spine (the reliability/workflow clusters) get an explicit close-or-re-milestone pass; nothing rides into 3.3.x silently.

## Risks / watch items

- **#2339 — two-authority migration-id conflict — RESOLVED (CLOSED 2026-07-06).** The upgrade dry-run JSON contract that rejected dotted `migration_ids` (first live offender: `3.2.0rc45_retire_standalone_skill_surface`) was fixed by widening the contract pattern; it no longer reds local runs. It was the two-authority failure class Decision 8 of the suite-map mission (PR #2368) exists to prevent; the fix confirms that class is being paid down rather than accreting.
- **#2342 — quarantined perf test pending verdict (still OPEN 2026-07-08).** The retrospective 200-mission 5s NFR breach on CI (`test_200_missions_under_5s`) remains unadjudicated (real regression vs CI flake); the quarantine lane must not become a permanent parking lot. (Distinct from the WP-prompt-latency NFR flake #2032, which was timing-isolated and CLOSED via PR #2429/#2433.)
- **#2345 / #1790 — dedup decision MADE; #1790 still OPEN.** The dedup was resolved by picking **#2345** as the canonical ticket (CLOSED 2026-07-05 — bind the `occurrence_map_complete` guard at plan/tasks-finalize so bulk-edit schema errors fail before implement). Its sibling **#1790** (validate `occurrence_map.yaml` at authoring + add a rich-occurrences schema example) remains OPEN and should be dispositioned as the authoring-side residual rather than re-litigated as a duplicate.
- **Milestone-drift on critical-path items** — resolved for the known set on 2026-07-04 (#1239/#1231/#1734/#825 and #2034 all pulled into 3.2.x by operator ruling), but the class remains live: a critical-path issue filed without a milestone silently escapes the burn count. The sub-issue milestone sweep (executed 2026-07-04, see next steps) is the standing counter-measure.
- **#2071 children are audit-fed.** The epic forbids pre-creating children; exit criterion 4 has open-ended scope until the audit's ticket set is complete. Watch for scope creep into #1931 territory (hygiene items belong in the campsite epic, not the blocker).
- **#1797 ↔ #2071 intra-pair sequencing (tidy-first enabler).** The spine lists #1797 (degod/unshim) and #2071 (test-QA) as peer blockers of #1619 but leaves their *relative* sequencing implicit. Ruling ([`qa-tidy-first-sequencing.md`](testing/qa-tidy-first-sequencing.md)): they are **not merely parallel** — a **targeted** subset of #1797 is a cheap enabler of #2071, while the bulk stays independent. Only *structure-induced* test friction (fragile-because-god-module, per the [CaaCS co-change ranking](testing/test-change-coupling-caacs.md)) is cheapened by degod; *test-intrinsic* friction (CT3/4/5 #2074/#2075/#2076, CT7 #2564, quarantine #2295/#2309/#2342, legacy-contract #2553/#2323) is not. Do **not** gate #2071 behind the full degod program. Order: (1) a small dead-code/deshim sweep first (`#2463`, `#2293`, `#2499`, `#2561`, + the `#2559` dead-code-gate tooling) — it deletes code *and its tests*, near-zero risk; (2) fold CaaCS-implicated god-surface degod **into** the QA mission as campsite-first WPs (route full decompositions `#2059`/`#2057`/`#2056`/`#2532` to their own #1797 slices); (3) fix genuinely-clean-but-badly-written tests directly.
- **Wave-numbering homonyms — confirmed, not hypothetical.** Mission names and the roadmap's Wave 0–4 are distinct namespaces: PR #2308 is literally titled "Wave 2 tasks.py degod" yet delivered the roadmap's **Wave 1**, and "Unshim Wave 1/2" (PRs #2325/#2328) map to roadmap Waves 1∥/2∥ (plus the Wave-3 category_7 slice in #2325). Anchor all status claims to issue/PR numbers, never wave labels.
- **Avoid multi-path split-brain bugfix.** #2385/#1873/#2105 are the same underlying defect (upgrade-run auto-commit doesn't cover every touched checkout) surfacing at different call sites; fixing them independently risks exactly the kind of divergent-husk split-brain regression this milestone is paying down elsewhere. **#2392** is the counter-measure: one canonical `commit_touched_checkout` seam, applied symmetrically, instead of N partial patches. PR #2387 (an earlier single-path attempt) was redirected to `pr:needs-revision` for this reason — it should be re-pointed at the #2392 design rather than landed as-is. #2367's two seams (#2367-A vcs-lock stop-gap, #2367-B merge-snapshot rollback) are deliberately kept OUT of the consolidation and tracked separately.
- **Instructed-not-enforced / metadata split-brain.** #2399 and #2093 are the same "canonical authority exists in name, bound only by prompt instruction or hardcoded frontmatter copy" defect class as #2364 (dispatch-time model-discipline rule) and the sibling framing epic #1868 (different concrete domain — package layering, mission identity, guard capability, daemon identity, CI suite map, versioned contracts — not agent-profile/WP-metadata authority). **#2400** (P1) is the counter-measure, clustering #2399 + #2093 under one sub-epic instead of three unrelated parent epics (#2399 was under #1799 alone; #2093 under #1676; the WP-claim slice #1841 and doc-only companion #1840 under #1808). The pair is mutually coupled, not independently sequenceable: land #2093's intent/binding split and #2399's resolve→materialize→record mechanism together, or the half that lands first has nothing to bind against.
- **Runtime-state eviction ↔ #2160 `shell_pid` writer collision (new, 2026-07-16).** #2400's new build mission **#2684** (runtime-state eviction) moves the `shell_pid` claim off `WP##.md` into the event log, but that claim is written at **4 sites** that overlap #2160's Wave-2 `implement.py`/`workflow.py` degod — `implement.py:1730`, `workflow_executor.py:669` (implement) & `:1337` (review), and `tasks_move_task.py:1638` (**`move-task`**, the primary lane-transition writer, initially undersized out of the eviction's scope). The eviction's `shell_pid` move must **co-sequence with (or land behind) the Wave-2 trio degod**, not race it; a native `blocked_by` edge #2684 → #2160 records the ordering. Also load-bearing in #2684: the ADR must pin whether runtime state that mutates **off the transition axis** (resume `shell_pid` refresh, mid-work subtask marks, activity-log notes) gets a non-transition self-edge event class, or folds onto existing transitions with a documented staleness-fallback behavior change. Scope + the authoritative squad corrections live in `wp-op-schema-design/docs/plans/investigations/wp-runtime-state-eviction-scope.md`.
- **Contract-ownership + doctrine-phantom residue (newly filed 2026-07-07, both OPEN).** Two tickets surfaced while landing the DevEx/CI-hygiene batch above. **#2441** — *contract-ownership boundary*: shared contracts and their retirement are not a modeled, owned artifact, so a WP can break a contract pinned by a test outside its `owned_files`; #2438's `pre_review_gate` catches the *dynamic* symptom at review time but the *static* ownership half is still unmodeled — needs a scheduling/scope decision (likely under #1868's seam-binding). **#2447** — *doctrine phantom*: the removed `core/mission_detection.py::_detect_from_branch()` is still referenced in shipped doctrine (`git-operations-matrix.md`), the prose sibling of the #2443 coverage-allowlist repoint (which fixed only the CI-config reference). Small, self-contained doc fix; fold into the next #1931/doc-hygiene slice rather than tracking standalone.

## Immediate next steps

1. **Wave 0 — ✅ done**: PR #2368 shipped (`ci-suite-map-bind-01KWNPMP`), closing #2034, #2333 (folded in-mission), and #2283 factor (a) — factors (b)/(c) remain under CT7 (#2077).
2. **Post-mission op — ✅ done**: P0 #2346 fixed (CLOSED 2026-07-04).
3. **Then the Wave 2 degod trio** (workflow.py / implement.py / acceptance) against the now-bound suite map, closing the #2160 class — still the next degod slice (#2160 OPEN).
4. **Keep milestones consistent downward** — ✅ executed 2026-07-04: the spine epics' sub-issue trees were swept (33 children assigned 3.2.x, 48 already correct, zero unexplained drift); the surviving deviations are all evidenced (#1711/#1709/#1710 at 3.3.x by operator batch; the Beads epic #1168 deferred to 3.3.0). The retired 3.2.1 milestone was closed and its last resident (#1716) folded into 3.2.x. Re-run the sweep whenever the spine gains children.
