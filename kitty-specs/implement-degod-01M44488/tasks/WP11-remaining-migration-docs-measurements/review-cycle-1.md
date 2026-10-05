---
affected_files: []
cycle_number: 1
mission_slug: implement-degod-01M44488
reproduction_command:
reviewed_at: '2026-10-05T06:05:25Z'
reviewer_agent: claude
wp_id: WP11
---

# WP11 review feedback (cycle 1)

Reviewer: reviewer-renata. Tactics applied: code-review-incremental, delete-the-assertion-not-the-test,
architectural-gate-non-vacuity (all plants were re-run by the reviewer and reverted).

Most of WP11 is good: the counter went from 68 to 43 (reproduced; object sites unchanged at 19, so
nothing was laundered), the characterization suite is unedited and green, every plant I re-ran went
red, and the docs and CHANGELOG are accurate. One FR-011 objective is unmet and was not reported, so
this is a reject.

## Blocking

1. **`tests/specify_cli/lanes/test_lane_base_honoring.py:251-289`: the remaining family patches were not migrated, and the report does not mention it.**
   - **What:** `_run_implement_via_seam` still patches five family string targets:
     - `implement.find_repo_root`;
     - `implement_phases.detect_feature_context`;
     - `implement_planning_commit._ensure_planning_artifacts_committed_git`;
     - `implement_phases._ensure_vcs_in_meta`;
     - `implement_claim.start_implementation_status`.

     These are 5 of the counter's 6 remaining string sites (`string_by_file`).
   - **Why:** the WP's FR-011 objective names this file explicitly: "the remaining patches in
     `test_lane_base_honoring.py` and `test_implement_base_flag.py`; any other file the counter's
     `string_by_file` still lists". The counter is under its ≤ 45 target, but meeting the number
     does not discharge a named objective, and the implementer's report does not mention the file.
   - **How:** rewrite `_run_implement_via_seam` on the characterization fixture (`init_repo` /
     `activate_repo` / `build_mission` / `implement_cli`), as you already did for
     `TestImplementBaseFlagIntegration`. Keep every existing assertion of the AC-1 base-honoring
     tests unchanged.
   - **Alternative:** if a patch truly cannot go (for example the status-surface isolation the
     comment at ~L272 describes), record in the activity log, per remaining site, why it must stay.
     The orchestrator then files a follow-up issue.
   - Do the same for `tests/specify_cli/cli/commands/test_implement_cores.py:584`
     (`implement_cores.subprocess.run`): migrate it, or record why it stays.

## Non-blocking (record or hand to the orchestrator; no code change required to approve)

2. **Follow-up issue needed (charter: pre-existing failure → GitHub issue).** I confirmed the
   implementer's finding empirically. I inserted `commit_planning_artifacts` into the N-claim loop
   of `test_sequential_n_lane_claims_write_zero_wp_file_bytes` and ran it as a temporary probe,
   since reverted. The second `auto_commit=False` claim is refused with this output:

   ```text
   Planning artifacts not committed: kitty-specs/demo-mission/status.events.jsonl
   ```

   The first claim's real status write leaves `status.events.jsonl` uncommitted. The old test
   passed only because `start_implementation_status` was mocked. Dropping the old
   "claim reaches allocation / no inter-allocation commit is ever needed" assertion was therefore
   honest, not a weakening, because the claim is false in reality. That contract now has no test,
   though, so the orchestrator must file it as an issue: a real product gap for `--no-auto-commit`
   on missions whose status lives on the primary partition.
3. **`docs/architecture/wp-runtime-state-eviction.md:80`, wording nit.** The page says
   "used as an event sidecar by `implement_claim.py::claim_policy_metadata`". But
   `claim_policy_metadata` is defined in `specify_cli.status` and only *called* in
   `implement_claim.py::_start_wp_implementation_status`. Suggested wording: "by
   `implement_claim.py::_start_wp_implementation_status` (via `status.claim_policy_metadata`)".
4. **`tests/cli/test_implement_bulk_edit_planning.py`.** The old `create_workspace.assert_called_once()` /
   `assert_not_called()` assertions became "the phase returns / raises". This is acceptable: the WP
   asked for phase-verdict tests, and the CLI smoke is the characterization refusal. The
   "proceeds to allocation" claim now rests on the phase order in `implement()`, not on an
   observation. Note it in the activity log.
5. **Quickstart §2 references a deleted file.** `tests/cli/commands/test_resolve_lanes_dir.py`
   was deleted in WP03 (`afd9cf7ba`). Running quickstart §2 verbatim errors with "no tests ran".
   Drop the path from quickstart.md, through the orchestrator.

## Verified OK

- Characterization: no diff since `8cbe74f94`, and green. `_implement_dispatch.py` has no diff in
  this WP.
- F-50: the dispatch map is used only for `allocate` in `test_status_emit_on_alloc_failure.py` (the
  characterization file has 17 sites, plus this one). The test reads the real `status.events.jsonl`.
  - Plant "emit planned→blocked on allocation failure" turned all 4 tests red.
  - Plant "drop `OrphanedPlanningCommitError` from the next-step tuple" turned the orphaned case red.
- vcs-lock tests: predicate→False turned the #2222 test red; predicate→True turned the
  non-lock-blocks test red.
- `test_birth_cutover.py`: with `allocate` and `record_claim` both planted to raise, the birth
  cutover and accept birth cutover tests (27 tests) stayed green. The removed patches were dead.
- N1/N2/allocate plants (`direct:` workspace_context, no-op `commit_planning_artifacts`, skipped
  `create_lane_workspace`): each turned its test red.
- `test_planning_commit` reload fix is legitimate:
  - at `7e5dc38fc`, `-n0 test_commit_router.py test_planning_commit.py` has 2 TestGuard failures;
  - at HEAD, 107 pass.
- `test_doctrine_asset` internal-pack reds: environment (worktree-relative). Identical 3 failures
  at base `7e5dc38fc` from a temporary worktree; 12/12 pass from the repository root checkout.
  Not caused by this mission.
- Gate files (quickstart §3, plus `test_commit_router_layering`, plus `test_commit_recipes`): 511
  passed, 1 failed. The only red is #5699 (`_commit_message.py`).
- Regression subset, plus touched files: 523 passed.
- Docs:
  - `test_spk_skill_pack.py` (reads the matrix): 7 passed.
  - `check_docs_freshness --ci`: errors=0.
  - `updated:` bumped.
  - Re-pointed symbols exist.
  - The CHANGELOG "2,304 → 438" matches merge-base `7c2dbd4eb` and HEAD, and the entry carries the
    #5232 sentence and no "feature" terminology.
- The format-exclude list only shrank (3 entries), and the ratchet is green.
- ruff check, ruff format, and C901 are clean on changed files. No src Python changed, so mypy is
  N/A.
- Commit trailers are correct, with no model identifiers.
