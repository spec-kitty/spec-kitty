---
doc_status: draft
updated: '2026-11-28'
---

# Validity evaluation

Evaluator V, profile `researcher-robbie`, charter context for the action `review` loaded. The profile's success definition asks for recommendations; the envelope allows none on implementation, and the envelope wins. I authored nothing that is evaluated here.

This file judges whether the measures measured what the hypotheses say, whether the pre-registration was applied as written, and how far each verdict can be carried. It replaces no earlier verdict. The synthesis verdict, the review verdict and my evaluation are kept side by side in `verdict-ledger.csv` (23 rows: 8 hypotheses, 1 experiment, 12 scenarios, 2 controls).

## 1. Method and limits

- Read: files 00 to 05, the hypothesis assessment and its finding map, the three reproduction reports and result tables, both challenge files, the major rows of the two item tables, the deviation sections of ten workstream reports, `dispatch/F.txt`, and two raw artefacts (`evidence/B1/series.csv`, `evidence/C/m01c-m01d-components-per-commit.csv`).
- Nothing was re-run. "Evaluator-computed" figures are my arithmetic over a committed artefact; they are exploratory and decide nothing.
- Not read: the other evaluator's files, most finding records, and the synthesis documents other than the hypothesis assessment (I rely on the review's trace of them).
- One evaluator, one pass.

## 2. Reproduction rates and what they mean

Joined from the three result tables (162 findings: 67 decisive, 95 seeded).

| Set | n | Reproduced | With difference | Claim wider than evidence | Mislabelled | Not reproduced | Blocked |
|---|---|---|---|---|---|---|---|
| Decisive | 67 | 60 (89.6%) | 4 | 3 | 0 | 0 | 0 |
| Seeded | 95 | 81 (85.3%) | 11 | 2 | 1 | 0 | 0 |
| All | 162 | 141 (87.0%) | 15 | 5 | 1 | 0 | 0 |

- The sample follows section 11.3: every finding marked decisive, plus a seeded 20% of the rest with at least five per workstream.
- A command or an equivalent probe was re-executed for 101 of 162 (62.3%) and for 45 of 67 decisive findings (67.2%); the rest were recomputed from the raw artefact or re-derived from the repository.
- All 391 file-backed evidence hashes checked by the reviewers match (98, 148, 145).
- No number a verdict rests on failed to reproduce. The seven decisive findings that fall short do so in wording, denominators or side figures.

What the rate carries:

1. It supports the **numbers**, not the **judgements** behind the H04 cells, the H07 states, the M02 traces, the H06 authority column and the ledger hand samples. Those were re-tabulated, not re-made.
2. "Decisive" was assigned by the synthesiser. The map omits two findings that M03b is computed from (F-B1-006, F-A1-031), and most "strongest evidence against" findings were not sampled.
3. The weakest workstream is A2 (1 of 5 seeded reproduced). No hypothesis verdict rests on it.
4. The shortfalls are uneven across verdicts:

| Verdict | Decisive ids | Outcome | Effect |
|---|---|---|---|
| H01, H02, H03, H04, H06 | 5, 8, 3, 3, 1 | all reproduced | none on the counts; M01a and M01b re-derived by an independent extractor at 5 revisions |
| H05 | 2 | 1 reproduced, 1 with difference | the difference lies outside the scored figures |
| H07 | 2 | 1 reproduced, 1 wider than evidence | **touches the headline share** (section 3) |
| H08 | 20 | all reproduced | none; the dispute is about counting |
| PX-01 | 3 | all reproduced, replayed | strengthens it |
| AS-08, AS-09, AS-12 | 1, 1, 3 | wider; with difference; 1 of 3 wider | each needs a narrower basis |

## 3. Per hypothesis: construct, thresholds, frame

"As registered" means sections 2, 3 and 6 of the pre-registration.

### H01 (inconclusive; review agrees). Stands with reservations.

