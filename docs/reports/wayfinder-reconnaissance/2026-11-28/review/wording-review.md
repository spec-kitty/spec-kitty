---
doc_status: draft
updated: '2026-11-28'
---

# Wording review: terms, claim strength, consistency, views

Reviewer L, profile `lexical-larry` (semantic analyst: detects terminology drift and proposes canonical alignment; it does not rewrite documents). Under the envelope I write only under `review/` and change nothing. The profile's handoff to a glossary curator is not used: no glossary change is proposed.

Item list: `wording-items.csv`, 57 rows (L-001 to L-057), each with the exact quoted text, the problem, a grade and what the evidence does allow one to say. Grades: **major**, a reader would take away something the evidence does not support; **minor**; **note**.

| Grade | Synthesis documents | Sampled finding records | Total |
|---|---|---|---|
| major | 5 | 0 | 5 |
| minor | 23 | 6 | 29 |
| note | 21 | 2 | 23 |
| Total | 49 | 8 | 57 |

## Scope and method

- All 18 `.md` files directly in `synthesis/`. I read 17 in full and the first part of `S-A-phase1.md`, whose content `hypothesis-assessment.md` repeats. The `.csv` tables were opened only where a document cited them for a value I checked.
- Terms were checked against `docs/context/` in core, especially `naming-decision-tool-vs-agent.md`, `orchestration.md` (Mission Run, primary, routing, residue) and `identity.md`, and against how the finding records use them. I took the design brief's vocabulary from the PDF.
- For claim strength I opened the cited finding record (claim, evidence kinds, scope, disconfirmation) for every sentence I graded. I re-ran no measurement and ran no test or build.
- The sample is the 67 `decisive` rows of `review/sample.csv`. None is in workstream A2, so all 67 were read.

## 1. Terms

**Checked and clean.** "Feature" for the domain object: 0 hits in the 18 documents. "Residue": 0. "Primary" appears only in "Lamport-primary", which is the records' own phrase. "Projection" is given a sense where the report uses it (component catalogue, Terms; AS-09 "(derived status snapshot)"). Prospective names (Kira, HUD, Operations Deck, Wayfinder) are kept in the proposed view everywhere I looked.

**Overloaded words used without their sense.**

- *coordination* has four senses (L-039): the brief's mission coordination (M07b), the orchestrator as "external coordination", the ecosystem's coordination branch and status (`decision-timeline.md`, deviation part D), and the coordinator. In `hypothesis-assessment.md` the H07 column is headed just "Coordination (M07b)". A reader who knows the codebase will read it in the topology sense.
- *charter* names the project charter document ("core charter", "events charter") and the `spec-kitty-charter` repository (L-042). Two documents give opposite readings of "charter's" rule: in `assurance-gaps.md` section 5 it is core's charter (F-E1-022), and in `knowledge-model.md` and `open-human-decisions.md` B7 it is the charter repository.
- *ledger* stands for the status event log ("Status ledger and reducer"), the 75 exception ledgers of H05, the activation ledger and the migration ledger (L-041). This happens although the component catalogue says it adopts core's term "status event log".
- *harness* means the tool in the research prompt and the events cross-repository test harness elsewhere (L-043).
- *independence* is used for the R3 dimensions, for review independence of actors (an ecosystem guard) and for the investigation's own independent review (L-046).
- *merge* and *routing* each appear once or twice without their sense (L-047, L-048).

**One thing under several names.** Core's glossary decides that "tool" is the concrete execution product. F-A2-003 cites that decision. The component catalogue nevertheless picks "agent tool" (L-040). Across the documents the same product is also "external tool (the agent CLI or IDE)", "executor", "harness", and in AS-04 "the latest agent". Further pairs: "missing" in `hypothesis-assessment.md` against "absent" in `execution-capability-matrix.md` for the same state (L-019), and different row names for the same M04 capability in S-A and S-B (L-045).

