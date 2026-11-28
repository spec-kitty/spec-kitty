---
affected_files: []
cycle_number: 1
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T02:27:54Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review feedback (reviewer: claude::reviewer-renata)

Reviewed commit e94a5626 (range 54314e59..e94a5626) on lane-c. ruff, `ruff format --check --force-exclude`, C901 and mypy are clean on the six changed files. The new tests pass (15 passed, 1 xfailed). Changes are requested for the findings below; every one must be folded or explicitly answered.

## 1. HIGH: `agent action implement` still records no claim base for a default Mission's planning WP (FR-011 not met on the canonical CLI path)

- `src/specify_cli/cli/commands/agent/workflow_executor.py:496-521` (`guard_repo_root_claim`) returns early unless `is_single_branch_repo_root_lane(...)`. For a `lanes_with_coord` planning WP, `agent action implement` therefore never calls `implement_support.guard_repo_root_claim`, and the change at `implement_support.py:377` never runs on that path.
- Reproduced with the integration fixture (`tests/integration/test_7860_planning_evidence_window.py::setup_default_mission`, then `agent action implement WP02`). On this lane `git for-each-ref refs/spec-kitty/` is empty after the claim. A real owned commit in the coordination worktree is then refused by the gate with "no implementation commit since claim in the Mission branch checkout ... beyond <no recorded claim base>". This is `test_planning_work_where_implement_puts_it_moves_into_review` as it fails on this lane. The base (e94a5626~1) gives the same "<no recorded claim base>".
- The WP03 tests call `implement_support.guard_repo_root_claim` directly (`tests/lanes/test_planning_claim_base_7860.py::claim`). They skip the executor wrapper, so they miss this.
- Required fix:
  - Make the agent claim path record the claim base for the `mission_branch_checkout` kind. For example, the executor wrapper records the claim base (without the `WRITE_CHECKOUT_*` guard) whenever `workspace.is_shared_checkout` and the lane is the planning lane. Keep the single_branch guard where it is.
  - Add a test that drives `agent action implement` (CLI subprocess or the Typer app) and asserts `read_claim_base` equals the coordination worktree HEAD.
  - Add a positive gate control through `move-task --to for_review` after an owned commit in the coordination worktree.
  - This is an out-of-map edit (`workflow_executor.py`); record the rationale with add-history.
  - Also check the native `spec-kitty implement` path for the same WP. If it records the base, say so with a test; if it does not, fix it the same way.

## 2. MEDIUM: the xfail for the sibling-commit evidence case cannot detect anything

- Location: `tests/lanes/test_planning_claim_base_7860.py`, `test_the_evidence_axis_refuses_the_hollow_wp_a_sibling_commit_let_through`.
- The xfail is `strict=True, raises=(ImportError, AttributeError, TypeError)`. The call it wraps is `planning_evidence_window(repo, mission_dir, manifest(), PLANNING_WP)`.
- WP04 (lane-d) defines `planning_evidence_window(repo_root, lanes_manifest, lane, wp_id, events)`. Binding the test's arguments to that signature raises `TypeError: missing a required argument: 'events'` (verified against lane-d).
- So after WP04 merges, the test still xfails, through a TypeError, and it can never XPASS.
- There is a second gap. `claim()` records only the claim-base ref, not a claim status event. WP04's window start is the claim-event commit, so a correctly called `planning_evidence_window` would raise `PlanningWindowUnresolved`, not reach the assertion.
- Required fix (either one):
  - (a) Narrow `raises=` to `AttributeError` only (the one honest "not merged yet" failure). Drive the claim through a real claim status transition, so the body is correct once WP04 lands. Assert through the real caller that produces `IMPLEMENTATION_MISSING` (the evidence check used by `move-task` / `accept`), not through private helper composition.
  - (b) Drop the test and record the residual as a named WP05 obligation (add-history and the WP05 hand-off).

## 3. MEDIUM: an unregistered `PLANNING_CHECKOUT_MISSING` now reaches the public envelope `error_code`; `data.error_type` and the new `resolve-workspace` failures were added with no contract decision

