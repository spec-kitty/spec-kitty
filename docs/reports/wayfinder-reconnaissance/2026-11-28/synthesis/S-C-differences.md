---
doc_status: draft
updated: '2026-11-28'
---

# S-C differences: my phase-1 reading against the investigators' readings

Synthesis S-C. Phase 1 is `S-C-phase1.md`. In phase 2 I read the 21 interpretation records listed in `sealed/held-back-records.csv`, the confidence fields of all finding records, and the workstream reports (G1 and G2 in full; the exploratory sections of A1, A2, D2, E1 and F; the section lists of D1, E3 and H06b).

## 1. Where the readings agree

| Investigator's reading | Confidence | My phase-1 reading | Used in |
|---|---|---|---|
| F-A1-037: status and title alone do not tell which decision is in force | medium | Same (need 1 of phase 1) | K1, decision C6 |
| F-A1-038: activation has three incompatible authority statements | medium | Same | Decision B2 |
| F-B1-027: the built-in pack is a load-time dependency of the package | medium | Same, under testability | Attribute table |
| F-B2-035: three consumers of the packs contract differ in how they pin it; core's schema set has no pin | low | Same, as candidate I10 | I10, need N8 |
| F-B3-013: M03b depends on granularity; the records speak between packages, the weight lies inside one | medium | Same | Decision F3 |
| F-E1-034: an ungated rule reaches an agent as one id in a list of 50 | low | Same observation used (F-E1-015); I did not carry the "depends on the agent" clause, which nothing observed supports or refutes | Governance answer |
| F-E1-035: ledger growth is mostly new gates registering existing constructs | low | Same reading of F-E1-018 and F-E1-019 | Attribute table |
| F-F-028: the interface version does not signal a verb removal | medium | Same | I9, scenario QS-B |
| F-G2-015: 6 of 12 checks needed implementation-internal facts; baselines exist for 3 core checks and no Java check | medium | Same count. My explanation (section 2.1 below) goes one step further | Invariants file, section 2.1 |

## 2. Where they differ

### 2.1 What separates the contract-only from the implementation-aware checks

- **G2** (F-G2-015, medium): classifies each check by the knowledge it needed. It does not say why core and charter differ.
- **G1** (`workstream-reports/G1.md`): names, per invariant, what was missing: a readable baseline, a declared surface for four of six packages, the exception lists, the domain boundary inside `specify_cli`, the sanctioned writers per state.
- **Mine.** The split is not the language. It is whether the intended model and its exceptions are published where a reader without the test sources can see them. This is an inference over F-G1-001, F-G1-003, F-G1-005 and F-G2-015; neither investigator states it.
- **Kept: mine, marked as inference.** G1's own list supports it. Evidence against it, which I keep visible: charter has no enforced baseline either (F-G2-015), so the agreement in Java may come from charter having few exceptions, not from publishing them. I cannot separate the two with one Java subject.

### 2.2 G1's rule for the charter-offering door

- **G1** (F-G1-003, medium): 36 of 36 `specify_cli` imports of `charter.offering` avoid `charter.offering.api`; G1 notes it may have read the published sentence too broadly.
- **Mine.** The module's docstring says `specify_cli` must not import that module; the `charter.*` facades are the door (synthesis-run read, local checkout at `23ea4709af`, not `head`; agrees with F-D1-015 and F-B3-011). So 36 of G1's 656 rule hits come from a rule coded the wrong way round.
- **Kept: mine.** It does not change any count in the hypothesis assessment, which reports G1's number as G1 gave it. It is an example of 2.1, not a correction of the verdict.

### 2.3 F-B1-026: do the layers hold

- **B1** (medium): the two lower layers are not below `specify_cli` in the import graph; the ledgers record that state.
- **Mine, phase 1.** "Direction between the six packages is enforced and holds."
- **Changed.** "Holds" was too strong. The attribute table now says 0 unrecorded violations, gives the 228 ledgered upward imports, and carries B1's reading beside them. **The investigator was right** to put the weight on the ledgers.

### 2.4 F-C-032: per-commit spread

- **C** (medium): the fall in components per commit cannot be separated from a change in how work is cut into commits.
- **Mine, phase 1.** I took the fall from S-A's table without that qualification.
- **Changed.** Decision A1 now carries it.

