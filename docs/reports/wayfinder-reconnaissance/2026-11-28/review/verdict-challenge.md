---
doc_status: draft
updated: '2026-11-28'
---

# Verdict challenge

Reviewer V, profile `paula-patterns`, squad-delegate mode (one lens, no scout swarm). The profile's success definition asks for a release decision and a scoped follow-up issue; the envelope forbids both, and the envelope wins.

## Method

- For each of H01 to H08 and PX-01 I applied section 6 or 7 of `01-pre-registration.md` to the workstream measure tables and the raw artefacts, and wrote my verdict to a scratch file before opening `synthesis/hypothesis-assessment.md`. The scratch file is reproduced in section 12.
- Raw artefacts opened: B1 `series.csv`; C `m02-trace-sample.csv`; A1 `component-catalogue.csv` and `decision-timeline.csv`; the D1 and D2 `independence-matrix.csv`; E1 `ledger-totals.json` and `ledger-sample-30.csv`; E3 `detection.csv`; F's two classification files and `coordination-responsibilities.txt`; G1 `invariant-results.csv`; H06b `checks.csv`.
- One command reached a repository: a `grep` for `source_documented` and `publication_approved` under `src/` and `packs/built-in/` of the core checkout (read-only). No test, build or download was run.
- Figures marked "reviewer-computed" are my own arithmetic over a named artefact. They are exploratory and decide nothing by themselves.
- I did not reproduce findings. That belongs to the reproduction reviewers.

## Outcome

| | My verdict | Synthesiser's | Result |
|---|---|---|---|
| H01 | inconclusive | inconclusive | agree |
| H02 | inconclusive | inconclusive | agree |
| H03 | supported | supported | agree, with a qualification on what is supported |
| H04 | inconclusive | inconclusive (partial) | agree on the verdict; the label "partial, one capability" is not robust |
| H05 | inconclusive | supported | **overturn** |
| H06 | supported | supported | agree |
| H07 | contradicted | contradicted | agree; robustness low |
| H08 | contradicted (core Python decides it) | inconclusive | **overturn** |
| PX-01 | stalls at a guard with no documented producer | the same | agree |

6 of 8 hypothesis verdicts agree, 2 are overturned. 11 of 12 scenario classifications agree, 1 is changed (AS-05). Both the original and my result stand in the record; the architect decides.

Two of my nine prior verdicts differ from what I report here (H05, H08). Both changes came from raw artefacts opened after the prior note.

## 1. H01: inconclusive (agree)

Window start at the 2026-06-30 month end, end at P3a and P3b (`evidence/B1/series.csv`; F-B1-001, F-B1-004; F-C-008).

| Measure | Start | End P3a / P3b | Change |
|---|---|---|---|
| M01a | 6.602 | 7.541 / 7.598 | +14.2% / +15.1% |
| M01b load-time share | 0.85% | 0.69% / 0.72% | lower |
| M01d | 52.7% (June, n=438) | 35.1% (n=94) / 34.4% (n=224) | lower |

0 of 3 measures rose by 25%. M01a is above the start value plus 10%, so the contradiction criterion fails on one limb. Inconclusive.

Checks:

- Criterion adapted: no. The phase-1 file has the same reading.
- Trend across the convergence: one sentence does it. "M01a rises in every period, from 3.3 at P0 to 9.2 at head" (strongest evidence against) reads one line through the merge `2554bd13ad`. The per-period table beside it is correct. Note.
- Paired workstreams: M01d and M01c replicate (F-CX-003, F-CX-004). M01a and M01b have no replication at all; C2 did not measure them. The synthesis says so.
- Breaches: C's T3 boundary does not touch the window comparison.

**Something the assessment does not say (reviewer-computed, exploratory).** M01a counts edges whose two ends lie in different components, so it moves when a package is split. From the same `series.csv`:

| Period | Components | Share of module edges that cross a component | All module edges per 1,000 lines | M01a |
|---|---|---|---|---|
| 2026-03-31 to 2026-06-30 | 31 to 71 | 43.2% to 49.8% | 12.35 to 13.26 (+7.4%) | +23.6% |
| Window, to P3a / P3b | 71 to 79 / 77 | 49.8% to 55.2% / 54.6% | 13.26 to 13.65 / 13.90 (+2.9% / +4.8%) | +14.2% / +15.1% |
| Merge result to head | 77 to 74 | 54.6% to 58.3% | 13.90 to 15.87 (+14.2%) | +21.7% |

