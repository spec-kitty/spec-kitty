---
work_package_id: WP01
title: 'Owned-checkout ownership boundary (code regression #5988)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 8dca72a0c83a7b9e319a79af1bf69ba346d2ac9a
created_at: '2026-10-10T06:16:48.814037+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Code regression
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/workspace/test_owned_root_anchor_guard.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/workspace/root_resolver.py
- tests/integration/test_owned_lifecycle_acceptance_finalize.py
- tests/integration/test_owned_lifecycle_acceptance_e2e.py
- tests/integration/test_owned_lifecycle_acceptance_review.py
- tests/specify_cli/workspace/test_owned_root_anchor_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Owned-checkout ownership boundary (#5988)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer, agent: claude) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Fix the genuine product regression behind the nightly `integration` suite (#5988, **14 tests**). An **owned-checkout** mission (`P`) must never cross into the repository-root checkout (`R`). The brownfield scout confirmed this is **TWO distinct seams**, each a single targeted edit — NOT per-caller threading (read its full map in the Activity Log before coding).

Done when:
- FR-001 (seam A): the `meta.json` birth write converges on the same lock root as its sibling create writers; `test_armed_get_main_repo_root_pin_owned_mission_create` passes (`passed_through == []`).
- FR-002 (seam B): the owned status writes land in `P` (not redirected to `R`), `R` is never materialised into, and the owned `next` walk reaches `implement`/`review` (not a reset-to-`analyze` with `error_code: None`).
- FR-003: non-vacuous behavioral guards on **both** seams, each with a same-fixture positive control.
- All 14 owned-lifecycle acceptance tests green; new repro(s) red-first.

## Context & Constraints

- **Root cause**: `f815fc9b66` (#5883) collapsed path resolution onto `resolve_canonical_root` (`core/paths.py:380`), which follows an owned linked worktree's `.git` pointer back to `R`.
- **C-001**: fix in CODE; do NOT relax the acceptance pins. **R1 (critical)**: the LOCK mutex landing under `R` is *tolerated* by the tests (`tolerate_status_mutex_for`) — do NOT "fix" the lock root to `P`; that de-converges the mutex (a new regression). Keep lock-root (mutex) and status-surface-root (must be `P`) separate.

**Two seams (from the scout):**

- **Seam A — lock-root convergence (sub-cluster A, 1 test)**. `core/mission_creation_meta.py:199` wraps the birth write in `mission_write_lock(feature_dir, fallback_to_dir_name=True)` with no `repo_root`, so it locks under `R` while every sibling create writer threads `write_root=P`. **Fix (one hop, one caller)**: `_write_create_meta(...)` gains a `repo_root`/`write_root` param; caller `core/mission_creation.py:683` passes the already-local `write_root` (set at `:572`, = `P` for owned). `resolve_status_lock_root` already early-returns a non-None `repo_root` (`root_resolver.py:57-58`) — no change there. Do NOT touch the other ~98 `mission_write_lock` callers; they already thread a `repo_root` (status_transition.py:437, emit.py:707, work_package_lifecycle.py:113, mission_finalize_*.py, …).

- **Seam B — write-target redirect (sub-cluster B, the real `next→analyze` cause, 13 tests)**. `canonicalize_feature_dir` (`workspace/root_resolver.py:83`) is owned-UNAWARE: when `R` holds a stale copy it returns `R/kitty-specs/<slug>` (`:137-141`), so an owned status write is silently redirected to `R` — mutating `R` (fails the `assert_unchanged`/"never materialised in R" pins) and starving `P`'s status so `next` reads nothing → `analyze`. **Fix (ONE seam edit, covers all 8 write sites with zero threading)**: make `canonicalize_feature_dir` refuse to redirect when `feature_dir` is inside a linked **owned checkout** of this mission, mirroring the existing coord-worktree non-redirect guard at `root_resolver.py:114-130`. The 8 sites that route through it (do NOT patch individually): `status/emit.py:972,1047,1066,1253`, `status/work_package_lifecycle.py:310,466`, `coordination/status_transition.py:964,2003,2011`.

**The 14 failing #5988 tests (verify each green; map A vs B):**
- `test_owned_lifecycle_acceptance_finalize.py::test_armed_get_main_repo_root_pin_owned_mission_create` — **A** (+ B on the finalize status emits).
- `test_owned_lifecycle_acceptance_e2e.py::test_quickstart_walk_from_every_cwd[{R,P,elsewhere}-{no-,}stale-copy]` (6), `::test_action_commands_refuse_owned_checkout_without_touching_r`, `::test_walk_validates_ownership_exactly_once_per_command` — **B** (materialise-in-R / next-walk), create leg A-adjacent.
- `test_owned_lifecycle_acceptance_review.py::TestUs3As4OwnedReviewBase::test_review_prompt_is_scoped_to_wp_owned_files`, `::TestUs3As5OwnedReviewBaseUnavailable::{test_no_owned_files_is_blocked,test_no_claim_event_is_blocked,test_ambiguous_claim_commit_is_blocked}`, `::TestFr009PromptGovernance::test_p_only_governance_reaches_owned_implement_and_review_prompts` — **B** (review reads status written by prior steps; redirect to `R` starves `P`).

## Subtasks

- **T001** — Red-first: confirm the armed-pin (A) and a representative `..._e2e.py` "materialised in R" / next-walk test (B) are RED on the base for the right reasons (A: pin trips on `resolve_canonical_root`; B: `canonicalize_feature_dir(P_feature_dir)` returns `R/kitty-specs/<slug>`). These acceptance tests are the #5988 pins.
- **T002** — **Seam A**: thread `write_root` through `_write_create_meta` (`mission_creation.py:683` → `mission_creation_meta.py:199` → `mission_write_lock(..., repo_root=write_root)`). Verify the armed-pin green; confirm non-owned creates behaviour-neutral (`write_root == R`).
- **T003** — **Seam B**: make `canonicalize_feature_dir` (`root_resolver.py:83`) owned-aware — no redirect to `R` for a linked owned checkout of this mission (mirror the coord-worktree guard at `:114-130`). Verify the 13 B tests green. Do NOT thread the owned fact into the 8 write sites, and do NOT change the lock root (R1).
- **T004** — Two non-vacuous behavioral guards in `tests/specify_cli/workspace/test_owned_root_anchor_guard.py`, floored on the real linked-worktree fixture shape (`tests/integration/conftest.py` `git worktree add`): (a) **B guard** — with a linked owned `P` whose mission dir exists AND a stale copy at `R/kitty-specs/<slug>`, assert `canonicalize_feature_dir(P_feature_dir) == P_feature_dir`; same harness asserts the coord-worktree and plain-worktree-with-canonical-copy cases STILL redirect (self-mutation control, so "never redirect" cannot pass). (b) **A guard** — assert `_write_create_meta` plumbs `write_root` (patch `mission_write_lock`, assert the `repo_root` kwarg == `write_root`).
- **T005** — Run the three owned-lifecycle acceptance files + the new guard; all 14 + guards green. Record the A/B trace per test in the Activity Log.

## Branch Strategy

- Planning base: `fix/nightly-suites-green-rework` · Merge target: `fix/nightly-suites-green-rework`. Execution worktree is allocated per the computed lane from `lanes.json`; do not pick a base manually.

## Validation (targeted — NO heavy suites)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/integration/test_owned_lifecycle_acceptance_finalize.py \
  tests/integration/test_owned_lifecycle_acceptance_e2e.py \
  tests/integration/test_owned_lifecycle_acceptance_review.py \
  tests/specify_cli/workspace/test_owned_root_anchor_guard.py
```
Plus the owning subsystem unit tests for any writer you touch (e.g. `tests/status/`, `tests/specify_cli/workspace/`). Do NOT run `make test-fast` or whole `tests/architectural`.

## Definition of Done

- All 14 #5988 tests green; red-first shown; guard non-vacuous; shared-mission lock behaviour unchanged for non-owned paths; `ruff`/`mypy` clean on changed files; Activity Log records the per-sub-cluster-B trace.

## Reviewer Guidance (opus)

- Confirm BOTH seams fixed at the single site each (A: `_write_create_meta` threads `write_root`; B: `canonicalize_feature_dir` owned-aware) — NOT per-call-site threading of the 8 write sites.
- **R1**: confirm the lock root was NOT changed to `P` (the mutex-under-`R` toleration is intact) — only the status write *target* (B) and the birth-write convergence (A) changed.
- Verify both guards fail under self-mutation (the coord/plain-worktree cases still redirect). Confirm non-owned creates are behaviour-neutral. Re-run all 14 tests. Confirm no pin was relaxed (C-001). Note the deferred `root_resolver` lock-vs-surface refactor is out of scope (follow-up).
