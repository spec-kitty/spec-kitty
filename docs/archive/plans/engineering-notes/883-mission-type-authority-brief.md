---
title: 'Mission #883 Brief: Doctrine as Mission-Type Authority'
description: 'Lead-architect debrief for mission #883 — intent, operator guidance, research, adversarial second opinion, and a conversation transcript for maintainer review.'
doc_status: deprecated
type: explanation
updated: '2026-07-14'
related:
- docs/adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md
- docs/architecture/mission-type-resolution.md
- docs/architecture/mission-system.md
---

# Mission #883 Brief: Doctrine as Mission-Type Authority

> **Retired (deprecated).** Superseded via ADR `2026-07-14-2-doctrine-to-core-mission-type-resolution-unification` and canonical `docs/architecture/mission-type-resolution.md` (#883). Preserved as a historical record.

This brief captures the intent, operator guidance, research, and adversarial
review that shaped mission #883 **before** the spec stage, so maintainers can
review the reasoning that produced
[ADR 2026-07-14-2](../../../adr/3.x/2026-07-14-2-doctrine-to-core-mission-type-resolution-unification.md).
It is a decision record and hand-off, not a design spec.

> Status at time of writing: pre-spec. The ADR is Accepted; `/spec-kitty.specify`
> has not yet run. This brief is the sign-off package for the spec stage.

---

## 1. Executive / lead-architect debrief

**What #883 is.** Issue #883 asks for mission-type governance profiles so
non-software missions (documentation, research, plan) stop inheriting software-dev
doctrine by default. Investigation showed the *mechanism* for mission-aware
governance already shipped (ADR 2026-05-16-1) but the *content* did not — and that
the real problem is larger and structural.

**The real problem (evidence-based).** Per-mission-type behaviour is resolved
through **two parallel trees** (`src/doctrine/missions/` canonical; the live
`src/specify_cli/missions/` derived copies) and **three competing governance
surfaces** (`governance_refs` — inert and dangling; `governance-profile.yaml` —
live but empty; `actions/*/index.yaml` — live and populated), with a hardcoded
`software-dev` default woven through the core loop. A documentation/research/plan
mission that never set `template_set` silently loads software-dev doctrine — the
exact leak the issue fears — live today.

**The decision.** Unify onto one charter-mediated `doctrine → charter → core`
resolution path. Doctrine *offers* mission types (governance, steps, gates,
templates); charter *activates and customises* them; the core FSM *consumes* one
resolved `MissionType`. The `MissionType` doctrine artefact becomes **load-bearing**
— the single answer to "what is this mission type, what steps, what gates?" The
end-state **deletes** `src/specify_cli/missions/`; `software-dev` becomes an
ordinary peer doctrine type. #883 is **slice 1**: governance first, plus one gated
dossier-gate swap that proves the core is measurably less dependent on the
`specify_cli` tree.

**How it was hardened.** A four-lens pre-spec research squad established the map;
an architect converted it to a concrete seam; a second, adversarial four-lens
squad (test-strategy, architecture-refutation, implementer-reality,
slice-discipline) returned a **unanimous REFINE** and corrected four material
overstatements before anything was committed (see §5).

**The one thing to know going into spec.** The dominant risk is the dossier gate
swap: it is a type-boundary crossing (`ConfigResult` ≠ `ExpectedArtifactManifest`)
over content that has **already drifted with `specify_cli` ahead**. It is handled
as a gated, isolated, non-blocking lane — reconcile the doctrine tree upward,
prove the swap user-invisible with a *transitional* parity scaffold, then flip and
delete the copies. No parity ratchet survives the mission.

**Recommendation:** proceed to `/spec-kitty.specify` on the refined design. The four
spec-stage decisions (governance declaration shape, overlay adapter form, artefact
depth, ADR meta) were resolved with the operator in a spec-stage interview (§8);
nothing architecture-level remains open.

---

## 2. Mission intent and north star

- **North star:** `src/doctrine/missions/` becomes the live source of truth; the
  derived `src/specify_cli/missions/` tree is **removed** — a transparent swap the
  user does not notice. `software-dev` becomes a peer built-in doctrine mission
  type; no `software-dev-default` special-casing; the core holds no per-type
  knowledge.
- **The `MissionType` doctrine artefact is load-bearing** — it answers "what is
  this mission type? what steps does it contain? what gates are checked?" Steps
  (action sequence / step contracts), gates (expected-artifacts), and governance
  all resolve *through* it.
- **#883 = slice 1** of a `specify_cli/missions` retirement epic (governance +
  the gated gates/dossier swap). Later slices widen the same seam to templates,
  step contracts, and full gate migration, then delete the tree.