Before the window, most of the M01a rise coincides with the component count more than doubling. In the window the granularity-free density moves by under 5%. After the convergence the component count falls and density still rises by 14%. This does not change the verdict, because M01a is the pre-registered measure. It does change the sentence "M01a rises more in both neighbouring periods than in the window; the window is not distinguished from them": on the granularity-free reading the period after the convergence is distinguished, and the period before is not comparable.

## 2. H02: inconclusive (agree)

From `m02-trace-sample.csv` (F-C-018 to F-C-021) and F-C2-018 to F-C2-021:

- Stopped by an automated gate before `main`: 1 of 30 (C), 2 of 30 (C2). Threshold 70%. Not contradicted.
- Reached `main` from a Mission with acceptance recorded on or before the merge, then found by a person: 4 of 30 in M02a against 5 of 30 in M02b. Threshold 50% and 15 points above the comparator. Not supported.
- Untraceable origin: 2 of 30 (C), 10 of 30 (C2). Ten is one third, and the rule says "more than a third".

Checks:

- C against C2 is not averaged. Origin replicates (13 / 15 / 2 in both), detection does not (a person: 22 against 16), acceptance is not comparable (F-CX-008). The table shows both.
- The not-assessable rule is one count away in C2 (10 of 30, plus 9 weak traces). The synthesis states this. I would put it in the summary table as the sensitivity; "how acceptance is recorded" is the second sensitivity, not the first.
- "430 of 858 Mission `meta.json` files carry `accepted_at` (F-C-021)" is in that finding's disconfirmation field, not its claim: a search note used as a measured value. Note.

The support criterion fails on its acceptance clause, which was read from `meta.json` at head by one reader, with 9 of 24 introducing changes being blame candidates. The verdict is as much "not measured well" as "not shown".

## 3. H03: supported (agree, qualified)

Core Python decides. M03a: 0 unrecorded violations by static check and by the gate's own collector functions (F-B1-010); 48 ledger entries (F-B1-011). M03b at the pre-registered component unit: 162 of 656 edges, 24.7% (F-B3-002). Below 70%, so the support criterion is met on that limb.

Checks:

- Unit: section 3 of the pre-registration fixes the component as the second-level subpackage. Using 24.7% and not 78.6% follows the pre-registration. No adaptation.
- "More than 100 recorded exceptions": the synthesis counts 48 ledger entries and reports the limb as not met. The unit of an "exception" was not pre-registered. The same finding gives 228 upward import statements behind those entries, and F-G2-003 gives a second recorded baseline of 231 (file, module) pairs for the `charter.activation.api` door. Under either count the limb is met. The verdict is the same; its description changes. "The support comes from the absence of a recorded model ... not from a breach of one" is true of M03b only. Minor.
- Breach: B3 printed `layer-edges-head.csv`, all 14 top-level edges with weights, before fixing its mapping rules. The breach table says "no category count existed yet". For the top-level variant (78.6%), which is the document's strongest evidence against, B3 had seen every edge it then classified. The decisive full-granularity figure is 45 points below the threshold and no rule choice tested moves it by more than 21.5 points (F-B3-009), so the verdict survives. Note.
- Decisive set: `hypothesis-finding-map.csv` omits F-B1-006 (the 656-edge table) and F-A1-031 (the frozen documented table), which M03b is computed from. Minor.
- F-B3-008 (0 of 8 documented may-depend pairs unused; documented must-not pairs observed only where ledgered) points toward contradiction and is cited in no final document. Note.

## 4. H04: inconclusive (agree); the count of capabilities is 0, 1 or 2

The observed cells are investigators' judgements (F-D1-031 and F-D2-021 are interpretation records, medium confidence, one judge per cell). The declared column is the synthesiser's own mapping of A1's catalogue rows onto the twelve capabilities. Neither is a measurement in the strict sense, and the two synthesis documents map differently:

