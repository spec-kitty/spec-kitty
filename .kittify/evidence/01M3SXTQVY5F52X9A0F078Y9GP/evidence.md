# Review r2: #5353 slice-3 R review folds (reviewer-renata, Op 01M3SXTQVY5F52X9A0F078Y9GP)

Branch `issue-5353-r-followup` @ 8ad1a8d4. Scope: the commits after 7a18c247 (d101b641, 18ead7a3, 6d506eec, 6a79eb7a, 6bfa9218, 8ad1a8d4).

## Verdict: REQUEST-CHANGES (small folds)

The operator ruling is implemented faithfully:
- The retrospect auto-commit uses the STANDARD `commit_for_mission(kind=RETROSPECTIVE)`.
- The retrospect path has no remaining use of `MERGE_BOOKKEEPING`, `commit_merge_bookkeeping`, `commit_coord_seed_bookkeeping` or `safe_commit` (grep over `retrospect.py`, `agent_retrospect.py` and `retrospective/` returns 0 hits).
- The router's partition classifier is the only authority.
- A protected target gives a warning and no commit.

Three folds remain on the shared router change and on its operator-facing text.

## Findings (ranked)

1. **MEDIUM: d101b641 makes the shared router commit a coord-resident status log outside `feature_status_lock`. A concurrent status transition can then lose its row.**
   - The coord arm of the transactional status shell (`coordination/status_transition.py::_emit_on_coord_then_commit`) holds L1 across emit → `safe_commit`.
   - `commit_for_mission` now commits a coord-worktree `status.events.jsonl` with no lock. Its callers are retrospect, and `spec-commit` given that path.
   - Probe (`scratchpad/r2/probe_race.py`, real `build_coord_mission`):
     1. Append a row, as the transition's emit does.
     2. Call `commit_for_mission(..., kind=RETROSPECTIVE)` on the coord log. Result: `committed kitty/mission-terminus-01M5001A`.
     3. Call `_commit_status_artifacts_to_coord`. It raises `SafeCommitStagedTreeUnchanged`.
   - In `_emit_on_coord_then_commit` that exception leaves `committed=False`, so the `finally` truncates the row from the working tree while the coordination HEAD carries it. The transition also reports failure for an event that did land.
   - This was not reachable through the router on origin/main, which dropped coord-resident status logs. The pre-fold `commit_coord_seed_bookkeeping` route had the same race.
   - Fix, either one:
     - (a) In `_stage_artifacts_in_coord_worktree`/`_commit_partition_group`, take `feature_status_lock(repo_root, <coord feature dir name>, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS)` around the commit whenever a coord-resident STATUS_STATE path is committed.
     - (b) Have retrospect hold the same L1 across `emit_captured` and the auto-commit, as the status shell does.
   - If deferred, file an issue and cite it in the PR.
   - Blast radius otherwise:
     - I grepped every `commit_for_mission` caller: report_transaction, mission_setup_plan x3, mission_finalize x2, mission_record_analysis, spec_commit_cmd, write_seam, orchestrator_api, acceptance x2, and the `RealCoordCommitRouter` families (mark_status dead shim, map_requirements, review/cycle).
     - None of them hands the router a coord-resident STATUS_STATE path except retrospect, and `spec-commit` when the operator names one explicitly. So there is no new double commit.
     - The transactional shell commits through `safe_commit` directly, not through the router.
     - `ProjectionTeardownGate` is unaffected in kind. A retrospect commit that lands on the coordination branch inside the projection window makes the CAS gate fail closed, which is the intended behaviour.
2. **MEDIUM (coverage): the router's own test module does not pin sibling or nested rejection for a status log.**
   - My break B2 committed ANY `status.events.jsonl` under `.worktrees/`, including a sibling Mission's coord worktree. It **survived** 60 tests: test_commit_router.py, the partition, placement and fail_loud tests, test_finalize_coord_staging.py, test_finalize_clobber_e2e.py and the coord retrospect suite.
   - B3 (sibling accepted) and B7 (nested accepted) are caught, but only by `tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py` using `tasks.md`, not by `tests/coordination/test_commit_router.py`.
   - Fold: in `test_commit_router.py`, extend `test_coord_staging_keeps_a_status_log_already_in_the_coord_worktree`, or add a parametrised sibling, with two cases:
     - a sibling coord worktree's `status.events.jsonl`, e.g. `.worktrees/002-other-coord/...`;
     - a nested `.worktrees/001-demo-coord/.worktrees/x/.../status.events.jsonl`.
   - Assert both are excluded.
   - Optionally add a symlinked repo_root case (`_is_directly_in_worktree` resolves both sides, which is correct, but nothing pins it).
3. **LOW-MEDIUM: the protected-target warning recommends the wrong branch on a coord Mission** (`retrospect.py::_warn_protected_target_refused`; the changelog repeats it).
   - "commit it from a non-protected branch (for example the mission branch)". On a coord Mission, which is the realistic protected-`main` case (a create on the primary branch defaults to coord), the only `kitty/mission-<slug>-<mid8>` branch IS the coordination branch.
   - Following the hint lands the PRIMARY-partition `retrospective.yaml` on the coordination branch: the coord residue the partition forbids.
   - Fold: say "a feature branch" and drop the mission-branch example, or name it only when the topology is coordless. Update the changelog sentence to match.
   - On consistency with the ruling: the event log still reaching the coordination branch is NOT a widening. The coordination branch is not protected, the commit is STANDARD-capability, and B6 shows `safe_commit`'s own STANDARD guard still refuses `main` even with a permissive policy stub.
