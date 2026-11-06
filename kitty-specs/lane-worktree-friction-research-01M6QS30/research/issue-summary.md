# Issue classification: method and results

**Window:** issues created 2026-08-06..2026-11-06 in `spec-kitty/spec-kitty`.
**Files:** `issue-classification.part{1,2}.csv` (1365 rows), `issue-hand-labels.csv` (170 hand labels) and `scripts/issue_classify.py` (the heuristic).

## Method

**Queries.** All queries were `gh api -X GET search/issues -f q='repo:spec-kitty/spec-kitty is:issue created:2026-08-06..2026-11-06 ...'`. The window was split into 7 date slices to stay under the search cap. Together they return 2550 issues.

**Population.** 1365 issues: the union of the labels `catfooding`, `reliability`, `type:bug`, `domain:git`, `domain:consolidation`, `domain:status`, `priority:P0` and `priority:P1`, deduplicated.

| Label | Issues |
|---|---|
| `reliability` | 745 |
| `priority:P1` | 528 |
| `catfooding` | 330 |
| `domain:status` | 265 |
| `priority:P0` | 262 |
| `domain:consolidation` | 180 |
| `domain:git` | 162 |
| `type:bug` | 16 |

**Classification.** All 1365 issues were classified by a keyword and label heuristic. 170 were also hand-classified, and those hand labels replace the heuristic in the CSV.

**Validation.** On a fresh holdout of 45 issues:
- lane vs non-lane agreement: 93%;
- cause code agreement: 89%;
- severity agreement: 51%, so severity is indicative only.

## Results

**By cause code:** NL 1037, CT 119, WC 52, WL 48, CG 48, SD 23, DP 13, UF 12, HC 9, HT 4.

**NL by area:** CI/tests 290, charter/doctrine 166, other 154, status model 102, hosted/status-api 89, upgrade 87, CLI UX 72, review 72, docs 5.

**By model:** none 1037, coord 137, worktree 94, lane-branch 54, single_branch 43.

**Lane-related share:**

| Subset | Share |
|---|---|
| Whole population | 328/1365 = 24.0% (hand-only subset: 24.1%) |
| `catfooding` | 123/330 = 37.3% |
| P0 or P1 | 177/790 = 22.4% |
| P0 | 65/262 = 24.8% (36.9% excluding bot "Nightly suite red" issues) |
| Data-loss issues | 41/129 = 32% |
| Data-loss or wrong-verdict | 164/462 = 35.5% |
| `domain:consolidation` | 72% |
| `domain:git` | 63% |

**Persistent per-lane checkout (model=worktree):** 94/1365 = 6.9% overall, and 37/330 = 11% within catfooding.

**Trend by month (all issues / catfooding only):**
- Aug: 15.7% / 31%
- Sep: 23.6% / 32%
- Oct: 25.9% / 46%
- Nov (6 days, n=61): 37.7% (only 1 catfooding issue)

**Top severe lane/worktree issues:** #4753, #4752, #4981, #5570, #5666, #4895, #4978, #5965, #5758, #7173.

## Caveats

- The population is selected by label. Across all 2550 issues the lane share is at most about 13%.
- **Authors:** two authors filed most lane issues, largely from QA and squad rounds.
- **Duplicates:** chains of regression and follow-up issues for one defect class (e.g. #4981 → #5570 → #6871 → #7121) overweight a few classes.
- **Bots:** 105 bot issues are classified NL:CI.
- **CT is broad:** it includes resume, abort and rollback windows that are only partly caused by coordination topology.

The classified rows are split into parts so each file stays under the 256 KiB Mission artifact cap that the corpus check enforces (`tests/contract/test_mission_status_reality.py`, `_CONTENT_CAP`). Each part carries the header row; concatenate them to rebuild the table.
