---
title: Naming/Identity SSOT Strangler — Tracker Landscape (planner-priti)
description: "Planner Priti's tracker landscape for the naming/identity SSOT strangler: the issues, epics, and sequencing under the decision-documentation directive."
doc_status: deprecated
updated: '2026-06-16'
---
# Naming/Identity SSOT Strangler — Tracker Landscape (planner-priti)

> **Profile-loaded.** Authored as **Planner Priti** (work decomposition + delivery
> sequencing) under **directive 003 — Decision Documentation Requirement**: every
> close/rescope verdict and the mission-slice recommendation below is documented
> with its rationale and hard evidence link for traceability.
>
> Squad context: spec-kitty 3.2.1 stabilization (the "confusing naming" /
> split-brain strangler). Goal: scope ONE cohesive mission unifying the
> naming/identity/read-path surface through a consistent SSOT, advancing
> **#1868** (canonical-seams epic) + **#1619** (runtime/state overhaul) and
> completing the **#1878** coordination strangler.
> Baseline: branch `research/naming-identity-ssot-strangler` @ cli 3.2.0
> (PR **#2001**, merge commit `fcf9be595`).

---

## 1. Full related-ticket table

Discovered via `gh issue list --state open --search` across 12 term sets
(naming/identity, mid8, split-brain, coordination, feature_dir, project-root,
worktree-naming, ownership, locate_project_root, read-path, lanes-dir). The 7
seed tickets plus everything materially on this surface.

| id | title (short) | state | relation | disposition |
|----|---------------|-------|----------|-------------|
| **#1878** | Umbrella: complete coordination placement/identity strangler (post-3.2.0) | OPEN | **umbrella** (child of #1666) | Stays open; sequences the residuals. Progress note posted. |
| **#1868** | Epic: canonical seams exist in name only — bind authority to type/owner | OPEN | **epic** (mission-identity seam) | Stays open; #2001 advanced it (single `branch_naming.py` authority). |
| **#1619** | Epic: unify mission execution context across coord/main/lane | OPEN | **root epic** | Stays open; #1971/#1993 advance it. |
| **#1666** | Epic: execution-state & context domain-boundary redesign | OPEN | epic (child of #1619) | Stays open; home of #1917. |
| **#1929** | Tracking: post-#1908 adversarial-panel findings | OPEN | meta-checklist | Checklist ticked (all 4 closed); recommend maintainer close. |
| **#1908** | Mission identity panel (#1929 cluster B) | OPEN | panel umbrella | Stays (umbrella, not a single closeable bug). |
| #1899 | Worktree dir-name grammar seam + 4th ratchet | **CLOSED ✓** | child of #1868 | **CLOSED by #2001** (this pass). Residual → #2000. |
| #1915 | `_merge_dependency_lane_tips` non-atomic across deps | **CLOSED ✓** | child of #1795 (#1684 follow-up) | **CLOSED by #2001** (this pass). |
| #1918 | mid8 dual-era heuristic false-positive | **CLOSED ✓** | child of #1868 | **CLOSED by #2001** (this pass). |
| #1949 | `mission_branch_name` double-appends mid8 (#1860 class) | **CLOSED ✓** | child of #1868 | **CLOSED by #2001** (this pass). |
| #1978 | merge preflight drops `-{mid8}` (P1 merge-blocker) | **CLOSED ✓** | child of #1868 | **CLOSED by #2001** (this pass). |
| #1917 | `_validate_base_ref` missing `--` separator | **CLOSED ✓** | child of #1666 | **CLOSED by #2001** (this pass). |
| #1916 | accept-readiness side-effect (ensure_identity) | **CLOSED ✓** | child of #1914 | **CLOSED by #2001** (this pass). |
| **#2000** | Route remaining out-of-scope `<slug>-<mid8>` composes through seam | OPEN | residual of #1899 | **3.2.1 mission — WP1** (tagged). |
| **#1971** | Consolidate 3-way `locate_project_root` split-brain | OPEN | child of #1932; advances #1619 | **3.2.1 mission** (tagged). |
| **#1993** | Extract `resolve_lanes_dir()` pure seam | OPEN | advances #1619/#1666 | **3.2.1 mission** (tagged). |
| **#1888** | finalize-tasks ownership accepts non-existent `owned_files` | OPEN | ownership-validation | **3.2.1 mission** (tagged). |
| #1900 | Drain topology-ratchet C-002 allowlist | OPEN | sibling of #2000 | Candidate / pairs with #2000; sequence in #1878. |
| #1716 | Make coordination topology coherent (create→planning) | OPEN | child of #1878 family | Out-of-scope (broader topology); #1878 sequencing. |
| #1887 | Squash-merge duplicates planning artifacts under `.worktrees/<slug>-coord/` | OPEN | coord read-path | Follow-up (merge-path, not naming SSOT). |
| #1827 | merge baseline-validation circular failure | OPEN | child of #1878 (item 7) | Out-of-scope (crash-window); #1878. |
| #1357 | lock-serialize `CoordinationWorkspace.resolve()` race | OPEN | coordination | Out-of-scope (concurrency, not naming). |
| #1766 | strict `owned_files` induces workarounds | OPEN | ownership | Separate (leeway policy; distinct from #1888). |
| #1979 | WP changes shared contract pinned by out-of-owned test | OPEN | ownership | Separate follow-up. |
| #1890 | doctor recommends nonexistent `worktree repair` cmd | OPEN | coordination UX | Follow-up (doc/UX). |
| #1832 | implement claim reports "no workspace resolved" | OPEN | read-path | Follow-up — re-test after #1993 lands. |

---

## 2. Epic tree

```
#1619  Epic: unify mission execution context across coord/main/lane (ROOT)
│
├── #1666  Execution-state & context domain-boundary redesign
│     └── #1917 ✓ (_validate_base_ref --)            [CLOSED #2001]
│     └── #1993   resolve_lanes_dir() pure seam       [3.2.1]
│
├── #1878  Umbrella: coordination placement/identity strangler (post-3.2.0)
│     ├── #2000   <slug>-<mid8> compose residual       [3.2.1 — WP1]
│     ├── #1900   C-002 allowlist drain                 (pairs w/ #2000)
│     ├── #1827   merge baseline circular failure        (out-of-scope)
│     └── #1716   coord topology coherence               (out-of-scope)
│
#1868  Epic: canonical seams exist in name only (mission-identity seam)
│     ├── #1899 ✓ worktree dir-name grammar + 4th ratchet [CLOSED #2001]
│     ├── #1918 ✓ mid8 dual-era false-positive            [CLOSED #2001]
│     ├── #1949 ✓ mission_branch_name double-append       [CLOSED #2001]
│     └── #1978 ✓ merge preflight drops -mid8 (P1)        [CLOSED #2001]
│
#1914  Umbrella: governed/gate ops no-op-stable
│     └── #1916 ✓ accept-readiness side-effect            [CLOSED #2001]
│
#1795  (#1684 cross-lane family)
│     └── #1915 ✓ multi-dep merge non-atomic              [CLOSED #2001]
│
#1929  meta-checklist (post-#1908 panel) — references #1915/#1917/#1916/#1918
        (NOT their parent; all 4 now ticked)
#1932  (Codebase cleanup & DevEx)
        └── #1971  project-root 3-way split-brain          [3.2.1]
```

**Duplicates / overlaps observed:** none requiring dedup-merge. #2000 is the
named residual of #1899 (correctly split, not a dup). #1971 and #1993 overlap
thematically (both read-path/resolution SSOT) — bundle into one mission but keep
as distinct WPs. #1766 vs #1888 are adjacent but distinct (policy-leeway vs
existence-check) — keep separate.

