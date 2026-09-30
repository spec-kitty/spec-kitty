---
title: 3.2.1 LEAD-slice scoring — NEUTRAL tracker / ROI / dependency-readiness pass (planner-priti)
description: Planner Priti's neutral 3.2.1 lead-slice scoring on tracker reality, dependency-readiness, ROI (impact over effort), and Eisenhower importance/urgency.
doc_status: deprecated
updated: '2026-06-16'
---
# 3.2.1 LEAD-slice scoring — NEUTRAL tracker / ROI / dependency-readiness pass (planner-priti)

> **Author:** Planner Priti (work-decomposition + delivery-sequencing). **Lens:** tracker reality,
> dependency-readiness, ROI (impact ÷ effort), Eisenhower (importance × urgency). **Posture:**
> *neutral* — no predetermined winner. The white-team corroboration was briefed to *confirm* the
> operator's naming-first intuition (primed; weak as proof). The red-team was briefed to *refute* it
> (backlash risk). I weigh both honestly and score every candidate on merits, including naming as one
> candidate among seven. **Directive 003:** every verdict below carries its live-ticket evidence.
> **Scope discipline:** investigation only — no tickets assigned, claimed, or mutated this pass.

> **Method honesty.** Severity/state are taken from the **live tickets** (`gh issue view`, verified
> 2026-06-16), not from issue prose or the (stale, self-corroborated) `3.2.x.md` §Corroboration. The
> synthesis (`DIALECTIC-SYNTHESIS.md`) is the adjudicated input; where white and red disagree I score
> on what *survives* adjudication. ROI is directional (no story-pointed estimates exist) — I band it
> S/M/L from the squad's own sizing and from the live ticket bodies.

---

## 0. Live ticket state (verified this pass — the ground truth the rest rests on)

| Candidate | # | Live title (short) | State | Priority labels | Milestone | Assignee | Note vs prior sweeps |
|---|---|---|---|---|---|---|---|
| 1 | **#1716** | coord topology coherent create→planning | OPEN | **P0 + launch-blocker** + reliability | **none** | — | live, unmilestoned P0 |
| 2 | **#1832** | implement claim "no workspace resolved" | OPEN | **P1** + bug + reliability | none | — | live read/report-path bug |
| 3 | **#1827** | merge baseline circular failure (unrecoverable) | OPEN | **P1** + bug + reliability | none | robertDouglass | live, *unrecoverable-by-tool* |
| 4 | **#1891** | `agent --json` broken | OPEN | **P1** + bug | none | LynnColeArt | live, breaks CI/orchestration |
| 5 | **#1619 / #1666** | unify exec-context / domain-boundary epics | OPEN | **P0** epic + launch-blocker (#1619) | none | #1666→robertDouglass | epics, not a slice; need a *shippable cut* |
| 6 | **#1878** write-side bounded slice | OPEN | **P2** epic | none | — | umbrella; bounded slice TBD |
| 7 | **Naming routing rider** | #2000/#1971/#1993/#1888/#1900 | all OPEN | mixed: **#1888 P1**, #1900 P2, rest none/tech-debt/enh | **3.2.x (all 5)** | stijn-dejongh (+robertD on #1971) | the *only* milestoned slice |

**Already-shipped / dropped (do not re-score):** #1899, #1915, #1918, #1949, #1978, #1917, #1916 —
all CLOSED-completed against PR #2001 with evidence comments (per the priti tracker-landscape sweep,
re-confirmed: these are *not* in the candidate set). **#1888 is a "verify-and-close + carry test"**,
*not* a build — material to its ROI below. **None of the seven live candidates is already closed.**

