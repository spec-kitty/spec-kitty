---
doc_status: draft
updated: '2026-11-28'
---

# Executive summary

**Bottom line.** This was a read-only study of five Spec Kitty repositories, commissioned to give evidence for the design of Wayfinder, a proposed repository of architectural knowledge and assurance. The story that started the design, that a period of local fixes wore down the separation between components, was not confirmed: the registered test came out inconclusive, and close to contradicted. Where a rule is written as an automated check, it holds. Where a rule lives only in a document, between two repositories, or in a check that runs without comparing anything, the study found departures that nothing reported. The architectural knowledge is mostly correct but scattered and unranked. Two of the eight verdicts were overturned in review and several rest on a choice only the architect can make. Nothing about Wayfinder itself was tested.

| Measure | Value | Source |
|---|---|---|
| Finding records, from 18 workstreams | 414 | `05-status.md` |
| Sampled findings reproduced by independent reviewers | 141 of 162 (87.0%); 0 not reproduced | `evaluation/validity-evaluation.md` |
| Hypotheses supported / contradicted / inconclusive | synthesis 3 / 1 / 4; adversarial review 2 / 2 / 4 | `evaluation/verdict-ledger.csv` |
| Unrecorded violations of the enforced layering in core | 0 of 8,332 module edges | F-B1-010 |
| Documentation questions answered from one authoritative, uncontradicted, correct source | 2 of 20; 0 answers incorrect | F-H06b-013 |
| Planted violations flagged by existing checks | 16 of 23 against the set that was run; 20 of 23 against per-change CI (reviewer's figure) | F-E3-006, `review/repro-R3.md` |
| Planted contract breaks caught by a compatibility or version check | 0 of 6 | F-E3-015 |
| Acceptance checks of a Mission that look beyond its own repository | 0 of 13 | F-E1-032 |

A Mission is Spec Kitty's unit of planned work, from specification to accepted result. "Core" is the main repository, `spec-kitty`.

**What happened.**

1. **The founding story was not confirmed.** In the window the architect gave (2026-07-01 to 2026-09-05), one of three structure measures rose by 14% to 15% and two fell. Support was out of reach under any reading. The measure that rose also rises when a package is split; a variant that ignores splits moved by under 5% in the window (reviewer-computed, exploratory). The window is not the steepest period on the registered measure (F-B1-001, F-B1-004, F-C-008; `review/verdict-challenge.md`).
2. **Rules written as checks hold.** Core's layering shows 0 unrecorded violations, with the known exceptions listed and mostly flat or shrinking. Reverse-dependency violations planted by a blind author were detected in 5 of 6 cases (F-B1-010, F-E1-018, F-E3-003).
3. **What no check looks at went unreported.** A research Mission could not pass its third of six steps with documented commands. Contract-compatibility checks in two repositories passed without a baseline to compare against. A command was removed from a versioned interface with the version unchanged (F-E1-028, F-E3-013, F-F-007).
4. **The knowledge is mostly right, and scattered.** No documentation answer was wrong against the code and 12 of 20 were fully correct. A contradicting document was found for 10 of 20. There are 521 decision records in six repositories and no ecosystem-wide rule for which one prevails (F-H06b-013, F-A1-026, F-A1-003).
5. **Several results are weaker than their label.** The review overturned two verdicts. The post-hoc evaluation found that one "contradicted" result does not show what its name suggests, and that two hypotheses were not measured well enough to decide.

**Still open.** The outside observer's predictions have not been returned, so the comparison of prediction and result is pending; see Open risks.

**What we need from the architect.**

- **Decide whether the inside of `specify_cli` is meant to have a recorded model.** It holds 77.6% of core's source lines. Both sides of the dialectical review name this ruling as the one that would move them, in opposite directions (F-B1-013; decision F3).
- **Rule on two readings that flip a verdict.** Whether a reference in an exception list's header counts for its entries moves H05 across all three verdicts. What "a different result" means decides H08 (decisions A5 and A4).
- **Decide the order of work and the smallest shape.** Both sides agree the brief's full scope is not warranted by the evidence. They disagree on whether rulings come before any design, and on where an index would live (decisions F1, F2; disagreements D07, D09).
- **Decide which executed observations become tracker issues.** The study filed none, by mandate. Nine observations are listed for this decision; whether they were already known was not checked.

# Part A. What the evidence supports

This part holds empirical conclusions only. Each is in the observed view, at the head revisions of 2026-11-28, unless marked. "Head" means the latest revision on a repository's main branch that day. A "pin" is the fixed revision of another repository that core actually composes; "released" means a published artefact. The three can differ, and one check gave 5 of 5 at core's pin and 0 of 19 at head (F-D1-021).

<div style="page-break-before: always"></div>

## A.1 The verdicts, stage by stage

Three stages judged each item independently: the synthesis, the adversarial review, and a post-hoc evaluation of both. They are shown side by side. In the last column "stand" covers both earlier verdicts. Where the stages differ, all stand in the record and the architect decides.

| Item | Question | Synthesis | Review | Evaluation |
|---|---|---|---|---|
| H01 | Did local fixes erode component separation? | inconclusive | inconclusive | stand, with reservations; close to contradicted |
| H02 | Does Mission acceptance miss ecosystem regressions? | inconclusive | inconclusive | stand, with reservations; borders on not assessable |
| H03 | Do documented boundaries exceed implemented ones? | supported | supported, qualified | stand, with reservations |
| H04 | Has extraction fallen short of independence? | inconclusive (partial, one capability) | inconclusive; the count is 0, 1 or 2 | verdict stands; the label "partial" does not |
| H05 | Has compatibility sediment accumulated? | supported | **inconclusive (overturn)** | stand, with reservations; a ruling is needed |
| H06 | Is architectural knowledge fragmented? | supported | supported | stand, with reservations |
| H07 | Is execution infrastructure less mature? | contradicted | contradicted, low robustness | stands by the letter, with reservations |
| H08 | Are technology-neutral invariants viable? | inconclusive (edge of contradicted) | **contradicted (overturn)** | synthesis count does not stand; review stands, with reservations |
| PX-01 | Can a research Mission finish as documented? | stalls at a guard with no documented producer | the same | stands |

An invariant here is a rule that must always hold, such as "no new import cycles". A guard is a condition a Mission step waits for.

## A.2 What each verdict rests on

| Item | Decisive figures | What moves it |
|---|---|---|
| H01 | Cross-component import density +14.2% and +15.1% on the two lines; load-time cycles lower; share of commits touching two or more components down 17.6 and 18.3 points | Read from the first point inside the window the rise is 9.8% and 10.6%, against a limit of 10%. The reviewer's own extractor gives +13.4% and +14.2% |
| H02 | 1 or 2 of 30 sampled cross-component fixes stopped by a check before main; 4 of 30 reached main after a recorded acceptance, against 5 of 30 in the comparator | Acceptance is recorded on 430 of 858 Missions. 16 of 24 introducing changes are blame candidates (the review's count; the finding said 9) |
| H03 | 162 of 656 component edges match a documented relationship (24.7%) | 464 or 465 of the 656 lie inside one top-level package where no record speaks. Across top-level packages the share is 84.4% |
| H04 | 34 cells counted as claimed: 9 established, 22 partly, 1 not, 2 not assessable | A second synthesis document counts 43 cells differently. Cell values are single-judge readings |
| H05 | 420 of 3,357 exception entries carry a reference (12.5%) | With the list header counted, hand samples give 22 of 30 and 16 of 30. 24 of 27 lists that existed on 2026-09-07 are flat or shrinking |
| H06 | 2 of 20 meet all three conditions; 6 with borderline rows relaxed; threshold 10 | A contradicting source for 10 of 20 caps the count at 10 without any judgement |
| H07 | 12 of 14 execution responsibilities verified (85.7%) against 15 of 15 | On the registered denominator it is 11 of 11, or 10 of 11. With two weak rows removed it is 10 of 14, a gap of 28.6 points, which is inconclusive |
| H08 | In core Python the two kinds of check agree for 2 of 6 invariants; in the charter repository's Java for 4 of 5 assessable | A consistent count of differing invariants is 2 or 4, never the synthesis's 3 |

The window comparison says nothing about the convergence merge of 2026-09-05, which joined two parallel lines of development. No trend is drawn across it, by rule. It is reported apart: the merged tree had 60 fewer modules and 44,144 fewer source lines than the public line's last commit, and density did not step (F-B1-002, F-C-012).

Evidence of deterioration is also kept apart from evidence of cause. The one measure meant to attribute density to a class of work did not replicate and cannot rank classes (F-CX-006). One causal reading is contradicted by both runs: corrective commits touch fewer components than capability-growth commits in every period (F-C-006, F-C2-008).

## A.3 Disconfirmations

Three results went against the commission's working assumptions. They are results, not gaps.

- **H01.** The evidence does not show that fixes in the window eroded the separation of components. Two of three measures fell.
- **H07.** By the registered test, execution is not less verified than coordination. The evaluation adds that this shows tested record-keeping and gating exist. It does not show that execution infrastructure is mature, because the measure leaves out the three responsibilities that no record places anywhere (F-F-001, F-F-012, F-F-024).
- **H08.** On the review's reading, a check written from public contracts alone gives a different answer from one written with the implementation, for four of six invariants in core Python. This bears on a premise of the design, and it is not a test of Wayfinder.

Further evidence against a reading of weak assurance: exception caps were lowered by 164 and raised by 44 over the period (F-E1-019); the largest recorded boundary exception, 231 file-and-module pairs, matches the observed pairs exactly (F-G2-003); the charter repository's Java shows 0 violations in 136 executed architecture tests (F-B2-005).

## A.4 Departures that no check reported

Each item below was executed, statically confirmed or read from history. "R" marks a finding a reviewer reproduced; the others were not in the review sample. None was checked against the issue trackers, so "unreported by a check" does not mean "unknown to the maintainers".

| Observation | Evidence | Limit |
|---|---|---|
| A research Mission stalls at step 3 of 6. The guard waits for an event that nothing in core writes; tests write it by hand. Guard and prompt name different file paths | F-E1-028 to F-E1-030 (R; replayed by a reviewer) | One mission type; no producer found in core or seven other repositories; later steps not reached |
| Contract-compatibility checks in two repositories passed with no baseline to compare against | F-E3-013 (R), F-E3-015 | Exploratory, executed |
| The verb `merge-mission` was removed from the orchestrator interface with the contract version unchanged at 1.6.0; two consumers still name it | F-F-007, F-F-008 (R) | Consumers are in other repositories |
| A required cross-repository check in the events repository runs against a pin of 2026-05-21 and is skipped on fork pull requests, which reads as success | F-E1-010 | The events guide records the fork case and a maintainer step for it |
| The events packaged conformance suite is invoked by no workflow, although a guide names it as a gate | F-E1-012 (R) | The guide is a secondary source |
| Mission acceptance runs 13 checks; none reads another repository, a pin, a contract or a gate result | F-E1-032 (R) | A statement of scope; no record places ecosystem checks there |
| No ruleset requires an approving review; each lists a bypass actor | F-E1-004 (R) | Organisation-level rulesets not read |

The synthesis catalogued 14 departures with no recorded exception found, 8 covered by a recorded exception, and 8 contradictions between records where code was checked (`synthesis/deviation-catalogue.md`). The catalogue covers only what the workstreams looked at: 77 of 89 rules in one workstream's frames were not traced.

## A.5 Controls

**Planted violations.** One agent wrote 24 patches from the intended model without seeing any check. Another applied them. Against the 66 of 310 gate files that were run, 16 of 23 assessable patches were detected: private import 3 of 6, reverse dependency 5 of 6, ownership bypass 3 of 5, incompatible contract 5 of 6. The reviewer showed that per-change CI runs the whole set, and against it 20 of 23 are flagged, 16 by a failure that names the violation. Four of the extra detections come from a check that reacts to how the patch was written, so they do not show the rule is guarded (`review/repro-R3.md`).

**Blind replication.** The history measures were computed twice, by different models under different profiles. 342 of 463 comparable rows agree within 10% (73.9%). All-class history measures replicate. Every by-class figure, the causal sub-measure and the detection route do not.

# Part B. Interpretations

These are readings of the evidence. Each names who made it. None is a measurement.

**H03 shows silence, not breach.** Synthesis, review, evaluation and both dialectic parties agree. The low figure comes from the absence of a recorded model inside `specify_cli`. No documented prohibition was found broken without a recorded exception (F-B3-003). Whether that silence is a choice is the architect's ruling.

**The knowledge exists and is mostly right.** The third synthesiser reads the observations this way: knowledge is spread over many records, not current everywhere, and not ranked across repositories. Review and evaluation add two cautions. The questions were written after the coordinator had read core's agent-guidance file, which lists contested subjects. And the "no contradicting source" condition fails on any stale page, so the score falls with the size of the corpus, about 2,051 files.

**H08 turns on where core keeps its exceptions, not on technology.** The contract-only check could not read core's exception lists and baselines, which sit in test files. In Java, where the model is published, the checks agreed. Review and evaluation both give this reading. It was not tested by re-running the check with the lists supplied as data.

**The enforced model is the intent of record for structure.** Core's records say that the package list and the layer tests prevail over every prose map (recorded intent, F-A1-001). The review notes that this is intent written as tests, and sees no conflict with the brief's rule against regenerating intent from implementation. The synthesis framed it as a conflict. Both readings are in the record.

**Core holds what records, prepares and gates; acting on a running process sits outside core or nowhere.** This is one workstream's interpretation at medium confidence (F-F-027). Starting agents is delegated to an external orchestrator by recorded intent (F-F-005). Supervision, stopping on request and attaching a person have no holder in any repository read and no record that places them. Under the architect's ruling that is not a deficiency against intent; it is an unplaced responsibility.

**Half of the undetected planted violations sit on unclear rules.** The patch author judged the rule ambiguous or partly so for 4 of the 7 that the run set missed. For these, "undetected" may reflect an unstated rule as much as a missing check (synthesiser's inference).

**Copies with a pin lag; copies without one drift.** The synthesis first wrote that copies drift in every case observed. The review found counter-examples of identical copies and narrowed the statement. No census of copies was taken.

**Conflicts between a recorded decision and the brief are not violations.** Seven are listed for the architect (decisions B1 to B7), for example that nothing Python moves to the charter repository while the brief says "complete Charter extraction". Under the architect's ruling they inform a later decision.

# Part C. Prospective design recommendations

Everything in this part is in the proposed view. Nothing is approved and nothing authorises work. Wayfinder does not exist; no element below was tested, and the statement that Wayfinder's unavailability would not disrupt operations (AS-10) is a desk assessment with no empirical standing.

**Start from the needs the evidence shows.** The synthesis reads nine needs from the observations and finds several independent observations for four registers of references:

| Register | What it would hold | Need behind it |
|---|---|---|
| K1 Decision index | One row per decision record: identity, in-force status, supersession links, view | 521 records in six repositories; status field unreliable; 6 of 10 supersession chains cross repositories |
| K2 Component register | One identity per component, with its names in each repository | Three recorded decompositions of core; 50 of 72 documented relationships do not resolve to an observed component |
| K3 Contract and pin register | Each surface that crosses a boundary: owner, readers, pins | 33 pin and lock surfaces; one relation with no check; 10 formats defined on both sides of a boundary |
| K4 Invariant and exception register | Each rule, its published model, its exception list, the check that runs it | 6 of 12 sampled rules end at an instruction with no check; owner on 2 of 30 sampled exception entries |

A term map (K5) rests on one workstream at low confidence. Scenario bindings and evidence records (K6, K7) come from the brief more than from the evidence.

**Hold references, not copies.** The evidence argues against any element that restates what a repository owns without a pin. It does not argue against a register of references.

**Other design readings from the synthesis.**

- Keep four views, not the brief's three: recorded intent, observed, approved plan, proposal. The study needed the fourth to read H04.
- Bind evidence to the subject's commit plus the pin set it composed for structure, and to released artefacts for independence claims. The two gave different answers. This is a reading, not a ruling.
- Let local checks stay local. An ecosystem check would read their declared inputs and results; the evidence does not say it must run them again. A build-based check took 45 minutes and was lost to the environment three times (F-G2-012).
- For exceptions, the observed gap is owner and approval, not rationale: rationale on 30 of 30 sampled entries, owner on 2, approval on 1 (F-E1-025). The brief's five fields exceed every recorded rule.
- A register reveals; it does not stop. If Wayfinder has no acceptance authority and acceptance stays local, the evidence does not show where an ecosystem violation would stop a change (decision F4).

**Four shapes; the evidence does not choose.**

| Shape | What it is | For | Against |
|---|---|---|---|
| A | Registers generated into an existing place | No new repository to pin | Ties architecture knowledge to a documentation tool with no enforced model of its own |
| B | A thin register repository of references with checks | Owns no content, so nothing in it can drift from an owner | Still a new repository; useless unless owners publish models and exception lists readably |
| C | The brief's full scope, with prose views | One place to read the intended system | Needs a precedence ruling first; both dialectic parties say the evidence does not warrant it |
| D | Each repository publishes locally; no index | Removes the cause named for the H08 disagreement | Nobody holds the cross-repository view |

**What the evidence is silent on.** The cost of keeping any register true is unknown; the study built four tables once, by hand and script. Performance, fault injection, the runner assignment contract and the right number of scenarios were not measured.

# Part D. Where the dialectical review left disagreement

Two agents argued opposite positions from the same record: A for a knowledge and assurance repository, B for the sufficiency of existing governance. A recorder kept the result without weighing it. Of 23 points, 8 ended conceded (5 by A, 3 by B), 9 narrowed with a residue, and 6 stayed open (`dialectic/disagreements.csv`).

**Agreed without pressure**, stated independently by both before either saw the other: H01 does not support the founding story; H02, H04 and H07 carry no weight for the design; the enforced tier holds; H03 shows silence; H06 is robust; PX-01 is a real defect no check reported; contract compatibility is effectively unchecked in two repositories; the brief's full scope is not warranted; nothing about Wayfinder was tested.

**Still disagreed**, in the parties' terms:

| Point | A | B | What would settle it |
|---|---|---|---|
| Are the unreported departures a class or a list? (D01) | A class, shown by 14 uncovered entries from a partial trace; the residue lies between repositories | Without a rate, class and list cannot be told apart; the items are checks present but not wired, plus PX-01 | A tracker check of the 14 entries; tracing the 77 untraced rules |
| Did density rise after the convergence where no model exists? (D02) | Yes: the one measure that moved, moved where assurance has no model | Not located: the series has no split by top-level package; placing it in `specify_cli` is conjecture | The density series split by top-level package |
| Is H06 a practical cost? (D03) | A cost, because agents act on these documents; that harm has occurred is conjecture | Limited weight: 0 of 20 answers incorrect; question selection is a limit | A second question set by an author who has not read the guidance file |
| Were the uncovered entries already known? (D04) | Not shown either way | "No exception found" is an upper bound on "unknown" | A tracker check |
| Do the checks guard the rules or react to patch shape? (D05) | 16 of 23 by a failure naming the violation | 20 of 23 flagged; accepts the caution on four | A re-run with patches that add no uncalled function |
| Where does an index live? (D07) | Shape B resting on D; whether a new repository, the evidence does not say | D first; the need for K1 and K3 is observed, the location open | Regenerate the tables at a second date and count hand corrections; then decisions B5, C1, F1 |
| Does K4 belong centrally? (D08) | Yes, after decisions F2 and F3 | Not shown | The contract-only check re-run with exception lists as data |
| Order of work (D09) | Accepts that rulings precede design | Rulings first; they cost nothing and each moves a verdict | The architect's choice |
| Unplaced responsibilities (D10) | A matter for a knowledge repository before a runner | One decision record closes it | The architect's choice |
| "Nothing in the gate inventory is built to report these" (D11) | As stated | For five items the check exists and is not wired, fed or followed | None named |
| Can one repository hold a cross-repository view? (D12) | No | 15 such relations exist, each held through a pin; what is shown is lag | Trace duplicated formats and pin surfaces for a defect that reached a release |

The rebuttals were written in parallel. Three points (D02, D11, D12) were raised for the first time in B's rebuttal, so A had no chance to answer them. The record marks them; that is a property of the procedure, not a concession.

Neither party could say whether any departure has harmed a user of a released version, what a register costs to keep true, or whether a register would have caught PX-01.

# Part E. How far to trust this

## E.1 Reproduction

Three reviewers who authored nothing re-derived their own claim from the raw artefacts before reading each finding. The sample was every finding marked decisive plus a seeded 20% of the rest.

| Set | Sampled | Reproduced | With a difference | Claim wider than evidence | Mislabelled | Not reproduced |
|---|---|---|---|---|---|---|
| Decisive | 67 | 60 (89.6%) | 4 | 3 | 0 | 0 |
| Seeded | 95 | 81 (85.3%) | 11 | 2 | 1 | 0 |
| All | 162 | 141 (87.0%) | 15 | 5 | 1 | 0 |

A command was re-executed for 101 of the 162; the rest were recomputed from raw artefacts. All 391 evidence hashes checked match. No number a verdict rests on failed to reproduce. The rate supports the numbers. It does not support the judgements behind the H04 cells, the H07 states, the H02 traces or the H06 authority column, which were re-tabulated, not re-made. The weakest workstream was the term mapping (1 of 5 seeded reproduced); no verdict rests on it.

The review also traced 55 statements across the synthesis documents: 38 trace cleanly, 11 with a qualification, 6 do not hold as written. It filed 52 challenge items (8 major) and 57 wording items (5 major). This report uses the readings the review allows.

## E.2 What was not measured

- **Events Java.** Its build never succeeded here because dependency retrieval was rate-limited. Everything that needed it is not assessable. This is a coverage limit.
- **Independence tests.** No stand-in was tried behind the charter seam. Each Python version range admitted one published version, so the lockstep test collapsed. The contradiction criterion for H04 was unreachable.
- **Gate coverage.** 244 of 310 architectural gate files were not run against the planted violations, so detection in core is a lower bound.
- **Execution.** No stop-on-request or attach scenario was executed.
- **Acceptance.** It was read from a field present on half the Missions, and 13 of 30 sampled fixes never reached main, which caps the H02 support share at 17 of 30.
- **Scope.** One cited repository, `spec-kitty-go`, was not attached. History before 2026-01 is baseline only.
- **Time.** All but H01 and H02 hold for one day's head revisions. H01 holds for the window only; H02 for 2026-09-07 to 2026-11-28.
- **Samples.** 30 for each fix sample and each exception hand sample; 12 of 816 Missions for the rebuild test; one historical case each for three scenarios.

## E.3 The process, including what the coordinator did wrong

A separate evaluator graded the controls. Counted from its tables: of 21 pre-registered controls, 11 held, 8 held in part, 1 did not hold and 1 was not checked; of the architect's 12 rulings, 5 held and 7 held in part. It lists 20 deviations. None invalidates a result.

The coordinator's failures, as the evaluation records them:

- **Steering in four briefs.** The experiment brief presumed a stall. One brief told the answering agent that differing sources "matter". One listed exactly fifteen example responsibilities, which the workstream adopted as its comparator. One suggested "a few dozen" gate files, and 66 of 310 were run.
- **Briefing gaps.** The checker of the twenty questions did not get the question texts. The term-mapping workstream got no definitions.
- **Blind arms were not blind.** The session placed agent-guidance files in every executor's context. This reached the documentation-only answerer, the contract-only checker and the blind patch author. The coordinator's notes list it for one of the three.
- **Record keeping.** The pre-registration's commit appears in 0 of 414 findings, though promised in each. Per-agent instructions and resume messages are not in the dispatch folder. Phase-one and final synthesis files were committed together, so their order rests on the synthesisers' word. Reviewers were told which findings were decisive. Two synthesisers presented different independence matrices, unreconciled. The status file was left stale and counts four breaching workstreams where five are listed.
- **Environment.** Grounding ran a test session in the production checkout before approval. No tracked file changed.
- **Prior exposure.** The window the architect gave equals the dates the coordinator had proposed after seeing raw cycle counts. The architect had seen no series. The measure concerned fell, against the direction such exposure would favour.

Five workstreams declared their own breaches; the evaluation found no verdict changed by them. Seven were interrupted by a usage limit and resumed; the resume messages are not recorded.

## E.4 The outside observer

The prediction packet contains definitions and criteria, no outcomes. The status file records that the predictions have not been returned and that no finding was disclosed to the observer. The comparison is pending. The evaluation notes that all findings sit on a pushed research branch, so blindness now rests on the architect's confirmation that the observer saw none first.

# Part F. Outstanding human decisions

All are the architect's. Options carry no preference. The full list, with evidence and unknowns, is `synthesis/open-human-decisions.md`. The first table holds rulings that would settle a verdict and conflicts between recorded intent and the brief. The second holds decisions on the records, the coverage of this study, and the shape of Wayfinder.

| Group | Decision | Why it matters |
|---|---|---|
| Verdicts | A1: confirm or change the H01 window | The window is provisional; a final H01 verdict waits on it |
| Verdicts | A2: does an approved plan not yet carried out count as a claim? | H04 becomes supported if it does. The review adds that two further mapping choices give 0, 1 or 2 capabilities |
| Verdicts | A4: does "same imports, different pass or fail" count as a different result? | Decides H08. The review says the question applies to two invariants, not one: the consistent options are 2 (inconclusive) or 4 (contradicted) |
| Verdicts | A5: does a reference in an exception list's header count for its entries? | H05 is supported, inconclusive or contradicted depending on the answer |
| Verdicts | A6: are responsibilities no record places "inside the ecosystem"? | Changes what H07's result means, not the verdict |
| Intent against proposal | B1 to B4: charter extraction, activation authority, events ownership, event ordering | Recorded decisions and the brief differ; three records disagree on who is authoritative for activation |
| Intent against proposal | B5: which source is normative for structure | Gates shape C and registers K2 and K4 |
| Intent against proposal | B6: where supervision, cancellation and attachment are placed | Unplaced today |
| Intent against proposal | B7: one exception field set, or one per repository | Three recorded rules differ |

| Group | Decision | Why it matters |
|---|---|---|
| Records | C1 to C8: eight contradictions between records | For one (is the merge path enforced) observation shows the charter text is the stale side; for the others it does not |
| Coverage | D1 to D4: attach `spec-kitty-go`; rebuild events Java elsewhere; commission the stand-in test; re-run undetected patches on the full gate set | Each closes a named coverage limit |
| Housekeeping | D5, D6: the carrier Mission will not reach done; whether these reports reach main | Follow from the authorised deviations |
| Issues | E: which of nine executed observations become tracker issues | The charter asks for an issue per pre-existing failure; the mandate here was non-remedial |
| Shape | F1 to F7: where knowledge lives; whether core publishes its model and exceptions outside test files; whether `specify_cli` gets a model; who can stop a change; views; first invariant set; revision binding | F2 gates shapes B and D; F3 decides what H03 means |

# Open risks

No issue was filed for any row, under authorised deviation D-3, and none was checked against the trackers.

| Risk | Why it matters | Issue | Owner |
|---|---|---|---|
| A user who starts a research Mission cannot finish it with documented commands | The product stalls at step 3 of 6 while its tests pass | none filed | architect decides (section E) |
| A breaking contract change can pass a check named for compatibility | Consumers in other repositories learn of a break only when they fail; one removal has already passed unseen | none filed | architect decides (section E) |
| The comparison with the outside observer's predictions loses its value | Findings are on a pushed branch; this report also discloses them | not applicable | architect |
| Two verdicts are carried forward without a ruling | H05 and H08 each have two defensible readings with opposite outcomes | not applicable | architect (A4, A5) |
| A design is built on H03 or H06 as if they showed breach or harm | H03 shows silence; no H06 answer was wrong | not applicable | architect (F3) |
| A register becomes the next stale document | Upkeep cost was not measured; a prior 56-record target architecture binds nothing | not applicable | architect (F1) |
| Results are read as true of the events Java services | They were never built here; all statements about them are static | not applicable | architect (D2) |

# Appendix: method, sources and caveats

## Method

Read-only investigation of five repositories at their head revisions of 2026-11-28, the revisions core pins, and released artefacts. Measures, thresholds, samples and controls were fixed in a pre-registration approved by the architect before measurement. Eighteen workstreams ran as subagents; none received the hypotheses. Stages, each writing to its own folder: predictions (pending), investigation, synthesis (interpretations withheld until a first reading was drafted), adversarial review with reproduction, post-hoc evaluation, dialectical review, this report.

Three departures from the debrief procedure, with the architect's authority:

1. **Source of facts.** This debrief reports no GitHub activity, so the collector was not run. Its rule is kept in spirit: every number and statement traces to a file in the report folder. Issue and pull-request references are omitted.
2. **Vehicle.** The work ran as a research Mission with subagents, not as a dispatch Op (`00-rulings-and-deviations.md`, D-1).
3. **Placement.** The architect ruled that the investigation's documents are stored in the report folder on a research branch. The Markdown source of this report is in `report/`. The PDF is written outside the repository and handed over.

The PDF was rendered with the branded generator and each page was inspected. A designer review pass was not run.

## Where each deliverable lives

All paths are under `docs/reports/wayfinder-reconnaissance/2026-11-28/`.

| # | Deliverable | File, under synthesis/ |
|---|---|---|
| 1 | Component catalogue | `component-catalogue.md`, `.csv` |
| 2 | Decision timeline | `decision-timeline.md`, `.csv` |
| 3 | Dependency models | `dependency-models.md`, `dependency-edges.csv` |
| 4 | Deviations | `deviation-catalogue.md` |
| 5 | Independence and contracts | `independence-and-contracts.md`, `independence-matrix.csv` |
| 6 | Historical coupling | `coupling-and-deterioration.md` |
| 7 | Assurance coverage and gaps | `assurance-gaps.md` |
| 8 | Execution capability matrix | `execution-capability-matrix.md`, `.csv` |
| 9 | Attributes, invariants, scenarios | `quality-attributes-invariants-scenarios.md` |
| 10 | Knowledge model | `knowledge-model.md` |
| 11 | Hypothesis assessment | `hypothesis-assessment.md` |
| 12 | Open human decisions | `open-human-decisions.md` |

Deliverable 5 also has `contract-surfaces.csv`, and deliverable 11 `hypothesis-finding-map.csv`. Also in the folder: `01-pre-registration.md`; `findings/` and `evidence/` (414 records and raw artefacts); `workstream-reports/`; `review/`; `evaluation/` (with `verdict-ledger.csv`); `dialectic/`; `operations-log.txt`.

## Acceptance scenarios, side by side

The scenarios are proposals from the brief. Each was classified, not passed or failed.

| Scenario | Synthesis | Review | Evaluation | Main reservation |
|---|---|---|---|---|
| AS-01 Charter internals change without consumer change | not demonstrated | agree | stands | No stand-in was tried; rests on import counts |
| AS-02 External runner records and retrieves evidence without the CLI | partly | agree | stands | Reading executed; no write was sent |
| AS-03 New state-machine configuration needs no unrelated change | partly | agree; "not assessable under the present layout" is closer | stands, with reservations | Last mission type added before the present layout |
| AS-04 New tool adapter preserves mission semantics | partly | agree | stands, with reservations | One historical case; semantics not measured |
| AS-05 Standalone installation provides declared capabilities | demonstrated for released artefacts | **partly (changed)** | synthesis stands with reservations; review stands | Installation shown; a packaged check passed for one package only |
| AS-06 Unauthorised dependency is rejected | partly | agree | stands, with reservations | Detection measured against 66 of 310 gate files |

| Scenario | Synthesis | Review | Evaluation | Main reservation |
|---|---|---|---|---|
| AS-07 Temporary exception stays attributable and bounded | partly | agree | stands, with reservations | Same question as H05; owner on 2 of 30 |
| AS-08 Interrupted assignment stays identifiable and recoverable | partly | agree | stands, with reservations | One basis was wider than its evidence: a per-subtask status surface exists |
| AS-09 Lost projection is reconstructable | demonstrated for lane state | agree | stands, with reservations | 12 of 816 Missions; 4 of 12 rebuilt files change identity fields |
| AS-10 Wayfinder unavailability does not disrupt operations | not assessable (desk only) | agree | stands | No subject exists; never empirical |
| AS-11 Compatible release does not force lockstep upgrades | partly | agree | stands, with reservations | Version test collapsed; 0 of 19 packs at open-packs head validate, by that repository's recorded intent |
| AS-12 Mission acceptance does not conceal ecosystem violations | not demonstrated | agree | stands, with reservations | 0 of 13 holds for built-in checks; a Mission can add its own |

## Inspected revisions

| Repository | Head, 2026-11-28 |
|---|---|
| `spec-kitty` (core) | `5c4fc5a79d` |
| `spec-kitty-charter` | `06cdfbe948` |
| `spec-kitty-events` | `646e330b89` |
| `spec-kitty-open-packs` | `f9a557510d` |
| `doc-kitty` | `1acc49fbe2` |

Core pins: built-in pack at open-packs `a79c36318b`; internal pack at `ecda7b00c7`; events read service at tag `service-v0.1.0-rc.1`; events Python package locked at 11.3.0; tracker package at 0.5.2. Released: `spec-kitty-cli` 3.2.7 and 4.0.0rc8; core head is 4.0.0rc9, not published. Thirteen further repositories were cloned read-only as supplementary sources.

## Definitions

- **Verdicts.** Supported, contradicted, inconclusive, not assessable, by the pre-registered criteria only. "Not assessable" is never read as support.
- **Views.** Recorded intent: what a record says. Observed: what was run or computed. Approved plan: recorded, not yet carried out. Proposal: the design brief and the recommendations here.
- **Reproduced.** The reviewer's own derivation from raw artefacts matched the finding's figure.
- **Decisive.** A finding the synthesiser marked as one a verdict rests on. The evaluation notes that this set omits two findings the H03 figure is computed from.
- **Corrected figures.** Where a later stage corrected a number, this report quotes the later one and says so: the count of blame candidates in H02 (16 of 24, not 9); the mutation detection against per-change CI (20 of 23 beside 16 of 23); the H07 share on the registered denominator (11 of 11 or 10 of 11 beside 12 of 14); the count of contradictions between records (25 rows, not 18).

## Traceability

The full table is `report/traceability.csv`: one row per statement, with its kind, source files and finding identifiers. The summary's headline figures were re-checked against their sources after rendering.

| Statement | Kind | Source |
|---|---|---|
| Verdict table, all 21 items | conclusion | `evaluation/verdict-ledger.csv` |
| Reproduction rates | method | `evaluation/validity-evaluation.md` section 2; `review/repro-R1.md` to `repro-R3.md` |
| Overturns of H05 and H08 | conclusion | `review/verdict-challenge.md` sections 5 and 8 |
| Departures no check reported | conclusion | `synthesis/deviation-catalogue.md` part A3; `synthesis/assurance-gaps.md` |
| Interpretations | interpretation | `synthesis/knowledge-model.md`; `review/synthesis-challenge.md`; `evaluation/validity-evaluation.md` section 3 |
| Registers and shapes | recommendation | `synthesis/knowledge-model.md` sections 3 to 5 |
| Disagreements | conclusion | `dialectic/dialectic-record.md`; `dialectic/disagreements.csv` |
| Process grades and deviations | method | `evaluation/process-evaluation.md`; `evaluation/process-deviations.csv` |
| Decisions | decision | `synthesis/open-human-decisions.md` |

## Caveats

- One evaluator and one pass per review role. Reviewer-computed and evaluator-computed figures are arithmetic over committed artefacts; they are exploratory and decide nothing alone.
- The pre-registration was not fully blind. Before it was written the coordinator had seen raw cycle counts and had read core's agent-guidance file.
- The operations log is the coordinator's own account of one investigation that ran outside the mission runtime. It is a single case and supports no rate.
- A blocked build or missing access is a coverage limit throughout, never evidence of a defect. The absence of prospective components named in the brief is not a deficiency.
- The generator's monospace web font is fetched over the network at render time; if it was refused, code spans fall back to the platform face.
