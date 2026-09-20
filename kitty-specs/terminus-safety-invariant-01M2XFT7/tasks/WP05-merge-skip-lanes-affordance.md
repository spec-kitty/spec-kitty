---
work_package_id: WP05
title: Direct-on-target completion affordance `merge --skip-lanes` (#2745)
dependencies:
- WP02
requirement_refs:
- FR-012
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/merge.py
create_intent:
- tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/merge.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, implementer-only boundaries, and TDD/type-safety discipline. Do not proceed until the profile is loaded.

## Objective

Add the `--skip-lanes`/`--no-lanes` **CLI option** to `spec-kitty merge` and wire it onto the executor skip-lanes capability that **WP02 builds** (T021), so an operator can transactionally complete a **merge-ready direct-on-target mission** with no lane branch. Keep the fixed error-translation chain in `merge.py`. Delivers the CLI half of **FR-012** (co-owned with WP02, which owns the executor plumbing). This turns the safe-but-**stuck** direct-on-target path (US5) into a whole lifecycle.

**Scope boundary (FOLD 1 — load-bearing).** This WP owns `cli/commands/merge.py` ONLY. The executor-side plumbing (`_MergeRunState`, `_run_lane_based_merge`, `require_lanes_json`, `_phase_merge_lanes` absent-lane tolerance) is **WP02's T021** — it inherently needs `executor.py` changes and is NOT this WP's to make. This WP: (1) adds the Typer option, (2) threads it into the executor entry call, (3) adds the CLI-surface + regression tests. Do NOT edit `executor.py` here and do NOT assume "the existing executor path" already completes a no-lane mission — verified live, it does not (`require_lanes_json` is unconditional; there is no such path until WP02 builds it).

## Context

- **Spec**: US5 (direct-on-target missions can be completed and closed cleanly) — US5-1 (a merge-ready direct-on-target mission with no lane branch completes transactionally via the affordance, no hard-fail on the absent lane), US5-2 (the flag on a NOT-merge-ready mission still refuses before any mutation — not a bypass of the invariant). D6 (operator ruled to fold #2745's completion affordances). FR-012.
- **Contract**: `contracts/terminus-safety-contract.md` → **C-DIRECT-ON-TARGET (COMPLETE)**: a merge-ready direct-on-target mission with no lane branch completes transactionally via `merge --skip-lanes`/`--no-lanes` (no hard-fail), still enforcing the merge-ready precondition.
- **Domain Language**: **direct-on-target path** — the sanctioned fallback where a WP is implemented directly on the target branch with no lane branch.
- **Constraints**: C-003 (no new uncaught error surface — preconditions raise through the existing `typer.Exit(1)` envelopes; the merge CLI translates a FIXED set of exceptions). Terminology canon — the flag uses canonical `lanes` vocabulary, never `feature`.
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/cli/commands/merge.py:574` — `def merge(...)` (the Typer command; add the flag param here)
  - `src/specify_cli/cli/commands/merge.py:541-554` — the FIXED except-translation chain (`SparseCheckoutPreflightError`, `MissingLanesError`/`CorruptLanesError`, `CoordinationTeardownError` → `typer.Exit(1)`); preserve it, add no new escaping type
  - `src/specify_cli/cli/commands/merge.py:546-548` — `MissingLanesError` currently translates to a hard `Exit(1)` (the "safe-but-stuck" hard-fail on the absent lane); once WP02's skip-lanes plumbing tolerates the absent manifest, this hard-fail no longer fires on the skip-lanes path
  - **WP02's skip-lanes capability** (built in T021): the skip-lanes flag on `_MergeRunState` (:268) + `_run_lane_based_merge` (:1831) + absent-lane tolerance in `require_lanes_json` (:1918) / `_phase_merge_lanes` (:397-460). This WP passes the CLI option THROUGH to that capability.
  - WP02's merge-ready precondition in `executor.py` (`_assert_mission_terminal_ready`) — WP02 guarantees the skip-lanes path still runs it; this WP asserts that end-to-end at the CLI surface (US5-2)

## Per-Subtask Guidance

### T015 — RED-first #2745 skip-lanes test

Create `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`, `@pytest.mark.regression`, issue-pinned to #2745. Drive through the pre-existing `merge` CLI entry point (C-004):
- **US5-1 (genuine completion — not just no-hard-fail)**: a merge-ready **direct-on-target** mission (WP committed on the target branch, NO lane branch) completes via `merge --skip-lanes`. Assert the mission is GENUINELY merged, not merely exit-0 / no-hard-fail — verify a **merge baseline is recorded** (`merged_at` present) AND the **target ref has advanced to include the WP commit** (the target-branch tip contains the direct-on-target work). A bare "exit 0 / no MissingLanesError" assertion is insufficient and would pass a no-op.
- **US5-2 (no bypass)**: the `--skip-lanes` flag on a mission that is NOT merge-ready still refuses before any mutation — the FR-001 precondition (`_assert_mission_terminal_ready`) is not bypassed; the target ref is unchanged.
- **Transactional rollback on the skip-lanes path**: force a post-mutation failure on a `--skip-lanes` completion and assert the state rolls back (target/coord refs restored, no half-termination) — the affordance reuses WP02's checkpoint primitive.

RED before T016, GREEN after. Note: these tests depend on WP02's T021 executor plumbing being in place — sequence WP05 after WP02.

### T016 — Add the `--skip-lanes`/`--no-lanes` CLI option and wire it to WP02's capability

Add the flag param on the `merge` command (:574) and thread it into the executor entry call so it reaches WP02's skip-lanes capability (`_run_lane_based_merge` / `_MergeRunState`). This WP does NOT implement the absent-lane tolerance itself — that is WP02's T021 (it lives in `executor.py`, which this WP does not own). Keep the fixed except-translation chain at :541-554 intact; add no new escaping error type (C-003). The completion stays transactional because WP02's capability reuses the checkpoint primitive.

Terminology canon: the option uses canonical `lanes` vocabulary (`--skip-lanes`/`--no-lanes`), never `feature`. If the executor entry signature needs a new parameter, that signature change is part of WP02's T021 (coordinate) — this WP passes the value through, it does not edit `executor.py`.

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. PR to `main` opens later; the operator merges.
- Depends on WP02 (reuses the precondition + transactional path) — land after WP02.
- Commit the T015 red-first test as a distinct commit before T016.

## ATDD / Test Strategy (red-first defect)

- **#2745** issue-pinned `@pytest.mark.regression` (T015): direct-on-target completes via the flag; flag on a not-merge-ready mission still refuses. RED before, GREEN after.
- Run the merge CLI command tests (`tests/specify_cli/cli/commands/`) plus the full `tests/merge/` directory. Record commands + counts.

## Definition of Done

- [ ] `--skip-lanes`/`--no-lanes` CLI option added on `merge` and wired through to WP02's executor skip-lanes capability; `executor.py` is NOT edited in this WP (FOLD 1).
- [ ] T015 asserts GENUINE completion (merge baseline recorded AND target ref advanced to include the WP commit), NOT merely exit-0 / no-hard-fail; plus a transactional-rollback assertion on the `--skip-lanes` path.
- [ ] The option does NOT bypass the WP02 merge-ready precondition — a not-merge-ready mission still refuses before any mutation, target ref unchanged (US5-2).
- [ ] The fixed except-translation chain (:541-554) is preserved; no new escaping error type (C-003).
- [ ] The option name uses canonical `lanes` vocabulary (no `feature`).
- [ ] T015 regression test green; merge CLI tests + `tests/merge/` green.
- [ ] `ruff` + `ruff format --check` + `mypy` clean; C901 ≤ 15.
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Precondition bypass** — the option becoming an escape from the merge-ready gate. Mitigation: WP02's capability runs the precondition on the skip-lanes path; assert US5-2 end-to-end at the CLI surface.
- **Vacuous US5-1** — a test that only checks exit-0 / no `MissingLanesError` would pass a no-op. Mitigation: assert merge baseline + target-ref advance (genuine completion).
- **Ownership overlap** — the temptation to implement the tolerance in `executor.py` here. Mitigation: that is WP02's T021; this WP only adds the CLI option + wiring + tests. Sequence WP05 after WP02.

## Reviewer Guidance (reviewer-renata)

- Confirm this WP edits `merge.py` ONLY — the executor plumbing is WP02's T021 (FOLD 1).
- Confirm T015 asserts GENUINE completion (baseline recorded + target ref advanced), not just exit-0 / no-hard-fail, and includes a transactional-rollback assertion.
- Confirm the option still enforces the merge-ready precondition end-to-end (US5-2) — not a bypass.
- Confirm no new escaping error type; the fixed translation chain is intact (C-003).
- Confirm canonical `lanes` terminology.
- Confirm the #2745 test drives the real CLI and is genuinely red-first.
