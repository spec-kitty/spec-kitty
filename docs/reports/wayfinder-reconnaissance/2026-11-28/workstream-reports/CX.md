---
doc_status: draft
updated: '2026-11-28'
---

# Workstream CX: comparison of two independent runs (C and C2)

Audience: the commissioning architect and the synthesis team. They know workstream C's brief and need to know which of its numbers held up across two independent runs, and why the others did not. This report judges agreement between the runs. It does not say which run is right and draws no conclusion about the architecture.

## Profile and directives applied

Profile `analyst-annie`, with charter context for action `review`.

- DIRECTIVE_003 (decision documentation). Every classification threshold and every comparison rule is written down below and in `evidence/CX/script-build*.txt`.
- DIRECTIVE_032 (conceptual alignment). Its "confirm with the requester" step conflicts with the no-interaction envelope, and the envelope wins. I state my interpretations instead:
  - "Replicated" means a relative difference of at most 10%, where relative difference = |C − C2| divided by the mean of the two values.
  - "Line" means a line of history.
  - "Same direction" means both runs move the same way between consecutive slices; a flat value in both counts as the same direction.
- DIRECTIVE_047 (audience-oriented writing). The audience is named above.

The profile's boundary against architecture decisions matches the envelope.

## Method and tools

- Tools: Python 3.13.18, PyYAML 6.0.3, git 2.43.0.
- Inputs: `dispatch/C.txt`; every file in `evidence/C/` and `evidence/C2/`; the claims in `findings/C` and `findings/C2`; the deviation sections of `workstream-reports/C.md` and `C2.md`. No other workstream's material was read.
- Method: I joined the two runs' per-commit files on the 12-character SHA, compared their samples SHA by SHA, and built `evidence/CX/comparison.csv` (477 rows) from both runs' CSVs.
- Where a difference needed an explanation, I recomputed from the published evidence only:
  - M01f estimator variants;
  - M01f sensitivity to the largest sampled commit;
  - pooled 2026-08 public-line means for C;
  - pooled events T1 for C2.
- One query reached the repository: `git show --name-only` on the 86 commits whose component counts differ between the runs, to find their src directories. Both runs reached core at head `5c4fc5a79de1`.

## Coverage

**Covered.** Every measure family in the brief: volume denominators, the commit classification, M01c, M01d (both component levels), the co-change matrix, M01f, M01g, M02a, M02b, the events sibling series, recurrence, 14-day refix chains and the convergence merge. Slices: T1, T2 pooled, T2 per line, T3, and 14 month-line cells.

**Not covered.**
- No independent re-run of either AST walker (M01f).
- No third reader for the five commits on which the two classification readers disagree.
- M02 frame-member overlap could not be measured, because C2 published no frame list.
- The narrative change chains are purposive in both runs and are not compared.

## Measures

| Family | Replicated | Not replicated | Not comparable | Descriptive | Key values (C vs C2) | Finding |
|---|---|---|---|---|---|---|
| Volume, all classes | 25 | 0 | 0 | 0 | code commits 947/1,809/3,026 in both; same 6,345 SHAs | F-CX-001 |
| Volume, by class | 30 | 30 | 0 | 0 | T3 compatibility-work 303 vs 69 | F-CX-001 |
| Classification | 2 | 0 | 0 | 4 | between-run label agreement 89.4%, kappa 0.841; sample of 50 identical, 38/50 each | F-CX-002 |
| M01c, all classes | 18 | 0 | 0 | 0 | T1 2.823 vs 2.806; T3 1.681 vs 1.683 | F-CX-003 |
| M01c, by class | 79 | 29 | 0 | 0 | compatibility-work T1 2.35 vs 5.51 | F-CX-003 |
| M01d, all classes | 10 | 2 | 0 | 0 | T1 0.542 vs 0.543; top-level T2 EXPERIMENTAL 0.083 vs 0.074 | F-CX-004 |
| M01d, by class | 46 | 26 | 0 | 0 | — | F-CX-004 |
| M01c/M01d monthly | 40 | 1 | 0 | 0 | 2026-03 median 1.5 vs 1.0 | F-CX-004 |
| Co-change | 41 | 2 | 0 | 0 | top-15 overlap 14, 15, 15, 15 of 15 | F-CX-005 |
| M01f | 4 | 17 | 0 | 3 | T2 file edges 1.651 vs 5.953 per kloc; sample overlap 40/15/11 of 150 | F-CX-006 |
| M01g | 9 | 0 | 1 | 0 | identical 120 commits; reviews 5/0/0 in both | F-CX-007 |
| M02a/M02b | 10 | 7 | 2 | 2 | frames 666 vs 698, 1,262 vs 1,264; origin 13/15/2 and 21/9 in both | F-CX-008 |
| Events sibling | 18 | 3 | 1 | 0 | 2026-10 share 0.268 vs 0.218; imported 141 vs 0 | F-CX-009 |
| Recurrence | 3 | 2 | 0 | 0 | components 69/88 vs 68/88; files 497/1,712 vs 517/1,977 | F-CX-010 |
| Refix | 1 | 2 | 1 | 0 | T3 84.7% vs 70.8% | F-CX-010 |
| Convergence merge | 6 | 0 | 0 | 0 | src files 481 vs 480 | F-CX-011 |
| **Total** | **342** | **121** | **5** | **9** | | |

