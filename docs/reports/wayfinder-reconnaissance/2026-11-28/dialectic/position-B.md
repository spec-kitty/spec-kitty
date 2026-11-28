---
doc_status: draft
updated: '2026-11-28'
---

# Position B

Role B of the dialectical review, profile `reviewer-renata`, charter context for the action `review` loaded. The profile asks for an approve or reject decision; the envelope leaves decisions to the human architect, and the envelope wins. I authored none of the work discussed. Reproduction review R1 ran under the same profile in another session.

I ran no test, build or measurement. I read files 00 to 05, the synthesis, the review, the evaluation, the design brief and seven finding records. I did not read `position-A.md`. Figures are quoted from the cited files; my own counts are marked.

The role is assigned. Section 6 lists what I cannot defend. "Smaller responses" in section 5 are options in the **proposed** view, taken from the synthesis, not implementation proposals.

## 1. The position in five sentences

1. Where the ecosystem has written a rule down as a gate, the rule holds, and the departures from it are listed, counted and mostly shrinking.
2. The hypothesis that started the design, that a period of point fixes degraded orthogonality, is not supported and sits closer to contradicted than to supported.
3. Of the three "supported" or contested verdicts that favour the design (H03, H05, H06), two turn on an operational choice made after data existed, and the third measures documents, not architecture.
4. The one hypothesis that tests the design's own premise (H08) came out inconclusive or contradicted, and the design itself was never tested.
5. The gaps that executed evidence does show are local and specific; a documentation-first repository without acceptance authority is not shaped to close them.

## 2. Recorded governance and existing gates do their job, as far as the evidence can show

**The enforced tier holds.**

- 0 unrecorded violations in 8,332 module edges of core (F-B1-010); the layer gate itself passed 80 of 80 when E3 and D1 ran it (F-E3-001, F-D1-027).
- 0 of 656 component edges match a documented prohibition without a recorded exception (F-B3-003). All 8 documented may-depend pairs are in use (F-B3-008). F-B3-008 is cited by no synthesis document (`synthesis-challenge.md`).
- Load-time import cycles stay below 2% of modules at every point and none spans two components (F-B1-004).
- Charter Java: 0 violations in 136 executed architecture tests (F-B2-005). Events Java: 0 violating package edges by static check (F-B2-011); its build is a coverage limit.

**The gates detect planted violations.** Against the frozen set E3 used, 16 of 23 assessable mutations were detected. Reviewer R3 shows that this set was 66 of 310 gate files, and that against per-change CI, as far as executed evidence goes, 20 of 23 are flagged, core 15 of 15, with 16 failures naming the violation (`repro-R3.md` on F-E3-006). The three unflagged mutations are all outside core, and the mutation author judged the rule behind two of them partly ambiguous (M-RD-4, M-IC-2; F-E2-004, F-E2-006). I accept R3's caution: four of the extra detections come from a dead-symbol gate reacting to patch shape, so they do not show the rule is guarded.

**Exceptions are governed.**

- 24 of 27 ledgers that existed on 2026-09-07 are flat or shrinking (F-E1-018).
- Caps were lowered by 164 and raised by 44 over the range (F-E1-019).
- The largest recorded boundary exception, 231 (file, module) pairs behind `charter.activation.api`, matches the observed pairs exactly and names an issue, an owner and a drain target (F-G2-003, F-E1-022).
- Growth in the number of ledgers is mostly new gates registering constructs that already existed: 30 of 57 file ledgers were created in the range (F-E1-018; reading F-E1-035, low confidence). Adding ratchets is tightening (conjecture as to motive).

**The process catches defects before `main`.** In both independent samples, 13 of 30 cross-component "fixes" corrected something introduced in the same pull request that never reached `main` (F-C-019, F-C2-018, replicated, F-CX-008). The synthesis says a gate that blocks a change before any commit leaves no trace in this frame (`assurance-gaps.md`, section 4). The M02 frame therefore sees the assurance system's misses and almost none of its catches.

**Recorded intent is ranked where structure is concerned.** Core states 14 precedence rules; the enforced pair prevails over every prose module map (F-A1-001). The synthesis' own summary is that "the knowledge exists and is mostly right" (`knowledge-model.md`, section 1): 0 of 20 documentation answers were incorrect against code and 12 were fully correct (F-H06b-013).

## 3. Observed departures are bounded, known or deliberate

The deviation catalogue has 26 entries in part A where implementation departs from a record (`deviation-catalogue.md`).

| Group | Entries | What it means |
|---|---|---|
| A1, covered by a recorded exception | 8 | Known and ledgered; A1.1 flat since 2026-09-07, A1.4 lowered from 45 to 33 with a drain date |
| A2, covered by a note or disputed | 4 | One dynamic import; three Java items "partly recorded" or annotation-only |
| A4, the record lags the implementation | 4 | The implementation is ahead of or stricter than the record |
| A3, no recorded exception found | 14 | See below |

