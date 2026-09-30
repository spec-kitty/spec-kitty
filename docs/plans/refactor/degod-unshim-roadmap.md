---
title: Degod / Unshim Program — Roadmap
description: 'Sequenced roadmap for degodding and unshimming the codebase — the structural cure for the measured test-friction: the waves, the epic frame, and the invariants.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# Degod / Unshim Program — Roadmap

> **Historical (3.2.x cycle; status checked 2026-09-30).** Kept as a record. The waves this program tracked have executed: the `specify_cli.next` and `specify_cli.glossary` shims were deleted by #2291 (the 3.3.0 shim removals, closed 2026-07-04 via PR #2328), and the dead-symbol burn-down #2293 closed on 2026-09-25. The 3.3.x milestone was retired on 2026-08-23. The follow-on Mission Clarity Layer (#1746) is now milestoned *CLI 4.x stable*. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

*Synthesis of a 3-lens inventory pass (2026-07-01), grounding the structural cure for the measured test-friction (HIGH & accelerating; regression-reintroduction SEVERE). Read against `upstream/main` @ `b5ff365ce`.*

## The frame

Test friction is a **symptom**. The disease is two structural conditions, and they map to an existing epic frame:

```
#1619  (parent: execution-context unification)
   │
   ├── #1868  static-seam binding      ∥      #2173  runtime-port binding     (peer enablers)
   │   (AST call-site gates + ratchets)         (Protocol + default-param DI)
   │
   └── #1797  degod / unshim DELIVERY   (where shims get deleted + god-objects extracted)
```

- **#1868** binds *what a seam is and refuses bypass* (layer rules, identity value-object, guard capability, CI suite map, contract versions).
- **#2173** binds *how infra is supplied without coupling* (FS/Clock/GitOps/SaaSQueue/Renderer ports). They **share mechanism** — #2173's Phase-1 canonicalizer gate (#2164) generalizes a #1868 artifact; #1868's `ResolvedMission` is the value #2173's `MissionResolver` resolves.
- **#1797** is the downstream consumer: every deletion is only *safe* once #1868 has bound the seam the shim held and/or #2173 has injected the port the god-object reached through.

## ⚠️ The refinement to "degod tasks.py first"