## 3. Operator guidance (chronological)

1. **Kickoff:** start on a shadow-clone sibling, branch off `upstream/main`, begin
   with a research squad; "foundational doctrine feature — warrants additional
   scrutiny and architectural alignment."
2. **Crux decisions:** full consumer merge; fix the leak now; add the per-type
   project override (the charter customise layer); author full governance sets for
   all three non-software types. Clarified the model: *doctrine offers, charter
   activates/customises, core FSM consumes.*
3. **North-star clarification:** the end-goal is to **delete** the specify_cli
   template tree and make `software-dev` a built-in doctrine type feeding step
   contracts, gates, and templates from doctrine → charter → core.
4. **Capture:** "I want this captured as an ADR, and docs/architecture updated."
5. **Second opinion:** "go for sweep" + a second-opinion squad on the refined lens;
   "handle this as the careful consultants / architects we are"; "ensure the test
   suite is regarded as a first-class change surface, not an afterthought."
6. **Dossier scope:** chose the gated, isolated, non-blocking dossier-flip lane.
7. **Swap + testing posture:** the doctrine path (dead code) becomes alive and the
   CLI path is removed **without the user noticing the swap**; parity tests are
   transitional (add at start, delete before merge) — **no surviving parity
   ratchet**; tests verify behaviour and shift to doctrine-module + integration
   level; **do not keep code whose sole purpose is to avoid test-suite churn**; the
   `MissionType` doctrine artefact is to be added/enhanced and become load-bearing.

## 4. Pre-spec research synthesis (four-lens squad)

Full synthesis (with file:line anchors) accompanies the mission; condensed here.

- **Content & prior-art (researcher-robbie):** the mechanism shipped, content did
  not; classified existing doctrine artifacts universal vs software-dev-only vs
  other-domain; found the `DIR-010/DIR-011` dangling-reference defect; identified
  genuine content gaps for docs/research/plan.
- **Resolution architecture (architect-alphonso):** traced the live paths; found
  `governance_refs` inert; found the `template_set`-inferred software-dev leak;
  recommended one charter-mediated resolver bundle and splitting `template_set`.
- **Split-brain / boundary (paula-patterns):** mapped the dual missions-tree; the
  doctrine-side `expected-artifacts.yaml` is a dead read-path; flagged the
  mission-type key has no single canonicalization point.
- **Doctrine mechanism (doctrine-daphne):** `governance_refs` produces no DRG
  edges; `activate mission-type --cascade` is a no-op; designed the non-leakage +
  non-vacuity enforcement test.

## 5. Adversarial second opinion (four-lens squad) — unanimous REFINE

All four lenses affirmed the direction and corrected the ADR's overstatements:

- **Architecture refutation (paula):** the overlay stack is **not "free"**
  (`base.py` skips files without an `id`; the profile has none); the leak is **not
  closed by construction** (`mission.py:575` still defaults to software-dev on the
  dossier path, and charter may not import specify_cli); the dossier flip is a
  type-boundary crossing over drifted content.
- **Implementer reality (python-pedro):** the ADR's named leak anchors point at
  **dead code** — the live leak is `_load_action_doctrine_bundle` (`context.py:865`)
  via `build_charter_context` and `build_charter_context_json`; the "byte-identity
  golden suite" **asserts the fallback being deleted** and must be re-authored; the
  dossier reader returns a different type (`ConfigResult`).
- **Test suite as first-class (reviewer-renata):** the named suite is
  **substring-based, not a byte gate**; produced a test-change ledger
  (STALE/STUB/VALID); found `plan` has no action indices (empty-grain must be
  legitimate, not an error); the non-vacuity twin must resolve the **unioned**
  bundle.
- **Slice discipline (planner-priti):** corrected the WP DAG (SEAM before LEAK),
  split CONTENT ×3 (hides 6–8 net-new artifacts), and isolated the dossier lane as
  detachable and non-blocking.

Every correction is folded into the ADR's decisions.

## 6. Testing posture (operator-mandated)

- Parity/snapshot tests are **transitional** — added at a swap's start, **deleted
  before merge**. No surviving parity ratchet.
