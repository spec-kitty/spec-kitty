---
work_package_id: WP01
title: Idempotent worktree metadata reconciliation
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: fix/upgrade-idempotent-worktree-metadata
merge_target_branch: fix/upgrade-idempotent-worktree-metadata
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-idempotent-worktree-metadata. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-idempotent-worktree-metadata unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-idempotent-worktree-metadata-01M38X2Y
base_commit: 1e9a8f48bfd5dfa85b0d66c5ad974377aeeb5bfa
created_at: '2026-09-24T06:03:16.265508+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-09-24T05:57:02Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/upgrade/runner.py
- tests/upgrade/test_worktree_stamp_guard.py
- tests/upgrade/test_upgrade_worktree_commit.py
- tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Idempotent worktree metadata reconciliation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix GitHub issue **#4972**: an idempotent / already-current `spec-kitty upgrade` mints a fresh per-worktree `last_upgraded_at = now_utc()` while advancing `version` on each live worktree, then auto-commits it per branch — so `main`, coord, and lane branches diverge on one bookkeeping line of `.kittify/metadata.yaml` and every in-flight coord mission wedges (`implement` dependency-lane auto-merge conflict; `merge` stale-lane refusal), both exiting 0 "already up to date".

**Done when:**
- A repeat / already-current `upgrade` on a project with live worktrees leaves each worktree's `.kittify/metadata.yaml` **byte-identical to the main checkout's** (shared `last_upgraded_at`, `version=target`) and creates **no** per-worktree "apply spec-kitty upgrade changes" commit.
- After a repeat upgrade, `implement WP##` (dependent WP) and `merge` both exit 0 and `main` receives every approved WP's code.
- A genuine upgrade (migration applied content, or synthesized metadata) still stamps `now_utc()` and auto-commits — **no #2385 regression**.
- The `current_version == target_version` teammate-first-run path is covered.
- `ruff check`, `ruff format --check`, `mypy` clean; touched functions ≤ complexity 15; every new branch/helper has a focused test.

## Context & Constraints

- Spec: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/spec.md`
- Plan: `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/plan.md` (Implementation Concern Map IC-1..IC-7)
- Root-cause tracer (line-verified): `kitty-specs/upgrade-idempotent-worktree-metadata-01M38X2Y/traces/tracer-root-cause.md`
- **Strategy: prevention-only (operator-confirmed).** Do **NOT** touch the consumers `src/specify_cli/lanes/merge.py` or `src/specify_cli/lanes/stale_check.py`.
- **Fix locus:** `_upgrade_worktrees` in `src/specify_cli/upgrade/runner.py` (~374) — the shared mint site. Do NOT fix in the CLI-only `_run_no_migrations_worktree_stamp` wrapper (`cli/commands/upgrade.py:808`); two of the three `_upgrade_worktrees` callers (`runner.py:159`, `:219`) bypass it. The single `last_upgraded_at` mint is `runner.py:~541`; the `version != target` dirty-driver branch is `~:536-538`; the #1838 save-gate is `~:531-542`.
- **Prior-art correction:** extend the **#1838** save-gate, NOT #1872 (which gates migration-record writes and is inert on the no-migrations path).
- **#2385 preservation:** auto-commit is churn-gated (`autocommit.py:388-390`), so an aligned no-op self-cancels — no new special-case for the commit. Keep the genuine-change branches (`runner.py:~503-511` migration content; `~:435` synthesized metadata) stamping `now_utc()` + committing.

## Branch Strategy

- Planning artifacts were generated on `fix/upgrade-idempotent-worktree-metadata`; completed changes merge back into `fix/upgrade-idempotent-worktree-metadata` (then a PR takes it to upstream `main`).
- The execution worktree for this WP is allocated from `lanes.json` by `spec-kitty implement WP01`. Do not hand-construct the worktree path.

## Subtasks

### T001 — Red-first regression pinned to #4972

**Purpose**: Witness the wedge through the real entry points BEFORE any fix.

- New test `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py`, marked `@pytest.mark.regression` with a `# Issue: #4972` pin.
- Reproduce the issue's trigger arm: a coord mission mid-flight (WP01 `in_progress` in `lane-a`, WP02 `planned` depending on WP01, coord worktree materialized), run `upgrade` twice, then drive `implement WP02` + `merge`. Assert (pre-fix) that the branches diverge on `.kittify/metadata.yaml` / the mission wedges. Prefer the lightest fixture that still exercises `_upgrade_worktrees` → autocommit through the real code, mirroring existing patterns in `tests/upgrade/test_upgrade_worktree_commit.py`.
- Run it, confirm it is **RED**, and record the exact command + output in `traces/tracer-red-first.md`.

