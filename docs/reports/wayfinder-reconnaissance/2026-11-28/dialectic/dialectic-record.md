---
doc_status: draft
updated: '2026-11-28'
---

# Dialectic record

Role R, recorder, profile `minutes-mahad`; charter context for the action `review` loaded. I authored none of the four papers and none of the work they discuss. This file records; it decides nothing, adds no position and does not weigh one side against the other. The human architect decides.

Sources: `position-A.md` (A, profile `architect-alphonso`), `position-B.md` (B, profile `reviewer-renata`), `rebuttal-A.md`, `rebuttal-B.md`. The table of disagreements is `disagreements.csv` (ids D01 to D23); this file refers to it by id.

## 0. How the papers were written

- Both position papers were written without sight of the other (each says so).
- The rebuttals were written in parallel: A did not read `rebuttal-B.md`; B did not read `rebuttal-A.md`. Points raised for the first time in one rebuttal therefore received no answer from the other side. That is a property of the procedure, not a concession, and section 4 marks such points.
- Both authors note a conflict between their profile and the envelope (A's profile verbs "design" and "decide"; B's profile asks for approve or reject) and say the envelope won. Mine: the profile asks which minutes format to produce and works from a transcript; the brief fixes the format and the source, so the envelope wins. The profile's attribution rule is applied as the `whose_decision` column; the record contains no action items.
- Neither author re-ran anything. B opened `evidence/B1/series.csv` (header) and F-B1-013 for its rebuttal.

Status values in the CSV: **conceded by A** or **conceded by B** (one side gave the point up); **narrowed** (at least one side narrowed its claim and a residue of disagreement remains, or the residue was passed to a named ruling); **open** (neither side moved).

## 1. Reference check

| Checked | Result |
|---|---|
| Finding ids of the form F-xx-nnn cited in the four papers | 82 distinct ids, plus F-H06b-013 and F-A1-012 (cited inside the range "F-A1-011 to F-A1-013"). All 84 exist as files under `findings/` |
| Files cited | `review/repro-R3.md`, `review/verdict-challenge.md`, `review/synthesis-challenge.md`, `evaluation/validity-evaluation.md`, `synthesis/hypothesis-assessment.md`, `synthesis/assurance-gaps.md` (including section 2.1), `synthesis/knowledge-model.md` (sections 1, 3, 4, 6), `synthesis/deviation-catalogue.md`, `synthesis/open-human-decisions.md` (sections A to F), `evidence/B1/series.csv`: all exist |
| Review items H-07, C-01, W-01, A-02 | Present in `review/challenge-items.csv` and `review/synthesis-challenge.md` |
| Mutation ids M-RD-4, M-IC-2, M-PI-3, M-PI-5, M-OB-4 | Present in E2 and E3 findings |
| Decision ids A1 to A6, B5 to B7, C1, C5, D3, D4, F1 to F4; deviation D-3; ruling R4; PX-01; AS-10; registers K1 to K7 | All present in the cited files |
| Deviation-catalogue counts quoted by B (A1 8, A2 4, A3 14, A4 4; C and D together 11) and by A (part B 8) | Match the catalogue's own Counts table (C 4, D 7) |
| Figures spot-checked: 77 of 89 untraced rules; 135 of 310 boundary gate files (F-E1-001); 31 entries in the orchestrator version ledger (F-F-007); 8 pairwise precedence records (F-A1-003); 20 of 23 and 16 of 23 (`repro-R3.md`); the density table (+14.2% / +15.1% in the window, +2.9% / +4.8% granularity-free, +21.7% and +14.2% after the merge, `verdict-challenge.md` section 1) | Each matches its source |

No cited id or file was missing. One reading aid, not a correction: A's "90.7%" is the share of `specify_cli` lines with no stated internal model; B's "92.8%" (concession 6) is the share of all core lines. Both are in F-B1-013 and have different denominators.

## 2. Agreement reached without pressure

Stated independently in both position papers, before either author saw the other:

