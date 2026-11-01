---
title: QA Mission — Tidy-First Sequencing (does degod-before-test-QA pay off?)
description: 'Which degod/deshim/dead-code cleanup makes the #2071 test-QA mission cheaper, driven by the CaaCS co-change data — and which does not.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/archive/plans/testing/test-suite-friction-audit.md
- docs/archive/plans/testing/test-change-coupling-caacs.md
- docs/archive/plans/refactor/degod-unshim-roadmap.md
- docs/plans/3-2-x-milestone-roadmap.md
---
# QA Mission — Tidy-First Sequencing

> **Historical (3.2.x cycle).** Kept as a record. The test-friction epics this note served, #2071 (tests as scaffold, not friction) and its parent #1931, are closed. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

*Sequencing note, 2026-07-13. Written while planning the second of the "two
missions, perf first" pair (the CI test-topology-performance mission shipped as
PR #2609; this covers the sibling #2071 CT-friction slice).*

## The question

Would running one or more degod / deshim / dead-code-removal missions **first**
make the planned #2071 test-QA mission more efficient?

**Bottom line: yes, but only for the slice of test friction that is *downstream
of src structure* — and the [CaaCS co-change data](test-change-coupling-caacs.md)
should pick that slice, not a blanket "degod everything first."** A broad
degod-first sequencing would delay the QA mission for partial benefit and
serialize it behind the whole #1797 / #2173 program. A narrow dead-code/deshim
pass plus *interleaved* targeted degod is almost pure win.

## Why it depends: two independent causes of test friction

The discriminator is *why* a given test is painful. The two causes respond
differently to structural cleanup:

1. **Test-intrinsic friction** — fakeable DoDs, over-mocking a *clean* unit,
   retry-to-green, quarantine because of a real flake, legacy contracts. This is
   the bulk of #2071's core (CT3 #2074, CT4 #2075, CT5 #2076, the CT7 gate hole
   #2564, the legacy-contract backfill #2553/#2323, the quarantine debt
   #2295/#2309/#2342). **Degodding src does nothing for these** — the test is
   bad independent of the code it exercises. Do not sequence structural work
   ahead of this.