- **Construct.** Reasonable proxies for "orthogonality". M01a moves when a package is split: the component count went 71 to 79 or 77 inside the window (review item C-01). M01d depends on commit practice; squash-style commits are 21% to 44% of code commits by period.
- **Thresholds and points.** Applied as registered. Start at the 2026-06-30 month end, the nearest point on or before 2026-07-01; end at P3a and P3b. No value is read across the merge.
- **Robustness (evaluator-computed).** Support is unreachable under any reading: M01b load-time and M01d fall whichever end month is taken (June 52.7%; July 41.1%; August 47.5% public, 31.3% EXPERIMENTAL; September 35.1% and 34.4%). The verdict sits near **contradicted**: read from P2 (2026-07-08), the first point inside the window, M01a rises 9.8% to P3a and 10.6% to P3b, against a limit of 10%. Reviewer R2's own extractor gives +13.4% and +14.2% from the registered start.
- **Controls.** Before and after use pooled periods for M01d and points for M01a. The sibling series exists for M01d only.
- **Causal sub-measures.** M01g counts GitHub review objects only. M01f is unusable (section 5). None enters the verdict.

### H02 (inconclusive; review agrees). Stands with reservations, close to not assessable.

- **Construct, weak.** Three parts of the support criterion were not measured as the hypothesis needs:
  - 13 of 30 sampled "fixes" corrected something inside the same pull request and never reached `main`. The frame rule ("subject marks a fix") admits them, so the support share is capped at 17 of 30.
  - "Passed its Mission's acceptance" was read from `accepted_at` in `meta.json`, present on 430 of 858 Missions. A missing field is not a missing acceptance.
  - "Detected by a person" includes agent review squads.
- **Not-assessable rule.** C2 has 10 of 30 untraceable, exactly one third, plus 9 weak traces. R1 found that 16 of 24 introducing changes are blame candidates, not 9 as the finding says. One more untraceable row triggers the rule.
- The verdict is as much "not measured well" as "not shown".

### H03 (supported; review agrees, qualified). Stands with reservations.

- **Thresholds.** The component unit of section 3 was used as registered: M03b 24.7%.
- **Construct.** This is the main reservation. Section 3 says that where no intended model exists the result is "no intended model", not "aligned"; M03c is "reported, not scored". M03b nevertheless scores 464 or 465 of 656 edges as undocumented because the documented tier has no row inside `specify_cli`. The measure cannot tell silence from mismatch. Among the 192 edges that cross a top-level package, 84.4% are documented, which is the inconclusive band.
- **Unregistered unit.** "Recorded exceptions" is 48 entries, 144 edges, 228 statements or 330 names. Two of the four exceed the limit of 100.
- **Breach.** B3 saw the 14 top-level edges before fixing its rules. That touches the 78.6% variant, not the decisive figure.
- What stands: the records are silent about the inside of `specify_cli`. It does not follow that documented concepts and code disagree.

### H04 (inconclusive, partial; review: count is 0, 1 or 2). Verdict stands with reservations; the label "partial" does not.

- **Construct.** The matrix follows ruling R3. Its cells are single-judge readings, filed as interpretation records. The declared column is the synthesiser's mapping, and two synthesis documents map differently (34 against 43 claimed cells).
- **Criteria gap.** Section 6 defines "established" and "not established". 22 of the 34 counted cells are "partly established", which decides nothing under either criterion.
- **Tests not taken.** M04d collapsed (one published version per range), M04e was not attempted behind `charter.offering.api`, M04b for events was blocked. The contradiction criterion was unreachable; these are coverage limits.
- Three mapping choices made after the data give 0, 1 or 2 capabilities. Reviewer R2 found the D2 tally wider than its evidence (3 unqualified "established", not 7).

### H05 (supported; review overturns to inconclusive). Both stand with reservations; a ruling is needed.

- **Thresholds.** Applied as registered to the entry-level census: 12.5%, or 30.8% without two lint baselines. E1 chose that reading without sight of the hypothesis, and it is the most literal reading of "entries that carry".
- **The other reading.** With the ledger header counted, a hand sample gives 22 of 30 and 16 of 30. One reader, n = 30, no interval. With M05b at 88.9% the first sample reaches the contradiction criterion; the second (53%) is inconclusive.
- **On the overturn.** The review applies "the measures disagree" to two readings of one measure, which stretches section 5. The state is: supported under the reading taken, not robust to the alternative.
- **Construct.** 2,265 of 3,357 entries sit in two lint baselines, 1,929 in one formatter exclude list: format debt, not compatibility sediment, though section 6 admits it.
- **Deviation.** M05b is net change, not gross additions and removals (declared).

### H06 (supported; review agrees). Stands with reservations.

- **Thresholds.** Applied as registered to run 1: 2 of 20, or 6 with four borderline rows relaxed, against 10.
- **Robust bound.** A contradicting source was found for 10 of 20, so at most 10 can pass, whatever the authority judgement.
- **Selection and instrumentation.** Questions written after reading core's guidance file (declared). One checker, without the question texts (5 of 5 sampled subjects fit). H06a had guidance files in context. Both gaps push the count up, so the direction is safe.
- **Construct.** The third condition fails on any stale page, so the score falls with corpus size.