1. H01 does not support the brief's founding story; support is out of reach, and M01b and M01d fell (F-B1-001, F-B1-004, F-C-008). Corrective commits touch fewer components than capability-growth commits in both runs (F-C-006, F-C2-008).
2. H02, H04 and H07 carry no weight for the design (F-C-021; `verdict-challenge.md` section 4; F-F-001, F-F-002).
3. The enforced tier holds: 0 unrecorded violations in 8,332 module edges (F-B1-010).
4. H03 shows silence, not breach: 464 of 656 edges sit inside one top-level package where no record speaks (F-B3-002). What it means waits on decision F3.
5. H06 is supported robustly: a contradicting source for 10 of 20 questions (F-H06b-013).
6. PX-01 is a real, reproduced defect that no gate reported (F-E1-028 to F-E1-030).
7. Contract compatibility is effectively unchecked in two repositories: 0 of 6 incompatible-contract mutations caught by a compatibility or version check (F-E3-013, F-E3-015).
8. Mission acceptance reads nothing beyond its repository: 0 of 13 (F-E1-032).
9. No ruleset requires an approving review and each has a bypass actor (F-E1-004).
10. No ecosystem-wide precedence exists among records (F-A1-003).
11. The brief's full scope, with prose views restated in a separate repository (shape C), is not warranted by the evidence (A section 6; B section 5; F-A1-021, F-A1-036).
12. Nothing about Wayfinder was tested (AS-10 desk only) and the cost of keeping any register true is unknown.
13. Core publishing its model and exception ledgers outside test files (decision F2) is the cause the H08 evidence names (F-G2-015, F-G1-003, F-G1-005).
14. 0 of 20 documentation answers were incorrect against code; 12 were fully correct (F-H06b-013).

Rebuttal A lists most of these as agreement; rebuttal B says "the disagreement left is narrower than the roles suggest; I do not widen it."

## 3. What each side withdrew or narrowed in rebuttal

**A** (rebuttal-A section 3):

- Withdrew "inside `specify_cli`" as a departure: "With no record there is nothing to depart from." Kept as an unmodelled area pending F3 (D06).
- Narrowed "14 such entries" as the size of the uncaught class: "'No exception found' is an upper bound on 'unknown'" (D01).
- Withdrew the missing core-to-charter-service check as a gap: it sits on a pending approved plan (F-E1-008; ruling R4) (D14).
- Narrowed the pack case to "a contradiction between two repositories' records with an executed consequence" (D13).
- Narrowed H03: dropped "any suggestion that a model would have bounded it (conjecture)" (D02).
- Narrowed "a repository is warranted" to "a generated cross-repository index (K1, K3) and published local models and ledgers"; whether that is a new repository is open; K2 and K4 only after F2 and F3 (D07, D08).
- Narrowed the exception-field point: the 231-pair baseline is exact and names issue, owner and drain target (F-G2-003, F-E1-022); "the gap is 2 of 24 leaves with all three fields, not absence of governance" (D20).
- Kept: sections 3.1, 3.2, 3.4, 3.5, the H06 argument and the H08 reading.

**B** (rebuttal-B section 2):

- Withdrew "too large" against A; it "stands against the brief's initial scope only" (D15).
- Narrowed "aimed at the wrong problem": a register of rule-to-check bindings "could report a check that is named and run nowhere, or a compatibility check with no baseline, if it is kept true. It would reveal, not stop." Kept the point for PX-01 and anything behavioural (D01, D18).
- Narrowed K1 and K3 from optional to "the cross-repository need for K1 and K3 is observed. Where they live is open" (D07).
- Narrowed "governance and gates are doing their job" to "rules written as gates over import structure hold. A check that reports green without comparing is not doing its job, in two repositories" (D21).
- Narrowed H06 limits: "'fails on any stale page' describes fragmentation and is not only an artefact. The selection of questions remains a limit" (D03).

## 4. Disagreements, in the parties' own words

Each is in the CSV with evidence columns. Quotations are from the papers; nothing is paraphrased into a middle position.

**D01. Class or list.** A: the departures "no existing gate looks at" form a class, "shown by 14 uncovered entries from a partial trace, not by a rate"; after narrowing, "the residue lies between repositories, where no local gate can hold the view." B: "Without [a rate], 'class' and 'list of items' cannot be told apart on this evidence"; the items are "checks present but not wired, plus PX-01." B's split of the 14 A3 entries (6 behaviour, 8 record keeping) is, in B's words, "one reader's, made today"; A calls it fair.

**D11. "Nothing in the gate inventory is built to."** A (position section 3): "nothing in the gate inventory is built to" report these departures. B (rebuttal 1.1): "for five of A's items the check or the rule is present and not wired, not fed or not followed. That is a different condition from 'no place holds the knowledge'" (F-E3-013, F-E3-014, F-E1-012, F-E1-010, F-F-007). First raised in rebuttal-B; A's rebuttal could not answer it.

