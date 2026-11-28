---
doc_status: draft
updated: '2026-11-28'
---

# Reproduction review R3: workstreams E1, E2, E3, G1, G2, H06b

Reviewer R3, profile `analyst-annie`, charter context for the action `review` loaded. The profile's handoff to implementers is not used; the envelope wins. I authored none of the reviewed work.

For every sampled finding I opened the card and the raw artefacts first, wrote my own claim in `logs-R3/own-claims.txt`, and only then opened the finding record. Per-finding results are in `repro-R3-results.csv`.

## 1. Reproduction rate

Sample: 59 findings (31 decisive, 28 seeded). Recorded SHA-256 matched for 145 of 145 evidence files named on the 59 cards.

| Workstream | Decisive: reproduced | Decisive: with difference | Decisive: wider than evidence | Seeded: reproduced | Seeded: with difference |
|---|---|---|---|---|---|
| E1 | 5 of 7 | 2 of 7 | 0 | 6 of 6 | 0 |
| E2 | none sampled | | | 4 of 5 | 1 of 5 |
| E3 | 2 of 3 | 0 | 1 of 3 | 5 of 5 | 0 |
| G1 | 10 of 10 | 0 | 0 | 2 of 2 | 0 |
| G2 | 10 of 10 | 0 | 0 | 5 of 5 | 0 |
| H06b | 1 of 1 | 0 | 0 | 5 of 5 | 0 |
| All | 28 of 31 | 2 of 31 | 1 of 31 | 27 of 28 | 1 of 28 |

Overall 55 of 59 reproduced, 3 of 59 reproduced with a difference, 1 of 59 claim wider than its evidence, 0 not reproduced, 0 blocked by the environment. A command or script was re-run for 52 of 59; the other 7 were recomputed from the raw artefact or re-derived from the repository at the stated revision.

What "reproduced" rests on, by workstream:

- **E1.** The ledger census script re-run on my own shared clones: 75 of 75 ledger rows equal on every count. Both seeded 30-entry samples redrawn: 30 of 30 and 30 of 30 rows. The 12-rule chain sample redrawn from its recorded frames: 6 of 6 and 6 of 6. PX-01 replayed in a disposable clone with the investigator's authored inputs: same block at `gathering`, same exit code, same two guard failures. Live rulesets re-queried read-only: equal.
- **E2.** Apply check re-run: 24 of 24 lines identical. Ambiguity counts re-run: byte-identical.
- **E3.** 16 of 24 mutations re-run in my own clones and environments: all of classes PI and RD except M-PI-4, plus M-IC-2, M-IC-5 and a seeded draw of 3 of the 7 remaining core mutations (`random.Random(20261128)`: M-OB-4, M-OB-1, M-IC-4). 16 of 16 gave the recorded verdict. Not re-run: M-PI-4, M-OB-2, M-OB-3, M-OB-5, M-OB-6, M-IC-1, M-IC-3, M-IC-6.
- **G1.** Both walk scripts re-run on fresh archives of core head, the charter head, the charter baseline tag and a fresh download of the rc8 wheel: 19 of 19 detail files byte-identical. The core build check re-run in both arrangements.
- **G2.** The four check scripts re-run: three result files equal as JSON, and both full tables kept in scratch have the recorded hashes.
- **H06b.** The code-checks script re-run: 401 of 401 lines identical. Counts recomputed from the check tables.

## 2. Findings that differ or are wider than their evidence

### F-E3-006 (decisive): claim wider than evidence

- Investigator: "Overall: 16 of 24 mutations detected (16 of 23 assessable); 15 by a gate per-change CI selects for the diff ... 7 not detected". Counterevidence: empty.
- Reviewer: the counts are right for what was run, which is the frozen gate set: 66 of 310 core architectural test files, lint, types and mirror tests. The claim sentence drops that qualifier. The same workstream's exploratory records show that all 4 core mutations among the 7 "not detected" fail a battery gate outside the frozen set (the dead-symbol gate for 4, the path-literal gate for 1), and its own `gate-selection.json` records that per-change CI selects the whole battery for each core diff. I reproduced the dead-symbol failure for 3 of the 4.
- Both values: against the frozen set, 16 of 23 detected and 7 not. Against per-change CI as far as executed evidence goes, 20 of 23 are flagged by some check (core 15 of 15), 16 of them by a failure that names the violation, and 3 of 23 are unflagged (M-PI-6, M-RD-4, M-IC-2, none in core).
- Caution in the other direction: the dead-symbol failures come from the way the patches were written (an added function that nothing calls), not from a guard on the violated rule. They do not show that the rule is protected.

F-E3-002 keeps the words "by the frozen gate set" and reproduces; its counterevidence field is also empty although M-PI-3 and M-PI-5 fail the dead-symbol gate.

### F-E1-018 (decisive): reproduced with difference

- All file-ledger figures equal mine (27 existing ledgers 3,261 to 2,530; 30 created in range holding 827).
- Difference: "Marker scans excluding noqa went from 247 to 429". The start total covers 14 scans, the end total 17: three charter scans (61 markers) have no start value. Comparable figure: 247 to 368.
- For the reader of M05b: the share of file ledgers that are flat or shrinking is 38 of 57 (66.7%) when ledgers created in the range count as growing, and 24 of 27 (88.9%) among ledgers that existed at the start. Both follow from `ledgers.csv`; the finding gives the second split only.

### F-E1-025 (decisive): reproduced with difference

