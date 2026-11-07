# Merged PRs and git churn: method and results

Window: 2026-08-06..2026-11-06. Data: `pr-classification.csv`, one row per merged PR, 1305 rows. Scripts: `scripts/prs/` (`fetch.sh`, `churn.py`, `cand.py`, `build.py`, with the hand codes in `cls.txt`).

## Method

- **History.** Fetched with `git fetch --shallow-since=2026-07-15 origin main`.
- **Commits.** `git log origin/main --since=2026-08-06 --until=2026-11-07 --no-merges --format='@@%H%x09%s' --name-only`, scored by `churn.py`.
- **PRs.** `gh api -X GET search/issues -f q='repo:spec-kitty/spec-kitty is:pull-request is:merged merged:<7-day slice>'` found 1305 PRs. Sizes come from REST `pulls/{n}` and file lists from `pulls/{n}/files`. The 166 lane-related PRs were classified by hand. Every other PR is marked `NONLANE`.

## Git churn

- **All commits.** 11,076 non-merge commits, of which 3,514 touch `src/`. Of those `src/` commits, 65.3% have a fix-type subject, which is the baseline.
- **Lane-model areas** (`lanes/`, `coordination/`, `workspace/`, `consolidation/`, `policy/lane_tip_recorder.py`, `mission_runtime/`): 546 commits, 15.5% of `src/` commits. 67.8% of them are fix-type.
- **Consolidation.** The only area clearly above the baseline, at 70.5% fix-type (165 of 234).
- **Top files by fix commits:**
  - `tasks_move_task.py` (55)
  - `orchestrator_api/commands.py` (55)
  - `consolidation/executor.py` (54 of 69)
  - `runtime_bridge.py` (54)
  - `cli/commands/upgrade.py` (48)
  - `mission_finalize.py` (45)
  - `consolidation/reconciliation.py` (38 of 52)

## Merged PRs

- **Total churn.** 5,457,241 lines (additions plus deletions).
- **Lane-related PRs.** 166 of 1305 PRs (12.7%), carrying 11.7% of churn.
  - With every PR capped at the 95th-percentile size: 14.3% of churn.
  - Among the 748 PRs that touch `src/`: 18.4% of PRs and 19.9% of churn.
- **PR size.** Lane-related PRs are about 3x larger: median 1,869 lines against 621.

PRs and churn by cause code (166 lane-related PRs):

| Cause code | PRs | Lines changed |
|---|---|---|
| CG | 40 | 117k |
| SD | 33 | 133k |
| NL (lane allocation, refactors) | 27 | 132k |
| CT | 18 | 61k |
| WC | 16 | 117k |
| HC | 12 | 25k |
| WL | 8 | 32k |
| HT | 7 | 9k |
| UF | 3 | 10k |
| DP | 2 | <1k |

By model:

| Model | PRs |
|---|---|
| lane-branch | 73 |
| coord | 46 |
| worktree | 23 |
| single_branch | 21 |

## Changelog

- **`docs/changelog/unreleased/` `*.fixed.md`.** 17 of 72 fragments (24%) mention lane or worktree terms.
- **`CHANGELOG.md` 4.0.0rc1..rc8 Fixed entries.** 228 of 525 (43%) mention them, peaking at rc5 with 96 of 175. These keyword counts overcount, because "consolidat" also matches generic wording.

## Caveats

- **Merge styles.** Most PRs were rebase-merged, which is why commit counts are far higher than PR counts.
- **Fix regex.** The regex is loose, so the fix-share gaps between areas are weak evidence.
- **Large PRs.** A few bulk PRs over 100k lines inflate the baseline. The capped and `src/`-only figures correct for that.
- **One code per PR.** A PR that spans several causes carries only one code.
- **Older PRs.** PRs merged before the 2026-09-07 repository move are counted only when they moved with the repository.