**D12. Can one repository hold a cross-repository view?** A: "No single repository's gate can hold a cross-repository view" (position section 5). B: "15 cross-repository check relations exist, each held by one repository's gate through a pin (F-E1-008). Single repositories do hold cross-repository views. What the evidence shows is lag." B accepts that K1 and K3 "have no natural owner among the five repositories." First raised in rebuttal-B; unanswered.

**D02. Where density rose.** A: "the one structural measure that moved after the convergence moved where the assurance has no model to compare against" (F-B1-001; review item C-01). B: "No finding I read places the 21.7% rise, or the 14.2% granularity-free rise, inside `specify_cli`. That it sits there is plausible from size ... and is conjecture"; `series.csv` has no split by top-level package; door rules in other gate files "were not inventoried rule by rule" (`assurance-gaps.md` 2.1). First raised in rebuttal-B; unanswered. Both say no cause can be drawn (M01f did not replicate) and no trend across 2554bd13ad.

**D03. Practical weight of H06.** A: "An agent that acts on a partly correct answer ... produces a change that is locally reasonable and architecturally off. That this has happened at any rate is conjecture." B: "A's own word is conjecture; 0 of 20 answers were incorrect"; the questions were written after reading core's guidance file (`verdict-challenge.md` section 11).

**D04. Were the A3 entries already known?** A: "Not shown either way." B: "Upper bound on unknown." Both cite `open-human-decisions.md` section E: no tracker check was made.

**D05. Gates guard the rule, or react to patch shape?** A: "On failures that name the violation the count stays 16 of 23." B: "20 of 23 are flagged, core 15 of 15", while accepting R3's caution that four extra detections come from a dead-symbol gate "so they do not show the rule is guarded" (`repro-R3.md`).

**D06. Is the silence inside `specify_cli` chosen?** A: "Unknown; it matters because 77.6% of lines sit there." B: "May be chosen, since the enforced pair is the authority" (F-A1-001). Both: decision F3.

**D07. Where an index lives.** A: shape B (a thin register of references with checks) resting on shape D. B: "D first; A or B undecided, K1 and K3 only"; earlier, "a new repository is a 34th surface and a seventh decision-record home (inference)." A: "Whether it needs its own repository the evidence does not say."

**D08. K4 centrally.** A: yes, "the brief's traceability chain." B: "Not shown: G1 was never re-run with the ledgers as data, and exception fields differ by recorded rule per repository (F-E1-024)."

**D09. Order of work.** A (as B reads it): "Design shape B now." B: "Rulings A1 to A6, F2, F3 first; they cost nothing and each moves a verdict." A's rebuttal accepts "rulings A1 to A6, B5 and C1 precede any design." The recorder notes the two papers characterise A differently here; A's rebuttal did not see B's table.

**D10. Unowned responsibilities** (supervision, cancellation, attachment; F-F-012, F-F-024). A: "a matter for a knowledge repository before it is one for a runner." B: "a gap in recorded intent that one decision record closes (B6)."

**D13. The pack case** (0 of 19 at open-packs head, F-D1-021). A: "A deliberate decision in one repository that contradicts a standing record in another is the cross-repository case." B: "by recorded intent of open-packs (F-A1-015). It is a contradiction between records for the architect (decision C5), not something a gate missed."

**D18. PX-01 and a register.** A: "That a register would have caught PX-01 ... is conjecture." B: "An executed walk through a mission type would catch it; a record of intent would not (inference)."

## 5. Counterevidence a side did not answer

Answered means the other paper engaged the evidence, not that it agreed.

**Raised by A, not answered by B:**

- B lists these itself as counterevidence it could not answer (rebuttal-B section 4): 0 of 6 incompatible-contract mutations caught by a compatibility check, and the verb `merge-mission` removed inside contract version 1.6.0 with 2 of 3 consumers still naming it (F-E3-015, F-F-007, F-F-008); 0 of 60 exception entries with all four fields and no ruleset requiring approval (F-E1-025, F-E1-004); no ecosystem-wide precedence (F-A1-003).
- A section 3.4: 6 of 12 sampled rules end at a step instruction with no gate (F-E1-014); none of 6 sampled architecture rule texts appears in the action's charter context (F-E1-015). Not addressed by B in either paper.
- A section 3.5: amendment markers on 77 of 239 core ADRs and 61 of 83 charter records against a recorded immutability rule (F-A1-018); the core charter's statement that nothing on GitHub enforces the workflow against three rulesets (F-E1-006, F-A1-006). B classed A3.11 as record keeping; it did not dispute the facts.
- A section 3.3: 10 formats defined on both sides of a service boundary (F-D2-010) and 7 of 8 pack-schema pairs differing (F-B2-031, medium confidence). B did not address them.