**Outside terms used as if they were ecosystem terms** (L-044, L-049). The rows of the execution matrix keep the brief's vocabulary: resource identity, human attachment, execution infrastructure, unit of agent work, execution unit. That vocabulary is never mapped to the ecosystem's own terms (Op, Mission Run, work package, lane, tool). `knowledge-model.md` writes "the runner assignment contract" as if it existed.

## 2. Claim strength

The five major items:

1. **Two different independence matrices** (L-001, also a consistency item). See section 3.
2. **"Missing" in the H07 table** (L-019). The pre-registered criterion counts only responsibilities "that recorded intent places inside the ecosystem". F-F-024 and F's own artefact say that no record places cancellation or attachment anywhere. `execution-capability-matrix.md` calls the state "absent" and gives three denominators (12 of 14, 11 of 11, 12 of 13). `hypothesis-assessment.md` gives only F's count. The verdict does not change, because it is contradicted under every reading. The word does change: a reader takes away two deficiencies against intent, which rulings R5 and R7 exclude.
3. **"Meaning changed ... on 63% of 4.x core records"** (`knowledge-model.md` N1; L-017). F-A1-018 counts amendment markers, 33 of 52. A change of meaning is shown for one record.
4. **"Copies drift in every case observed"** (`open-human-decisions.md` F1; the same generalisation appears in `knowledge-model.md` section 4; L-018). The four cases were found because they differed. No set of copies was enumerated, so copies that did not drift were never looked for. The sentence feeds decision F1 directly.
5. **"Direction between the six packages holds"** (`quality-attributes-invariants-scenarios.md`; L-002). `S-C-differences.md` 2.3 records that "holds" was too strong and that the table was changed. The word is still there.

Minor items:

- **Trend across the convergence (L-020).** "From 3.3 at P0 to 9.2 at head" is a span across merge `2554bd13ad`. The per-period values carry the same point within the rules.
- **Universal claims from one probe or one run.**
  - "Core's Python writer performs every status write" (L-021) rests on one executed write plus a static result. Four documents repeat it.
  - "A research Mission cannot pass step 3" (L-023) rests on one run, and no producer outside core was searched for.
  - "Every check in this investigation was a script over files" (L-024) is false for the tests, builds and binaries the investigation ran.
- **"By design" (L-022).** F-F-014 says the Op record omits the model id by a recorded choice. It does not say that the model of a work package goes unrecorded by design.
- **"Released services ... 53 of 53" (L-025).** The count holds for the read service only.
- **"Found by a person" (L-010).** Some of the 17 detections name agent review squads, which the source text cannot tell apart from people.
- **"Missing" for operations the brief proposes (L-032).** `open-human-decisions.md` B6 drops the matrix's caveat that no record asks for these operations.

Notes cover softer wording: "4 in force by merge" against the finding's "may be in force" (L-026); a universal "did not exist before" (L-027); "doc-kitty builds every repository's site" (L-028); G1's 593 rule breaks with 36 of its 656 hits coming from a rule coded the wrong way round (L-029); a name search at low confidence presented as "no counterpart" (L-030); "corroborated by absence" (L-031).

Most of the documents are careful. In `assurance-gaps.md`, `coupling-and-deterioration.md` and `dependency-models.md` I found almost no causal verb on correlational evidence. Each says what its numbers do not show, keeps cause apart from deterioration, and marks inference. `hypothesis-assessment.md` quotes its criteria before each verdict. The strength problems sit mostly in the S-C documents, where findings are summarised a second time, and in short summary lines.

## 3. Consistency

**Major: two independence matrices (L-001).** `hypothesis-assessment.md` (S-A) and `independence-and-contracts.md` (S-B) present the M04 matrix with different values for the same cells. The cells are charter activation logical (E contested, against partly), work-package state machine logical (N, against partly disputed), doc-kitty source (NA, against established, static only) and charter activation distribution and deployment ("N (silent)", against "not claimed"). The claimed-cell counts also differ: 34 present claims with 9 established in S-A, 43 declared cells with 10 established in S-B. S-A says it adopted the investigators' values unchanged, and S-B departs from them on purpose. Each document is coherent alone. Neither says that the other exists, and the H04 verdict is stated on S-A's values.

