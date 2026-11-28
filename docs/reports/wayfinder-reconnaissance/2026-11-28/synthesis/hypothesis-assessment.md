---
doc_status: draft
updated: '2026-11-28'
---

# Hypothesis assessment

Synthesis S-A, profile `synthesizer-sam`. Sources: workstreams A1, B1, B2, B3, C, C2, CX, D1, D2, E1, E2, E3, F, G1, G2, H06a, H06b.

## How to read this file

- Verdicts apply the criteria of section 6 of `01-pre-registration.md` only. The adversarial review may overturn them.
- A measure value is in the **observed** view unless stated. Kinds: `exec` executed, `static` static-derived, `hist` history-derived, `doc` document-claim. Revisions are `head` unless stated.
- What a record says is **recorded-intent** or **approved-plan** and rests on document-claims.
- A statement marked "(inference)" is the synthesiser's own.
- Exploratory observations are named and decide nothing.
- First reading: `S-A-phase1.md`. Changes since: `S-A-differences.md`. Decisive findings: `hypothesis-finding-map.csv`, where a role is relative to the hypothesis, not to the verdict.

## Summary

| | Verdict | Rests on | Sensitivity |
|---|---|---|---|
| H01 | inconclusive | M01a +14% to +15%; M01b and M01d lower | M01a, M01b from one run |
| H02 | inconclusive | 1 to 2 of 30 stopped by a gate; 4 of 30 after a recorded acceptance | How acceptance is recorded |
| H03 | supported | M03b 24.7% at component granularity | 78.6% at top level |
| H04 | inconclusive (partial) | One capability with a present claim not established | Supported if approved-plan claims count |
| H05 | supported | M05c 12.5% | Whether a ledger header counts for its entries |
| H06 | supported | 2 of 20 meet all three conditions | 6 of 20 relaxed |
| H07 | contradicted | 85.7% against 100% | What "verified" covers |
| H08 | inconclusive | 3 of 6 invariants differ in core Python; 4 if I3 counts | Edge of contradicted |
| PX-01 | stalls at a guard with no documented producer | F-E1-028 to F-E1-030 | Grep re-run at synthesis |

## H01. Local fixes eroded orthogonality

**Criteria (quoted).** "contradicted: M01a and M01b (load-time variant) are both at or below the start value plus 10%, and M01d did not rise by more than 5 percentage points; supported: at least two of M01a, M01b, M01d rose by 25% or more (M01d: 10 points or more); otherwise inconclusive."

**Window.** 2026-07-01 to 2026-09-05, provisional (approved-plan, `04-approval-and-dispatch.md`). Start read at the 2026-06-30 month end. End read at P3a (public line) and P3b (EXPERIMENTAL line). No value is read across the convergence merge.

### Deterioration

| Measure | Start | End P3a | End P3b | Change | Kind | Findings |
|---|---|---|---|---|---|---|
| M01a, cross-component import edges per 1,000 source lines | 6.602 (1,900 / 287,790) | 7.541 (3,197 / 423,962) | 7.598 (2,886 / 379,818) | +14.2% / +15.1% | static, historical | F-B1-001 |
| M01b load-time, modules in a cycle | 0.85% (9 / 1,061) | 0.69% (9 / 1,311) | 0.72% (9 / 1,251) | lower | static, historical | F-B1-004 |
| M01b load-time, largest cycle | 9 of 1,061 | 9 of 1,311 | 9 of 1,251 | same count | static, historical | F-B1-004 |
| M01b all imports, modules in a cycle | 26.7% | 28.8% | 27.1% | +8% / +2% | static, historical | F-B1-003 |
| M01c, components per code commit, median / p90 | 2 / 5 (June) | 1 / 3 (Sept) | 1 / 3 (Sept) | lower | hist | F-C-005, F-C-008 |
| M01d, share of code commits touching two or more components | 52.7% (June, n=438) | 35.1% (Sept, n=94) | 34.4% (Sept, n=224) | 17.6 / 18.3 points lower | hist | F-C-008, F-C2-010 |

Read from `evidence/B1/series.csv` and `evidence/C/m01c-m01d-components-per-commit.csv`.

- Contradiction criterion: **not met**. M01a is 14% to 15% above the start value, more than the 10% allowed.
- Support criterion: **not met**. No measure rose by 25% (M01d: 10 points). M01b and M01d fell.
- **Verdict: inconclusive.**

