---
doc_status: draft
updated: '2026-11-28'
---

# Synthesis challenge

Reviewer V, profile `paula-patterns`. This file covers the eleven synthesis documents other than the hypothesis assessment, which is in `verdict-challenge.md`. Every item below has a row in `challenge-items.csv` with its finding ids.

## Method and grades

- For each document I picked the five statements that carry most weight and traced each to finding ids and, where a figure decides something, to the raw artefact. "Traced" means the figure in the document equals the figure in the finding or artefact. It does not mean I reproduced the finding.
- I searched `synthesis/input/observations-index.csv` and `findings/` for counter-examples and for records no final document cites.
- **major**: changes a conclusion of the document or of a verdict. **minor**: an error or overstatement that leaves the conclusion standing. **note**: a limit the reader should know.
- Reviewer-computed figures are my arithmetic over a committed artefact. They are exploratory.

## Counts

55 statements traced over 11 documents: 38 trace cleanly, 11 trace with a qualification, 6 do not hold as written.

Items filed in `challenge-items.csv`: 52 (8 major, 21 minor, 23 note). Of the 52, 13 concern `hypothesis-assessment.md` and its finding map and are argued in `verdict-challenge.md`; the other 39 are below.

Finding ids cited in the final documents: 365 of 414 exist and resolve; 0 cited ids are unknown. 49 finding records are cited by no final document.

What I looked for and did not find:

- A blocked build treated as a defect: 0 cases. The events Gradle block is labelled a coverage limit in every document that mentions it.
- A desk assessment presented as verification: 0 cases. AS-10 and the prospective operations matrix are labelled wherever they appear.
- A threshold changed after measurement: 0 cases. Phase-1 and final verdicts are the same in all eight hypotheses.

## Cross-document inconsistencies

These matter more than any single document, because the report will be written from all of them.

| # | Subject | One document | Another | Grade | Filed as |
|---|---|---|---|---|---|
| X1 | H08, core Python agreement | `hypothesis-assessment.md`: three invariants differ, I3 arguable; verdict inconclusive | `quality-attributes-invariants-scenarios.md` 2.1 and `knowledge-model.md` 4: the two agents agree "only for I4 and I6", 2 of 6 | major | H-09, Q-01, O-01 |
| X2 | H04, claimed cells | `hypothesis-assessment.md`: 34 claimed; 9 / 22 / 1 / 2 | `independence-and-contracts.md`: 43 claimed; 10 / 29 / 2 / 2 | major | H-07 |
| X3 | H04, charter service logical claim | S-A: a present claim, the one capability counted | S-B: both "not established" cells are tied to a cutover that has not happened | major | H-07 |
| X4 | H04, work-package state machine | S-A: D1's "not established"; "no catalogue row claims it" | S-B: declared "claimed"; cell "partly (disputed)" | major | I-01 |
| X5 | Recorded contradictions | `deviation-catalogue.md`: "A1 reports 18" | `open-human-decisions.md` and A1's file: 25 rows | minor | D-01 |
| X6 | doc-toolkit consumers | `knowledge-model.md`: four sites pin four versions | `independence-and-contracts.md`: three other sites, three versions; core pins a git commit | minor | X-06 |

X1 to X4 are the grounds for the two overturned verdicts and for the H04 remark in `verdict-challenge.md`.

## 1. `coupling-and-deterioration.md`

| Statement | Trace | Result |
|---|---|---|
| Import density rose in every period: +23.6%, +14% to +15%, +21.7%; the window is not the steepest | F-B1-001; `series.csv` | figures hold; conclusion qualified, see below |
| Load-time cycles did not grow; none spans two components at head | F-B1-004 | holds |
| Per-commit scatter fell after June and cannot be separated from commit practice | F-C-008, F-C-030, F-C2-011, F-CX-004 | holds; replicated |
| The convergence removed about 10% of lines and edges; density did not step | F-B1-002, F-C-012 | holds against the public parent only |
| No causal sub-measure can attribute the density rise to a class of work | F-CX-006, F-C-015 | holds |