### T002 — Reconcile at the shared mint site

**Purpose**: Kill the divergence at `_upgrade_worktrees`.

- In `runner.py`, when `worktree_metadata_dirty` is driven **solely** by the `version != target` bookkeeping bump (not by a migration that applied content, nor by synthesized metadata), set `version = target` and set `last_upgraded_at` to the **main checkout's stored value** (the already-loaded target `ProjectMetadata` value — do not mint `now_utc()` at ~:541).
- Extend the existing #1838 save-gate; keep one authority for the timestamp value.
- Keep the change small and within complexity ≤15 — extract a helper (e.g. `_reconcile_worktree_bookkeeping`) if the branch pushes the function over.

### T003 — Preserve #2385 (genuine change still stamps + commits)

- Ensure the migration-applied-content branch (`~:503-511`) and synthesized-metadata branch (`~:435`) still stamp `now_utc()` and auto-commit.
- Add/extend a focused unit test (in `tests/upgrade/test_upgrade_worktree_commit.py` or `test_worktree_stamp_guard.py`) proving a genuine worktree change still produces the stamp + commit (no dirty-worktree-blocks-merge regression).

### T004 — Cover the `current_version == target_version` teammate first-run

- Add a focused unit test asserting that when `current_version == target_version` (the `upgrade.py:822` gate is true), the worktree metadata ends byte-identical to the main checkout — the same behavior as the operator's second run.

### T005 — Caller coverage + gates green

- Verify by reading the code that the fix at `_upgrade_worktrees` covers callers `runner.py:159`, `:219`, `:260`.
- Post-fix: re-run the T001 regression → confirm **GREEN**; record command + output in `traces/tracer-red-first.md`. Decide the regression test's final home (keep as focused unit test near the stamp, or a functional home) — do not leave a transitional repro marked `regression` if it belongs as a unit test.
- Run the blast radius (record commands + counts in `traces/tracer-blast-radius.md` and the PR): `make test-fast`, `PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/ -q`, plus `tests/e2e/test_upgrade_post_state.py` and `tests/specify_cli/cli/commands/test_upgrade_command.py`. Run `ruff check .` (touched files), `uv run --frozen ruff format --check` (touched files) and `mypy` on the touched module.

## Test Strategy

Red-first per ADR 2026-07-17-1: T001 lands RED through the pre-existing entry point before the fix (T002). New branches/helpers get focused unit tests in the same change (Sonar new-code gate).

## Definition of Done

- All five subtasks complete; T001 GREEN post-fix.
- Consumers untouched; fix confined to `src/specify_cli/upgrade/runner.py` + `tests/upgrade/`.
- Gates green (ruff / format / mypy / complexity); blast-radius counts recorded.
- Tracers (`tracer-red-first.md`, `tracer-blast-radius.md`) filled with real commands + output.

## Risks & Reviewer Guidance

- **Reviewer**: confirm the reconcile branch fires ONLY when the version bump is the sole dirty driver (no #2385 regression), that the shared timestamp comes from the main checkout (not a fresh `now_utc()`), and that no consumer file was modified. Verify the fix sits in `_upgrade_worktrees`, not the CLI wrapper, so all three callers inherit it.