### 2.5 F-A2-020: where terminology drift sits

- **A2** (medium): each glossary's precedence rule points at another repository; 9 of 22 drift rows lie on the core and charter boundary.
- **Mine, phase 1.** I had the drift (need 4) and not the precedence observation.
- **Changed.** Added to need N4 and decision C7. **The investigator was right.**

### 2.6 F-D2-022: what counts as a candidate for a tracker issue

- **D2** (medium): no observation in its workstream is a defect; most gaps are staged work the records call pending; three items have no record either way.
- **Mine.** Section E of the decisions file lists observations with executed or static evidence and no recorded exception. It includes two items from the Java repositories (an undetected contract change, an unwired checker) that come from E3, not D2.
- **Kept: both.** D2's three unclassified items are named in a sentence and left out of the table. The list is for the architect's decision and classifies nothing as a defect.

### 2.7 F-C-033: which sample to cite for detection

- **C** (low): for defects that reached `main`, 21 of 24 sampled were found by a person, across both frames.
- **Mine.** Decision F4 cites 15 of 30 from the cross-component frame alone (F-C-019), because that frame is the pre-registered one, and notes that the detection route is not replicated between C and C2.
- **Kept: mine.** C's pooled figure is an interpretation at low confidence.

### 2.8 F-F-027: the record and act line

- **F** (medium): core holds what records, prepares and gates; acting on a running process is outside core or nowhere.
- **Mine, phase 1.** Same facts, listed as separate observations.
- **Changed.** Decision B6 now states F's reading and cites it. It is the clearer formulation.

## 3. Verdicts

I do not change any verdict and I do not disagree with one under the criteria of section 6 of the pre-registration. Two remarks on what a verdict does not carry:

- **H08, inconclusive.** I agree. The criterion counts invariants "in both languages". The Java side is one repository, and its build-based check was lost for one of the two agents (F-G1-012). The result is thinner for Java than the table suggests.
- **H07, contradicted.** I agree on the criterion. The verified share compares counts of passing tests. It does not carry F's reading that every responsibility needing action on a running process is outside core, and two have no holder (F-F-027, F-F-012, F-F-024). Decision A6 puts the question of the denominator to the architect.

## 4. Confidence fields

Of the 186 finding ids cited in my three documents: 121 high, 63 medium, 2 low (script over `findings/`, synthesis-run).

- The two low ones are F-G1-009 (core I5 from public information: the check runs and gives no pass or fail) and F-G1-012 (charter I6: no verdict, environment). Both are cited for exactly that: a check that could not decide. The low confidence fits the use.
- Eight of the cited ids are interpretation records, all medium: F-A1-037, F-A1-038, F-A2-020, F-B1-026, F-C-032, F-D2-021, F-D2-022, F-F-027. Each is labelled "interpretation" where it is cited.
- The coordinator declares A2's outside-term mapping low confidence. Element K5 says it rests on that workstream alone.

## 5. Statements of mine that no finding carries

Marked "(inference)" in the documents:

- The published-model explanation of H08 (2.1 above).
- The local against ecosystem split of checks (`knowledge-model.md`, section 2).
- The reading that the observations argue against any element that restates what a repository owns.
- The three desk points on AS-10.
- Candidates I10 and I12, and scenarios QS-A to QS-E.
- That `full_go_conformance: false` refers to the unattached repository.

## 6. Synthesis-run checks

| Check | Result |
|---|---|
| Read `src/charter/offering/api.py` docstring; grep for importers of the module under `src/` | Importers only inside `src/charter` (10 files). Local checkout `23ea4709af`, not `head` |
| Count of `quality_attributes` tags and `confidence` values over `findings/` | 42 uses of "consistency" or "discoverability"; 248 high, 146 medium, 20 low over 414 records |
| Confidence of the ids cited in my documents | 121 high, 63 medium, 2 low, of 186 |

No other command was run. No test, build or gate was executed by this synthesis.

## 7. What I did not do

- I did not re-run any G1 or G2 check, or open every per-row CSV behind them.
- I read C, C2 and CX claims in shortened form and rely on S-A's tables for H01 and H02.
- I did not open `review/`.
- I did not check any listed observation against the issue trackers.