- Enduring tests verify **behaviour** and shift to **doctrine-module + integration**
  level (e.g. "a documentation mission resolves documentation governance and gates,
  not software-dev doctrine").
- **No code is kept solely to avoid test-suite churn** — no compat shims, no
  preserved signatures, no byte-freeze. The suite is expected to change
  substantially and is rewritten to the new behaviour.

## 7. Refined work-package spine

Four lanes; ~10–12 WPs (Q3 added the steps lane). Lane A: **WP-TIDY**. Lane B
(critical path): **WP-CANON → WP-SEAM → WP-LEAK → WP-OVERRIDE** (override rides the
overlay stack: `id` + `BaseDoctrineRepository` subclass). Lane C (parallel
authoring): **WP-CONTENT-DOC / -RESEARCH / -PLAN**. Lane D (detachable,
non-blocking): **WP-GATES-RECONCILE → WP-GATES-MIGRATE** and **WP-STEPS-MIGRATE**
(route step-contract resolution through the artefact). Join: **WP-ENFORCE**
(enduring behavioural non-leakage / non-vacuity as doctrine-module + integration
tests). Transitional parity scaffolds live in WP-SEAM, WP-GATES-MIGRATE, and
WP-STEPS-MIGRATE and are deleted before merge.

## 8. Decisions resolved with the operator (spec-stage interview)

1. **Governance declaration shape:** the `MissionType` artefact **references a
   sibling `governance-profile.yaml`** (the live, schema'd, hard-failing surface)
   for type-grain governance, unioned with the action-grain index; governance-
   profile.yaml is kept, not absorbed. Lower churn.
2. **Overlay adapter form:** **ride the `doctrine/base.py` overlay stack** — add an
   `id` to `MissionTypeProfile` + a `BaseDoctrineRepository` subclass, for canonical
   builtin → org → project layering and #832 support (no bespoke second merge).
3. **Artefact depth in slice 1:** **governance + gates + steps.** Step-contract
   resolution routes through the artefact now (`WP-STEPS-MIGRATE`); only templates
   (`template_set`) defer to a later slice.
4. **ADR meta:** **Accepted, epic altitude.**

Still settled inside the named WPs (not architecture-level): the non-leakage
denylist membership, and the per-entry degrade for mission-less
`build_charter_context` callers.

---

## Appendix A — Conversation transcript (for maintainer review)

Reconstructed from the working session; operator turns quoted, agent turns
summarised to their decisions and actions.

**Operator:** "Start a new feature branch off `upstream/main` (use one of the
shadow clone sibling directories). We will work on issue 883. Start with a research
squad. This is a foundational doctrine feature and warrants additional scrutiny and
architectural alignment."

**Agent:** Selected the independent `spec-kitty-gate-doctrine` clone (own `.git`,
has `upstream`; preferred over a worktree per the one-clone-per-mission
discipline); fetched `upstream/main` and cut
`mission/883-mission-type-governance-profiles` off it. Launched a four-lens pre-spec
research squad — researcher-robbie (content/prior-art), architect-alphonso
(resolution architecture), paula-patterns (split-brain/boundary), doctrine-daphne
(doctrine mechanism) — all read-only against the mission branch.

**Agent (as lenses returned):** Reported that the "one surface" framing was wrong —
there are three governance surfaces; the live prompt path (`governance-profile.yaml`)
is leak-proof but empty; the action-scoped path leaks software-dev by
`template_set` inference; `governance_refs` is inert and dangling. Confirmed the
dual missions-tree, with the doctrine-side `expected-artifacts.yaml` a dead
read-path. Recommended landing governance on the doctrine side, splitting
`template_set`, one canonicalizer, and an enforcement test with a non-vacuity twin.

**Agent → Operator (four crux decisions):** surface strategy; leak-fix scope;
number of governance layers; content depth.

**Operator:** Leaned to "full consumer merge" and clarified the model — *doctrine
offers mission types + step contracts + prompts + governance; charter activates
and/or customises them like any other doctrine artefact; core is an FSM that
adheres to configured templates/steps/types, semi-prepared for "states &
transitions as config."* Chose: fix the leak now; add the per-type project
override; author full governance sets for all three non-software types.

**Agent:** Reflected the doctrine/charter/core model back; dispatched a focused
architect design pass to convert it into a concrete unified seam.

**Operator:** "Our end-goal: the specify-cli versions of the templates can be
deleted, and 'software-dev' becomes a built-in doctrine type, feeding the step
contracts, gates, and templates from the doctrine, through the charter, into the
execution loop."

**Agent:** Raised the design altitude — #883 is slice 1 of a `specify_cli/missions`
retirement; the seam must be the general `doctrine → charter → core` path (governance
first) and move consumers off the specify_cli tree. Fed this to the architect, who
returned the concrete seam: a `resolve_mission_type_context` bundle, per-type
override via the overlay stack, `governance_refs` retirement, the FSM attachment
point, a reader-migration order, and a WP spine.

**Operator:** "I want this captured as an ADR, and I'm expecting docs/architecture
to be updated."

**Agent:** Scouted ADR conventions; drafted ADR 2026-07-14-2 at epic altitude
(status Accepted, #883 = slice 1); freshened the ADR indexes; rendered it for
review.

**Operator:** "Go for sweep. As this is such a critical mission, I'd like a second
opinions squad on the refined lens — given my earlier guidance. We will handle this
change as the careful consultants / architects we are. Ensure the test suite is
regarded as a first-class change surface, and not an afterthought."

**Agent:** Ran, in parallel, a docs/architecture sweep (curator-carla) and a fresh
adversarial four-lens second-opinion squad — reviewer-renata (test suite,
first-class), paula-patterns (architecture refutation), python-pedro (implementer
reality), planner-priti (slice discipline). Held all commits pending
reconciliation.

**Agent (as lenses returned):** Reported a unanimous REFINE with four material
corrections — overlay not "free"; leak not closed by construction (dossier-path
default + layer rule); dossier flip a type-boundary crossing over drifted content;
the "byte-identity golden suite" is substring-based and asserts the fallback being
removed; `plan` empty-grain must be legitimate; CONTENT undersized; spine
resequenced. Surfaced the one operator decision: dossier-flip scope.

**Operator:** Chose the gated, isolated, non-blocking dossier-flip lane.

**Agent:** Revised the ADR to correct every overstatement and fold in the refined
WP spine and the dossier decision; corrected the two docs spots that had echoed the
overstatements; verified docs-freshness green.

**Operator:** "To be clear: we want the doctrine/charter path (flagged dead code)
to become alive, and the cli version (currently live) to be dead/removed without
the user noticing the swap. You may add parity tests to help your work, but these
should not survive the mission merge (add them at start of mission, delete them
after). Do not add a parity test / ratchet that survives the mission. Tests should
verify behaviour and will likely: shift to doctrine module tests; be checked at
integration level. Do not keep code with the sole purpose to avoid test suite
changes / significant updates. Our goal is to achieve the idea of the doctrine
being the source of truth for 'What is this mission type? What steps does it
contain? what gates are checked?' The 'MissionType' doctrine artefact type is to be
added/enhanced, and become load bearing."

**Agent:** Recorded the durable discipline to memory; revised the ADR and docs to
the transparent-swap / transitional-parity / no-shim / load-bearing-`MissionType`
intent (this brief and the current ADR reflect that revision).

**Operator:** "I want you to repeat and capture this mission's intent, my guidance,
and your research. Store this into the relevant docs directory, and give me the
executive/lead architect debrief summary before I sign off on the mission spec
stage. Include a transcript of our conversation so far, for other maintainers to
review. Commit and push to a feature branch. Delegate subagent Priti to add a
comment to issue #883 with said summary."

**Agent:** Authored this brief (intent, guidance, research, second opinion, testing
posture, WP spine, open decisions, transcript); committed and pushed the ADR + docs
sweep + brief to the feature branch; delegated planner-priti to post the debrief to
issue #883 ([comment 4973299470](https://github.com/Priivacy-ai/spec-kitty/issues/883#issuecomment-4973299470)).

**Operator:** "Interview me on the open decisions, make the trade-offs clear."

**Agent:** Ran a four-question spec-stage interview with trade-offs and side-by-side
previews. Operator decided: (Q1) the `MissionType` artefact **references** a sibling
`governance-profile.yaml` rather than absorbing governance; (Q2) the per-type
override **rides the `base.py` overlay stack** (`id` + `BaseDoctrineRepository`
subclass); (Q3) slice 1 covers **governance + gates + steps** (templates defer);
(Q4) ADR stays **Accepted, epic altitude**. Folded into the ADR (Decisions resolved)
and §8 of this brief; added `WP-STEPS-MIGRATE` to the spine.