- `src/specify_cli/orchestrator_api/wp_lifecycle.py:281-296` (`_fail_workspace_resolution`) puts any `StructuredError.error_code` verbatim into the envelope `error_code`.
  - `PLANNING_CHECKOUT_MISSING` is not in `allowed_error_codes` (`src/specify_cli/core/upstream_contract.json`) or in the documented list (`docs/api/orchestrator-api.md`, "Error Codes").
  - `test_a_mission_branch_no_checkout_holds_is_planning_checkout_missing` asserts this leak as the intended behaviour.
  - Precedent: #5642 (`BOOKKEEPING_FAILED` + `data.bookkeeping_error_code`) and PR-CONTRACT-002 (`test_open_decision_unregistered_decision_error_code_falls_back_never_leaks`). An unregistered code must never reach the public `error_code`.
  - The `WRITE_CHECKOUT_*` passthrough on start is pre-existing (#5100 B5). WP03 now extends it to a new code and to `resolve-workspace`, which used to be read-only and infallible on this arm.
- WP03 also adds the key `data.error_type` to `LANE_ALLOCATION_FAILED` / `TRANSITION_REJECTED`. The WP prompt's own risk note says not to add keys without a version-bump decision from the dispatcher, and there is no record of that decision.
- Required fix:
  - Envelope a non-registered `StructuredError` under the caller's registered fallback code, with the refinement in a data key. For example, `LANE_ALLOCATION_FAILED` with `data.workspace_error_code = "PLANNING_CHECKOUT_MISSING"`, keeping `data.mission_branch` and the remedy.
  - Update the test to match.
  - Get and record the dispatcher's contract decision: a CONTRACT_VERSION minor bump with an `envelope.py` history line, the `docs/api/orchestrator-api.md` text and a changelog fragment for the additive `data.error_type` / refinement key and the new `resolve-workspace` failure modes. Or a recorded ruling that no bump is needed.
  - Note in the changelog that `workspace_path` / `lane_branch` change value for a default Mission's planning WP.

## 4. LOW: the #5296 waiver now fires for a default `single_branch` Mission and reports a false "deferred to target"

- `implement_support.py:883-906`: `_planning_lane_writes_on_mission_branch` reads `planning_write_ref(...).on_mission_branch`, which is True for any `topology_source: default`, not-landed Mission, including a settled `single_branch` one. WP02's resolver excludes `single_branch` in `_mission_branch_target`; this function does not.
- Probe: a default `single_branch` Mission with the root checkout on its Mission branch gives `_planning_claim_waives_code_lanes(...) == True` and `check_claim_ancestry(...).code_lanes_deferred_to == "main"` (before WP03: `None`).
- `agent action implement` (`workflow.py:2035-2049`) then prints "code dependency lanes are not merged into the repository root checkout on the target branch". That is false: the root checkout is on the Mission branch, and a `single_branch` Mission has no code lanes. This is a behaviour change for `single_branch`, which the WP said must stay unchanged.
- The self-heal helper `_planning_self_heal_workspace` already uses the `_mission_branch_target` rule; the waiver should use the same one.
- Required fix:
  - Exclude stored `single_branch` from the new waiver arm, for example by deciding it from the resolved workspace kind (`MISSION_BRANCH_CHECKOUT_KIND`) or by reusing the resolver's rule.
  - Add a `single_branch` default-Mission control test asserting `code_lanes_deferred_to is None` with the root checkout on the Mission branch.

## 5. LOW: the start path resolves the workspace twice and reads the write branch again outside the guarded block

- `wp_lifecycle.py:393-395`: `_ensure_repo_root_checkout_or_fail` resolves and discards the workspace, then `_resolve_repo_root_workspace_or_fail(..., guard=False)` resolves it again. `_repo_root_start_workspace` then calls `_repo_root_lane_branch`, which calls `planning_write_ref` a further time, outside the `try` that envelopes its errors.
- Required fix:
  - Resolve once with `guard=True` and use that result.
  - For `MISSION_BRANCH_CHECKOUT_KIND`, take `lane_branch` from `workspace.branch_name` (the resolver already decided it), or keep `_repo_root_lane_branch` inside the guarded block, so a `PlanningWriteRefUnavailable` raised there can never escape as a traceback.
  - If `_ensure_repo_root_checkout_or_fail` then has no caller, remove it.

## 6. LOW: stale docstrings and comments in touched code

- `implement_support.py`, `reenter_lane_self_heal` docstring ("A PLANNING lane instead reconciles the shared repository-root checkout") and the inline comment "Root is shared, not an allocator-owned disposable lane checkout". The planning workspace may now be the Mission-branch checkout. Name both checkouts.
- `wp_lifecycle.py:504-512`, `_existing_workspace_for_stamp` docstring: "A repo-root-lane WP exists only in a STORED single_branch mission" is false, because every planning-lane WP of a lanes Mission is a repo-root lane. See item 7.
- `for_review_gate.py:240-241`: when `on_mission_branch` holds but `workspace.branch_name` is empty, `lane_branch` silently stays the target and the refusal names the target as the Mission branch. Either assert or fail closed, or name the case in the docstring.

## 7. LOW (pre-existing; record, do not necessarily fix here): the orchestrator stamps `execution_mode` differently from the CLI for planning WPs

- `_existing_workspace_for_stamp` returns `None` for every topology except `single_branch`, so orchestrator `start-review` / `transition` stamp `"worktree"` for a planning WP of a lanes Mission.
- `start-implementation` stamps `"direct_repo"`. CLI `move-task` stamps `ResolvedWorkspace.status_execution_mode` (`"direct_repo"` for `mission_branch_checkout`, per WP02's `runs_in_checkout_root`).
- This predates WP03 (it already held for the `repo_root` kind), so it is not a WP03 regression, but it contradicts WP02's semantics for the new kind.
- Required: record it with add-history and file a follow-up issue, or fix it here if it is cheap (resolve through `resolve_workspace_for_wp` for the repo-root lane on every topology, then use `status_execution_mode`).

## 8. Residuals to record (no code change asked)

- (a) With the coordination worktree removed, `start-implementation` refuses with `MISSION_NOT_FOUND` before it reaches `PLANNING_CHECKOUT_MISSING`, because the Mission directory lives only on the Mission branch. This fails closed: no claim base is recorded and there is no fallback to the repository root checkout. It does not name contract C1's remedy (restore the coordination worktree). `PLANNING_CHECKOUT_MISSING` is covered only through a monkeypatch. Record this as a residual for WP05 / a follow-up, so the lookup refusal can name the coordination doctor remedy.
- (b) The `_lane_assignment_or_legacy` silent legacy fallback (an unreadable or absent `lanes.json` gives the bare legacy path) is pre-existing and unchanged by WP03. No action.
- (c) `_planning_self_heal_workspace` imports the private `workspace.context._mission_branch_target` across modules. Prefer a public seam, or note why the private import is acceptable.

## Tests run (reviewer)

- WP03 tests (3 files): 15 passed, 1 xfailed.
- At-risk set (`tests/lanes tests/orchestrator_api tests/coordination tests/specify_cli/orchestrator_api tests/contract/test_orchestrator_api.py tests/integration/test_7860_planning_evidence_window.py tests/specify_cli/workspace tests/agent/test_orchestrator_commands_integration.py`, `-n 4 --dist loadfile`): 2841 passed, 2 skipped, 1 xfailed, 2 failed.
  - Both failures are in `tests/integration/test_7860_planning_evidence_window.py`: `..._on_the_topic_branch_moves_into_review` (IMPLEMENTATION_MISSING, WP04's axis) and `..._where_implement_puts_it_moves_into_review`.
  - At the base, the first fails the same way and the second also fails with "<no recorded claim base>", which is item 1.
- ruff check, ruff format --check --force-exclude, ruff C901, mypy (3 source files): clean.