- **Major (C-01).** "What it does not show" omits the confound that M01a moves when packages are split. From the same `series.csv` (reviewer-computed): the component count went 31 to 71 before the window, 71 to 79 or 77 inside it, 77 to 74 after the convergence. All module edges per 1,000 lines moved +7.4%, +2.9% or +4.8%, and +14.2%. Summary point 1 gives the three M01a rises as comparable and concludes the window is not distinguished. On the granularity-free series the order changes: the period after the convergence carries the rise, the window is nearly flat, and the period before is mostly new component boundaries. The data are in the packet; the document does not use them.
- **Minor (C-02).** "Consistent with: import density grows with size and with every class of work." Class is exactly what M01f could not resolve (cells too small, T2 not replicated). "Every class" has no trace.
- **Note (C-03).** "The convergence removed code and edges" compares with the public parent. The merge tree equals its EXPERIMENTAL parent, so against that line nothing was removed. Both sentences are in the section; the summary keeps only the first.
- **Note (C-04).** Left out: the purposive change chains (F-C-025 to F-C-027, F-C2-025), which the brief asked for, and F-G2-013 (`specify_cli.cli` sits in an 85-package cycle; 15 other subpackages import it at 65 sites).

## 2. `deviation-catalogue.md`

| Statement | Trace | Result |
|---|---|---|
| A1.1: 228 upward imports under two ledgers of 22 and 10 entries | F-B1-011, F-E1-018 | holds |
| A1.2: 80 of 101 consumer files import behind `charter.activation.api`; baseline of 231 pairs matches | F-D1-015, F-G2-003 | holds |
| A3.1, A3.2: research guard path mismatch; no writer of the awaited event | F-E1-029, F-E1-030; my `grep` | holds |
| A3.9: events documents say a timestamp never orders; the reducer orders by timestamp | F-H06b-002, F-A1-014 | holds |
| "A1 reports 18 recorded contradictions" | `recorded-contradictions.csv`, 25 rows | does not hold (18 is the number of finding records) |

- **Minor (D-01).** The count above.
- **Note (D-02).** A3.12 lists one purposive Mission with materialisation drift among deviations with no recorded exception. The row says it is one case outside the seeded sample, where 12 of 12 agreed. It belongs in a list of open observations more than in a catalogue of departures.
- **Note (D-03).** A3.11 sets a recorded rule (decision records are immutable) against a count from a heuristic regex (A1 deviation 5). Both sides are documents about documents; part A's own rule asks for an observation of code, build or history.
- The separation of approved plans (part C) and proposals (part D) from deviations follows ruling R4. I found no approved plan filed as a deviation.

## 3. `assurance-gaps.md`

| Statement | Trace | Result |
|---|---|---|
| 16 of 24 detected, 15 by a per-change gate, 7 undetected, 1 not assessable | `detection.csv`, `detection-counts.txt` | holds |
| 0 of 6 incompatible-contract mutations caught by a compatibility or version check | F-E3-015 | holds; exploratory, labelled |
| 0 of 13 acceptance checks look beyond the Mission's repository | F-E1-032 | holds; static |
| "Detection after the fact by people dominates" | F-C-019, F-C2-018, F-CX-008 | qualified |
| "For core against the charter service no check exists", listed as a gap | F-E1-008 | holds as a fact; framing qualified |

- **Minor (A-01).** "After the fact": of C's 22 detections by a person, 5 were inside the same pull request, before `main`. The detection route does not replicate between C and C2 (22 against 16). The sentence should say "by people", and keep "after reaching `main`" for the 15.
- **Minor (A-02).** The summary table lists the missing core-to-charter-service check as an observed gap without the sentence that section 4.4 of `dependency-models.md` carries: it matches a pending approved plan. Under ruling R4 a plan not yet carried out is not a deficiency.
- **Note (A-03).** 8 of the 11 core detections have no single-mutation run; they were attributed by the file a failure names in a batch of 13. Disclosed, but the per-class table does not mark which cells rest on batch attribution.
- **Note (A-04).** The mirror tests behind two IC detections were chosen by the gate runner after reading the mutation list; the selection was not blind to the target file.
- **Note (A-05).** Left out: F-E1-011, an events workflow that runs a script from another repository's default branch without a pin.

## 4. `component-catalogue.md`

Five statements traced (three decompositions, F-A1-030; 51 of 74 components with no documented counterpart, F-B3-007; size concentration, F-B1-013 and F-B2-001; four pack readers, F-D2-016; staged components are not gaps, F-D2-020). All hold.

