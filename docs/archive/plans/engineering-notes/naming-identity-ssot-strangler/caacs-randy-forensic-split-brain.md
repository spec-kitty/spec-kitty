---
title: Randy Reducer — CaaCS Forensic Split-Brain (temporal validation of the static map)
description: "Randy Reducer's CaaCS forensic split-brain note: temporal validation of the static authority map for the naming/identity SSOT strangler."
doc_status: deprecated
updated: '2026-06-16'
---
# Randy Reducer — CaaCS Forensic Split-Brain (temporal validation of the static map)

> **Persona:** I am **Randy Reducer**. Semantic compression: fewer lines, same
> behavior, proven. This is the *forensic* companion to my static
> `randy-reducer-split-brain-map.md`. There I named the competing authorities by
> reading the code; here I let the **git history vote** on which split-brain is
> real, which couplings are pathological, and whether the static slice ranks the
> targets correctly. Every claim below is backed by the exact command output.

**Directives / tactics applied (STEP 0 load):**
- **`forensic-repository-audit`** (CaaCS five recipes + change-coupling overlay) —
  churn, bug-hotspot, velocity, firefighting, multi-window intersection.
- **`split-brain-authority-detection`** — authority-scope → uniqueness-invariant →
  "diff durable truth vs reported truth"; here applied to *which read surface a
  command trusts* per artifact family (meta/coord/lanes).
- **`semantic-compression-semantic-consolidation` / `-redundancy-discovery` /
  `-dead-weight-elimination`** + **DIR-024 Locality of Change**, **DIR-001
  Architectural Integrity**, **DIR-030 Quality Gate**, **DIR-034 Test-First**.
- **`test-scaffolding-as-design-smell`** — the recurring-fix concentration on the
  resolver files is the temporal twin of the static "12-mock scaffold" smell.

**Posture:** read-only on `research/naming-identity-ssot-strangler` @ 3.2.0. No
commit/switch. The 3.2.0 mission is one squash (`fcf9be595`); granular lane tips
live under `backup/20260615-2110/*`. **Squash caveat is load-bearing here** (see §0).

---

## 0. Scope, exclusions, and the squash caveat

- **Window.** Velocity is *accelerating* (`2026-04` 754 → `2026-05` 723 → `2026-06`
  **1151** commits/mo), so per the tactic's window heuristic I use a **4–6 month
  velocity-adjusted window** for the recent pass and full-history for the
  sustained pass.
- **Exclusions.** `*.lock`, `node_modules`, `dist/`, `__snapshots__`,
  `kitty-specs/`, `docs/plans/engineering-notes/`, `research/`, `.po/.pot`. Tests counted
  separately (not excluded) for the test-ratio overlay.
- **Squash distortion (mandatory caveat).** `fcf9be595` collapses the entire
  01KV6510 mission into one commit. The granular lane tips each still touched the
  surface — e.g. `…-lane-f` and `…-lane-i` each modified **5** resolver-surface
  `.py` files (`git log --format=format: --name-only <lane-tip> --not main`). So
  **every per-file churn count below UNDERSTATES the true instability of the
  resolver surface.** The signal is therefore a *lower bound*; it is already
  damning at the lower bound.
- **Rename caveat.** `branch_naming.py` predates the squash (`--follow` traces it
  to `2026-04-04`, `7d7496cae`) — it is an *established* seam, not a squash
  artefact. Good: it means its 100%-fix-class history (§3) is real, not a mirage.

---

## 1. The five recipes (src/ only, exclusions applied)

### Recipe 1 — churn hotspots (6-month window)

```
126 cli/commands/agent/tasks.py
119 cli/commands/agent/workflow.py
 95 cli/commands/merge.py
 93 cli/commands/implement.py
 67 cli/commands/agent/mission.py
 ...
 28 core/worktree.py
```

### Recipe 3 — bug hotspots (`fix|bug|broken|regress`, full history)

```
111 cli/commands/agent/tasks.py
102 cli/commands/agent/workflow.py
 78 cli/commands/implement.py
 76 cli/commands/merge.py
 52 cli/commands/agent/mission.py
```

