---
doc_status: draft
updated: '2026-11-28'
---

# Rebuttal B

Role B, profile `reviewer-renata`. I read `position-A.md` after `position-B.md` was filed and did not read `rebuttal-A.md`. Nothing was re-run; I opened `evidence/B1/series.csv` (header) and F-B1-013 for point 2. Position A conceded more than I expected (H01, H02, H04, H05, H07, the enforced tier, the brief's full scope). The disagreement left is narrower than the roles suggest; I do not widen it.

## 1. The three strongest points of A

### 1.1 "The existing gates did not report them and nothing in the gate inventory is built to" (A, section 3)

I conceded the facts (my section 6, items 1, 3, 4). I dispute "nothing is built to".

- The compatibility checks exist and are built to compare; they lack a baseline, and print that they do (F-E3-013, F-E3-015). The example checker detects a mutation and is invoked by nowhere (F-E3-014). The conformance suite exists and is run by no workflow (F-E1-012). The harness check exists and is skipped on forks (F-E1-010). The orchestrator API has a version ledger with 31 entries and a stated rule; one removal was not entered (F-F-007).
- So for five of A's items the check or the rule is present and not wired, not fed or not followed. That is a different condition from "no place holds the knowledge". The owning repository holds it.
- PX-01 is the exception: no check exists. A concedes that a register catching it "is conjecture". An executed walk through a mission type would catch it; a record of intent would not (inference).
- A calls this a class, "shown by 14 uncovered entries from a partial trace, not by a rate". I agree it is not a rate. Without one, "class" and "list of items" cannot be told apart on this evidence. Whether the items were already known was not checked against the trackers (`open-human-decisions.md`, section E).

### 1.2 "The one structural measure that moved after the convergence moved where the assurance has no model" (A, section 4, H03)

This is A's best argument and I cannot dismiss the density rise (my concession 7). The location is not in evidence.

- M01a counts cross-component edges over all components of core. `evidence/B1/series.csv` carries one value per revision and no split by top-level package; the component edge table exists for `head` only. No finding I read places the 21.7% rise, or the 14.2% granularity-free rise, inside `specify_cli`. That it sits there is plausible from size (77.6% of lines, F-B1-013) and is conjecture.
- "No model to compare against" is measured against the layer gate. `assurance-gaps.md` section 2.1 says door rules for charter activation, the charter offering and status live in other gate files, and that those files "were not inventoried rule by rule". 135 of 310 gate files are classed as boundary gates (F-E1-001). The 90.7% figure is a lower bound on what is modelled.

We agree that decision F3 settles what H03 means.

### 1.3 "The gaps are between repositories. No single repository's gate can hold a cross-repository view" (A, section 5)

- 15 cross-repository check relations exist, each held by one repository's gate through a pin (F-E1-008). Single repositories do hold cross-repository views. What the evidence shows is lag (F-E1-009, untested for effect except F-D1-021) and one absent relation that waits on an approved plan.
- F-D1-021 (0 of 19 packs at open-packs head) is by recorded intent of open-packs (F-A1-015). It is a contradiction between records for the architect (decision C5), not something a gate missed.
- I accept one thing from this point. A decision index across six record homes (K1) and a pin view (K3) have no natural owner among the five repositories, and shape D alone leaves them open, as `knowledge-model.md` says itself. I had offered them as optional. A's 521 records, 6 of 10 supersession chains crossing repositories and 8 pairwise precedence statements (F-A1-026, F-A1-027, F-A1-003) are document-claims, but they are enough to say the need is observed, not optional.

## 2. What I withdraw or narrow

| My point | Now |
|---|---|
| "Too large" (section 5) | **Withdrawn against A.** A dropped shape C and the prose views. It stands against the brief's initial scope only |
| "Aimed at the wrong problem": a knowledge repository "describes these gaps; it stops none of them" | **Narrowed.** A register of rule-to-check bindings could report a check that is named and run nowhere, or a compatibility check with no baseline, if it is kept true. It would reveal, not stop. I keep the point for PX-01 and for anything behavioural |
| K1 and K3 as optional (section 5, last bullet) | **Narrowed.** The cross-repository need for K1 and K3 is observed. Where they live is open |
| "Recorded governance and existing gates are doing their job" (section 2 heading) | **Narrowed** to: rules written as gates over import structure hold. A check that reports green without comparing is not doing its job, in two repositories |
| H06 limits | **Narrowed.** A is right that "fails on any stale page" describes fragmentation and is not only an artefact. The selection of questions remains a limit |

## 3. Disagreements that remain

| # | Question | A | B | What would settle it | Kind |
|---|---|---|---|---|---|
| 1 | Are the uncaught departures a class or a list | A class, from 14 entries | A list of checks present but not wired, plus PX-01 | The 14 entries of part A3 and section E checked against the trackers; the 77 untraced rules of E1's frames traced; per entry, whether a rule or check already existed in the owning repository | Evidence |
| 2 | Did density rise where no model exists | Yes, inside `specify_cli` | Not located | M01a between the merge result and head split by top-level package; an inventory of the rules in the non-layer gate files | Evidence |
| 3 | Does the practical weight of H06 hold | Partly correct documents lead agents to off changes | A's own word is conjecture; 0 of 20 answers were incorrect | A second question set by an author who has not read core's guidance file; a sample of defects on `main` traced to a documentation cause | Evidence |
| 4 | A new repository (shape B) or an existing place (shape A) on top of shape D | B | D first; A or B undecided, K1 and K3 only | The four tables regenerated at a second date, with the hand corrections counted, to give an upkeep cost; rulings B5 and C1 | Evidence, then choice |
| 5 | Does K4 (invariants, exceptions, bindings) belong centrally | Yes, the brief's traceability chain | Not shown: G1 was never re-run with the ledgers as data, and exception fields differ by recorded rule per repository (F-E1-024) | That re-run (A lists it too); ruling B7 | Evidence, then choice |
| 6 | Order of work | Design shape B now | Rulings A1 to A6, F2, F3 first; they cost nothing and each moves a verdict | None; a matter of sequence | Architect's choice |
| 7 | Unowned responsibilities (supervision, cancellation, attachment) | A gap in recorded intent, a matter for a knowledge repository | A gap in recorded intent that one decision record closes (B6) | None | Architect's choice |

## 4. Counterevidence I could not answer

- 0 of 6 incompatible-contract mutations caught by a compatibility check, and a verb removed inside one contract version with consumers still naming it (F-E3-015, F-F-007, F-F-008).
- 0 of 60 sampled exception entries carry all four fields; no ruleset requires an approval (F-E1-025, F-E1-004).
- No ecosystem-wide precedence among records (F-A1-003).