- **Minor (K-01).** Point 6 is labelled "(observed)": fleet-kitty "calls itself active and has its own dispatch, heartbeats and workers". F read it at README and search level only (F-F-019). That is a document-claim about itself, in the recorded-intent view.
- **Note (K-02).** Row "Mission type descriptors ... byte-identical" is marked "claim read; artefact not opened". Honest, and it means the row is unverified here.

## 5. `decision-timeline.md`

Population table, the activation chain, the amendment counts and the approved-plans table trace to F-A1-026, F-A1-012, F-A1-013, F-A1-018 and F-A1-033. All are document-claims and the page says so.

- **Minor (T-01).** "Records per month, excluding v0.11: 21, 23, 5, 36, 14, 22, 27, 86, 91, 119, 77." The series sums to 521, which includes the 56 v0.11 records. Excluding them, September is 35, not 91 (reviewer-computed from `evidence/A1/decision-timeline.csv`; all 56 v0.11 records are dated by git first-add in September). October stays the densest month.
- **Note (T-02).** Status classes are heuristic and 432 of 521 records were not read in depth. The page says so; the "status at head" column should not be quoted as fact in the report.

## 6. `dependency-models.md`

Five statements traced (0 unrecorded violations, F-B1-010; 48 entries for 228 statements, F-B1-011; M03b at two granularities, F-B3-001 and F-B3-002; the door table, F-B3-011, F-B3-012, F-D1-015; the head, core-pin and released table, F-D1-003, F-D1-021, F-D1-023). All hold.

- **Note (M-01).** "No unrecorded violation" rests on a static check and on the gate's helper functions. The pytestarch assertions ran only for E3 and D1, and the page cites E3 as "claim read". The page is open about this.
- **Note (M-02).** The pin-distance table counts commits. The page says commits are not behaviour change. The summary of `assurance-gaps.md` reuses the distances as a gap without that sentence.
- I found no place where the intended and observed models are merged.

## 7. `independence-and-contracts.md`

| Statement | Trace | Result |
|---|---|---|
| 43 claimed cells: 10 established, 29 partly, 2 not established, 2 not assessable | recount of `independence-matrix.csv` | holds internally; differs from S-A (X2) |
| Work-package state machine, logical: "partly (disputed)" | D1: "not established" | the synthesiser's value replaces the investigator's |
| Charter activation, logical: "partly" | D1: established; D2: not established | a merge of two workstreams |
| doc-kitty, source: "established, static only" | D1: not assessable; F-B2-019, F-B2-021 | an upgrade from another workstream's static evidence |
| Version tolerance was exercised at one point only | F-D1-003, F-D1-013 | holds |

- **Major (I-01).** The work-package state machine cell. The page marks the cell as claimed, then sets aside D1's "not established" for its own "partly". With the page's own declared value and the investigator's observed value, this is a present claim not established, which is what H04's support criterion counts. The page keeps D1's value in the CSV and says a reviewer may prefer it. I do: D1 measured two code definitions in two repositories tied by a pin 4,369 commits old (F-D1-024, F-D1-012). Whether the cell is claimed at all is the open point (X4).
- **Minor (I-02).** Charter activation, logical, merges D1 and D2, who measured different subjects (the file in core; the served form). Averaging to "partly" hides that each is clear in its own scope. The cell is marked contested and does not count toward a verdict.
- **Minor (I-03).** doc-kitty: logical "established" rests on its own repository, its tags and an import census. That is close to judging independence from repository separation, which ruling R3 excludes. The packet also holds a counter-example on the logical dimension that the row does not weigh: doc-kitty's ADR calls the mission-status contract "core's" (F-A1-025), and its TypeScript reader is one of four pack readers (F-D2-016).
- **Note (I-04).** The cell rule ("established: the count shows no bypass, or an executed test passed") was written by the synthesiser after the matrices existed.

## 8. `execution-capability-matrix.md`

Five statements traced (three readings of the share; five rows narrower than their name; the provider passed 9 of 10 end-to-end tests with fake agents, F-F-018; 9 of 25 prospective cells verified, desk, F-F-021; the single case, F-F-022). All hold, and this page is more candid than the H07 section of the assessment: it states that the comparator set was in effect chosen by the coordinator.

