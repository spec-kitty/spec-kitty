---
title: '3.2.x Open-Core Delivery Plan'
description: 'PO-facing 3.2.x synthesis: a verified status re-read, the open-core breaking-change delivery strategy, and the bounded remaining-work sequence.'
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/external/product-manager-evaluator.md
related:
- docs/plans/3-2-x-approach.md
- docs/plans/3-2-x-milestone-roadmap.md
- docs/changelog/3.2.x.md
- docs/development/how-to/manage-issue-tracker.md
- docs/plans/domains/doctrine-charter-domain-plan.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---

> **Superseded (2026-09-06, Convergence #3881).** This plan describes the pre-convergence
> line, including the since-removed local sync daemon / delivery / import-history surface.
> It is kept as a historical record. The active-cycle plan of record is the
> [4.0.0 Milestone Roadmap](4-0-0-milestone-roadmap.md); the
> [3.2.x Milestone Roadmap](3-2-x-milestone-roadmap.md) is the prior-cycle record.

# 3.2.x Open-Core Delivery Plan

> **Related domain plans (durable throughlines):** this plan is the release-scoped, PO-facing view. Its "SaaS" scope is the open-core doctrine/charter split (see the [Doctrine & Charter — Domain Plan](domains/doctrine-charter-domain-plan.md)); the hosted product surface and its P0 cluster lived in the SaaS & Hosted Sync domain plan (retired 2026-09-06 (Convergence #3881): the hosted-sync surface re-homed to the authoritative upstream repos; see the convergence-retirement ADR), which this plan's remaining-work table does not cover.

*Synthesis for the product owner, 2026-07-30. Supersedes the "G2 is the blocking
spine / G1 is off-spine" framing of the [milestone roadmap](3-2-x-milestone-roadmap.md)
where the two disagree — see [Status re-read](#1-status-re-read-verified). Status
verified against remote `main` (`b04da00e1`) by two read-only audits on 2026-07-30;
load-bearing claims carry file/issue evidence, and every unverified claim is marked.*

## TL;DR for the PO

- **3.2.x is far more done than its roadmap shows.** The structural "brain surgery"
  — moving the core domains onto single sources of truth, and making the doctrine
  layer drive the runtime — is **substantially landed**. The roadmap reads "spine
  idle" only because the work landed under different issue numbers than it tracks.
- **What actually remains is a small, bounded set** (§3): close the charter's
  "back doors" so it's the single entry point; lift the already-packaged built-in
  doctrine into its own module; build the still-design-only schema (Creed / Values /
  the signed relationship model); one parked refactor; and recover the release gate.
- **The delivery strategy is an open-core breaking-change window** (§2): ship the
  breaking + design changes **as soon as possible** to a small, known, consenting set
  of early-adopter consumers, **without ever stalling P0 fixes**, and make each break
  cheap to absorb. There is **no hard freeze** — we engineer our way to "no longer
  noticeably impacts downstream," we don't schedule it.
- **One honest caveat up front:** `main` is **not release-ready** — CI has been red
  for 10+ consecutive runs (partly by the red-main-is-honest policy, partly TBD). See
  [Release posture](#15-release-posture--not-tag-ready).

---

## 1. Status re-read (verified)

The milestone roadmap (last substantive pass 2026-07-04 / -17) predates the work that
actually delivered the milestone's goals. Re-audited against the code and tracker on
2026-07-30:

### 1.1 G1 — doctrine/charter/DRG drives the runtime: **the capability is BUILT and ACTIVE**

- **Mission-types-as-doctrine ships today.** `research`, `software-dev`, and
  `documentation` (plus `plan`) resolve through the charter → mission-type-profile →
  runtime path. The **entire data plane is doctrine-sourced** — governance profiles,
  per-action indices, step contracts, templates, expected-artifacts, step prompts, and
  the DRG identity node are 100% overlayable YAML/MD under `src/doctrine/missions/`
  (built-in → org → project). `resolve_step_contract_ids()`
  (`src/doctrine/missions/step_contracts.py`) is the *sole* step-contract authority —
  no `specify_cli` copy. Only the **execution engine** (per-type state machine, gate
  handler dispatch, an action-sequence YAML fallback) is still in code.
  - *Correction to the roadmap:* earlier framing called mission-types-as-a-doctrine-kind
    an unbuilt "keystone." It is built. G1's done-signal is **demonstrated
    doctrine→runtime governance** — already true and observable in the three shipping
    types — not "a pack-split epic is 100% complete."
- **The one real G1 gap: the charter is not yet the *sole* door — now substantially
  closed.** Mission `charter-sole-door-bypass-closure-01KZ3WAA` (landed 2026-08-04) ran
  the scoping pass this section originally flagged as missing, and confirmed the closed
  set below is real, not a point-in-time grep. *(Door count: the mission's own Phase-0
  scoping pass corrected this plan's ~22 grep estimate down to ~20 — the mission's
  `spec.md` and the CHANGELOG both cite ~20 as the confirmed count; treat ~20 as
  authoritative going forward, not an average of the two figures.)*
  - *Closed by this mission:* every enumerated direct-construction and `._inner`
    reach-around bypass around the charter's `DoctrineService` factory — direct
    `AgentProfileRepository(...)`/`doctrine.service.DoctrineService(...)` construction
    across runtime/review/invocation, plus two `._inner` attribute reach-arounds (a
    third, `profiles_cmd.py:117`'s `object.__getattribute__` spelling, was surfaced by a
    gate this landing pass widened). Activation gating extended from 3 of 10
    doctrine-artifact kinds to all 9 charter-activatable kinds plus the `mission-type`
    token — note honestly that `mission-type` gating itself *pre-existed*; this mission
    verified it and added regression coverage rather than building it new. The two
    previously-divergent "canonical" builder functions unified onto one
    (`charter.doctrine_service_builder.build_activation_aware_doctrine_service`), and a
    triplicated missions-root hardcode consolidated onto
    `MissionTemplateRepository.default_missions_root()`. Five zero-tolerance AST/qualname
    architectural gates (one per bypass category) ship the durability guarantee, widened
    during landing with 35 injection tests.
  - *What "closed" means, precisely:* the enforceable invariant shipped is **Policy A** —
    "a raw service never escapes its acquisition site unwrapped" — which carries **zero**
    exclusions and covers builder *calls* as well as constructions. **Policy B** (one
    single constructor for every acquisition) remains the aspiration and still carries
    named locality exclusions. The mission proves Policy A, not Policy B; the two are not
    the same claim and should not be conflated when reporting this as "done."
  - *Residual, honestly bounded — not the full door list:*
    `doctrine.template_catalog.resolve_template_by_id` (5 importers);
    `specify_cli/runtime/resolver.py`'s tier-1–4 reimplementation; `runtime/home.py`'s
    `importlib.resources` root lookup (a 4th resolution path for the same root); three
    root-relative missions-root duplicates (`src/kernel/paths.py`,
    `src/specify_cli/template/manager.py`,
    `src/specify_cli/cli/commands/charter/list_cmd.py`); one escalated
    `AgentProfileRepository` site (`tool_surface/profiles/projection.py`, tracked #3176);
    and the two `.kittify/profiles` sites, deliberately out of scope per the mission's own
    C-006. Sequenced follow-ons: #3176, #3091, #3022, #3101.
- **Creed / Values / signed relationship model — still ahead.** Creed and
  Foundational-Values exist **as design docs only, not in code**. The signed `impacts`
  relation (ADR [2026-07-26-3]) is **accepted but unimplemented**; note that
  `in_tension_with` already exists as a *full symmetric* DRG relation, so this is a
  fold-and-extend, not a from-scratch build.

### 1.2 G2 — strangle the core domains onto SSOTs: **substantially DELIVERED**

- The execution-context SSOT lives in `src/mission_runtime/`; the Strangler migration
  relocated `resolve_action_context` there and **deleted** the old
  `core/execution_context.py` (removed, not shimmed — no parallel resolver survives).
  Naming/identity derive once; the identity primitive moved to the lower layer.
- Read / write / coord authority each sit on the SSOT with **measured, gated** residual
  bypasses (6 read / 12 write, per the seam doc's honest-bounds table) — not hidden
  shadow paths.
- **Degod/unshim is largely landed, not idle:** shim registry drained to `shims: []`;
  the coord-authority trio degod is done (`workflow.py` / `review.py` reduced to 0 LOC);
  `runtime_bridge` decomposed. The one remaining god-module is `_read_path_resolver`
  (~1677 LOC), explicitly parked for its own scoped mission.

### 1.3 G3 — DevEx enablers: **substantially delivered**

CI is sharded by domain; the architectural-adversarial pole is de-serialized into an
always-on parallel job; the `-m unit`/`-m contract` selection gap is closed;
non-vacuity gate twins and shrink-only ratchets are pervasive and enforced; the
zero-producer / inert-slot silence guards landed this cycle.

### 1.4 The traceability gap (the roadmap's real defect)

The placement-seam work **is** the delivery of the named spine — filed under new
numbers the roadmap never adopted:

| De-facto work (landed) | Delivers the named spine epic |
|---|---|
| #2906 read-side · #2841 write-side · #2917 birth-cutover | **#1619** execution-context unification |
| #2884 · #2262 · MissionResolver port | **#2173** infra-port binding |
| coord-authority trio degod · runtime_bridge decomposition | **#1797** degod/unshim delivery |

Because burn-down keys on #1619/#1797/#2173 and those show as open parents, the
milestone *looks* stalled while it is in fact largely delivered. This is the exact
inverse of the roadmap's own "anchor to issue numbers" watch item — **the anchors went
stale.** The fix is re-anchoring (§3, item R), not more work.

### 1.5 Release posture — **NOT tag-ready**

`pyproject` = 3.2.6; the Unreleased changelog is rich (asset kind, silence guards,
CLI UX, import-history, fork hooks). But **`main` CI Quality has been red on every run
for 10+ consecutive pushes (2026-07-28 → 07-30), 9 failing jobs including the
release-gating `regression tests (blocking)`.** Red CI is the release authority
([ADR 2026-07-17-1]); the baseline P0 pins (#2736/#2772/#1834) are intentionally red.
- **Open item (unverified):** whether all 9 red jobs reduce to those known baseline
  pins, or include a fresh regression from the write-side-seam landing. **This must be
  resolved before any tag conversation** — it is the difference between "honest baseline
  red, tag when the P0s clear" and "we shipped a regression."

---

## 2. The delivery strategy: open-core breaking-change window

### 2.1 Organizing principle

3.2.x is the **last permitted breaking-change window** for the doctrine/charter
surface. The goal is not "finish the doctrine system" — it is **draw the
consumer-facing seam and get every breaking change through it**, so a small set of
consenting early-adopter consumers absorbs the churn once and then lives on a stable
surface. The success metric is *"the seam is drawn and the breaking changes are
spent,"* not feature-completeness.

### 2.2 The done-bar (operator-stated)

1. **All provisioned assets reachable by the runtime *through the charter* — charter
   as the sole door.** This is a *no-bypass* condition: any path that reaches assets
   around the charter is a second seam that leaks internals and forces a *second*
   break later. (Concretely = close the ~22 doors in §1.1.)
2. **Active and consumer-usable is the bar.** Internals may shift freely; the **entry
   points and usage must stay consistent and stable**. You cannot promise a stable seam
   you have not enumerated and versioned — so enumerating the consumer surface (charter
   access path, CLI verbs, pack/manifest layout, resolution API) *is* the stability
   contract, and doubles as the fix for the traceability problem: once the consumer
   contract is the tracked artefact, internal churn stops being externally visible.
3. **Built-in artefacts extracted from `src/` into a root-level module.** Good enough
   for the current version; a later move to a **separate repo happens transparently**
   for consumers because they already consume across the boundary. *Verified: this is
   ~90% done structurally — `src/doctrine/pyproject.toml` already declares a standalone
   `spec-kitty-doctrine` v1.0.0 with kernel-only deps, guarded by a layer test. The one
   blocker is a charter↔doctrine import cycle (two misfiled function-local imports in
   `agent_profiles/repository.py`); resolve it and the lift mirrors the
   runtime/events/tracker cutover already done.*

### 2.3 Dual-track, no hard freeze

- **P0 fixes for early adopters flow continuously and are never stalled.** Drawing the
  module boundary *protects* the P0 lane — once built-ins live behind the boundary, a
  P0 fix lands in one place instead of being re-landed on both sides. Do the boundary
  extraction **in-place on `main` via small strangler steps** (move → shim → repoint →
  delete), **never a long-lived branch** that diverges from the P0 stream.
- **"No longer noticeably impacts downstream" is engineered, not scheduled.** A break
  stops being noticeable when it is **(a) auto-migrated and (b) deprecation-shimmed.**
  With both, breaks can ship continuously and still feel stable.

### 2.4 The "minimal-hurt" machinery (for the small, consenting consumer set)

1. **Every schema break rides the migration rail** (`spec-kitty migrate …` +
   doctor/upgrade framework): a pack-schema change ships *with* the codemod that moves
   a consumer's pack forward — adapting is "run one command," not "read a diff."
2. **Deprecation shims, not hard cutovers:** land the new path, keep the old working
   with an in-band warning naming the replacement + removal version, remove a cycle
   later. The warning is the communication (seen at runtime, not only in release notes).
3. **A versioned contract + one predictable migration-note stream** the consumers can
   pin against and watch.
4. **Batch the consumer-visible breaks; stream the invisible ones.** The real cost is
   *adaptation-event count*, not speed: cluster consumer-visible breaks into a few
   deliberate, pre-announced adaptation points, and hand the named consumers an **RC to
   test each break before it reaches a stable tag.** With a handful of known consumers
   this is a heads-up message + a pre-release — a relationship, not a broadcast.

---

## 3. Remaining work, sequenced

The re-audited backlog is small and mostly known. Ordered so each step de-risks the
next; **P0 fixes run continuously alongside all of it.**

| # | Work | Why here | Verified state |
|---|---|---|---|
| **R** | **Re-anchor the tracker** — adopt the placement-seam swarm as executing children of #1619/#2173/#1797; re-score the milestone against real coverage; reconcile this plan / the approach doc / the roadmap so "doctrine-first" is canonical and the spine reflects reality. | Cheapest, highest-value: makes 3.2.x *measurable* again. Prerequisite to any honest PO burn-down. | Pure tracker/doc work. ~½ day. |
| **0** | **Resolve the CI-red question** — classify the 9 red jobs: baseline P0 pins vs fresh write-side-seam regression. | Gates every release conversation; distinguishes "honest red" from "shipped a bug." | Unverified today — needs per-job failed-test logs. |
| **1** | **Boundary extraction** — resolve the charter↔doctrine import cycle, lift built-ins into `spec-kitty-doctrine`, in-place via strangler steps + import shims. | Lowest-risk break; removes the P0/restructure rework collision; unblocks the transparent repo split later. | **LANDED** — mission `doctrine-built-in-seam-consolidation` (2026-08-02): one fail-closed built-in doctrine location seam, `packs/built-in` relocation complete. |
| **2** | **Charter-as-sole-door** — close the ~20 bypass doors so all provisioned assets resolve through the charter. | The G1 done-bar; the *no-bypass* half of the stability contract. | **Substantially LANDED** — mission `charter-sole-door-bypass-closure-01KZ3WAA` (2026-08-04) ran the confirming scoping pass this row's caveat asked for (the ~22 grep estimate is corrected to a confirmed ~20 — see §1.1), closed every enumerated `AgentProfileRepository`/raw `doctrine.service.DoctrineService` construction and `._inner` reach-around, unified the two divergent "canonical" builders, extended activation gating from 3/10 to all 9 charter-activatable kinds plus the `mission-type` token, and shipped 5 zero-tolerance architectural gates. This proves **Policy A** ("a raw service never escapes its acquisition site unwrapped," zero exclusions) — not the stronger **Policy B** (one single constructor), which still carries named exclusions; see §1.1 for the distinction. Residual doors — `resolve_template_by_id`'s 5 importers, `runtime/resolver.py`'s tier-1–4 reimplementation, `runtime/home.py`'s importlib-resources root path, three root-relative missions-root duplicates, and one escalated `AgentProfileRepository` site — are sequenced as #3176/#3091/#3022/#3101. Mission `charter-pack-usage-journey` (2026-08-02) remains unrelated hardening of the *existing* door, not part of this closure. |
| **3** | **Enumerate + version the consumer surface** — charter access path, CLI verbs, pack/manifest layout, resolution API. | Turns "stable entry points" from aspiration into a checkable contract; the tracked artefact going forward. | New work; small once #2 lands. |
| **4** | **Schema build** — signed `impacts` relation (fold `in_tension_with` in), then Creed + Foundational-Values. | Schema-shaping = a consumer-visible break → must land *inside* the window, schema-first, then migrate content, then the batched adaptation point. | `impacts` = ADR-accepted, unimplemented; Creed/Values = design-only. |
| **5** | **Parked degod** — `_read_path_resolver` (~1677 LOC) as its own scoped mission. | Independent of the doctrine work; not a rider. | Known, parked. |

**Sequencing rule for the breaks:** boundary (1) → sole-door (2) → contract (3) → schema
(4), with the content migration and its batched, pre-announced adaptation point last.
Schema-first, freeze-last — landing that order backwards is the one way the strategy
fails (you'd promise stability, then break it).

---

## 4. Consumer communication plan

For the small, known, consenting early-adopter set:
- One **"held/adapting until <adaptation point>"** note per consumer-visible break —
  not silent staleness.
- Each break ships **codemod + deprecation shim + a migration note** in the single
  contract-version stream.
- **RC pre-release** to the named consumers before each break reaches a stable tag.
- Cluster breaks into **as few adaptation points as possible** — a consenting consumer
  would rather adapt once to five coordinated changes than five times to one.

---

## 5. Open decisions for the PO

1. **Sequencing of the breaks into tags** — the version numbers (3.2.6 / 3.2.7) are
   urgency signals, not commitments. Confirm whether the boundary (item 1) and the
   schema (item 4) ship as one adaptation point or two.
2. **CI-red disposition (item 0)** — is red-main-is-honest acceptable to hold through
   the window, or do we want a green-able baseline before the first consumer-visible
   break?
3. **Charter-sole-door scope (item 2)** — **resolved.** Mission
   `charter-sole-door-bypass-closure-01KZ3WAA` ran the scoping pass, confirmed ~20 doors
   (not ~22), and closed the enumerated set per §1.1/§3 item 2. Remaining decision: whether
   the residual doors (#3176/#3091/#3022/#3101) ship as their own missions now or wait
   behind the schema work (item 4).
4. **`_read_path_resolver` (item 5)** — spec now as an independent mission, or leave
   parked behind the doctrine work?
5. **Consumer roster** — confirm the named early-adopter set that receives RCs and
   migration notes.

---

*Method: two read-only status audits (G1 doctrine/charter; G2/G3 + release posture),
each grounded independently in the code and the live `Priivacy-ai/spec-kitty` tracker,
2026-07-30. Unverified items are flagged inline and gathered as open items in §1.4,
§1.5, and §3 item 0.*