| Choice | `hypothesis-assessment.md` (S-A) | `independence-and-contracts.md` (S-B) |
|---|---|---|
| Cells counted as claimed | 34 | 43 |
| Established / partly / not established / not assessable | 9 / 22 / 1 / 2 | 10 / 29 / 2 / 2 |
| Charter service, logical "not established" | a present claim (counts) | "tied to a cutover that has not happened" |
| Work-package state machine, logical | D1's "not established"; "no catalogue row claims it" | declared "claimed"; cell changed to "partly (disputed)" against D1 |
| D1's and D2's cell values | "adopted unchanged" | five changed |

Three hinges, each decided after the data were seen:

1. Do approved-plan claims count (write service, logical)? If yes: 2 capabilities, supported. The synthesis names this hinge.
2. Is the charter service's logical claim present or planned? S-A says present, S-B says planned. If planned, S-A's "one capability" becomes none.
3. Is the work-package state machine claimed, and does D1's cell stand? S-B says claimed and replaces D1's value with its own. With S-B's declared value and D1's observed value, it is a second capability on a present claim, and the support criterion is met with no approved plan involved.

So the outcomes are: none (inconclusive, not partial), one (inconclusive, partial), two (supported). "Inconclusive" is the right report of that spread. "Partial, one capability" is one combination among several and should not be carried forward as a finding. Two disagreements were smoothed and should be shown raw: D1 against the synthesiser on the work-package state machine, and D1 against D2 on charter activation, merged to "partly".

Also: M04d collapsed (each range admits one published version, F-D1-003) and no stub was tried behind `charter.offering.api` (F-D1-015), so the contradiction criterion was never reachable in this run. A coverage limit.

## 5. H05: I overturn supported to inconclusive

Values (F-E1-018, F-E1-020, F-E1-025; `ledger-totals.json`; `ledger-sample-30.csv`):

| Measure | Reading 1 | Reading 2 |
|---|---|---|
| M05b, ledgers flat or shrinking | 38 of 57 (66.7%), new ledgers counted as growing | 24 of 27 (88.9%), ledgers that existed on 2026-09-07 |
| M05c, entries carrying a reference or retirement condition | 420 of 3,357 (12.5%), on the entry itself | 22 of 30 and 16 of 30 sampled, with the ledger header counted |

The synthesis takes M05c reading 1, which is below 40%, and reports supported. My prior note did the same. I changed after opening the sample file:

- 1,929 of the 3,357 entries are bare paths in the formatter exclude list. Its header carries the retirement condition. All 18 sampled entries from it are scored "entry: no; ledger: yes".
- The `charter.activation` boundary baseline (231 pairs) is scored 0% at entry level (F-E1-020). Its leaf names an issue, an owner and a drain target (F-E1-022). It is one of the two best-attributed ledgers in core and counts as carrying nothing.
- So reading 1 measures where a reference is written, not whether the entry has one. The pre-registered wording "entries that carry a tracking reference or a retirement condition" does not choose between the readings.
- With reading 2 for both measures (88.9% and about 73%), the **contradiction** criterion is met. With reading 1 for M05c the support criterion is met. One measure, two defensible operationalisations, opposite criteria.

Section 5 of the pre-registration defines inconclusive as "neither is met, or the measures disagree". They disagree. E1 chose reading 1 without sight of the hypothesis, so nothing was adapted after the fact; the synthesis simply took the census as "the measure as taken" and filed the hand sample under evidence against. I report inconclusive. Decision A5 in `open-human-decisions.md` already puts the header question to the architect; it should say that the other answer reaches the contradiction criterion, not merely "not supported on that measure".

Not covered by either reading: the 18 marker scans. With them, flat or shrinking is 41 of 75 (reviewer-computed from `ledger-totals.json`; 3 not computed).

## 6. H06: supported (agree)

2 of 20 meet all three conditions; 6 of 20 relaxed (F-H06b-013; `checks.csv`). A bound that needs no judgement on authority or correctness: a contradicting source was found for 10 of 20, so at most 10 can pass, and 10 is the support threshold. The verdict does not rest on borderline rows.