4. **NIT: `ruff format --check` flags three touched files:** `retrospect.py`, `commit_router.py` and `test_agent_retrospect_synthesize.py`. All three are in the `[tool.ruff.format].exclude` ratchet (pyproject 542/562/1163), so no gate trips. Pre-existing; not a fold.

## Checked OK
- The protection policy comes from `ProtectionPolicy.resolve(repo_root)`, the same boundary resolve used by spec_commit_cmd, report_transaction, record-analysis, orchestrator_api and review/cycle. The router mission-scopes it internally (`_mission_scoped` → `for_mission`). `_refused_on_protected_target` uses `resolve_for_mission`, which is consistent with that scoping.
- The multi-group result (`_merge_group_results`) returns the caller-partition group (the PRIMARY record), so the protected refusal is what the retrospect CLI sees. A coord-group `error` takes priority and falls to "auto-commit failed".
- Commit order: fixes come before the style, test and changelog commits.
- Trailers present.
- `git diff origin/main...HEAD -- src/` is only the intended product code.
- `agent_retrospect.py` was dropped from the format ratchet in the same commit that reformatted it.
- mypy: 0 issues on 3 files. ruff check and C901: clean.
- No new noqa or type-ignore.
- Changelog has Before/After. Terminology: Mission.
- The RETIRE of `test_auto_commit_failure_is_nonfatal` is justified (see R1).

## Planted breaks (every one reverted; `git checkout -- src/`, `git status --porcelain` empty after each)
| id | mutation | target | result |
|---|---|---|---|
| B1 (impl F1) | router at `d101b641^` | test_commit_router.py + coord retrospect | RED 5: `assert [] == [PosixPath('/...vents.jsonl')]`; coord `assert '' == 'chore(retros...inus-01M5001A'`, `assert 0 == 1` (RetrospectiveCaptured) |
| B2 (own, router) | `.worktrees` branch also keeps any `status.events.jsonl` (sibling Mission's coord log) | router + finalize staging + coord retrospect (60 tests) | **SURVIVED** (finding 2) |
| B3 (own, router) | `_is_directly_in_worktree` relative to `worktree.parent` (any coord worktree) | same | RED 1, outside the router module: `test_staging_skips_foreign_worktree_artifacts` `assert [PosixPath('/...BD/tasks.md')] == []` |
| B7 (own, router) | `_is_directly_in_worktree` returns True (nested accepted) | same | RED 1, outside the router module: `test_staging_skips_nested_worktree_artifacts` `assert [PosixPath('/...BD/tasks.md')] == []` |
| B4 (own) | `_uncommitted_target_files` drops the coord-residue filter | retrospect suites | RED: `assert 'status.events.jsonl' not in 'Warning: re...events.jsonl'` |
| B5 (impl F2) | `retrospect.py` at 7a18c247 (MERGE_BOOKKEEPING route) | retrospect suites | RED 5: `assert 'c93d7becd559...' == '051aa1d38a6f...'` (protected main moved) |
| B6 (own, policy) | router called with an always-unprotected policy stub | retrospect suites | RED 5: `assert "target branch 'main' is protected" in "Warning: retrospective auto-commit failed: safe_commit: refusing to commit to protected branch 'main' ..."` (the STANDARD safe_commit guard still refused main) |
| R1 (retire) | `_maybe_auto_commit` `except` swallows silently | replacement `test_create_warns_and_exits_zero_when_the_commit_router_raises` / kept `test_auto_commit_raises_is_nonfatal` | replacement RED `assert 'auto-commit failed: coordination worktree resolution failed' in ''`; kept test PASSED (blind) |

## Tests run (PYTHONPATH=worktree/src, repo .venv, -n 8 --dist loadfile)
Command: `pytest` over the following files. Result: **401 passed, 2 skipped**.
- tests/coordination/: test_commit_router.py, test_commit_router_fail_loud.py, test_commit_router_layering.py, test_coord_teardown_guard.py, test_projection_teardown.py
- tests/specify_cli/coordination/: test_commit_router_partition.py, test_commit_router_partition_authority.py, test_commit_router_placement.py, test_status_transition.py, test_status_transition_adoption.py, test_status_transition_degrade.py, test_teardown_seam_persist_before_destroy.py, test_teardown_single_seam_routing.py
- tests/specify_cli/cli/commands/agent/: test_finalize_coord_staging.py, test_finalize_clobber_e2e.py
- tests/integration/test_accept_matrix_coord_partition.py
- tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py
- tests/cli/commands/: test_retrospect_coord_autocommit.py, test_retrospect.py
- tests/cli/: test_agent_retrospect_synthesize.py, test_agent_retrospect_missing_record.py
- tests/architectural/: test_guard_capability_call_sites.py, test_layer_rules.py, test_ruff_format_exclude_ratchet.py

Other checks:
- mypy on the 3 src files: no issues.
- ruff check and `--select C901`: clean.
