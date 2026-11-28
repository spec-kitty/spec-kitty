---
doc_status: draft
updated: '2026-11-28'
---

# Reproduction review R1: workstreams A1, A2, F, CX, C, C2, H06a

Reviewer R1, profile `reviewer-renata`. Directives applied: DIRECTIVE_003, DIRECTIVE_032, NO_FULL_HEAVY_SUITES_IN_MISSION; no conflict with the envelope. Tools: git 2.43.0, Python 3.13, the core virtualenv (Python 3.11.15, pytest 9.0.3). Row-level results are in `repro-R1-results.csv`; raw output is in `logs-R1/`.

## Method

For each of the 55 sampled findings I read the card, checked the recorded hashes, read or recomputed the artefacts, wrote my own claim, and only then opened the finding record. Where the investigator's scripts needed scratch inputs that were not shipped (C, C2), I re-derived the figures from the repository at the stated revision with my own script (`logs-R1/script-own-c.txt`, `script-own-m02.txt`) and did not present that as a re-run of theirs. The column `command_rerun` says yes when I executed the stated method or an equivalent command against the stated revision; the notes say which.

One procedural slip: a grep over evidence files also matched two finding files (F-A2-008, F-A2-012) and showed one line of each before my claim for them was written. Both rows carry a note.

## Reproduction rate

| Set | n | Reproduced | Reproduced with difference | Claim wider than evidence | View or kind mislabelled | Not reproduced | Could not reproduce |
|---|---|---|---|---|---|---|---|
| Decisive | 15 | 13 (86.7%) | 0 | 2 | 0 | 0 | 0 |
| Seeded | 40 | 32 (80.0%) | 6 | 1 | 1 | 0 | 0 |
| All | 55 | 45 (81.8%) | 6 | 3 | 1 | 0 | 0 |

| Workstream | Decisive: reproduced of n | Seeded: reproduced of n | Other outcomes |
|---|---|---|---|
| A1 | 1 of 1 | 8 of 8 | none |
| A2 | none sampled | 1 of 5 | 3 with difference, 1 mislabelled |
| C | 5 of 5 | 5 of 6 | 1 with difference |
| C2 | 4 of 4 | 6 of 6 | none (one disconfirmation result is wrong, see below) |
| CX | 2 of 2 | 3 of 5 | 1 with difference, 1 wider than evidence |
| F | 1 of 3 | 5 of 5 | 2 decisive wider than evidence |
| H06a | none sampled | 4 of 5 | 1 with difference |

Hashes: all 98 file-backed evidence items in my sample match their recorded SHA-256 (`logs-R1/sha-check.txt`). All 17 document-claim items of A1 carry a whole-file hash that matches `git show` at the stated revision. The 8 document-claim items of A2 and H06a carry no hash. Every MANIFEST of the seven workstreams matches its files, with no unlisted file (`logs-R1/manifest-check.txt`).

No number in the decisive set failed to reproduce. The two decisive findings that fall short do so in wording beyond the numbers.

## Decisive findings that are wider than their evidence

**F-F-001 (M07a, execution responsibilities).** The counts equal the table: locus 11 / 2 / 2, state 12 verified / 1 delegated / 2 missing. Three points:

1. The brief asks for the share verified "among responsibilities that a record places inside the ecosystem". The table's own column marks 11 rows that way, which gives 11 of 11. The finding leads with 12 of 14 = 85.7%, a denominator of everything not delegated. That brings in X06, X07 and X13, which the table marks "no record places it". Both figures are in the claim; the report's deviation list does not name the change of denominator.
2. X08 (handover) is marked verified on `tests/status/test_actor_identity_reconciliation_4665.py`. That file tests same-agent claim reconciliation and that a different identity is refused. The workstream's own definition of X08 is transfer of an in-flight unit, and its table note says none exists. The disconfirmation states that every verified test was checked against its code path. With X08 as present but unverified the figures are 10 of 11 and 11 of 14.
I re-ran three of the fourteen batches in a scratch clone: 19, 76 and 31 tests pass (`logs-R1/F-rerun-batches.txt`). A fresh clone fails at collection with `BuiltInPackMissing` until the fetched pack tree is supplied; the method does not say so. All 42 named test files exist at head.

