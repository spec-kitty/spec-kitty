# Implementation Plan: rc5 consolidate regressions

**Branch**: `kitty/rc5-consolidate-regressions` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification + grounding memo [research.md](research.md)

## Summary

Four independent fail-closed fixes in the consolidation/coordination subsystem, each closing
one rc5 regression shape with a red-first test through the real entry point:

1. #5569 — correct the approved-authorship claim so content reachable from a fully-canceled
   lane is never attributed to a surviving lane; remove fully-canceled dependency tips from the
   closed-world anchors. Flips residual 7.
2. #5571 — classify the coordination-worktree dirty refusal on `--resume` with the existing
   behind-own-HEAD classifier, refresh in place when the lag is pure, never advise a commit.
3. #5570 — delete the coordination/mission branch with compare-and-delete against the gated tip.
4. #5572 — record strand commit SHAs in the reconcile marker; heal reverts only those, else refuses.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, git CLI (≥ 2.38 already required by the squash axis)
**Storage**: git refs; `.kittify/runtime/merge/<mission_id>/state.json` (ConsolidationState)
**Testing**: pytest (`unit`, `git_repo` markers), real git repos in `tmp_path`, CliRunner for CLI entry points
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single project (`src/specify_cli/`)
**Performance Goals**: no measurable change; one extra `rev-list` per fully-canceled lane, one `update-ref -d`
**Constraints**: C-001..C-004 (fail-closed, hard scope, no attestation, single authority)
**Scale/Scope**: ~4 source modules, ~4 new/changed test modules

## Charter Check

- Single canonical authority: every fix extends an existing seam (reconciliation claim,
  `classify_resume_dirty_remedy`, `repair_coord_strand`, branch-delete helper). PASS.
- ATDD/red-first: each WP opens with a failing test commit through the real entry point. PASS.
- Architectural gate discipline: no new allowlist; `test_single_rollback_authority.py` AST pin
  must stay green (no new restore path). PASS.