### Periods before and after (control)

| Period | M01a | M01b load-time share | M01d |
|---|---|---|---|
| Before: 2026-03-31 to 2026-06-30 | 5.342 to 6.602 (+23.6%) | 1.72% to 0.85% | T1 54.2% (513 / 947) |
| Window: 2026-06-30 to line ends | 6.602 to 7.541 / 7.598 (+14% / +15%) | 0.85% to 0.69% / 0.72% | T2 pooled 37.4% (677 / 1,809) |
| After: merge result to head | 7.598 to 9.249 (+21.7%) | 0.72% to 0.67% | T3 34.3% (1,039 / 3,026) |

Findings: F-B1-001, F-B1-004, F-C-007, F-C2-009. C took T3 from the merge on 2026-09-05 (declared breach, 4 commits). M01a rises more in both neighbouring periods than in the window; the window is not distinguished from them (inference).

### Sibling series

`spec-kitty-events`, share of code commits touching two or more components: T1 75.0% (n=24), T2 44.8% (n=87), T3 29.5% (n=237), or 41.0% (n=105) without 141 commits that repeat a core commit's date and subject (F-C-022; C2's test for imported commits differs, F-CX-009). The sibling falls in the same direction as core.

### Convergence, reported apart

The merge `2554bd13ad` has the same tree as its EXPERIMENTAL parent. Against the public parent it differs in 3,179 files; under `src/` in 481 files (+17,449 / -61,454 lines) in 63 components. The merge result has 60 fewer modules and 44,144 fewer source lines than P3a; M01a is 7.598 against 7.541 (F-B1-002, F-C-012, F-C2-004; replicated, F-CX-011). No trend is drawn across it.

### Cause, reported apart

These sub-measures are at most "consistent with" a reading. None is a verdict.

- M01e. Corrective maintenance is the largest class of code commits in every period: 53.7%, 46.7%, 53.7% (C); 57.1%, 52.8%, 62.1% (C2). Rule against reading: 38 of 50 in both runs; the rule sets agree on 89.4% of 6,345 commits (F-C-004, F-C-013, F-C2-006, F-CX-002).
- M01f. Not replicated in T2 (1.65 against 5.95 per 1,000 changed lines). Eleven of eighteen class cells rest on fewer than 20 commits (F-C-014, F-C-015, F-C2-014, F-CX-006). **Not usable to rank classes.**
- M01g. A GitHub review by another account: 5 of 40 sampled commits in T1, 0 of 40 in T2 and in T3; replicated exactly (F-C-016, F-C2-016, F-CX-007). Reviews recorded outside GitHub's review object are not counted.

Not consistent with "corrective changes spread wider": corrective commits touch fewer components than capability-growth commits in every period, in both runs (F-C-006, F-C2-008). Authorship was recorded (F-C-017) and is not a measure of supervision.

### Strongest evidence against the verdict

