---
title: 3.2.1 lead-slice — neutral scoring synthesis
description: "Neutral scoring synthesis for the 3.2.1 lead slice after the biased white-team and the red-team passes: three scorers' consolidated ranking (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# 3.2.1 lead-slice — neutral scoring synthesis

**Date:** 2026-06-16. **Method:** after the white-team corroboration (found confirmation-biased) and
the red-team refutation, the operator chose a **neutral scoring pass**. Three scorers — debugger-debbie
(severity), planner-priti (tracker/ROI/sequencing), architect-alphonso (architectural blast-radius) —
independently scored the **same flat candidate set** against a neutral rubric, drawing on both white and
red evidence, with an explicit de-bias instruction (*score naming fairly as one candidate; no
predetermined answer*). Inputs: `scoring-debbie-severity.md`, `scoring-priti-tracker.md`,
`scoring-alphonso-architecture.md`. This is the synthesis.

## The candidates (flat, as scored)

| # | Candidate | Priority |
|---|-----------|----------|
| #1716 | coord topology coherent from mission-create→planning (write-side coord split-brain) | P0 launch-blocker |
| #1832 | `agent action implement` claim succeeds but "no workspace resolved" (read-path) | P1 bug |
| #1827 | `spec-kitty merge` post-merge baseline circular failure (unrecoverable) | P1 bug |
| #1891 | `agent --json` broken | P1 bug |
| #1619/#1666 | unify execution-context / execution-state — *shippable 3.2.1 slice* | P0 epics |
| #1878 write-side slice | bounded, characterization-first coord/primary write cut | P2 umbrella |
| Naming routing rider | route ~14–26 `mission_id[:8]`→`resolve_mid8` + ratchet tripwire + #1993/#1971/#1888/#1900 | mixed |

## The reframe that resolves the panel (alphonso, verified on checkout)

> **#1716, the #1619 slice, the #1878 write-side slice, and #1832 are not four candidates — they are
> one surface at four grains.** The write-side coord/topology authority is the root; #1832 is its
> smallest, safest, *verifiable* instance; the #1619 builder-hardening is the same surface as an
> internal-invariant fix; the #1878 slice is the same surface at the entry/durability grain.

