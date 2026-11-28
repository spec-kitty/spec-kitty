---
doc_status: draft
updated: '2026-11-28'
---

# Coupling and deterioration

Synthesis S-A. What the measured series show about coupling in core Python and its change over time. Sources: B1, B3, C, C2, CX, G1, G2.

## Rules applied

- All values are in the **observed** view. Structural values are static-derived at historical revisions or at `head`; change values are history-derived.
- Three periods: T1 2026-04-01 to 2026-06-30, T2 2026-07-01 to 2026-09-05 (two lines from 2026-08-19), T3 2026-09-06 to 2026-11-28.
- No trend is drawn across the convergence merge `2554bd13ad`. Its effect is reported on its own.
- Commits touching more than 500 files (22) are excluded from per-commit measures; commits outside `src/` are counted apart (F-C-028, F-C-002).
- Paths are compared through a rename map (F-C-029).
- Evidence of deterioration is kept apart from evidence for a cause.
- Pre-registered measures: M01a to M01g. Everything else here is exploratory and is marked.

## 1. Structural series (M01a, M01b)

Read from `evidence/B1/series.csv` (F-B1-001, F-B1-003, F-B1-004).

| Point | Line | Modules | Source lines | M01a, edges per 1,000 lines | M01b all imports, in a cycle | M01b all imports, largest cycle | M01b load-time, in a cycle |
|---|---|---|---|---|---|---|---|
| P0 2026-01-16 | public | 110 | 27,141 | 3.316 | 22.7% | 18.2% | 0.00% |
| 2026-03-31 | public | 348 | 84,420 | 5.342 | 14.4% | 12.4% | 1.72% |
| P1 2026-06-16 | public | 1,000 | 265,826 | 6.260 | 23.7% | 17.3% | 1.00% |
| 2026-06-30 | public | 1,061 | 287,790 | 6.602 | 26.7% | 19.2% | 0.85% |
| P2 2026-07-08 | public | 1,070 | 296,060 | 6.867 | 27.3% | 19.5% | 0.84% |
| 2026-07-31 | public | 1,198 | 358,728 | 6.950 | 44.5% | 41.8% | 0.75% |
| 2026-08-31 | public | 1,304 | 415,995 | 7.515 | 28.6% | 11.7% | 0.69% |
| 2026-08-31 | EXPERIMENTAL | 1,235 | 366,585 | 7.510 | 26.6% | 11.4% | 0.73% |
| P3a 2026-09-04 | public | 1,311 | 423,962 | 7.541 | 28.8% | 11.8% | 0.69% |
| P3b 2026-09-05 | EXPERIMENTAL | 1,251 | 379,818 | 7.598 | 27.1% | 11.4% | 0.72% |
| *merge result* | *merged* | *1,251* | *379,818* | *7.598* | *27.1%* | *11.4%* | *0.72%* |
| P4 2026-09-13 | merged | 1,257 | 390,507 | 7.739 | 28.8% | 13.9% | 0.88% |
| P5 2026-10-02 | merged | 1,325 | 439,604 | 8.094 | 43.9% | 38.4% | 0.83% |
| P6 2026-10-14 | merged | 1,331 | 446,024 | 8.988 | 31.9% | 14.1% | 0.75% |
| P7 2026-11-28 | merged | 1,490 | 524,936 | 9.249 | 33.1% | 13.5% | 0.67% |

### By period

| Period | M01a | Change | M01b load-time share |
|---|---|---|---|
| T1 (2026-03-31 to 2026-06-30) | 5.342 to 6.602 | +23.6% | 1.72% to 0.85% |
| T2, public line (to P3a) | 6.602 to 7.541 | +14.2% | 0.85% to 0.69% |
| T2, EXPERIMENTAL line (to P3b) | 6.602 to 7.598 | +15.1% | 0.85% to 0.72% |
| T3 (merge result to head) | 7.598 to 9.249 | +21.7% | 0.72% to 0.67% |

What this shows:

- Import density across components rose in every period. The rise in the window T2 is the smallest of the three. Source lines more than tripled in T1 (84,420 to 287,790) and grew by 38% in T3 (F-B1-001, F-C-003).
- Load-time cycles are small and stable: 8 to 11 modules at every point since P1, none spanning two components at `head` (F-B1-004).
- With function-level and type-checking imports counted, a quarter to a third of modules sit in a cycle, and the largest cycle is unstable. It was 501 of 1,198 modules at the end of July, 152 a month later, 509 at P5 and 187 at P6. At P5 six single edges each cut it to 249 or fewer when removed alone; at `head` no single edge cuts the 201-module cycle by 50 (F-B1-005, exploratory).