Of the 14 in A3, by my own classification, 6 concern product behaviour (A3.1, A3.2, A3.5, A3.6, A3.7, A3.12) and 8 concern how records and ledgers are kept (A3.3, A3.4, A3.8 to A3.11, A3.13, A3.14). A3.12 is one purposive case against 12 of 12 agreeing in the seeded sample (F-D1-026). The catalogue states that whether an item is already known was not checked against the trackers (`open-human-decisions.md`, section E). "No exception found" is therefore an upper bound on "unknown".

Parts C and D hold 11 entries that are approved plans not yet executed, or recorded decisions that differ from the brief. Under ruling R4 neither is drift. The charter offering served from core, the Python event writer, and the absence of a core-to-charter-service check all sit on pending approved plans (F-A1-033, F-D2-017, F-E1-008; `synthesis-challenge.md`, A-02).

Several "gaps" are deliberate by record: dispatch is delegated (F-F-005); open-packs ended compatibility with the as-is CLI on purpose (F-A1-015), which is why 0 of 19 packs at its head validate; the dynamic-import blind spot is stated in the gate's own docstring (F-B1-012).

## 4. The measures and samples do not carry the weight put on them

**H01, the founding narrative.** Inconclusive by the letter. Support is out of reach under any reading: M01b load-time and M01d fell (F-B1-004, F-C-008, replicated F-C2-010). Read from P2, the first point inside the window, M01a rises 9.8% and 10.6% against a contradiction limit of 10% (`validity-evaluation.md`, section 3). M01a moves when packages are split; the granularity-free density moved 2.9% and 4.8% inside the window (`verdict-challenge.md`, section 1; reviewer-computed, exploratory). Corrective commits touch fewer components than capability-growth commits in every period, in both runs (F-C-006, F-C2-008). The brief calls the degradation "attributed experience"; the evidence leaves it there.

**H02.** Inconclusive and one row from not assessable (10 of 30 untraceable in C2, plus 9 weak traces). Acceptance was read from a field present on 430 of 858 Missions. "A person" includes agent review squads (F-C-019). The detection route does not replicate, 22 against 16 (F-CX-008).

**H03.** Supported only through silence. 464 of 656 edges lie inside one top-level package where no record speaks; the pre-registration's own section 3 says that case is "no intended model", not misaligned. Among the 192 edges that cross a top-level package, 84.4% are documented (`hypothesis-assessment.md`, H03). Core's record makes the enforced pair the authority by decision (F-A1-001), so the silence may be chosen. The hypothesis says concepts exceed implementation boundaries; the measure shows the records stop at package level.

**H04.** The count of capabilities is 0, 1 or 2 depending on three mapping choices made after the data (`verdict-challenge.md`, section 4). Cells are single-judge readings. The contradiction criterion was unreachable because three tests were not taken (`validity-evaluation.md`, H04). Among 34 present claims, 1 is not established.

**H05.** One ruling moves it across all three verdicts. 1,929 of 3,357 entries are bare paths in one formatter exclude list whose header carries the retirement condition; that is format debt, not compatibility sediment. With headers counted, 22 of 30 and 16 of 30 sampled entries carry a condition (F-E1-025).

**H06.** I concede the verdict (section 6). Its weight is limited: the coordinator wrote the questions after reading a file that lists contested subjects; one checker, without the question texts; and the third condition fails on any stale page among 2,051 files, so the score falls with corpus size (`verdict-challenge.md`, section 11).

**H07.** Contradicted. The brief's premise that execution infrastructure is comparatively immature is not shown. I do not lean on it: the comparator was a ceiling (`validity-evaluation.md`, H07).

**General.** The 87.0% reproduction rate supports numbers, not the judgements behind H04 cells, H07 states, M02 traces or the H06 authority column (`validity-evaluation.md`, section 2). Everything except H01 and H02 holds for one day's head revisions. The outside observer's predictions have not been returned, so the one control against hindsight is still pending.

## 5. The preliminary design is premature, too large, and partly aimed at the wrong problem

**Premature.**

- Wayfinder was not tested. The pre-registration says M08 "is not a test of Wayfinder"; AS-10 is desk only; the brief itself asked to "test Wayfinder itself, not just core".
- H08 is inconclusive (synthesis) or contradicted (review). In core Python the contract-only and implementation-aware checks agree for 2 of 6 invariants.
- At least six rulings precede any design: A1 to A6 each move or reframe a verdict, and B5 and C1 gate the shape (`open-human-decisions.md`).
- "The cost of keeping any register true" is unknown (`open-human-decisions.md`, F1; `knowledge-model.md`, section 6). The design's whole risk is upkeep, and the evidence has nothing on it.

**Too large.**