- Toward support: M01a rises in every period, from 3.3 at P0 to 9.2 at head (F-B1-001). With all imports, 33.1% of modules are in a cycle at head, and the largest cycle jumps (19% of modules in June, 42% end of July, 12% at both line ends) on single function-level imports (F-B1-003, F-B1-005; exploratory).
- Toward contradiction: load-time cycles stay below 2% of modules and none spans two components (F-B1-004). M01d falls by more than 17 points.
- On the measure: the commit is not a uniform unit. Squash-style commits are 42.6%, 21.0% and 44.2% of code commits by period (F-C-030, F-C2-011; investigators' readings F-C-032, F-C2-032).

### Not measured, and limits

- M01a and M01b come from one workstream, cross-checked against `grimp` at two revisions.
- Dynamic imports and non-Python coupling are not counted.
- Prior exposure: the coordinator had seen raw M01b counts, and proposed the same window dates.

## Blind replication (C against C2)

Rule: a measure is replicated when the two values differ by 10% or less (F-CX-001 to F-CX-013).

| Measure | Result | Detail |
|---|---|---|
| Volume denominators, all classes | replicated | 25 of 25 rows |
| Volume by commit class | not replicated | 30 of 60 rows; rule order differs |
| M01c, all classes | replicated | 18 of 18 rows |
| M01c by class | partly | 29 of 108 rows not replicated |
| M01d, all classes, component level | replicated | every period; 14 of 14 months |
| M01d, top-level variant | partly | T2 EXPERIMENTAL 11%, fork-window segment 12% |
| Co-change top pairs | replicated | 14 or 15 of 15 shared per period |
| M01f, file-level edges per 1,000 lines | not replicated in T1 (4.31 / 5.36), T2 (1.65 / 5.95); replicated in T3 (3.62 / 3.33) | different samples |
| M01f, pairs new to the graph | replicated in T1; not in T2, T3 | |
| M01g | replicated exactly | same 120 commits, same answers |
| M02 frames | replicated | 666 / 698; 1,262 / 1,264 |
| M02 origin split | replicated | identical counts; 4 and 2 of 30 commits shared |
| M02 detection route | not replicated | a person 22 / 16; untraceable or not determinable 7 / 11 |
| M02 acceptance | not comparable | different definitions |
| Events sibling series | replicated by month for the same component set | |
| Recurrence, components | replicated | 69 / 68 of 88 |
| Refix within 14 days | replicated in T1; not in T2, T3 | 84.7% / 70.8% in T3 |
| Convergence merge effect | replicated | within 2% |
| Direction of change between periods | 198 of 220 agree | every all-class M01c and M01d step agrees |

The measures that decide H01 from history (M01d, M01c all classes) replicate. The causal sub-measure M01f and the M02 detection route do not.

## H02. Mission-local acceptance misses ecosystem regressions

**Criteria (quoted).** "contradicted: at least 70% of M02a were stopped by an automated gate before reaching `main`; supported: at least 50% of M02a reached `main` after passing their Mission's acceptance and were then detected by a person or a later, unrelated run; and that rate exceeds M02b's by 15 points or more; otherwise inconclusive. If more than a third are untraceable: not assessable."

| | M02a (C) | M02a (C2) | M02b (C) | M02b (C2) |
|---|---|---|---|---|
| Frame (sample 30 each) | 666 | 698 | 1,262 | 1,264 |
| Defect introduced in the same pull request, never on `main` | 13 | 13 | 21 | 21 |
| Introduced by an earlier change on `main` | 15 | 7 traced, 10 untraceable | 9 | 8 |
| Origin untraceable | 2 | 10 (and 9 weakly traced) | 0 | 1 |
| Detected by an automated check before `main` | 1 | 2 | 3 | 5 |
| Detected by an automated run after `main` | 0 | 0 | 1 | 1 |
| Detected by a person | 22 | 16 | 8 | 8 |
| Detector not named | 7 | 11 | 18 | 16 |
| Reached `main` from a Mission with acceptance recorded before | 4 | 3 in later pull requests | 5 | not comparable |

All history-derived, head. Findings: F-C-018, F-C-019, F-C-020, F-C-021, F-C2-017 to F-C2-021, F-CX-008. C's table was re-tabulated from `evidence/C/m02-trace-sample.csv`.

- Contradiction criterion: **not met** (3% and 7%).
- Support criterion: **not met**. 4 of 30 (13%) in M02a against 5 of 30 (17%) in M02b.
- Not-assessable rule: C 2 of 30 untraceable; C2 10 of 30, which is one third and not more. Not triggered on the stated counts. With C2's 9 weak traces counted as untraceable it would be.
- **Verdict: inconclusive.**

**Strongest evidence against.** Toward support: 15 of 30 sampled cross-component fixes corrected a defect that had reached `main`, all 15 found by a person; the comparator has 9 of 30 (F-C-019, F-C-020). The acceptance clause is what fails, and acceptance is under-recorded: 430 of 858 Mission `meta.json` files carry `accepted_at` (F-C-021). 0 of 13 acceptance checks look at another repository, a pin, a contract or a gate result (F-E1-032, static).

**Limits.** Nine of 24 introducing changes are blame candidates. The detector is taken from text, which often does not say whether a reviewer was a person or an agent squad.

## H03. Conceptual boundaries exceed implementation boundaries

**Criteria (quoted).** "contradicted: M03a shows no unrecorded violation and fewer than 25 recorded exceptions, and M03b is 90% or more; supported: any unrecorded violation of the enforced tier, or more than 100 recorded exceptions, or M03b below 70%; otherwise inconclusive." Core Python decides; Java qualifies.

| Measure | Core Python, head | Kind | Findings |
|---|---|---|---|
| M03a, unrecorded violations of the enforced tier | 0 of 8,332 module edges | exec + static | F-B1-010 |
| M03a, recorded exceptions | 48 ledger entries in 4 ledgers, standing for 228 upward import statements | exec + static | F-B1-011 |
| M03b, component granularity (74 components) | 162 of 656 edges, 24.7%; by weight 30.1% | static | F-B3-002 |
| M03b, top-level granularity (6 packages) | 11 of 14 edges, 78.6%; by weight 91.2% | static | F-B3-001 |
| M03b without the general layer rule | 23.9% / 57.1% | static | F-B3-009 |
| M03c, lines with no intended internal model | 487,284 of 524,936, 92.8% (reported, not scored) | static | F-B1-013 |

- Contradiction criterion: **not met** (48 exceptions; M03b below 90% by edges at both granularities).
- Support criterion: **met** through M03b below 70% at the pre-registered unit, the component of section 3. The other two limbs are not met.
- **Verdict: supported.**

What the verdict says. 464 of the 656 edges join two components inside one top-level package, and no frozen record speaks to them (F-B3-002, F-B3-006). Of the 192 edges that cross a top-level package, 84.4% are documented, and no documented prohibition without a recorded exception is observed (F-B3-003). The support comes from the absence of a recorded model inside `specify_cli`, not from a breach of one: "no intended model", not "misaligned".

**Disagreement kept.** One string-literal dynamic import (`charter.offering.missions.glossary_hook` to `glossary.attachment`) crosses a forbidden pair. B1 files it as outside the rule's graph and noted in the rule's docstring (F-B1-012). G2 counts it as one edge in no recorded ledger (F-G2-001). On G2's reading the first support limb is met as well.

**Java (qualifies).** Charter: 0 violations in 136 executed architecture tests; 9 exemption lines; 2.8% of lines under no rule (F-B2-005, F-B2-006; exec). Events: 0 violating package edges by static check; 4 exceptions; 5.5% of Java lines under no rule; build blocked (F-B2-011, F-B2-012; static). doc-kitty has no enforced model (F-B2-020). The Java results do not show what core shows.

**Strongest evidence against.** At top-level granularity M03b is 78.6% by edges, which is inconclusive. Granularity moves the value by 53.9 points, more than any rule choice (F-B3-009).

**Declared breaches.** See the last table (F-E3-001, F-D1-027 for the gate run).

## H04. Extraction has not consistently achieved independence

**Criteria (quoted).** Counted "only over cells where recorded intent claims independence": "contradicted: every claimed cell is observed as established, by executed evidence; supported: a claimed cell is observed as not established for two or more capabilities; one capability only: inconclusive, reported as partial; a blocked test makes its cell not assessable."

Declared: `evidence/A1/component-catalogue.csv` (document-claims; F-A1-029). Observed: `evidence/D1/independence-matrix.csv`, `evidence/D2/independence-matrix.csv`. E established, P partly, N not established, NA not assessable. **Bold**: claimed by a record. *Italics*: claimed as a planned state, cut-over pending.

| Capability | Logical | Contract | Source | Distribution | Deployment |
|---|---|---|---|---|---|
| Charter activation | E (contested) | **P** | N (silent) | N (silent) | N (silent) |
| Charter offering, Python in core | **P** | **P** | **NA** | N (not pursued) | *N* |
| Charter offering as served (Java) | **N** | **P** | **P** | **E** | **E** |
| Events contracts, Python package | **P** | **P** | **P** | **E** | library |
| Events contracts, bundles | **P** | **P** | **P** | **E** | NA |
| Status ledger and reducer | **P** | **P** | P (silent) | P (silent) | N (silent) |
| Events read service | **P** | **P** | **P** | **E** (build NA) | **E** |
| Events write service | *N* | *P* | *NA* | *P* | *P* |
| Mission state machine | P | P | P | P | N |
| Work-package state machine | N | P | N | N | N |
| Packs | **P** | P (contested) | **P** | **P** | NA |
| Glossary | P (contested) | NA | NA | N | N |
| Tracker client | **E** | P (silent) | **P** | **E** | library |
| doc-kitty | **E** | **P** | **NA** | **P** | NA |

Findings behind the cells: F-D1-003 to F-D1-028, F-D2-001 to F-D2-017.

- Contradiction criterion: **not met**. Of the 34 cells claimed as a present fact, 9 are established, 22 partly established, 1 not established and 2 not assessable. The mapping of catalogue rows to the twelve capabilities is the synthesiser's (inference).
- Support criterion, strict reading: **one capability**. Charter offering as served, logical: the charter repository records itself as canonical owner of charter structure (recorded-intent, charter ADR-0015), while core answers offering reads in-process with its own Python and schemas; 118 divergences are recorded, 111 open (F-D2-016, F-D2-017, F-B2-031).
- Second candidate: events write service, logical. Core's Python writer performs every status write at head (F-D2-017, exec). The claim "one writer" is an **approved-plan** whose binding the records themselves call pending (F-A1-033, F-D2-020). Under ruling R4 an unexecuted approved plan is not an unmet claim.
- Third candidate: the work-package state machine is code in core, mirrored as code in `spec-kitty-events` against a pinned core commit (F-D1-024, F-D1-012). No catalogue row claims it.
- **Verdict: inconclusive, reported as partial.**

**Sensitivity.** If the catalogue's "claimed" label is applied without separating approved plans from present claims, two capabilities have a claimed cell not established and the criterion for **supported** is met. That reading is the architect's to rule on.

**Beside the verdict.** Distribution is established where a separate artefact is published. Logical ownership is established in 0 of 5 service rows: each responsibility a service names is still carried out by Python in core (F-D2-014 to F-D2-017).

**Not assessable.** Every executed Java check of `spec-kitty-events` (HTTP 429; F-D2-002). A stub behind `charter.offering.api` was not attempted (F-D1-015). Neither is evidence of a defect.

## H05. Compatibility sediment accumulated

**Criteria (quoted).** "contradicted: at least 70% of ledgers are flat or shrinking, and at least 70% of entries carry a reference or retirement condition; supported: fewer than 40% on either measure; otherwise inconclusive."

| Measure | Value | Kind | Findings |
|---|---|---|---|
| M05a, population | 75 ledgers: 57 file ledgers with 3,357 entries (2,265 in two lint baselines), 18 marker scans with 1,612 markers | static, head | F-E1-016, F-E1-017 |
| M05b, file ledgers flat or shrinking, 2026-09-07 to 2026-11-28 | 38 of 57 (66.7%): 6 shrinking, 32 flat, 19 growing | hist | F-E1-018, `ledger-totals.json` |
| M05b, ledgers that existed on 2026-09-07 | 24 of 27 (88.9%); 30 were created in the range | hist | F-E1-018 |
| M05c, entries with an issue, ADR or retirement condition | 420 of 3,357 (12.5%); 336 of 1,092 (30.8%) without the two lint baselines; inline markers 44 of 429 (10.3%) | static | F-E1-020 |
| M05d, age (reported) | median 84 days, maximum 279; a lower bound | hist | F-E1-021 |

- Contradiction criterion: **not met**.
- Support criterion: **met** by M05c under every denominator reported. M05b is above 40% under both.
- **Verdict: supported.**

**Strongest evidence against.** M05c counts a reference on the entry itself. Read by hand, with the ledger header counted for its entries, a retirement condition is present for 22 of 30 sampled entries and 16 of 30 in a second sample (F-E1-025). Under that reading M05c is not below 40%. Growth at ledger level is mostly new gates registering existing constructs (F-E1-019; investigator's reading F-E1-035, low confidence).

**Deviation.** E1 reports net change split by ledger age, not gross additions.

## H06. Architectural knowledge is fragmented

**Criteria (quoted, first run).** "contradicted: 16 or more answered from one authoritative source, correct against the code, with no contradicting source found; supported: 10 or fewer; otherwise inconclusive."

| Count, run 1, of 20 | Value |
|---|---|
| Answered | 19 yes, 1 partly |
| One source cited | 18 |
| Cited source authoritative under the repositories' own rules | 11 yes, 8 no, 1 unclear |
| Correct against code | 12 correct, 8 partly correct, 0 incorrect |
| Contradicting documentation source found | 10 |
| Meets all three | **2** (questions 11 and 13); 6 with four borderline judgements relaxed |
| Run 2, with agent-guidance files | 12 answers changed; correct 13; meets all three 2 |

Findings: F-H06b-013 (decisive), F-H06b-001 to F-H06b-012, F-H06a-021; exec + static + doc, head; `evidence/H06b/checks.csv`.

- Support criterion: **met** (2, or 6, against a threshold of 10). **Verdict: supported.**

**Disagreement kept (H06a against H06b).** H06a reports three questions with no single answering document, among them Q11 (F-H06a-021). H06b scores Q11 as meeting all three conditions and counts 19 as answered. The verdict does not depend on it.

**Strongest evidence against.** No answer is incorrect, and 12 of 20 are fully correct. Dropping the authority condition gives 7 or 8 of 20, still within the support range.

**Declared breaches.** See the last table. The coordinator wrote the questions after reading core's `CLAUDE.md`.

## H07. Execution infrastructure is comparatively immature

**Criteria (quoted).** Over responsibilities that recorded intent places inside the ecosystem: "contradicted: the verified share for execution is within 20 points of the verified share for coordination; supported: it is 30 points or more below; otherwise inconclusive."

| | Execution (M07a) | Coordination (M07b) |
|---|---|---|
| Responsibilities | 15 | 15 |
| Verified by execution | 12 | 15 |
| Delegated by recorded intent (excluded) | 1 (dispatch) | 0 |
| Missing | 2 (on-demand cancellation, human attachment) | 0 |
| Verified share | 12 of 14, 85.7% | 15 of 15, 100% |

Findings: F-F-001, F-F-002 (decisive), F-F-005, F-F-011, F-F-012, F-F-024; exec + static, head; `evidence/F/m07a-execution-responsibilities.csv`.

- The gap is 14.3 points. Contradiction criterion: **met**. **Verdict: contradicted.**

**Strongest evidence against.** "Verified" means that named tests covering the responsibility pass. The 11 verified responsibilities held by core record, prepare or gate. Starting and supervising are held by an external provider; stopping on request and attaching a person are held by no repository read (F-F-003, F-F-011, F-F-012, F-F-024). Supervision rests on a probe the workstream wrote (F-F-011). The model that ran a work package is recorded nowhere in core (F-F-014).

**M07c, single case, not generalisable.** This investigation's parallel executors used none of core's execution-unit identities (F-F-022, F-F-023).



## H08. Technology-agnostic invariants are viable

**Criteria (quoted).** "contradicted: for four or more invariants, the contract-only check cannot be written or gives a different result from the implementation-aware check; supported: for five or more, both checks can be written and agree, in both languages; otherwise inconclusive."

G1 saw public contracts and metadata only; G2 saw the implementation. All executed, head.

| Invariant | Core Python: G1 / G2 | Agree? | Charter Java: G1 / G2 | Agree? |
|---|---|---|---|---|
| I1 no new cycles | 0 new at package level against a substituted baseline (rc8 wheel) / 1 unledgered cycle edge, 2 cycles | no | 0 new / acyclic main scope | yes |
| I2 no private access | 593 entries break a rule / 0 new against recorded baselines | no | 6 imports in one package pair / the same 6 | yes |
| I3 no reverse dependency | 312 import names from two lower layers / 229 sites, all in ledgers | same imports, different verdict | 0 / 0 | yes |
| I4 no CLI concern in domain | 9 references in 5 modules / 8 sites in 4 files | yes | 0 / 0 | yes |
| I5 no state mutation outside owner | cannot give pass or fail / 0 confirmed outside writers for 3 ledgers, 11 allow-listed for the status log | cannot be written | partial / 0 after reading 18 sites | partly |
| I6 independent build, install, test | fails without the pack tree, passes with it / the same | yes | not completed (environment) / builds, 16,177 tests pass | not assessable |

Findings: F-G1-001 to F-G1-012, F-G2-001 to F-G2-012, F-G2-015.

- Support criterion: **not met**. Both checks agree in both languages for I4 only (I6 is not assessable on one side).
- Contradiction criterion: three invariants firmly differ or cannot be written in core Python (I1, I2, I5). I3 is the fourth if a different count and a different pass or fail count as "a different result"; both agents found the same imports, in the same two packages, and none elsewhere.
- **Verdict: inconclusive**, at the edge of contradicted.

**What separates the two agents (inference from F-G1-001, F-G1-003, F-G1-005, F-G2-015).** In core Python, "new" and "private" are decidable only with the recorded baselines and ledgers, which sit in test files. In Java, four invariants were checkable from the documented model and agreed.

**Limits.** This tests expressibility, not Wayfinder, which does not exist. G1's charter build was lost to memory and cache contention (coverage limit).

## PX-01

**Outcome: stalls at a guard with no documented producer.** A `research` Mission created and advanced with documented commands passed scoping and methodology and was blocked at gathering, the third of six steps (F-E1-028, exec, head).

- The guard counts rows of type `source_documented` in `mission-events.jsonl`. In `src/` the string occurs only in the reader and the guard; tests write the rows by hand (F-E1-029). The grep was re-run at synthesis with the same result (synthesis-run).
- The guard looks for `source-register.csv` in the Mission directory; the prompt, both templates and the glossary page name `research/source-register.csv` (F-E1-030).
- A later guard waits in the same way for a `publication_approved` row; that step was not reached (F-E1-029).

Not covered: a producer outside core. No workaround was tried.

## Acceptance scenarios

Each is classified, not passed or failed. The scenarios are proposals.

| Scenario | Classification | Basis | Findings |
|---|---|---|---|
| AS-01 Charter internals change without consumer change | not demonstrated | 80 of 101 consumer files import behind `charter.activation.api`; no stub tried behind `charter.offering.api` | F-D1-015, F-B3-011, F-G2-003 |
| AS-02 External runner records and retrieves evidence without the CLI | partly | Reading: the released read service answered a log written by core. Writing: the write service starts in a rehearsal; no write was sent | F-D2-003, F-D2-008, F-D2-012, F-D2-017 |
| AS-03 New state-machine configuration needs no unrelated change | partly | Mission types are pack data; the latest addition (2026-02) touched 5 files, 0 Python; none under the present layout; guards are Python | F-D1-024, F-D1-025, F-E1-031 |
| AS-04 New tool adapter preserves mission semantics | partly | The latest agent touched 35 files in 12 components, 10 of them Python source; semantics not measured | F-D1-025 |
| AS-05 Standalone installation provides declared capabilities | demonstrated for released artefacts | Three wheels install alone; two service binaries run from release assets. Events Java build not assessable | F-D1-008, F-D2-003, F-D2-004, F-D2-002 |
| AS-06 Unauthorised dependency is rejected | partly | Reverse dependency 5 of 6 detected; private import 3 of 6 | F-E3-002, F-E3-003 |
| AS-07 Temporary exception stays attributable and bounded | partly | Bounded: 24 of 27 older ledgers flat or shrinking. Attributable: 12.5% of entries carry a reference; owner present for 2 of 30 | F-E1-018, F-E1-020, F-E1-025 |
| AS-08 Interrupted assignment stays identifiable and recoverable | partly | Work package, consolidation and Op recovery are tested; nothing records what the executor process was doing | F-F-017 |
| AS-09 Lost projection (derived status snapshot) is reconstructable | demonstrated for lane state | 12 of 12 rebuilt, lanes equal for 80 work packages; byte-identical to the committed file in 0 of 12 | F-D1-026, F-D1-020 |
| AS-10 Wayfinder unavailability does not disrupt operations | not assessable | Desk only. No subject exists. Not empirical | none |
| AS-11 Compatible release does not force lockstep upgrades | partly | Read service rc.2 replaces rc.1. Python ranges admit one version each, so the test collapsed. Core's validator accepts 0 of 19 packs at open-packs head | F-D2-011, F-D1-003, F-D1-013, F-D1-021, F-D2-013 |
| AS-12 Mission acceptance does not conceal ecosystem violations | not demonstrated | 0 of 13 acceptance checks look beyond the Mission's repository; 15 of 30 sampled fixes corrected defects already on `main` | F-E1-032, F-E1-033, F-C-019, F-E3-006 |

## Deviations and breaches that touch a verdict

| Item | Touches | Effect |
|---|---|---|
| B1 could not run the layer gate (memory) | H03 | E3 and D1 ran it: 80 of 80 |
| B3 saw part of B1's output before fixing its rules | H03 | No category count existed yet |
| C's T3 starts 2026-09-05; "landing fold:" subjects classed by code, not by the written rule | H01 | 4 commits; about 120 commits, by class only |
| E3 batched 13 mutations and ran 66 of 310 gate files | AS-06, AS-12 | Detection is a lower bound |
| F could not commit its comparator list | H07 | Timestamp precedes classification |
| H06a had guidance files in context; H06b inferred the questions | H06 | Would raise the count, if anything |
| Events Gradle build never ran | H03, H04, mutations | Cells not assessable; never a defect |
