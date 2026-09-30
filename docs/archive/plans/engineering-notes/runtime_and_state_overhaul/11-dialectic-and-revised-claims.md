---
title: '11 — Dialectic: Corroboration vs Refutation → Revised Claims'
description: Dialectic (Phase 2) corroborating versus refuting the context-needs claims under the Architect Alphonso framing, yielding the revised claims for the overhaul.
doc_status: deprecated
updated: '2026-06-03'
---
# 11 — Dialectic: Corroboration vs Refutation → Revised Claims

**Phase:** 2 (requirements, lens 2+3) · **Date:** 2026-06-03 · **Method:** two parallel agents under
the Architect Alphonso framing — one building the affirmative case from the User Journeys + ADRs, one
adversarially refuting. This document reconciles them **honestly**: where the refutation won, the
claim is revised, not defended.

> **Headline:** none of our four claims survived intact, and that is the most valuable outcome so far.
> The refutation surfaced **existing assets we were about to reinvent** (`ActionContext`,
> `MissionOrchestration.states`, ADR 2026-03-09-1) and **standing decisions we were about to violate**
> (the determinism freeze, the fail-closed topology rule). The design is now sharper and *less*
> greenfield.

---

## Claim A — behaviour binding · **VERDICT: REFUTED as stated → narrowed**

**We claimed:** behaviour (profile/role/directives) is *wrongly frozen at run-start*; the activity
ledger is *observational only* and should become the canonical source.

**Affirmative (best):** behaviour is designed as a runtime-resolved governed *(profile, action,
governance-context)* triple, with a first-class lifecycle trail meant to be consumable, not just
audit — `docs/architecture/governed-profile-invocation.md:14-32, 96-126`.

**Refutation (damaging, and correct):**
- Run-start freezing is a **deliberate determinism contract**, not a bug:
  `docs/adr/2.x/2026-02-17-1-canonical-next-command-runtime-loop.md:42-43` — "`next` planning
  uses the **frozen mission template captured at run start (not live mission file edits)**" with
  drift → `blocked`. Honoured by `engine.py:129 _freeze_template()` + `planner.py:305 _check_template_drift()`.
- The premise "behaviour is frozen / ledger is observational" is **factually wrong for the parts that
  matter**: profile/role/directives are read **live at prompt-build** from WP frontmatter
  (`prompt_builder.py:157,163,184`), and live lane/dependency state **is** consulted at claim gating
  (`runtime_bridge.py:767-772`, `dependency_graph.py:50`).

**Reconciliation — what's actually true:**
- The **step topology** (which step is next) is frozen at run-start *on purpose* (determinism). **Preserve this.**
- **Behaviour** (profile/directives) is **already resolved live** — so our "wrongly frozen" framing is wrong.
- The real, *smaller* residue: behaviour resolution is **split across two reads with no single owner** —
  the frozen step (`_resolve_step_agent_profile(run_dir, current_activity)`, `runtime_bridge.py:2167`)
  **and** live WP frontmatter (`prompt_builder.py:163`). These *should* agree (frontmatter is written
  from the step), but nothing guarantees it. **Revised Claim A:** *consolidate behaviour resolution
  behind one owner so the frozen-step profile and the live-frontmatter profile cannot diverge* — a
  consistency concern, not a frozen-vs-live error. The activity ledger stays the **provenance/audit**
  record, not the resolution source.

---

## Claim B — mission phase · **VERDICT: WEAKENED → narrowed**

**We claimed:** mission phase (planning→implementing→integrating→done) is *not first-class* and should be.

**Affirmative (best):** "Mission phase" is named as a runtime decision input
(`docs/architecture/runtime-loop.md:33`) and every journey uses explicit phase tables.

**Refutation (correct):** a mission-level state machine **schema already exists** —
`src/doctrine/missions/models.py:76 MissionOrchestration` (`states`, `transitions`, `guards`,
`required_artifacts`); run progress is persisted in `MissionRunSnapshot` (`completed_steps`,
`issued_step_id`, `blocked_reason`); per-type `action_sequence` orders the lifecycle; the 9-lane
`WPState` machine owns WP-level phase. **And** the canonical terminology ADR *deliberately demotes*
"phase": `docs/adr/3.x/2026-04-04-2:110-111` — prefer `mission action`/`step` for runtime nodes.