What it does not show: whether a rise in density is harmful. M01a counts distinct module pairs; it has no threshold of its own beyond the pre-registered ones.

Limits: one workstream, cross-checked with `grimp` at two revisions. Dynamic imports are not edges (0 to 8 literal sites per revision).

## 2. The convergence, reported apart

- The merge tree equals its EXPERIMENTAL parent (zero differing files). Every structural measure of the merge result equals P3b (F-B1-002).
- Against the public parent: 3,179 files differ; under `src/`, 481 files, +17,449 / -61,454 lines, 63 components. The largest differences are in `specify_cli/sync` (36,491 changed lines), `specify_cli/cli` (11,064), `zeitgeist_client` (5,832), `delivery` (5,718) (F-C-012; replicated within 2%, F-CX-011).
- Relative to P3a the merge result has 60 fewer modules, 44,144 fewer lines, 311 fewer cross-component edges; density 7.598 against 7.541 (F-B1-002).
- From the fork point the public line changed 1,100 `src` files and the EXPERIMENTAL line 1,295 (F-C-012).
- 576 non-merge commits carry a cherry-pick trailer; 202 of them fall after the merge (F-C-031, F-C2-027; exploratory).

The convergence removed code and edges in roughly equal proportion. Density did not step.

## 3. Change coupling (M01c, M01d)

Read from `evidence/C/m01c-m01d-components-per-commit.csv`. C and C2 agree on every all-class value below within 10% (F-CX-003, F-CX-004).

| Period | Code commits | Median / p90 / mean components | Share touching two or more components | Same, six top-level packages |
|---|---|---|---|---|
| T1 | 947 | 2 / 6 / 2.82 | 54.2% | 24.9% |
| T2 pre-fork | 829 | 1 / 4 / 2.07 | 39.8% | 15.6% |
| T2 public, fork window | 277 | 1 / 3 / 1.82 | 43.3% | 16.6% |
| T2 EXPERIMENTAL | 703 | 1 / 3 / 1.63 | 32.3% | 8.3% |
| T2 pooled | 1,809 | 1 / 3 / 1.86 | 37.4% | 12.9% |
| T3 | 3,026 | 1 / 3 / 1.68 | 34.3% | 11.5% |

Monthly share touching two or more components (F-C-008): 2026-01 35.2%, 02 27.0%, 03 50.0%, 04 66.1%, 05 47.4%, 06 52.7%, 07 41.1%, 08 pre-fork 37.9%, 08 public 47.5%, 08 EXPERIMENTAL 31.3%, 09 public 35.1%, 09 EXPERIMENTAL 34.4%, 09 merged 34.4%, 10 36.9%, 11 31.5%.

What this shows:

- Per commit, change is less scattered after T1, on both taxonomies and in both runs (F-C-005, F-C-007, F-C2-007, F-C2-009, F-C2-012).
- By class, capability-growth commits touch the most components in every period (mean 3.58, 2.63, 2.91); corrective commits fewer (2.28, 1.57, 1.54) (F-C-006, F-C2-008).

What it does not show:

- That a unit of intent became more local. The commit is not a uniform unit: squash-style commits are 42.6%, 21.0% and 44.2% of code commits and touch more components (F-C-030). The EXPERIMENTAL line recorded 596 pull requests as merge commits; at the level of first-parent change units the difference between the two lines disappears (40.5% against 40.2%) (F-C2-011). The investigators' readings F-C-032 and F-C2-032 say the same and are kept.
- A class-mix effect only: within corrective commits the share also falls (F-C2-009, F-C2-031).

The sibling series in `spec-kitty-events` falls in the same direction: 75.0%, 44.8%, 29.5% (F-C-022). This is consistent with a change in how work is cut into commits across the ecosystem, and does not establish it.

## 4. Where change concentrates (co-change, recurrence)

Pre-registered as supporting tables, not as verdict measures.

- `specify_cli/cli` is touched by 49.6% of code commits in T1, 34.8% in T2 and 36.2% in T3. 12 to 13 of the 15 largest co-change pairs include it in T1 and T3 (F-C-009, F-C-011; top pairs replicate, F-CX-005).
- Leading pairs: T1 `charter/offering` with `cli`, 84 commits (support 8.9%); T3 `specify_cli` root files with `cli`, 98 commits (3.2%). The largest pair without `cli` in T3 is `consolidation` with `lanes`, 54 commits (F-C-009, F-C-011).
- 497 of 1,712 corrected files (29.0%) received corrective commits in three or more months; three files in all eleven months. C2: 517 of 1,977 (26.2%). 69 or 68 of 88 components did (F-C-023, F-C2-022, F-CX-010).
- A fix followed within 14 days by another fix sharing a file: 80.7% in T1, 84.7% in T3 (C); 79.1% and 70.8% (C2). With an identical file set: 15.2%, 31.1%, 28.6% (C2). The loose rate is an upper bound driven by a few hot files; the T3 value does not replicate (F-C-024, F-C2-023, F-CX-010).

