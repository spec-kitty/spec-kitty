---
title: Randy Reducer — Split-Brain Authority Map (naming/identity SSOT strangler)
description: "Randy Reducer's split-brain authority map for the naming/identity SSOT strangler: the behavioral envelope for each divergent authority."
doc_status: deprecated
updated: '2026-06-16'
---
# Randy Reducer — Split-Brain Authority Map (naming/identity SSOT strangler)

> **Persona:** I am **Randy Reducer**. Semantic compression: fewer lines, same
> behavior, proven. This map establishes the *behavioral envelope* for each
> concept first, then finds the competing implementations of that one concept,
> names the single SSOT it must collapse to, and quantifies the LOC/dead-weight
> delta — **grep-backed, not issue-prose-trusted**.

## Loaded directives / tactics applied

- **split-brain-authority-detection** (`semantic-compression-semantic-consolidation`):
  for every concept (project-root, mid8, mission-dir name, worktree path,
  lanes-dir, status/feature read surface, ownership validity) I locate **every**
  competing implementation and identify the ONE that must own the behavior. No
  silent fallbacks, no parallel authorities.
- **semantic-compression** (paradigm + `redundancy-discovery` +
  `dead-weight-elimination`): only delete redundancy that grep evidence proves
  redundant; smallest behavior-preserving diff; route callers through the
  canonical seam.
- **DIR-024 Locality of Change** + **behavioral-boundary-mapping**: each
  consolidation routes callers through the existing seam without widening into a
  speculative rewrite.
