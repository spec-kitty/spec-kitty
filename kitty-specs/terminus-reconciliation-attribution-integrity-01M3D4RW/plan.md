# Implementation Plan: Terminus Reconciliation Attribution Integrity

**Branch**: `fix/terminus-reconciliation-attribution-integrity` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Epic #5001 reconciliation-gate follow-ups #5022, #5018, #5021, #5038

## Summary

Fix four defects in the `spec-kitty merge` pre-teardown reconciliation gate so it attributes work at the correct granularity — never shipping a canceled WP's deletion under squash (#5022), never blocking a legitimate mixed approved+canceled write-scope lane (#5018), never false-failing a completed squash on resume (#5021 r1), and never false-refusing a clean single-lane squash's bookkeeping projection (#5038). The 3-way merge-resolution content case (#5021 r2) stays an honest `xfail(strict)`. All edits are confined to `src/specify_cli/merge/` and its tests. The technical approach is grounded by two opus lenses (alignment + scope), which confirmed all four are LIVE on HEAD and mapped the exact seams.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git (subprocess), the existing `merge/git_probes.py` probe layer (`changed_paths_in_range`, `blob_id_at`, `patch_id_of`, `first_parent_commits_in_range`) — no new third-party dependency
**Storage**: git repository state (lane branches, coord worktree, `.kittify/merge-state.json`); no database
**Testing**: pytest — real-CLI red-first repros in `tests/terminus/` (via `conftest.py`'s `build_coord_mission`/`run_terminus`, no `_run_git`/subprocess mocking) + unit/property tests in `tests/merge/`
**Target Platform**: Linux/macOS/Windows CLI (cross-platform git)
**Project Type**: single (CLI library)
**Performance Goals**: merge stays within the CLI < 2s typical-project budget; new attribution work is bounded by the squash/merge window (no O(repo history) scans)
**Constraints**: fail-closed in the data-loss direction preserved; fixes correct attribution granularity, never gate strictness (C-001); `mypy --strict`, `ruff`, `ruff format` clean with no new suppressions; complexity ≤ 15
**Scale/Scope**: ~3 source files (`reconciliation.py`, `executor.py`, `bookkeeping_projection.py`), 4 new red-first repros + focused unit tests

## Constitution Check (Charter)

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first (C-011)**: PASS by construction — each WP lands an issue-pinned `@pytest.mark.regression` real-CLI repro RED through `spec-kitty merge` before the fix, GREEN after. Committed as the lane's first commit.
- **Red-main / honest-red (Standing Order #9, ADR 2026-07-17-1)**: PASS — #5021 r2 stays `xfail(strict)`; no green-washing. WP1 must not un-strict the 3-way xfail.
- **Tiered rigour (core domain)**: PASS — this is core merge-integrity; implement=sonnet, review=opus, adversarial data-loss lens pre-merge.
- **Single canonical authority**: PASS — extends the existing `ApprovedWpCommitSet` authorship model (adds `authored_deletions`), does not add a second attribution authority.
- **Locality of change / smallest-viable-diff**: PASS — edits confined to `merge/`; no `lanes/` edits (parallel-safety with Epic #4883 / #4857).
- **Terminology canon**: N/A to code paths here (no Mission/Feature user-facing surface added).
- **No new dependency**: PASS — supply-chain section N/A.

## Project Structure

### Documentation (this mission)

```
kitty-specs/terminus-reconciliation-attribution-integrity-01M3D4RW/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + adversarial evidence
├── data-model.md        # Phase 1 — ApprovedWpCommitSet + authored_deletions
├── contracts/
│   └── reconciliation-gate-contract.md   # gate PASS/FAIL/REFUSE behavior contract
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/merge/
├── reconciliation.py        # WP1 (deletion attribution), WP2 (commit-level exclusion)
├── executor.py              # WP3 (resume tolerance), WP4 (projection proof precision)
└── bookkeeping_projection.py# WP4 (projected_content_matches_target precision)

tests/
├── terminus/
│   ├── conftest.py                 # existing real-CLI harness (reused)
│   ├── test_repro_5022.py          # WP1 red-first
│   ├── test_repro_5018.py          # WP2 red-first
│   ├── test_repro_5021.py          # WP3 red-first (residual 1)
│   └── test_repro_5038.py          # WP4 red-first
└── merge/
    └── test_reconciliation.py      # unit/property + the kept 3-way xfail(strict)
```

**Structure Decision**: Single CLI library. All production edits live under `src/specify_cli/merge/`; tests split between the real-CLI `tests/terminus/` repros (per-facet, issue-pinned) and the unit/property `tests/merge/test_reconciliation.py`.

## Complexity Tracking

No Constitution violations. The one structural risk is #5018's ordering constraint: `_collect_excluded` currently runs before `_collect_authored` in `build_approved_wp_set`, so WP2 must thread the authored SHA/patch-id sets into `_collect_excluded` (keeping each collector pure) rather than reorder-and-share mutable state.

## Parallel Work Analysis

### Dependency Graph

```
WP1 (#5022 deletion attribution — adds authored_deletions + _final_authored_deletions,
     threads _collect_authored → build_approved_wp_set)
   │  (WP2 reuses WP1's authorship-threading refactor of build_approved_wp_set)
   ▼
WP2 (#5018 commit-level exclusion — subtracts authored SHAs/patch-ids in _collect_excluded)

WP3 (#5021 r1 resume tolerance — executor.py resume/teardown path)      ─┐ independent of
WP4 (#5038 projection proof precision — executor.py + bookkeeping_projection.py) ─┘ WP1/WP2 attribution axes
```

- **Sequential**: WP1 → WP2 (shared `build_approved_wp_set` / `_collect_authored` seam; WP2 depends on WP1's threading).
- **Parallel-capable**: WP3 and WP4 are independent of the WP1/WP2 attribution axes (they touch the executor resume/teardown + projection proof), but both edit `executor.py`, so they SERIALIZE against each other and against WP2 on that file to avoid churn conflicts.
- **File ownership**: WP1/WP2 → `reconciliation.py`; WP3 → `executor.py` (resume/teardown); WP4 → `executor.py` (`_assert_squash_projected_content_landed`) + `bookkeeping_projection.py`.

### Coordination Points

Because WP2, WP3, WP4 all touch `executor.py`/`reconciliation.py`, execution is effectively **serial (WP1→WP2→WP3→WP4)** to keep lanes conflict-free — this is a small, tightly-coupled core-integrity mission, not a wide fan-out. Lanes collapse by write-scope; the finalize step computes the actual lane layout.

### Integration verification

After all WPs: run `tests/terminus/` + `tests/merge/` in full; confirm the four repros GREEN and the 3-way `xfail(strict)` still xfailing; run an adversarial data-loss pass over the integrated diff (pre-PR squad §6).