### H07 (contradicted; review agrees, low robustness). Stands by the letter, with reservations.

- **Thresholds.** The registered denominator is "responsibilities that recorded intent places inside the ecosystem". F's own table marks 11 rows that way: 11 of 11, or 10 of 11 with handover downgraded (R1). Both are within 20 points of 100%. The headline 12 of 14 uses another denominator, not declared as a deviation.
- **Sensitivity (evaluator-computed).** On the 14-row denominator, without handover and without the self-written supervision probe: 10 of 14, a gap of 28.6 points, inconclusive.
- **Construct.** This is the main reservation.
  - "Verified" means named tests pass.
  - The registered denominator leaves out exactly the three responsibilities that no record places anywhere (supervision, cancellation, human attachment). The measure cannot register an unowned responsibility, which is what the hypothesis is about.
  - The comparator is the example list in `dispatch/F.txt`, taken over unchanged: fifteen tested areas of core, close to a ceiling by construction.
- What stands: tested record-keeping and gating exist for execution about as often as for coordination. It does not follow that execution infrastructure is mature.

### H08 (inconclusive; review overturns to contradicted). The synthesis count does not stand; the review verdict stands with reservations.

- **Thresholds.** The synthesis counts I2 as different and sets I3 aside on a ground that holds for both. A consistent count is 2 (raw sets) or 4 (what each check reports). "Result" is not defined in section 6.
- **Instrumentation.** G1 had the agent-guidance file and two architecture documents, more than "public contracts, schemas and package metadata". It substituted a baseline for I1. One I2 rule was coded the wrong way round. G1's charter I6 was lost to the environment.
- **Scope and construct.** One Java repository; the review's verdict is decided by core Python alone. The disagreement comes from where core keeps its exception ledgers (in test files): a matter of publishing baselines, not of technology. M08 is not a test of Wayfinder.

### PX-01. Stands.

Replayed by reviewer R3 with the same stall; a reviewer probe separated the two guard failures. No producer was found in core or in seven other repositories. Holds for core head and the `research` mission type.

## 4. Sampling frames, seeds and sizes

As registered and confirmed by the reviewers wherever a draw could be tested: seed 20261128 (28 seeded records); M01e 50 commits, identical in both runs; M01g 40 per period; M02a and M02b 30 each, redrawn exactly from frames of 666 / 698 and 1,262 / 1,264; twenty questions in two runs; 15 and 15 responsibilities; six invariants on core Python and one Java repository; 24 mutations, six per class; points P0 to P7 with a monthly series on both lines; a review sample of 67 decisive and 95 seeded findings.

Departures: the checker lacked the question texts (H06); the comparator list's timestamp is self-recorded (H07); one Java cell was lost (H08); 23 of 24 mutations were assessable, against 66 of 310 gate files.

Not fixed in advance, and differing between workstreams: one generator across frames or a fresh one per frame (E1; C against C2 for M02b).

## 5. Blind replication, C against C2

C2 ran on another model (Opus against Fable) and another profile, as registered. CX compared 477 rows; 463 are tests.

- **Replicated: 342 of 463 (73.9%).** All-class volume (25 of 25), all-class M01c (18 of 18), all-class M01d at component level, the co-change top pairs, M01g (identical), the M02 frames and origin split, recurrence by component, the merge effect.
- **Not replicated: 121.** Sorted by source:

| Source | What did not replicate | Evidence |
|---|---|---|
| Definition | volume, M01c and M01d by class (rule order); top-level M01d in T2 (rename lineage against directory); fork-window segment (reachability against date); refix chains; events component set; Mission acceptance (not comparable) | F-CX-001 to F-CX-004, F-CX-009, F-CX-010, F-CX-013 |
| Data (sampling) | M01f: same frame, 40, 15 and 11 of 150 commits shared; one commit holds 65.8% of C's T2 lines, and one supplies 75 of 95 edges in a C2 cell | F-CX-006; R1 on F-C2-015 |
| Data and definition, not separated | M02 detection route, 22 against 16 of 30: samples share 4 commits, coding agrees on 5 of the 6 commits both traced, and the buckets differ | F-CX-008; R1 on F-CX-013 |
| Tooling | none above 10%: the two AST walkers agree on 61 of 66 shared commits; the percentile method and rename detection move results by less than 10% | CX exploratory |

