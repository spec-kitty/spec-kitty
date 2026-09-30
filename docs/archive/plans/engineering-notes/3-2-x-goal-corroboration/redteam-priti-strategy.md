---
title: RED TEAM — Refuting the 3.2.x Strategy & Corroboration (planner-priti, antithesis)
description: Planner Priti's red-team refutation (dialectic antithesis) of the 3.2.x strategy and corroboration, read-only at 3.2.0.
doc_status: deprecated
updated: '2026-06-16'
---
# RED TEAM — Refuting the 3.2.x Strategy & Corroboration (planner-priti, antithesis)

> **Author:** Planner Priti, operating as RED TEAM (dialectical antithesis).
> **Branch:** `design/naming-identity-ssot-alignment` @ 3.2.0 (read-only; no commit, no branch switch).
> **Stance:** The white team CONFIRMED the operator's strategy. My job is to REFUTE it — attack the
> scoping, the sequencing, and the *objectivity* of the corroboration. Default prior: "the priorities
> are wrong / the conclusion was pre-baked." I concede only where the evidence forces me to.
> **Directives applied (planner-priti):** DIR-003 (Decision Documentation) — every counter-claim below
> carries its git/tracker/file evidence so the refutation is auditable, not rhetoric. Modes engaged:
> *prioritisation* (Eisenhower: is the first slice the important-urgent quadrant or the
> settled-low-impact one?) and *risk-analysis* (where does the deferral leave durability risk live?).

---

## 0. The chronology that frames everything (the load-bearing evidence)

Every refutation below rests on one reconstructed timeline, `git log` on this branch:

