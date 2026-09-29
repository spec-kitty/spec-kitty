---
work_package_id: WP05
title: Planning self-heal never merges onto the target checkout (#5296)
dependencies:
- WP02
requirement_refs:
- C-007
- FR-008
planning_base_branch: issue-5338-consolidation-claim-rollback-integrity
merge_target_branch: issue-5338-consolidation-claim-rollback-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-5338-consolidation-claim-rollback-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5338-consolidation-claim-rollback-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidation-claim-rollback-integrity-01M3PD1T
base_commit: 28d6b38d0d32d97409d23ad7f4be3ddb2db28a23
created_at: '2026-09-29T14:03:57.147754+00:00'
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 2 - Integration
history:
- at: '2026-09-29T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_planning_target_checkout_waiver.py
- tests/terminus/test_repro_5296.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/lanes/implement_support.py
- tests/lanes/test_planning_claim_self_heal.py
- tests/lanes/test_planning_target_checkout_waiver.py
- tests/terminus/test_repro_5296.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Planning self-heal never merges onto the target checkout (#5296)

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

#5296: claiming a planning work package (`execution_mode: planning_artifact`, lane `lane-planning`) that depends on approved code WPs runs the dependency self-heal, which merges every code dependency lane into the planning lane's worktree — the **repository root checkout, on the target branch** — so code lands on the target before consolidation, bypassing its attribution window. Operator decision (DM `01M3PJWGGKTRT9W03MJHFV44Q2`, superseding the refuse decision which deadlocks): **skip the merge and waive code-lane ancestry** for exactly that placement; the claim proceeds; the code reaches the target only through `spec-kitty consolidate`.

Done means (FR-008, SC-003):
- In a LANES mission, claiming the planning WP whose dependency lane-a is approved succeeds; the target branch SHA is unchanged; lane-a's files are NOT in the repository root checkout; a notice says code lanes reach the target through consolidation.
- After approving the planning WP, `spec-kitty consolidate` exits 0, the reconciliation gate passes, and lane-a's code is on the target (live-verified feasible in the post-plan residual hunt).
- Control: when the repository root checkout's HEAD is NOT the mission's target branch, the self-heal behaves exactly as today.
- On a PROTECTED target (`main`), today's claim dies with `ProtectedBranchCommitError` in the self-heal (a deadlock already on main, live-verified); after the fix the claim proceeds without any commit on the target.

## Context & Constraints

- Live-verified facts (post-plan residual hunt item 3):
  - `create_planning_workspace` always returns `repo_root`; `workspace/context.py:~835-848` gives every planning lane `resolution_kind="repo_root"` regardless of topology. So the discriminator is **"repository root checkout HEAD (`git symbolic-ref --short HEAD`) == `lanes_manifest.target_branch`"**, not placement.
  - `check_claim_ancestry` (`lanes/implement_support.py:~515`) returns `ok=False` listing the missing "approved dependency lane lane-a"; `resolve_claim_ancestry_gate` (~:565-585) then self-heals via `reenter_lane_self_heal` (~:307-384) which calls `_merge_dependency_lane_tips` (`lanes/worktree_allocator.py:~1193`) in the root checkout and re-checks.
  - `_approved_dependency_lane_refs` (~:444) is the ONE predicate both `check_claim_ancestry` and the self-heal (~:372) consume.
- **Single seam**: implement the waiver ONLY in `_approved_dependency_lane_refs` (post-plan split-brain fold). When it returns no code-lane refs for this case, `check_claim_ancestry` passes first and the self-heal merge — and its `assert_not_protected_branch` — is never reached. Do not add a second check in `reenter_lane_self_heal` or `resolve_claim_ancestry_gate`.
- **C-007**: do not touch `_merge_dependency_lane_tips` internals (pinned by `tests/architectural/test_destructive_op_routing.py`); allocator call sites (:786/:845/:958) are code-lane only.
- Which dependency lanes are "code lanes"? Every dependency lane other than `lane-planning` itself (a planning lane's dependencies on other planning-lane WPs are in the same lane, not dependency lanes). Keep the rule that simple; document it in the docstring.
- LANES fixture: `tests/terminus/lanes_fixture.py` (WP02). Use an unprotected target (`develop`) for the main repro; add the protected-`main` claim-only case as a second repro (it must not commit on `main`).

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks; see `lanes.json`)
- **Planning base branch**: `issue-5338-consolidation-claim-rollback-integrity`
- **Merge target branch**: `issue-5338-consolidation-claim-rollback-integrity`

Start with `spec-kitty agent action implement WP05 --agent claude --mission consolidation-claim-rollback-integrity-01M3PD1T` (after WP02 is approved).

## Subtasks & Detailed Guidance

### Subtask T022 – Red-first real-CLI repro (commit FIRST)

- `tests/terminus/test_repro_5296.py` with `build_lanes_mission` (extend the builder call, or build on top of it, to add WP02 as `execution_mode: planning_artifact` in `lane-planning` depending on WP01 in lane-a):
  1. Approve WP01 through the real status path the fixture uses (move-task/emit), record `git rev-parse develop` and the root checkout file list.
  2. Claim WP02 through the real entry point: `spec-kitty agent action implement WP02 --agent claude --mission <slug>` (run from the repo root with the lane's `spec-kitty` — via `run_terminus`-style subprocess with the lane `PYTHONPATH`).
  3. Assert (RED today): exit 0; `develop` SHA unchanged; `src/pkg/wp01.py` (the lane-a file) NOT present in the root checkout; output contains the notice.
  4. Continue: make a planning commit on `develop` under `kitty-specs/<slug>/` (what a planning WP does), approve WP02, `spec-kitty consolidate --mission <slug> --yes` → exit 0; `blob_present_at(repo, "develop", "src/pkg/wp01.py")`; output contains the reconciliation PASS line.
  5. Protected-target claim case (target `main`): claim WP02 → exit 0 (today: `ProtectedBranchCommitError`), `main` SHA unchanged.
- Markers `integration`, `git_repo`, `regression` (issue-pinned e2e; kept after the fix). Build with `build_lanes_mission(..., with_planning_lane_wp=True, planning_depends_on_code=True, approve_planning_wp=False)` (WP02 T011 parameters). Commit: `test(lanes): red-first repro for planning claim merging code lanes onto the target (#5296)`.

### Subtask T023 – The waiver in `_approved_dependency_lane_refs`

- Add a small pure helper `_root_checkout_is_target(main_repo_root: Path, lanes_manifest: LanesManifest) -> bool` (`git symbolic-ref --short -q HEAD` in `main_repo_root` == `lanes_manifest.target_branch`; detached/unresolvable → False).
- In `_approved_dependency_lane_refs`, when `is_planning_lane(lane)` (canonical predicate; the constant is `PLANNING_LANE_ID` in `lanes/compute.py:~31` — do not compare ids by hand) AND `_root_checkout_is_target(...)`: return `[]` (no code-lane ancestry requirement) and emit a one-time console notice: `Planning work package: code dependency lanes are not merged into the repository root checkout on the target branch; they reach <target> through \`spec-kitty consolidate\` (#5296).` — emit the notice from the caller that owns console output if this module does not print (check the module's conventions; prefer returning a flag and letting `check_claim_ancestry` / the CLI layer print).
- Update the docstring (the C-005 rationale plus the #5296 waiver and its exact scope). Keep complexity ≤ 15.

### Subtask T024 – Keep the existing control; add the on-target contract

Post-tasks finding 5: in `tests/lanes/test_planning_claim_self_heal.py` the repository root checkout is on `feat/planning` while `target_branch` is `main` (`test_claim_ancestry_gate._write_meta_and_lanes`), so the scoped waiver never fires there — `test_planning_materialization_claim_merges_approved_dependency` (and the protected / dirty / conflicting variants) are ALREADY the off-target controls and must stay green unchanged (rename only if it clarifies, e.g. `..._off_target_checkout_...`).
- Add `test_planning_claim_on_target_checkout_waives_code_lane_ancestry`: same helpers, but check out `main` (== target) in the root → claim ancestry ok, root HEAD unchanged, no merge commit, lane-a file absent.
- Add `test_planning_claim_on_protected_target_checkout_does_not_raise`: root on protected `main` == target → no `ProtectedBranchCommitError`, HEAD unchanged.

### Subtask T025 – Unit tests + targeted runs

- `tests/lanes/test_planning_target_checkout_waiver.py`: `_root_checkout_is_target` truth table (on target, other branch, detached HEAD); `_approved_dependency_lane_refs` returns `[]` for lane-planning on target, unchanged refs for a code lane and for lane-planning off target.
- Run (record counts):
  - `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5296.py tests/lanes/test_planning_claim_self_heal.py tests/lanes/test_planning_target_checkout_waiver.py -q`
  - other tests of the module: `grep -rl "implement_support\|check_claim_ancestry\|resolve_claim_ancestry_gate\|reenter_lane_self_heal" tests/ | head -20` → run those files
  - fast tier `tests/lanes -m "fast or unit"`
  - NAMED gates: `tests/architectural/test_destructive_op_routing.py` (unchanged allocator), `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_legacy_terminology.py`
  - ruff check/format + mypy on `implement_support.py` and new tests.

## Risks & Mitigations

- **Over-broad waiver** (skipping ancestry for code lanes) → scope strictly to `lane-planning` + root-HEAD-is-target; control test.
- **Consolidation later refusing lane-planning as stale ("overlapping files")** — issue #5296 step 1 saw this when the target already held the code; after the fix the target does NOT hold it, and the residual hunt reached rc 0; keep the end-to-end consolidate assertion in T022 as the proof.
- **Existing missions already wedged** by a prior self-heal are not repaired here (out of scope; mention in the Activity Log).

## Review Guidance

- Reviewer ≠ implementer; red→green verified (T022 at WP base vs tip).
- The waiver lives in ONE function; no second check elsewhere.
- Target SHA asserted unchanged with real `git rev-parse`; end-to-end consolidate passes.
- HARD RULE respected.

## Activity Log

- 2026-09-29T13:00:00Z – system – Prompt created.
