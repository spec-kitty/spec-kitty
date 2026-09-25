# Phase 0 Research: Advancing next — task-board authority unification

## Parallel-authority inventory (the divergence to collapse)

Enumerated so NFR-002 ("single board authority at the shared seam") is reviewable against a concrete list. Line numbers are on `main` HEAD `42adce940e` and are indicative (the file moves); the symbol is authoritative.

| # | Authority | Location | Role | Coord-aware? | Regression path? |
|---|-----------|----------|------|--------------|------------------|
| 1 | `_finalized_task_board_override_step` | `src/runtime/next/runtime_bridge.py:662` | Board → step-name map (planned/claimed/in_progress→`implement`; for_review→`review`; in_review→`blocked:review_in_progress`; all-acceptable→`accept`/`done`; else `blocked:no_actionable_wp`) | **Yes** (takes `status_dir`) | Yes (planned→implement) |
| 2 | `_state_to_action` | `src/runtime/next/decision.py:394` | Advancing step → (action, wp, workspace); implement branch dependency-aware via `preview_claimable_wp(feature_dir)` **without `status_dir`**; review branch only looks for a `for_review` WP then falls through to a WP-less `("review", None, …)` | **No** (`feature_dir` only) | No (cannot go review→implement) |
| 3 | `_should_advance_wp_step` + `_wp_blocks_step` | `src/runtime/next/runtime_bridge.py:745`, `:826` | Advancing stay-vs-leave boolean for the issued step | Partially (anchors `tasks/` via placement seam at `:794`, but `committed_authority.wp_ending(feature_dir, wp_id)` reads `feature_dir`) | n/a (boolean only) |
| 4 | `preview_claimable_wp` | `src/runtime/next/discovery.py` | Canonical dependency-aware claimable-WP resolver; takes `status_dir` | **Yes** | n/a |

**Sole caller of #1** is query mode (`runtime_bridge.py:2776`). Every advancing path (`_build_wp_iteration_decision:2937`, `_map_wp_step_decision:3047`, plus `_map_non_wp_step_decision:3118` for non-WP steps) routes through #2. That asymmetry IS the bug.

## Decision 1 — Route advancing WP-iteration action selection through the query authority (#1 + #4)

- **Decision**: both advancing WP-iteration builders consult `_finalized_task_board_override_step` (coord-aware `status_dir`) for the step, then `preview_claimable_wp(..., status_dir=<coord-aware>)` for the WP, mirroring query mode's `_build_finalized_override_query_decision`. `_state_to_action`'s WP-iteration step→action logic delegates to / is retired into this path.
- **Rationale**: query mode already computes the correct answer for both faces (planned→implement; coord-aware read sees lane rows). Unifying on it — rather than patching the review branch and threading `status_dir` separately — is the single-canonical-authority move and forecloses the #4860 branch-by-branch recurrence (the combined coord×review cell, US3, is only green if the authority is shared).
- **Alternatives considered**:
  - *Patch `_state_to_action`'s review branch to map planned→implement + add `status_dir`*: rejected — leaves two divergent authorities (#2 vs #1), reintroduces the whack-a-field the alignment lens named (a naive planned→implement inside `_state_to_action("review")` conflates review-step with implement-action across all five `_state_to_action` call sites), and does not by construction cover the combined cell.
  - *Emit `blocked`+recovery only (never re-dispatch)*: rejected by the operator (Decision Moment 01M3BGRBWBDWG3F3EEA4Z5S8VQ) — leaves the autonomous loop unable to self-heal. Kept as the floor for the genuinely-no-actionable-WP case.

## Decision 2 — `blocked:*` sentinels become `kind=blocked` + named recovery, never the composed placeholder

- **Decision**: when the board authority returns a `blocked:*` sentinel, the advancing builder emits `kind=blocked` (exit 1) with a concrete recovery command in the reason/payload; a WP-less action never reaches `_build_prompt_or_error`'s composed-marker path.
- **Rationale**: FR-004/FR-005 — the composed placeholder (`decision.py:553-572/:601-610`) is only reachable because `_state_to_action("review")` returns a *non-None* WP-less action, so the existing `action is None → blocked` branch (`:2945`/`:3054`) is skipped. Routing the WP-less case to `blocked` closes the exit-0-forever no-op.
- **Recovery command shape**: the payload names a runnable `spec-kitty` invocation appropriate to the sentinel (e.g. for `review_in_progress`, guidance that another reviewer holds the WP; for `no_actionable_wp`, the dependency/claim state to inspect). Exact string pinned in the contract and asserted in tests.

## Decision 3 — Coord-read stays fail-closed (ADR 2026-09-24-2)

- **Decision**: the coord-aware status read used by the advancing path raises `CoordinationWorktreeUnmaterialized` / `CoordinationBranchDeleted` on an unmaterialized/deleted coordination surface, surfaced as a blocked reason that names the unmaterialized surface — NOT collapsed into the generic `no_actionable_wp` floor (an empty-primary substitution that fabricates "no WP" is exactly the #4975 defect class).
- **Rationale**: NFR-003; consistency with the just-landed coord-read-fail-closed seam (`mission_runtime.resolution._classify_artifact_surface`). Query mode already resolves the coord surface through the placement seam; the advancing path must use the same resolution, inheriting the fail-closed behavior.

## Decision 4 — Decision-layer-only; no engine-state write (NFR-001)

- **Decision**: the selector reads the board and returns an envelope; it performs no run/engine-state write and no DAG regression. The `not should_advance` stay-in-step path already avoids `next_step()`; the issued step marker is unchanged.
- **Rationale**: the alignment lens confirmed the DAG is forward-only and there is no legitimate review→implement engine regression; the action is meant to be recomputed from the board each call (which is exactly what query mode does). Verified by a snapshot-byte-identical-before/after assertion.

## Decision 5 — Test seam and red-first strategy (C-001, C-002)

- **Decision**: drive the red-first repros through the public `decide_next_via_runtime` (advance) and `query_current_state` (query) functions in `tests/runtime/test_bridge_parity.py`; pin lane-fixture mapping cases in `tests/next/test_finalized_task_routing.py`. Assert both an absolute anchor (`action=implement wp_id=WP01`) and advance==query parity for every matrix cell, including the combined coord×review cell (US3).
- **Rationale**: the defect is only observable at the composed decision — a private-helper test (`_state_to_action`) would miss the placeholder-swallow at `_build_prompt_or_error`. The public seam is the same one `test_bridge_parity.py` already exercises (`advance_to_step`, `drive_decide_next`, `drive_query` helpers exist).

## Supply-chain security (advisory, plan)

**N/A** — this mission adds, upgrades, and removes **zero** dependencies (internal `src/runtime/next/` change only). No registry authenticity / lifecycle-script / LTS analysis applies. Recorded here so the plan's supply-chain posture is explicit, not silent.

## Adversarial evidence (plan)

The post-spec adversarial squad (analyst-annie + reviewer-renata, opus) ran against the spec; both BLOCKERs and all SHOULDs were folded into the spec revision (`e7c48b7`) — see `checklists/requirements.md` Notes. No contested finding was dropped:
- combined coord×review cell → **accepted** (US3 added).
- multi-WP dependency-order scenario → **accepted** (US1 S5).
- NFR-001/002/003 claim-vs-assertion tightening → **accepted**.
- parallel-authority inventory enumeration → **accepted** (this document + spec Key Entities).
- `lanes_with_coord` / early-reject / dependency-walled / unmaterialized-coord arms → **accepted**.