- Sample draws and all tallies equal, except partial retirement conditions in the secondary sample: finding 4, CSV 6 when entry and ledger level are combined (4 at ledger level only).
- The secondary sample reproduces only with a fresh generator, while the chain sample of the same workstream uses one generator across two frames. Neither convention is stated.

### F-E2-001 (seeded): reproduced with difference

- Finding and report: "22 of 24 patches touch one file". Evidence (`apply-check.txt` and the patches): 23 of 24.

## 3. Evidence-kind labels

- F-E1-029 (E2) and F-E1-033 (E2) label source code read at a revision as `document-claim` while supporting an `observed` claim. `static-derived` is the fitting kind. The values are unaffected; 2 of 59 sampled findings.

## 4. Deviations the workstreams did not declare

**E1**

- The committed `rulesets-live-2026-11-28.json` lists 14 rulesets because the core block repeats 4 rulesets of other repositories; live there are 10. Required contexts are unaffected.
- The marker-scan totals mix scans with and without a start value (section 2).
- Scope of F-E1-032 says 6 acceptance modules; the directory has 9 at head. A negative invariant of method `custom_command` runs a Mission-authored command, so a Mission can add any check; the record states only that invariants "could name any path". The 0 of 13 holds for built-in checks.
- The full entry file from my census re-run has a different hash from the one in the manifest. The manifest's file is not committed, so the cause cannot be established; all 75 aggregated rows agree.

**E2**

- 11 of 15 core patches add a function that nothing calls (E3's count). This makes those patches visible to an unrelated gate and confounds a detection measure. E2 could not know it under its blindness rule; neither report lists it as a property of the mutation set that limits what detection means.

**E3**

- Declared: batching, worker count, 66-file set, exploratory runs. Not declared: the headline tier "not detected by the frozen set: 7 of 24" is reported in the measures table beside "gate per-change CI selects: 15 of 24" as if the two were tiers of one scale, while 4 of the 7 fail a per-change gate.
- `--tests *HexagonalArchitectureTest` ran 1,656 tests in the charter build, in my run and in the investigator's log; the filter did not restrict the task to the 99 tests of that class. No effect on the verdicts.
- The investigator has no single-mutation run of the architectural set for 8 batch members with a detection (declared). I ran 6 of them alone against the named gate (M-PI-2, M-RD-1, 2, 3, 5, M-OB-1): each fails it, baseline green. M-OB-3 and M-OB-6 were not re-run.

**G1**

- The pre-registration gives the first agent "only public contracts, schemas and package metadata". G1 also read two architecture documents and the agent guidance file loaded with its session, which names seams, state files and owners. The report says so under its constraint section, not under deviations. Rules R2 and R3 of its I2 check come from that guidance text.
- The third named core gate, which G1 could not finish, passed for me alone at head: `test_layer_rules.py`, 80 passed.

**G2**

- None found. Its I6 gate run reports 2 failures of 129; the record attributes them to the copy without the pack tree, and my baseline of the same file in a synced clone (80 passed) agrees.

**H06b**

- None beyond the declared one (questions inferred from answers). The 20 question texts are fixed in the pre-registration; for the 5 sampled per-question findings the inferred subject fits the pre-registered question in 5 of 5.
- Same file, two counts: H06b reports an issue number on 9 of 30 baseline leaves, E1 on 18 of 30, because E1 also reads the comment block above each leaf. Owner is 5 of 30 in both.

## 5. Disconfirmation searches

Every sampled finding carries a search. My own bounded searches for the opposite, on the decisive ones:

- **F-E1-029 (no producer of the guard's event).** No producer in core `src/`, nor in the orchestrator, MCP, fleet, container, charter, events or open-packs repositories; hits outside core are copies of mission text. After my replay the Mission event log held 5 rows, all of one other type.
- **F-E1-030.** With a copy of the register at the Mission root, the artifact failure clears and only the event-count failure remains. This probe was outside the investigator's instructions; it is a reviewer check in a disposable clone, not a repair.
- **F-E1-032.** No read of another repository, pin or lockfile in the acceptance code; the `custom_command` path noted above is the only opening found.
- **F-E3-003 (M-RD-4 undetected).** The 5 events test files that parse source also pass with the mutation applied (288 passed).
- **F-G1-003.** `charter.offering.api` exists and has 0 importers in `specify_cli`; the count stands. Against the recorded baseline the same imports are 0 new (F-G2-003), so the two workstreams measure different things for I2 and do not contradict each other.
- **F-H06b-013.** 5 of 5 cited contradicting passages are present at head with the stated status.

## 6. What I could not check, and my own deviations

- Not re-run: the full charter `verifyAll` (45 minutes; F-G2-012 rests on its log), 8 of 24 mutations, the gate inventory script, the E2 import check as written (replaced by a parse check), the events Gradle build (not attempted; known blocked, coverage limit).
- Hand classifications were not redone: the 60 sampled ledger entries beyond a few rows, the H06b authority and contradiction columns beyond 5 passages, the G2 adjudication of write candidates.
- My trimmed log of the 66-file batch run shows the totals (1295 passed, 0 failed, 2 errors) but not the names of the 2 errors; I take them to be the 2 baseline set-up errors the investigator records, without proof.
- My wheel build for F-G1-011 ran while a mutation patch was applied in the same clone; the build outcome is unaffected, the wheel was used only for metadata.
- Load: the charter Gradle run (2 workers) overlapped with single-process pytest runs and once with a 2-worker pytest run. This is above the limit of 2 for about ten minutes.
- I read the pre-registration's measure sections for my workstreams and its headings, not every section.
- Path strings in two G1 summary files and key order differ between my re-run and the committed files; contents are equal.
