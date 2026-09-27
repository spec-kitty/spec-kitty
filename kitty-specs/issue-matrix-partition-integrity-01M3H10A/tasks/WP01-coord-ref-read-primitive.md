---
work_package_id: WP01
title: 'Coordination-ref content read primitive (IC-01a) — #5171/#4943'
dependencies: []
requirement_refs:
- FR-005
- FR-007
- NFR-002
- NFR-003
planning_base_branch: claude/spec-kitty-ci-failures-r0xui3
merge_target_branch: claude/spec-kitty-ci-failures-r0xui3
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-ci-failures-r0xui3. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-ci-failures-r0xui3 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history:
- Created by /spec-kitty.tasks 2026-09-27
agent_profile: implementer-ivan
authoritative_surface: src/mission_runtime/resolution.py
create_intent:
- tests/mission_runtime/test_issue_matrix_ref_read.py
execution_mode: code_change
owned_files:
- src/mission_runtime/resolution.py
- tests/mission_runtime/test_issue_matrix_ref_read.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load implementer-ivan
```

Apply the resolved initialization, boundaries, directives, and tactics. State which you applied, then continue.

## Objective

Add a NEW read authority in `src/mission_runtime/resolution.py` that returns ISSUE_MATRIX **content**
(text/bytes) read from a git ref (`git show <ref>:<path>`) when the artifact has no on-disk worktree.
Crucially, it resolves the ref via the **same lifecycle-phase authority the write path uses**
(`resolve_lifecycle_phase` → `resolve_placement_only`), so a read can never diverge from where the
verdict was written. It fails closed on ambiguity and does not regress the deliberate #4959 raise.

Read `../plan.md` (IC-01a + the MAJOR-3 resolution box), `../research.md` (D2/D4), `../data-model.md`
(LifecyclePhase authority + fail-closed), and `../contracts/issue-matrix-read.md`.

## Context (confirmed live code)

- `resolve_lifecycle_phase` (`src/mission_runtime/lifecycle_phase.py:220-273`) derives phase from
  durable signals: baseline absent → PRE_CONSOLIDATION; baseline + Target Ref (`meta.target_branch`)
  present → CONSOLIDATED; baseline + Target Ref deleted + completion evidence → PUBLISHED.
- `resolve_placement_only` (`resolution.py:1640-1674`): PUBLISHED + kind∈`_E2_CONSOLIDATED_ELIGIBLE_KINDS`
  (`:154-162`, includes ISSUE_MATRIX) → `_resolve_consolidated_e2_target` (consolidated PRIMARY ref,
  `:171-208`); otherwise coord topology → `destination_ref` = coordination branch (`:1442-1443,1674`).
- `_classify_artifact_surface` (`resolution.py:1966-1983`) RAISES `CoordinationWorktreeUnmaterialized`
  on `CoordState.UNMATERIALIZED` for **all** coord kinds (deliberate #4959 fix). `CoordinationWorktreeUnmaterialized`
  subclasses `StatusReadPathNotFound`, so `coord_read_dir_for` (`:2195`) silently absorbs it to `None` →
  caller falls back to `feature_dir` → PRIMARY residue. **That absorb-to-residue is the live #5171 bug** —
  do NOT try to make `_classify` / `coord_read_dir_for` return content (their `Path | None` contract cannot
  carry it, and changing it re-introduces the residue path). The new read is **standalone** (see T002).
- **In-layer git plumbing to reuse (MINOR-1, keeps the ledger clean)**: `src/mission_runtime/lifecycle_phase.py`
  already ships `_rev_is_valid` (`:276`, `git rev-parse --verify --quiet` — the deleted-ref leg),
  `_path_present_at_rev` / `_git_object_present` (`:291`/`:320`, `git cat-file -e <rev>:<path>` —
  existence-on-ref, squash-robust, distinguishes absent-vs-broken), a shared `_GIT_PROBE_TIMEOUT`, and the
  typed `LifecyclePhaseProbeError`. The FR-007 fail-closed legs map 1:1 onto these. The only net-new
  plumbing is a `git show <rev>:<path>` content read alongside them.

## ⚠ Layer-rule constraint (do not trip the ledger)

`src/mission_runtime/` must NOT import `specify_cli.*` (shrink-only ledger
`tests/architectural/test_layer_rules.py::TestMissionRuntimeBoundary`). Reuse the in-layer
`lifecycle_phase.py` git helpers above; do NOT reach into `specify_cli` (e.g. `coord_branch_has_committed_artifact`
lives in `specify_cli.coordination.surface_resolver` — out of layer, do not import it).

## Subtasks

### T001 — Failing-first test (RED before T002-T004)
Create `tests/mission_runtime/test_issue_matrix_ref_read.py`. Build fixtures with a real git repo:
- **Post-consolidation CONSOLIDATED (the #5171 case)**: baseline present, Target Ref present, coord
  branch retained, worktree removed; write `#11 -> fixed` on the coord branch. Assert the new read
  returns `fixed` content from the coord branch ref. Positive/negative pair: coord `in-mission` returns
  `in-mission` (probe can see the value), coord `fixed` returns `fixed`.
