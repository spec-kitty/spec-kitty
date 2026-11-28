---
doc_status: draft
updated: '2026-11-28'
---

# Rebuttal A

Role A, profile `architect-alphonso`. `rebuttal-B.md` not read. Nothing re-run. `position-A.md` is unchanged. "(conjecture)" marks an argument without evidence.

## 1. Agreement reached without pressure

Written blind, the two papers agree that: H01 is near contradicted and H02, H04, H07 carry no weight for the design; the enforced tier holds (F-B1-010); H03 shows silence and waits on decision F3; H06 is robust; PX-01 is real and uncaught; contract compatibility is unchecked in two repositories (F-E3-015); Mission acceptance reads nothing beyond its repository (F-E1-032); shape C is not warranted; publishing local models and ledgers (F2) is what the H08 evidence names (F-G2-015).

## 2. B's three strongest points

### 2.1 "The executed gaps are local; a repository without acceptance authority stops none of them"

- Accepted: 5 of the 6 rows in B's table sit in one repository's own gate set and need local responses. A register stops nothing by itself; decision F4 is open.
- Not accepted: that the table is the whole list. It leaves out departures with no owning repository:
  - the orchestrator API verb removed with the contract version unchanged, with 2 of 3 consumers in other repositories still naming it (F-F-007, F-F-008);
  - 10 formats defined on each side of a service boundary with no single source (F-D2-010); 7 of 8 pack-artifact schema pairs differing between core and the charter repository (F-B2-031);
  - no ecosystem-wide precedence among 521 decision records in six repositories (F-A1-003, F-A1-026);
  - four consumers pinning four open-packs commits (F-D1-002).
- B answers the pack case (0 of 19 at open-packs head, F-D1-021) by saying open-packs ended compatibility on purpose. The core charter says the opposite (F-A1-015). A deliberate decision in one repository that contradicts a standing record in another is the cross-repository case.

The point narrows my claim. The residue lies between repositories, where no local gate can hold the view (inference).

### 2.2 "Against per-change CI, 20 of 23 mutations are flagged, core 15 of 15; M02 sees misses, not catches"

- The figure is right and I underused it (`repro-R3.md`, on F-E3-006).
- Its weight is less than B gives it. 4 of the extra core detections are the dead-symbol gate reacting to an uncalled function, which R3 says does "not show that the rule is protected". On failures that name the violation the count stays 16 of 23. For M-PI-3, M-PI-5 and M-OB-4 no gate on the rule itself was observed (F-E3-007, F-E3-008, F-E3-012).
- On M02 I agree: the frame sees misses. 13 of 30 corrected in the same pull request is a catch I did not credit (F-C-019, F-C2-018). The other figure stands: all 15 that reached `main` in C's sample were found by a person or a review squad.
- None of this bears on PX-01, the vacuous compatibility checks or the verb removal, where a rule had no gate or the gate compared nothing.

### 2.3 "Premature: untested, upkeep cost unknown, rulings come first, and a precedent that binds nothing"

- Accepted in full: nothing about Wayfinder was tested; the cost of keeping a register true is unknown; rulings A1 to A6, B5 and C1 precede any design; planning's 56-record target architecture is a precedent of a documentation-first source that binds nothing (F-A1-036).
- B then offers, as the smaller response, "shape A or B limited to K1 and K3, generated from record headers and pin files", plus shape D. In `position-A.md`, section 6, I argued for shape B resting on shape D. The remaining gap between the two papers on what to build is therefore K2 and K4, and whether the index lives in a new repository or an existing one.
- "None of these needs a new normative source" is true and not what I claimed: a generated index is not normative. Whether it needs its own repository the evidence does not say.

## 3. What I withdraw or narrow

| Point in `position-A.md` | Now |
|---|---|
| Section 1, "inside `specify_cli`" as a place where the ecosystem "departs from its own records" | **Withdrawn** as a departure. With no record there is nothing to depart from. It stays as an unmodelled area, pending F3 |
| Section 3, "14 such entries" as the size of the uncaught class | **Narrowed.** B's split (6 on behaviour, 8 on record keeping, one reader) is fair, and nobody checked the trackers. "No exception found" is an upper bound on "unknown".  |
| Section 3.3, core against the charter service has no check | **Withdrawn** as a gap. It sits on a pending approved plan (F-E1-008 counterevidence; ruling R4) |
| Section 3.3, the pack case as an uncaught departure | **Narrowed** to a contradiction between two repositories' records with an executed consequence |
| Section 4, H03 and the 21.7% rise | **Narrowed.** I keep that density rose after the convergence where no model exists (B concedes it). I drop any suggestion that a model would have bounded it (conjecture) |
| Section 5, "a repository is warranted" | **Narrowed** to: a generated cross-repository index (K1, K3) and published local models and ledgers are warranted by several independent observations. Whether that is a new repository is open. K2 and K4 are warranted only after F2 and F3 |
| Section 5, the exception-field row | **Narrowed.** The 231-pair baseline is exact and names issue, owner and drain target (F-G2-003, F-E1-022). The gap is 2 of 24 leaves with all three fields, not absence of governance |

I keep sections 3.1, 3.2, 3.4 and 3.5, the H06 argument, and the H08 reading.

## 4. Disagreements that remain

| # | Question | A | B | What would settle it |
|---|---|---|---|---|
| 1 | Is there a class of departure that only a cross-repository view can see? | Yes: the verb removal, duplicated formats, precedence, divergent pins | The executed gaps each sit in one repository | Evidence: trace each of the 10 duplicated formats (F-D2-010) and the 33 pin surfaces for a defect that reached a release. Then the architect's reading |
| 2 | Does H06 describe a cost or only a property of a large corpus? | A cost, since agents act on these documents (conjecture as to rate) | Limited weight; measures documents, not architecture | Evidence: a second question set by someone who has not read core's guidance file; the contradiction search restricted to authoritative sources; a trace from a partly correct answer to a change |
| 3 | Were the A3 entries unknown to the maintainers? | Not shown either way | Upper bound on unknown | Evidence: a tracker check for the entries of section E of `open-human-decisions.md` |
| 4 | Do core's gates guard the rules or the patch shape? | 16 of 23 by a failure naming the violation | 20 of 23 flagged | Evidence: decision D4, re-run with patches that add no uncalled function |
| 5 | Is the silence inside `specify_cli` chosen? | Unknown; it matters because 77.6% of lines sit there | May be chosen, since the enforced pair is the authority | The architect's ruling (F3). Not a matter of evidence |
| 6 | Index in a new repository, an existing one, or none | Shape B on D | D first; A or B limited to K1 and K3 if wanted | The architect's choice (F1), after C1 and B5. The upkeep cost is evidence nobody has |

## 5. What neither paper could answer

- Whether any of this has harmed a user of a released version.
- What drives import density after the convergence (M01f did not replicate).
- The outside observer's predictions, not yet returned.