**Reconciliation — what's actually true:**
- Phase-position **is** first-class — but **distributed** across `action_sequence` (type ordering),
  `MissionRunSnapshot` (run progress), and `WPState` (WP lane). It is **not unowned.**
- Caveat from our own earlier finding (`07`): `MissionOrchestration` is **schema-only / unwired** —
  nothing in `status/` consumes it. So the *schema* exists but is **not the runtime authority.**
- **Revised Claim B:** do **not** introduce a new `MissionPhase` enum (it fights the canonical
  vocabulary). The defensible residue is narrow: there is **no single derived "coarse lifecycle
  position"** unifying mission-action + WP-lane, and `MissionOrchestration` is unwired. If we want a
  coarse phase, **derive** it from existing state (`completed_steps` + WP-lane aggregate) or **wire**
  `MissionOrchestration` — not add a competing concept.

---

## Claim C — interaction policy · **VERDICT: REVISED (partly refuted, partly reconciled)**

**We claimed:** branch/merge/execution/workspace strategy should be a first-class
`MissionInteractionPolicy` with **charter-default → per-run override**, owned by the Mission Run.

**Affirmative (strong):**
- The bootstrap journey **explicitly designs** charter-selected approaches to reconfigure
  branch/worktree/merge at run time — `docs/archive/plans/user_journey/001-project-onboarding-bootstrap.md:224,
  236-241`, Acceptance Scenario 7 `:192-198`.
- A working **charter-default → config → default** precedence already exists for merge
  (`merge/config.py:4-7`; `MergeState.strategy`), and the retrospective ADR **ratifies that exact
  pattern as house style** with a traceable `source_map`: `docs/adr/3.x/2026-05-19-1:79-85`
  ("Charter wins by default; config may delegate").
- `branch_strategy` / `execution_mode` are already charter-extracted and per-WP-carried fields.

**Refutation (the critical constraint):** per-run **workspace/branch topology** override is an
**anti-goal**. `docs/adr/3.x/2026-04-03-1` makes `lanes.json` mandatory and **fail-closed**:
"There is **no runtime fallback** to per-WP worktrees… or structure 'detection' logic." A per-run
mutable topology policy would reintroduce exactly the variability that ADR deliberately removed for
merge-safety.

**Reconciliation — the synthesis is better than either side:**
- The **charter-default mechanism is right and is the house pattern** (retrospective ADR proves it).
- But "**per-run override**" must mean **resolved once at *decompose/plan* time (P3) and then frozen**
  — *not* mutable per operation at implement/merge. The strategy is *chosen* when the mission is
  planned; it is then **baked into `lanes.json` + persisted policy** and consumed fail-closed
  thereafter. This honours both the journey (charter selects strategy) **and** ADR 2026-04-03-1
  (topology is fixed, no runtime detection).
- **Revised Claim C:** a first-class **resolved-and-frozen** `MissionInteractionPolicy` —
  charter default → config → plan-time resolution → **frozen** onto the Mission Run / `lanes.json` →
  consumed immutably. It **closes the dead branch-strategy extraction** without reintroducing runtime
  topology variability. Merge strategy may remain late-bound (it acts once, at the end); branch/
  workspace/parallelism must be plan-time-frozen.

---

## Meta-claim — context fragments · **VERDICT: WEAKENED toward REFUTED → reframed onto existing assets**

**We claimed:** model the flow as a *new* composition of domain-owned context fragments.