The operator's call (tasks.py degod leads) is right — **with one prerequisite the inventory surfaced**: the degod's entire payoff is *stub-testable pure cores*, but those unit/contract tests **currently run in no CI job at all** (#2034: no gate selects `-m unit`/`-m contract`; 30+ unit + 20+ contract files execute nowhere pre-merge — the same #2283 delivery-topology root cause). **Binding seams and extracting pure cores whose tests silently don't run is negative work.** So:

**Wave 0 (small, must lead): bind the CI suite map — close the `-m unit`/`-m contract` gap (#2034/#2283).** The path-filter half is already bound (dorny + the `_gate_coverage.py` model); the remaining surface is narrowly the marker→job authority. This is the enforcement substrate that makes every later wave's tests actually run, and it *retroactively* protects the already-bound seams (WS2 identity, WS3 guard). Small mission, maximal leverage. Then tasks.py.

## The waves

Degod (D), Unshim (U), and Seam-bind (S) tracks interleave. Unshim is cheap/parallel; degod is the structural main line; seam-binds are the enablers each wave needs.

| Wave | Track | Deliverable | Why here |
|---|---|---|---|
| **0** | S | ✅ EXECUTED (ci-suite-map-bind-01KWNPMP, 2026-07-04) — **Bind CI suite map**: marker→job authority BOUND via CI-validated invariants (the parsed gate model + a `unit`/`contract` residual job + marker-completeness/workflow-coherence/src-path-topology invariant suites); `-m unit`/`-m contract` now select a blocking gate; completeness fails closed. Closes #2034/#2296/#2297/#2333 (#2283 factor (a) closed; (b)/(c)→CT7 #2077). | Prerequisite: makes every later wave's guards + pure-core tests actually run pre-merge. |
| **1** | D | ✅ EXECUTED (degod-wave2, PR #2308: tasks.py 4569→1206, 10/10 WPs; closed #2305/#2116/#2306/#2307) — **tasks.py = #2116 body-thinning via ports.** golden-CLI-char-test FIRST (template: completed `mission.py` #2056); co-designed the reference port set; first extraction = status/lane decision core (unified #2116 b+c). | The #1 hotspot (79% fix-ratio); established the port protocol every follower reuses. |
| **1 ∥** | U | **category_4 removable-now sweep** ✅ EXECUTED (unshim-wave1-01KWKVHB, PR #2325: cat4 8→0) — delete 8 backcompat re-export shims (~135 LOC, 0 src callers), re-point ~15 test imports, drain `category_4` 8→0. + wire-or-delete `retrospective.lifecycle` (#2280 just landed) + delete dead `RELEASE_FLOW` token. | Disjoint from the CLI command; immediate LOC + allowlist-debt reduction; low risk. |
| **2** | D+S | **coord-authority trio: workflow.py + implement.py + acceptance/__init__.py** (79% / 71% / **87%** fix). Consume Wave-1 ports; land **#2164 Phase-1 canonicalizer gate** alongside (they're the write/placement seams it protects). | Share tasks.py's exact seams; the #2160/#2164 coord-authority class; highest post-tasks leverage. |
| **2 ∥** | U+S | ✅ EXECUTED (unshim-wave2-01KWMCAX, 2026-07-03) — re-pointed `specify_cli.next`'s live callers → `runtime.next`, then **full-deleted** the `specify_cli.next` shim (#2291/#612) + `glossary` shim (#2290/#613) + the **charter_lint/freshness/preflight** shim packages; canonical imports are `runtime.next`, `glossary`, `specify_cli.charter_runtime.*`. Shim registry drained to `shims: []`; `category_b` honest baseline 215. Bound **WS1 `mission_runtime` outbound layer rule** (#2326/WS1 #2327) — allowed-exception ledger + committed CI-selected negative test + shrink-only stale-entry guard. | The next-shim looked deletable but had live callers (the #2159/uv_receipt trap); WS1 gate stays green. |
| **3** | D+S | **orchestrator_api degod** (83% fix; the port-consumer shell). + **category_7 orphan triage** ✅ EXECUTED (unshim-wave1-01KWKVHB, PR #2325: task_profile/sync.replay/tracker_client_glue/retrospective.lifecycle DELETED; policy.audit → #2321; auth.transport ADR-deferred to Robert). + bind **WS4 daemon-identity** (unblocks daemon-lifecycle degod). | Advances #1619 execution-context; drains the largest dead-code carry. |
| **4** | D+S+U | **sync adapter cluster** (`sync.py`+`emitter`+`queue`+`daemon`) — CLI-split + adapter-consolidation (NOT pure-core; it's the reference adapter cluster #2173 Phase-2 leans on). + **WS6 versioned-contract policy ADR** + `SPEC_KITTY_*` env census → delete retired vars. + `category_b` 237-symbol burn-down. | The infra tail; safe last because it's adapter-shaped, and the contract-seam lets retired paths be deleted safely. |

## Seam state (the enablers), from the #1868 lens

| Seam | State | Blocks/enables |
|---|---|---|
| Mission identity (WS2) | **DONE** (residue #2138) | Unblocks inline-identity extraction (Wave 1+) |
| Guard capability (WS3) | **DONE** (residues: dead `RELEASE_FLOW`; no arch-ban on raw `git commit` outside `commit_helpers`) | De-inlined; small unshim tail in Wave 1∥ |
| **CI suite map (WS5)** | **marker→job authority BOUND** (ci-suite-map-bind-01KWNPMP, 2026-07-04; #2034/#2296/#2297/#2333 closed) — remaining WS5 = mypy CI-scope AC only (advisory-vs-enforced decision → #1868 follow-up) | **Meta-seam — gates whether every other guard runs. Wave 0 EXECUTED.** |
| Package layering (WS1) | **DONE** (`mission_runtime` outbound layer rule bound by unshim-wave2-01KWMCAX / WS1 #2327: 9-subpackage allowed-exception ledger + committed negative test + shrink-only guard; WS2–WS6 residuals remain) | Unblocked the `specify_cli.next` shim deletion (executed Wave 2∥) |
| Versioned contracts (WS6) | IN-PROGRESS (pinning bound; no policy ADR) | Enables retired-env/path deletion → Wave 4 |
| Daemon identity (WS4) | OPEN (reaper bound #2261; reuse/kill deferred per C-007) | Blocks daemon-lifecycle degod → Wave 3 |

## Non-negotiable invariants (carry into every wave)

- **CoordRead-authority ≠ CoordWrite-authority** — two distinct ports, never unified (the structural form of the #2160 fix; re-unifying is a regression).
- Stay **OUT of the blind primitive** `primary_feature_dir_for_mission` (FR-011 recursion).
- Ambiguity → `MissionSelectorAmbiguous`/`ActionContextError`, **never silent**.
- Ports on the **builder/shell**, not the frozen `MissionExecutionContext`; **one adapter per port**.
- Golden-CLI-characterization test FIRST on every command degod (freeze flags/exit-codes/`--json` incl. the coord exit-0 silent-skip arm) — it *replaces* the file:line ratchets (DIRECTIVE-041), not mutates them.

## Tracking restructure (#1797 gaps found)

`#1797` (sanitization) has no children for: (a) the category_4 removable-now sweep, (b) the charter legacy-shim cycle-close + `__deprecated__` markers, (c) linking the #612/#613 3.3.0 shim removals, (d) category_7 orphan triage, (e) the category_b symbol burn-down. Recommend filing these as #1797 children so the unshim track is tracked, and confirming #1619 as the program parent with #1868 ∥ #2173 as peer enablers.

## Immediate next step

**Wave 0 then Wave 1.** Scope the CI-suite-map bind (#2034/#2283) as a small first mission, then tasks.py = #2116 as the degod pilot. The category_4 unshim sweep can run in parallel with either from day one.

## First functional pickup after the program (operator ruling 2026-07-04)

**#1746 — Mission Clarity Layer (P1, milestone 3.2.x)** is the first *functional* mission queued after the degod/unshim/QA cluster completes. The 2026-07-04 backlog revitalization confirmed the whole SI chain (#1733, #1738–#1745) is intact, dependency-ordered, and unimplemented (`tasks/mission_card.py` / `tasks/emi.py` absent). Constraint carried from triage: co-design with #1666's communication-artefact contract — the MC layer's artifacts are exactly the surface #1666 wants under contract.