---

## 3. Close / rescope actions TAKEN

**Conservative rule applied:** closed ONLY with hard merged-code evidence
(seam present + named regression test verified green locally + issue-matrix
`fixed` verdict in mission 01KV6510). All seven below were closed `completed`
with an evidence comment naming PR #2001 (`fcf9be595`), the commit, and the test.

| issue | action | evidence (verified this pass) |
|-------|--------|-------------------------------|
| **#1915** | **CLOSED completed** | `worktree_allocator.py:289–345` snapshot+`reset --hard`; `tests/lanes/test_worktree_allocator_atomicity.py::test_1915_later_dep_conflict_rolls_back_earlier_dep_merge` asserts `HEAD==pre_loop_head` & earlier-dep file absent; 9/9 green |
| **#1899** | **CLOSED completed** | `branch_naming.py:484–529` `worktree_dir_name`/`worktree_path`; `tests/architectural/test_no_worktree_name_guess.py` (4th ratchet) 3/3 green. Residual → #2000 (not orphaned) |
| **#1978** | **CLOSED completed** | `merge/preflight.py:94–97` routes via `mission_branch_name_required`; `tests/merge/test_mid8_embedded_preflight.py`; 41/41 green |
| **#1949** | **CLOSED completed** | `branch_naming.py:212–231` `_idempotent_legacy_body`; RED-first `mission_id=None` test in `test_branch_naming_seam.py` green |
| **#1918** | **CLOSED completed** | `branch_naming.py:142–200` heuristic-demotion + authoritative `resolve_mid8`; callers routed (commit 38f0bdc47); regressions green |
| **#1917** | **CLOSED completed** | `_validate_base_ref` uses `--`/`--end-of-options`; `tests/specify_cli/cli/commands/test_implement_base_ref.py` 3/3 green |
| **#1916** | **CLOSED completed** | read-only readiness paths; `tests/specify_cli/cli/commands/test_accept_readiness_no_write.py` 5/5 green under `SPEC_KITTY_ENABLE_SAAS_SYNC=1` |

