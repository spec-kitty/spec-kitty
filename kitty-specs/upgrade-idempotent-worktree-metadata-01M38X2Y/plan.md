# Implementation Plan: Upgrade idempotency — no divergent per-worktree metadata stamps

**Branch**: `fix/upgrade-idempotent-worktree-metadata` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/spec.md` (fixes GitHub issue #4972)

## Summary

An idempotent / already-current `spec-kitty upgrade` mints a fresh per-worktree `last_upgraded_at = now_utc()` while advancing `version` on each live worktree, then auto-commits it per branch — so `main`, coord, and lane branches diverge on one bookkeeping line of `.kittify/metadata.yaml` and every in-flight coord mission wedges (`implement` dependency-lane auto-merge conflict; `merge` stale-lane refusal), both exiting 0. The prevention-only fix (operator-confirmed, DM `01M38X487WENDRSAEY24BN841K`) reconciles the worktree bookkeeping to the **main checkout's shared stored value** when the version bump is the sole driver, at the single mint site `_upgrade_worktrees` (`src/specify_cli/upgrade/runner.py`), so all three callers inherit it and the file is byte-identical across branches. Consumers (`lanes/merge.py`, `lanes/stale_check.py`) are intentionally unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Standard project stack (`typer`, `rich`, `ruamel.yaml`); no new dependency added or upgraded — **supply-chain security section N/A** (no dependency change).
**Storage**: `.kittify/metadata.yaml` (generated per-checkout `ProjectMetadata`; `version`, `last_upgraded_at`, `schema_version`)
**Testing**: pytest — `tests/upgrade/` (unit) + real `upgrade`→`implement`/`merge` regression for the wedge
**Target Platform**: Linux/macOS dev + CI
**Project Type**: single (CLI top-adapter layer, `src/specify_cli/`)
**Performance Goals**: N/A (correctness fix; no hot path)
**Constraints**: Prevention-only (consumers untouched); preserve #2385 auto-commit for genuine change; extend the #1838 save-gate rather than add a second authority; `ruff`/`mypy`/format clean; complexity ≤15; new-code coverage for every new branch.
**Scale/Scope**: One mint site + its no-op condition; one regression test + focused unit coverage. Small, self-contained.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (DIRECTIVE_044):** ✅ The fix extends the existing #1838 version/timestamp save-gate at `runner.py:531-542` and reuses the main checkout's already-loaded `ProjectMetadata.last_upgraded_at`; it does not add a parallel timestamp authority. Placed at the single mint site so all three `_upgrade_worktrees` callers share one behavior.
- **Architectural alignment (DIRECTIVE_001):** ✅ Change is confined to the `src/specify_cli/upgrade/` adapter layer; no module-seam or shared-package-boundary change.
- **ATDD-first / red-first (ADR 2026-07-17-1):** ✅ A `@pytest.mark.regression` test pinned to #4972 reproduces the wedge through the real entry points and is RED before the fix.
- **Tiered rigour:** ✅ Bookkeeping-reconciliation logic (the no-op-driver detection + shared-value write) gets focused unit tests; the end-to-end wedge gets one regression test.
- **Terminology:** ✅ No user-facing term changes; "Mission" canon unaffected.
- **Not a bulk edit:** ✅ `meta.json` has no `change_mode: bulk_edit`; the fix changes one string-write site, not the same identifier across many files. No `occurrence_map.yaml` needed.

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (behavioral contract for the reconcile rule)
├── traces/              # tracer files (root-cause, red-first, blast-radius)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── runner.py            # FIX LOCUS: _upgrade_worktrees (~374), the version!=target branch (~536-538),
│                        #            the last_upgraded_at mint (~541), save (~542). Callers: ~159, ~219, ~260.
│                        #            #1838 save-gate ~531-542; #1872 record-gate ~474-486 (NOT this path).
├── autocommit.py        # commit_touched_checkout churn-gate (~388-390) — relied on, not changed.
└── (metadata via) src/kernel/... ProjectMetadata.load / save

src/specify_cli/cli/commands/upgrade.py
                         # _run_no_migrations_worktree_stamp (~808), current_version==target gate (~822).
                         # NOT the fix locus (wrapper; two callers bypass it) — verified during implement.

tests/upgrade/
├── test_worktree_stamp_guard.py        # extend: aligned-value / no-divergence unit assertions
├── test_upgrade_worktree_commit.py     # extend: no per-worktree commit on version-only no-op
├── test_upgrade_auto_commit_unit.py    # churn-gate self-cancel coverage
├── test_commit_decision.py             # commit-decision coverage
└── test_issue_4972_*.py (new)          # red-first regression through upgrade->implement/merge
```

**Structure Decision**: Single-project CLI layout. The entire change lives in `src/specify_cli/upgrade/runner.py` (the shared mint site) plus tests under `tests/upgrade/`. No consumer (`src/specify_cli/lanes/`) is touched — prevention-only per C-001.

## Implementation Concern Map

| # | Concern | Surface | FR/NFR | Notes |
|---|---------|---------|--------|-------|
| IC-1 | Detect the version-only bookkeeping no-op driver | `runner.py` `_upgrade_worktrees` ~531-542 | FR-002, FR-005, C-002 | Distinguish "dirty solely because `version != target`" from "dirty because a migration applied content / metadata synthesized". Only the former takes the aligned write. |
| IC-2 | Write the shared (main-checkout) `last_upgraded_at` instead of `now_utc()` | `runner.py` ~541 | FR-001, C-002 | Read the main checkout's stored value (`ProjectMetadata.load` on the primary `.kittify`); set `version=target` + that shared timestamp so bytes match across branches. |
| IC-3 | Ensure no divergent per-worktree commit is created | `runner.py` ~561 → `autocommit.py` ~388-390 | FR-002 | Rely on the existing churn-gate: an aligned no-op yields an empty baseline delta → no commit. No new special-case. |
| IC-4 | All three callers inherit the fix | `runner.py` ~159, ~219, ~260 | FR-003 | Fix at `_upgrade_worktrees`, not the CLI wrapper. Verify `:159`/`:219` paths in implement. |
| IC-5 | Preserve #2385 for genuine change | `runner.py` ~435, ~503-511 | FR-005, C-002 | Migration-applied content / synthesized metadata still stamp `now_utc()` + auto-commit. Guard with an explicit test. |
| IC-6 | Red-first regression through real entry points | `tests/upgrade/` | NFR-001 | Coord mission mid-flight, `upgrade` x2, then `implement WP02` + `merge`; RED before fix, GREEN after. Pin `# Issue: #4972`. |
| IC-7 | Cover the `current_version==target` teammate first-run | `tests/upgrade/` | FR-004 | Same code path (upgrade.py:822 gate true); focused test asserting aligned bytes. |

## Parallel Work Analysis

Single-stream, small fix — no parallelism needed. Natural ordering:

### Dependency Graph
```
WP01 (red-first regression + fix at the shared mint site + focused unit coverage) → done
```
The regression test (red-first), the reconcile-rule implementation, and the #2385-preservation + teammate-first-run unit tests are one cohesive change to one file (`runner.py`) plus its co-located tests. Splitting would create an artificial dependency on a half-written `runner.py`. Plan for **one work package**; `/spec-kitty.tasks` will confirm slicing.

### Work Distribution
- **Sequential work**: red-first repro must be RED before the fix lands in the same WP.
- **Parallel streams**: none.
- **Agent assignments**: single implementer (sonnet) + reviewer (opus).

### Coordination Points
- Verify the fix at `_upgrade_worktrees` covers callers `:159` and `:219` (not just the CLI path) before review.