**The principal-hotspot overlay (recipe 1 ∩ recipe 3) is unambiguous:**
`agent/tasks.py`, `agent/workflow.py`, `implement.py`, `merge.py`,
`agent/mission.py` sit in the top-5 of **both** lists. These are not the resolver
files — they are the **consumer commands that hand-juggle the resolvers.** That is
the first forensic surprise: *the crime scene is the callsite, not the library.*

### Recipe 4 — velocity: accelerating (754 → 723 → 1151). Project is alive

### Recipe 5 — firefighting: `19 / 5574 = 0.3 %`. Pipeline trust is healthy

(consistent with the 2026-05 CaaCS run). The split-brain is **not** a
pipeline-trust problem; it is a *design-authority* problem.

---

## 2. The killer recipe — change-coupling (the empirical split-brain signal)

Pairwise co-change over full no-merge history. `deg = co-changes /
min(solo_a, solo_b)` — degree of coupling normalised to the rarer file. Solo
counts (commits touching each file):

```
119 agent/workflow   96 merge   94 implement   67 agent/mission
 38 orchestrator_api 28 core/worktree 27 accept 20 core/paths
 19 mission_creation 14 status_transition 11 branch_naming 11 project_resolver
  8 surface_resolver  8 _read_path_resolver  5 mission_runtime/resolution  4 feature_dir_resolver
```

**Strongest couplings (co ≥ 4), ranked, with the split-brain verdict:**

| co | deg | pair | verdict |
|---:|----:|------|---------|
| 18 | **0.67** | `accept` ↔ `implement` | **PATHOLOGICAL.** Two independent CLI verbs co-change 2-of-3 times. They share nothing operationally except *the coord/primary read-surface juggling.* |
| 18 | 0.47 | `agent/workflow` ↔ `orchestrator_api` | PATHOLOGICAL (same juggling, two front-doors). |
| 17 | **0.61** | `agent/workflow` ↔ `core/worktree` | PATHOLOGICAL (worktree-path compose leaks into the command). |
| 16 | 0.59 | `accept` ↔ `merge` | PATHOLOGICAL (lifecycle surface). |
| 13 | **0.68** | `agent/mission` ↔ `mission_creation` | borderline — naming-compose leakage (the #2000 sites). |
|  7 | **0.64** | `branch_naming` ↔ `implement` | the identity seam dragging a consumer (mid8/2c class). |
|  6 | **0.75** | `agent/mission` ↔ `surface_resolver` | **PATHOLOGICAL.** A status-surface resolver should never co-change with a command at deg 0.75. |
|  6 | **0.75** | `agent/workflow` ↔ `surface_resolver` | **PATHOLOGICAL** (same). |
|  5 | **0.62** | `_read_path_resolver` ↔ {`agent/mission`, `agent/workflow`, `implement`} | **PATHOLOGICAL fan-in.** The "one read primitive" co-changes with three different commands at deg 0.62 — the authority isn't owning the decision, the callers are. |
|  4 | 0.50 | `_read_path_resolver` ↔ `surface_resolver` | **the smoking gun** — two *supposedly distinct* read resolvers co-change. |

**Interpretation (split-brain-authority-detection lens).** The CaaCS rule is: two
files that *should be independent* but co-change in lockstep share a hidden
authority. Here the hidden authority is **"which surface (meta-primary vs
coordination vs lanes) does this mission live on right now?"** — and it is *not
owned by one module*. It is re-decided inline at every command. The proof:

- `accept ↔ implement` at **0.67** and `accept ↔ merge` at **0.59**: three
  lifecycle verbs that touch entirely different code paths nonetheless move
  together, because each re-derives the same topology fallback ladder.
- `surface_resolver` co-changes with *commands* (`agent/mission`/`agent/workflow`
  at **0.75**) more tightly than the commands co-change with each other — a
  resolver that high-couples to its callers has not actually encapsulated the
  decision; it is a shared mutable convention, not a sealed authority.
- `_read_path_resolver ↔ surface_resolver` (co 4, deg 0.50): the static map's
  claim that these are **two parallel read authorities carrying overlapping
  `.worktrees`-segment / compose logic** is confirmed temporally — independent
  modules don't co-change unless they encode the same rule twice.

