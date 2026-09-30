---
title: CaaCS — Robbie's Forensic Dataset (Quantitative Evidence Base)
description: "Researcher Robbie's CaaCS forensic dataset: the quantitative evidence base for the naming/identity SSOT strangler, read-only at 3.2.0."
doc_status: deprecated
updated: '2026-09-30'
---
# CaaCS — Robbie's Forensic Dataset (Quantitative Evidence Base)

**Author:** Researcher Robbie (CaaCS squad — quantitative data engine)
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0 (read-only; no commit/switch)
**HEAD:** `be706e915`  ·  **Date produced:** 2026-06-16

> **Governance.** Directive applied: **DIR-003** (Decision Documentation — every number
> below carries the exact git/radon command that produced it, so any reviewer can reproduce
> it on this branch). Tactic applied: **`forensic-repository-audit`** (the repo's canonical
> CaaCS method, after Tornhill's *Your Code as a Crime Scene*): churn hotspots → bus-factor →
> bug hotspots → velocity → firefighting → complexity overlay → change-coupling. Method/format
> reused verbatim from `docs/architecture/audits/2026-05-spec-kitty-caacs.md` and
> `docs/architecture/assessments/code-as-a-crime-scene-overview.md`.

This note is the **empirical/temporal** companion to the static squad's structural findings in
`00-OVERVIEW.md`. The static lenses (randy/paula/pedro/alphonso) mapped the *shape* of the
split-brain; this note supplies the *behavioural* evidence — which files are actual crime scenes,
which co-change, and which are accreting — that the static read lacks.

---

## 0. Scope, exclusions, and data caveats (read first)

**Surface (18 files mined + neighbours):** the 14 prompt-named surface files plus 4 high-relevance
agent CLI orchestration files (`agent/mission.py`, `agent/workflow.py`, `agent/status.py`,
`agent/tasks.py`) that the OVERVIEW flags as carrying the un-routed `mission_id[:8]` / read-path sites.

**Exclusion list (per tactic step 1):** lockfiles, `__pycache__`, `.mypy_cache`, `CHANGELOG*.md`,
generated agent dirs (`.claude/` etc., naturally outside `src/`), mission-state JSONL/JSON. The
surface is hand-curated Python source, so vanity-file dominance is not a risk here.

**Tooling:** `git` 2.x; `radon` 6.x via `<path-to-radon>`
(complexity overlay); `wc -l` for SLOC (`cloc` not installed — acceptable for Python-only scope).

### Data caveats — these materially shape every table below

1. **Young repo / 1y == full history.** First commit `2025-08-21`, HEAD `2026-06-16` — the repo is
   ~10 months old. For nearly every surface file `full == 1y` commit count, and most show
   `1y == 6m`. The CaaCS "audit window" collapses to "all of history"; there is no quiescent tail
   to compare against. **Velocity is uniformly high and recent** — every surface file was last
   touched 0–7 days ago. Treat "churn since 1 year" as "lifetime churn".
2. **3.2.0 squash distortion (`fcf9be595`).** The 3.2.0 naming-seam mission landed as ONE squash
   commit touching 7 surface files at once. This (a) inflates the 2026-06-16 co-change degree for
   those 7 files, and (b) collapses the seam's internal per-file coupling. Granular 3.2.0 lane
   history is preserved under `backup/20260615-2110/*` but is NOT folded into these counts (it is
   off the HEAD ancestry). **The pre-3.2.0 history — the richer recurring-bug seam — IS fully
   intact and is where the temporal signal below comes from.**
3. **Conventional-Commits inflates raw defect %.** This repo uses `fix:`/`feat:`/`refactor:`
   prefixes pervasively, and the bug-grep matches the commit *body* too. Raw "defect density %"
   is therefore near-saturated (70–100%) and **not discriminating**. The discriminating signals
   are the **absolute bug-fix count** and the **naming-class-fix count** (§2), not the percentage.
4. **No rename-following in bulk recipes.** Counts use bare `git log -- <path>` (no `--follow`).
   Known splits in this window: `implement.py` shows a sawtooth (1238 LOC Mar → 693 Apr) from an
   extraction/cutover, so its lifetime churn under-counts. Young files
   (`branch_naming.py` Apr-04, `surface_resolver.py` Jun-06, `_read_path_resolver.py` May-28) have
   no pre-creation history by construction.
5. **MI/avgCC gaps.** `radon mi` returns `0.00` for the largest files (`merge.py`, `agent/mission.py`,
   `agent/workflow.py`, `agent/tasks.py`) — MI floors at 0 for very large modules; read it as
   "worst possible", not "missing". Where avgCC reads `NA` in a trend cell, radon hit a transient
   parse on the historical blob; the **LOC trend** is the load-bearing series there.

---

## 1. Hotspot table — churn × complexity (the principal-hotspot overlay)

Per-file churn (commit count + lines added/deleted, full history `--no-merges`), current SLOC,
and radon complexity (avg CC, **max-block CC**, MI, #blocks). Ranked by the Tornhill principal-
hotspot proxy **churn(commits) × max-block-CC** — unstable *and* complex.

| Rank | File | Commits | Lines churned (+/−) | SLOC | avgCC | **maxCC** | MI | churn×maxCC |
|---|---|---|---|---|---|---|---|---|
| **1** | `cli/commands/agent/tasks.py` | 126 | +7554 −3014 = **10568** | 4540 | 11.9 | **178** | 0.0 | **22428** |
| **2** | `cli/commands/agent/mission.py` | 67 | +4975 −1035 = 6010 | 3940 | 10.5 | **220** | 0.0 | **14740** |
| **3** | `cli/commands/agent/workflow.py` | 119 | +5203 −2471 = 7674 | 2732 | 8.5 | 84 | 0.0 | 9996 |
| **4** | `cli/commands/merge.py` | 95 | +5814 −2811 = 8625 | 3341 | 7.9 | **102** | 0.0 | 9690 |
| **5** | `cli/commands/implement.py` | 93 | +3777 −2421 = 6198 | 1356 | 6.9 | 57 | 19.8 | 5301 |
| 6 | `__init__.py` | 126 | +4795 −4437 = 9232 | 356 | 3.5 | 7 | 46.2 | 882 |
| 7 | `core/mission_creation.py` | 19 | +661 −44 = 705 | 617 | 7.6 | 36 | 49.4 | 684 |
| 8 | `core/worktree.py` | 28 | +1012 −306 = 1318 | 706 | 9.8 | 19 | 43.4 | 532 |
| 9 | `cli/commands/agent/status.py` | 29 | +1544 −546 = 2090 | 998 | 5.9 | 16 | 36.9 | 464 |
| 10 | `core/paths.py` | 19 | +747 −178 = 925 | 570 | 5.3 | 19 | 42.6 | 361 |
| 11 | `ownership/validation.py` | 10 | +412 −27 = 439 | 385 | 4.8 | 12 | 55.6 | 120 |
| 12 | `coordination/surface_resolver.py` | 8 | +634 −65 = 699 | 569 | 3.2 | 14 | 53.5 | 112 |
| 13 | `lanes/branch_naming.py` | 11 | +906 −61 = 967 | 845 | 2.8 | 8 | 34.7 | 88 |
| 14 | `missions/_read_path_resolver.py` | 8 | +499 −74 = 573 | 425 | 3.2 | 8 | 57.1 | 64 |
| 15 | `lanes/worktree_allocator.py` | 8 | +534 −65 = 599 | 469 | 2.8 | 7 | 61.1 | 56 |
| 16 | `core/project_resolver.py` | 10 | +204 −128 = 332 | 76 | 2.5 | 4 | 77.7 | 40 |
| 17 | `coordination/workspace.py` | 5 | +390 −41 = 431 | 349 | 2.3 | 8 | 62.0 | 40 |
| 18 | `missions/feature_dir_resolver.py` | 4 | +103 −28 = 131 | 75 | 1.0 | 1 | 100.0 | 4 |

**Reading the overlay (the load-bearing finding):**

- **The hotspots are the lifecycle CLI orchestrators, NOT the naming seam itself.** Ranks 1–5
  are all command-layer god-modules: `agent/tasks.py`, `agent/mission.py`, `agent/workflow.py`,
  `merge.py`, `implement.py`. They carry max-block CC of **57–220** (the ruff/Sonar ceiling is 15)
  and MI floored at 0. These are where naming/path logic is *consumed inline* and where every
  naming change has to be re-applied.
- **The new SSOT seam files are cold & simple by design.** `branch_naming.py` (rank 13, maxCC 8),
  `_read_path_resolver.py` (rank 14, maxCC 8), `worktree_allocator.py` (rank 15) — the 3.2.0
  consolidation *worked*: the authority modules are low-complexity. The danger is no longer in the
  seam; it is in the **un-consolidated callers** (ranks 1–5) that still hand-roll the logic.
- **`feature_dir_resolver.py` (rank 18, maxCC 1, MI 100) is a pure thin shim** — the
  re-export the OVERVIEW describes. Quantitatively confirmed: lowest complexity, lowest churn,
  highest MI of the whole surface. Yet it co-changes with everything (§3) — the hallmark of a
  hub shim.

---

## 2. Defect density — the recurring crime scenes

Two lenses. **(a)** raw bug-fix commits (`-i -E --grep='fix|bug|broken|regress|hotfix|revert'`) —
**saturated by Conventional Commits, low signal** (kept for completeness, flagged per caveat 3).
**(b)** the discriminating lens: commits whose message matches the **naming/identity-split class**
(`mid8|branch.?nam|worktree.?nam|split.?brain|orphan|project.?root|read.?path|resolver|identity.?seam`)
that touch each file — i.e. *how often this file was the scene of a naming-split fix*.

| File | (a) bugfix commits | (a) density% | **(b) naming-class fixes** |
|---|---|---|---|
| `cli/commands/implement.py` | 78 | 84% | **28** |
| `cli/commands/agent/tasks.py` | 111 | 88% | **25** |
| `cli/commands/agent/workflow.py` | 103 | 87% | **24** |
| `cli/commands/merge.py` | 76 | 80% | **20** |
| `cli/commands/agent/mission.py` | 53 | 79% | **19** |
| `core/mission_creation.py` | 17 | 89% | 9 |
| `cli/commands/agent/status.py` | 24 | 83% | 9 |
| `lanes/worktree_allocator.py` | 7 | 88% | 8 |
| `core/paths.py` | 16 | 84% | 8 |
| `missions/_read_path_resolver.py` | 7 | 88% | 7 |
| `lanes/branch_naming.py` | 11 | 100% | 7 |
| `core/worktree.py` | 23 | 82% | 7 |
| `core/project_resolver.py` | 8 | 80% | 7 |
| `coordination/surface_resolver.py` | 8 | 100% | 6 |
| `ownership/validation.py` | 7 | 70% | 5 |
| `__init__.py` | 34 | 27% | 4 |
| `missions/feature_dir_resolver.py` | 3 | 75% | 3 |
| `coordination/workspace.py` | 4 | 80% | 3 |

**Repo-wide naming-class fix volume: 175 commits** (`git log -i -E --grep='mid8|branch.?nam|...'`).
This is the recurring-defect spine the OVERVIEW's "whack-a-mole" thesis predicts — and it is
**concentrated in the consumers, not the seam**: the top-5 crime scenes (implement, tasks,
workflow, merge, mission) absorbed **116 of the file-level naming-fix touches**, vs. 7 each for the
actual authority modules (`branch_naming`, `_read_path_resolver`). The defect class lives where the
logic is *re-derived inline*, exactly the sites WP02/WP03/WP04 in the OVERVIEW route through the seam.

**Firefighting (pipeline-trust signal):** 31 `revert` + 11 `hotfix` commits repo-wide. The largest
is `bb126ed7c revert(#129): roll back 87 direct-push commits — resubmit via PR` — a process
firefight (branch-protection violation), not a code-defect revert. No revert storms localized to the
surface files. Pipeline trust is adequate; the recurrence is *defect re-entry*, not *rollback churn*.

---

## 3. Change-coupling matrix — what moves together

Co-change computed over full history (`--no-merges`), all surface-file pairs. Two views: **absolute
co-change count** (raw coupling strength) and **degree %** (`co-changes / commits-touching-the-
lower-churn-file` — surfaces hub/shim coupling).

### 3a. Strongest absolute coupling — the lifecycle-orchestrator cluster

| Co-changes | Pair |
|---|---|
| **56** | `agent/tasks.py` ↔ `agent/workflow.py` |
| 45 | `agent/tasks.py` ↔ `implement.py` |
| 39 | `agent/workflow.py` ↔ `implement.py` |
| 34 | `agent/tasks.py` ↔ `merge.py` |
| 33 | `implement.py` ↔ `merge.py` |
| 27 | `agent/workflow.py` ↔ `merge.py` |
| 24 | `agent/mission.py` ↔ `agent/tasks.py` |
| 23 | `agent/mission.py` ↔ `agent/workflow.py` |
| 19 | `agent/mission.py` ↔ `merge.py` |
| 17 | `agent/workflow.py` ↔ `core/worktree.py` |

> **The five lifecycle commands (`tasks` · `workflow` · `implement` · `merge` · `mission`) form a
> tight mutual-coupling clique (18–56 co-changes each pair).** A naming/path change *fans out across
> all of them*. This is the empirical fingerprint of the OVERVIEW's "three authorities derived
> ad-hoc at the callsite" — the logic is duplicated across the orchestrators, so they move as one.

### 3b. Strongest degree % — the shim-hub coupling

| Co-changes | Degree% | Pair |
|---|---|---|
| 4 | **100%** | `merge.py` ↔ `feature_dir_resolver.py` |
| 7 | **88%** | `implement.py` ↔ `worktree_allocator.py` |
| 6 | 75% | `merge.py` ↔ `worktree_allocator.py` |
| 6 | 75% | `agent/workflow.py` ↔ `surface_resolver.py` |
| 6 | 75% | `agent/tasks.py` ↔ `_read_path_resolver.py` |
| 6 | 75% | `agent/mission.py` ↔ `surface_resolver.py` |
| 3 | 75% | `_read_path_resolver.py` ↔ `feature_dir_resolver.py` |
| 13 | 68% | `agent/mission.py` ↔ `core/mission_creation.py` |
| 7 | 64% | `implement.py` ↔ `branch_naming.py` |

> **`feature_dir_resolver.py` never moves alone** — every one of its 4 commits co-changes with a
> consumer (100% with merge, 75% with `_read_path_resolver`). Confirmed thin-shim behaviour: it
> exists only to be re-exported, so it churns *reactively*. **Strongest meaningful pair:
> `implement.py` ↔ `worktree_allocator.py` (7 co-changes, 88% degree)** — implement drives the
> allocator on nearly every allocator change; the #1993 `resolve_lanes_dir` extraction sits exactly
> on this seam. `agent/mission.py` ↔ `mission_creation.py` (13 co-changes, 68%) is the create-path
> coupling that WP04's `mission_dir_name` routing targets.

---

## 4. Complexity / size TREND — is the surface accreting?

LOC (and avg CC where radon parsed the historical blob) sampled at intervals via
`git show <sha-before-date>:<path>`. `absent` = file did not exist yet.

| Date | `branch_naming` | `implement` | `core/paths` | `_read_path_resolver` | `merge` | `surface_resolver` |
|---|---|---|---|---|---|---|
| 2025-12-15 | absent | absent | absent | absent | 209 | absent |
| 2026-01-15 | absent | 775 | 148 | absent | 587 | absent |
| 2026-02-15 | absent | 1093 | 212 | absent | 812 | absent |
| 2026-03-15 | absent | 1238 | 262 | absent | 1223 | absent |
| 2026-04-15 | 322 | 693 ↓ | 362 | absent | 1228 | absent |
| 2026-05-15 | 322 | 732 | 498 | absent | 1752 | absent |
| 2026-06-01 | 322 | 925 | 500 | 162 | 2302 | absent |
| **2026-06-16** | **845** | **1375** | **579** | **425** | **3357** | **569** |

**Trend verdicts:**

- **`merge.py` — steepest, relentless monotone accretion: 209 → 3357 LOC (+3148, +1506%) over 7
  months.** Never sheds mass; +1055 LOC in the last 2 weeks alone. This is the clearest "never
  settled" growth curve on the surface and the strongest standalone refactor signal (it pairs with
  rank-4 hotspot + maxCC 102).
- **`branch_naming.py`: 322 → 845 (+523) — but this is the 3.2.0 squash seam-consolidation jump**
  (`fcf9be595`, confirmed via per-file log), i.e. accretion *by absorbing duplicated logic into one
  authority* — **healthy consolidation, not sprawl** (avgCC stayed 2.7–3.3 throughout).
- **`core/paths.py`: 148 → 579 (+291%), monotone** — the project-root authority steadily absorbing
  the 3-tier `SPECIFY_REPO_ROOT` / worktree / `.kittify` logic (#1965/#1971). Accreting but *toward*
  SSOT; maxCC 19 says it is near the worth-watching line.
- **`_read_path_resolver.py`: 162 → 425 (+162% in 16 days)** — youngest and *fastest-growing*
  surface file. Born 2026-05-28, already the read-path SSOT, growing faster per-day than anything
  else. The #1993 extraction will add to it; watch it does not become the next god-resolver.
- **`implement.py`: sawtooth** (1238 Mar → 693 Apr extraction → 1375 now) — a refactor split it,
  then it re-accreted past its pre-split size. Re-growth after extraction is the OVERVIEW's
  "re-strangle" risk made visible.

---

## 5. Age / stability — volatile vs settled

`first` = first commit touching the path; `last` = most recent; `daysSinceTouch` from HEAD date.

| File | First touch | Last touch | Span (days) | Days since touch |
|---|---|---|---|---|
| `lanes/branch_naming.py` | 2026-04-04 | 2026-06-16 | 72 | 0 |
| `lanes/worktree_allocator.py` | 2026-04-04 | 2026-06-16 | 72 | 0 |
| `core/paths.py` | 2025-12-17 | 2026-06-15 | 179 | 0 |
| `core/project_resolver.py` | 2025-11-11 | 2026-06-15 | 216 | 0 |
| `__init__.py` | 2025-08-22 | 2026-06-08 | 289 | 7 |
| `missions/_read_path_resolver.py` | 2026-05-28 | 2026-06-16 | 18 | 0 |
| `missions/feature_dir_resolver.py` | 2026-06-04 | 2026-06-12 | 7 | 3 |
| `coordination/surface_resolver.py` | 2026-06-06 | 2026-06-16 | 9 | 0 |
| `coordination/workspace.py` | 2026-05-28 | 2026-06-16 | 18 | 0 |
| `cli/commands/implement.py` | 2026-01-11 | 2026-06-16 | 155 | 0 |
| `cli/commands/merge.py` | 2025-11-11 | 2026-06-16 | 216 | 0 |
| `ownership/validation.py` | 2026-03-30 | 2026-06-15 | 77 | 0 |
| `core/mission_creation.py` | 2026-04-06 | 2026-06-12 | 66 | 3 |
| `core/worktree.py` | 2025-12-17 | 2026-06-13 | 177 | 2 |
| `cli/commands/agent/mission.py` | 2026-04-06 | 2026-06-16 | 70 | 0 |
| `cli/commands/agent/workflow.py` | 2025-12-30 | 2026-06-16 | 167 | 0 |
| `cli/commands/agent/status.py` | 2026-02-08 | 2026-06-15 | 127 | 0 |
| `cli/commands/agent/tasks.py` | 2025-12-17 | 2026-06-16 | 180 | 0 |

> **The entire surface is volatile — nothing is settled.** Every file was touched within the last
> **7 days** (most within 0–2). There are no "cold, stable" refactor-safe candidates on this surface;
> the whole naming/identity/coord seam is *actively in flux*, which is consistent with a strangler
> mid-flight. The youngest files (`feature_dir_resolver` 7d, `surface_resolver` 9d,
> `_read_path_resolver`/`workspace` 18d) are the freshly-minted SSOT layer — born during the
> consolidation, not yet hardened. **Implication for sequencing:** because everything is hot, any WP
> here will collide with concurrent activity; the OVERVIEW's "ratchet-before-code, byte-identical"
> discipline is the right hedge against the volatility this table quantifies.

---

## 6. Synthesis — what the temporal evidence adds to the static read

The static squad mapped *where the duplication is*. The git history says *which duplication actually
hurt*, and the answer refines the mission shape:

1. **The seam is cold; the consumers are the crime scene.** Hotspot ranks 1–5 and naming-class-fix
   density both point at the lifecycle CLI orchestrators (`tasks`/`mission`/`workflow`/`merge`/
   `implement`), not at `branch_naming.py`/`_read_path_resolver.py`. The 3.2.0 consolidation
   succeeded in making the *authority* simple (maxCC ≤ 8); the remaining risk is the **un-routed
   callers** — which is exactly WP02–WP04's "route the composes/mid8 through the seam" work. The
   data validates the OVERVIEW's "verify-and-close the seam, route the consumers" framing over a
   re-implementation.
2. **The 5-orchestrator coupling clique (§3a) is the fan-out the strangler must break.** 18–56
   co-changes per pair quantifies the "duplicated per command" fallback ladders. Every WP that
   leaves logic inline these files keeps the clique alive.
3. **`merge.py` is an independent, untreated growth problem** (steepest trend, rank-4 hotspot,
   maxCC 102) that this naming mission only *touches* (#1878 write-side is explicitly out of scope).
   Flag it: it is accreting faster than it is being consolidated, and the deferred #1878 mission
   will inherit a bigger module the longer it waits.
4. **Watch `_read_path_resolver.py`'s growth rate** — fastest-accreting file, and WP02 (#1993) adds
   to it. The dataclass-return discipline the OVERVIEW prescribes is what keeps it from becoming the
   next 220-maxCC god-resolver.

---

## Appendix — reproduction commands (DIR-003)

```bash
# Surface set: 14 prompt files + agent/{mission,workflow,status,tasks}.py  (/tmp/surface_files.txt)

# Churn (commits) + windows
git log --no-merges --format='%H' -- <file> | wc -l                 # full
git log --no-merges --since="1 year ago" --format='%H' -- <file> | wc -l

# Lines churned
git log --no-merges --numstat --format='' -- <file> \
  | awk '$3!=""{a+=$1;d+=$2} END{print a, d}'

# Complexity overlay
<path-to-radon> cc -a <file>          # avgCC, blocks
<path-to-radon> cc -j <file>          # max-block CC (parsed)
<path-to-radon> mi -s <file>          # MI

# Defect density (raw) + naming-class (discriminating)
git log --no-merges -i -E --grep='fix|bug|broken|regress|hotfix|revert' --format='%H' -- <file> | wc -l
git log --no-merges -i -E \
  --grep='mid8|branch.?nam|worktree.?nam|split.?brain|orphan|project.?root|read.?path|resolver|identity.?seam' \
  --format='%H' -- <file> | wc -l

# Change-coupling: per-commit surface-file sets → itertools.combinations pairs
git log --no-merges --name-only --format=__C__%H                    # parsed in python (see §3)

# Complexity/size trend
sha=$(git rev-list -1 --before="<date> 23:59" HEAD); git show "$sha:<file>" | wc -l

# Age/recency
git log --reverse --format='%ad' --date=short -- <file> | head -1   # first
git log --format='%at' -- <file> | head -1                          # last (epoch)

# Firefighting
git log --no-merges -i --grep='revert'  --format='%h' | wc -l       # 31
git log --no-merges -i --grep='hotfix'  --format='%h' | wc -l       # 11
```