2. **Structure-induced friction** — tests that are brittle *because* the
   unit-under-test has no clean seam: heavy fixtures, deep mock stacks, and
   co-change with src on every refactor. **Here degod-first pays off twice.**
   Once the god-module is split into ports + a pure core (the #2173 infra-logic
   pattern, delivered by the #1797 degod waves), those tests collapse to small
   mock-free units. Rewriting them *before* the seam exists means rewriting them
   *again* after — you pay the de-scaffold cost twice.

## The discriminator: CaaCS co-change

Do not guess which friction is which. The
[test-change-coupling (CaaCS) analysis](test-change-coupling-caacs.md) ranks
`src ↔ test` co-change; its high-co-change clusters are exactly the
structure-induced friction where degod-first helps. Before committing the QA
mission's scope, read that ranking:

- If the fragile #2071 tests cluster on the known god-surfaces (`cli/commands/
  doctor.py` #2059, `cli/commands/merge.py` #2057/#2026, `agent/mission.py`
  #2056, `charter/context.py` #2532, `next_step` #2603), that overlap **is** the
  enabler list.
- If they are spread across otherwise-clean units, structural work will not move
  the needle and the QA mission should just fix the tests directly.

(The `cli/commands/tasks.py` crime-scene — the original highest-co-change
surface, #2034/#2116 — has already been degodded, PR #2308, 4569→1206 LOC. That
is the proof-of-mechanism: its tests got a golden-CLI seam *first*, then thinned.)

## ROI ranking for this goal

| Cleanup | Effect on the QA mission | Verdict |
|---|---|---|
| **Dead-code removal** | Deletes the code *and its tests* outright — zero rewrite, near-zero risk | **First.** Cheapest friction reduction available. |
| **Deshim** | Hardening tests around a scheduled-dead surface is wasted work; delete the shim + its tests now | **First.** Tidy-first: shim deletions in the *current* cycle. |
| **Targeted degod of surfaces the QA mission will rewrite** | Creates the seam so the test rewrite is durable, not double-work | **Interleave**, gated on the CaaCS overlap; scope to *only* those surfaces. |
| **Broad god-module degod** (whole doctor.py / merge.py / mission.py) | Real but long, merge-serialized; the #1797 / #2173 program already owns it | **Do not gate the QA mission on it** — separate track. |

## Concrete issue clusters (tracker, 2026-07-13)

**Dead-code / deshim enablers — cheapest, do first (`tidy-up` / `tech-debt`):**
- **#2463** — drop pre-3.2.x legacy mission support (empty-mid8 / dual-era
  bare-slug branches). Dead-code removal; deletes its dual-era tests.
- **#2293** — unshim: burn down `category_b_grandfathered_legacy` dead-symbol
  carry-over (237 symbols).
- **#2499** — consolidate `compat/registry.py` shim registry into the Contract
  Registry loader.
- **#2561** — `runtime_bridge` compat-delegate surface (repoint monkeypatches,
  retire the delegate).
- **#2559** — dead-code gate is blind to first-party `module.attr` dynamic
  access. This is *tooling* that makes the deletions above provably safe — a
  force-multiplier for the whole dead-code sweep.

**Targeted degod enablers — interleave per CaaCS overlap (`tidy-up` / `tech-debt`):**
- **#2603** de-god `next_step` (remove `# noqa: C901`), **#2604** reduce
  `_mt_commit_wp_file` complexity, **#2532** decompose `charter/context.py`,
  **#2059** decompose `cli/commands/doctor.py`, **#2057**/**#2026** decompose
  `cli/commands/merge.py`, **#2056** decompose `agent/mission.py`, **#2465**
  `workflow.py` resolver consolidation, **#2560** `runtime_bridge` strangler
  slice, **#2595**/**#2600** extractions.

**Test-intrinsic (the QA mission's own core — degod does NOT help):**
- **#2071** epic; **#2074/#2075/#2076** (CT3/4/5); **#2564** (CT7 gate hole);
  **#2553/#2323** (legacy-contract backfill); **#2295/#2309/#2342** (quarantine).

## Recommended sequencing

1. **A small dead-code + deshim sweep first** (its own quick mission or a WP-0
   cluster) — `#2463`, `#2293`, `#2499`, `#2561`, plus the `#2559` tooling gate.
   It shrinks the QA mission's surface *before* it starts, at near-zero risk,
   because deleting code deletes its tests.
2. **Fold small, local structural cleanup INTO the QA mission** as a
   campsite-first WP cluster, scoped to exactly the surfaces it rewrites — the
   CaaCS-implicated god-surfaces from §"discriminator". Route any god-module too
   big for a campsite step to its tracked degod issue (`#2059`/`#2057`/`#2056`/
   `#2532`); do **not** inline the full decomposition.
3. **Do not block #2071 behind the full #1797 / #2173 program.** Pin the tests on
   genuinely-clean-but-badly-written units and fix them directly.

## Relationship to the 3.2.x spine

This refines, it does not contradict, the
[milestone roadmap](../../../plans/3-2-x-milestone-roadmap.md) dependency spine, where
**#1797 (degod/unshim DELIVERY)** and **#2071 (test-QA friction)** already sit as
**peer blockers** of the #1619 root. The spine says both must land before #1619;
this note adds the *intra-pair* sequencing the spine leaves implicit: they are
not merely parallel — a **targeted** subset of #1797 (the CaaCS-implicated
god-surfaces + the dead-code/deshim sweep) is a cheap **enabler** of #2071, while
the bulk of #1797 stays on its own track. Concretely: the dead-code/deshim sweep
leads, the CaaCS-overlap degod interleaves as campsite work, and the remaining
god-module decompositions proceed independently under #1797 / #2173.
