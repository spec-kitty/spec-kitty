---
title: Naming/Identity SSOT Strangler — Implementer Feasibility (python-pedro lens)
description: "Python Pedro's implementer feasibility for the naming/identity SSOT strangler: call-graphs, threading cost, and test scaffolding, read-only at 3.2.0."
doc_status: deprecated
updated: '2026-06-16'
---
# Naming/Identity SSOT Strangler — Implementer Feasibility (python-pedro lens)

**Profile:** python-pedro (implementer — feasibility, call-graphs, test scaffolding).
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0. No commits/switches made.
**Date:** 2026-06-16.

## Directives applied (python-pedro)

- **DIR-010 Specification Fidelity** — verify every issue claim against real code before scoping; do not carry issue prose that the merged 3.2.0 code already invalidated.
- **DIR-024 Locality of Change** — each consolidation stays at its own seam; no drive-by widening (#1993 explicitly out-of-scope for #1991).
- **DIR-025 Boy Scout** — when routing a compose site, tighten the ratchet allow-list in the SAME WP (shrink, don't grow).
- **DIR-030 Test+Typecheck Gate** — ruff/mypy clean on new code; every new branch/helper gets a focused test in the same WP.
- **DIR-034 Test-First** — red-green-refactor; the #1993 extraction is a TDD poster child (write the zero-mock test first, then extract).
- **Tactic: test-scaffolding-as-design-smell** — the 12-mock test in `TestImplementCoordTopologyLanesJson` (tests/agent/test_implement_command.py) is the design signal driving #1993; the fix is a pure seam, not more mocks.

## HEADLINE FINDING — most of the issue surface is ALREADY SHIPPED in 3.2.0

I grepped every claim. **Three of the seven issues are functionally complete on this branch**, and a fourth (#1899) is ~85% done. Carrying their issue prose verbatim into the spec would produce phantom scope. Code-grounded status:

| Issue | Issue's premise | Verified code reality | Real residual |
|---|---|---|---|
| **#1888** finalize-tasks existence-check | "owned_files never existence-checked" | **DONE.** `validate_glob_matches()` (`src/specify_cli/ownership/validation.py:319`) already classifies literal-vs-glob, hard-errors on literal zero-match with nearest-match suggestion, soft-warns on glob zero-match, suppresses via `create_intent`. Wired at `cli/commands/agent/mission.py:3348-3371` (shipped as #1886, T015-T018, FR-006). | **NONE / verify-only.** #1888 is a duplicate of the already-merged #1886. Close as fixed after a confirming test for the exact #1888 typo scenario. |
| **#1915** `_merge_dependency_lane_tips` atomicity | "non-atomic; earlier dep merge survives later conflict" | **DONE — provably.** Snapshot+reset (option **(a)**) implemented: `_current_head()` snapshot at `worktree_allocator.py:291`, `git reset --hard <pre_loop_ref>` at lines 336-342 on any conflict. Multi-dep regression tests exist: `test_1915_later_dep_conflict_rolls_back_earlier_dep_merge` + `test_1915_all_clean_deps_still_merge` (`tests/lanes/test_worktree_allocator_atomicity.py:193,227`). | **NONE.** Both the fix AND the ≥2-dep regression test the issue demands are present. Close as fixed. |
| **#1899** worktree dir-name grammar seam + 4th ratchet | "grammar seam + 4th ratchet still open" | **~85% DONE.** `worktree_dir_name()`/`worktree_path()`/`mission_dir_name()` all exist (`lanes/branch_naming.py:484,516,532`). 4th ratchet `tests/architectural/test_no_worktree_name_guess.py` exists and is comprehensive (walks `/`-division chains + name-shape composes, with `file:line` allow-list + strictness proof). | **Residual = the 3 allow-listed sites only** (identical to #2000's list) + the surface_resolver R2 short-circuit dedupe rider. The "seam + ratchet" infrastructure is built; only the migration tail remains. |
| **#2000** route 3 out-of-scope `<slug>-<mid8>` composes | open, accurate | Confirmed: `mission_creation.py:321`, `worktree.py:367`, `worktree.py:370` are allow-listed in the ratchet (`test_no_worktree_name_guess.py:113-115`). | **OPEN — this is the real work.** Mechanical routing + allow-list shrink. |
| **#1993** extract `_resolve_lanes_dir()` pure seam | open, accurate | Confirmed inline at `implement.py:974-982` (`_lanes_feature_dir`). The cited 12-mock test is `TestImplementCoordTopologyLanesJson` in `tests/agent/test_implement_command.py`. | **OPEN — real work.** Pure extraction; high test-ROI. |
| **#1971** 3-way `locate_project_root` split-brain | "3 defs, divergent authority" | **PARTIALLY DONE.** `project_resolver.locate_project_root` now **delegates** to the authoritative `paths.locate_project_root` (deferred import, `project_resolver.py:23`, landed as #1971/commit 8431dd931). The behavior split-brain (`lint`/`helpers` ignoring SPECIFY_REPO_ROOT) is **already closed**. | **Residual = collapse the hops + dedupe.** `__init__.py:52` → `project_resolver` → `paths` is a 2-hop indirection; `core/__init__` re-exports the wrapper. True consolidation = point the 4 `project_resolver` callers + `__init__` wrapper at `paths` and delete the wrapper (verifying no import cycle — the reason it was kept). |
| **#1878** umbrella (coord placement/identity strangler) | epic, 8 deferred items | Out of this mission's core SSOT lane; it's the coordination-branch strangler (different seam family). Items 3 (worktree-naming allocator unification) + 5 (AC10 lint expansion) **touch the same naming seam** and could be co-scoped. | **Reference only** — pull items 3 & 5 if the mission has headroom; the rest is a separate coordination mission. |

**Net: the cohesive 3.2.1 mission is ~2 substantive issues (#2000+#1899-tail, #1993) + 1 cleanup (#1971-tail), NOT seven.** #1888 and #1915 should be closed as already-fixed (file confirming-only tests if desired). This is the single biggest planning input — the spec should NOT size for 7.

---

## Per-issue feasibility

### #2000 — route 3 `<slug>-<mid8>` composes through the seam  ·  **S · low risk · mechanical**

**Targets (verified):**
- `core/mission_creation.py:319-321` — `human_slug = strip_numeric_prefix(mission_slug); mission_slug_formatted = f"{human_slug}-{mid8(mission_id)}"` → the kitty-specs dir name. **Replace with `mission_dir_name(mission_slug, mid8=mid8(mission_id))`** (note: `mission_dir_name` already does the `strip_numeric_prefix` + idempotent-suffix internally, so the local `human_slug` line is also subsumed → net LOC reduction).
- `core/worktree.py:365-370` — `human_slug = strip_numeric_prefix(mission_slug); branch_name = f"{human_slug}-{mid8(mission_id)}"; worktree_path = repo_root / WORKTREES_DIR / branch_name`. This is the **mission** worktree (not lane). **Replace name compose with `mission_dir_name(...)`**; the `repo_root / WORKTREES_DIR / name` join is a legit directory join (leave it, or use a `mission_worktree_path()` helper if one is added — see #1899).
- All 3 sites are git-traced to #601/`c16291214`, predate the seam, currently allow-listed in `test_no_worktree_name_guess.py:113-115`.

**Test strategy:** golden-value parity test — assert `mission_dir_name("057-foo", mid8="01KV6510") == "foo-01KV6510"` already covered; add a parity assertion that the OLD inline f-string output `== mission_dir_name(...)` for the legacy AND embedded inputs (byte-identical proof). Then **remove the 3 entries from `_ALLOWED_SITES`** and let the ratchet prove no regression (DIR-025).

**No-shadow-path risk:** `mission_dir_name` **strips the NNN- prefix** (canonical grammar). The inline composes ALSO call `strip_numeric_prefix` first → byte-identical. CONFIRM there is no pre-existing on-disk dir created with the un-stripped slug at these sites (there isn't — both call strip). The hazard is the *coordination* read path, which composes VERBATIM (`coord_mission_dir_name`, no strip) — **do NOT route these creation sites through the coord variant.** mission_creation/worktree are canonical-create → `mission_dir_name`, correct.

### #1899 — worktree dir-name grammar seam + 4th ratchet  ·  **S (residual only) · low risk**

**The seam + ratchet are already built (3.2.0).** Residual is exactly:
1. The 3 #2000 sites (full overlap — see ownership map).
2. **Dedupe rider:** surface_resolver R2 short-circuit hand-rolls the `.worktrees`-segment test instead of calling its own classifier (alphonso Q1 nit). Target: `src/specify_cli/coordination/surface_resolver.py` — grep the R2 short-circuit for an inline `".worktrees"` literal and route through the classifier. **S, low risk.**
3. Optional: add a `mission_worktree_path()` emit-helper so `worktree.py:370`'s `repo_root / WORKTREES_DIR / name` join also goes through the seam (parallels `worktree_path()` for lanes). Verify against the 5th-ratchet-shape note (`test_no_worktree_name_guess.py:18-29` already anticipates a "no `.worktrees/` literal" shape).

**Test strategy:** the ratchet self-tests the allow-list shrink. Add a unit test for the surface_resolver classifier call (zero-mock, `tmp_path`).

### #1993 — extract `_resolve_lanes_dir()` pure seam  ·  **S/M · low risk · design-relieving**

**Exact inline logic (`implement.py:974-982`):**
```python
_lanes_feature_dir: Path = feature_dir
if not (feature_dir / "meta.json").exists():
    from specify_cli.missions._read_path_resolver import primary_feature_dir_for_mission
    primary_candidate = primary_feature_dir_for_mission(repo_root, mission_slug)
    if (primary_candidate / "meta.json").exists():
        feature_dir = primary_candidate
```

**IMPLEMENTER CORRECTION to the issue's proposed code:** the issue's snippet uses `resolve_feature_dir_for_mission` + `candidate_feature_dir_for_mission` and reassigns `_lanes_feature_dir`. The **actual** code keeps `_lanes_feature_dir = feature_dir` (the coord-aware surface already resolved upstream) and on the meta-missing branch reassigns **`feature_dir`** (not `_lanes_feature_dir`) to `primary_feature_dir_for_mission(...)`. So `_lanes_feature_dir` deliberately retains the COORD-aware dir while `feature_dir` falls back to primary for meta reads. **This is a two-variable dance, not one** — the extraction must preserve BOTH outputs or the seam silently changes which surface `require_lanes_json` reads (regression risk). Recommend the helper return the lanes-dir AND have the caller separately handle the `feature_dir` meta-fallback, OR return a small dataclass `(lanes_dir, feature_dir)`.

**Module placement:** put `_resolve_lanes_dir` (or the pure resolver) in `src/specify_cli/missions/_read_path_resolver.py` next to `candidate_/primary_feature_dir_for_mission` — the blessed KITTY_SPECS path-constructor module (enforced by `test_no_raw_mission_spec_paths.py`). Do NOT inline a new constructor in implement.py.

**Model to mirror:** `resolve_status_surface_with_anchor` (`coordination/surface_resolver.py:433`) returns a surface object with `.read_dir` (used at `implement.py:1018`). The issue cites this as the analog — match its shape for `_status_feature_dir`.

**Test strategy (the payoff):** replaces 12 mocks with `tmp_path`: create a coord-worktree dir with `lanes.json` but no `meta.json`, and a primary dir with `meta.json`; assert the helper returns the coord surface for lanes and the primary for meta. **Zero mocks** (tactic: test-scaffolding-as-design-smell). Write this test RED first.

### #1971 — collapse `locate_project_root` hops  ·  **S/M · low-med risk · cleanup**

**Verified call-graph (122 references; 3 defs):**
- `paths.py:48` (~44 LOC, authoritative: SPECIFY_REPO_ROOT + worktree-pointer + .kittify walk) — the bulk of callers import here.
- `project_resolver.py:8` — **now delegates to paths** (deferred import, line 23). 4 callers: `cli/helpers.py:19`, `cli/commands/lint.py:25`, `__init__.py:53`, `compat/planner.py:779`.
- `__init__.py:52` — wrapper → `project_resolver`. Caller: `__init__.py:125`.

**The behavior split-brain the issue worries about is ALREADY CLOSED** (lint/helpers now inherit env-var+worktree authority via the delegate). Residual is pure DRY: collapse the 2-hop indirection. **Risk = the documented import-cycle hazard** — `project_resolver.py:14-21` explains the deferred import exists precisely to avoid `core/__init__` → `project_resolver` → `paths` → package-init cycle. **Do NOT convert to a module-level import** (the docstring calls that out as a regression). Safe move: repoint the 4 `project_resolver` callers' import sites to `from specify_cli.core.paths import locate_project_root` (deferred where needed), keep `project_resolver.locate_project_root` as a thin re-export OR delete it after `core/__init__` re-export is redirected.

**Test strategy:** existing 26+ caller tests are the safety net; add a focused test asserting `lint`/`helpers` honor SPECIFY_REPO_ROOT (the original split-brain symptom) — this both documents the fix and guards regression. Run `tests/architectural/` for import-cycle/boundary gates.

### #1878 — umbrella (reference only)

Coordination-branch placement/identity strangler; **different seam family** (coord placement vs naming SSOT). Only items **#3 (worktree-naming allocator unification)** and **#5 (AC10 lint expansion to new placement/identity seams)** touch the naming seam. Co-scope ONLY if the mission has headroom after the core lanes. The rest (resolver strangler, ref-advance helper, `_ensure_branch_checked_out` shim, #1827 crash window) is a separate mission — do not absorb.

---

## WP-decomposition sketch (3.2.1 mission) — foundation → routing → enforcement

Mirrors the 3.2.0 mission shape (seam-first → migrate composers → tighten ratchet). **Because #1888/#1915 are done**, the mission is small (~4 WPs). Recommended:

```
WP01  Verify-and-close already-shipped issues (#1888, #1915)        [foundation/hygiene]
      - confirming tests: #1888 exact-typo scenario via validate_glob_matches;
        #1915 already covered — assert + close.
      - owned: tests/ownership/test_glob_matches_*.py (new), issue-matrix verdicts.
      - deps: none. Pure verification; unblocks the spec's scope-truth.

WP02  #1993 — extract _resolve_lanes_dir pure seam                  [foundation seam]
      - extract resolver into missions/_read_path_resolver.py; preserve the
        TWO-variable (lanes-dir vs feature_dir) semantics; zero-mock test.
      - owned: src/specify_cli/missions/_read_path_resolver.py,
        src/specify_cli/cli/commands/implement.py (the 974-982 block only),
        tests/missions/test_resolve_lanes_dir.py (new).
      - deps: none.

WP03  #1971 — collapse locate_project_root hops                     [SSOT consolidation]
      - repoint 4 project_resolver callers + __init__ wrapper at paths;
        keep deferred-import cycle safety; SPECIFY_REPO_ROOT regression test.
      - owned: src/specify_cli/core/project_resolver.py,
        src/specify_cli/__init__.py (lines 52-55 only),
        src/specify_cli/core/__init__.py (re-export),
        src/specify_cli/cli/helpers.py, src/specify_cli/cli/commands/lint.py,
        src/specify_cli/compat/planner.py, tests/core/test_locate_project_root_authority.py (new).
      - deps: none.

WP04  #2000 + #1899-tail — route mission-dir composes + shrink ratchet [routing + enforcement]
      - route mission_creation.py:321 + worktree.py:367/370 through
        mission_dir_name(); add mission_worktree_path() emit-helper (optional);
        surface_resolver R2 classifier dedupe; REMOVE the 3 allow-list entries;
        byte-identical golden-parity tests.
      - owned: src/specify_cli/core/mission_creation.py,
        src/specify_cli/core/worktree.py,
        src/specify_cli/lanes/branch_naming.py (only if adding mission_worktree_path),
        src/specify_cli/coordination/surface_resolver.py (R2 short-circuit only),
        tests/architectural/test_no_worktree_name_guess.py (allow-list shrink),
        tests/lanes/test_branch_naming_parity.py (golden parity).
      - deps: none on others; LAST because the ratchet shrink is the enforcement
        capstone and should land after the routing is proven.
```

### Dependency DAG

```
WP01 (close #1888/#1915)  ─┐
WP02 (#1993 seam)         ─┤  all independent foundations
WP03 (#1971 collapse)     ─┘
                              WP04 (#2000+#1899) — independent, but sequence LAST
                                   (enforcement capstone / ratchet shrink)
```
All four WPs are **independent** (no hard data deps). WP04 is *recommended last* for review clarity (ratchet tightening reads cleanest after routing lands), not because of a code dependency.

### Ownership-overlap hazard map

| File | WPs touching | Hazard | Mitigation |
|---|---|---|---|
| `src/specify_cli/lanes/branch_naming.py` | WP04 only (add `mission_worktree_path`) | LOW — append-only | Single owner WP04. If WP01 wants a golden-table helper, gate it behind WP04. |
| `src/specify_cli/core/worktree.py` | WP04 | none (sole owner) | — |
| `src/specify_cli/core/mission_creation.py` | WP04 | none (sole owner) | — |
| `src/specify_cli/__init__.py` | WP03 | LOW — only lines 52-55 | Scope owned_files to the wrapper; **`__init__.py` change needs pyproject version bump + CHANGELOG (CLAUDE.md rule).** |
| `src/specify_cli/core/__init__.py` | WP03 | re-export edit | sole owner WP03 |
| `src/specify_cli/cli/commands/implement.py` | WP02 (974-982) | this file is huge + hot; #1991/#1992 just touched it | Narrow owned-region to the extraction block; rebase risk if other missions touch implement.py concurrently. |
| `tests/architectural/test_no_worktree_name_guess.py` | WP04 | the ratchet itself — allow-list edit | sole owner WP04; the shrink IS the deliverable. |

**Cross-mission rebase hazard:** `implement.py` and `branch_naming.py` are the hottest files in recent missions (#1908, #1991, #1992, #2000). Land this mission promptly or expect rebases.

---

## No-shadow-path / byte-identical risks (the 3.2.0 lesson)

1. **#2000/WP04 — canonical vs coord grammar.** `mission_dir_name` STRIPS `NNN-`; `coord_mission_dir_name` does NOT. The 3 creation sites already `strip_numeric_prefix` → route to **`mission_dir_name`** (canonical). Routing them to the coord variant would silently change on-disk names. Golden-parity test must cover legacy (`057-foo`) AND embedded (`foo-01KV6510`) inputs to prove byte-identity.
2. **#1993/WP02 — two-surface seam.** The inline code keeps `_lanes_feature_dir` on the COORD surface while reassigning `feature_dir` to PRIMARY for meta. A naive extraction that returns one path collapses the surfaces → `require_lanes_json` reads the wrong dir (silent C-LANES-1 regression). The seam MUST preserve both outputs.
3. **#1971/WP03 — deferred import is load-bearing.** `project_resolver`'s deferred import prevents a package-init cycle (documented at `project_resolver.py:14-21`). Reverting to module-level import is an explicit regression. Keep deferral where the cycle exists.
4. **#1899/WP04 — `.worktrees/` join vs name compose.** The ratchet distinguishes a name-shape compose (flagged) from a legit `dir / ".worktrees" / already_composed_name` join (allowed). `manifest.py:254` and 30+ migration sites are legit joins — do NOT sweep them into the seam. Only the `<slug>-<mid8>` NAME composition routes.
5. **#1888/#1915 — do not "fix" what's fixed.** Re-implementing the already-shipped existence-check or atomicity would create a parallel impl (the exact anti-pattern). Verify, test, close.
