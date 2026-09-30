---
title: spec-kitty CaaCS Audit — 2026-05
description: 'The full 2026-05 Code-as-a-Crime-Scene forensic audit of the spec-kitty repository: metadata, hotspot findings, and the bus-factor and complexity observations.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# spec-kitty CaaCS Audit — 2026-05

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states and milestones below are as of May 2026, and any reference to a 3.3 milestone is void (3.3.x was retired on 2026-08-23). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

## Audit metadata

- **Repository**: `spec-kitty` (fork at `<repo-root>`)
- **Branch**: `feat/caacs-doctrine`
- **Commit SHA at audit time**: `bc64dec6ee37dbbd6bc21a0a1aa3195f2bab1b57`
- **Audit date**: 2026-05-08
- **Window**: 1 year (`--since="1 year ago"`); velocity uses 2 years
- **Scope**: `src/` only (`src/specify_cli/`, `src/doctrine/`, `src/charter/`, `src/kernel/`,
  plus three empty leftover dirs `src/runtime/`, `src/dashboard/`, `src/constitution/` that
  contain only `__pycache__/` and are flagged as cleanup candidates).
- **Exclusion list applied** (vanity / generated / non-code):
  `**/__pycache__/**`, `**/.mypy_cache/**`, `**/CHANGELOG*.md`, `**/*.lock`,
  `uv.lock`, `poetry.lock`. Generated agent directories (`.claude/`, `.amazonq/`, etc.)
  live outside `src/` and are naturally excluded by the scope filter.
  No `**/*.json` exclusion was applied because there are very few JSON files in `src/`
  and they are intentional (schemas, manifests, `default-toolguides.json`); excluding
  them would have hidden two legitimately churning schema files.
- **Tooling**: `git` 2.x, Python 3.13.12, `radon` 6.0.1. `cloc` is not installed on
  this machine, so SLOC counts use `wc -l` instead (acceptable for the Python-only
  scope; documented under "Limitations").
- **Producer**: researcher subagent ("Reza"), instructed by the
  `forensic-repository-audit` tactic and `legacy-codebase-triage` procedure on
  this branch. Not architect-reviewed.

## Methodology

The five core CaaCS recipes from the
[`forensic-repository-audit`](../../../../../packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml)
tactic were executed verbatim against `src/`, with the exclusion list above
applied. The procedure
[`legacy-codebase-triage`](../../../../../packs/built-in/procedures/legacy-codebase-triage.procedure.yaml)
specifies the additional steps (temporal coupling, complexity overlay, DDD-tentative
classification, Eisenhower triage). The exact commands run are:

```bash
# 1. Churn (top 50)
git log --format=format: --name-only --since="1 year ago" -- src/ \
   ':!**/CHANGELOG*.md' ':!**/__pycache__/**' ':!**/*.lock' ':!**/uv.lock' \
   ':!**/poetry.lock' ':!**/.mypy_cache/**' \
  | grep -v '^$' | sort | uniq -c | sort -nr | head -50

# 2. Bus factor (overall + per top-15 hotspot)
git log --no-merges --since="1 year ago" --format='%an' -- src/ \
  | sort | uniq -c | sort -nr
git log --since="1 year ago" --no-merges --format='%an' --follow -- <file> \
  | sort | uniq -c | sort -nr   # per file

# 3. Bug hotspots
git log -i -E --grep="fix|bug|broken|regress|hotfix" --since="1 year ago" \
   --name-only --format='' --no-merges -- src/ <exclusions> \
  | grep -v '^$' | sort | uniq -c | sort -nr

# 4. Velocity (2y, monthly)
git log --since="2 years ago" --format='%ad' --date=format:'%Y-%m' --no-merges -- src/ \
  | sort | uniq -c

# 5. Firefighting
git log --oneline --since="1 year ago" --no-merges -- src/ \
  | grep -iE 'revert|hotfix|emergency|rollback'

# 6. Temporal coupling: Python script (/tmp/caacs/coupling.py) walks
#    `git log --no-merges --since="1y" --name-only --format=__COMMIT__%H -- src/`,
#    emits all unordered file-pairs per multi-file commit, counts.

# 7. Complexity (Python only)
radon cc -a -s --total-average src/specify_cli src/doctrine src/charter src/kernel
radon mi -s src/specify_cli src/doctrine src/charter src/kernel | grep -E " - [BC] "
```

### Inherited biases (per the tactic's failure_modes)

| Bias | Effect on this audit |
|------|----------------------|
| Squash-merge distortion | Repo uses both squash and non-squash merges (mixed history). Velocity counts upstream activity reasonably faithfully; PR-level metadata not consulted. |
| Weak commit messages | Conventional Commits dominate (`fix:`, `feat:`, `refactor:`, `docs:`). The fix-grep matches body too — a few false positives (e.g. spec commits that contain "fix" in prose). Spot-checked, false-positive rate is low. |
| Vanity-file dominance | Lockfiles, `__pycache__`, CHANGELOG excluded. Spot-checked top 4 hotspots for insertion/deletion ratio — all show substantive code change, not formatting noise. |
| No rename-following by default | The bulk recipes do **not** follow renames. Per-file authorship for top-15 hotspots used `--follow`. Three known renames in this window (`acceptance.py` → `acceptance/__init__.py`, `dashboard.py` → `cli/commands/dashboard.py`, `cli/commands/agent/feature.py` deleted in `7428880c4`) split history; documented in the hotspot table. |
| No complexity capture in raw git data | Mitigated via `radon` overlay (Python-only). |
| Bus factor is a question, not a verdict | This audit treats single-author concentration as an open question. |

## Scope expansion (2026-05-09)

This audit was originally scoped to `src/` only. On 2026-05-09 the scope was
broadened to `src/ + tests/ + kitty-specs/` to address the two largest blind
spots flagged in the original "Limitations" section: (1) absence of a test-
coverage overlay on the F-rated functions, and (2) inability to see
`kitty-specs/<mission>/` ↔ `src/` temporal coupling.

**What changed**

- **Scope:** `src/` → `src/ + tests/ + kitty-specs/`
- **Additional vanity exclusions** required by the expanded corpus:
  `**/status.events.jsonl`, `**/status.json`, `kitty-specs/**/tasks.md`
  (mission-state churn, not authoring), `kitty-specs/**/snapshot-latest.json`,
  `kitty-specs/**/dossiers/**` (dossier state files). The original exclusions
  (lockfiles, `__pycache__`, `CHANGELOG.md`, `.mypy_cache`) are retained.
- **Window unchanged:** still 1 year for churn / hotspots, 2 years for velocity.
- **Commit at re-run:** `81883352240c3f8e0249b78875f7fa140700418f` (HEAD on
  `feat/caacs-doctrine` advanced since the original run; original tables below
  reflect SHA `bc64dec6`, the broader-scope tables in this section reflect the
  newer SHA. The 1y window means the two windows overlap by ~364 days; observed
  shape is consistent.).

**Headline impact**

- **F1 (bus factor) — *worse*.** Single-author concentration rises from
  **89.5% → 95.2%** when tests and missions are folded in. Robert Douglass
  authored 2613 of 2744 commits across the full corpus. F1 is reaffirmed and
  intensified.
- **F2 (hotspot list) — *unchanged*.** The top-30 src/ files are identical;
  the extra rows that surface in the full-corpus view are tests and mission
  artifacts that *belong* to those same hotspots (e.g. `tests/sync/test_events.py`
  next to `sync/emitter.py`, `kitty-specs/041-…/tasks/WP*.md` next to
  `glossary/*`). The hotspot diagnosis is **stable under scope expansion**.