Both declared gaps bias toward a higher count, as the synthesis says. One limit is understated: H06b never had the question texts, so "answered: 19" was not checked against the questions. H06a's own count of three questions with no single answering document is the better-informed one. The verdict holds under either.

## 7. H07: contradicted (agree; low robustness)

12 of 14 (85.7%) against 15 of 15; gap 14.3 points; within 20 (F-F-001, F-F-002).

What the assessment leaves out or understates:

- **The comparator was set by the coordinator.** `dispatch/F.txt` lists fifteen example coordination responsibilities; F's list is those fifteen. They are established, tested areas of core, so 15 of 15 was close to given. `execution-capability-matrix.md` says this; the assessment's breach table says only that the list could not be committed. This biases toward support, so the contradicted verdict stands a fortiori.
- **One row carries the margin.** X06 supervision is "verified" by a probe the workstream wrote; the provider has no test of that path (F-F-011). Without it: 11 of 14, 78.6%, gap 21.4 points, inconclusive.
- **Part-level reading (reviewer-computed from `execution-capability-matrix.csv`).** Of 22 parts, 2 are delegated; of the other 20, 15 are implemented, 1 is specified only, 4 are absent. 75.0%, gap 25 points, inconclusive. The synthesis gives three readings and decision A6 says the verdict holds "under any listed reading"; this fourth one is not listed.
- "Verified" was defined by F as "named tests pass" (deviation 3). Five verified rows are narrower than their name.

The pre-registered unit is the fifteen responsibilities, so I keep contradicted. It says that tested record-keeping and gating exist for execution about as often as for coordination. It does not answer the brief's own challenge ("existing contracts already support heterogeneous resource mobilisation and recovery"): the desk matrix of prospective operations has 9 of 25 cells verified and attach missing for all five targets (F-F-021, exploratory, absent from the finding map).

## 8. H08: I overturn inconclusive to contradicted

Support needs five invariants agreeing in both languages. At most I4 qualifies. Not supported; no dispute.

Contradiction needs four invariants where the contract-only check "cannot be written or gives a different result". For core Python:

| | G1 result | G2 result | Raw sets | Verdicts |
|---|---|---|---|---|
| I1 | pass at package level; 16 new at second level against a substituted baseline | 1 edge in no ledger; a `charter`/`glossary` cycle G1 did not see | differ | differ |
| I2 | violations, 593 | 0 new against recorded baselines | close: 135 against 131 underscore rows; 416 against 426 into `charter.activation`; 36 against 28 into `charter.offering` | differ |
| I3 | violations, 312 import names | 229 sites, all in ledgers | same two packages | differ |
| I4 | 9 in 5 modules; not judged for 923 of 1,294 modules | 8 in 4 files; 154 sites in `specify_cli` | agree where G1 judged | agree in part |
| I5 | cannot give pass or fail | 0 confirmed, 11 recorded | | cannot be written |
| I6 | fails without the pack tree | the same | | agree |

The synthesis counts I1, I2 and I5 and sets I3 aside because "both agents found the same imports ... and none elsewhere". That argument applies to I2 just as well: on I2 the two agents also found nearly the same import rows, and the verdicts differ for the same reason, namely that G1 could not read the baselines. A consistent reading gives either:

- result means the raw set: I1 and I5 only. Two. Inconclusive, and not at the edge.
- result means what the check reports: I1, I2, I3, I5. Four. Contradicted.

Three is reached only by treating I2 and I3 differently. A check's result is what it reports; the pre-registration says "gives a different result", and G1's I3 row reads "violations" where G2's reads no unrecorded violation. I take the second reading. Two more facts point the same way:

- `quality-attributes-invariants-scenarios.md` (section 2.1) and `knowledge-model.md` (section 4) both state that in core Python the two agents agree "only for I4 and I6", that is, 2 of 6. That is four differing invariants, written by another synthesiser.
- G1 had the agent-guidance file in its context and counted it as public information (G1 report). This is not in the coordinator's list of breaches. It gave the contract-only agent more than contracts, and it still differed on four.

Scope of the overturn: it is decided by core Python. In charter Java four invariants agree, one is partial and one was lost to the environment for G1. The criterion does not say "in both languages" for contradiction; the synthesis also counted core alone. H08 as tested says nothing about Wayfinder.

