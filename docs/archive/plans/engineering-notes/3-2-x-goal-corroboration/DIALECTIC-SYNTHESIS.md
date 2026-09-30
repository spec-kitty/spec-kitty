---
title: Dialectic synthesis — 3.2.x design under white-team + red-team
description: 'Dialectic synthesis of the 3.2.x design under white-team corroboration and red-team refutation: what survives the adversarial test and what does not (2026-06-16).'
doc_status: deprecated
updated: '2026-06-16'
---
# Dialectic synthesis — 3.2.x design under white-team + red-team

> **Retired (deprecated).** Design shipped/superseded via the open-core delivery plan §1 "Status re-read (verified)" (G1–G3 goal corroboration folded into the plan) — see `docs/archive/plans/3-2-x-open-core-delivery-plan.md`. Preserved as a historical record.

**Date:** 2026-06-16. **Method:** a white-team squad corroborated the 3.2.x design/goals; a red-team
squad was then mandated to refute them. This is the synthesis — what survives the adversarial test,
what is refuted, and what remains genuinely contested. (Inputs: `corroboration-*` + `caacs-delta-*`
[white]; `redteam-*` [red]; and `../naming-identity-ssot-strangler/` [the original investigation].)

> **Meta-finding (own it):** the white-team squads were briefed to *corroborate the operator's
> intuition/goals*, which primed them toward agreement (red-team/priti, confirmed by commit
> timestamps). The corroboration is therefore weak as *proof*; its value is the assembled evidence,
> which the red team then re-read adversarially. The lesson for future scoping: run a **neutral or
> adversarial** scoping pass, not a confirmatory one.

## Adjudication

| # | Claim (white thesis) | Verdict | Basis |
|---|---|---|---|
| 1 | The static `branch_naming`/`mid8()` seam is the real, sound, load-bearing SSOT | **SURVIVES** | Conceded by all four red-teamers; it's the part doing the work. |
| 2 | The cheap `mid8()` routing of the ~14–26 bare `[:8]` sites is worth doing, low-risk | **SURVIVES** | Conceded by alphonso/debbie/priti; honest small win. |
| 3 | "Thread the `ExecutionContext` everywhere" is the central fix | **REFUTED** | Built-and-parked (2 fragment reads tree-wide, 0 on identity; `git log -S "context.identity"` = 0); **internally split-brained** (`branch_name`≠`branch_ref.target_branch` on one object, `resolution.py:793-801`); mutable; net *more* code. It's a **builder redesign mislabelled as adoption**. |
| 4 | Re-derivation is the root cause of the recurring defect class | **REFUTED** | The recurring bugs (#1949/#1589/#1990↔#1991) are **wrong-logic-in-the-authority**, fixed *inside* `branch_naming.py`; **#1589 recurred *via* the seam**. Threading prevents none. |
| 5 | The literal-ban ratchet is the *mechanism* and makes the class "can-never-regrow" | **CONFOUNDED / OVERSTATED** | Ratchet measures *syntax*, not coupling; it's a tripwire added *after* the cut (same squash), not its cause; passes today with 14 live `[:8]` sites; shape-shifting (`mid[:8]`/`[0:8]`/helper) defeats it. **Keep it as a tripwire, not an oracle.** |
| 6 | The strangler is measurably progressing (authorities cooled) | **UNPROVEN** | Per-block CC cooled for `transitions`/`context` (real), but `src/` SLOC **123k→266k (+115%)**, `core/execution_context.py` deleted → +1,336-line `mission_runtime/`, and **no legacy path retired in-range** = **extract-then-COEXIST**, the failure precondition. |
| 7 | Status is the success model (−76% bypass) | **CONTESTED → leans REFUTED** | Deep imports 182→34 **but facade imports 5→259, total +60%, files-coupled-to-status 44→78 (+77%)**. Red reads this as Goodhart/relabel; a charitable reading is *correct facade adoption* (more files use the facade, fewer reach inside). **Unresolved without a coupling-*quality* (not count) analysis** — do not cite −76% as settled. |
| 8 | Naming/identity is the right *lead* 3.2.1 slice | **REFUTED on priority** | It's the smallest, most-settled gap (one WP is verify-and-close) while **P0 #1716 (launch-blocker), #1827 (unrecoverable merge-baseline), #1832 (read-path), #1891** and the god-modules (`merge` CC 102, `mission` 220) go untouched. Chosen for safety, not impact. |
| 9 | The 3.2.x goals are evidence-grounded continuations | **WEAK / POST-HOC** | The taxonomy was authored *today*; the corroboration was primed. The **goals are legitimate operator *intent***, but "proven continuation" is unsupported. The underlying epics (#1619/#1666/#1868/#1878) *are* real and pre-existing. |
| 10 | Defer all of #1878 (coord/primary) to 3.3.x | **REFUTED on sequence** | The write/entry side *authors* identity + is the "highest blast radius" (white team's own §4) + holds the unrecoverable #1827. The read SSOT can't be more consistent than the write SSOT feeding it. Pull a bounded write-side slice *forward*. |

## What survives → the defensible 3.2.x core

- The **static `branch_naming`/`mid8()` seam** as the identity SSOT (already shipped).
- A **cheap routing rider**: route the ~14–26 bare `mission_id[:8]` sites through `resolve_mid8`/`mid8()`, plus a **ratchet extension as an anti-regression *tripwire*** (scoped honestly: partial, syntax-level, not a completeness guarantee).
- The DIR-031 bounded-context guardrails; the "cycle stays open" honesty about G1.

## What is refuted/revised → drop or reframe

- **Drop "thread the `ExecutionContext` everywhere"** as a mission spine. It is a *builder redesign* (fix the internal `branch_name`/`branch_ref` inconsistency; make the composite genuinely immutable) — a separate, later, carefully-sequenced effort, applied only at the 2 sites that already hold a context, **after** the freeze and **after** the write-side authority is consistent.
- **Reframe the ratchet** from "the mechanism / can-never-regrow" to "a cheap regression tripwire" that measures syntax; pair it with shape-aware detection or accept its limits.
- **Stop citing the confounded metrics** ("−76% status", "cooled") as proof; the honest statement is "per-authority complexity improved; system-level reduction is unproven; adoption has not retired any legacy path."

## Genuinely contested (needs a neutral follow-up, not a verdict here)

- **Status coupling: relabel (Goodhart) vs correct facade-adoption** — needs a coupling-*quality* analysis (does the facade hide internals, or just rename the import?).
- **Whether per-authority cooling amid system growth counts as "progress"** — depends on whether the growth is unrelated feature work (likely substantial) vs strangler-induced duplication.

## Implications for 3.2.x scope (operator decision — see §below)

The red team did **not** refute that the engineering is real; it refuted the **framing, the metrics-as-proof, and the sequencing**. The synthesis points to: **lead 3.2.1 with the high-impact/P0 work (#1716/#1827/#1832 + a bounded #1878 write-side slice), demote the naming work to a cheap routing+tripwire rider, and treat the `ExecutionContext` freeze as its own redesign** — pending a *neutral* scoping pass (not a confirmatory one). The naming slice remains a legitimate *low-risk opener* if quick-win value + establishing the ratchet pattern is explicitly preferred over impact — but that should be a chosen trade-off, not a data-driven conclusion.