- The brief's initial scope lists fourteen kinds of content. The synthesis finds several independent observations for four registers (K1 to K4), one low-confidence workstream for K5, and "little" for K6 and K7 (`knowledge-model.md`, section 3).
- The evidence the synthesis itself gathered argues against any element that restates what a repository owns (`knowledge-model.md`, section 4). The review narrowed "copies drift in every case" to "copies without a pin drift" (W-01); that still argues against shape C.
- A precedent exists: planning's target architecture of 56 records "binds nothing until ratified", names no core revision, and no ratification was found (F-A1-036). A second documentation-first architecture source would start in the same position unless C1 and B5 are ruled first.
- The ecosystem already has 521 decision records and 33 pin surfaces lagging 53 to 4,369 commits (F-A1-026, F-D1-001, F-D1-002). A new repository is a 34th surface and a seventh decision-record home (inference).

**Aimed at the wrong problem.** The executed gaps are these, and each sits in one repository's own gate set:

| Gap | Evidence | Where it sits |
|---|---|---|
| Contract compatibility check passes with no baseline | F-E3-013, F-E3-015 | charter, events |
| A required cross-repository check is skipped on forks and reads as success; pinned to 2026-05-21 | F-E1-010 | events |
| A contract example checker and the packaged conformance suite invoked by no workflow | F-E3-014, F-E1-012 | events |
| Dynamic imports invisible to direction gates | F-E3-008 | core |
| A research Mission stalls at a guard with no producer | F-E1-028 to F-E1-030 | core |
| Owner on 2 of 30 exception entries | F-E1-025 | each ledger |

The brief says Wayfinder "supplies verification evidence, not operational coordination or acceptance authority". The synthesis draws the consequence: if Wayfinder has no authority and acceptance stays local, "the evidence does not show where an ecosystem violation would stop a change" (`knowledge-model.md`, section 4). A knowledge repository describes these gaps; it stops none of them (inference).

**Smaller or different responses the evidence fits better** (proposed view, from the synthesis, for the architect):

- Shape D, or decision F2 alone: each repository publishes its model and exception ledgers in readable form. This is the one cause the evidence names for the H08 disagreement in core (F-G2-015; `validity-evaluation.md`, H08).
- A ruling on F3: state an internal model for `specify_cli` or record that none is intended. That alone decides what H03 means.
- A ruling on A5 and B7: where a reference lives and which fields an exception carries.
- The decision in section E of `open-human-decisions.md`: which of nine executed observations become tracker issues. The charter already asks for this (deviation D-3).
- If an index is wanted, shape A or B limited to K1 and K3, generated from record headers and pin files, which this investigation built once by script in a day (`knowledge-model.md`, section 6).

None of these needs a new normative source.

## 6. What I concede

I cannot defend the following, and role A is entitled to them.

1. **PX-01 is a real, reproduced defect** on a documented surface (F-E1-028, replayed by R3). No gate caught it. A product defect in one mission type, not structural drift, but it passed the existing assurance.
2. **H06 is supported robustly.** A contradicting source exists for 10 of 20 questions, which caps the score at the support threshold whatever the judgement on authority. No ecosystem-wide precedence exists (F-A1-003), and activation authority is recorded three ways (F-A1-011 to F-A1-013).
3. **Contract compatibility is effectively unchecked** in two repositories: 0 of 6 incompatible-contract mutations were caught by a compatibility or version check (F-E3-015).
4. **Mission acceptance looks at nothing beyond its repository** (0 of 13, F-E1-032), and in one run all 15 sampled cross-component defects that reached `main` were found by a person (F-C-019).
5. **Core does not meet its own exception policy**: of 24 non-zero baseline leaves, 2 name issue, owner and date (F-E1-022).
6. **"The gates do their job" says nothing about 92.8% of core's lines**, which have no internal model for a gate to check (F-B1-013). There, section 2 is silent, not reassuring.
7. **Import density rose in every period**, and the granularity-free density rose 14.2% after the convergence while the component count fell (`verdict-challenge.md`, section 1). I cannot say governance bounded that. Nor can anyone attribute it: M01f did not replicate.
8. **No ruleset requires an approving review and each has a bypass actor** (F-E1-004); a GitHub review by another account was found for 0 of 80 sampled commits in T2 and T3 (F-C-016, replicated). Reviews outside GitHub's review object were not counted.
9. **The mutation result is six cases per class**, not a sample of real changes. It supports "detects planted violations of written rules", not a detection rate.
10. **My own classification in section 3** (6 behaviour, 8 record-keeping) is one reader's, made today.

## 7. What would change this position

- The stub test behind `charter.offering.api` failing (D3), or a second judge filling the H04 cells and finding two present claims not established.
- The seven undetected mutations re-run against the full battery, with patches that add no dead symbol, and still undetected in core (D4).
- A tracker check showing that most of section E was unknown to the maintainers.
- The architect ruling that `specify_cli` is meant to have an internal model, which would turn H03's silence into a gap against intent.