- **New findings** (F15–F18): test-update lag on agent/* hotspots,
  glossary middleware as an under-tested hotspot, mission/code temporal
  coupling is **commit-level decoupled by design** (separate phases), and the
  glossary subsystem cluster (mission 041 + `src/specify_cli/glossary/`) is the
  second densest coupling cluster after agent/.

**Executive summary (one paragraph)**

Broadening the scope confirms — and somewhat sharpens — every finding from the
src/-only run. The 95.2% bus factor is the headline change; tests and mission
artifacts do not dilute the lone-author signal because the same author wrote
them too. The hotspot list does not move, which is reassuring (the recipes
are robust). The new signal worth acting on is the **test-update lag** on the
F2 cluster: `agent/tasks.py` and `agent/workflow.py` change with their tests
only ~30% of the time — i.e. ~70% of changes ship without test updates.
Combined with their F-rated complexity that's a non-trivial regression risk.
Mission ↔ code temporal coupling at the commit level is sparse (max 3
co-changes per pair) because the SDD pipeline deliberately separates planning
commits from implementation commits — that's not a defect, it's the design,
but it means the mission-driven causal coupling is invisible to single-commit
recipes and would need PR-grouping or trailer-based attribution to see clearly.

## Top findings (executive summary)

1. **Project is very alive but contributor-monopolised.** 1001 commits to `src/` in
   the last year, accelerating in 2026 (288 commits in Feb alone). One author
   (Robert Douglass) authored **89.5%** of all `src/` commits in the window
   (896 / 1001). Of the top 15 hotspots, 14 are >90% single-author. Bus factor is
   effectively 1 across the whole codebase. This is the dominant risk surfaced by
   the audit.
2. **`src/specify_cli/cli/commands/agent/` is a refactor target.** Three files
   (`tasks.py` — 3746 SLOC; `workflow.py` — 1895 SLOC; `mission.py` — 2314 SLOC)
   together hold five of the seven worst-complexity functions in the repo
   (`finalize_tasks` CC=160, `move_task` CC=139, `status` CC=87, `review` CC=84,
   `map_requirements` CC=74). They are also the top-three temporal-coupling
   pair (45 co-changes between `tasks.py` and `workflow.py` alone) and dominate
   the bug-hotspot table. **Both unstable and known-defective** = strongest refactor
   candidate the recipes can produce.
3. **Firefighting frequency is low (~0.8% of commits).** Eight matches across a
   year (2 reverts, 1 explicit hotfix, 5 "rollback" mentions that are
   feature-implementation references rather than emergency fixes). The team
   appears to trust the pipeline — this is a **healthy** signal that contradicts
   the "monopolised" risk above. The risk lives in knowledge transfer, not in
   merge discipline.
4. **Mission-template files churn alongside the CLI commands that consume them.**
   `software-dev/command-templates/{specify,plan,tasks,implement,review,tasks-packages}.md`
   appear in the top-30 hotspots and co-change with the agent commands (e.g.
   `tasks.md` ↔ `tasks.py`: 18 co-changes, `specify.md` ↔ `agent/tasks.py`: 12).
   This is **expected coupling** by design (templates are the contract between
   runtime and mission), not a defect — but it is also evidence that the
   "template + dispatcher" boundary is the load-bearing seam in the system.
5. **Three empty top-level src/ directories are leftovers from the
   shared-package-boundary cutover** (`src/runtime/`, `src/dashboard/`,
   `src/constitution/` contain only stale `__pycache__/`). Per `CLAUDE.md` these
   were either moved into `src/specify_cli/` or extracted to PyPI dependencies.
   Recommend deletion.

## Hotspot table (top 30, vanity-filtered)

### Hotspots — src/ only (original)

`Churn` = commits touching the file in the 1y window. `Bug commits` = subset whose
commit message matches `fix|bug|broken|regress|hotfix` (case-insensitive). `Bus
factor` is the percentage of those churn commits authored by the dominant author
(in every case below: Robert Douglass). `CC max` is the highest-rated cyclomatic
function in the file at HEAD (radon rank in parens). DDD column is
**architect-ratified**.

| # | File | Churn | Bug commits | SLOC | CC max | Top-author share | DDD (architect-ratified) |
|---|------|------:|------------:|-----:|--------|------------------|----------------|
| 1 | `src/specify_cli/__init__.py` | 119 | 25 | 224 | A | 49% (Robert; co-owned w/ Den, honjo, Bruno) | glue (CLI bootstrap) |
| 2 | `src/specify_cli/cli/commands/agent/tasks.py` | 87 | 74 | 3746 | F (160 `finalize_tasks`) | 98% | **core** (mission orchestration) |
| 3 | `src/specify_cli/cli/commands/agent/workflow.py` | 77 | 67 | 1895 | F (84 `review`) | 96% | **core** (lane/workflow dispatch) |
| 4 | `src/specify_cli/cli/commands/implement.py` | 67 | 55 | 718 | F (44) | 97% | **core** (workspace resolution) |
| 5 | `src/specify_cli/cli/commands/merge.py` | 56 | 42 | 1599 | F (63 `_run_lane_based_merge_locked`) | 96% | **core** (merge state machine) |
| 6 | `src/specify_cli/cli/commands/agent/feature.py` | 56 | 43 | DELETED | n/a | 100% | glue (deleted in `7428880c4`, mission-id cutover) |
| 7 | `src/specify_cli/cli/commands/init.py` | 50 | 28 | 1018 | F (94 `init`) | 96% | supporting (project bootstrap) |
| 8 | `src/specify_cli/cli/commands/__init__.py` | 48 | 23 | 115 | A | 96% | glue (wiring) |
| 9 | `src/specify_cli/sync/emitter.py` | 42 | 30 | 1682 | C (avg) MI=C | 93% | supporting (SaaS sync) |
| 10 | `src/specify_cli/missions/software-dev/command-templates/specify.md` | 38 | 28 | n/a (markdown) | n/a | n/a | **core** (SDD methodology contract) |
| 11 | `src/specify_cli/cli/commands/sync.py` | 36 | 23 | 1462 | MI=C | 97% | supporting (sync CLI) |
| 12 | `src/specify_cli/missions/software-dev/command-templates/tasks.md` | 33 | 27 | n/a | n/a | n/a | **core** (SDD methodology contract) |
| 13 | `src/specify_cli/cli/commands/dashboard.py` | 33 | 24 | 142 (renamed from `dashboard.py`) | n/a | 100% | glue (CLI shim) |
| 14 | `src/specify_cli/glossary/middleware.py` | 36 | 19 | 689 | n/a | 100% | supporting (glossary) |
| 15 | `src/specify_cli/dashboard/static/dashboard/dashboard.js` | 29 | 21 | n/a | n/a | n/a | supporting (UI) |
| 16 | `src/specify_cli/dashboard/scanner.py` | 28 | 24 | 785 | n/a | 93% | supporting (dashboard scanner) |
| 17 | `src/specify_cli/missions/software-dev/command-templates/plan.md` | 27 | 19 | n/a | n/a | n/a | **core** (SDD methodology contract) |
| 18 | `src/specify_cli/missions/software-dev/command-templates/implement.md` | 27 | 21 | n/a | n/a | n/a | **core** (SDD methodology contract) |
| 19 | `src/specify_cli/upgrade/migrations/__init__.py` | 26 | 20 | 89 | n/a | 100% | glue (migration registry) |
| 20 | `src/specify_cli/sync/events.py` | 26 | 19 | 499 | n/a | 96% | supporting (sync envelopes) |
| 21 | `src/specify_cli/next/runtime_bridge.py` | 26 | 25 | 2552 | F (46) MI=C | 96% | **core** (mission-next runtime bridge) |
| 22 | `src/specify_cli/tasks_support.py` | 25 | 17 | 31 | A | 100% | glue (re-export shim) |
| 23 | `src/specify_cli/status/emit.py` | 25 | 22 | 656 | E (40 batch) | 100% | **core** (status state machine) |
| 24 | `src/specify_cli/core/worktree.py` | 25 | 20 | 681 | n/a | 96% | **core** (git worktree mgmt) |
| 25 | `src/specify_cli/glossary/__init__.py` | 24 | 13 | n/a | n/a | 100% | supporting (glossary entrypoint) |
| 26 | `src/specify_cli/cli/commands/charter.py` | 23 | 18 | 2934 | E (38 `interview`) MI=C | 100% | supporting (charter CLI) |
| 27 | `src/specify_cli/acceptance.py` (now `acceptance/__init__.py`) | 22 | 17 | 793 | MI=B | 100% | supporting (acceptance workflow) |
| 28 | `src/specify_cli/orchestrator_api/commands.py` | 21 | 17 | 1097 | n/a | 100% | **core** (external orchestration API) |
| 29 | `src/specify_cli/agent_utils/status.py` | 21 | 15 | 570 | F (53 `_display_status_board`) | 100% | supporting (kanban renderer) |
| 30 | `src/specify_cli/cli/commands/agent/status.py` | 20 | 14 | 886 | n/a | 100% | supporting (status CLI) |

**Cross-reference (procedure exit condition):** files appearing in both top-10
churn and top-10 bug-hotspot lists are the strongest refactor candidates per the
tactic. That set is:
`agent/tasks.py`, `agent/workflow.py`, `implement.py`, `merge.py`, `agent/feature.py`
(deleted), `init.py`, `commands/__init__.py`, `sync/emitter.py`, `cli/commands/sync.py`.

> **DDD classifications above were ratified by Architect Alphonso (Stijn
> Dejongh) on 2026-05-08; the column may now be treated as authoritative
> for this audit run. Revisions and rationales are listed in the
> "DDD ratification notes (architect)" subsection below.**

### DDD ratification notes (architect)

- `src/specify_cli/missions/software-dev/command-templates/specify.md`: tentative=`supporting` → ratified=`core` — Mission templates encode the SDD methodology itself; they are the user-facing contract that differentiates spec-kitty from generic CLI scaffolders.
- `src/specify_cli/missions/software-dev/command-templates/tasks.md`: tentative=`supporting` → ratified=`core` — Same rationale as `specify.md`; the WP-decomposition contract is part of spec-kitty's differentiating methodology.
- `src/specify_cli/missions/software-dev/command-templates/plan.md`: tentative=`supporting` → ratified=`core` — Same rationale; the plan template is a load-bearing piece of the SDD pipeline contract, not a swappable doc fragment.
- `src/specify_cli/missions/software-dev/command-templates/implement.md`: tentative=`supporting` → ratified=`core` — Same rationale; defines the lane-aware execution handshake that no off-the-shelf tool replicates.
- `src/specify_cli/acceptance/__init__.py`: tentative=`core` → ratified=`supporting` — Acceptance gating is a common workflow-tool pattern; the differentiating state-machine logic lives in `status/emit.py` and the merge pipeline, not here.

### Hotspots — full corpus (src/ + tests/ + kitty-specs/)

Same 1y window. Same exclusions as src/-only **plus**: `**/status.events.jsonl`,
`**/status.json`, `kitty-specs/**/tasks.md`, `kitty-specs/**/snapshot-latest.json`,
`kitty-specs/**/dossiers/**`. `Origin` = which top-level directory the file
lives in.

| # | File | Churn | Origin | Note |
|---|------|------:|--------|------|
| 1 | `src/specify_cli/__init__.py` | 119 | src | unchanged from src/-only |
| 2 | `src/specify_cli/cli/commands/agent/tasks.py` | 87 | src | F2 hotspot |
| 3 | `src/specify_cli/cli/commands/agent/workflow.py` | 77 | src | F2 hotspot |
| 4 | `src/specify_cli/cli/commands/implement.py` | 67 | src | F2 hotspot |
| 5 | `src/specify_cli/cli/commands/merge.py` | 56 | src | F2 hotspot |
| 6 | `src/specify_cli/cli/commands/agent/feature.py` | 55 | src | deleted, pre-cutover hotspot |
| 7 | `src/specify_cli/cli/commands/init.py` | 50 | src |  |
| 8 | `src/specify_cli/cli/commands/__init__.py` | 47 | src | wiring |
| 9 | `src/specify_cli/sync/emitter.py` | 42 | src |  |
| 10 | `src/specify_cli/missions/software-dev/command-templates/specify.md` | 38 | src |  |
| 11 | `src/specify_cli/glossary/middleware.py` | 36 | src |  |
| 12 | `src/specify_cli/cli/commands/sync.py` | 36 | src |  |
| 13 | `src/specify_cli/missions/software-dev/command-templates/tasks.md` | 33 | src |  |
| 14 | `src/specify_cli/dashboard.py` | 33 | src | renamed → `cli/commands/dashboard.py` |
| 15 | `src/specify_cli/dashboard/static/dashboard/dashboard.js` | 29 | src | UI |
| 16 | `src/specify_cli/sync/events.py` | 28 | src |  |
| 17 | `src/specify_cli/dashboard/scanner.py` | 28 | src |  |
| 18 | `src/specify_cli/missions/software-dev/command-templates/plan.md` | 27 | src |  |
| 19 | `src/specify_cli/missions/software-dev/command-templates/implement.md` | 27 | src |  |
| 20 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP03-term-extraction-implementation.md` | 27 | kitty-specs | **first non-src/ entry**; glossary mission |
| 21 | `src/specify_cli/upgrade/migrations/__init__.py` | 26 | src |  |
| 22 | `src/specify_cli/next/runtime_bridge.py` | 26 | src |  |
| 23 | `src/specify_cli/glossary/__init__.py` | 26 | src |  |
| 24 | `src/specify_cli/tasks_support.py` | 25 | src |  |
| 25 | `src/specify_cli/status/emit.py` | 25 | src |  |
| 26 | `src/specify_cli/core/worktree.py` | 25 | src |  |
| 27 | `tests/sync/test_events.py` | 24 | tests | **first tests/ entry**; sync hotspot's test |
| 28 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP11-type-safety-and-integration-tests.md` | 24 | kitty-specs | glossary mission again |
| 29 | `src/specify_cli/cli/commands/charter.py` | 23 | src |  |
| 30 | `src/specify_cli/acceptance.py` | 22 | src |  |

**Interpretation:** the top-19 of the full-corpus table is **identical** to
the src/-only top-19. The first non-src/ entry is rank 20: a single mission's
WP file (mission 041, glossary semantic integrity, has 11 task files all in
the top-100). This is mission 041 doing what missions are supposed to do —
churning through revisions before being merged — *not* a hotspot in the
"buggy file" sense. Rank 27 is the first `tests/` entry (`test_events.py`),
which sits right next to its source (`sync/emitter.py` at rank 9). Conclusion:
**the F2 hotspot list is robust under scope expansion** — broadening to the
full corpus does not surface new structural hotspots; it surfaces (a) a
single high-revision mission and (b) tests that already track their hot
sources. F2 stands.

## Temporal coupling (top 30 pairs, both files non-vanity)

Source: 586 multi-file `src/`-only commits in the 1y window. 239,639 unique pairs
emitted (Cartesian product is large; we sliced top 30).

| # | Co-changes | File A | File B | Note |
|---|-----------:|--------|--------|------|
| 1 | 45 | `cli/commands/agent/tasks.py` | `cli/commands/agent/workflow.py` | Internal `agent/` cluster |
| 2 | 34 | `cli/commands/agent/tasks.py` | `cli/commands/implement.py` | Mission orchestration ↔ implementation dispatch |
| 3 | 29 | `cli/commands/agent/workflow.py` | `cli/commands/implement.py` | Same cluster |
| 4 | 26 | `cli/commands/implement.py` | `cli/commands/merge.py` | Workspace-lifecycle pair |
| 5 | 22 | `cli/commands/agent/tasks.py` | `cli/commands/merge.py` | Same cluster |
| 6 | 22 | `missions/software-dev/command-templates/plan.md` | `…/specify.md` | Mission templates co-evolve |
| 7 | 21 | `…/specify.md` | `…/tasks.md` | Mission templates co-evolve |
| 8 | 21 | `cli/commands/agent/feature.py` | `cli/commands/agent/tasks.py` | Pre-cutover coupling (`feature.py` deleted) |
| 9 | 20 | `sync/emitter.py` | `sync/events.py` | Sync envelope ↔ emitter (expected) |
| 10 | 19 | `cli/commands/agent/feature.py` | `cli/commands/agent/workflow.py` | Pre-cutover |
| 11 | 18 | `cli/commands/agent/tasks.py` | `missions/software-dev/command-templates/tasks.md` | **Template ↔ dispatcher seam** |
| 12 | 18 | `cli/commands/agent/feature.py` | `cli/commands/implement.py` | Pre-cutover |
| 13 | 17 | `cli/commands/agent/workflow.py` | `cli/commands/merge.py` | Same cluster |
| 14 | 17 | `cli/commands/agent/workflow.py` | `…/tasks.md` | **Template ↔ dispatcher seam** |
| 15 | 16 | `…/plan.md` | `…/tasks.md` | Mission templates co-evolve |
| 16 | 15 | `…/implement.md` | `…/review.md` | Mission templates co-evolve |
| 17 | 15 | `cli/commands/accept.py` | `cli/commands/implement.py` | Lifecycle pair |
| 18 | 15 | `cli/commands/agent/workflow.py` | `…/specify.md` | **Template ↔ dispatcher seam** |
| 19 | 15 | `cli/commands/implement.py` | `…/tasks.md` | **Template ↔ dispatcher seam** |
| 20 | 15 | `missions/software-dev/templates/task-prompt-template.md` | `templates/task-prompt-template.md` | **Duplicated template** (two locations co-edited) |
| 21 | 15 | `cli/commands/agent/feature.py` | `…/tasks.md` | Pre-cutover |
| 22 | 14 | `agent_utils/status.py` | `cli/commands/agent/tasks.py` | Status renderer ↔ status owner |
| 23 | 14 | `cli/commands/accept.py` | `cli/commands/merge.py` | Lifecycle pair |
| 24 | 14 | `cli/commands/agent/tasks.py` | `core/worktree.py` | Mission orchestration ↔ git worktree |
| 25 | 14 | `cli/commands/agent/workflow.py` | `core/worktree.py` | Same |
| 26 | 14 | `cli/commands/agent/feature.py` | `cli/commands/merge.py` | Pre-cutover |
| 27 | 13 | `dashboard/scanner.py` | `dashboard/static/dashboard/dashboard.js` | UI ↔ scanner (expected) |
| 28 | 13 | `…/tasks-packages.md` | `…/tasks.md` | Templates |
| 29 | 13 | `…/tasks-outline.md` | `…/tasks-packages.md` | Templates |
| 30 | 13 | `cli/commands/merge.py` | `core/worktree.py` | Merge ↔ worktree (expected) |

**Cluster signal:** the `agent/{tasks,workflow,feature}.py` ↔ `implement.py` ↔
`merge.py` ↔ `core/worktree.py` graph contains the densest coupling. Of the top-30
pairs, **22 involve at least one of those six files**. This is the system's
load-bearing transaction (mission state ↔ git worktree).

**Anomaly worth a question:** pair #20 — `missions/software-dev/templates/task-prompt-template.md`
co-edited 15 times with `templates/task-prompt-template.md`. **Why does the same
template exist in two locations and require synchronised edits?** This is a
candidate for connascence-of-meaning analysis (likely a stale duplicate after a
template-resolver chain change).

## Cross-cutting temporal coupling (mission ↔ src/ ↔ tests/) (2026-05-09)

The src/-only run could not see two important coupling kinds: (a) mission
spec ↔ source-file co-changes, and (b) source-file ↔ matching-test co-changes.
Both are computed here on the full corpus.

### Mission-directory ↔ src-file co-changes (top 20)

For each commit, all files in `kitty-specs/<mission>/` are collapsed to a
single token (the mission directory) and paired with each touched `src/` file.
Counts are deliberately low because the SDD pipeline lands planning commits
and implementation commits separately by design — a co-change here means
both the spec and the code were touched in the same commit (e.g. a fix that
also amended the spec, or an implementation commit that adjusted spec
metadata).

| # | Co-changes | Mission directory | Src file/dir |
|---|-----------:|-------------------|--------------|
| 1 | 5 | `012-documentation-mission/` | `src/specify_cli/cli/commands/` (any file) |
| 2 | 5 | `010-workspace-per-work-package-for-parallel-development/` | `src/specify_cli/cli/commands/` |
| 3 | 4 | `008-unified-python-cli/` | `src/specify_cli/cli/commands/` |
| 4 | 3 | `auth-local-trust-and-multi-process-hardening-01KQW587/` | `src/specify_cli/auth/token_manager.py` |
| 5 | 3 | `auth-local-trust-and-multi-process-hardening-01KQW587/` | `src/specify_cli/auth/session_hot_path.py` |
| 6 | 3 | `064-complete-mission-identity-cutover/` | `src/specify_cli/missions/software-dev/` |
| 7 | 3 | `067-runtime-recovery-and-audit-safety/` | `src/specify_cli/missions/software-dev/` |
| 8 | 3 | `065-tasks-and-lane-stabilization/` | `src/specify_cli/missions/software-dev/` |
| 9 | 3 | `unified-charter-bundle-chokepoint-01KP5Q2G/` | `src/specify_cli/upgrade/migrations/` |
| 10 | 3 | `phase-3-charter-synthesizer-pipeline-01KPE222/` | `src/charter/synthesizer/synthesize_pipeline.py` |
| 11 | 3 | `phase-3-charter-synthesizer-pipeline-01KPE222/` | `src/charter/synthesizer/errors.py` |
| 12 | 3 | `phase-3-charter-synthesizer-pipeline-01KPE222/` | `src/charter/synthesizer/write_pipeline.py` |
| 13 | 3 | `005-refactor-mission-system/` | `src/specify_cli/cli/commands/` |
| 14 | 3 | `008-unified-python-cli/` | `src/specify_cli/upgrade/migrations/` |
| 15 | 3 | `004-modular-code-refactoring/` | `src/specify_cli/cli/commands/` |
| 16 | 3 | `025-cli-event-log-integration/` | `src/specify_cli/cli/commands/` |
| 17 | 3 | `010-workspace-per-work-package-for-parallel-development/` | `src/specify_cli/upgrade/migrations/` |
| 18 | 3 | `011-constitution-packaging-safety-and-redesign/` | `src/specify_cli/upgrade/migrations/` |
| 19 | 3 | `015-first-class-jujutsu-vcs-integration/` | `src/specify_cli/cli/commands/` |
| 20 | 3 | `010-workspace-per-work-package-for-parallel-development/` | `src/specify_cli/core/worktree.py` |

**Interpretation:** the maximum is 5 co-changes/year for any
mission ↔ src pair. That is *very* low compared with the in-`src/` pairs
(top pair = 45 co-changes/y). This means **mission-driven causal coupling
is invisible to commit-level recipes** — the SDD pipeline works as designed,
landing spec edits and code edits in separate commits. To see the real
mission ↔ code coupling we'd need PR-level grouping, branch-level
attribution, or trailer-based association (e.g. `Mission: 041`). Treat this
table as a sanity check (no surprising couplings) rather than a refactor
signal.

The clusters that *do* surface are revealing as **secondary structure**: the
charter synthesizer phase-3 mission cluster (rows 10–12) shows three
synthesizer modules co-changing with their mission spec — that's the
expected pattern when a mission is genuinely active. The auth hardening
mission (rows 4–5) shows the same pattern for `auth/`. Mission 010
(workspace-per-WP) ↔ `core/worktree.py` (row 20) is the strongest *specific*
file coupling and is also expected by design.

### src-file ↔ test-file co-changes (top 20)

Per-pair count of commits touching both a `src/` file and a `tests/` file:

| # | Co-changes | Src file | Test file |
|---|-----------:|----------|-----------|
| 1 | 13 | `sync/emitter.py` | `tests/sync/test_events.py` |
| 2 | 12 | `cli/commands/agent/feature.py` | `tests/specify_cli/test_cli/test_agent_feature.py` |
| 3 | 12 | `glossary/extraction.py` | `tests/specify_cli/glossary/test_extraction.py` |
| 4 | 11 | `dashboard/scanner.py` | `tests/test_dashboard/test_scanner.py` |
| 5 | 11 | `glossary/middleware.py` | `tests/specify_cli/glossary/test_middleware.py` |
| 6 | 9 | `glossary/scope.py` | `tests/specify_cli/glossary/test_scope.py` |
| 7 | 8 | `sync/emitter.py` | `tests/sync/test_event_emission.py` |
| 8 | 8 | `sync/events.py` | `tests/sync/test_event_emission.py` |
| 9 | 8 | `sync/events.py` | `tests/sync/test_events.py` |
| 10 | 8 | `glossary/models.py` | `tests/specify_cli/glossary/test_models.py` |
| 11 | 7 | `sync/batch.py` | `tests/sync/test_batch_sync.py` |
| 12 | 7 | `sync/emitter.py` | `tests/sync/conftest.py` |
| 13 | 7 | `cli/commands/agent/tasks.py` | `tests/integration/test_task_workflow.py` |
| 14 | 7 | `status/transitions.py` | `tests/specify_cli/status/test_transitions.py` |
| 15 | 7 | `cli/commands/init.py` | `tests/specify_cli/test_cli/test_init_command.py` |
| 16 | 7 | `cli/commands/agent/tasks.py` | `tests/unit/agent/test_tasks.py` |
| 17 | 7 | `runtime/bootstrap.py` | `tests/unit/runtime/test_bootstrap.py` |
| 18 | 7 | `glossary/events.py` | `tests/specify_cli/glossary/test_checkpoint_resume.py` |
| 19 | 7 | `glossary/events.py` | `tests/specify_cli/glossary/test_event_emission.py` |
| 20 | 6 | `dashboard/static/dashboard/dashboard.js` | `tests/test_dashboard/test_static.py` |

**Interpretation:** the `sync/` and `glossary/` subsystems show the healthiest
src ↔ test co-change discipline (rows 1, 3, 4, 5, 6, 8–11, 18, 19 — ten of
the top twenty pairs are in those two subsystems). The `agent/*` cluster is
**conspicuously absent from the top of this table** — `agent/tasks.py`'s
strongest test pair is rank 13 with 7 co-changes, despite the file having 87
churn commits. That's a 8% co-change rate at the strongest-pair level.

### F2 hotspots: change-with-tests rate

For the F2 cluster specifically — how often does a commit that touches the
hotspot also touch a matching test?

| Hotspot | Commits touching file | Also touches matching test | Rate |
|---------|----------------------:|---------------------------:|-----:|
| `cli/commands/agent/tasks.py` | 87 | 26 | **29.9%** |
| `cli/commands/agent/workflow.py` | 77 | 21 | **27.3%** |
| `cli/commands/agent/mission.py` | 19 | 6 | **31.6%** |

**~70% of changes to the F2 cluster ship without a matching test update.**
This is new evidence the src/-only run could not produce. Combined with the
F-rated cyclomatic complexity in those files (CC=160 `finalize_tasks`,
CC=139 `move_task`, CC=87 `status`, CC=84 `review`), this is the strongest
empirical case for a refactor-with-test-build-out on the agent/* cluster.
**F2's priority is upgraded** in the revised triage matrix below.

## Test coverage proxy (2026-05-09)

For each top-20 hotspot, the matching test file(s) were located by name and
churn-compared. `Ratio` = test churn / src churn × 100. Heuristic flags:
**UNTESTED** (no matching test found), **UNDER-TESTED** (ratio < 10%),
**test-heavy** (ratio > 100%, healthy or potentially churny tests).

| Source | src churn | test churn | Ratio | Flag |
|--------|----------:|-----------:|------:|------|
| `cli/commands/agent/tasks.py` | 87 | 19 | 21.8% | **under-tested** |
| `cli/commands/agent/workflow.py` | 77 | 30 | 39.0% | **under-tested** |
| `cli/commands/implement.py` | 67 | 33 | 49.3% | under-tested-ish |
| `cli/commands/merge.py` | 56 | 44 | 78.6% | borderline |
| `cli/commands/init.py` | 50 | 51 | 102.0% | test-heavy (good) |
| `sync/emitter.py` | 42 | 110 | 261.9% | test-heavy (good) |
| `glossary/middleware.py` | 36 | 5 | **13.9%** | **under-tested** |
| `cli/commands/sync.py` | 36 | 110 | 305.6% | test-heavy (good) |
| `dashboard/scanner.py` | 28 | 19 | 67.9% | borderline |
| `next/runtime_bridge.py` | 26 | 50 | 192.3% | test-heavy (good) |
| `upgrade/migrations/__init__.py` | 26 | 34 | 130.8% | test-heavy (good) |
| `glossary/__init__.py` | 24 | 58 | 241.7% | test-heavy (good) |
| `status/emit.py` | 25 | 31 | 124.0% | test-heavy (good) |
| `core/worktree.py` | 25 | 28 | 112.0% | test-heavy (good) |
| `cli/commands/charter.py` | 23 | 34 | 147.8% | test-heavy (good) |
| `acceptance.py` | 22 | 24 | 109.1% | test-heavy (good) |
| `orchestrator_api/commands.py` | 21 | 46 | 219.0% | test-heavy (good) |
| `agent_utils/status.py` | 21 | 4 | **19.0%** | **under-tested** |
| `cli/commands/agent/status.py` | 20 | 18 | 90.0% | borderline |
| `cli/commands/accept.py` | 20 | 21 | 105.0% | test-heavy (good) |

**Three files flagged as under-tested by the ratio rule:**
1. `cli/commands/agent/tasks.py` (21.8%)
2. `cli/commands/agent/workflow.py` (39.0%)
3. `glossary/middleware.py` (13.9%)
4. `agent_utils/status.py` (19.0%)

The first two reinforce F2 — the agent/* cluster needs both a structural
refactor *and* a test-build-out. The third (`glossary/middleware.py`) is a
**new finding** (F16): the glossary subsystem looked healthy in the
src ↔ tests pair table (multiple healthy pairs in `glossary/*`) but
middleware specifically — the dispatch surface — is under-tested relative to
its 36 churn commits. The fourth (`agent_utils/status.py`) is the kanban
renderer with F-53 `_display_status_board`; under-tested at 19% ratio.

**No hotspot from the top-20 is genuinely UNTESTED** (initial heuristic
produced four false-negatives — `acceptance.py`, `orchestrator_api/commands.py`,
`agent/status.py`, `accept.py` — that have tests under non-conventional
names; corrected counts are shown above).

**Caveat:** ratio is a *churn proxy*, not coverage. A file with low test
churn might be tested via integration tests that evolve more slowly than
unit tests. The methodology cannot distinguish "tests don't change because
the source's behavior is stable on the contract surface" from "tests are
neglected." Treat the four under-tested flags as **prompts to verify**,
not verdicts.

## Bus factor / knowledge map

**Overall (1y, src/-only commits):**

| Author | Commits | Share |
|--------|--------:|------:|
| Robert Douglass | 896 | 89.5% |
| Stijn Dejongh | 33 | 3.3% |
| Den Delimarsky 🌺 | 32 | 3.2% |
| honjo-hiroaki-gtt | 5 | 0.5% |
| den (work) | 5 | 0.5% |
| Jerome LACUBE | 3 | 0.3% |
| Jerome Lacube | 3 | 0.3% |
| Bruno Borges | 3 | 0.3% |
| Zhiqiang ZHOU | 2 | 0.2% |
| Tanner | 2 | 0.2% |
| Ram | 2 | 0.2% |
| Brian Anderson | 2 | 0.2% |
| 13 others | 1 each | <0.2% each |

**Per-hotspot single-author share** (top 15, with `--follow`):

| File | Top author share |
|------|-----------------:|
| `__init__.py` | 49% (Robert) — only file with significant co-authorship; reflects 1.x-era contributors (Den, Bruno, honjo) |
| `cli/commands/agent/tasks.py` | 97.7% (Robert; 2 commits Stijn) |
| `cli/commands/agent/workflow.py` | 96.1% (Robert; 2 Stijn, 1 Jerome) |
| `cli/commands/implement.py` | 97.0% (Robert) |
| `cli/commands/merge.py` | 96.4% (Robert) |
| `cli/commands/agent/feature.py` (deleted) | 100% (Robert) |
| `cli/commands/init.py` | 96.0% (Robert) |
| `cli/commands/__init__.py` | 95.8% (Robert) |
| `sync/emitter.py` | 92.9% (Robert; 3 Stijn) |
| `cli/commands/sync.py` | 97.2% (Robert) |
| `cli/commands/dashboard.py` (renamed) | 100% (Robert) |
| `glossary/middleware.py` | 100% (Robert) |
| `dashboard/scanner.py` | 92.9% (Robert) |
| `upgrade/migrations/__init__.py` | 100% (Robert) |
| `sync/events.py` | 96.4% (Robert) |

**Open question (per the tactic):** is this single-author concentration a
**"stable mature ownership"** signal or a **"knowledge bus factor"** signal?
The recipes cannot answer that — only conversation with the team can. But the
combination of (a) 89.5% concentration, (b) high churn (still active), and
(c) high bug-fix density on those same files leans toward bus factor over
maturity.

### Bus factor — full corpus reassessment (2026-05-09)

Re-running on `src/ + tests/ + kitty-specs/` with the expanded exclusion list:

| Author | Commits | Share |
|--------|--------:|------:|
| Robert Douglass | 2613 | **95.2%** |
| Stijn Dejongh | 58 | 2.1% |
| Den Delimarsky 🌺 | 32 | 1.2% |
| honjo-hiroaki-gtt | 5 | 0.2% |
| den (work) | 5 | 0.2% |
| Tanner | 3 | 0.1% |
| Jerome LACUBE | 3 | 0.1% |
| Jerome Lacube | 3 | 0.1% |
| Bruno Borges | 3 | 0.1% |
| 16 others | ≤2 each | <0.1% |

**Total commits in window:** 2744 (vs. 1001 in src/-only). The other ~1740
commits are tests/ and kitty-specs/ authoring — and **97.8%** of those
non-`src/` commits are also Robert. Concentration is **not diluted** by tests
or specs; it is intensified.

**Per-hotspot (file + matching tests, full-corpus):**

| Hotspot | Top-author share (file + tests) |
|---------|-------------------------------:|
| `agent/tasks.py` + matching tests | 97.7% (Robert; 2 Stijn) |
| `agent/workflow.py` + matching tests | 96.1% (Robert; 2 Stijn, 1 Jerome) |
| `implement.py` + matching tests | 97.0% (Robert; 2 Stijn) |
| `merge.py` + matching tests | 96.4% (Robert; 2 Stijn) |
| `sync/emitter.py` + matching tests | 93.4% (Robert; 8 Stijn) |

**Verdict:** broadening the lens to "the file plus its tests plus its spec
history" does **not** improve the bus factor for any top-15 hotspot. The
slight uptick in Stijn's share on `sync/emitter.py` (3 → 8) is the only
visible co-ownership pocket; everywhere else the same author wrote the
implementation, the tests, and the mission spec. **F1 reaffirmed: bus factor
≈ 1 across the entire codebase.**

The original audit speculated that single-author concentration *might* be
"stable mature ownership". The full-corpus view rules that out: a mature
codebase with healthy ownership would show (a) test files maintained by
reviewers, (b) mission specs co-authored with planners, or (c) at least
multiple committers landing fixes on the F-rated functions. None of these
patterns appear. F1 is now classified **bus factor**, not maturity.

## Firefighting signal

8 commits in the 1y window match `revert|hotfix|emergency|rollback` (out of 1001
on `src/`, ~0.8%). Spot-read of all 8:

```
cf997620c fix(review): enforce rollback feedback capture across 2.x flows
cd128b881 Revert "fix: Restore ClarificationMiddleware (WP06) after parallel branch merge"
2e52be19b fix: backport v0.15.2 hotfix to 2.x — branch detection, subprocess encoding, hook safety
4a9509ed6 feat(WP06): define software-dev v1 mission YAML with guards and rollback
bce568943 feat(WP10): add rollback-aware merge resolution and JSONL merge
87f3efb1f feat(WP03): add deterministic reducer with rollback-aware conflict resolution
192ca305d refactor: Remove rollback-task command
d864c9829 Revert "feat(merge): run from primary repo when invoked in worktree"
```

Of these 8, only 3 are genuine emergency events:

- `cd128b881` — explicit revert of a parallel-branch-merge fix
- `d864c9829` — explicit revert of a merge-from-primary-repo feature
- `2e52be19b` — explicit hotfix backport from `v0.15.2` to `2.x`

The other 5 are features/refactors that contain rollback in their **scope**
(rollback-aware merge, rollback feedback capture, etc.), not rollback events.

**Verdict:** firefighting frequency is genuinely low (~0.3% of commits if we
strip the false positives). The team appears to trust the merge pipeline. This
is a **healthy signal** that contradicts the high single-author concentration
risk — the lone author has, so far, kept the pipeline reliable. The risk is
**bus factor**, not **pipeline trust**.

## Velocity trend (24 months, monthly commit count on src/)

```
2025-08:   2  ▏
2025-09:  54  ████▎
2025-10:  47  ███▊
2025-11:  70  █████▌
2025-12:  45  ███▌
2026-01: 185  ██████████████▌
2026-02: 288  ██████████████████████▊
2026-03:  71  █████▌
2026-04: 210  ████████████████▌
2026-05:  29  ██▎ (partial month, audit on day 8)
```

(prior 12 months in the 2y window had no commits to `src/` — repository began
significant activity in late 2025 / early 2026)

Project is **decisively alive and accelerating**: the 2026-Q1 commit count
exceeds the previous five months combined. The 2026-03 dip is plausibly the
gap between the 2.x cutover (2026-02 surge) and the post-cutover reliability
work (2026-04 surge). Last 30 days: 193 src/ commits. Last 90 days: 550.

## Triage matrix (Eisenhower, per procedure exit condition)

The procedure asks for a four-bucket assignment of audit findings. The
2026-05-09 scope expansion introduces new findings (F15-F18) which are
woven into the buckets below; the original buckets are otherwise preserved.

### Important + urgent (this week)

- **Schedule a knowledge-transfer pairing on `cli/commands/agent/tasks.py` and
  `agent/workflow.py`.** These are the two highest-churn-and-bug files, both
  >96% single-author, both contain F-rated cyclomatic functions. If the lone
  author is unavailable for two weeks, work on these files stops.
- **Question the duplicated template** at
  `missions/software-dev/templates/task-prompt-template.md` vs.
  `templates/task-prompt-template.md`. 15 co-edits in 1y suggests neither has
  become canonical; one of them is dead-code-by-edit-count and the audit cannot
  tell which from history alone.
- **Test-update lag on F2 cluster (NEW, 2026-05-09).** `agent/tasks.py` and
  `agent/workflow.py` change with their tests only ~30% of the time. Pair the
  refactor (already in this bucket) with a test-build-out pass: every commit
  that lands a behavior change in the F-rated functions should include a
  matching unit test. The lone-author dynamic means there is currently nobody
  enforcing this on review.

### Important + not urgent (this quarter)

- **Refactor `cli/commands/agent/tasks.py` (3746 SLOC, F-160 `finalize_tasks`,
  F-139 `move_task`).** This is the single strongest "both unstable and
  known-defective" candidate the audit produces. A connascence-of-meaning pass
  on the function boundaries is the natural follow-up. **Priority upgraded
  by the 2026-05-09 scope expansion**: 21.8% test-churn ratio and 29.9%
  change-with-tests rate make this both structurally and behaviourally risky.
  Refactor MUST include a test build-out, not just a structural decomposition.
- **Refactor `cli/commands/agent/mission.py` (2314 SLOC, F-160 `finalize_tasks`)**
  — note `finalize_tasks` is in `mission.py`, not `tasks.py` despite the name;
  this name-vs-location mismatch is itself a coupling smell.
- **Decompose `cli/commands/init.py` (F-94 `init`, 1018 SLOC).** Worst MI in
  the CLI command layer (after charter).
- **Decompose `cli/commands/charter.py` (2934 SLOC, MI=C, three E-rated
  functions).** Charter interview, generate, status, and synthesize are
  effectively four CLI verbs jammed into one file.
- **Re-examine `next/runtime_bridge.py` (2552 SLOC).** Nominally a "bridge"
  but is itself a hotspot (rank #21 by churn, rank #7 by SLOC). Bridge that
  needs 26 commits/year and contains an F-46 function isn't a bridge, it's a
  hub.
- **Investigate `glossary/middleware.py` test gap (NEW, 2026-05-09).** 36
  src commits / 5 test commits = 13.9% ratio, the worst hot-file ratio in
  the corpus. The glossary subsystem otherwise shows healthy src ↔ test
  co-change discipline; middleware is the outlier. Likely either (a) tested
  via integration tests that span multiple sources (in which case ratio is
  misleading), or (b) the dispatch surface where most behaviour change
  happens but unit-test surfaces have lagged. Verify before refactoring.
- **Investigate `agent_utils/status.py` test gap (NEW, 2026-05-09).** Kanban
  renderer with F-53 `_display_status_board`, 21 src commits / 4 test commits
  = 19.0% ratio. Same diagnosis as middleware; verify whether integration
  tests exercise it before declaring under-tested.

### Not important + not urgent (don't worry)

- **Firefighting frequency.** Genuinely low; do not invest in pipeline-trust
  remediation absent other signal.
- **Velocity.** Healthy and growing; no investment needed.
- **`src/kernel/` and `src/charter/`.** Small (694 + 11,384 SLOC), low churn
  (8 + 38 commits/y), no F-rated complexity outside `charter/compiler.py`
  (MI=B). Stable subsystems.
- **`__init__.py` at 119 commits.** Shape of the data: it's the package
  bootstrap and absorbs every new export. Replace question with a check: is
  it >300 SLOC of logic? (Answer: 224 SLOC — fine.)

### Parallelisable (delegate / batch)

- **Delete the three empty leftover dirs**: `src/runtime/`, `src/dashboard/`
  (top-level — note the *real* dashboard is `src/specify_cli/dashboard/`),
  `src/constitution/`. They contain only stale `__pycache__/`. Trivial, batchable.
- **Recipe-level cleanup of D-rated migrations**
  (`m_0_10_8_fix_memory_structure.py` — F-47, `m_3_1_1_charter_rename.py` — D-27,
  `m_3_2_0_codex_to_skills.py` — D-24, `m_3_2_3_unified_bundle.py` — D-22).
  Migrations are write-once-and-never-touch; refactoring them is parallelisable
  and low-risk.

## Cross-cutting observations

1. **The `agent/` directory is doing too much.** `cli/commands/agent/tasks.py`,
   `workflow.py`, `mission.py`, `status.py`, and the deleted `feature.py`
   together hold ~10,000 SLOC of CLI dispatch and contain six of the eight
   worst-complexity functions in the project. This is "everything-the-mission-
   touches-funnels-here" architecture. The CaaCS recipes cannot prescribe a
   refactor; they can only flag that the seam is overloaded.
2. **Template ↔ dispatcher coupling is a designed feature, but its volume is
   load-bearing.** Pairs #11, #14, #18, #19 in the temporal-coupling table all
   show command-template `.md` files co-changing with their CLI dispatchers
   ~12-18 times per year. The mission system's design contract (templates are
   the source-of-truth for agent prompts) is correct, but every change to a
   template requires a corresponding dispatcher change. Worth examining whether
   a template-loader abstraction could reduce that.
3. **The `sync/` package is a coherent cluster.** `emitter.py`, `events.py`,
   `background.py`, `batch.py`, `queue.py`, `client.py` all appear in the
   churn list and co-change with each other (not with the rest of the
   codebase). This is a healthy modular cluster — high internal coupling, low
   external coupling — and **does not** need a refactor; it needs a second
   maintainer.
4. **`__init__.py` co-authorship history is a leading indicator.** It is the
   only top-15 hotspot with non-trivial co-authorship (Den, Bruno, honjo all
   contributed). This reflects the 1.x-era contributor base, before the 2.x
   cutover concentrated authorship. The drop from "many contributors on
   `__init__.py`" to "one contributor on everything else" is the bus-factor
   transition the project lived through.
5. **No `tests/` were in scope.** This is a deliberate scope decision but it
   blinds the audit to the most important counterweight: test coverage on the
   F-rated functions. A file with CC=160 and a 95% test-line-coverage harness
   is a different beast than one with CC=160 and no tests. The CaaCS recipes
   cannot tell them apart.

## Multi-window refactor-candidate synthesis (2026-05-11)

This section executes the new tactic step
([`forensic-repository-audit`](../../../../../packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml),
"Compile a multi-window refactor-candidate list") that was added to the
tactic after the 2026-05-09 re-run. The recipe runs two passes — full
history and a velocity-adjusted recent window — over the
`src/ + tests/ + kitty-specs/` scope, filters to files present at HEAD via
`git ls-files`, and intersects the two top-30 lists to produce a refactor
candidate list anchored in code that still exists.

Commit at run time: `f1cd634d5cc106dee805140f365c0dbc6822d430` (branch
`feat/caacs-doctrine`). Exclusion list is the same one used in the
"Scope expansion (2026-05-09)" re-run: lockfiles, `__pycache__`,
`CHANGELOG.md`, `.mypy_cache`, `status.events.jsonl`, `status.json`,
`kitty-specs/**/tasks.md`, `kitty-specs/**/snapshot-latest.json`,
`kitty-specs/**/dossiers/**`.

### Window selection rationale

The velocity series in `## Velocity trend` above shows monthly src/
commits going `2 → 54 → 47 → 70 → 45 → 185 → 288 → 71 → 210 → 29`
from 2025-08 through 2026-05 (partial). The most recent four full
months (2026-01 through 2026-04) sum to **754 commits**, against
**218** for the prior four months (2025-09 through 2025-12) — a
**3.5×** quarter-over-quarter acceleration. Last-30-day count is 193,
last-90-day count is 550 (per the existing audit). By the tactic's
heuristic ("accelerating velocity → 3-6 month window"), spec-kitty is
unambiguously in the accelerating regime; **a four-month window** is
selected — short enough to filter out the pre-2026-Q1 lull, long
enough to capture both the 2026-02 surge (288 commits) and the
2026-04 surge (210 commits) so neither single-month spike dominates.

**Repository-age caveat (worth noting up front):** the first commit
touching `src/`, `tests/`, or `kitty-specs/` is dated 2025-08-22 —
the repository is only ~8.5 months old at audit time. The
"full-history" pass therefore covers a window that is only slightly
larger than the existing one-year step-2 window, and the
multi-year-churn signal the tactic is designed to surface
(*sustained* hotspots that have *never* settled) cannot exist in
this codebase yet. The full-history pass here behaves more like an
"all-time" pass than a true multi-year baseline. Interpretation
adjusts accordingly.

### Full-history pass (top 30, files present at HEAD)

`git log --format=format: --name-only -- src/ tests/ kitty-specs/`
with the exclusion list above, filtered by `git ls-files`. SLOC
column is `wc -l` of the file at HEAD; for markdown templates this
counts every line including blanks (the tactic uses SLOC as a rough
size proxy, not a strict logical-line count, and `cloc` is not
installed in this environment).

| # | Path | Full-history count | SLOC |
|---|------|------:|------:|
| 1 | `src/specify_cli/__init__.py` | 119 | 224 |
| 2 | `src/specify_cli/cli/commands/agent/tasks.py` | 87 | 3746 |
| 3 | `src/specify_cli/cli/commands/agent/workflow.py` | 77 | 1895 |
| 4 | `src/specify_cli/cli/commands/implement.py` | 67 | 718 |
| 5 | `src/specify_cli/cli/commands/merge.py` | 56 | 1599 |
| 6 | `src/specify_cli/cli/commands/init.py` | 50 | 1018 |
| 7 | `src/specify_cli/cli/commands/__init__.py` | 47 | 115 |
| 8 | `src/specify_cli/sync/emitter.py` | 42 | 1682 |
| 9 | `src/specify_cli/missions/software-dev/command-templates/specify.md` | 38 | 635 |
| 10 | `src/specify_cli/glossary/middleware.py` | 36 | 689 |
| 11 | `src/specify_cli/cli/commands/sync.py` | 36 | 1462 |
| 12 | `src/specify_cli/missions/software-dev/command-templates/tasks.md` | 33 | 674 |
| 13 | `src/specify_cli/dashboard/static/dashboard/dashboard.js` | 29 | 1568 |
| 14 | `src/specify_cli/sync/events.py` | 28 | 499 |
| 15 | `src/specify_cli/dashboard/scanner.py` | 28 | 785 |
| 16 | `src/specify_cli/missions/software-dev/command-templates/plan.md` | 27 | 359 |
| 17 | `src/specify_cli/missions/software-dev/command-templates/implement.md` | 27 | 257 |
| 18 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP03-term-extraction-implementation.md` | 27 | 255 |
| 19 | `src/specify_cli/upgrade/migrations/__init__.py` | 26 | 89 |
| 20 | `src/specify_cli/next/runtime_bridge.py` | 26 | 2552 |
| 21 | `src/specify_cli/glossary/__init__.py` | 26 | 204 |
| 22 | `src/specify_cli/tasks_support.py` | 25 | 31 |
| 23 | `src/specify_cli/status/emit.py` | 25 | 656 |
| 24 | `src/specify_cli/core/worktree.py` | 25 | 681 |
| 25 | `tests/sync/test_events.py` | 24 | 1211 |
| 26 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP11-type-safety-and-integration-tests.md` | 24 | 925 |
| 27 | `src/specify_cli/cli/commands/charter.py` | 23 | 2934 |
| 28 | `src/specify_cli/orchestrator_api/commands.py` | 21 | 1097 |
| 29 | `src/specify_cli/agent_utils/status.py` | 21 | 570 |
| 30 | `tests/conftest.py` | 20 | 822 |

Inline note: `tests/conftest.py` (rank 30) is the only newcomer relative
to the full-corpus step-2 table; it ranks 30 here because the step-2
top-30 cut absorbed the deleted-and-renamed entries (`feature.py`,
`dashboard.py`, `acceptance.py`) that have been removed from HEAD by
this pass's `git ls-files` filter.

### Velocity-adjusted pass (top 30, `--since="4 months ago"`)

Same recipe, same exclusions, same HEAD filter, `--since="4 months ago"`.

| # | Path | 4m count | SLOC |
|---|------|------:|------:|
| 1 | `src/specify_cli/cli/commands/agent/tasks.py` | 85 | 3746 |
| 2 | `src/specify_cli/cli/commands/agent/workflow.py` | 76 | 1895 |
| 3 | `src/specify_cli/cli/commands/implement.py` | 67 | 718 |
| 4 | `src/specify_cli/cli/commands/merge.py` | 54 | 1599 |
| 5 | `src/specify_cli/sync/emitter.py` | 42 | 1682 |
| 6 | `src/specify_cli/cli/commands/init.py` | 42 | 1018 |
| 7 | `src/specify_cli/missions/software-dev/command-templates/specify.md` | 38 | 635 |
| 8 | `src/specify_cli/glossary/middleware.py` | 36 | 689 |
| 9 | `src/specify_cli/cli/commands/sync.py` | 36 | 1462 |
| 10 | `src/specify_cli/cli/commands/__init__.py` | 35 | 115 |
| 11 | `src/specify_cli/missions/software-dev/command-templates/tasks.md` | 33 | 674 |
| 12 | `src/specify_cli/sync/events.py` | 28 | 499 |
| 13 | `src/specify_cli/missions/software-dev/command-templates/plan.md` | 27 | 359 |
| 14 | `src/specify_cli/missions/software-dev/command-templates/implement.md` | 27 | 257 |
| 15 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP03-term-extraction-implementation.md` | 27 | 255 |
| 16 | `src/specify_cli/next/runtime_bridge.py` | 26 | 2552 |
| 17 | `src/specify_cli/glossary/__init__.py` | 26 | 204 |
| 18 | `src/specify_cli/status/emit.py` | 25 | 656 |
| 19 | `tests/sync/test_events.py` | 24 | 1211 |
| 20 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP11-type-safety-and-integration-tests.md` | 24 | 925 |
| 21 | `src/specify_cli/dashboard/scanner.py` | 23 | 785 |
| 22 | `src/specify_cli/core/worktree.py` | 23 | 681 |
| 23 | `src/specify_cli/cli/commands/charter.py` | 23 | 2934 |
| 24 | `src/specify_cli/orchestrator_api/commands.py` | 21 | 1097 |
| 25 | `src/specify_cli/dashboard/static/dashboard/dashboard.js` | 21 | 1568 |
| 26 | `src/specify_cli/agent_utils/status.py` | 21 | 570 |
| 27 | `src/specify_cli/sync/__init__.py` | 20 | 190 |
| 28 | `src/specify_cli/status/models.py` | 20 | 422 |
| 29 | `src/specify_cli/status/__init__.py` | 20 | 169 |
| 30 | `src/specify_cli/missions/software-dev/command-templates/review.md` | 20 | 194 |

### Intersection (inner-join on path)

Files in **both** top-30 lists. Tag rule (verbatim from the tactic):
both-in-this-AND-in-step-2 → **urgent**; in-this-but-not-step-2 →
**slow-burn**; in-step-2-but-not-here → **unsettled burst**
(handled below).

| F# | R# | Path | SLOC | In step-2 (1y full-corpus) | Tag |
|---:|---:|------|-----:|:--------------------------:|-----|
| 2 | 1 | `src/specify_cli/cli/commands/agent/tasks.py` | 3746 | ✓ | **urgent** |
| 3 | 2 | `src/specify_cli/cli/commands/agent/workflow.py` | 1895 | ✓ | **urgent** |
| 4 | 3 | `src/specify_cli/cli/commands/implement.py` | 718 | ✓ | **urgent** |
| 5 | 4 | `src/specify_cli/cli/commands/merge.py` | 1599 | ✓ | **urgent** |
| 6 | 6 | `src/specify_cli/cli/commands/init.py` | 1018 | ✓ | **urgent** |
| 7 | 10 | `src/specify_cli/cli/commands/__init__.py` | 115 | ✓ | **urgent** |
| 8 | 5 | `src/specify_cli/sync/emitter.py` | 1682 | ✓ | **urgent** |
| 9 | 7 | `src/specify_cli/missions/software-dev/command-templates/specify.md` | 635 | ✓ | **urgent** |
| 10 | 8 | `src/specify_cli/glossary/middleware.py` | 689 | ✓ | **urgent** |
| 11 | 9 | `src/specify_cli/cli/commands/sync.py` | 1462 | ✓ | **urgent** |
| 12 | 11 | `src/specify_cli/missions/software-dev/command-templates/tasks.md` | 674 | ✓ | **urgent** |
| 13 | 25 | `src/specify_cli/dashboard/static/dashboard/dashboard.js` | 1568 | ✓ | **urgent** |
| 14 | 12 | `src/specify_cli/sync/events.py` | 499 | ✓ | **urgent** |
| 15 | 21 | `src/specify_cli/dashboard/scanner.py` | 785 | ✓ | **urgent** |
| 16 | 13 | `src/specify_cli/missions/software-dev/command-templates/plan.md` | 359 | ✓ | **urgent** |
| 17 | 14 | `src/specify_cli/missions/software-dev/command-templates/implement.md` | 257 | ✓ | **urgent** |
| 18 | 15 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP03-term-extraction-implementation.md` | 255 | ✓ | **urgent** |
| 20 | 16 | `src/specify_cli/next/runtime_bridge.py` | 2552 | ✓ | **urgent** |
| 21 | 17 | `src/specify_cli/glossary/__init__.py` | 204 | ✓ | **urgent** |
| 23 | 18 | `src/specify_cli/status/emit.py` | 656 | ✓ | **urgent** |
| 24 | 22 | `src/specify_cli/core/worktree.py` | 681 | ✓ | **urgent** |
| 25 | 19 | `tests/sync/test_events.py` | 1211 | ✓ | **urgent** |
| 26 | 20 | `kitty-specs/041-mission-glossary-semantic-integrity/tasks/WP11-type-safety-and-integration-tests.md` | 925 | ✓ | **urgent** |
| 27 | 23 | `src/specify_cli/cli/commands/charter.py` | 2934 | ✓ | **urgent** |
| 28 | 24 | `src/specify_cli/orchestrator_api/commands.py` | 1097 | — | **slow-burn** |
| 29 | 26 | `src/specify_cli/agent_utils/status.py` | 570 | — | **slow-burn** |

**Unsettled-burst residual (step-2 entries that did NOT make this
intersection):**

- `src/specify_cli/__init__.py` (step-2 #1) — 132 commits all-time but
  only 13 in the recent four months. **Settled**: the 2.x cutover
  churn here is mostly done.
- `src/specify_cli/cli/commands/agent/feature.py` — **deleted at HEAD**
  (`7428880c4`, mission-id cutover). Drops out by HEAD filter; not a
  refactor target.
- `src/specify_cli/dashboard.py` — **renamed** to
  `cli/commands/dashboard.py`. Drops out by HEAD filter; not a
  refactor target. The renamed file `cli/commands/dashboard.py` did
  not accumulate enough commits post-rename to enter either top-30.
- `src/specify_cli/acceptance.py` — **renamed** to
  `acceptance/__init__.py`. Drops out by HEAD filter; not a refactor
  target.
- `src/specify_cli/tasks_support.py` — 25 commits all-time, 17 in the
  recent window, but only 31 SLOC: it is a thin re-export shim. Real
  but unimportant.
- `src/specify_cli/upgrade/migrations/__init__.py` — 26 commits
  all-time, 13 recent, 89 SLOC: the migration registry. Real but
  small; churn-by-registration not churn-by-design.

None of the unsettled-burst residual is a "recent spike that hasn't
settled". All five either (a) have legitimately cooled (`__init__.py`,
`tasks_support.py`, `migrations/__init__.py`) or (b) have been
deleted/renamed and so dropped by the HEAD filter. The
**unsettled-burst category is empty for spec-kitty** under this
window choice — every hotspot the step-2 1y view surfaced is either
still hot in the four-month window or has been resolved (cut, merged,
or renamed).

### Interpretation

The multi-window synthesis adds **two new signals** relative to the
existing audit. First, it **confirms F2** (the `cli/commands/agent/*`
- `merge.py` + `sync/emitter.py` + `next/runtime_bridge.py` refactor
cluster): the top-five urgent candidates are exactly the F2 cluster
the existing audit named, and they hold rank in both windows (F#2-5
and R#1-4). Twenty-four of the twenty-six intersection files are
already known step-2 hotspots, so the audit's existing refactor
priority list is **stable and re-confirmed** rather than displaced.
Second, it surfaces **two genuinely new slow-burn candidates not in
the step-2 top-30**: `orchestrator_api/commands.py` (1097 SLOC, F#28
/ R#24) and `agent_utils/status.py` (570 SLOC, F#29 / R#26). Both
fell just outside the step-2 cut (which stopped at rank 30 =
`acceptance.py` with 22 commits / `agent_utils/status.py` was 21 in
the src/-only table but absent from the full-corpus 30) — the
multi-window view promotes them into the inspect-this-quarter bucket.
`orchestrator_api/commands.py` already appears in the open
follow-ups list as item 5's neighbour, but `agent_utils/status.py`
(the kanban renderer with an F-53 `_display_status_board` function)
is **newly elevated** to detailed-inspection status by this pass.

The unsettled-burst category is empty: every step-2 entry that
dropped out of this intersection did so for a settled reason (cooled
churn, deletion, or rename) rather than a "recent burst that may not
sustain". This is partly a consequence of the repository's youth —
there has not been enough wall time for any 1y hotspot to settle
into history — but it also means the existing F2 verdict is not
threatened by hidden short-lived bursts. The list is what it claims
to be.

1. **Scope (after 2026-05-09 expansion) = `src/ + tests/ + kitty-specs/`.** The
   remaining out-of-scope dirs are `architecture/`, `docs/`, and `.github/`.
   These are intentionally excluded (architecture docs and CI config are not
   what this audit is for).
2. ~~**No `tests/` overlay.**~~ *Lifted by the 2026-05-09 expansion.* See
   "Test coverage proxy" above; ratio-based proxy now exists, but it remains
   a churn proxy, not coverage.
3. **`cloc` not installed.** SLOC is `wc -l` (Python files only); language
   breakdown is implicit (everything in scope is Python except a few markdown
   templates and one JS dashboard file). For a pure-Python scope this is
   acceptable.
4. **Rename-following is partial.** Per-file authorship for the top-15 used
   `--follow`; the bulk recipes (churn, bug-hotspots, temporal coupling) did
   not. Three concrete renames in the window are documented inline:
   `acceptance.py` → `acceptance/__init__.py`, `dashboard.py` →
   `cli/commands/dashboard.py`, `cli/commands/agent/feature.py` deleted in
   `7428880c4`. Other renames likely exist and would push some files
   currently outside the top-30 closer to the top.
5. **Bug-grep heuristic.** `fix|bug|broken|regress|hotfix` is the recipe-
   spec'd grep. It matches commit body too, producing a low rate of
   false positives (spec/feat commits whose body mentions "fix" in prose).
   Spot-checked on 5 random matches: 4/5 are genuine fix commits, 1/5 is a
   spec commit that mentions opportunistic fixes in passing. Acceptable
   noise floor.
6. **Squash-merge mix.** History contains both squashed PRs (one commit each)
   and non-squashed PRs (multiple commits). Velocity counts are biased
   slightly downward against squashed PRs but the bias is uniform across the
   window so the **shape** of the velocity curve is reliable.
7. **The "vanity-file dominance" check is informal.** Top-4 hotspots were
   spot-checked for insertion-vs-deletion ratio (all show substantive
   churn). The full top-30 was not checked individually.
8. **DDD classifications are researcher-tentative** — architect sign-off
   required before treating any cell of the DDD column in the hotspot table
   as authoritative. The justifications are one-line and the researcher has
   no charter context to lean on.
9. **Per the tactic's own out-of-scope clause:** this audit is not a
   substitute for the brownfield-investigation skill (issues #665/#666);
   it is the evidence-gathering input to triage and connascence/premortem
   tactics, not a verdict.
10. **Mission state-file dominance (full-corpus run).** Without the new
    `kitty-specs/**/tasks.md`, `kitty-specs/**/snapshot-latest.json`, and
    `kitty-specs/**/dossiers/**` exclusions, mission-state files completely
    dominate churn (some snapshot-latest.json files have 24+ commits; some
    tasks.md files have 100+). Two such files leaked into the first uncleaned
    pass and were excluded in the published table. A future re-run on a fresh
    clone should re-validate this exclusion list — new state-file conventions
    may have been introduced.
11. **Mission ↔ src coupling visibility (commit-level).** As discussed in the
    cross-cutting section, the SDD pipeline deliberately separates spec edits
    from code edits at the commit level, so commit-pair recipes only see the
    *exception cases* (post-merge spec amendments, doc fixes during
    implementation). The full mission ↔ code coupling would require either
    PR-level grouping (we don't have local PR metadata) or a `Mission:`
    trailer convention (not yet adopted). This is a methodology gap, not a
    fix-now item.
12. **Test-coverage proxy is a churn ratio, not coverage.** A file with
    "test-heavy" status might still have low line/branch coverage; an
    "under-tested" file might be exercised heavily by integration tests that
    rarely change. The four flagged files (`agent/tasks.py`, `agent/workflow.py`,
    `glossary/middleware.py`, `agent_utils/status.py`) are *prompts to
    verify*, not verdicts. The recipes do not include `coverage.py` or any
    actual coverage tool; that would be a separate audit step.
13. **150 missions, 167 mission directories with churn.** The `kitty-specs/`
    tree is enormous (150 directories at the time of audit). Most of these
    are merged, archived, and quiescent; ~15-20 show recent activity. The
    "mission ↔ src" pair counts are dwarfed by sheer mission volume; if a
    future scope expansion narrows to "active missions only" (open WPs or
    unmerged), the signal-to-noise should improve.

## Open follow-ups for cross-check (Phase 3)

The following items should be cross-referenced against open `#822` sub-issues
by the planner:

1. Refactor `cli/commands/agent/tasks.py` (3746 SLOC, F-160 + F-139 + F-87 + F-74).
2. Refactor `cli/commands/agent/mission.py` (2314 SLOC, contains F-160
   `finalize_tasks` despite the name, suggesting a misplaced responsibility).
3. Decompose `cli/commands/charter.py` (2934 SLOC, three E-rated functions,
   MI=C).
4. Decompose `cli/commands/init.py` (F-94 `init`).
5. Examine `next/runtime_bridge.py` (2552 SLOC, F-46) — bridge or hub?
6. Resolve the duplicated `task-prompt-template.md` pair (15 co-edits/y at two
   paths).
7. Knowledge-transfer plan for `agent/`, `merge.py`, `implement.py`,
   `sync/emitter.py`, `glossary/middleware.py`, and `core/worktree.py` (all
   ≥96% single-author).
8. Delete empty leftover dirs `src/runtime/`, `src/dashboard/`,
   `src/constitution/`.
9. Re-run this audit with `tests/` in scope to overlay test coverage on the
   F-rated functions before scheduling refactors.
10. Re-run this audit with `kitty-specs/` in scope to surface
    feature-spec ↔ source-code temporal coupling, which is invisible to the
    current run.

## Scope-expansion changelog (2026-05-09)

What changed in this re-run, with one-line rationale per item:

- **Added** `## Scope expansion (2026-05-09)` near the top — declares the
  expanded scope, exclusions, and headline impact (F1 worse, F2 unchanged).
- **Added** new exclusions for kitty-specs/ state churn (`status.events.jsonl`,
  `status.json`, `tasks.md`, `snapshot-latest.json`, `dossiers/**`) — without
  these, mission state files dominate the churn ranking and obscure code
  hotspots.
- **Renamed** the original hotspot-table heading to
  `### Hotspots — src/ only (original)` — preserves the original table
  intact while making room for the broader view.
- **Added** `### Hotspots — full corpus (src/ + tests/ + kitty-specs/)` —
  shows that broadening scope adds zero new structural hotspots; mission 041
  WP files and `tests/sync/test_events.py` are the only non-src/ entries
  in the top 30, both of which track existing hotspots.
- **Added** `### Bus factor — full corpus reassessment` inside the existing
  Bus-factor section — re-runs `git shortlog` on the full corpus
  (95.2% Robert vs 89.5% in src/-only) and per-hotspot file+tests authorship
  (no improvement). Reclassifies F1 from "bus factor or maturity, unclear"
  to definitively "bus factor".
- **Added** `## Cross-cutting temporal coupling (mission ↔ src/ ↔ tests/)`
  — three sub-tables: (a) mission ↔ src pair counts (low signal, by design),
  (b) src ↔ tests pair counts (sync/ and glossary/ healthy, agent/ lagging),
  (c) F2 cluster change-with-tests rate (~30%, new finding F15).
- **Added** `## Test coverage proxy` — ratio table for top-20 hotspots,
  flagging four under-tested files (F2 cluster + glossary middleware +
  agent_utils status renderer).
- **Updated** the Limitations section — removed the (now-invalid)
  scope-only-src/ caveats; added five new caveats (10–13) about state-file
  exclusions, mission ↔ src commit-level invisibility, churn-vs-coverage
  proxy nature, and the size of the kitty-specs/ tree.
- **Updated** the Triage matrix — added test-update-lag bullet to the
  "Important + urgent" bucket; upgraded the agent/tasks.py refactor priority
  to require a test build-out; added two glossary-middleware and
  agent_utils/status investigation bullets to "Important + not urgent".
- **Added this changelog** at the bottom.
- **Added (2026-05-11)** `## Multi-window refactor-candidate synthesis (2026-05-11)`
  between the cross-cutting observations and the limitations sections —
  executes the new "Compile a multi-window refactor-candidate list" step
  added to the `forensic-repository-audit` tactic; uses a four-month
  velocity-adjusted window (accelerating regime per the existing velocity
  series), confirms F2, surfaces `orchestrator_api/commands.py` and
  `agent_utils/status.py` as new slow-burn candidates, and reports an
  empty unsettled-burst category.

The original audit-metadata, methodology, top-findings, hotspot table,
temporal-coupling table (within src/), bus-factor overall table, firefighting
section, velocity section, cross-cutting observations, and open follow-ups
are preserved verbatim from the 2026-05-08 run. Only the eight items listed
above were modified or added.

---

*Generated 2026-05-08 by researcher subagent following the
[forensic-repository-audit](../../../../../packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml)
tactic and
[legacy-codebase-triage](../../../../../packs/built-in/procedures/legacy-codebase-triage.procedure.yaml)
procedure on branch `feat/caacs-doctrine` at commit
`bc64dec6ee37dbbd6bc21a0a1aa3195f2bab1b57`. Scope-expansion re-run on
2026-05-09 at commit `81883352240c3f8e0249b78875f7fa140700418f` extended the
audit to `src/ + tests/ + kitty-specs/`; see "Scope expansion (2026-05-09)"
near the top and the changelog at the bottom for the diff. Not committed;
review-only artifact.*