- NO_FULL_HEAVY_SUITES_IN_MISSION: targeted modules + named arch gates only. PASS.
- Complexity ≤ 15 / Sonar: helpers extracted with focused tests. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/rc5-consolidate-regressions-01M4189Z/
├── spec.md
├── plan.md
├── research.md
├── tasks.md            (/spec-kitty.tasks)
└── tasks/WP0*.md
```

### Source Code (repository root)

```
src/specify_cli/consolidation/reconciliation.py   # IC-01
src/specify_cli/consolidation/executor.py         # IC-02 (preflight/resume), IC-03 (branch delete), IC-04 (marker writer + heal caller)
src/specify_cli/consolidation/preflight.py        # IC-02 (classifier reuse)
src/specify_cli/coordination/teardown.py          # IC-03 (expected tip plumbing)
src/specify_cli/coordination/coherence.py         # IC-04
src/specify_cli/cli/commands/_coordination_doctor.py  # IC-04 (thread recorded SHAs, refusal finding)
tests/consolidation/test_canceled_content_residuals.py  # IC-01 (residual 7 promoted)
tests/terminus/                                    # entry-point red-first tests per IC
tests/coordination/                                # IC-03 / IC-04 unit tests
```

**Structure Decision**: single project; tests colocated with the existing terminus/
consolidation/coordination suites they extend.

## Implementation Concern Map

### IC-01 — Canceled dependency content in the authorship claim

- **Purpose**: commits reachable from a fully-canceled lane's tip (after its base) are excluded content, never approved authorship of any other lane.
- **Relevant requirements**: FR-001, FR-002
- **Affected surfaces**: `consolidation/reconciliation.py` (`_collect_authored`, `_collect_excluded`, `_closed_world_anchors`, `_mixed_lanes` caller); `tests/consolidation/test_canceled_content_residuals.py`; new `tests/terminus/test_repro_5569.py`.
- **Sequencing/depends-on**: none
- **Brownfield fold (post-plan squad)**: lane-base logic lives in `wp_attribution.py:542-657` (first-claim stamp) and `reconciliation.py:1372-1379` (anchors); extract ONE shared `lane_base_anchor()` used by both — no second authority. Sized ~4–5 functions, ~300 test LOC. Run all five residuals; any XPASS other than residual 7 (notably residual 5 sibling-misattribution `:512`, residual 6 pre-claim `:636`) is a stop-and-escalate signal.
- **Risks**: lane base for a fully-canceled lane must be computed the same way the closed world computes it (first-claim stamp / dependency tips / target tip); a commit that is genuinely authored by an approved WP *and* reachable from a canceled lane (shared ancestor before the canceled lane's base) must not be excluded. Positive control: approved dependency lane. Both strategies through `consolidate`.

### IC-02 — Coordination worktree lag on resume

- **Purpose**: on `--resume`, a coordination worktree that only lags its own HEAD is refreshed in place; any other dirt refuses with advice that never says "commit".
- **Relevant requirements**: FR-003, FR-004
- **Affected surfaces**: `consolidation/executor.py` (`_pre_mutation_safety_preflight` coord guard, `_report_pre_mutation_refusal`, `_recover_behind_head_primary_on_resume` → generalise to a checkout parameter), `consolidation/preflight.py` (`classify_resume_dirty_remedy`, `is_pure_behind_head_lag` base = `pre_mutation_coord_sha`); new `tests/terminus/test_repro_5571.py`.
- **Sequencing/depends-on**: none
- **Brownfield fold**: parametrise `_recover_behind_head_primary_on_resume` and the advice path by checkout + base SHA; no coordination-only twin.
- **Risks**: recovery must stay resume-only and provably pure (#4933 gating rationale). Do not change the ancestry-only "already integrated" skip.

### IC-03 — Compare-and-delete coordination branch at teardown

- **Purpose**: the mission/coordination branch is deleted only if it still points at the gated tip; otherwise teardown refuses non-zero and keeps the branch.
- **Relevant requirements**: FR-005, FR-006
- **Affected surfaces**: `consolidation/executor.py` (`_delete_mission_branch`, `_teardown_coordination_triple`), `coordination/teardown.py` (expected-tip source); `tests/coordination/test_projection_teardown.py` (window test), entry-point test via the teardown path.
- **Sequencing/depends-on**: none (disjoint functions from IC-02/IC-04 in executor.py)
- **Brownfield fold**: no CAS-delete helper exists (`delete_bookkeeping_ref`, `git/ref_advance.py:793-803`, is 2-arg and bookkeeping-only). Add one `delete_branch_ref(ref, expected_sha)` to `git/ref_advance.py` beside `advance_branch_ref`/`restore_branch_ref`. Never restore on mismatch outside `rollback_to_snapshot` (AST pin `tests/consolidation/test_single_rollback_authority.py`).
- **Risks**: non-coordination missions also use `_delete_mission_branch` — expected tip there is the tip read at the same phase; unchanged when nothing moved. Out of scope: `orchestrator_api/commands.py:990` (no gate, pre-existing documented limitation) → follow-up issue.

### IC-04 — Recorded strand commits for the coordination heal

- **Purpose**: the reconcile marker records the strand's own commit SHAs; the heal reverts only those and refuses (no "Healed", non-zero) on foreign status commits or a legacy marker.
- **Relevant requirements**: FR-007, FR-008
- **Affected surfaces**: `consolidation/executor.py` (`_persist_coord_reconcile_marker`, `_heal_pending_coord_reconcile` caller), `coordination/coherence.py` (`repair_coord_strand`, `_recorded_strand_shas`), `cli/commands/_coordination_doctor.py`, `consolidation/state.py` (marker home; also read by `consolidation/rollback.py` and `consolidation/resolve.py`); `tests/terminus/test_repro_4973.py` (real reopen variant) or new `test_repro_5572.py`.
- **Sequencing/depends-on**: none
- **Brownfield fold**: keep `_recorded_strand_shas` as the single reader, preferring persisted SHAs. Sized ~6 functions, ~250 test LOC (kept as one WP per the one-WP-per-issue rule).
- **Risks**: legacy marker refusal must give a manual path; do not add a second revert authority.

## Complexity Tracking

No charter violations.