- CX attributes "all other non-replicated rows" to definitions. R1 grades that wider than its evidence for M02 detection, and I concur. One "replicated" row is not a comparison (F-CX-011: both numbers are the same literal).
- The 10% rule was applied as a symmetric relative difference, which section 11.3 does not define.
- M01a and M01b were outside the replication; R2's independent extractor is a post-hoc substitute at five revisions.
- **Meaning.** The all-class history measures are robust to analyst and model. Every by-class figure depends on unregistered classification detail. M01f cannot rank classes.

## 6. Threats to validity

| Threat | Where | Effect |
|---|---|---|
| Prior exposure: the coordinator saw raw M01b counts before registering | H01 | low; M01b falls, against the direction such exposure would favour |
| Prior exposure: the window equals the dates the coordinator proposed from grounding | H01 | weakens the independence that section 2.2 intended; the window is provisional |
| Selection: questions written after reading core's guidance file; comparator list supplied in the brief | H06, H07 | toward support in both; H07 is contradicted regardless |
| Instrumentation: single judge | H04 cells, H07 states, M02 traces, H06 columns, M05c hand samples | unknown; no inter-rater figure except M01e (38 of 50) |
| Instrumentation: context leaks | G1, H06a | G1 toward agreement; H06a toward a higher count |
| Instrumentation: a mutation artefact | AS-06, AS-12 | 11 of 15 core patches add an uncalled function that an unrelated gate catches |

## 7. Generalisation limits

- **Revision.** H03, H04, H05, H06, H07, H08, PX-01 and all scenarios hold for the head revisions of 2026-11-28 only. The released distribution (3.2.7, 4.0.0rc8) was tested for installation and pack validation only.
- **Period.** H01 holds for 2026-07-01 to 2026-09-05. H02, M05b and the mutation results hold for 2026-09-07 to 2026-11-28. Nothing may be read across the merge `2554bd13ad`.
- **Sample.** M02 and the ledger hand samples (30 each), AS-09 (12 of 816 Missions), AS-03, AS-04 and AS-11 (one case each).
- **Environment.** Events Java is static only. Mutation detection is a lower bound. H08's Java side rests on one repository.
- **The operations log** is the coordinator's own account of one investigation that, under deviation D-1, ran outside the mission runtime. It is a single case: it may illustrate M07c, and it supports no rate and no statement about what the runtime cannot do.

## 8. The outside observer's predictions

`predictions-outside-observer.md` does not exist; `05-status.md` records the predictions as not yet returned. **The comparison is pending.**

It will need:

1. the file as received, with the time of receipt and the pre-registration commit it refers to (`ab118801fd`);
2. a verdict and four probabilities for each packet row, so that a score can be computed for H01 to H08 and PX-01;
3. a statement of which verdict it is scored against. Three exist for H05 and H08 (synthesis, review, this evaluation);
4. the measured values for the direction-and-size items of every packet row, including the replication list and the mutation counts per class;
5. confirmation from the architect that the observer saw no finding first. All findings, the synthesis and the review are on the pushed research branch `claude/spec-kitty-arch-reconnaissance-fdeicj`, so blindness now rests on that confirmation alone.

The packet describes "a one-to-two-month window"; the window given is two months and five days.

## 9. What remains unknown, ranked

1. **Whether execution infrastructure is mature.** H07's measure excludes the unowned responsibilities and uses a ceiling comparator. No stop-on-request or attach scenario was executed.
2. **Whether extraction achieved independence.** No stub behind `charter.offering.api`, no version range with two members, no events Java build, no second judge. H04 is undetermined, not "partly".
3. **Whether Mission acceptance lets cross-component regressions through.** M02 could not read acceptance reliably; the support share was capped by the frame.
4. **Whether the inside of `specify_cli` is meant to have a model.** H03's support depends on it. It is a question of recorded intent, for the architect.
5. **Whether exceptions are attributable.** One ruling (does a ledger header count for its entries) moves H05 across all three verdicts.
6. **Whether contract-only checks fail for lack of published baselines or for a deeper reason.** G1 was not rerun with the ledgers as data; a second Java subject is missing.
7. **What drives import density after the convergence.** M01f cannot attribute the rise.
8. **How the gates perform under per-change CI** with mutations that add no dead symbol.
9. **How a research Mission behaves past the first unmet guard.**
