# Tasks: Upgrade idempotency — no divergent per-worktree metadata stamps

**Mission**: `upgrade-idempotent-worktree-metadata-01M38X2Y` | **Issue**: #4972
**Branch**: `fix/upgrade-idempotent-worktree-metadata` → PR to upstream `main`

One cohesive work package: the fix and its tests are a single change to `src/specify_cli/upgrade/runner.py` plus co-located `tests/upgrade/` coverage. Splitting would create an artificial dependency on a half-written `runner.py`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first `@pytest.mark.regression` test pinned to #4972 through real `upgrade` x2 → `implement`/`merge` (RED before fix) | WP01 | |
| T002 | Reconcile at the shared mint site `_upgrade_worktrees`: version-only no-op writes `version=target` + main-checkout's shared `last_upgraded_at`, not `now_utc()` | WP01 | |
| T003 | Preserve #2385: genuine change (migration content / synthesized metadata) still stamps `now_utc()` + auto-commits — focused unit test | WP01 | |
| T004 | Cover the `current_version==target_version` teammate-first-run entry (focused unit test asserting aligned bytes) | WP01 | |
| T005 | Verify all three `_upgrade_worktrees` callers (`:159`/`:219`/`:260`) inherit the fix; run blast-radius tests + `ruff`/`mypy`/format clean | WP01 | |

## Work Package WP01: Idempotent worktree metadata reconciliation

**Goal**: An idempotent / already-current `spec-kitty upgrade` reconciles live-worktree `.kittify/metadata.yaml` to the main checkout's shared value instead of minting a fresh divergent per-worktree `last_upgraded_at`, so in-flight coord missions stay drivable — while genuine upgrades still stamp and commit.

**Priority**: P1 (MVP — the whole mission)

**Independent Test**: The #4972 repro trigger arm (`UPGRADES=2`) drives a coord mission mid-flight, `upgrade` twice, then `implement WP02` + `merge`; both exit 0 and `main` receives both WPs' code (matching the single-upgrade control). RED before the fix, GREEN after.

**Dependencies**: none

**Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, NFR-004

**Included subtasks**: T001, T002, T003, T004, T005

**Implementation sketch**:
1. T001 — Author the red-first regression first; witness it RED at the pre-fix entry point and record the command + output in `traces/tracer-red-first.md`.
2. T002 — In `_upgrade_worktrees` (`runner.py`), when `worktree_metadata_dirty` is driven solely by the `version != target` bookkeeping bump, set `version=target` and `last_upgraded_at` to the main checkout's stored value (loaded once via `ProjectMetadata`), instead of `now_utc()` at ~:541. Extend the #1838 save-gate (~:531-542); do not add a second authority.
3. T003 — Ensure the genuine-change branches (migration applied content ~:503-511; synthesized metadata ~:435) still stamp `now_utc()` and auto-commit; add a focused unit test proving no #2385 regression.
4. T004 — Add a focused test for the `current_version==target_version` path (upgrade.py:822 gate true) asserting byte-identical worktree metadata.
5. T005 — Confirm the fix at the shared site covers callers `:159`/`:219`/`:260`; run the blast-radius suite and `ruff`/`ruff format --check`/`mypy`.

**Risks**:
- Over-broad suppression could reintroduce #2385 (dirty worktree blocks merge) — mitigated by gating strictly on "version-bump is the sole driver".
- Reading the main checkout's stored timestamp must handle a project whose main `.kittify/metadata.yaml` is itself mid-write; use the already-loaded target `ProjectMetadata` rather than a second disk read where possible.

**Estimated prompt size**: ~300 lines.

## MVP

WP01 is the entire mission.
