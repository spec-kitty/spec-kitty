---
title: 3.2.1 scoping — Debbie severity scoring (NEUTRAL panel)
description: Debugger Debbie's neutral severity scoring of the 3.2.1 scoping candidates, a no-predetermined-answer panel pass, read-only at 3.2.0.
doc_status: deprecated
updated: '2026-06-16'
---
# 3.2.1 scoping — Debbie severity scoring (NEUTRAL panel)

**Author:** Debugger Debbie (NEUTRAL severity-scoring pass — no predetermined answer).
**Branch:** `design/naming-identity-ssot-alignment` @ 3.2.0 (read-only; no commit/switch).
**Date:** 2026-06-16.
**Directives applied (debugger-debbie.agent.yaml):** D-001 (find the owning boundary / structural
fork, not the symptom), D-003 (persist falsified/surviving hypotheses), D-030 (does a producer-
conformance gate actually prevent recurrence?), D-032 (divergence-matrix lens for two-surface bugs).

**Lens:** bug-reality + severity. For each bug candidate I reproduced the logic path against the
code and cite `file:line`. For epics/slices/naming I scored the severity of the *problem addressed*.
Scores are 1–5 (5 = most severe / most-verified / highest impact). This is a fresh verification —
I did **not** inherit the red-team's priority verdict; I re-derived each from code.

---

## Verification notes (the evidence behind each score)

### #1716 — coordination topology coherent from create→planning (P0, write-side) — VERIFIED REAL, OPEN

- `mission create` writes the topology-activation signal immediately:
  `src/specify_cli/core/mission_creation.py:411` (`meta["coordination_branch"] = …`).