- **PUBLISHED case**: Target Ref deleted + completion evidence; verdict on consolidated primary. Assert
  the read resolves the consolidated-primary ref (not the coord branch).
- **Fail-closed legs (T004)**: deleted ref → refuse; probe error → refuse; empty authored set with live
  references → refuse. Each paired with a same-fixture positive control (ref present + non-empty →
  resolves). 
- **#4959 non-regression (T003)**: an UNMATERIALIZED read of a NON-issue-matrix coord kind
  (TRACER_FILE / REVIEW_CYCLE / ACCEPTANCE_MATRIX / STATUS_STATE) still raises
  `CoordinationWorktreeUnmaterialized`.
Confirm the whole file is RED on the mission base.

### T002 — Standalone ref-content read authority (MAJOR-2)
Add a NEW **standalone** function in `resolution.py` (a sibling to `resolve_placement_only`, NOT an edit
to `_classify_artifact_surface` and NOT a change to `coord_read_dir_for`/`resolve_artifact_surface` `Path`
semantics). It resolves the ref via the same phase authority the write uses (call `resolve_lifecycle_phase`
/ reuse `resolve_placement_only`'s ref selection: PUBLISHED → consolidated-primary; CONSOLIDATED/PRE_CONSOLIDATION
coord → coordination branch), then reads content via `git show <ref>:<path>`. Returns **content** (or a
typed refusal), never a `Path`. The WP02 helper calls this directly for ISSUE_MATRIX post-consolidation.
Keep ≤ complexity 15 by extracting FOUR helpers (named for review): (i) ref resolution off the phase
authority, (ii) existence probe (`_rev_is_valid`), (iii) content probe (`git show`), (iv) empty-authored-set
check. Hoist repeated `git` arg / diagnostic literals to module constants (S1192, MINOR-2).

### T003 — #4959 non-regression (NOT a `_classify` content change)
Do **not** make `_classify_artifact_surface` return content or stop raising for ISSUE_MATRIX — the new
standalone read (T002), dispatched by the WP02 helper, is the ISSUE_MATRIX post-consolidation path, so
`_classify` keeps raising `CoordinationWorktreeUnmaterialized` unchanged for **all** coord kinds. T003 is a
guarding test that (a) the raise still fires for the other coord kinds (TRACER_FILE / REVIEW_CYCLE /
ACCEPTANCE_MATRIX / STATUS_STATE), and (b) the ISSUE_MATRIX post-consolidation read is actually served by
the standalone T002 path (so the carve-out is not vacuous). If any tiny `_classify`/dispatch change proves
necessary, it must be behavior-preserving for the other kinds and covered by (a).

### T004 — Fail-closed legs
Existence via `git rev-parse --verify` (resolved ref). Ref absent → refuse (typed). Content probe error →
refuse on a distinct path (do not swallow into "deleted"). Empty authored set while gating references
exist → refuse (never "nothing to enforce"). Each leg proven with its same-fixture positive control.

## Definition of Done
- T001 RED on base, GREEN on final. All fail-closed legs paired with positive controls.
- Read resolves via the phase authority (verified by the PUBLISHED vs CONSOLIDATED test arms).
- #4959 non-regression test passes (other coord kinds still raise).
- `ruff check .` + `ruff format --check .` clean; mypy clean; no `specify_cli` import added to mission_runtime.
- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest tests/mission_runtime -q`.

## Reviewer guidance
Verify the read drives off `resolve_lifecycle_phase` (grep the diff) — a hardcoded coord/primary ref is a
divergence bug. Verify the #4959 raise still fires for non-issue-matrix kinds. Confirm no `Path`-semantics
change to `coord_read_dir_for`.
