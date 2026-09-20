---
work_package_id: WP02
title: Merge safety core (#4764 + rollback + direct-on-target refuse)
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- FR-008
- FR-010
- FR-012
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
- T021
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/executor.py
create_intent:
- tests/merge/test_issue_4764_terminus_safety.py
- tests/merge/test_merge_rollback_resume_coherence.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/policy/merge_gates.py
- src/specify_cli/merge/executor.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, boundaries (implementer only — no scope expansion beyond the owned files), and TDD/type-safety discipline. This is the cohesive merge-path core; do not proceed until the profile is loaded.

## Objective

The heart of the terminus-safety invariant. Five coupled changes on the merge path, all on the two owned files:

1. **De-conflate** the terminal-lane invariant OUT of the mode-softened evidence gate in `merge_gates.py` (FR-003 — `warn` keeps softening evidence-QUALITY gates, never the terminal-lane readiness).
2. Add an **unconditional merge-ready precondition** in `executor._phase_gates_and_state` (before `_phase_merge_lanes`), extracted as `_assert_mission_terminal_ready(run)`, raising `typer.Exit(1)` — refuses before ANY mutation regardless of `merge_gates.mode` (FR-001, FR-002, FR-006).
3. **Unify** the coord-transaction machinery into ONE checkpoint primitive with a NEW pre-mutation checkpoint + reset on post-mutation failure, reset running BEFORE `_phase_cleanup_worktrees_and_branches` (FR-007, FR-008).
4. **Direct-on-target refuse-before-advance** guard (FR-010, US3-3).
5. **Executor-side skip-lanes plumbing** (FOLD 1 — the executor capability behind `merge --skip-lanes`): a skip-lanes flag threaded through `_run_lane_based_merge` + `_MergeRunState`, with absent-lane tolerance in `require_lanes_json` / `_phase_merge_lanes`, so a merge-ready no-lane direct-on-target mission consolidates/records transactionally. WP05 wires the CLI option onto this capability; the plumbing itself is executor-owned, so it lives here (FR-012, co-owned with WP05).

Delivers **FR-001, FR-002, FR-003, FR-006, FR-007, FR-008, FR-010** and the executor half of **FR-012**.

**Why FR-012's executor plumbing is here (FOLD 1, verified live)**: `require_lanes_json` (`executor.py:1918`) and the `_phase_merge_lanes` → `consolidate_lane_into_mission` loop (:397-460) are UNCONDITIONAL — there is NO existing executor path to complete a no-lane direct-on-target mission (grep `skip_lanes`/`no_lanes` = 0 hits). `--skip-lanes` therefore inherently requires `executor.py` changes, which is WP02's owned file, not WP05's. This plumbing also gives the direct-on-target refuse test (T010) a genuine entry point that actually reaches the target-advance path (FOLD 3).

## Context

- **Spec**: US1 (merge refuses an unapproved mission before it mutates) — scenarios US1-1..US1-6, especially **US1-5** (`--resume` re-evaluates LIVE readiness, never vacuous on a stale `merged_at`/baseline) and **US1-6** (cancelled-without-provenance ⇒ not ready). US3 (fail-after-mutation rolls back) — US3-1 (coord ref/worktree reset, `--resume` reads coherent state), US3-3 (direct-on-target refuse-before-advance, target ref provably unchanged). Edge cases: legitimately-softened evidence gate must proceed; rollback after coord teardown must run before teardown or fail closed; `--force` retains hollow-review semantics (out of scope for softening).
- **Contract**: `contracts/terminus-safety-contract.md` → **C-MERGE** (PRE/REFUSE/PASS/WARN), **C-ROLLBACK**, **C-DIRECT-ON-TARGET (SAFE)**.
- **Data model**: `data-model.md` → merge-ready predicate (derived from the WP01 aggregate); coordination checkpoint fields (pre-mutation coord ref SHA, pre-mutation worktree state, pre-done coord ref SHA folded in, target ref for the direct-on-target arm).
- **Research** (`research.md`): #4764 root cause — `MergeGateConfig.mode="warn"` (`policy/config.py:27`) makes the evidence gate non-blocking (`merge_gates.py:121`), so `executor.py` never stops; consolidation + bake happen before the backstop fails with no rollback. A precondition stops before any mutation.
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/policy/merge_gates.py:118-121` — `if not policy.enabled or policy.mode == "off": ... is_blocking = policy.mode == "block"`
  - `src/specify_cli/policy/merge_gates.py:147` — `_evaluate_evidence_gate` (the softenable evidence path; terminal-lane readiness must NOT ride here)
  - `src/specify_cli/policy/merge_gates.py:173`, `:314` — inline `is_acceptable_ending(...)` uses
  - `src/specify_cli/merge/executor.py:343` — `def _phase_gates_and_state(run)` (precondition goes at the TOP, before consolidation)
  - `src/specify_cli/merge/executor.py:397` — `def _phase_merge_lanes(run)` (the first mutation phase)
  - `src/specify_cli/merge/executor.py:282` / `:486` — `done_marked_before_target` flag (direct-on-target boundary)
  - `src/specify_cli/merge/executor.py:553` — `_capture_pre_target_coord_ref_sha`
  - `src/specify_cli/merge/executor.py:644` — `_revert_coord_done_commit`
  - `src/specify_cli/merge/executor.py:788` — `_restore_and_guard_coord_coherence`
  - `src/specify_cli/merge/executor.py:1588` — `_phase_cleanup_worktrees_and_branches` (reset MUST run before this; after teardown a reset silently no-ops)
  - `src/specify_cli/merge/executor.py:1815-1827` — the phase call sequence (`_phase_gates_and_state` → `_phase_merge_lanes` → ... → `_phase_cleanup_worktrees_and_branches`)
  - **Skip-lanes plumbing seams (FOLD 1, verified live)**:
    - `src/specify_cli/merge/executor.py:268` — `_MergeRunState` (thread a skip-lanes flag onto the run state)
    - `src/specify_cli/merge/executor.py:1831` — `_run_lane_based_merge(...)` (accept + propagate the skip-lanes flag)
    - `src/specify_cli/merge/executor.py:1918` — `require_lanes_json` (UNCONDITIONAL today; tolerate an absent lane manifest when skip-lanes is set AND the mission is a merge-ready no-lane direct-on-target mission)
    - `src/specify_cli/merge/executor.py:397-460` — `_phase_merge_lanes` → `consolidate_lane_into_mission` loop (UNCONDITIONAL today; skip the per-lane consolidation for the no-lane path while still recording the direct-on-target completion transactionally)
    - grep `skip_lanes` / `no_lanes` = 0 hits today (net-new capability)

## Per-Subtask Guidance

### T005 — RED-first #4764 + `--resume` vacuous-pass tests

Create `tests/merge/test_issue_4764_terminus_safety.py`, marked `@pytest.mark.regression` and issue-pinned to #4764. Drive through the **pre-existing CLI merge entry point** (C-004):
- **#4764 core**: a mission with a non-cancelled WP `in_progress` (unapproved) under default `merge_gates.mode: warn`. Assert: `merge` exits non-zero; a clear "not merge-ready — WPs missing approval" refusal; NO lane consolidation (lane commits beyond coordination intact); NO `mission_number` bake (coord and primary `meta.json` still agree, number still unassigned); the WP can still transition to `for_review`. (US1-1, US1-2; NFR-003 review integrity.)
- **US1-5** (`--resume` vacuous-pass refusal): a `--resume`d merge whose baseline was already stamped mid-flight AND a non-cancelled WP still unapproved ⇒ merge re-evaluates LIVE terminal readiness and still refuses; it does NOT pass vacuously on the stale `merged_at`/baseline marker.
- **US1-3 / US1-4 non-regression**: a normal merge-ready mission proceeds under any gate mode; a merge-ready mission with a soft evidence-quality concern still softens that gate to a warning under `warn`.

These are RED before T006/T007 and GREEN after.

### T006 — De-conflate the evidence gate (`merge_gates.py`)

Separate the terminal-lane readiness from the mode-softened evidence-quality path. Evidence-QUALITY gates (`_evaluate_evidence_gate` :147, risk, dependency, issue-matrix) stay softenable under `warn`; the terminal-lane invariant ("every non-cancelled WP approved/done") must NOT be softened by `mode`. The cleanest shape: the terminal-lane readiness becomes the executor precondition (T007) and is removed from / no longer gated by the softenable evidence path here. Keep the `is_acceptable_ending` uses that legitimately classify cancelled-with-provenance.

### T007 — Unconditional merge-ready precondition (`executor.py`)

Extract `_assert_mission_terminal_ready(run) -> None` and invoke it at the TOP of `_phase_gates_and_state` (:343), BEFORE `_phase_merge_lanes` (:397) runs any consolidation. It calls the WP01 aggregate `mission_terminal_acceptability` (import from `specify_cli.status_lanes` — facade-safe; or via the `specify_cli.status` facade for any `status`-package reader it needs, C-002). On not-merge-ready, raise `typer.Exit(1)` (NO new error type — C-003) with a message naming the missing WP(s). Keep the function at C901 ≤ 15 (C-006) — extract, don't inline. This precondition is unconditional across `merge_gates.mode` (FR-002).

### T008 — Unify the coord-transaction machinery into one checkpoint primitive

Fold `_capture_pre_target_coord_ref_sha` (:553), `_restore_and_guard_coord_coherence` (:788), and `_revert_coord_done_commit` (:644) into ONE checkpoint primitive that holds NAMED checkpoints (a NEW pre-mutation checkpoint captured before `consolidate_lane_into_mission`, plus the existing pre-done boundary). On a post-mutation failure, reset the coord ref (+ worktree) to the pre-mutation checkpoint so consolidation + bake are undone and `--resume` reads a coherent state (FR-007, FR-008). The reset MUST run BEFORE `_phase_cleanup_worktrees_and_branches` (:1588) — after teardown `_coord_worktree_root` returns None and a reset silently no-ops (spec Edge Case: run before teardown, or detect and fail closed). Preserve every existing rollback path already wired at :966/:990/:1002/:1205/:1263 — unify them onto the primitive, don't drop them.

### T009 — Direct-on-target refuse-before-advance guard (US3-3)

For the direct-on-target path (no lane branch; done marked after target advance at `:971-985`, `done_marked_before_target` :486), ensure a not-merge-ready mission refuses BEFORE advancing the target ref — the target ref is provably unchanged. The T007 precondition (`_assert_mission_terminal_ready`) must be the SOURCE of the refusal on this path.

**FOLD 3 — the refusal must not pass vacuously via the wrong gate.** Verified live: `require_lanes_json` (:1918) fires BEFORE `_phase_gates_and_state` (:343), so today a not-merge-ready NO-LANES mission refuses via `MissingLanesError` (the WRONG reason — a missing manifest, not an unapproved WP) and `_assert_mission_terminal_ready` never runs. The direct-on-target path this WP must protect is the **skip-lanes path** (T021): once skip-lanes tolerates the absent manifest, the flow reaches `_assert_mission_terminal_ready`, which is where the refusal must originate. Order the checks so that on the skip-lanes path a not-merge-ready mission is refused by `_assert_mission_terminal_ready` (message names the missing WP), NOT swallowed as a `MissingLanesError`.

**D5 caveat (load-bearing)**: the *rollback-after-target-advance* on the direct-on-target path is a distinct, harder seam with no existing machinery. If it proves mission-sized, **ship the refuse-before-advance guard (US3-3) and mark the target-advance rollback as a tracked #3897 follow-up in this WP's Definition of Done** — do NOT silently drop it. The interim state is provably safe because refuse-before-advance makes the half-terminated state unreachable (FR-010 acceptance arm 3).

### T010 — RED-first rollback + direct-on-target refuse tests

Create `tests/merge/test_merge_rollback_resume_coherence.py`, `@pytest.mark.regression`:
- Force a post-mutation failure after consolidation + bake ⇒ coord ref and worktree reset to pre-merge state; mission remains reviewable; a subsequent `--resume` reads a coherent state (no split-brain between committed coordination `done` markers and worktree bytes) — US3-1.
- **Direct-on-target refuse (FOLD 3 — non-vacuous)**: construct a mission that actually REACHES the target-advance path — a NO-LANES direct-on-target mission driven through the **skip-lanes path** (T021), NOT a plain no-manifest mission that would trip `require_lanes_json` first. Assert the refusal ORIGINATES from `_assert_mission_terminal_ready` (the message names the missing WP), that it is EXPLICITLY NOT a `MissingLanesError`, and that the target ref SHA is provably unchanged — US3-3. State the entry point in the test (the skip-lanes path).
- (If the target-advance rollback arm ships) a direct-on-target completion that advanced the target ref and then fails rolls the target ref back — US3-2.

### T021 — Executor-side skip-lanes plumbing (FOLD 1, FR-012 executor half)

Build the executor capability behind `merge --skip-lanes`/`--no-lanes` (WP05 adds the CLI option and wires it here):
- Thread a skip-lanes flag onto `_MergeRunState` (:268) and through `_run_lane_based_merge` (:1831).
- Make `require_lanes_json` (:1918) tolerate an absent lane manifest ONLY when skip-lanes is set and the mission is a merge-ready no-lane direct-on-target mission (never a blanket bypass of the manifest requirement for real lane missions).
- In `_phase_merge_lanes` (:397-460), skip the per-lane `consolidate_lane_into_mission` loop for the no-lane path while still recording the direct-on-target completion transactionally (reuse the T008 checkpoint primitive so a post-mutation failure still rolls back).
- The T007 merge-ready precondition still runs on this path (no bypass — the skip-lanes tolerance is about the missing MANIFEST, not the readiness gate). This is what makes T009/T010's FOLD-3 refuse test reach `_assert_mission_terminal_ready`.
- Add executor-level tests for the skip-lanes plumbing (merge-ready no-lane mission genuinely completes; not-merge-ready no-lane mission refuses via `_assert_mission_terminal_ready`). WP05 owns the CLI-surface tests.

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. The mission branch later opens a PR to `main`, which the operator merges.
- Commit each red-first test (T005, T010) as a distinct commit BEFORE its implementation commit.

## ATDD / Test Strategy (red-first defect)

- **#4764** issue-pinned `@pytest.mark.regression` (T005): RED through the pre-existing CLI merge entry point before the fix, GREEN after. Plus the `--resume` vacuous-pass refusal (US1-5) and rollback resume-coherence + direct-on-target refuse (T010).
- **NFR-002 non-regression**: every previously-passing merge path stays green, incl. `--resume`. Run the FULL `tests/merge/` directory plus the acceptance suites. Record commands + passed/failed counts. Attribute any pre-existing red per the baseline-red gotcha (green-on-base + red-on-branch = yours).
- **NFR-004**: the precondition adds negligible latency (a single aggregate read).

## Definition of Done

- [ ] `_assert_mission_terminal_ready(run)` runs at the top of `_phase_gates_and_state`, before any consolidation, unconditional across `merge_gates.mode`; raises `typer.Exit(1)` naming the missing WP(s).
- [ ] Terminal-lane readiness de-conflated from the mode-softened evidence gate in `merge_gates.py`; evidence-quality gates still soften under `warn` (FR-003).
- [ ] One unified checkpoint primitive with a pre-mutation checkpoint; post-mutation failure resets coord ref/worktree BEFORE `_phase_cleanup_worktrees_and_branches`; `--resume` reads coherent state.
- [ ] Direct-on-target refuse-before-advance guard proven (target ref unchanged on a not-merge-ready mission), with the refusal ORIGINATING from `_assert_mission_terminal_ready` (not a `MissingLanesError`) via the skip-lanes path (FOLD 3). **If** the target-advance rollback is deferred per D5, this DoD explicitly records it as a tracked #3897 follow-up (not silently dropped).
- [ ] Executor-side skip-lanes plumbing (T021): a skip-lanes flag threaded through `_MergeRunState` + `_run_lane_based_merge`; `require_lanes_json` / `_phase_merge_lanes` tolerate the absent lane for a merge-ready no-lane direct-on-target mission and complete it transactionally; the T007 precondition still runs (no bypass). WP05 wires the CLI option onto this capability.
- [ ] T005 + T010 regression tests green; full `tests/merge/` green (no false-block on a merge-ready mission, incl. `--resume`).
- [ ] `ruff` + `ruff format --check` + `mypy` clean; touched/new functions C901 ≤ 15; no new escaping error type (C-003).
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Complexity ceiling** — `_phase_gates_and_state` and the checkpoint primitive are near the C901=15 ceiling. Extract testable helpers; do not inline the precondition or the reset logic.
- **False-block regression (NFR-002)** — a too-broad precondition blocks a legitimate merge-ready mission (esp. all-cancelled-with-provenance boundary, or on `--resume`). Mitigation: reuse the WP01 aggregate exactly; assert US1-3 non-regression.
- **Reset-after-teardown no-op** — a reset placed after `_phase_cleanup_worktrees_and_branches` silently does nothing. Mitigation: reset strictly before teardown; add a fail-closed detection if the coord worktree is already gone.
- **D5 scope balloon** — the target-advance rollback is the mission's hardest seam. Mitigation: ship the interim refuse-before-advance guard and track the rollback as #3897 follow-up rather than blocking the WP.

## Reviewer Guidance (reviewer-renata)

- Confirm the precondition fires BEFORE any mutation and is NOT routed through `policy.mode` (FR-002) — a `warn`-mode unapproved merge must exit non-zero with nothing consolidated/baked.
- Confirm evidence-quality gates still soften under `warn` (FR-003) — the invariant hardened only terminal-lane readiness.
- Confirm the checkpoint primitive is ONE unified thing (C-001, no forked rollback machinery) and the reset precedes teardown.
- Confirm `--resume` re-evaluates live readiness (US1-5) and does not pass vacuously.
- If the D5 target-advance rollback is deferred, confirm the follow-up is tracked and the refuse-before-advance guard provably keeps the state safe.
- Confirm the direct-on-target refuse test (T010) reaches the target-advance path via the skip-lanes plumbing and that the refusal is `_assert_mission_terminal_ready` (naming the missing WP), NOT a vacuous `MissingLanesError` (FOLD 3).
- Confirm the skip-lanes plumbing (T021) does NOT bypass the merge-ready precondition and reuses the T008 checkpoint primitive (transactional completion).
- Confirm the #4764 test drives the real CLI entry point and is genuinely red-first (not asserted post-hoc).