**Tracker inversion (the load-bearing neutral fact):** the milestone holds **exactly the 5 naming
issues**. The P0 launch-blocker (#1716), both unrecoverable/automation-breaking P1s (#1827/#1891), the
live read-path P1 (#1832), and the P0 epics (#1619/#1666) are **all unmilestoned**. That is a real,
verifiable priority inversion — it does not by itself decide the lead, but it is the single fact a
neutral planner cannot ignore.

---

## 1. Per-candidate scored table (1–5 each; 5 = strongest)

Dimensions: **Sev** = severity/priority (live); **Evid** = evidence quality (verified-real & reproducible
vs speculative); **Impact** = user/launch impact today; **Dep** = dependency-readiness (5 = start now,
unblocked); **ROI** = impact ÷ effort; **Fit** = honest advance of 3.2.x G2 per the synthesis;
**SeqRisk** = sequencing risk (5 = *low* risk / closes shadow paths; 1 = *high* risk / opens them).

| # | Candidate | Sev | Evid | Impact | Dep | ROI | Fit | SeqRisk | Σ/35 | One-line read |
|---|---|---|---|---|---|---|---|---|---|---|
| 2 | **#1832** implement read-path | 4 | 5 | 4 | 4 | **5** | 5 | 4 | **31** | Cheap report-path fix on the exact SSOT seam; *consume the resolved context, don't re-derive*. Highest ROI. |
| 3 | **#1827** merge baseline circular | 4 | 5 | 5 | 4 | 4 | 4 | 4 | **30** | Live *unrecoverable-by-tool* durability bug; bounded write-side fix in the merge transaction. Highest pain. |
| 1 | **#1716** coord topology coherence | 5 | 4 | 5 | 2 | 3 | 5 | 2 | **26** | True P0 launch-blocker; but it *is* the deep write-side problem — high blast radius, semantics-sensitive, slow. |
| 7 | **Naming routing rider** | 2 | 5 | 2 | 5 | 4 | 4 | 4 | **26** | Cheap, settled, ready-now, byte-identical; safe quick win — but low impact and plurality is verify-and-close. |
| 4 | **#1891** `agent --json` | 3 | 5 | 4 | 5 | **5** | 2 | 5 | **29** | Tiny, fully-ready, breaks CI/orchestration today; high ROI but *off* the G2 SSOT theme. |
| 6 | **#1878** write-side bounded slice | 4 | 4 | 4 | 3 | 3 | 5 | 3 | **26** | The keystone the read SSOT depends on; right *direction*, but "bounded" is unproven — scoping risk. |
| 5 | **#1619/#1666** epic slice | 5 | 3 | 4 | 2 | 2 | 5 | 2 | **23** | Strategically central but *not a slice*; the `ExecutionContext` redesign the synthesis says to defer. |

### Scoring rationale (the load-bearing per-cell reasoning)

**#1832 (Σ31) — highest.** Sev 4 (P1, live, *every* claim). Evid 5: reproduced in a real dogfood
mission (F-003, rc42), with the exact failing line identified — the claim's *final* read re-derives
instead of consuming the context it just used to create the workspace. Impact 4: every orchestrator
parsing `Workspace:`/`cat <prompt>` gets an error; the skipped prompt-regen is *dangerous* (stale
cross-mission prompt survives), not cosmetic. ROI **5**: this is a textbook S "consume-don't-rederive"
fix — the cheapest real-pain fix in the set. Fit **5**: it is *literally* the G2 thesis (route the
consumer through the resolved SSOT) applied to a live bug, not a metaphor. Dep 4: the naming sweep flags
it as likely-closeable *after* #1993 lands, so it is mildly gated, but the report-path fix is
independently startable. SeqRisk 4: closes a shadow path (the re-derivation), opens none.

**#1827 (Σ30).** Sev 4 (P1) but *effective* severity is higher — it is **unrecoverable through the
tool**; the operator must hand-edit `meta.json` and commit. Evid 5: reproduced on rc40/rc41, root cause
named (validation runs *before* the transaction writes `baseline_merge_commit`; re-run re-merges and
fails identically). Impact 5: a stabilization cycle that ships with an unrecoverable merge failure in
the field is self-defeating. ROI 4: the fix is bounded (write the field inside the transaction + resume
detects already-merged) but lives in the `merge.py` god-module (maxCC 102) so it costs more than #1832.
Fit 4 / SeqRisk 4: it is write-side coord/primary, the surface the synthesis says is *under-served*.

**#1716 (Σ26) — the P0.** Sev **5** (only P0+launch-blocker in the set). Evid 4: clearly real and
operator-visible (the split-authority "spec/setup-plan on main, then status refuses stale primary"
trap), with precise file:line evidence — but it is an *architectural* root cause, not a single repro.
Impact **5**: blocks the create→planning lifecycle. ROI **3** and Dep **2** and SeqRisk **2** are what
hold it back as a *lead*: it *is* the #1878 write-side keystone — semantics-sensitive, highest blast
radius (every lifecycle transition), characterization-first. Leading the *whole* cycle with the slowest,
riskiest, deepest item front-loads risk. It is the most *important* candidate and a poor *first* slice —
the classic important-but-not-quickest quadrant.

**Naming rider (Σ26).** Sev **2**: the live priorities are weak — only #1888 is P1 (and it is
verify-and-close), the rest are tech-debt/enhancement/none + a P2 (#1900). Evid 5: byte-identical,
characterization-tested, grep-verified. Impact **2**: the synthesis adjudicates the duplication as real
but *low-severity* (Sub-class B / tidiness debt); the recurring P1 merge-blockers were authority-logic
bugs already fixed *inside* the seam, which threading/ratcheting would not have prevented (debbie R1,
randy R-1). ROI 4: cheap and ready. Dep **5**: fully unblocked, already milestoned, already in lanes.
Fit 4 / SeqRisk 4: establishes the ratchet *tripwire* pattern (honest, partial) and is shadow-path-free
— **but** beware the #1993 half-strangle hazard (see §3): extracting `resolve_lanes_dir` for *reads*
while the write side still composes lanes paths ad-hoc can re-open the split it just closed unless #1832
(read consumer) lands with it.

**#1891 (Σ29) — the sleeper.** Sev 3 (P1). Evid 5: three concrete reproes on rc37 (`CommitResult` not
serializable; `implement --json` rejects the flag; preamble before JSON). Impact 4: breaks *external/CI
automation and the orchestrator-API contract* — exactly the integration surface a stabilization cycle
should protect. ROI **5** and Dep **5** and SeqRisk **5**: it is a tiny, fully-independent,
zero-shadow-path fix (serialize the result, add the flag, strip preamble). Fit **2** is the only thing
that demotes it: it does *not* advance G2's SSOT theme — it is pure DevEx/G3 hygiene. High intrinsic ROI,
low thematic fit for a *G2-lead*.

**#1878 bounded slice (Σ26).** Sev 4 / Impact 4 / Fit 5: it is the keystone — the read SSOT *cannot be
more consistent than the write SSOT feeding it* (synthesis verdict 10, alphonso R3). Dep 3 / ROI 3 /
SeqRisk 3: "bounded" is aspirational until scoped; the umbrella (#1878, P2) contains #1716/#1827/#1357/#1887/#1834 — a real risk that a "bounded" slice grows. The right move is to pull a *named* sliver
forward (#1827 is the cleanest such sliver), not to open the umbrella.

**#1619/#1666 epic slice (Σ23) — lowest.** Sev 5 (P0 epic) but Evid 3 and ROI 2 and Dep 2 and SeqRisk 2
sink it. The synthesis **refutes** "thread the `ExecutionContext` everywhere" as the spine: it is a
*builder redesign mislabelled as adoption* — the composite is mutable, internally split-brained
(`branch_name` ≠ `branch_ref.target_branch`), net *more* code, ~5% adopted, and the dashboard
structurally cannot consume it. As a *lead slice* this is the worst choice: largest, riskiest,
least-shippable, and the one the adjudication explicitly says to defer behind a freeze. (The epics
themselves are real and pre-existing — they advance *through* the other candidates, not as a standalone
slice.)

---

## 2. ROI ranking (impact ÷ effort — my specialty)

| Rank | Candidate | Effort band | Impact band | ROI verdict | Why |
|---|---|---|---|---|---|
| **1** | **#1832** implement read-path | **S** | High (live, every claim) | **Highest** | Smallest real-pain fix; *is* the G2 pattern; closes a shadow path. |
| **2** | **#1891** `agent --json` | **S** | High (CI/orchestration) | **Very high** | Tiny + fully ready; but off-theme for a G2 lead. |
| **3** | **#1827** merge circular | **S–M** | Highest (unrecoverable) | **High** | Bounded transaction fix; costs more (lives in merge god-module). |
| **4** | **Naming rider** | **S** (mechanical) | Low (tidiness debt) | **Medium-high** | Cheap + ready, but low-impact; value is the *tripwire pattern*, not the bug it closes. |
| **5** | **#1878 bounded slice** | **M** | High (keystone) | **Medium** | High ceiling, but scoping risk drags effort up. |
| **6** | **#1716** coord topology | **L** | Highest (P0) | **Medium-low** | High impact / high effort / high risk — ROI suffers as a *first* move. |
| **7** | **#1619/#1666** epic | **XL** | High | **Low** | Redesign, not a slice; deferred by adjudication. |

---

## 3. Dependency / sequencing graph (what must precede what)

```
                         ┌─────────────────────────────────────────────┐
                         │  WRITE-SIDE AUTHORITY (authors identity)      │
                         │  #1716 (P0, coord topology) ─┐                │
                         │  #1827 (P1, merge baseline) ─┤  #1878 umbrella │
                         │  ...#1357/#1887/#1834        ─┘  (P2)          │
                         └───────────────┬─────────────────────────────-─┘
                                         │ feeds (read SSOT ≤ write SSOT consistency)
                                         ▼
   #1993 extract resolve_lanes_dir ──► #1832 implement read-path consumes resolved ctx
   (read seam, milestoned)              (P1, live) ── likely CLOSEABLE once #1993 + read-consume land
                                         │
                                         ▼
   #2000 / #1971 / #1900  ── mechanical compose/route + ratchet tripwire (parallel, independent)
   #1888  ── verify-and-close (independent; no build)
   ───────────────────────────────────────────────────────────────────
   #1891  agent --json  ── FULLY INDEPENDENT of all of the above (DevEx/G3)
   #1619/#1666 / ExecutionContext freeze ── AFTER write side consistent + AFTER naming freeze
```

**Edges (binding constraints):**

1. **Write-side → read-side (the synthesis keystone).** #1716/#1827 (write authority) logically
   *precede* any read-side consolidation, because a read SSOT cannot be more consistent than the write
   SSOT feeding it (synthesis 10, alphonso R3). You can ship read fixes first, but they will *re-diverge*
   unless the write side stops composing what the read side must resolve.
2. **#1993 → #1832 (the half-strangle hazard).** Extracting `resolve_lanes_dir` for reads *without*
   routing the live read consumer (#1832) through it is the #1993 half-strangle flagged in research:
   it closes the read split structurally while the claim's final read still re-derives — so **#1993 and
   #1832 should land together**, not #1993 alone.
3. **Naming rider is internally parallel** (#2000/#1971/#1993/#1888/#1900 fan into ≥3 lanes), but its
   *enforcement* (extend the ratchet) must SEQUENCE LAST so it ratchets the routed state, not the
   pre-routed one.
4. **#1891 has zero edges** — startable today, independent of everything; the only thing demoting it is
   thematic fit, not readiness.
5. **#1619/#1666 ExecutionContext freeze is gated twice** — after the write side is consistent *and*
   after the naming freeze (synthesis "What is refuted" §). It cannot lead.

**Readiness summary:** Ready-now & unblocked → **#1891, #1832, naming rider, #1827** (the merge fix is
self-contained even though it logically wants the write-side cleanup around it). Gated/slow →
**#1716** (deep, semantics-first), **#1878 bounded** (needs scoping), **#1619/#1666** (deferred redesign).

---

## 4. FINAL ranked recommendation for the 3.2.1 LEAD slice

### Recommended LEAD: **#1832 (implement read-path "no workspace resolved")** — paired with **#1993** as its enabling seam

**Trade-off stated plainly.** I am choosing **highest-ROI live-bug-on-the-SSOT-seam** over both (a) the
operator's safe naming-first opener and (b) the highest-*severity* item (#1716). Here is the honest
cost of that call:

- **Why not #1716 (the P0), even though it outranks on severity?** #1716 is the most *important*
  candidate and the worst *first* candidate. It is the deep #1878 write-side keystone — highest blast
  radius, semantics-sensitive, characterization-first, slow, risky. Leading the *whole* stabilization
  cycle with it front-loads the maximum risk into 3.2.1. The neutral move is to **schedule #1716 into
  the cycle (it must NOT stay unmilestoned)** but not make it the *lead slice*. It is the lead of a
  *later, dedicated write-side patch*, sequenced right after the read-path quick wins.
- **Why not the naming rider (the operator's intuition)?** It survives adjudication as *good, cheap,
  safe work* — but as the synthesis says, it is the *smallest, most-settled gap*, its plurality is
  verify-and-close (#1888), and its headline ROI (the ratchet "can never regrow") is **overstated** —
  the ratchet is a syntax tripwire that passes today with 14 live `[:8]` sites, and the recurring P1
  bugs were authority-logic, not re-derivation, so it would have prevented none of them. Leading with it
  optimises for *safety of the first move*, not *impact*. It belongs in the cycle (it is already
  milestoned and lane-ready) — as a **parallel low-risk track**, not the headline.
- **Why #1832 wins.** It is the rare candidate that is **simultaneously**: a *live, reproduced* P1
  (real pain, not speculative), the *cheapest* real-pain fix (S), *on-theme* for G2 (it is literally
  "consume the resolved SSOT instead of re-deriving" — the thesis applied to a bug), and *shadow-path-
  closing*. Pairing it with **#1993** (the `resolve_lanes_dir` seam it should consume) avoids the
  half-strangle hazard and lands one clean read-side SSOT consolidation that *proves* the G2 pattern on
  a real defect rather than on a tidiness ratchet. It is honest about impact (a real bug closed), honest
  about effort (small), and honest about the strategy (read-side first is fine *provided* the write-side
  bugs are scheduled right behind it — which is why #1827/#1716 are the immediate follow-ons).

### Runner-up: **#1827 (merge baseline circular failure)**

**Trade-off vs the lead.** #1827 has the **highest user pain** in the set (unrecoverable-by-tool;
manual `meta.json` surgery required) and is the cleanest *named* write-side sliver to pull forward from
issue #1878. I rank it second, not first, only because (a) it lives in the `merge.py` god-module (maxCC 102),
so the fix carries more regression surface and effort than #1832, and (b) the synthesis's keystone logic
says the write side wants #1716's topology coherence around it to be durable. If the operator weights
**"never ship a stabilization cycle with an unrecoverable bug in the field"** above ROI — a legitimate
stabilization-cycle stance — #1827 becomes the lead and #1832 the fast follow. I would support that
swap; it is a values call (pain-first vs ROI-first), not a data error.

### The neutral cycle shape (lead + parallel tracks, since 3.2.x ships emergent patches)

3.2.1 is an emergent patch in an open cycle, so the realistic answer is **a lead + parallel low-risk
tracks**, not a single slice:

1. **LEAD — #1832 + #1993** (read-path SSOT, proves G2 on a live bug). *Sequence first.*
2. **Fast follow — #1827** (write-side unrecoverable bug; pull forward from #1878). *Schedule into 3.2.1.*
3. **Parallel safe track — naming rider** (#2000/#1971/#1888 + #1900, ratchet *last* as a tripwire,
   honestly scoped). Already milestoned/lane-ready; let it run in its own lanes.
4. **Parallel DevEx track — #1891** (tiny, independent, unblocks CI/orchestration). Cheap insurance.
5. **MUST schedule, do NOT lead — #1716** (the P0 launch-blocker must leave "unmilestoned" *now*; it is
   the lead of a dedicated write-side patch, not of 3.2.1).
6. **Defer — #1619/#1666 ExecutionContext freeze** (redesign, gated behind write-side consistency + the
   naming freeze, per adjudication).

---

## 5. Top-3 + dependency note + single recommendation (the message back)

**Ranked top-3 for the 3.2.1 LEAD slice:**

1. **#1832 (implement "no workspace resolved")** — live, reproduced P1; cheapest real-pain fix; *is* the
   G2 "consume-the-SSOT-don't-re-derive" thesis applied to an actual bug; closes a shadow path. **Highest ROI.**
2. **#1827 (merge baseline circular failure)** — highest user pain (unrecoverable-by-tool); the cleanest
   named write-side sliver to pull forward; costs more (merge god-module).
3. **#1716 (P0 coord-topology launch-blocker)** — highest *severity*, but the deep/slow/risky write-side
   keystone — the most important item and the worst *first* move; **must be scheduled, not led with.**

**Dependency note:** write-side authority (#1716/#1827) logically precedes read-side consolidation (a
read SSOT can be no more consistent than the write SSOT feeding it); and **#1993 must land with #1832**,
not alone, or the `resolve_lanes_dir` extraction half-strangles the read path. **#1891** is fully
independent (start anytime). **#1619/#1666 ExecutionContext freeze is deferred** behind write-side
consistency + the naming freeze.

**Single recommended lead:** **#1832, paired with #1993** — the highest-ROI, on-theme, shadow-path-closing
read-side SSOT slice; with **#1827 the runner-up** (becomes the lead only if the operator weights
"no unrecoverable bug in the field" above ROI). The naming rider stays in the cycle as a parallel
low-risk track — *not* the headline — and the P0 #1716 must be milestoned into the cycle immediately as
the lead of the dedicated write-side follow-on.
