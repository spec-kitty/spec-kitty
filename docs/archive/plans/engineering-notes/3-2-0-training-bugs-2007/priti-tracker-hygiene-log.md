---
title: '#2007 tracker-hygiene action log — planner-priti'
description: "Planner Priti's tracker-hygiene action log for #2007: the scoping and recording-only operations performed under operator authorization (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# #2007 tracker-hygiene action log — planner-priti

**Date:** 2026-06-16 · **Operator authorization:** "go" (2026-06-16) · **Op type:** tracker hygiene (scoping/recording only — no implementation).

## Hard constraints honored

- **CLOSE NOTHING** — zero issues closed. All 6 #2007 children + the epic remain OPEN.
- **ASSIGN NOBODY** — no assignee added by this op. (Pre-existing assignee on #1891 = `LynnColeArt`, left untouched — not added by me.)
- **No patch version numbers prescribed** — only the minor-cycle milestone label `3.2.x` used.
- **Native sub-issue graph** used for parenting (not body checklists), per `HOW_TO_MAINTAIN.md`.

---

## Task 1 — record the 2 existing-ticket mappings (no assign, no close)

| Issue | Bug | Comment | Native sub-issue of #2007 |
|-------|-----|---------|---------------------------|
| **#1890** | bug #13 — coord-worktree repair surface | mapping comment + `doctor workspaces --fix` fix direction | added |
| **#1891** | bug #16 — `agent action implement --json` contract | mapping comment naming the exact residual | added |

- Comment on #1890: https://github.com/Priivacy-ai/spec-kitty/issues/1890#issuecomment-4718319284
- Comment on #1891: https://github.com/Priivacy-ai/spec-kitty/issues/1891#issuecomment-4718319875
- **Re-home note:** both were parented under #1801 (Epic: CLI user experience). GitHub enforces a **single native parent**, so I `DELETE`d each from #1801 and `POST`ed to #2007 (operator-directed umbrella parent for this bug class). #1801 referenced in prose so the functional-epic linkage is preserved.
  - re-home note comments: #1890 → issuecomment-4718327472 · #1891 → issuecomment-4718327623

## Task 2 — fix the milestone inversion

Attached to open milestone **3.2.x (#4)** via `gh issue edit <n> --milestone "3.2.x"`:
- **#2007** (epic) → 3.2.x
- **#1890** → 3.2.x
- **#1891** → 3.2.x
- (plus the 4 net-new children below, created directly on 3.2.x)

No closed milestone touched.

## Task 3 — net-new sub-issues along #2007's 6 suggested clusters

The 6 suggested clusters map to: **4 net-new** issues opened here, **2 already covered** by existing residuals (#1890 = coord-worktree-repair cluster; #1891 = implement/review-JSON cluster) which were parented + milestoned in Task 1/2 instead of duplicated.

| New # | Cluster | Member bugs | Type | Labels | Milestone | Parent |
|-------|---------|-------------|------|--------|-----------|--------|
| **#2008** | C1 — Command-surface validation & docs/prompt drift | #1, #5, #9 (+ folded #3 specify bootstrap UX) | Bug | bug, priority:P1 | 3.2.x | #2007 |
| **#2009** | C2 — Charter status/sync/preflight consistency | #2 | Bug | bug, priority:P2 | 3.2.x | #2007 |
| **#2010** | C3 — Mission context / read-path resolver unification | #4, #7, #8, #11, #12, #14, #15 (+ folded #10 finalize glob) | Bug | bug, priority:P0, launch-blocker | 3.2.x | #2007 |
| **#2011** | C6 — Submodule / root detection hardening | #6 | Bug | bug, priority:P0, launch-blocker | 3.2.x | #2007 |

Each body captures the member bug numbers + the **pinned root cause from debbie** (verbatim where critical):
- **#2011 (C6/#6):** second root authority — `assert_initialized` → `resolve_canonical_root` (`core/paths.py:284-288`) walks UP into the parent repo on a submodule `.git` file; #1944/#1965 patched only `locate_project_root`. Reproduces on HEAD/v3.2.0. Launch-relevant.
- **#2010 (C3/#7+class):** `is_committed` (`missions/_substantive.py`) has no primary-branch leg (coord-only); `_commit_to_branch` (`cli/commands/agent/mission.py:1178-1195`) silently swallows commit failures → `commit_created: None` + untracked artifact; the "single resolver" is not behavior-equivalent across input classes. **#10/#11 need live repro in Robert's monorepo/coord env.**

### Folded-in loose bugs (no inventory bug dropped)

- **bug #3** (specify bootstrap `NO_BRIEF`/`NO_TICKET` typed-state) → comment on **#2008** (C1). issuecomment-4718343091
- **bug #10** (finalize zero-match glob exit-1; distinct from #1888; needs live repro) → comment on **#2010** (C3). issuecomment-4718343238

## Task 4 — functional-epic cross-references (no double-parent)

- **#2010 (C3)** body references functional epics **#1832 / #1716 / #1619** (#1716 carries `launch-blocker`) for the underlying read-path/coord-topology surface — native parent stays the #2007 umbrella.
- **#1890/#1891** comments reference **#1801** (CLI UX epic) as the prior functional home.

---

## Final state (verified via GraphQL)

Issue #2007 (OPEN, milestone 3.2.x) native sub-issues:

| # | State | Type | Milestone | Labels | Assignee |
|---|-------|------|-----------|--------|----------|
| 1890 | OPEN | Bug | 3.2.x | bug, priority:P1 | — |
| 1891 | OPEN | Bug | 3.2.x | bug, priority:P1 | LynnColeArt (pre-existing, not added here) |
| 2008 | OPEN | Bug | 3.2.x | bug, priority:P1 | — |
| 2009 | OPEN | Bug | 3.2.x | bug, priority:P2 | — |
| 2010 | OPEN | Bug | 3.2.x | bug, priority:P0, launch-blocker | — |
| 2011 | OPEN | Bug | 3.2.x | bug, priority:P0, launch-blocker | — |

**Confirmation: NOTHING was closed. NOBODY was assigned by this op.**