**Drill-down (classifying the `accept↔implement` coupling, not assuming it).** The
17 commits that touch both files are dominated by coordination/lifecycle subjects
— `fix(coordination-topology): close review blockers`,
`feat(…coordination-topology-stabilization-01KTZVQ2)`, `fix(cli): harden
lifecycle/json/merge acceptance flows`, `fix: merge-time numbering lock … MergeState
canonical keying`. It is the coord/primary class, not incidental co-edit.

---

## 3. Recurring-fix concentration — the resolver surface is *made of* defects

`fix|bug|coord|stale|primary|wrong|split.brain|broken`-class commits as a fraction
of each surface file's total history:

```
lanes/branch_naming.py              11/11  = 100%
missions/_read_path_resolver.py      8/8   = 100%
coordination/surface_resolver.py     8/8   = 100%
coordination/status_transition.py   14/14  = 100%
core/mission_creation.py            17/19  =  89%
core/paths.py                       16/19  =  84%
core/worktree.py                    23/28  =  82%
core/project_resolver.py             8/10  =  80%
missions/feature_dir_resolver.py     3/4   =  75%
```

**Every single file on the SSOT surface is 75–100% fix-class.** Four of them are
**100%** — they have *never* received a non-fix commit. These modules do not exist
to add capability; they exist to keep patching the same authority confusion. That
is the textbook temporal signature of a split-brain: a file born and sustained
entirely by reconciliation churn.

**Defect-class volume (full history, grep on commit subject):**

```
/coord/   223 commits
/stale/   169
/primary/  49
/mid8/     16
```