- **test-scaffolding-as-design-smell**: heavy mock-count regression tests
  (#1993's 12-mock test) are the oracle that a pure seam is missing.

**Verification posture:** I corrected the issue surface against the actual code.
Two of the seven issues are **already (partly) closed** and must be *verified and
closed*, not re-implemented — flagging that up front is itself a reduction
(prevents re-introducing shadow paths over working authorities).

---

## Authoritative split-brain table

| # | Surface (concept) | Competing implementations (file:line) | Proposed SSOT | Dead-code / LOC delta | Issue refs | Risk |
|---|---|---|---|---|---|---|
| 1 | **Project-root resolution** | `core/paths.py:48` `locate_project_root` (~44 LOC; env-var + worktree-pointer + `.kittify` walk — **the real authority**, 26 callers). `core/project_resolver.py:8` (now **delegates** to paths via deferred import, commit `1a21d6157` #1971; ~6 LOC wrapper). `__init__.py:52` (wrapper → project_resolver → paths: **double-hop**). | `core/paths.locate_project_root` — the only authority. | **PARTLY DONE.** project_resolver already delegates (#1971 landed). Residual: (a) collapse the `__init__.py:52` double-hop to import `paths` directly; (b) redirect the 4 `project_resolver` callers (`cli/helpers.py:19`, `cli/commands/lint.py:25`, `compat/planner.py:779`, `__init__.py:53`) to import `paths` directly, then **delete the `project_resolver.locate_project_root` re-export shim** (≈18 LOC docstring+wrapper + an `__all__` entry). | #1971 | LOW — delegation already proven byte-equal; only import redirects + shim deletion remain. Watch import-cycle (the deferred-import comment documents why). |
| 2a | **`<slug>-<mid8>` mission-dir compose** | `core/mission_creation.py:321` `f"{human_slug}-{mid8(mission_id)}"` (allow-listed). `core/worktree.py:367` same body. | `lanes/branch_naming.mission_dir_name(slug, mid8=…)`. | Replace 2 inline f-strings with seam calls; **remove 2 ratchet allow-list entries** (`test_no_worktree_name_guess.py` `_ALLOWED_SITES`). Byte-identical via shared golden table. | #2000, #1899 | LOW — mechanical; ratchet is the equivalence oracle. |
| 2b | **`.worktrees/<slug>-<mid8>` path compose** | `core/worktree.py:370` `repo_root / WORKTREES_DIR / branch_name` (allow-listed). `orchestrator_api/commands.py:771` (per #1899 prose — verify). | `lanes/branch_naming.worktree_path(...)` / `worktree_dir_name(...)`. | Replace inline join with `worktree_path()`; **remove 1 ratchet allow-list entry**. | #2000, #1899 | LOW. |
| 2c | **Bare `mission_id[:8]` mid8 derivation** (NOT caught by the ratchet's idiom-3, which keys on `endswith(f"-{mid8}")` / `f"{slug}-{mid8}"`) | `cli/commands/implement.py:386`, `cli/commands/agent/workflow.py:292`, `cli/commands/agent/mission.py:772` (`raw_mid[:8]`), `git/sparse_checkout.py:286`, `cli/commands/mission_type.py:643`, `context/mission_resolver.py:163`, `doctrine_synthesizer/apply.py:745,831`, `dashboard/scanner.py:438`, `status/aggregate.py:250`. (`doctor.py:3070/3162` already use `_mid8()` with `[:8]` only as except-fallback — the **correct** pattern.) | `lanes/branch_naming.mid8(mission_id)` (or `resolve_mid8()` when slug-tail cross-check is wanted). The seam comments at `surface_resolver.py:370` and `coordination/status_transition.py:270` already flag "NOT a local `[:8]` slice (#1918)" — proving this idiom recurs and escapes the ratchet. | Route ~10 sites through `mid8()`; **extend ratchet idiom-3 to flag a bare `mission_id[:8]` / `<…>_id[:8]` derivation** outside the seam (close the completeness gap that lets this class regrow). | #2000, #1899 (#1918 lineage) | MEDIUM — must distinguish genuine mid8 derivation from unrelated `[:8]` hash/state truncation (`manifest_store.py:478`, `invocation/executor.py:469`, `drift_detector.py` are NOT mid8). Ratchet rule must be `mission_id`/`mid`-scoped. |
| 3 | **lanes.json *directory* resolution** (which `feature_dir` feeds `require_lanes_json`) | The reader `lanes/persistence.require_lanes_json` is a single authority **parameterized by `feature_dir`** — the split-brain is the *feature_dir each caller hands it*. `implement.py:974` inlines `_lanes_feature_dir` (coord-aware) vs `feature_dir` (meta-anchored). `merge.py:3148`, `orchestrator_api/commands.py:368/430`, `mission_type.py:656`, `context/resolver.py:200`, `workspace/context.py:795` each re-derive their own feature_dir. | A pure `resolve_lanes_dir(repo_root, mission_slug)` seam (issue's proposed signature) living next to `resolve_status_surface_with_anchor` — coord-aware-with-primary-fallback, zero-mock testable. | Extract the 8-line inline block in `implement()`; converges N inline derivations onto 1 helper. **Net LOC roughly flat in `implement` but removes the 12-mock test scaffold** (the design smell — test-scaffolding-as-design-smell tactic). | #1993, #1878 | LOW behaviorally (pure extraction, no behavior change per #1993 scope gate) but **HIGH coupling-visibility**: confirms surface #4 is the real disease. |
| 4 | **Coord-vs-primary *read surface* resolution** (the 3.2.0 split-brain) | THREE topology-aware resolver families, each its own authority: (a) `missions/_read_path_resolver.resolve_mission_read_path` (coord-first→primary; the "one read primitive", 12 sites) re-exported via `feature_dir_resolver.candidate_feature_dir_for_mission` (27 sites); (b) `coordination/surface_resolver.resolve_status_surface[_with_anchor]` (status-emitter surface, 10 sites); (c) `feature_dir_resolver.resolve_feature_dir_for_mission` → `mission_runtime.resolve_action_context` (action-context surface, 25 sites). `implement()`/`finalize`/`accept` chain (a)+(c) by hand and meta-anchor back to primary; status routes through (b). | The **action context** (`mission_runtime.resolve_action_context`) should be the single topology authority; (a) and (b) become *projections* of it (`feature_dir` / `status read_dir` / `lanes_dir`) rather than parallel resolvers. Commands consume the resolved context object, never re-derive. | The inline 3-surface juggling in `implement.py:957-985` (`feature_dir` + `_lanes_feature_dir` + `_status_feature_dir`, ~30 LOC of fallback logic) is **duplicated** in finalize/accept. Consolidating to a `MissionSurfaces` projection deletes the repeated fallback ladders. `_read_path_resolver` + `surface_resolver` carry overlapping `_compose_mission_dir` / `.worktrees`-segment / R2 logic — candidates for merge. | #1878 (umbrella), #1993, #1991 | **HIGH** — this is the load-bearing topology; the 3.2.0 mission itself bled here. Strangle behind the action-context projection incrementally; characterize coord/flat/primary/husk topologies before each move. |
| 4-rider | **`.worktrees`-segment classifier dupe** | `surface_resolver.is_under_worktrees_segment` (line 199, "blessed home" for `".worktrees" in parts`) vs its OWN hand-rolled `any(part == _WORKTREES_SEGMENT for part in feature_dir.parts)` at line 480 (the alphonso Q1 nit). | `is_under_worktrees_segment`. | Replace line-480 hand-roll with the function call. ~3 LOC. | #1899 (rider) | LOW. |
| 4-rider2 | **mid8 in planning-commit worktree** | `cli/commands/agent/mission.py:772` `_planning_commit_worktree` does `raw_mid[:8]` (folds into 2c). | `mid8()`. | 1 line. | #2000 | LOW. |
| 5 | **Ownership path-existence validation** | `ownership/validation.validate_glob_matches` (line ~83) **ALREADY** classifies literal-path-zero-match → hard error (`GlobValidationResult.errors`) with `create_intent` suppression + nearest-match suggestion, and **is already called** by finalize-tasks at `mission.py:3348` and `:3570`. The lane-overlap detector `lanes/compute.py:163-200` does glob-vs-glob overlap only (correctly — overlap is a different concern). | `validate_glob_matches` — already the SSOT. | **NONE — already implemented.** Landed in commit `991162c0a` (`coordination-topology-stabilization-01KTZVQ2`). | #1888 | **N/A — verify-and-close.** Issue describes mission-131 behavior that predates the fix. Add a regression test asserting a literal `owned_files` typo hard-errors, then close #1888. Re-implementing would create a shadow path. |
| — | **#1915 (non-atomic dep-lane merge)** | `lanes/worktree_allocator.py:_merge_dependency_lane_tips` — `git merge --abort` rolls back only the conflicting merge; earlier clean dep-merges survive. | Not a *naming/identity* split-brain — it's a transactional-atomicity bug. | Out of this mission's SSOT envelope. | #1915 | Recommend it stay a **separate** WP or its own mission (snapshot-HEAD + `reset --hard`, or docstring honesty per option (b)). Do not fold into the naming strangler. |

---

## Prioritized consolidation order (strangle in this sequence to avoid shadow paths)

1. **Verify-and-close the already-done (#1888, #1971-partial).** Confirm
   `validate_glob_matches` wiring + add the missing literal-typo regression test
   (#1888 → close). Confirm `project_resolver` delegation, then do the cheap
   `project_resolver`/`__init__` caller redirect + shim deletion (#1971 → close).
   *Doing this first prevents a later WP re-implementing a working authority.*

2. **#2000 mechanical compose routing (2a/2b/4-rider2).** Route the 3 allow-listed
   sites + `_planning_commit_worktree` mid8 through `mission_dir_name()` /
   `worktree_path()` / `mid8()`; shrink the ratchet allow-list. Byte-identical,
   ratchet is the oracle. *Tightens enforcement before adding new code.*

3. **Extend the ratchet to the `mission_id[:8]` class (2c) THEN route the ~10
   sites.** Add idiom-4 (bare mid8 derivation) so the completeness oracle covers
   the class that currently escapes it; routing the sites then runs green and the
   class can never regrow. *Ratchet-first so no new bare-slice sneaks in.*

4. **Extract `resolve_lanes_dir()` pure seam (#1993).** Low-risk pure extraction
   that also *exposes* surface #4's duplication and kills the 12-mock test.

5. **Project the three read surfaces onto the action context (#1878, surface 4 +
   4-rider).** The hard, load-bearing slice — do it LAST, behind characterization
   tests for coord/flat/primary/husk topologies, collapsing the inline
   3-feature_dir juggling in `implement`/`finalize`/`accept` onto one
   `MissionSurfaces` projection. Merge the overlapping `_compose_mission_dir` /
   `.worktrees`-classifier logic across `_read_path_resolver` and
   `surface_resolver`.

6. **Defer #1915** to its own WP/mission (atomicity, not naming).

This ordering strangles **outermost-cheapest-first**: every step tightens an
existing oracle (delegation already proven, ratchet) *before* the next step adds
code, so no consolidation introduces a parallel path that a later step has to
re-strangle.

---

## Biggest split-brain (callout)

**The coord-vs-primary read-surface resolution (surface 4, #1878) is the
load-bearing split-brain — and it is *three* competing authorities, not two.**
`resolve_mission_read_path` (coord-first read primitive), `resolve_status_surface`
(status-emitter surface), and `resolve_feature_dir_for_mission →
resolve_action_context` (action-context surface) each independently decide "where
does this mission live, coord or primary?", and the high-traffic commands
(`implement`/`finalize`/`accept`) hand-juggle all three inline — meta-anchoring to
primary for config, coord-anchoring for lanes.json, status-anchoring for events —
in ~30 lines of fallback ladders **duplicated per command** (`implement.py:957-985`).
This is the exact mechanism that plagued the 3.2.0 mission itself (#1718, #1772, #1991).
The reduction is to make the **action context the one topology authority**
and reduce the read-primitive and status-surface to *projections* of it, so
callers consume a resolved `MissionSurfaces` object and never re-derive coord-vs-
primary. Every other item on this map (#2000 composes, #1993 lanes-dir, the mid8
slices) is a cheap mechanical rider; this one is where the LOC and the recurring
defect class actually live.
