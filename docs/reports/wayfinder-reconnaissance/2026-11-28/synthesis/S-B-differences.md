---
doc_status: draft
updated: '2026-11-28'
---

# S-B differences: my phase-1 reading against the investigators' readings

Synthesiser S-B. Phase 1 is [S-B-phase1.md](S-B-phase1.md), written before `findings/`, `workstream-reports/` and `synthesis/sealed/` were opened. In phase 2 I read the 15 interpretation records of A1, A2, B1, B2, B3, D1, D2, E1 and F, the confidence fields of seven findings, and the workstream reports of A1, A2, B1, B2, B3, D1, D2 and F in full. I searched the reports of G2, H06b and E1 for my subjects and did not read them whole. I did not read the reports or interpretation records of C, C2, CX, E2, E3, G1 or H06a; they bear on other synthesis documents.

## 1. Where the readings differ

| # | Subject | Investigator's reading | My phase-1 reading | Kept | Why |
|---|---|---|---|---|---|
| 1 | Charter activation, logical cell | D1: established (F-D1-031), from 1 literal outside the owner and no I/O | partly | Mine, with D1's value shown | D1's disconfirmation search looked inside core only. D2's row for the served form is "not established" (F-D2-021) and A1 reads three authority statements (F-A1-038). The dimension asks for one named owner; inside core there is one, across the records there is not |
| 2 | Work-package state machine, logical cell | D1: not established, "two definitions in two repositories" | partly | Mine, marked disputed | D1 counts definitions. I count named owners: core's file is the stated origin, and the mirrors declare and test that. D1's reading is defensible; the cell says "disputed" and both values are in the CSV. A reviewer may prefer D1's |
| 3 | doc-kitty, source cell | D1: not assessable (not measured) | established, static only | Mine | B2 measured it (F-B2-019, F-B2-021). D1 did not see B2's output. The cell is labelled static-derived |
| 4 | Cells where a record declines the dimension | D1: "not established" (charter activation and offering distribution and deployment; mission state machine deployment) | not claimed | Mine | My brief defines this. D1 was told not to fill a declared column, so it could not make the distinction. D1's observed value stays in the CSV |
| 5 | Library and document deployment cells | D1: "not established (library; by design)"; D2: "not assessable" | not applicable | Mine | Same observation, clearer label; nothing is lost |
| 6 | M07a verified share | F: 12 of 14 (F-F-001) | 11 of 11 by the artefact's own "record places it" column; both to be shown | Both, plus a third from the split rows | F states its single-locus rule as a deviation and its figure follows from it. The pre-registration's wording supports the stricter denominator. Neither is wrong; the choice belongs to the verdict |
| 7 | M07a, meaning of "verified" | F: verified for 12 rows | verified part is narrower than the row name in five rows | Mine, as a qualification | F says the same in its exploratory notes and in deviation 3; it did not split the rows because its rubric asked for one state per row |
| 8 | Dynamic import `charter.offering` to `glossary` | B1: recorded by the rule's docstring, so 0 unrecorded violations; G2: the one row in no ledger | both kept | Both | They disagree on what "recorded" means for M03a. I do not choose |
| 9 | Core modules importing `spec_kitty_events` | B1: 27 modules; B2: 25 files; D1: 29 files for events and tracker | noted, not reconciled | All three | Different units. No workstream reconciled them and I did not recount |

## 2. Where the investigators were right and I changed my documents

| # | Change | Source |
|---|---|---|
| 1 | Charter service deployment: I had moved to "partly" while drafting, because the claimed CLI-spawned form is not enabled. D2's "established as a unit" answers the dimension's question (can it run as its own unit); I restored "established as a unit" and put the pending CLI-spawned form in the note | F-D2-021, F-D2-017 |
| 2 | The two lower layers: I had only the ledger counts. B1's interpretation, that `runtime` and `mission_runtime` are not below `specify_cli` in the import graph and the ledgers record that state, is carried into the dependency model as an adopted interpretation | F-B1-026 |
| 3 | Built-in pack: I had it as a difference between checkout and wheel. B1's framing, a load-time dependency of the Python package that the wheel satisfies by packaging, is carried into the packs row and the distribution table | F-B1-027 |
| 4 | Write counts on shared files: B1's own sample found 6 of 12 write-labelled sites to be writes at the path. The dependency model now calls the write counts upper bounds | B1 report, limits |
| 5 | Gaps at head for the Java services: D2 classifies them as staged work the repositories describe, with three items that have no recorded statement either way. I use that classification and name the three items | F-D2-022 |
| 6 | "By design" statements: D1 says they rest on text at head and were not traced to an ADR decision. Added as a limit | D1 report |
| 7 | Decision coverage: A1 deep-read 89 records (40 seeded, 49 purposive), not 40. The timeline's coverage table uses 89 | A1 report |
| 8 | Comparator for M07: my draft of the execution matrix said F chose the list. F's list is the fifteen examples in its brief. Corrected | dispatch/F.txt, F report |
| 9 | Orchestrator API version drift in a core ADR (1.10.0 against 1.31.0) added to the contract surfaces as a report-level note, since no finding was filed | H06b report |
| 10 | Charter repository `verifyAll` passing with no sibling checkout (16,177 tests) added beside D2's named tasks | F-G2-012 |

## 3. Where the readings agree

- A1's two interpretations (status fields do not tell what is in force; activation intent is not single-valued) match what I read from the chain file (F-A1-037, F-A1-038).
- B3's interpretation that granularity moves M03b more than any rule choice matches my reading of `m03b-summary.json` (F-B3-013).
- D2's summary, separate build, release and process together with shared formats and a second implementation in every row, matches my matrix: logical independence is established in none of its five rows (F-D2-021).
- F's record/act split matches the artefact (F-F-027). F's reading of the orchestrator API version as not signalling a verb removal matches F-F-007 and F-F-008 (F-F-028).

## 4. Confidence fields

The interpretation records I rely on carry "medium" (F-A1-037, F-A1-038, F-B1-026, F-B1-027, F-B2-034, F-B3-013, F-D1-031, F-D2-021, F-D2-022, F-F-027, F-F-028); F-B2-035 carries "low" and I do not rely on it. Of the observations I checked, F-F-001, F-D1-015 and F-D2-017 carry "high"; F-B1-010 and F-D1-024 carry "medium". F-B1-010 is medium because the pytestarch assertions did not run; my documents say so where the zero-violation count is used. F-A2-019 (outside-term mapping) is declared low confidence after a briefing gap; I use it only for the statement that eleven outside phrases occur in none of nine repositories.

## 5. Statements of mine that no finding carries

Marked in the documents as my own inference:

- that the architecture at open-packs head and the one core composes have separated (from F-D1-021, F-D1-023, F-A1-015);
- that a parallel unit of work which is not a work package had no native identity (from F-F-022, F-F-023; single case);
- the third share in the execution matrix, 12 of 13 over split rows;
- that the component catalogue needs two keys per row, the recorded name and the observed unit (from F-B3-007).

## 6. Synthesis-run checks

| Check | Result |
|---|---|
| `ls pins/ packs/` in the working tree | `pins/` holds `README.md` and `read-service.source.yaml`; agrees with F-D1-001 |
| ADR `2026-06-02-1`, line 23 | says the Pi invoker belongs in the external orchestrator package; agrees with F-F-005. The ADR's subject is Pi skill-only support |
| ADR `2026-10-07-2`, line 29 | says the Python transport's delivery profile maps the proposed `spec-kitty.orchestrator/2` semantics; agrees with F-F-006 |

No test, build or download was run.
