---
doc_status: draft
updated: '2026-11-28'
---

# S-A phase 1: evidence-first reading

Written by the synthesiser (profile `synthesizer-sam`) before opening `findings/`, `workstream-reports/` or `synthesis/sealed/`.
Inputs: `synthesis/input/observations-index.csv` (393 observation records), and the raw artefacts named below.
Verdicts use the criteria of section 6 of the pre-registration only. They may change in phase 2; changes are logged in `S-A-differences.md`.

Profile boundaries applied: synthesise through new artefacts only, do not edit other agents' outputs, no inflation. The profile's default output folder (`synthesizer/`) is overridden by the envelope (`synthesis/`).

Artefacts opened in this phase: `evidence/B1/series.csv`; `evidence/C/m01c-m01d-components-per-commit.csv`; `evidence/C/m02-trace-sample.csv`; `evidence/D1/independence-matrix.csv`; `evidence/D2/independence-matrix.csv`; `evidence/A1/component-catalogue.csv`; `evidence/E1/ledger-totals.json`; `evidence/E1/px01-summary.txt`; `evidence/E3/detection-counts.txt`; `evidence/F/m07a-execution-responsibilities.csv`; `evidence/G1/invariant-results.csv`; `evidence/G2/invariant-results.csv`; `evidence/H06b/checks.csv`.

Synthesis-run checks (read-only, core checkout whose `src/` equals `head` 5c4fc5a79d): `grep source_documented src` returns readers and the guard only; `glossary_hook.py:115` holds the `import_module("glossary.attachment")` call.

## H01

Window: 2026-07-01 to 2026-09-05, read at 2026-06-30 (start) and at P3a and P3b (end). All values observed, static-derived or history-derived, historical revisions.

| Measure | Start | End, public line (P3a) | End, EXPERIMENTAL line (P3b) | Change |
|---|---|---|---|---|
| M01a, edges per 1,000 lines | 6.602 (1,900 / 287,790) | 7.541 (3,197 / 423,962) | 7.598 (2,886 / 379,818) | +14.2% / +15.1% |
| M01b load-time, share of modules in a cycle | 0.85% (9 / 1,061) | 0.69% (9 / 1,311) | 0.72% (9 / 1,251) | lower |
| M01b load-time, largest cycle | 9 modules | 9 | 9 | equal count, lower share |
| M01d, share of code commits touching two or more components | 52.7% (June, n=438) | 35.1% (Sept, n=94) | 34.4% (Sept, n=224) | 17 to 18 points lower |

Sources: F-B1-001, F-B1-004, F-C-008, F-C2-010, F-CX-004.

- Contradiction criterion: needs M01a at or below start plus 10%. M01a is 14% to 15% above. Not met.
- Support criterion: needs two of three to rise by 25% (M01d: 10 points). None does. Not met.
- Reading: **inconclusive**. Density of cross-component imports rose moderately; load-time cycles and change scatter did not rise.
- Before the window (2026-03-31 to 2026-06-30): M01a 5.342 to 6.602 (+23.6%); M01b load-time 1.72% to 0.85%; M01d T1 54.2%. After (merge result to head): M01a 7.598 to 9.249 (+21.7%); M01b load-time 0.72% to 0.67%; M01d T3 34.3%. Both neighbours show a larger M01a rise than the window.
- Convergence, apart: the merge tree equals the EXPERIMENTAL parent. Against the public parent it has 60 fewer modules and 44,144 fewer lines (F-B1-002, F-C-012, F-C2-004).
- Exploratory, not in the verdict: the all-imports variant of M01b moves sharply (largest cycle 19% of modules in June, 42% at end of July, 12% at both line ends); single function-level imports explain the jumps (F-B1-003, F-B1-005).
- Cause, apart: M01f does not replicate in T2 (1.65 against 5.95 per 1,000 changed lines) and class cells are too small to rank (F-C-014, F-C-015, F-C2-014, F-CX-006). M01g: reviews by another account 5 of 40 in T1, 0 of 40 in T2 and T3, replicated exactly (F-C-016, F-CX-007). These say nothing causal on their own.

## H02

M02a sample of 30 from a frame of 666 (C) or 698 (C2). C: defect introduced in the same pull request 13, by an earlier change on `main` 15, untraceable 2. Detection: automated before `main` 1, automated after `main` 0, a person 22, untraceable 7. Of the 15 that had reached `main`, 4 came from a Mission with acceptance recorded on or before the merge (F-C-018, F-C-019, F-C-021; `m02-trace-sample.csv` re-tabulated here).

- Contradiction (70% stopped by an automated gate before `main`): 1 of 30 (C), 2 of 30 (C2). Not met.
- Support (50% reached `main` after passing acceptance, then found by a person or later run; 15 points above M02b): 4 of 30 (13%) against 5 of 30 in M02b. Not met.
- Not-assessable rule (more than a third untraceable): C 2 of 30; C2 10 of 30, exactly one third, plus 9 weakly traced (F-C2-018). Not met on the stated count, but at the edge in C2.
- Reading: **inconclusive**. The acceptance link is the weak part: `accepted_at` is absent for 428 of 858 Missions, so "passed acceptance" is under-recorded.
- Against this reading, toward support: without the acceptance clause, 15 of 30 reached `main` and all 15 were found by a person, against 9 of 30 in M02b. Detection does not replicate between C and C2 (person 22 against 16; F-CX-008).