"Descriptive" rows record sample overlaps and agreement rates; they are not replication tests.

### How the samples compare

| Sample | Frames | Overlap between the two samples |
|---|---|---|
| Classification validation | identical | 50 of 50 |
| M01g | identical | 40 of 40 per period |
| M01f | identical in size and membership; class strata and allocation differ | 40, 15 and 11 of 150 |
| M02a | 666 vs 698 | 4 of 30 |
| M02b | 1,262 vs 1,264 | 2 of 30 |

For M02b, C draws from a fresh random stream while C2 draws after M02a from the same stream, so the draws differ even though the frames are almost the same.

### Between-period directions (F-CX-012)

Of 220 comparisons that have a previous slice, the direction agrees in 198.

**Directions both runs agree on:**
- All-class M01c and M01d, at both component levels: 25 of 25 steps (lower from T1 to T2, roughly flat from T2 to T3).
- M01f new-to-graph pairs: lower from T1 to T2 and from T1 to T3.
- Refix share (one shared file): lower from T1 to T2, higher from T2 to T3.

**Directions the runs disagree on:**
- M01f file-edge rate: T1 to T2 and T2 to T3.
- M01f new-to-graph pairs: T2 to T3.
- 13 by-class rows.
- One month: 2026-08 public M01d.

## Definitional choices that moved a result by more than 10% (F-CX-013)

1. **Classification rule order and keyword fall-through.** C tests compatibility keywords before the fix prefix; C2 tests them after it. C2 also sends unprefixed, chore and docs subjects through keyword rules. Affected: the by-class volumes and by-class M01c and M01d.
2. **Component assignment.** C follows each file's rename lineage to its final path; C2 maps by directory only. The runs differ on 80 of 6,345 commits for component count and 43 for top-level count. Affected: top-level M01d in T2 EXPERIMENTAL, T1 pair counts, and the file-recurrence denominator.
3. **Fork-window boundary.** C assigns by reachability from the fork point; C2 by date (277 vs 285 commits).
4. **M01f estimator and allocation.** C weights by stratum with proportional allocation; C2 uses an unweighted ratio with at least 10 commits per class. Combined with a heavy-tailed sample: one C T2 commit holds 65.8% of the sampled lines; without it C T2 is 4.846 against C2's 5.953. Frames are identical here, so this is a difference of samples drawn from the same frame.
5. **M02 rules.** The fix-subject rule and the contract-path rule differ between the runs.
6. **M02 detection buckets.** C uses "untraceable"; C2 uses "not determinable" and splits reviewer findings from issue reports.
7. **Refix matching.** The runs differ on rename lineage, line compatibility, fix set and the strict-overlap rule (C uses Jaccard; C2 uses the share of the first fix's files).
8. **Events component universe** and the test for imported commits.
9. **Mission-acceptance definition and agent-authorship column.** Not comparable.

**Choices that moved results by no more than 10%:**
- rename detection in the merge diff;
- the percentile method (nearest rank in C, interpolation in C2);
- bulk-commit treatment, once bulk commits are subtracted from C's counts.

## Deviations

1. **Relative difference.** The brief does not define it. I used the symmetric form, |C − C2| divided by the mean of the two values.
2. **Descriptive rows.** I added a "descriptive" label for sample overlaps and agreement rates, so they are not counted as replication tests.
3. **Co-change aggregate.** It is restricted to pairs with at least 10 joint commits in either run. Counts of 3 to 9 move by more than 10% on a single commit.
4. **Pooling where the slicing differs.**
   - For the T2 public line, CX summed C's pre-fork and fork-window pair counts. The sum is a lower bound, because C applies its at-least-3 threshold to each segment.
   - CX pooled C's 2026-08 public segments by weighted mean and share.
   - CX pooled C2's months 04 to 06 for events T1.
5. **Finding count.** 13 records against a cap of 15. The monthly series is carried in F-CX-004, not in a record of its own.

## Blocked items

None.

## Exploratory observations (not answers to measures)

- On commits both runs sampled, the two M01f edge counters agree on 61 of 66. The two independently written AST walkers give nearly identical edge counts; the M01f gap comes from sampling and estimation.
- M02 origin splits are identical in both runs (13/15/2 and 21/9) although the samples share only 4 and 2 commits.
