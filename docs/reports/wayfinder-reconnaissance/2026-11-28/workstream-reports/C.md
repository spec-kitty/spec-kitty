---
doc_status: draft
updated: '2026-11-28'
---

# Workstream C: evolution and change coupling

View: observed. Evidence: history-derived (version control and tracker). All figures are measurements of commits as recorded. No cause is attributed and no verdict on the architecture is given.

## Profile and directives applied

Profile `researcher-robbie` (investigate, synthesise, no production code, no final decisions). Its "actionable recommendations" success criterion conflicts with the envelope; the envelope won and no recommendation is filed. From `charter context --action review`: DIRECTIVE_003 (decisions recorded: rules written before classifying), DIRECTIVE_032 (overloaded terms named by sense: "line" is a line of history, "merge" is branch integration unless "convergence merge" is said), DIRECTIVE_048 (every figure names a revision), DIRECTIVE_050 (no credentials in outputs; account names replaced by ordinals), NO_FULL_HEAVY_SUITES_IN_MISSION (no test suite was run).

## Method and tools

git 2.43.0, Python 3.13.18, gh 2.89.0 (REST, read-only), spec-kitty-cli 4.0.0rc9. Core at `5c4fc5a79de1`, events at `646e330b896b`.

- Unit: one non-merge commit, its own diff (`git log --no-merges -M --numstat`). Merge commits are counted in the denominators only; their own content is not measured, except the convergence merge, which is compared with each parent.
- Lines of history by reachability from the fork point `38090b6493`: pre-fork, public, experimental, converged. Month and period by committer date (UTC).
- Component: the brief's definition, through a rename map (file lineage from recorded renames, then 16 directory rules). 98 components were touched since 2026-01; 21 no longer exist at head.
- Classes by `evidence/C/classification-rules.txt`, written before any classification.
- Samples: `random.Random(20261128)` over frames sorted by SHA.

## Coverage

Covered: 20,454 non-merge commits of core (6,356 code commits since 2026-01), 1,475 of events, 120 pull request lookups, 60 fix traces. Not covered: content inside ordinary merge commits; a per-pull-request or per-Mission unit; a second reader for the classification and trace judgements; a rename map for events.

## Measures

| Measure | T1 | T2 (pooled; pre-fork / public / experimental) | T3 | Findings |
|---|---|---|---|---|
| Non-merge commits | 2,806 | 4,427 (2,231 / 796 / 1,400) | 10,051 | F-C-001 |
| Code commits | 950 | 1,816 (831 / 279 / 706) | 3,027 | F-C-001 |
| Docs, specs, tests only | 55.6% | 50.4% | 49.8% | F-C-002 |
| Changed src lines (code commits) | 438,385 | 439,951 | 476,670 | F-C-001 |
| Python lines under src at period end | 287,790 | 423,962 public, 379,818 experimental | 524,936 | F-C-003 |
| Corrective-maintenance share of code commits | 53.7% | 46.7% | 53.7% | F-C-004 |
| M01c median / p90 / mean | 2 / 6 / 2.82 | 1 / 3 / 1.86 (means 2.07 / 1.82 / 1.63) | 1 / 3 / 1.68 | F-C-005, F-C-006 |
| M01d, two or more components | 54.2% | 37.4% (39.8 / 43.3 / 32.3) | 34.3% | F-C-007, F-C-008 |
| M01d, two or more top-level packages | 24.9% | 12.9% | 11.5% | F-C-007 |
| Largest co-change pair, support | charter/offering with cli, 8.9% | cli with core, 4.1% | specify_cli root files with cli, 3.2% | F-C-009..011 |
| Commits touching `specify_cli/cli` | 49.6% | 34.8% | 36.2% | F-C-009..011 |
| M01f, edges new to the repository per 1,000 changed Python lines (95% interval) | 1.38 (0.63..2.74) | 0.24 (0.05..1.30) | 0.28 (0.07..0.54) | F-C-014, F-C-015 |
| M01g, pull request found | 39 of 40 | 39 of 40 | 40 of 40 | F-C-016 |
| M01g, review object by another account | 5 of 40 | 0 of 40 | 0 of 40 | F-C-016 |
| Fix commit followed within 14 days by a fix sharing a file | 80.7% | 70.1 / 71.2 / 80.4% | 84.7% | F-C-024 |

Other measures:

- **Convergence merge** (F-C-012): its tree equals the EXPERIMENTAL parent's tree. Against the public parent it differs in 481 src files (+17,449/-61,454) in 63 components, led by `specify_cli/sync` (36,491 changed lines).
- **Classification agreement** (F-C-013): 38 of 50, kappa 0.66; 41 of 50 if a cherry-pick trailer is decisive.
- **M02a** (F-C-018, F-C-019, F-C-021): frame 666 of 2,276 fix commits. Sample of 30: defect from the same pull request 13, from an earlier change on main 15, untraceable 2. Detection: automated before main 1, automated after main 0, a person 22, untraceable 7.
- **M02b** (F-C-020, F-C-021): frame 1,262. Sample of 30: same pull request 21, earlier change 9. Detection: automated before main 3, automated after main 1, a person 8, untraceable 18.
- **Mission acceptance of the 24 introducing changes** (F-C-021): acceptance recorded on or before merge 9, Mission without `accepted_at` at head 8, no Mission artifacts 6, unknown 1.
- **Sibling series, events** (F-C-022): share touching two or more components 75.0% (n=24), 44.8% (87), 29.5% (237); 41.0% (105) in T3 without the 141 commits imported from core.
- **Recurrence** (F-C-023): 497 of 1,712 corrected files (29.0%) have corrective commits in three or more months; 69 of 88 corrected components.
- **Narrative chains** (F-C-025..027): 11 purposive chains, 3 to 4 per period.
- **Population rules** (F-C-028, F-C-029): 22 bulk commits excluded; rename map.

## Deviations

1. **Period boundary.** T3 is the converged line from the merge on 2026-09-05, not from 2026-09-06 (4 commits affected). T2 is given per line segment and pooled. Written in the rules file before measurement.
2. **Source lines by class.** Not meaningful; given per point and per component.
3. **M01g tooling.** The `gh` CLI (REST) was used instead of the GitHub MCP tools, to script 120 lookups; both are read-only. EXPERIMENTAL-line pull requests were found by SHA search in the archived repository.
4. **M01f sampling in T2.** One pooled sample of 150 over the three line segments (59 / 26 / 65), not one per line.
5. **M02 detection categories.** A fourth value, "untraceable", is used for pre-merge folds whose text names no detector; it stays in the denominator. An origin kind "same pull request" was added, because 34 of 60 sampled fixes correct something that never reached main.
6. **Classification reading.** The cherry-pick trailer lay below the body excerpt that was read, so the reading was blind to it. Both agreement figures are reported.
7. **Rules file against code.** `classification-rules.txt` was not edited after classification. The code also treats `landing` and `fold` as first words, so about 120 code commits with the unprefixed subject form "landing fold: ..." are corrective-maintenance; by the literal text of the file they would be "other". Carried in F-C-004.

## Blocked items

None. All 120 review lookups and all 60 traces returned data. Two sampled commits have no pull request in either tracker.

## Limits that bear on every figure

- The commit is not a uniform unit. The share of squash-style commits is 42.6%, 21.0% and 44.2% by period, and such commits touch more components (F-C-030, F-C-032).
- Class is assigned by rule with 76% agreement against one reader.
- Nine of 24 introducing changes in M02 are blame candidates, not confirmed origins.
- A review given by an agent squad or recorded in a Mission artifact leaves no review object and is not counted in M01g. Sampled commits whose pull request has a comment by another human account: 3, 9 and 15.
- M01f counts every import statement in changed files, including function-local ones, and cannot see dynamic imports. One commit holds 65.8% of the sampled T2 lines.
- The shared-file test for fix-of-fix chains is an upper bound; the citation test (4.3% in T1, 26.3% in T3) is a lower bound that depends on citation habits.

## Exploratory observations

Marked exploratory in their records; none answers a measure.

- F-C-030: squash-style share and its correlation with components touched.
- F-C-031: 112 code commits after the merge carry a cherry-pick trailer and fall in the convergence-activity class by rule; the sample reading suggests part are routine cherry-picks.
- F-C-032 (interpretation): period differences in M01c and M01d cannot be separated from commit granularity with these data.
- F-C-033 (interpretation): of the 24 sampled defects that had reached main, 21 were detected by a person, 1 by an automated run on main, 2 are untraceable.

## Outputs

`evidence/C/` (38 files and `MANIFEST.csv`, 1.3 MB), `findings/C/F-C-001..033.yaml` (31 observations, 2 interpretations).