**F-F-017 (interruption knowledge).** Items 1 to 4 match the artefacts (1,182 core tests passed; 90 orchestrator tests passed; 9 of 10 end-to-end tests, the failure being an exact pin on contract 1.3.0 against 1.31.0). Item 5 says that beyond the shell PID "no holder records what it was doing", and the disconfirmation result is "None". My search found a surface it did not look at: `spec-kitty agent tasks mark-status` records per-subtask status in the Mission event log, and `spec-kitty-orchestrator` `loop.py:683-705` injects that call into the agent prompt (tested in `tests/test_subtask_tracking.py`). It is cooperative and coarse, but it records in-flight progress (`logs-R1/F-subtask-progress-surface.txt`).

## Decisive findings that reproduced, with what I checked

- **F-C-008, F-C-018 to F-C-021.** My own computation gives the share of code commits touching two or more components as T1 54.6% (517 of 947), T2 36.9% (668 of 1,809), T3 34.4% (1,040 of 3,026), against 54.2%, 37.4%, 34.3%. Fourteen of 15 monthly cells are within 2%; 2026-08 public is 45.4% against 47.5% under my simpler rename handling. The M02 frames (666 and 1,262 of 2,276) and both seeded samples of 30 reproduce exactly. The trace tallies re-tabulate. Detection route (c), "a person", includes agent review squads (the record says so in part).
- **F-C-021** carries one wrong limitation: its scope, and the report, say nine of the 24 introducing changes are blame candidates only. The trace table has 16 of 24 (9 in M02a, 7 in M02b, three marked weak).
- **F-C2-010, F-C2-018 to F-C2-020.** Frames 698 and 1,264 of 2,553 and both samples reproduce exactly. C2's contract rule matches any `/contracts/` path, so 23 of 698 frame members (3.3%) are there only for a file under `kitty-specs/<mission>/contracts/`.
- **F-CX-004, F-CX-008.** Re-running the two build scripts gives a byte-identical `comparison.csv`. On the six fixes both runs traced, detection coding agrees for five.
- **F-A1-029.** All per-dimension counts re-tabulate (200 cells: 89 claimed, 86 silent, 4 explicitly not pursued, 3 contested, 18 not applicable). Eight citations spot-checked are accurate. Two limits: the "silent" coding is not uniform (the migration-ledger row is silent on the logical dimension although its cited ADR calls the ledger "the single authority"), and "40 components named by the records" is not exhaustive (core ADRs name the end-to-end testing repository and Kitty Desktop; neither has a row).

## Seeded findings that did not reproduce cleanly

| Finding | Investigator's value | My value | Likely reason |
|---|---|---|---|
| F-C-012 | whole-tree difference of the convergence merge from the public parent: 3,179 files, +69,807/-349,905 | 3,205 files, +80,347/-360,445 with `--no-renames`, the method named for the src figures; 3,179 only with rename detection | two diff modes mixed in one sentence; the scope note's 348 cherry-pick commits is 320 by my count |
| F-CX-011 | "3,179 vs 3,179" listed as a replicated row | both entries are the rename-detecting count; the build script holds them as literals | not a comparison of two methods |
| F-CX-013 | detection gap in M02a (22 vs 16 of 30) attributed to bucket definitions; "all other non-replicated rows trace to a definition" | the comparison table gives the cause as different samples (overlap 4); Fisher exact p = 0.18; on shared commits 5 of 6 agree | sampling variation is not separated from definition. The frames (666 vs 698, 4.7%) are also listed under "moved by more than 10%" |
| F-A2-002 | core src has 170 lines matching `harness` | 204 lines (`git grep -w`); 170 is a token count in the evidence file | unit mislabelled |
| F-A2-004 | 10 projection-named classes in 6 modules | 9 classes in 6 modules; the record itself lists 9 names | miscount |
| F-A2-008 | charter repository `docs/context/domain.md:107` and `:104` | the quoted text is at `:73` and `:70` at 06cdfbe | every `domain.md` line number in `drift.csv` that I checked is 34 too high |
| F-A2-012 | view observed, evidence static-derived; `domain.md:120` | `drift.csv` rows D07 and D08 are quotations of glossary text, a document-claim; the sentence is at `:86` | kind mislabelled; the record's scope says code was not checked |
| F-H06a-002 | 4 differing sources | 3 are listed in the answers file; a semicolon inside a parenthesis split one into two | parsing artefact; my search found two further differing passages in core (ADR 2026-10-01-2 body; ADR 2026-10-12-2:164) |