- The coord **worktree** is NOT materialised at create — the read resolver itself documents the gap:
  `src/specify_cli/missions/_read_path_resolver.py:241-242` ("the transitional window between
  `mission create` and the first coord-worktree materialisation").
- The recent topology-stabilization mission (01KTZVQ2, squash `991162c0a`) closed
  **#1164/#1883–#1888 + read-surface/ff-merge slices of #1878** — but its issue list does **not**
  include #1716 (`kitty-specs/coordination-topology-stabilization-01KTZVQ2/spec.md:7`). It added a
  graceful read-side *fallback* to primary during the window (mitigation) and FR-003/FR-010 fix two
  *symptoms* (setup-plan accepting a coord-committed spec; zero manual ff-merges). **The architectural
  root cause #1716 names — write/topology split where the signal is set before authority materialises
  — is still present.** GitHub state: OPEN (confirmed via API).
- **D-001 verdict:** this is the *owning boundary* defect — the write side authors identity/topology
  while the authoritative surface does not yet exist. Highest blast radius of the candidate set.

### #1832 — implement claim succeeds but "no workspace could be resolved" (P1, read-path) — VERIFIED REAL, OPEN

- Logic path: `src/specify_cli/cli/commands/agent/workflow.py:1336` (first resolve) → on
  `not workspace.exists`, `top_level_implement(...)` creates the worktree (`:1357`) → **re-resolve**
  `:1372` → if still `not workspace.exists`, the exact reported error fires `:1375`.
- The re-resolution depends on `find_context_for_wp` → `build_feature_context_index`
  (`src/specify_cli/workspace/context.py:434`), and only falls through to a derived path with
  **`mission_id=None`** (legacy grammar `{slug}-{lane}`, no mid8) at `context.py:819-821`. A
  read-after-write where the just-created modern-grammar (`{slug}-{mid8}-lane-{id}`) worktree is not
  re-indexed in-process resolves to a non-existent legacy path → the error.
- **D-032 verdict:** classic two-surface divergence — the CREATE path and the RESOLVE path disagree
  on the workspace identity. The issue's own "single resolution path" suggested-direction is correct.
- No fix commit references #1832; the brittle re-resolve at `:1372` is unchanged. Still OPEN.
- **Severity tempering:** worktree/branch/status are all actually correct; the failure is confined to
  the final report + prompt-regen skip. Workaround exists (use canonical `kitty-specs/.../WPxx.md`).
  The *dangerous* part is the skipped `/tmp/spec-kitty-implement-WPxx.md` regen colliding across
  missions — that elevates it above cosmetic.

### #1827 — merge baseline validation before baseline_merge_commit written (P1) — **OVERSTATED / LIKELY ALREADY FIXED**

- The issue claims a *circular* ordering: assert-before-write. **Current code orders it correctly:**
  1. `_record_baseline_merge_commit` writes the field into the **target-checkout** meta.json
     (`src/specify_cli/cli/commands/merge.py:2574`, writing to `target_feature_dir`).
  2. `baseline_meta_path` is appended to `files_to_commit` (`:2694-2695`).
  3. `safe_commit` lands it on the target branch (`:2708`, capability `MERGE_BOOKKEEPING`).
  4. **Only then** `_assert_baseline_merge_commit_on_target` validates the committed value (`:2741`).
- The assert reads the **recorded** working-meta baseline, not a re-derived HEAD, expressly to make
  `--resume` convergent (`:1727-1734`). The "re-run re-merges and fails identically" symptom is
  guarded by resume reconciliation. Reported on rc40/rc41; the ordering + resume fix landed via the
  coordination/merge-stabilization line (`78024bd48` "persist target bookkeeping", `aa9ec6392` "stage
  merge bookkeeping from target checkout", squash `991162c0a` / `3f2af08f0` #1879). GitHub: still
  OPEN, but the code no longer exhibits the described circular failure.
- **D-003 (persist):** H-VERIFY — the *exact* failure in #1827's body is not reproducible against
  HEAD. Recommend: re-test on current build and **close as fixed** unless a residual resume edge is
  shown. Do NOT lead 3.2.1 with this.

### #1891 — agent --json broken — PARTIALLY FIXED; one verified residual

- Part 1 (`map-requirements --json` "CommitResult is not JSON serializable"): **FIXED** —
  `4c492aa85`/`bc927ef80` (present on this branch; `committed` is now a bool + `commit_sha`).
- Part 2 (`agent action implement --json` rejected): **STILL REAL** — the command signature
  `implement(...)` at `src/specify_cli/cli/commands/agent/workflow.py:1140-1162` has **no `--json`
  option**; an orchestrator cannot get `workspace_path`/`prompt_file`/lane as structured data. This
  is the residual, and it directly degrades the implement-review loop's machine surface.
- Part 3 (preamble before JSON on `finalize-tasks`/`setup-plan`): not separately re-verified;
  bounded.
- **Severity tempering:** affects orchestration/automation, not data integrity; human output works.

### #1619 / #1666 — execution-context / domain-boundary epics (P0 epics)

- The *problem* (coord/main/lane split-brain authoring identity in ≥2 surfaces) is exactly what
  #1716/#1832 are concrete instances of — high severity at the class level. But the synthesis +
  red-team (corroborated here) refute "thread the ExecutionContext everywhere" as the *fix*: the
  composite is a mutable `@dataclass` with an internal `branch_name`≠`branch_ref.target_branch`
  inconsistency, and threading converges on ~2 sites. **A shippable 3.2.1 slice is small** — fix the
  internal inconsistency at the 2 context-holding sites *after* the write-side authority is
  consistent. Score reflects the *problem* severity, not the (refuted) full-epic framing.

### #1878 write-side slice (P2 umbrella)

- The coordination-stabilization mission already consumed the read-surface/ff-merge portions of
  #1878. The *remaining* bounded write/entry slice is essentially the #1716 root cause re-framed.
  Severity inherits from #1716; as a standalone P2 umbrella its incremental value is the structural
  guard, not a distinct new bug.

### Naming routing rider (#2000/#1971/#1993/#1888/#1900)

- The authority exists (`mid8`/`resolve_mid8` at `src/specify_cli/lanes/branch_naming.py:122,169`);
  **20** bare `mission_id[:8]`/`[0:8]` sites remain in `src/specify_cli/` (grep-verified). Routing
  them is cheap and real (I conceded C1 in the red-team pass). **But:** the ratchet
  (`tests/architectural/test_no_worktree_name_guess.py`, `\bmid8\b`) passes *today* with those 20
  sites live → it is a syntax tripwire, not a completeness oracle (D-030). None of the recurring
  high-severity bugs (#1716/#1832/#1827) is a bare-`[:8]` slice — they are surface-selection /
  read-after-write / ordering bugs. **Lowest problem-severity of the set.**

---

## Scored table

| Candidate | Severity | Evidence (verified-real?) | User/launch-impact | One-line justification + file:line |
|---|---|---|---|---|
| **#1716** topology create→planning (P0) | **5** | **5** | **5** | Launch-blocker root cause still live; signal set before authority materialises — `mission_creation.py:411` vs `_read_path_resolver.py:241-242`; OPEN, not in 01KTZVQ2's issue list (`coordination-topology-stabilization-01KTZVQ2/spec.md:7`). |
| **#1832** no-workspace-resolved (P1) | **4** | **5** | **4** | Reproduced create→re-resolve divergence `workflow.py:1336→1357→1372→1375`; legacy-grammar fallback `context.py:819-821`; dangerous prompt-regen skip; workaround exists. OPEN. |
| **#1827** merge baseline ordering (P1) | **2** | **2** | **2** | **Overstated/likely-fixed:** record→commit→assert is correctly ordered `merge.py:2574→2695→2708→2741`; resume-convergent by design `:1727-1734`. Body not reproducible on HEAD. |
| **#1891** agent --json (P1) | **3** | **4** | **3** | Part 1 FIXED (`4c492aa85`); **residual real**: `action implement` has no `--json` `workflow.py:1140-1162`. Automation-surface, not data-integrity. OPEN. |
| **#1619/#1666** execution-context epics (P0) | **4** | **4** | **3** | Problem (split-brain authoring) is real & high-class severity (#1716/#1832 are instances); the *fix framing* (thread-everywhere) refuted; shippable slice is small (~2 sites). |
| **#1878 write-side slice** (P2) | **4** | **3** | **3** | Read-surface/ff-merge parts already shipped (01KTZVQ2); remaining slice ≈ #1716 root cause; value is the structural guard. |
| **Naming routing rider** | **2** | **4** | **2** | Cheap, real consolidation (20 `[:8]` sites, `branch_naming.py:122,169`); ratchet is a syntax tripwire passing today with 20 live sites (`test_no_worktree_name_guess.py`); not the recurring high-severity class. |

---

## Top-3 by severity (Debbie / verified)

1. **#1716 (P0, write-side topology).** The highest-blast-radius, verified-still-open defect: the
   topology signal is authored at `mission create` before the authoritative coord worktree exists,
   and the recent stabilization mission closed adjacent issues but **not this root cause**. This is
   the *owning-boundary* fix (D-001). **Lead 3.2.1 here.**
2. **#1832 (P1, read-path).** Verified create-vs-resolve divergence (D-032) hitting *every* claim in
   at least one dogfood mission; the prompt-regen skip makes it more than cosmetic. Cheap, contained,
   high-frequency. Strong second.
3. **#1619/#1666 — a *bounded* execution-context slice.** Score the problem class, not the refuted
   "thread everywhere." The smallest defensible slice: make the composite's internal
   `branch_name`/`branch_ref` consistent + immutable at the ~2 context-holding sites, sequenced
   *after* the write side is fixed. (#1891-residual is a worthy cheap rider but lower-severity.)

**Demote:** #1827 (overstated — re-test then close), and the **naming rider** (lowest problem-
severity; keep as a cheap opportunistic rider + honest tripwire, never the lead).

## Newly-surfaced item (not in the candidate list)

- **No new HIGH-severity *bug* outside the set.** The open-P0 list is #1716/#1666/#1619 plus
  meta-trackers (#1599/#1601) and known-debt (#1766 ownership leeway). The synthesis-cited
  **god-modules** (`merge.py` / `agent/mission.py` high CC) are a *maintainability* risk that
  amplifies recurrence cost (#1716/#1827 both live in `merge.py`'s blast zone) but are not a
  standalone launch bug — fold extraction into whichever of #1716/#1827 touches those files.

## Persisted hypotheses (D-003 — so they are not re-litigated)

- **H-VERIFY-1:** #1827's circular-ordering body does **not** reproduce on HEAD (record→commit→assert
  is ordered correctly, resume-convergent). Re-test on current build; close if green.
- **H-SURVIVES-1:** #1716's write-side root cause survives the 01KTZVQ2 mission (which fixed
  neighbours + a read-side fallback, not the materialisation-timing split).
- **H-SURVIVES-2:** #1832 is a read-after-write/two-surface divergence, not a naming-slice bug; the
  naming rider would not fix it.
- **H-FALSIFIED-1:** "All four P1 bugs are live" — *falsified*; #1891 part 1 is fixed and #1827 is
  (very likely) fixed.