**Rescope / tag (commented, NOT closed):**

| issue | action |
|-------|--------|
| **#2000** | Tagged 3.2.1 mission (WP1); confirmed as the live residual of #1899; pairs with #1900. |
| **#1971** | Tagged 3.2.1 mission; project-root SSOT (only `paths.py` tier fixed by #1965). |
| **#1993** | Tagged 3.2.1 mission; read-path/lanes-dir pure seam. |
| **#1888** | Tagged 3.2.1 mission; ownership existence-check; distinct from #1766/#1979. |
| **#1929** | Checklist boxes ticked (all 4 findings closed); recommended maintainer-close. |
| **#1878** | Strangler progress note posted (7 closed, 4 scoped into 3.2.1, residuals sequenced). |

---

## 4. Recommended 3.2.1 mission slice

**Mission theme:** "Naming/Identity & Read-Path SSOT — strangler completion."
One cohesive mission, advancing #1868 + #1619, completing #1878 items #3/#5.

**In-scope (bundle — the cohesive slice):**

| WP | issue | why it belongs | size |
|----|-------|----------------|------|
| WP1 | **#2000** | Route the 3 allow-listed `<slug>-<mid8>` composes (`mission_creation.py:321`, `worktree.py:367/370`) through the canonical seam; remove from the ratchet allow-list. Byte-identical via golden table. Pair with #1900. | S (mechanical) |
| WP2 | **#1971** | Consolidate the 3-way `locate_project_root` split-brain onto `paths.locate_project_root`; verify the 4 `project_resolver` callers want env-var/worktree authority; watch import cycles. One project-root authority. | M |
| WP3 | **#1993** | Extract `_resolve_lanes_dir()` pure topology-aware seam (the 3-surface family: feature_dir / status / lanes). No behavior change; kills 12-mock scaffolding smell. | S–M |
| WP4 | **#1888** | finalize-tasks: warn/fail when a non-glob `owned_files` entry matches zero existing files (typo guard; restores the parallel-WP collision guard). | S |

Rationale for the bundle: all four are "one authority for *where/what is named*"
problems on the same surface (#2000 = name compose; #1971 = project-root resolve; #1993 = read-path resolve; #1888 = ownership-path existence). They share reviewers,
the golden-value/seam test idiom, and the SSOT framing — high cohesion, low
cross-coupling, parallelizable into ≥3 lanes.

**Out-of-scope / follow-up (keep separate):**

- **#1900** — C-002 allowlist drain: pairs with #2000 but is a separate ratchet
  surface; fold in only if WP1 lands trivially, else sequence next under #1878.
- **#1827** (merge baseline circular failure), **#1357** (resolve() race),
  **#1716** (coord topology coherence), **#1887** (squash-merge dup artifacts):
  coordination/merge mechanics, NOT naming SSOT — stay under #1878 sequencing.
- **#1766** (ownership leeway policy), **#1979** (shared-contract pin break):
  ownership-policy follow-ups, distinct from #1888's existence-check.
- **#1890** (doctor stale cmd), **#1832** (workspace-resolve report): UX/doc and
  a likely-fixed read-path symptom — re-test #1832 after WP3.

**Claim / assignment plan:** assign the four in-scope tickets (#2000, #1971, #1993, #1888) to **stijn-dejongh**; reference **#1878** (strangler umbrella),
**#1868** (seam epic), and **#1619** (runtime/state root) in the mission spec's
issue-matrix and in each tracker comment naming the mission, per the
ticket-based-mission-hygiene standing rule.