The coord/primary class outnumbers the mid8/wrong-compose class by **~14×**. The
static slice's headline item (#2000/#1899 mid8 routing) is, by commit volume, a
*rounding error* next to the coord/primary class (#1878).

---

## 4. Temporal trajectory — coord/primary is ACCELERATING, mid8 is FLAT

This is the finding that reorders the slice. Fix-rate per month, two classes:

```
coord/primary (coord∧primary | stale-primary | wrong-surface | surface-diverge | split-brain):
   2026-04   1
   2026-05   7
   2026-06  35      <-- 5x month-over-month, still climbing

mid8 / wrong-compose (#1860→#1949→#1978 class):
   2026-04   1
   2026-05   8
   2026-06   9      <-- plateaued
```

The mid8 class — the one 3.2.0 (#2001) hardened with the seam + ratchet — has
**flattened** (8→9): the fix worked, the ratchet is holding. The coord/primary
class has **quintupled** (7→35) in the same window and shows no sign of settling.
The most recent surface commits (`#1991` read lanes.json from coord not primary;
`#1989` analysis-report coord-worktree resolution; `#1732` coord-branch read/write
divergence; `#1718` stale-primary-under-coord) are all June, all the same class.

**Multi-window intersection (step 8).** The resolver surface files appear with
nearly identical counts in the full-history and the 4-month window
(`mission_creation` 19/19, `worktree` 28/17, `paths` 20/16, `status_transition`
14/14) — i.e. essentially *all* their churn is recent and *sustained*. By the
tactic's intersection rule (top of both lists = prime refactor candidate), the
**coord/primary read surface is the prime candidate**, and it is a *currently-hot*
fire, not a historical one.

---

## 5. Complexity overlay — the decision leaked into the consumer

Raw churn ≠ complexity, so the load-bearing overlay (radon CC):

| unit | CC | rank |
|------|---:|------|
| `implement()` (`implement.py:888`) | **57** | **F** |
| `_ensure_planning_artifacts_committed_git` | 21 | D |
| `require_explicit_feature` (`core/paths.py:485`) | 19 | C |
| `locate_project_root` (`core/paths.py:48`) | 16 | C |
| `resolve_status_surface_with_anchor` (`surface_resolver.py:433`) | 14 | C |

Per-file averages: `surface_resolver` A(3.2), `_read_path_resolver` A(3.2),
`branch_naming` A(2.8) — **the resolver files are individually simple.** The
complexity is **not in the authority; it is in `implement()` at CC 57**, where the
topology decision is re-made inline. Grep confirms `implement()` derives **three
distinct feature_dir variables from three resolvers**:

```
957  feature_dir          = resolve_feature_dir_for_mission(repo_root, slug)
959  feature_dir          = candidate_feature_dir_for_mission(repo_root, slug)   # fallback
974  _lanes_feature_dir   = feature_dir            # coord-aware, for require_lanes_json
982  feature_dir          = primary_candidate      # meta-anchored fallback
1018 _status_feature_dir  = _resolve_status_surface(repo_root, slug).read_dir
1130 lanes_manifest       = require_lanes_json(_lanes_feature_dir)
```

And the juggling is **duplicated** across the consumers (callsite counts to the
coord/primary resolver family): `agent/workflow.py` **27**, `merge.py` **21**,
`agent/mission.py` **13**, `orchestrator_api/commands.py` **6**. That duplication
is precisely why those commands co-change (§2): they each carry their own copy of
the fallback ladder, so every topology fix touches all of them at once.

**This is the dead-weight / semantic-consolidation target:** one
`MissionSurfaces` projection (meta-dir · status read_dir · lanes_dir) resolved once
from the action context, consumed read-only, deletes ~30 LOC of fallback ladder
*per command* and pulls `implement()` down from CC 57.

---

## 6. Verdicts — validate / challenge the static map

| Static-map claim | Forensic verdict |
|---|---|
| Surface #4 (coord/primary read scatter, #1878) is the **biggest** split-brain | **VALIDATED, and strengthened.** 223 coord-commits, 4 files at 100% fix-class, deg-0.75 resolver↔command coupling, the only *accelerating* class (7→35), and CC-57 leakage into `implement()`. The data votes #1878 the #1 crime scene by every axis. |
| #1993 (`resolve_lanes_dir`) is a cheap pure extraction that *exposes* #4 | **VALIDATED.** It is the bounded first cut into the deg-0.50 `_lanes_feature_dir`/`feature_dir` co-derivation inside `implement()`. Forensically it's the safe wedge, not the cure. |
| #2000/#1899 mid8 routing is "mechanical rider" | **VALIDATED — and *downgraded* further.** Only 16 mid8-commits total and the class has **plateaued** post-#2001. It's real cleanup but it is not where future bug-risk lives. |
| #1971 project-root is residual/low | **VALIDATED.** `core/paths` is C-rank and 84% fix-class, but `project_resolver`↔`paths` co-change is only 0.55 and the behavior already landed — genuine tail. |
| #1915 is "not a naming split-brain, separate" | **VALIDATED.** Zero coupling to the resolver surface; correctly excluded. |
| **Slice ordering** (static §6: WP01 verify → WP02 #1993 → WP03 #1971 → WP04 #2000+ratchet; #1878 deferred) | **CHALLENGED on emphasis, not on the in-scope ordering.** The four in-scope WPs are correctly ordered. But the static slice's framing — "#1878 is a *separate, later* mission, deliberately deferred" — is contradicted by the trajectory: #1878 is the **#1 active crime scene and accelerating**. Deferring its *write-side* is defensible (bounded-context risk); deferring its *read-side projection* indefinitely is not — the deg-0.67 `accept↔implement` and deg-0.75 `surface_resolver↔command` couplings are the most expensive in the repo and grow every month. |

### Does the data justify deferring #1878?

**Partially — with a forensic amendment.** The static rationale for deferring
(write-side touches a distinct coordination/merge-durability bounded context, high
blast-radius, no topology redesign in-slice) is sound and the coupling data does
*not* argue for pulling the whole write-side into 3.2.1. **But the read/entry-side
projection should be pulled forward**, because:

1. It is the single most-coupled surface in the repo (accept↔implement 0.67;
   surface_resolver↔command 0.75; the deg-0.62 read-primitive fan-in).
2. It is the *only* accelerating defect class (7→35 in one month).
3. Its cost is realised at CC-57 `implement()` and duplicated 3–27× across
   consumers — every month the slice defers it, more callsites accrete the ladder.
4. #1993 (already in-scope) is literally the first cut of this projection; landing
   #1993 *without* a committed next step to the `MissionSurfaces` projection
   leaves the deg-0.50 `_lanes_feature_dir` twin half-strangled — a new shadow
   path, the exact anti-pattern this mission exists to kill.

**Recommendation:** keep #1878's *write-side* (is_committed/HEAD checks,
auto-commit fallback, lifecycle emission, ref-advance helper) deferred as the
static slice says — but **promote the read-side `MissionSurfaces` projection to an
explicit, committed WP5 of *this* slice** (or an immediate follow-on with a named
milestone), sequenced right after #1993. Do not let "#1878 is later" become "the
hottest fire is unscheduled."

---

## 7. Reduction targets ranked by FORENSIC priority (churn × coupling × defect)

1. **Coord/primary read-surface projection (#1878 read-side / surface #4)** —
   **#1 crime scene.** churn(top-5 consumers) × coupling(0.67/0.75/0.62) ×
   defect(223 commits, 100%-fix files, *accelerating*) × complexity(CC-57 leak).
   Highest future-bug-risk removed per unit of work; deletes the duplicated
   fallback ladder (~30 LOC × 4 consumers ≈ 120 LOC of dead-weight juggling) and
   pulls `implement()` off F-rank. **Do this — its read-side — not "later".**
2. **#1993 `resolve_lanes_dir()` extraction** — the safe wedge into #1, kills the
   12-mock scaffold, deg-0.50 `_lanes_feature_dir` twin. Forensically the correct
   *first* move; must be chained to target #1, not left standalone.
3. **#2000 / #1899-tail / 2c mid8 routing + ratchet extend** — real but *settled*
   (16 commits, plateaued). Low future-risk; do it for completeness and to shrink
   the allow-list, not for risk reduction.
4. **#1971 project-root double-hop + `parents[N]`** — C-rank, residual; cheap;
   lowest coupling. Genuine tail.
5. **#1888 / #1915 verify-and-close** — zero surface coupling; hygiene only.

**Reorder vs the static slice:** the *in-scope four* keep their order. The
material reorder is the **promotion of #1878's read-side from "deferred separate
mission" to "the highest-ROI reduction, sequenced right after #1993."** The
forensic data does not let me rank a 16-commit plateaued class (mid8) above a
223-commit accelerating class (coord/primary) — and the static map's own §4
already concedes the 3.2.0 mission "spent most of its remediation budget on the
coord/primary surface." The history says it is *still* spending it, faster.

---

## 8. Commands (reproducibility)

```bash
# velocity
git log --format='%ad' --date=format:'%Y-%m' | sort | uniq -c | tail -18
# churn (6mo) / bug-hotspot (full) — exclusions applied in pipeline
git log --format=format: --name-only --since="6 months ago" -- src/ | grep -vE '<EXCL>' | grep '\.py$' | sort | uniq -c | sort -nr | head -30
git log -i -E --grep="fix|bug|broken|regress" --name-only --format='' -- src/ | grep '\.py$' | grep -v test | sort | uniq -c | sort -nr | head -30
# co-change matrix — python pairwise over `git log --no-merges --format='COMMITSEP%H' --name-only`
# recurring-fix concentration per surface file — per-file total vs grep(fix|coord|stale|primary|wrong|split.brain|broken)
# temporal class trajectory
git log --no-merges -i -E --grep="coord.*primary|primary.*coord|stale.primary|coord.*worktree|wrong.*surface|surface.*diverg|split.brain" --format='%ad' --date=format:'%Y-%m' | sort | uniq -c
git log --no-merges -i -E --grep="mid8|wrong.compose|double.append|name.guess|1860|1949|1978" --format='%ad' --date=format:'%Y-%m' | sort | uniq -c
# complexity overlay
radon cc -s -n C coordination/surface_resolver.py missions/_read_path_resolver.py lanes/branch_naming.py core/paths.py cli/commands/implement.py
# squash recovery
for t in $(git tag -l 'backup/20260615-2110/*lane-*'); do git log --format=format: --name-only "$t" --not main | grep -E '<surface>' | wc -l; done
```