## H03

- M03a, core Python: 0 unrecorded violations of the enforced tier; 48 recorded ledger entries standing for 228 upward import statements (F-B1-010, F-B1-011). The gate itself was not run by B1 (memory); E3 and D1 report it passing 80 of 80 (F-E3-001, F-D1-027).
- One dynamic import crosses a forbidden pair (charter to glossary). B1 files it as outside the rule's graph and noted in the rule's docstring; G2 counts it as one edge in no ledger (F-B1-012, F-G2-001). The two disagree on whether it is "recorded".
- M03b: 24.7% of 656 component edges at the pre-registered component granularity; 78.6% of 14 edges at top-level granularity (F-B3-002, F-B3-001).
- M03c: 92.8% of source lines have no intended internal model (F-B1-013).
- Contradiction (no unrecorded violation, fewer than 25 exceptions, M03b 90%): not met (48 exceptions; M03b below 90% at both granularities by edges).
- Support (any unrecorded violation, or more than 100 exceptions, or M03b below 70%): met through M03b at component granularity.
- Reading: **supported**, on M03b only. The support comes from absence of a documented model inside `specify_cli` (464 of 656 edges join components of one top-level package), not from violation of one. At top-level granularity the reading would be inconclusive.
- Java qualifies: charter 0 violations, 9 exemption lines, 2.8% of lines without a rule (F-B2-005, F-B2-006); events 0 violations statically, 4 exceptions, build not run (F-B2-011).

## H04

Contradiction (every claimed cell established by executed evidence): not met; most claimed cells are observed as partly established.
Support (a claimed cell not established for two or more capabilities): depends on what counts as "claimed".

- Cells observed as not established where the record states the claim as a present fact: none that I can fix without interpretation.
- Cells not established where the claim is an approved plan with a pending cut-over: events write service, logical ("one writer"; core's Python writer performs every write, F-D2-017); charter offering as served, logical (two implementations, 118 recorded divergences, F-D2-016).
- Work-package state machine, logical: not established (two code definitions, F-D1-024); the catalogue has no row that claims it, only "sole status authority" for the status model.
- Reading: **inconclusive (partial)** under a strict reading of "claimed"; supported if approved-plan claims count. To be tested in phase 2.

## H05

- M05b: 57 file ledgers; 6 shrinking, 32 flat, 19 growing: 38 of 57 (66.7%) flat or shrinking. Among the 27 that existed on 2026-09-07: 24 of 27 (F-E1-018, `ledger-totals.json`).
- M05c: 420 of 3,357 entries (12.5%) carry a reference or retirement condition; 336 of 1,092 (30.8%) without the two lint baselines; inline markers 10.3% (F-E1-020).
- Contradiction (70% on both): not met. Support (below 40% on either): met by M05c under every denominator reported.
- Reading: **supported**, on M05c. Against: read by hand with ledger headers counted, a retirement condition is present for 22 of 30 and 16 of 30 sampled entries (F-E1-025); under that reading M05c would not be below 40%.

## H06

Run 1: 2 of 20 answers meet all three conditions; 6 of 20 with four borderline judgements relaxed (F-H06b-013, `checks.csv`). Support threshold is 10 or fewer. Reading: **supported**. Correct against code: 12 of 20, partly 8, incorrect 0. Run 2 does not change the count. Both declared limits (guidance files in context in run 1; questions inferred by the checker) would, if anything, raise the count.

## H07

Execution: 12 of 14 verified (85.7%), 1 delegated, 2 missing. Coordination: 15 of 15 (F-F-001, F-F-002). Difference 14.3 points, inside 20. Reading: **contradicted**. Against: the verified execution responsibilities record, prepare or gate; starting and supervising are outside core, stopping and attaching are held nowhere.

## H08

Core Python: the contract-only check differs for I1 and I2 and cannot give pass or fail for I5; I3 finds the same imports but cannot tell recorded from unrecorded; I4 and I6 agree. Charter Java: I1 to I4 agree, I5 partial, I6 not assessable for the contract-only agent (environment). Support (five agree in both languages): not met. Contradiction (four differ or cannot be written): three firm, four if I3 counts. Reading: **inconclusive**, at the edge of contradicted.

## PX-01

Stalls at a guard with no documented producer (gathering, third of six steps) (F-E1-028, F-E1-029, F-E1-030; `px01-summary.txt`; grep re-run).

## Scenarios, first pass

AS-01 not demonstrated; AS-02 partly; AS-03 partly; AS-04 partly; AS-05 demonstrated for released artefacts; AS-06 partly; AS-07 partly; AS-08 partly; AS-09 demonstrated for lane state; AS-10 not assessable (desk only); AS-11 partly; AS-12 not demonstrated.