## 5. Structure at head (context for the series)

Static-derived, `head`. Exploratory unless a measure id is given.

- 74 components, 656 directed component edges, 4,855 module edges. 62 components are in a cycle counting all imports; one cycle holds `mission_runtime`, `runtime` and 58 of 67 `specify_cli` components. At load time the cycle holds 48 (F-B1-006, F-B1-007).
- 60 of 74 components each reach 71 others (F-B1-008).
- Between top-level packages the upward edges are `runtime` to `specify_cli` (98 module edges, 50 at load time) and `mission_runtime` to `specify_cli` (30, 1 at load time). Both are held in shrink-only ledgers: 22 and 10 subpackage entries, flat since 2026-09-07 (F-B1-009, F-B1-011, F-E1-018).
- Private access: 734 of 10,427 cross-component imported names (70.4 per 1,000) reach something marked private; 200 of them target one module (F-B1-014, F-B1-015). G2 counts 131 rows across top-level packages by the underscore convention (F-G2-003).
- 259 of 542 exception classes are caught or raised by name outside their component (F-B1-018).
- 59 of 1,296 modules outside the CLI adapter import a command-line library; four are outside `specify_cli` (F-B1-020).
- 82 of 185 path keys under `.kittify/`, `kitty-specs/` or a user directory are constructed in two or more components; the status event log path in 14 components (F-B1-016).

The investigator's reading F-B1-026 (medium confidence) is that the two lower layers are not below `specify_cli` in the import graph, and that the ledgers record that state. The synthesiser's own reading agrees with the numbers and adds one qualification: at load time `mission_runtime` has one upward module edge, so the statement is strong for `runtime` and weak for `mission_runtime`.

## 6. Cause: what can and cannot be said

| Sub-measure | Result | Usable? |
|---|---|---|
| M01e, commit class | Corrective maintenance is the largest class in every period (47% to 62% depending on run). Rule against reading 76%; rule sets agree on 89.4% | For class sizes, yes. Compatibility-work differs fourfold between runs in T3 (303 against 69) |
| M01f, new edges per 1,000 changed lines | T2 does not replicate (1.65 against 5.95). Both runs: pairs new to the import graph fall from T1 to later periods | Direction T1 to later only |
| M01f by class | Cells too small; several rest on one to three edges | No |
| M01g, review by another account | 5 of 40, 0 of 40, 0 of 40; replicated exactly | Yes, for the one channel it measures |

Findings: F-C-004, F-C-013 to F-C-016, F-C2-005, F-C2-006, F-C2-014 to F-C2-016, F-CX-002, F-CX-006, F-CX-007, F-CX-013.

- The data are **not consistent with** "corrective commits spread across more components than other classes": they touch fewer, in every period and both runs.
- The data are **consistent with** "import density grows with size and with every class of work": M01a rises in all three periods, including T1, which precedes the window.
- Nothing here separates sustained local optimisation from growth as an explanation of the M01a rise. No measure taken can.
- Formal review objects by a second account are absent from the T2 and T3 samples. Review recorded elsewhere exists (reviewer-detected defects in the M02 samples) and was not measured (F-C2-034). This is a statement about one review channel and says nothing about supervision.

## 7. Summary of what the series show

1. Cross-component import density rose in every period measured: +24%, +14% to +15%, +22%. The window is not the steepest.
2. Load-time cycles did not grow. Deferred-import cycles are large and fragile.
3. Per-commit scatter fell after June 2026, in core and in the sibling repository, and the fall cannot be separated from a change in commit practice.
4. The convergence removed about 10% of source lines and of edges; density did not step.
5. Change concentrates in `specify_cli/cli` and in a recurrent set of files; about 29% of corrected files are corrected in three or more months.
6. No causal sub-measure is strong enough to attribute the density rise to a class of work.

## Not covered

- Coupling through files, events and schemas, except as counts of path construction at `head`.
- The Java repositories over time (no series was taken).
- Content introduced inside merge commits other than the convergence.
- History before 2026-01.