One reproduced finding has a disconfirmation result that is wrong in substance. **F-C2-015** asks whether one commit drives a class rate and answers "a handful of import-heavy small fixes". In the sample file one commit (365f1bb255, 115 files) supplies 75 of the 95 added edges of T1 corrective-maintenance; without it the rate is 3.0 per 1,000 changed lines, not 12.0.

## Disconfirmation searches

Every sampled record carries a disconfirmation entry. In my reading 9 of the 55 are not a search for the opposite or reached a result my own search contradicts: F-C-008 (a within-series comparison), F-C2-015, F-F-001, F-F-017, F-CX-013, F-A1-029 (the grep terms cannot find logical-ownership statements), F-A1-007 (see below), F-H06a-002 (two differing passages missed) and F-A2-012 (a note was looked for only in core).

On F-A1-007 the claim "no record found that ends the programme exception" holds for primary records. Core `AGENTS.md:682` at head (to which `CLAUDE.md` is a symbolic link) does describe the git-pin regime as historical. The A1 brief ranks that file as a secondary source.

## Undeclared deviations and delivery gaps

- **C.** The limit "nine of 24 are blame candidates" is wrong (16 of 24). Its scripts need scratch inputs; the regeneration command is given, as the common brief allows. All measures asked were delivered.
- **C2.** The M01f period rate is a pooled ratio over a sample that is not proportionally stratified (a floor of 10 per class). No weighted figure or interval is given; CX reports the effect. The allocation is described in the finding's scope and not in the report's deviations.
- **CX.** `samples-output.txt` prints "C2 agree 39" for rule against reading where the table and C2 say 38. The cause text says 80 commits differ in component count; the evidence file has 86 rows. The report is 1,597 words by `wc -w` against a cap of 1,500.
- **F.** The denominator change described above. The timestamp of the pre-registered list is self-recorded (declared).
- **A1.** None found in the sampled material.
- **A2.** Line numbers for the charter repository's `domain.md` are wrong at the stated revision. Evidence kinds for glossary quotations are labelled static-derived in at least F-A2-012.
- **H06a.** `script-discoverability.txt` counts differing sources by splitting on semicolons. Seven of 20 answers (Q2, Q4, Q6, Q7, Q8, Q14, Q18) contain items with unbalanced parentheses, so their per-question counts are upper bounds. The measure "questions with any differing source" (15 of 20) is not affected. The run-1 exposure to agent-guidance text is declared.

Sampling followed seed 20261128 and the stated frames wherever I could check: C M02a and M02b, C2 M02a and M02b, and the classification sample of 50 shared by C and C2.

## What I could not check

- Trace judgements in the M02 samples (who introduced a defect, how it was detected) are the analysts' readings. I spot-checked 8 of C's 60 rows and the 6 rows both runs traced; tracker lookups were not repeated.
- The import-edge extraction behind M01f was not re-run in either run; I re-tabulated the sample files only.
- Rule-based commit classes were not re-implemented.
- Eleven of F's fourteen test batches were not re-run (memory shared with other reviewers). The orchestrator end-to-end run and the timeout probe were not repeated.
- A1's catalogue, relationship table and authority map are hand-compiled; I checked citations by sample (8, plus the 17 passages of the seeded findings), not exhaustively.