- **Minor (E-01).** A fourth reading is missing. Over the page's own 22 parts, leaving out the 2 delegated ones, 15 of 20 are implemented (75.0%; reviewer-computed). Against 15 of 15 that is 25 points, in the inconclusive band. Decision A6 then says the verdict holds "under any listed reading", which is true only because this one is not listed.
- **Note (E-02).** "A parallel unit of work that is not a work package had no native identity" comes from the single case and from a run that deliberately bypassed the runtime (deviation D-1). The page says both.

## 9. `quality-attributes-invariants-scenarios.md`

Five statements traced (attribute table rows for modularity, exception governance and recoverability; the H08 table; candidates I7 to I13 labelled proposed). They hold.

- **Major (Q-01).** Section 2.1: "In core Python, only for I4 and I6." See X1. The page then reports H08 as inconclusive without noting that its own sentence meets the contradiction count.
- **Minor (Q-02).** "The attributes the brief puts first have the most recorded rules and gates." Marked inference; no count of rules or gates per attribute exists in the packet.
- **Note (Q-03).** The "knowledge integrity" row is grounded in 42 tag uses. Investigators share one finding template; the count shows a tagging habit as much as a property of the ecosystem.
- **Note (Q-04).** QS-D ("0 of 19 packs at head validate") is given as the observed state of a proposed scenario. open-packs records that it ended compatibility with the as-is CLI on purpose (F-A1-015). The row should carry that, or it reads as a failure.

## 10. `knowledge-model.md`

The page states at the top that everything in it is a proposal and desk assessment. I found no proposal presented as a finding. The challenges are to its reasoning.

- **Major (W-01).** "Copies drift in every case observed" (also decision F1). The packet holds counter-examples: the two `mission.yaml` copies are byte-identical (F-H06b-009); doc-kitty's vendored contract equals its pin in 7 of 7 files (F-B2-021); 5 OpenAPI building blocks are identical across two repositories (F-B2-030); the two mission-status projections agree byte for byte (F-D2-014). The narrower statement the evidence carries is: copies without a pin or a lock drift, copies with one lag. That changes the argument against shape C from "restating fails" to "restating without a pin fails".
- **Minor (W-02).** "Core's recorded rule is the reverse" of the brief's "never regenerate normative intent from implementation". The enforced pair is a package list and hand-written layer rules. It is intent written as tests; nothing is generated from the implementation. The rule says prose maps yield to it. I see no conflict between a recorded decision and the proposal here, and decision B5 is framed on one.
- **Minor (W-03).** "Checks inside one repository detect well: reverse dependency 5 of 6." This is the best of four classes. Private import is 3 of 6, ownership bypass 3 of 5 assessable, charter 2 of 4 (F-E3-002, F-E3-004, F-E3-006).
- **Note (W-04).** K5 rests on A2, whose outside-term mapping is declared low confidence after a briefing gap. The page says so.
- **Note (W-05).** "Every check in this investigation was a script over files" is offered as consistent with the brief's "no persistent service". It is one case, run outside the runtime.

## 11. `open-human-decisions.md`

- **Major (O-01).** A4 puts the H08 question as "do the same imports, a different pass or fail count (I3)". The same question applies to I2, where the synthesis already counted the difference. Put to the architect for I3 alone, the choice is narrower than the evidence (X1).
- **Minor (O-02).** A2: "One capability has a present claim not established." See X3 and X4; the count is 0, 1 or 2.
- **Minor (O-03).** A5: the alternative is given as "not supported on that measure". With headers counted and the pre-existing ledgers as the population, both limbs of the contradiction criterion are met.
- **Minor (O-04).** Section E: "`spec-kitty --version` and four other read commands write into the user's home directory." The finding says the directories were there after five commands had run; which one wrote was not isolated (F-B1-025, B1 report).
- **Note (O-05).** Section E lists observations "with no recorded exception found" and says whether an item is already known was not checked against the trackers. The report should repeat that sentence beside the list.

## Findings no final document cites

49 of 414. Most are per-question H06a records, volume denominators and terminology rows. Four bear on a conclusion: F-B3-008 (toward contradiction of H03), F-G2-013, F-E1-011, and the change chains F-C-025 to F-C-027 with F-C2-025.

## Limits

- I traced figures; I did not reproduce them.
- `component-catalogue.csv`, `decision-timeline.csv`, `dependency-edges.csv` and `contract-surfaces.csv` were checked for row counts and for unknown finding ids only, not row by row.
- The phase-1 and differences files were read for changes of reading; they were not themselves graded.