## 9. PX-01 (agree)

Stalls at `gathering` on a guard with no documented producer (F-E1-028 to F-E1-030). My `grep` finds `source_documented` and `publication_approved` under `src/` only in `runtime_bridge_composition.py`, `runtime_bridge_io.py` and `runtime_bridge_cores.py`, all readers or the guard. Two guard failures arrived together (no producer; a path mismatch for `source-register.csv`), and no workaround was allowed, so the run cannot say which alone would stall. The outcome class is correct for the first; the second is a separate "stalls for another reason".

## 10. Acceptance scenarios

I agree with 11 of 12 classifications.

- **AS-05, "demonstrated for released artefacts": I classify it partly.** M04a asks to install alone and run the artefact's own packaged checks. 4 of 4 install alone, but only the events package ships and passed a packaged check (1,200 tests); the tracker and the CLI ship none and were smoke-tested (F-D1-008). The scenario's words are "provides declared capabilities".
- AS-03: the latest mission type predates the present layout (F-D1-025), so the historical trace says nothing about today. "Partly" is acceptable; "not assessable under the present layout" is closer.
- AS-06 and AS-12 rest on a detection figure that is a lower bound (66 of 310 gate files). Stated.
- AS-10 is labelled desk only everywhere I looked.

## 11. Alternative explanations

For each supported or contradicted verdict, the best competing reading of the same numbers.

| Verdict | Competing explanation | Evidence that would separate them |
|---|---|---|
| H03 supported | A granularity artefact. Core's records say the enforced pair is the authority and prose maps are derived, so the documented tier stops at package level by decision. A low M03b then shows where the records choose to be silent, not that concepts outrun implementation. 0 strict must-not edges are observed (F-B3-003) | A record stating whether the inside of `specify_cli` is meant to have a model. M03b recomputed against the four bounded modules A1 found (F-A1-030), once they are mapped to subpackages |
| H06 supported | Selection and corpus size. The coordinator wrote the questions after reading core's guidance file, which lists contested subjects. And the "no contradicting source" condition fails on any stale page among 2,051 files, so the score falls with corpus size | A question set drawn by someone who has not read that file. The contradiction search restricted to the authoritative tier. A second checker for the 20 rows |
| H07 contradicted | A ceiling. The comparator is a list of tested features chosen by the coordinator, and "verified" means a test passes for a narrowed reading of the row | Part-level scoring (75%, section 7). A comparator drawn independently. One executed stop-on-request and one attach scenario |
| H08 contradicted (mine) | Not technology, but where core keeps its exceptions. The checks differ because ledgers and baselines sit in test files. One G1 rule was coded the wrong way round (36 hits, `S-C-differences.md` 2.2). Java agrees perhaps because it has few exceptions | G1 re-run with the ledgers published as data. A second Java subject (events, once it builds) |
| H05 supported (synthesiser's) | A recording artefact: references live in ledger headers; one lint list holds 57% of all entries | The census repeated with header inheritance |

## 12. Prior verdict note, as written before reading the assessment

```
H01 inconclusive. M01a +14.2/+15.1%; M01b load share down; M01d down.
H02 inconclusive. gate-before-main 1/30, 2/30; after-acceptance <= 4/30; untraceable 2/30, 10/30.
H03 supported by letter at the prereg unit: M03b 24.7%. B3 breach touches the measure.
H04 inconclusive/partial unless approved-plan claims count; then supported.
H05 supported by letter via M05c 12.5%; M05b 24/27 the other way; headers would flip M05c.
H06 supported: 2/20; contradiction found for 10, so at most 10.
H07 contradicted by letter: 14.3 points; one item flips it to 21.4.
H08 inconclusive: I1, I2, I5 clear (3); I3 arguable; I6 charter n/a.
PX-01 stalls at a guard with no documented producer, plus a second guard failure.
```

## 13. Limits

One reviewer, one pass, no measurement re-run. H04 cells and H07 states are judgements; I compared them and did not re-derive them from code. The reviewer-computed figures (sections 1, 5, 7) were not checked by a second person.