| Time (2026-06-16) | Commit | Event |
|---|---|---|
| **00:55** | `40e5209a5` | **v3.2.0 tagged** (PR #2003). The work is shipped and frozen. |
| 06:58 | `31b9a291b` | naming/identity SSOT strangler research squad (3.2.1 scoping) |
| 07:04 | `be706e915` | planner-priti pre-spec ticket sweep (3.2.1) |
| 07:19 | `19f072d0c` | CaaCS forensic squad (3.2.1) |
| **07:30** | `facd585e6` | **release-goals declaration FIRST authored** (README + 3.2.x.md) |
| 07:31 | `61115beb0` | `HOW_TO_MAINTAIN.md` §5 milestone model |
| 07:35 | `0eda6b7c7` | context-threading squad — "operator-intuition **VALIDATED**" |
| 07:36 | `9182452aa` | release-goals: "resolve mechanism note → **CONFIRMED**" |
| **07:59** | `96af72839` | release-goals: "**restructure 3.2.x to operator's 3 goals**" |
| 08:31 | `cde8488dc` | 3.2.x goal corroboration — 3-POV squad |
| 08:41 | `a5bce7bbd` | CaaCS forensic-delta corroboration |
| **08:42** | `2d666ba3d` | release-goals: "**fold corroboration verdict into the declaration**" |

**Read it plainly:** the goals were *not declared before 3.2.0 and then verified*. The tag shipped at
00:55; the goals were first written down at 07:30 (6.5 h *after* the release); the squads that
"validated" them ran 07:35–08:41; and the verdict was *folded back into* the declaration at 08:42. The
declaration and its corroboration were authored on the **same morning, after the fact, in a single
session**. This is the structural fact the other four refutations exploit.

---

## 1. Confirmation-bias attack — the corroboration is not an independent test

| Claim under attack | Counter-case | Evidence | Holds / survives | Severity |
|---|---|---|---|---|
| "Four **independent** investigations corroborated the goals" (`3.2.x.md` §Corroboration) | They are not independent of the conclusion. Every squad was briefed with the operator's claim *as the thing to test* ("Claim under test: the operator's 3.2.x goals are evidence-grounded continuations" — verbatim header of `corroboration-priti-planning.md`). Commit subjects pre-announce the verdict before the analysis is written: `0eda6b7c7` "operator-intuition **VALIDATED**", `9182452aa` "→ **CONFIRMED**". A squad told to "confirm X" and whose deliverable is titled "VALIDATED" is primed to find X. No squad was tasked to *disprove* the goals or to propose a *better* slice. | Commit log §0; squad file headers all phrase the task as "Claim under test … is corroborated". | **HOLDS.** The corroboration is structurally confirmatory, not adversarial. | **HIGH** |
| The corpus-vs-range "shape match" (G1 26/G2 28/G3 19 in-range ≈ 32/43/29 total) proves the goals are continuations (`3.2.x.md` §Corroboration; priti R4). | **Circular.** The goal buckets are defined by slug-keyword classification *of the same corpus* (priti's own Method: "slug-keyword-based with a fixed precedence … a *planning heuristic*, not a semantic read"). If you bucket the corpus three ways and then observe the range mirrors the corpus, you have shown the *classifier is stable*, not that the *goals are right*. The goals were derived from the corpus (08:42 "fold verdict into declaration"); finding the corpus fits them is tautological. | `corroboration-priti-planning.md` Method & R1/R4; the goals doc post-dates the corpus analysis. | **HOLDS.** "In-range shape mirrors total shape" is a self-consistency check of the bucketing, not a disconfirming test of the strategy. | **HIGH** |
| The goals are evidence-grounded. | **No pre-registered disconfirming test was run.** A neutral exercise would have asked: *what would the data look like if the goals were WRONG, and did we see that?* That counterfactual is never posed. What was NOT sought: (a) whether a *different* first slice has higher ROI (no alternative slice was scored); (b) whether the open P0/P1 queue contradicts "naming-first" (the squads never cross-checked the goal against the live launch-blocker list — see §2); (c) any squad arguing the *negative*. Paula's "Anti-corroboration" section is the closest, but it still concludes "confirming the pattern, not refuting it" — disconfirming evidence was *reframed as confirming*. | `corroboration-paula-patterns.md` §Anti-corroboration (every counter-signal is explained away as "mid-flight strangler"). No alternative-slice scoring exists in the corpus. | **HOLDS** (partially conceded: Paula *did* surface the inline-`[:8]` growth and the "Mirrors X" 5× as real counter-signals — but the framing absorbed them). | **MEDIUM-HIGH** |

**Verdict (1):** The corroboration is **methodologically confirmatory**. It demonstrates *internal
consistency* (the goals describe what shipped) but provides **no independent or disconfirming test** of
whether the goals are the *right priorities*. "These goals describe the 3.2.0 work" is true and trivial —
the goals were written *from* that work 6.5 h after it shipped.

---

## 2. Wrong-priority attack — naming-first leads with the smallest, most-settled gap

| Claim under attack | Counter-case | Evidence | Holds / survives | Severity |
|---|---|---|---|---|
| "The naming/identity slice is correctly the first 3.2.1 target … the single cheapest highest-ROI move" (`3.2.x.md` §Strategic read). | The white team's *own* data says naming/identity is the **smallest real gap**, and they lead with it precisely *because* it is small and safe — not because it is important. The slice is explicitly "~3–4 work packages of **mechanical routing**, one pure-seam extraction, and one shim retirement" and "**adoption/completion, not construction**" (`00-OVERVIEW.md` §1, `3.2.x.md` §G2). One of its four WPs (#1888) is a **"verify-and-close"** — confirm a fix that *already shipped* and add a test (`00-OVERVIEW.md` §6 WP01). Leading a release cycle with a slice whose plurality is "confirm something is already done" is the definition of vanity completion of a nearly-finished thing. | `00-OVERVIEW.md` §1, §6 (WP01 = verify-and-close #1888/#1915). | **HOLDS.** | **HIGH** |
| Identity is the "worst un-closed gap" so it deserves to be first. | The "worst gap" framing measures *ratchet-completeness*, not *operator pain*. By the forensic data the actual danger migrated into the **un-consolidated callers**: `merge.py` maxCC **60→102** (+2122 SLOC, **43 bugfix commits** in-range), `agent/mission.py` **158→220** (+1774 SLOC, 46 bugfix), `agent/tasks.py` **118→178** (47 bugfix). The naming slice touches *none* of these hotspots structurally — it routes `mid8` literals. The release leads with the cheapest cosmetic ratchet while the proven crime-scene god-modules (where the bugfix commits actually cluster) go untouched in 3.2.1. | `caacs-delta-robbie.md` consumer-hotspot table (merge/mission/tasks HEAT severe, 43–47 bugfix each); `00-OVERVIEW.md` §4 ranks coord/primary scatter "**Highest** blast radius". | **HOLDS.** The first slice avoids the highest-blast-radius surface the same squad identified. | **HIGH** |
| The slice is low-risk *and* high-impact. | These are in tension and the doc resolves it the wrong way for a *first* slice. "Highest-ROI, lowest-risk, first" (`3.2.x.md` §Emergent patches) optimises for *safety of the first move*, not *impact*. A neutral planner sequencing by Eisenhower (importance × urgency) would put the **live, recoverable-only-by-hand durability bugs** first (#1827 circular merge, #1832 "no workspace resolved", #1716 P0 launch-blocker), not a mechanical literal-ban. Choosing the low-impact-low-risk quadrant first is rearranging deck chairs while the P0 launch-blocker (#1716) sits unmilestoned. | §5 tracker data; `3.2.x.md` §Emergent patches. | **HOLDS.** | **HIGH** |

**Verdict (2):** **Naming-first is wrong-priority.** It is the lowest-impact, most-settled domain
(status already −76%/healthy; identity is "just" `mission_id[:8] → resolve_mid8`), chosen for safety,
while the highest-blast-radius surface (coord/primary write-side, the merge/mission/tasks god-modules)
is deferred. The white team's own §4 blast-radius ranking contradicts its own sequencing.

---

## 3. The #1878-defer attack — the read-side slice is the easy half; the hard half festers

| Claim under attack | Counter-case | Evidence | Holds / survives | Severity |
|---|---|---|---|---|
| Deferring the #1878 coord/primary **write-side** to 3.3.x is correct because it is "semantics-sensitive, characterization-first" (`3.2.x.md` §Non-goals). | The forensic data names coord/primary as **the #1 crime scene** and the WRITE side as where the durability bugs actually live. The white team's own §4 table: coord/primary read scatter (D, #1878) = "**Highest** blast radius … every mission lifecycle transition"; the 3.2.0 mission "**bled here**" (#1718/#1772/#1991). Deferring it defers *the actual problem*. The read-side slice is the *easy half* (a pure `resolve_lanes_dir` extraction, #1993) that leaves the durability-bug-bearing write/entry half untouched. | `00-OVERVIEW.md` §4 (D = Highest); §5(a) "the live disease is on the **entry/projection side (and the entire WRITE side)**, not the read authority". | **HOLDS.** The slice fixes the half that was *already mostly consolidated* and parks the half that is *scattered and bug-bearing*. | **HIGH** |
| Read and write can be safely strangled in separate cycles. | They will **re-diverge**. The whole mission thesis is "no two parallel paths for one concern." Strangling the read surface onto `resolve_action_context` while the write/entry side keeps hand-juggling 3 surfaces (`implement.py:957–985` "duplicated per command") *re-creates the split* the read consolidation just removed — the write side will compose names the read side then fails to resolve. This is the exact #1718 stale-primary-under-coord class the read fix was supposed to kill. A read-only fix to a read/write split-brain is half a fix that invites regression. | `00-OVERVIEW.md` §4 (mid8 double-append #1949, NNN-strip #1978 were **P1 merge-blockers** *on the write/compose side*); §5(a). | **HOLDS.** | **HIGH** |
| There is a live circular durability bug the deferral abandons. | **#1827** (P1, open, unmilestoned): `spec-kitty merge` validates `baseline_merge_commit` *before* writing it — "circular and **unrecoverable through the tool itself**," manual `meta.json` edit required. This is a write-side coord/primary durability bug in the exact `merge.py` hotspot (maxCC 102). It is deferred with #1878 to 3.3.x. A neutral planner does not ship a "stabilization" cycle that leaves an unrecoverable merge failure in the field for a whole minor cycle. | `gh issue view 1827` (priority:P1, no milestone, "unrecoverable through the tool itself"). | **HOLDS.** | **HIGH** |

**Verdict (3):** **The #1878 defer is wrong.** It defers the highest-blast-radius surface and a live
*unrecoverable* durability bug (#1827) to 3.3.x, while shipping the easy read-side half now. The two
surfaces will re-diverge because the write side keeps composing what the read side must resolve. The
goals doc even hedges this — "Open call: a bounded, guarded #1878 read-side slice may enter G2's first
mission" — which is itself an admission the line is arbitrary.

---

## 4. Post-hoc-rationalization attack — the goals are a narrative imposed after the fact

| Claim under attack | Counter-case | Evidence | Holds / survives | Severity |
|---|---|---|---|---|
| The 3.2.x goals are "**continuations** of in-flight trajectories, not net-new pivots" (`3.2.x.md` §Corroboration). | There is **no pre-3.2.0 artifact** stating G1/G2/G3. The release-goals dir's first commit is `facd585e6` at **07:30 on 2026-06-16** — *after* the 00:55 tag. `git log --before=2026-06-16 --grep` for "release goal / doctrine governs / core-domain strangle" returns **empty**. The goals were articulated **only now**, then evidence was found to fit. "Continuation" is true only in the trivial sense that *any* narrative written from a corpus continues that corpus. | §0 timeline; `git log -- docs/release-goals/` (first entry 07:30 06-16); empty pre-date grep. | **HOLDS.** No pre-existing roadmap/issue/ADR declares these three goals. | **HIGH** |
| The goals trace "the existing #1619/#1666/#1868/#1878 epic chains." | The *epics* pre-exist (true) — but that is not the same as the *3-goal framing* pre-existing. #1619/#1666 are open P0 epics with **no milestone** assigned (`gh issue view`); #1868/#1878 were never grouped into a "G1 doctrine / G2 strangle / G3 devex" triad before 07:59 ("restructure to operator's 3 goals"). The doc retrofits a clean three-goal story onto whatever happened to land. The epics are real; the *goal taxonomy* is post-hoc. | `gh issue view 1619/1666` (priority:P0, milestone: none); commit `96af72839` 07:59 "restructure to operator's 3 goals". | **HOLDS.** Epics ≠ declared release goals. | **MEDIUM-HIGH** |
| G1 ("doctrine governs execution") is on a proven trajectory. | Even the white team concedes G1 is **the weakest** — "doctrine *changes behaviour* proof/ratchet is **absent in-range**" (Paula); "output-shaping, not yet control-flow gating" (Alphonso); "success-criterion closure pending" (Priti). G1 is asserted as a "continuation" but has *no behaviour-gating test* and *no pre-3.2.0 statement* — it is the clearest case of a goal that is narrative, not plan. | `corroboration-paula-patterns.md` G1 row ("trajectory unproven"); `corroboration-alphonso-architecture.md` G1 gap. | **HOLDS.** | **MEDIUM** |

**Verdict (4):** **The goals are post-hoc.** Authored 6.5 h after the tag, with the verdict folded in
the same morning, and with zero pre-3.2.0 statement. The "continuation, not pivot" claim is
storytelling: it is unfalsifiable (any goal written from a corpus "continues" it) and was never
pre-registered. *Concession:* the underlying engineering trajectory (the #1619 decomposition, the
ratchet wall) is **genuinely real and continuous** — the work happened. What is post-hoc is the
*three-goal narrative and its corroboration*, not the code.

---

## 5. Tracker reality-check — neglected higher-priority work a neutral planner would lead with

The 3.2.x **milestone holds exactly 5 issues** — #2000, #1993, #1971, #1900, #1888 — i.e. *only* the
naming slice (`gh issue list --milestone 3.2.x`). Meanwhile the open queue:

- **7 open `priority:P0`**, **5 open `launch-blocker`**, **63 open `priority:P1`** — and the slice
  addresses **exactly one P1** (#1888), itself a "verify-and-close," not a build.

| Issue | Priority | Why a neutral planner prioritises it over naming polish |
|---|---|---|
| **#1716** | **P0 + launch-blocker** | "Make coordination topology coherent from mission create through planning" — the *write-side* coord/primary split-authority bug. Unmilestoned; deferred into the #1878 bucket. A P0 launch-blocker outranks a mechanical `[:8]` ratchet. |
| **#1827** | P1, open | `spec-kitty merge` circular baseline failure — **unrecoverable through the tool**, manual `meta.json` edit needed. Live durability bug in the merge hotspot. Deferred. |
| **#1832** | P1, open | `agent action implement`: "claim succeeds but reports **'no workspace could be resolved'**" on *every* claim — a live **read-path** bug. The read-side slice arguably *should* cover this; it does not scope it. |
| **#1891** | P1, open | `agent --json` broken on several commands (`CommitResult is not JSON serializable`) — breaks external/CI automation. Deferred. |
| **#1666 / #1619** | **P0 epics + launch-blocker** | The parent execution-context epics the whole strategy claims to "advance" — **no milestone**, no scheduled slice beyond the naming tail. |

| Claim under attack | Counter-case | Evidence | Holds | Severity |
|---|---|---|---|---|
| 3.2.x is a "stabilization-and-depth cycle." | A stabilization cycle that leaves a P0 launch-blocker (#1716) and an *unrecoverable* merge bug (#1827) unmilestoned, while milestoning only 5 mechanical naming issues, is not stabilising the things that destabilise operators. | `gh issue list` P0/P1/launch-blocker vs `--milestone 3.2.x` (5 issues, naming-only). | **HOLDS.** | **HIGH** |

**Verdict (5):** A neutral planner would lead 3.2.1 with **#1716 (P0 launch-blocker)** and **#1827 / #1832** (live recoverable-only-by-hand bugs), not the naming ratchet. The milestone scoping reveals the
priority inversion concretely: 5 naming issues milestoned, 7 P0 / 63 P1 not.

---

## 6. Where the strategy genuinely HOLDS (forced concessions)

Per the dialectic, I concede what the evidence forces:

- **The engineering work is real.** Robbie's before/after delta is sound and *candid*: authorities
  cooled (`context.py` maxCC 17→3; `transitions.py` −227 SLOC), the ratchet law is empirically true
  (status bypass −76% under its ratchet; un-ratcheted idioms grew). The #1619 decomposition and the
  20× ratchet wall (Paula: 3→60) happened. My attack is on the *strategy/priority/narrative*, not the
  code quality.
- **The `[:8] → resolve_mid8` ratchet is genuinely cheap and correct** *as a unit of work*. It will
  close the identity gap. My objection is **ordering**, not validity — it should not be *first*.
- **Naming-first is genuinely low-risk.** The slice is byte-identical, characterization-tested, and
  shadow-path-free. It is safe. "Safe" is exactly why it is the wrong *first* move for a *stabilization*
  cycle that has unrecoverable bugs in the field.
- **The "cycle stays open" framing is honest** about G1's depth gap. The doc does not overclaim G1
  closure.

---

## 7. Net strategy verdict

**The corroboration is confirmatory, not objective; the goals are post-hoc; and naming-first inverts
the priority order the white team's own forensic data implies.** The strategy is not *wrong about the
code* — the strangler is real and working. It is wrong about **sequence and framing**: it leads a
"stabilization" cycle with the safest, smallest, most-settled slice (a verify-and-close plus a
mechanical literal-ban) while deferring the highest-blast-radius surface (#1878 write-side, ranked
"Highest" by the same squad), an open P0 launch-blocker (#1716), and live unrecoverable durability bugs
(#1827, #1832, #1891) to a later cycle. The four "independent" corroborations were authored the same
morning, after the tag, from the same corpus the goals were derived from, with verdicts pre-announced in
the commit subjects — they prove self-consistency, not correctness of priority.

**Recommended antithesis position:** keep the naming ratchet (it is good work) but **demote it from
first** — lead 3.2.1 with #1716/#1827/#1832, pull a bounded #1878 write-side slice forward (the doc
already leaves that door open), and re-run a *genuinely adversarial* scoping pass (a squad tasked to
*break* the slice ordering, not confirm it) before the cycle's priorities are frozen.