This dissolves the apparent debbie (#1716-first) vs priti (#1832-first) disagreement: they are picking
**different grains of the same lead**, not different leads. Verified facts that anchor it:
- `ExecutionContext` is **mutable** (`context.py:184`) and its builder mutates substrate fields *after*
  freezing fragments (`resolution.py:793-801`) → `branch_name ≠ branch_ref.target_branch` **inside the
  claimed SSOT**. The split-brain lives *in* the authority, not just in non-adoption.
- The create-path and re-resolve-path are **different resolvers** (`workflow.py:1336→1357→1372`), which
  is exactly what #1832 reproduces; #1832's own ticket-grounded fix is "consume the same resolved
  context the claim used to create the workspace — single resolution path."
- `resolve_lanes_dir` does **not** exist yet (#1993 extraction is real); `merge.py` is a 3.3k-line
  god-module; only **2** context-fragment reads exist tree-wide; the dashboard uses **zero** context.

## Where the three scorers converge

1. **#1832 is the universally-endorsed entry point.** debbie #2-by-severity (verified real, reproduced);
   priti #1-by-ROI (cheapest real-pain fix, *is* the G2 "consume-the-SSOT-don't-re-derive" thesis as an
   actual bug not a metaphor); alphonso "the safest possible *first WP*, proves single-resolution."
2. **#1716 is the highest-severity / highest-blast-radius keystone.** debbie #1; alphonso #1 (paired);
   priti "most important candidate **and** the worst *first* move" (it's the deep/risky #1878 keystone).
3. **The naming rider is unanimously demoted** to a cheap, safe, **parallel** track — not the lead.
   Scored fairly (priti Σ26, alphonso 22/30), neither inflated nor punished. Its impact is low (tidiness
   debt), and the "ratchet can never regrow" claim is overstated (it passes today with ~20 live `[:8]`
   sites). **#1888 is verify-and-close, not a build.**
4. **Hard sequencing constraint (priti, echoed by alphonso):** **#1993 must land *with* #1832**, not
   alone — extracting `resolve_lanes_dir` by itself half-strangles the read path into a new shadow path.
5. **Tracker inversion is real, not rhetorical (priti, alphonso-confirmed):** the 3.2.x milestone holds
   **only** the 5 (now-closed) naming issues; #1716 (P0), #1827/#1891 (P1), #1832 (P1), and #1619/#1666
   (P0 epics) are **all unmilestoned**. This needs fixing regardless of which lead is chosen.

## Where they diverge (and the resolution)

- **#1827** — priti: highest *user* pain (unrecoverable in-tool, needs manual `meta.json` surgery), her
  runner-up lead. debbie: **may be stale** — the claimed "assert-before-write" circularity does **not**
  reproduce on current code (`merge.py` orders record→commit→assert correctly, resume-convergent).
  alphonso: neutral. → **Resolution: re-test #1827 first.** If it reproduces, it's a high-value
  fast-follow; if not, close-with-evidence (claim-exempt). Do not lead with it unconfirmed.
- **#1891** — partially fixed already on this branch (`4c492aa85` fixed the map-requirements
  CommitResult); residual (`agent action implement` has no `--json`) is **independent DevEx, start
  anytime**. Not a lead.

## Synthesized recommendation

**3.2.1 LEAD = the write-side / single-resolution authority surface — opened through #1832, driving to
issue #1716.** Concretely:
- **WP1 — #1832 + #1993** (must pair): single-resolution read-path fix. Safest first WP, lands a live
  P1, proves "consume the resolved context, don't re-derive," and supplies the `resolve_lanes_dir` seam.
- **WP-next — #1716**: the write-side coord/topology authority root (P0 launch-blocker, keystone of
  #1619/#1878). Higher characterization-test cost; sequence right after WP1 establishes the pattern.
- **Optional in-cycle — #1619 builder-hardening slice**: un-mutate the `ExecutionContext` builder, close
  the internal `branch_name ≠ branch_ref.target_branch` invariant, write the action-vs-bulk guardrail.
  Same surface, internal-invariant grain.

**Parallel tracks (explicitly NOT the lead):**
- **Naming routing rider** (#2000/#1971/#1900 + ratchet-as-tripwire + #1888 verify-close) — cheap, safe,
  low-impact; runs alongside. (#1993 goes with WP1, not here.)
- **#1827** — re-test, then fast-follow or close.
- **#1891 residual** — independent DevEx, anytime.

This **inverts the prior "naming-first" plan** the (biased) corroboration had produced: naming becomes a
rider, the write-side/single-resolution surface becomes the headline.

## The one trade-off that is the operator's to decide

All three scorers flag the same values call (none claims it's a data verdict):

- **Lead with IMPACT** — open the write-side/single-resolution surface (#1832→#1716). Frees P0/P1,
  attacks the #1619/#1878 spine, but carries higher characterization-test cost and semantics risk.
  *(All three scorers lean here.)*
- **Lead with SAFETY** — open with the byte-identical naming rider. Lowest risk and quick momentum, but
  frees no P0/P1 and parks the highest-blast-radius surface plus the unrecoverable bug class for later.

Neutral read: **impact, entered through #1832** — the safety of the naming-first plan is available
*inside* the impact plan (because #1832 is itself the safest first WP), so leading with impact does not
forfeit safety; leading with naming forfeits impact.

## Operator decision (2026-06-16)

The operator chose **SAFETY — naming routing rider first**, deliberately **overriding the panel's lean
toward impact**. This is recorded as a legitimate **values choice, not a data verdict**: all three
scorers leaned impact, and the panel's neutral read is that leading with naming forfeits the
highest-blast-radius surface and frees no P0/P1 this patch. The operator weighs *lowest-risk momentum
and establishing the ratchet/routing pattern* above that — a defensible stabilization-cycle stance.

**Therefore 3.2.1 = the naming routing rider** (route ~20 `mission_id[:8]`→`resolve_mid8`, ratchet
extension as tripwire, the `resolve_lanes_dir`/`locate_project_root` seams, #1888 verify-close). The
write-side/single-resolution surface (#1832→#1716), #1827 (re-test first), the #1619 builder-hardening,
and the #1891 residual **defer to later 3.2.x patches** — impact work follows the safe opener.

**Two constraints that survive the values call (carry into the mission slice regardless):**
1. **#1993 must NOT land alone.** Extracting `resolve_lanes_dir` by itself half-strangles the read path
   into a new shadow path (the read-side `_lanes_feature_dir` twin). In the naming-first plan #1832 is
   deferred, so either (a) #1993 carries a *minimal* read-side adoption of the new seam in the same WP,
   or (b) #1993 defers with #1832 to the write-side patch. Decide at slice time — do not ship #1993 as a
   bare extraction.
2. **The framing in `docs/release-goals/3.2.x.md` is corrected**, not preserved: naming-first is a
   chosen low-risk opener, *not* "the data says naming-first." The confirmation-biased "evidence-grounded
   continuation" claim is discounted; the dialectic + this neutral panel are recorded honestly.

**Follow-up (independent of the lead):** the verified **tracker inversion** is fixed — milestone the
unmilestoned P0/P1 work (#1716, #1827, #1832, #1891, #1619/#1666) onto 3.2.x/3.3.x so the burndown
reflects the real cycle, not only the naming issues.