**Affirmative (principles, strong):** domain-owned boundaries with stable seams are house doctrine —
`docs/architecture/00_landscape/README.md:52-55`; `docs/archive/architecture/02_containers/runtime-execution-domain-2x.md:24-37`
("Runtime decisioning and lifecycle mutation are separate authorities… worktree context does not
reassign lifecycle authority… metadata is the routing authority"); the bounded-context map in
`2026-05-19-1:201-231`.

**Refutation (the most important hit):** *composed domain-owned context already exists.*
- `src/specify_cli/core/execution_context.py:44 ActionContext` composes
  `action, mission_slug, feature_dir, target_branch, wp_id, lane_id, branch_name, execution_mode,
  workspace_path, commands, dependencies` — **the fragments we proposed** — and is backed by an
  **accepted ADR**: `docs/adr/3.x/2026-03-09-1-prompts-do-not-discover-context-commands-do.md`
  ("Prompts do not discover context. Commands do.").
- `context/models.py:18 MissionContext` (identity binding) and
  `next/_internal_runtime/schema.py:493 StepContextBundle` already compose context at boundaries.
- Over-fragmenting risks violating the **deep-module paradigm** and re-creating the scatter the
  WP-state ADR (`2026-04-06-1`) paid to consolidate.

**Reconciliation — the reframe:**
- We are **not inventing** context composition. **`ActionContext` + ADR 2026-03-09-1 already are the
  canonical "commands resolve context, prompts consume it" contract.** This is a *gift*, not a
  competitor.
- The actual problem (from `02`) is that `ActionContext`/`MissionContext` are **mutable, incomplete,
  and bypassed** — the ~40 surfaces still derive raw `repo_root/"kitty-specs"` paths instead of going
  through them.
- **Revised Meta-claim:** **extend and enforce `ActionContext`** (make it immutable, complete the
  topology gaps it lacks — the read/write/destination split from `02`/`09`, the F2×F3 commit-target
  kernel — and route the bypassing surfaces through it). The `09` "fragments" become the **internal
  structure of a hardened `ActionContext`**, not six new public objects. Keep it a **deep module**
  (small interface) per the paradigm; do not expose the fragments as a sprawling public API.

---

## Net effect on the design direction

| # | Before | After dialectic |
|---|--------|-----------------|
| A | Ledger should drive behaviour; it's wrongly frozen | **Preserve** topology freeze (determinism ADR); behaviour is already live; fix is **one owner** for profile resolution (frozen-step vs frontmatter divergence). Ledger = provenance. |
| B | Add first-class mission phase | **Don't** add a `MissionPhase` enum (fights canonical vocab). Phase is distributed/first-class already; optionally **derive** a coarse view or **wire** the unwired `MissionOrchestration`. |
| C | `MissionInteractionPolicy` with per-run override | **Resolved-and-frozen** policy: charter→config→**plan-time**→frozen onto `lanes.json`/Mission Run. Honours fail-closed topology ADR. Merge stays late-bound. |
| Meta | New 6-fragment composition model | **Extend/harden the existing `ActionContext`** (ADR 2026-03-09-1) — make it immutable, complete the topology split, enforce its use. Fragments = its internals, not public API. Stay a deep module. |

**The single biggest correction:** the redesign is **consolidation onto `ActionContext`**, not a
greenfield context family. This *lowers* risk and aligns with a standing accepted ADR — and it means
`05` invariant I-1/I-2 are achieved by **hardening + enforcing an existing resolver**, not building a new one.

## What still stands (un-refuted)

- The **root cause** (`05`): unowned/bypassed topology resolution — *strengthened*, since the owner
  (`ActionContext`) exists but is bypassed.
- The **invariants** I-1…I-10 (`05`) — all survive; they're now satisfied by hardening `ActionContext`.
- The **split read/write/destination** need (`02`, I-2) — survives; `ActionContext` lacks it today.
- The **one-atomicity-domain** rule (I-4) and the **commit-target** kernel — survive.
- **MissionStatus aggregate** (`07` §4) — un-refuted; event-sourcing makes it near-free.

## Next

1. Re-baseline `09`/`10` against these revisions (ActionContext as the spine; policy frozen-at-plan; behaviour single-owner; phase derived-not-added).
2. Take the **hardened-`ActionContext`** shape + the **plan-time `MissionInteractionPolicy`** into the BPMN/interaction diagrams.
3. Open question for Stijn: do we **harden `ActionContext` in place** or **supersede it** with a new immutable resolver that absorbs it (Strangler)? The dialectic favors *harden in place* (least churn, honors ADR 2026-03-09-1).