Minor arithmetic and identity mismatches:

| Item | Mismatch |
|---|---|
| L-003 | Monthly decision counts "excluding v0.11" sum to 521, the total that includes v0.11 (465 without) |
| L-004 | "14 entries ... 9, 4, 2" sums to 15 |
| L-005 | "15 cross-repository check relations" are enumerated as 14, here and in F-E1-008 |
| L-006 | 9 against 10 input items for F-D2-008 |
| L-007 | Pin lag range ends at 4,369 while another document lists 5,111 |
| L-008 | Pin graph: "depended on by the other four" against a table with one edge into doc-kitty |
| L-009 | "Holds at load time" against 1 load-time edge |
| L-010 | 15 against 17 defects that reached `main` |
| L-016 | "Run 2, with agent-guidance files", although run 1 had them too |

Notes record two citations that point at the wrong finding (L-011, L-012), the edge count 400 against 464 or 465 (L-013), a table "in date order" that is out of order (L-014), and three rulesets against the two on `main` (L-015).

Every finding id cited in the passages I checked exists. Verdict words agree between `hypothesis-assessment.md`, the phase-1 files, `quality-attributes-invariants-scenarios.md` and `open-human-decisions.md`.

## 4. Views

The view labels are mostly present and match the evidence kind. Every document opens with a view convention, and statements resting on document-claims are labelled recorded-intent. Departures:

- **L-033, minor.** `deviation-catalogue.md` puts A4.3 and A4.4 ("record against record") in Part A. Part A requires an observation of code, build or history, and both sides of these rows are document-claims.
- **L-034, minor.** Part D, meant for conflicts with the design brief's proposals (R4), holds core ADRs whose status field is Proposed. Those are recorded-intent with an open status, so "proposal" is used in two senses.
- **L-035, note.** Part D also lists the absence of a record ("No record forbids ...") in its "Recorded decision" column.
- **L-036, note.** An `open-human-decisions.md` row cites F-D1-020 for an observation that comes from that record's disconfirmation field, not from its claim.
- **L-037, note.** A count of the investigators' own tags is given as the "Source" of a quality attribute.
- **L-038, note.** An execution-matrix row is "delegated by record" on the strength of a documentation answer (F-H06a-015). The ADR behind it (2026-10-13-2) should be cited instead.

## 5. Sample of decisive claims

I read 67 of 67 decisive records: claim, evidence kinds, scope and disconfirmation. For 59 of 67 the claim says what its evidence entries carry, with scope and denominator. Claims are specific and bounded, rates carry denominators, executed and static evidence is kept apart, purposive cases are labelled, and limits sit in `not_covered`. Exploratory and interpretation records were not among the decisive rows I flagged.

| Records | Problem | Grade |
|---|---|---|
| F-C-018, F-C-019, F-C-020, F-C-021 | `scope.covered` repeats the M01 boilerplate (2026-01-01 on, code commits). The claims' frame is fix-subject commits on the converged line from 2026-09-07 (L-050 to L-053) | minor |
| F-F-001 | "Stopping is held nowhere" is unbounded. The supporting record (F-F-012) limits it to the repositories read, and "missing 2" counts responsibilities that no record places (L-055) | minor |
| F-H06b-013 | "Correct against code 12/20" does not say that correctness was judged against questions the checker inferred (L-057) | minor |
| F-C-019 | "A person" includes agent review squads (L-054) | note |
| F-D1-025 | "Latest supported agent" for a tool (L-056) | note |

The eight rows cover seven records (F-C-019 has two rows): 6 minor, 2 notes. No decisive record says more than its evidence supports in a way that would change a measure value.

## Limits

- The review covers wording only. I did not re-run measurements, so a number that agrees across documents but is wrong in its source would not show up here.
- I read the full text of the cited records only where a sentence was in question, plus the 67 sampled records. I did not read other non-decisive records.
- `S-A-phase1.md` was read in part.
- Terms were checked against core's glossary only. The events and charter glossaries were not opened.