**Raised by B, not answered by A:**

- Deliberate gaps: dispatch delegated by record (F-F-005); the dynamic-import blind spot stated in the gate's own docstring (F-B1-012). A's papers do not take these up.
- "The 87.0% reproduction rate supports numbers, not the judgements behind H04 cells, H07 states, M02 traces or the H06 authority column" (`validity-evaluation.md` section 2). Not addressed by A.
- Everything except H01 and H02 holds for one day's head revisions. Not addressed by A.
- The rebuttal-B points D02, D11, D12 (procedural: first raised in rebuttal).

**Answered across the papers:** the per-change CI figure (A engaged it, D05); the M02 frame seeing misses not catches (A: "a catch I did not credit"); the pack case (both engaged, D13); "premature" (A accepted it in full); H06 as fragmentation (B narrowed).

## 6. Questions nobody could answer

From both rebuttals and the position papers' limits sections:

1. Whether any of these departures has harmed a user of a released version (rebuttal-A section 5).
2. What drives import density after the convergence; M01f did not replicate (both).
3. The outside observer's predictions, not yet returned (both; `validity-evaluation.md` section 8).
4. The cost of keeping any register true (both; `knowledge-model.md` section 6; `open-human-decisions.md` F1).
5. Whether the A3 entries and section E observations were known to maintainers (D04).
6. Whether the 15 sampled defects that reached `main` (F-C-019) were cross-repository (decision F4 lists it; neither paper answers it).
7. Whether a register would have caught PX-01 or the verb removal: both papers mark the answer as conjecture or inference (D18).
8. Whether a defect from one of the 10 duplicated formats or 33 pin surfaces has reached a release (rebuttal-A D01 settle column).

## 7. Matters of evidence and choices for the architect

**Settled by further evidence (an investigation could do it):**

| Id | Evidence named by the parties |
|---|---|
| D01, D04 | Tracker check of the 14 A3 entries and section E; trace the 77 untraced rules; per entry, whether a rule or check already existed |
| D02 | M01a between the merge result and head split by top-level package; inventory of rules in non-layer gate files |
| D03 | A second question set by an author who has not read core's guidance file; contradiction search restricted to authoritative sources; defects on `main` traced to a documentation cause |
| D05 | Decision D4: re-run with patches that add no uncalled function, against the full battery |
| D12 | Trace the duplicated formats and pin surfaces for a defect that reached a release |
| D18 | No party named a test |

**Evidence first, then the architect's choice:**

| Id | Evidence, then ruling |
|---|---|
| D07 | Regenerate the four tables at a second date and count hand corrections (an upkeep cost); then F1, after B5 and C1 |
| D08 | G1 re-run with ledgers supplied as data; then B7 |
| D13 | Then C5 |

**The architect's choice, not a matter of evidence (both parties say so):**

| Id | Ruling |
|---|---|
| D06 | F3: does `specify_cli` get a recorded internal model |
| D09 | Order of work: rulings first, or design first |
| D10 | Where unowned responsibilities are placed (B6, A6) |
| D23 (H05) | A5: whether a ledger header counts for its entries |

D11 has no settling evidence or ruling named by either party; it was first raised in rebuttal-B and A had no opportunity to reply. The other rows (D14 to D17, D19 to D22) are concessions, or narrowings with no residue named; the CSV gives the side and the status.

## 8. What would move each party (as they stated it)

- A (position section 7): a gate battery or per-change CI that catches PX-01 or a removal without a version change; a second H06 question set scoring 11 or more; a ruling that `specify_cli` is meant to have no internal model; G1 re-run with ledgers as data still disagreeing with G2.
- B (position section 7): the stub test behind `charter.offering.api` failing (D3); a second judge on H04 finding two present claims not established; the seven undetected mutations still undetected in core on the full battery (D4); a tracker check showing most of section E was unknown; a ruling that `specify_cli` is meant to have an internal model.

Both name F3 as a ruling that would move them, in opposite directions.
