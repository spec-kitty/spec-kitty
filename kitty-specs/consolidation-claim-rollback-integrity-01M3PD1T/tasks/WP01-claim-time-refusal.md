---
work_package_id: WP01
title: Tidy-first + claim-time refusal (#5338)
dependencies: []
requirement_refs:
- C-001
- C-003
- FR-001
- FR-002
- NFR-003
- NFR-004
planning_base_branch: issue-5338-consolidation-claim-rollback-integrity
merge_target_branch: issue-5338-consolidation-claim-rollback-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-5338-consolidation-claim-rollback-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5338-consolidation-claim-rollback-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidation-claim-rollback-integrity-01M3PD1T
base_commit: 28d6b38d0d32d97409d23ad7f4be3ddb2db28a23
created_at: '2026-09-29T13:21:10.661984+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-09-29T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/terminus/test_repro_5338.py
- tests/consolidation/test_claim_integrity_refusal.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/consolidation/test_executor_phase_boundary.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/reconciliation.py
- tests/terminus/test_repro_5338.py
- tests/consolidation/test_claim_integrity_refusal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Tidy-first + claim-time refusal (#5338)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE: no heavy full suites during the mission

During implement and **every WP review**, you AND every implementer/reviewer subagent you dispatch must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission or to CI (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission consolidation-claim-rollback-integrity-01M3PD1T` and the Activity Log for a `review_ref`; if present, every feedback item is your TODO list.

---

## Objectives & Success Criteria

`spec-kitty consolidate` must **act on a claim-time REFUSE before mutating anything** (#5338). Today `_capture_reconciliation_claim` (`src/specify_cli/consolidation/executor.py:~2258`) builds `run.approved_wp_set` via `build_approved_wp_set` (:~2294) and only acts on `GitProbeError`; a `claim.refusal`, an unresolved surface, or a vacuous claim is **stored and ignored** until `MergeOutcomeVerifier.verify` at the post-mutation gate. On main a gate REFUSE does not even roll the target back (`_phase_reconcile_before_teardown`, :~2448 rolls back only on FAIL).

Done means:
- FR-001: a claim-integrity refusal exits 1 with recovery guidance **before `_phase_merge_lanes`**; target, mission branch and lane branch SHAs, `state.json` bookkeeping (`mission_number_baked`, `completed_wps`), and the status event logs are unchanged. (The post-fix marker re-stamp by `write_post_fix_marker` and a pre-existing `_heal_pending_coord_reconcile` heal are excluded from the comparison.)
- FR-002: a resume whose reconciliation already PASSed for the current target tip (`_resume_reconciliation_already_passed`, #5021) is NOT refused by this check.
- One predicate, no copy: the gate and the claim use the same claim-integrity logic.
- Behaviour-preserving tidy-first commit lands separately and first (Standing Order #2).

## Context & Constraints

- Spec: `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/spec.md` (US1, FR-001/002, SC-001/006). Plan IC-01/IC-02; research D1; live evidence in research D1 and `research/coord_repro_reference.py.txt` (`test_5338`).
- Charter: ATDD-first (red test committed before the fix), complexity ≤ 15, no suppression.
- **C-001 (#5359 overlap)**: open PR #5359 (branch `origin/issue-5046-mixed-lane-authorship`) rewrites `MergeOutcomeVerifier.verify`, `VerifyResult.recovery_guidance`, `build_approved_wp_set`, `_phase_reconcile_before_teardown`, `_rollback_target_after_failed_reconciliation`, `_run_lane_based_consolidation_locked`. **Do not edit those functions.** `_capture_reconciliation_claim`, `_clear_fresh_record_on_pre_mutation_exit` and the module-level code you add are NOT #5359-touched.
- Do not reorder phases in `_run_lane_based_consolidation_locked` (frozen by `tests/consolidation/test_executor_phase_boundary.py::test_locked_driver_calls_phases_in_frozen_order`).
- Terminology: "lane consolidation", "target branch", "repository root checkout"; never introduce "feature".

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks; see `lanes.json`)
- **Planning base branch**: `issue-5338-consolidation-claim-rollback-integrity`
- **Merge target branch**: `issue-5338-consolidation-claim-rollback-integrity`

Execution worktrees are allocated per computed lane from `lanes.json`; start with `spec-kitty agent action implement WP01 --agent claude --mission consolidation-claim-rollback-integrity-01M3PD1T`. Always run tests with `.venv/bin/python -m pytest` from the lane worktree using `PYTHONPATH=<worktree>/src` (or `uv run --frozen` from the worktree) so you import the lane's `src`, not the primary checkout's.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first real-CLI repro (commit FIRST, before any fix)

- **Purpose**: pin #5338 through the pre-existing entry point (`spec-kitty consolidate`), in a real temp repo, asserting real SHAs.
- **Steps**:
  1. Create `tests/terminus/test_repro_5338.py` using the existing coordination fixture helpers from `tests/terminus/conftest.py`: `build_coord_mission` (:314), `plant_canceled_commit` (:713), `run_terminus` (:819), `blob_present_at` (:136). A working scaffold of this exact scenario is in `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/research/coord_repro_reference.py.txt` (`test_5338`).
  2. Scenario B (verified RED on main): build a coord mission `wps=("WP01","WP02")` with a unique `mid8`; plant canceled WP03 content carried by WP02; run `consolidate --mission <slug> --yes` (gate FAILs, target restored). Then `git branch -D <lane branch of WP01>`; record SHAs of the target, the coordination/mission branch, every remaining lane branch, plus `state.json` `mission_number_baked`/`completed_wps` and the status event log bytes; run `consolidate --mission <slug> --resume --yes`.
  3. Assert: `returncode != 0`; target, coordination and remaining lane SHAs are unchanged; `mission_number_baked`/`completed_wps` unchanged; `status.events.jsonl` on the target and coordination refs unchanged (compare `git show <ref>:<path>` bytes); planted canceled file NOT on the target; the output contains the recovery guidance (e.g. "refused" and the lane-branch reason) and does NOT contain "Squashing" or a squash commit.
  4. FR-002 control (same fixture family): a resume whose `state.reconciliation_passed_target_sha` equals the target's current tip must still complete (exit 0). The cheapest real shape is `tests/terminus/test_repro_5021.py`'s mid-teardown resume — reuse/adapt its builder; if that is expensive, a focused unit test in T004 over `_capture_reconciliation_claim` with a refusing claim + PASS anchor is acceptable as the control, but keep at least one real-CLI control.
  5. Mark `@pytest.mark.integration`, `@pytest.mark.git_repo` and `@pytest.mark.regression` exactly like the neighbouring fixed repros (`test_repro_5021.py`, `test_repro_5038.py` keep `regression`: in pytest.ini it means "issue-pinned e2e", not "currently red").
  5b. **US1-AS2 fresh-run case (post-tasks squad finding 8)** — second test in the same file, from `research/coord_repro_reference.py.txt::test_5338_claim_refuse_missing_lane_branch`: fold lanes, delete a lane branch, run a FRESH `consolidate --yes`. Assert rc != 0, **no `state.json` left** for the mission (`.kittify/runtime/merge/<mission_id>/state.json` absent), and every branch SHA unchanged. Today it fails in `_phase_merge_lanes` (after the fresh-record guard) and leaves `state.json` behind — RED.
  5c. **FR-002 control non-vacuity (finding 9)**: in the #5021-style control, assert the lane branch is really gone before the resume (`git rev-parse --verify` fails) and add a unit assertion that `claim_integrity_refusal(<that claim>)` is non-None — so the control proves the exemption, not an absent refusal.
  6. Run it on the WP base — it MUST fail (record the failing assertion in the Activity Log). Commit: `test(consolidate): red-first repro for claim-time REFUSE acting before mutation (#5338)`.
- **Files**: `tests/terminus/test_repro_5338.py` (new, ~120 lines).
- **Notes**: each real-CLI repro takes ~35–40 s. Use a distinct mid8 per test. No mocked git.

### Subtask T002 – Tidy-first, behaviour-preserving (separate commit, before T003/T004)

- **Purpose**: Standing Order #2 campsite: one insertion point, fewer duplicated literals, no behaviour change.
- **Steps**:
  1. In `executor.py`, the phrase "Nothing was torn down" appears three times (:~2312 claim probe error, :~2553 and :~2576 projection refusals). Hoist the shared fragment to a module constant (e.g. `_NOTHING_TORN_DOWN = "Nothing was torn down"`) used by the non-#5359 sites only. Do NOT touch `reconciliation.py:215-228` (`recovery_guidance`, #5359-owned).
  2. Extract the claim-time `GitProbeError` exit (:~2300-2315) into `_exit_on_claim_probe_error(exc) -> NoReturn` (prints the same text, raises `typer.Exit(1) from exc`).
  3. grep tests for the exact strings you touched (`grep -rn "Nothing was torn down" tests/`) and keep output byte-identical.
  4. Run `tests/consolidation/test_executor_phase_boundary.py` (incl. `test_capture_reconciliation_claim_aborts_clean_on_git_probe_error`) — green before and after.
  5. Commit: `refactor(consolidate): hoist refusal literal and extract claim probe-error exit (tidy-first, no behaviour change)`.

### Subtask T003 – Pure predicate `claim_integrity_refusal(claim)`

- **Purpose**: one claim-integrity authority for claim time and gate time (single canonical authority).
- **Steps**:
  1. In `src/specify_cli/consolidation/reconciliation.py` add a module-level function (NOT a method edit):
     ```python
     def claim_integrity_refusal(claim: ApprovedWpCommitSet) -> str | None:
         """Strategy-independent claim-integrity refusal (verify() steps 1-3), or None."""
         reason = MergeOutcomeVerifier._refusal_reason(claim)
         if reason is not None:
             return reason
         if claim.is_vacuous_against_manifest:
             return f"derived claim is empty while the manifest lists {len(claim.manifest_wp_ids)} WP(s)"
         return None
     ```
     Match the exact vacuous text `verify()` uses today (reconciliation.py:~445). Do NOT edit `verify()` (#5359-owned): accept the duplicated literal for now and pin equality with the parity test below; rewiring `verify()` to call the predicate is a one-liner deferred until #5359 lands — note it in the Activity Log.
  2. Scope: ONLY these three checks. The squash "empty authored-blob set" REFUSE is a gate-time content check (it would wrongly refuse planning-artifact-only missions at claim time) — do not include it. #5359's new REFUSE reasons are also gate-time — out of scope.
  3. Unit tests `tests/consolidation/test_claim_integrity_refusal.py`: explicit `refusal` → that text; `surface_resolved=False` → surface text; vacuous → vacuous text; healthy claim → None; and a parity test asserting `claim_integrity_refusal(c)` is non-None iff `MergeOutcomeVerifier(repo).verify(target, c)` returns REFUSE for claims that fail steps 1-3 (build `ApprovedWpCommitSet` instances the way existing tests in `tests/consolidation/test_reconciliation.py` do).
  4. Add `claim_integrity_refusal` to the module `__all__` if the module declares one; make sure `tests/architectural/test_no_dead_symbols.py` stays green (it has a caller after T004).

### Subtask T004 – Act on the refusal at claim time

- **Purpose**: FR-001/FR-002.
- **Steps**:
  1. At the end of `_capture_reconciliation_claim` (after `run.approved_wp_set = build_approved_wp_set(...)`), add:
     ```python
     refusal = claim_integrity_refusal(run.approved_wp_set)
     if refusal is not None and not _resume_reconciliation_already_passed(run):
         _exit_on_claim_integrity_refusal(refusal)
     ```
     where `_exit_on_claim_integrity_refusal` prints a truthful claim-time message — e.g. `Consolidation refused before any change (fail-closed claim integrity): {refusal}. No branch, worktree or status record was changed by this run. Fix the cause, then re-run; if an earlier attempt left partial state, run \`spec-kitty consolidate --abort\` first.` — and raises `typer.Exit(1)`. The statement "no branch … was changed by this run" is TRUE here (pre-mutation); keep it scoped to "this run".
  2. This runs inside `_clear_fresh_record_on_pre_mutation_exit` (driver :~3303), so a fresh run's record is cleared automatically; a `--resume` record is kept (correct: the operator then `--abort`s).
  3. `_resume_reconciliation_already_passed(run)` only reads state + the target ref; calling it here is safe. Do not duplicate it.
  4. Keep `_capture_reconciliation_claim` ≤ 15 complexity (`.venv/bin/ruff check --select C901 src/specify_cli/consolidation/executor.py`).
  5. T001's tests must now pass (keep their markers). Commit: `fix(consolidate): refuse at claim time before any mutation when the claim fails integrity (#5338)`.

### Subtask T005 – Re-pin stale tests; run the targeted surface

- **Steps**:
  1. Find tests that construct a refusing / unresolved / vacuous claim and expect later phases or the gate to run: `grep -rln "refusal=\|surface_resolved=False\|is_vacuous_against_manifest\|_capture_reconciliation_claim" tests/consolidation tests/terminus tests/specify_cli/cli/commands tests/merge 2>/dev/null`. For each failing one decide per Standing Order #4: stale assertion (same valid scenario, the refusal now fires earlier) → re-pin with a one-line dated rationale citing #5338; valid test exposing a real product problem → fix the product. Never soften the fix.
  2. Run (and record counts in the Activity Log):
     - `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5338.py tests/consolidation/test_claim_integrity_refusal.py tests/consolidation/test_reconciliation.py tests/consolidation/test_executor_phase_boundary.py tests/terminus/test_repro_5021.py -q`
     - the owning fast tier: `PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation -m "fast or unit" -q -n auto --dist loadfile`
     - named gates: `tests/architectural/test_merge_pipeline_ratchets.py`, `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_no_legacy_terminology.py`
     - `.venv/bin/ruff check src/specify_cli/consolidation/ tests/terminus/test_repro_5338.py tests/consolidation/test_claim_integrity_refusal.py`, `.venv/bin/ruff format --check` on the same files, `.venv/bin/mypy src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/executor.py` (no new errors vs the base — compare counts).

## Test Strategy

Red-first real-CLI repro (T001) + unit predicate tests (T003) + targeted re-pins (T005). No mocked git in acceptance tests (NFR-004).

## Risks & Mitigations

- **False refusal of a legitimate resume** → FR-002 exemption + real control.
- **Stale tests** encoding "refused claim still merges" → re-pin with rationale; do not delete valid coverage.
- **#5359 rebase conflict** → you add a module-level function and edit only `_capture_reconciliation_claim`; `verify()` untouched.

## Review Guidance

- Reviewer ≠ implementer. Verify red→green: check out the WP base + T001 commit → the repro fails; WP tip → passes.
- Verify the assertions compare real `git rev-parse` SHAs and state/event bytes (not mocks) and include the canceled-file-not-on-target check.
- Confirm no edit to `verify()`, `recovery_guidance`, `build_approved_wp_set`, `_phase_reconcile_before_teardown`, `_run_lane_based_consolidation_locked`.
- Confirm the HARD RULE was respected (no whole `tests/architectural/`).
- mypy/ruff on touched files; complexity ≤ 15.

## Activity Log

- 2026-09-29T13:00:00Z – system – Prompt created.
