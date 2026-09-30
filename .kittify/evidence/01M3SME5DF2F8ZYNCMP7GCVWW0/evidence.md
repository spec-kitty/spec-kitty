# red-proofs-r (workstream R, #5353 slice-3 follow-ups)

Untracked. Every planted break reverted by restoring the saved fixed file (`cp` from scratchpad) or
`git checkout -- src/`; `git diff --stat src/` checked before each commit.

## Fix 1: retrospect auto-commit routes through the owning checkout (commit `fix(cli): route the retrospect auto-commit ...`)

Red-first through the pre-existing entry point (`spec-kitty retrospect create --json`, CliRunner) on a real coord
mission (`tests.terminus.conftest.build_coord_mission`, WP01 walked to `done` via `emit_status_transition` and
committed on the coord branch, `auto_commit: true`).

- Test: `tests/cli/commands/test_retrospect_coord_autocommit.py::test_create_commits_the_record_on_the_target_branch_of_a_coord_mission`
- Pre-fix src (`git checkout -- src/specify_cli/cli/commands/retrospect.py`, i.e. origin/main): **FAILED**
  `assert 'auto-commit failed' not in 'Warning: retrospective auto-commit failed: The following paths are ignored by one of your .gitignore files: .worktrees ...'`
- Fixed src: PASSED.

## Fix 3: "nothing to commit" is silent

- Test: `tests/cli/commands/test_retrospect.py::TestMaybeAutoCommit::test_auto_commit_of_already_committed_files_is_silent`
- Planted break: `retrospect.py:293` `contextlib.suppress(SafeCommitStagedTreeUnchanged)` -> `contextlib.suppress(ZeroDivisionError)`.
  Old tests: `test_auto_commit_enabled_commits_exactly_the_files_with_the_message` PASSED (did not see it).
  New test: **FAILED** `AssertionError: assert 'Warning: ret...ective.yaml\n' == ''` (`+ Warning: retrospective auto-commit failed: safe_commit: nothing to commit for destination_ref='main' (empty changeset). ...`).
- Pre-fix behaviour (origin/main) for the same situation: `git commit` exits 1 "nothing to commit" and the #5430
  warning fires (recorded as review nit 2 in 01M3RGWHEWXFNW77BVVVHT567C).
- Real failures keep the warning: `TestAutoCommitFailureIsSurfaced::…[commit-rejected-by-hook]` and
  `[add-blocked-by-index-lock]` stay green on the fixed src.

### Assertion changes in the #5430 tests (not weakened in contract)
- `_lock_the_index` fragment `index.lock` -> `failed to stage requested files`: the commit now goes through
  `safe_commit`, which reports a refused `git add` as its own staging error and does not carry git's stderr through.
  The warning still fires and names the file. Deferred upstream gap: `safe_commit` should carry git's stderr
  (`src/specify_cli/git/commit_helpers.py:1569`).
- `test_auto_commit_of_file_outside_repo_root_warns_and_commits_nothing`: `outside repository` -> `refusing to mutate index`
  (the old `relative_to` fallback no longer exists; the seam refuses the path).

## Fix 2: RetrospectiveCaptured is written where the auto-commit reads it (commit `fix(cli): write RetrospectiveCaptured ...`)

- Test: `tests/cli/commands/test_retrospect_coord_autocommit.py::test_create_writes_and_commits_the_captured_event_on_the_coordination_branch`
- Pre-fix src (fix-1 commit; `git checkout -- src/`): **FAILED**
  `assert 0 == 1` where `0 = ['', '', '', '', '', ''].count('RetrospectiveCaptured')` (the coord branch log carries only
  the WP lane events; the captured row went to the primary copy).
- Fixed src: PASSED.
- Design note: `emit_captured` / `emit_capture_failed` / `emit_skipped` gain `event_log_dir` (default `None` keeps the
  durable primary home, so the post-merge terminus and runtime bridge are byte-identical). The retrospect CLI passes
  `_canonical_events_path(...)` (`resolve_status_surface`), the same path it then commits.
- Blast radius after fix 2: test_retrospect*.py, tests/retrospective, tests/specify_cli/retrospective,
  tests/specify_cli/post_merge, tests/runtime/test_bridge_retrospective.py, tests/integration/retrospective,
  tests/integration/test_issue_4765_close_guard.py -> 750 passed, 8 skipped.

## Fix 4: `agent retrospect synthesize --proposal-id` refuses non-accepted ids (commit `fix(cli): refuse non-accepted ids ...`)

Red-first through the CLI (`CliRunner`, `agent retrospect synthesize`) on a real record written by `write_record`
(accepted / pending / rejected `add_glossary_term` proposals, real evidence event), nothing patched.

- Pre-fix src (`git checkout -- src/`): **10 FAILED, 1 passed** (`-k "proposal_id or proposal-id"`):
  - `test_synthesize_refuses_a_proposal_id_that_is_not_accepted_json[apply-pending]`: `assert 0 == 1`, and the envelope
    shows `"applied": [{"proposal_id": "…M2", "target_urn": "glossary:term:pending-term", …}]` (a pending proposal
    was APPLIED by id). Same for `[apply-rejected]` (rejected-term applied), `[apply-accepted-plus-pending]`,
    `[apply-unknown]` and all four `[dry-run-*]` cases (exit 0, pending/rejected planned).
  - `test_synthesize_refuses_a_rejected_proposal_id_with_a_rich_error`: `assert 0 == 1`.
  - `test_synthesize_help_says_proposal_id_must_name_accepted_proposals`: `'which must be accepted' in "Usage: …"` false.
  - `test_synthesize_proposal_id_narrows_the_accepted_batch`: passed pre-fix (narrowing already worked; it guards
    that the fix keeps narrowing).
- Planted break on the fixed src: `agent_retrospect.py:650` `set(proposal_id)` -> `{p.id for p in all_proposals if
  p.state.status == "accepted"}` (ignore the narrowing). `test_synthesize_apply_applies_only_accepted_proposals`
  PASSED (blind to it); `test_synthesize_proposal_id_narrows_the_accepted_batch` **FAILED**
  `assert ['01KQ6YEGA0B...D3E4F5G6H7M4'] == ['01KQ6YEGA0B1C2D3E4F5G6H7M4']` (both accepted applied).
- Fixed src: 39 passed (`test_agent_retrospect_synthesize.py` + `test_agent_retrospect_missing_record.py`).
- Exit code chosen: 1 (the command's "input refused before any work" code, as for an unresolvable mission handle);
  documented in `--help` and the Step 7 exit-code comment. `--json`: stdout empty, stderr
  `{"error": "proposal_not_accepted", "detail": …, "proposal_ids": […], "statuses": {id: status}}`, matching the
  `record_malformed` / `io_error` stderr payloads.

## D1: harness rewrite of tests/cli/commands/test_retrospect.py (RETIRE x20 + fold x1)

New guards: `TestCreateHarness` / `TestBackfillHarness` (21 test ids incl. params) on the real `retrospect_project`
fixture. Each planted break was run against the OLD test (still in the file) and its NEW replacement BEFORE the old
test was deleted (scratchpad driver `breaks.py` restores the src file after each run; src diff empty afterwards).
New guards without any break: 21 passed.

| # | where | mutation (old -> new) | old test | old | new test | new | new failing assertion |
|---|---|---|---|---|---|---|---|
| 1 | `src/specify_cli/cli/commands/retrospect.py:534` | `"evidence_refs": len(persisted.evidence_refs),` -> `"evidence_refs": len(persisted.proposals),` | `TestCreateCommand::test_create_success_json` | PASSED | `TestCreateHarness::test_create_json_reports_writes_emits_and_commits_the_record` | **FAILED** | `E   AssertionError: assert {'counts': {'...mission', ...} == {'counts': {'...mission', ...}` |
| 2 | `src/specify_cli/cli/commands/retrospect.py:434` | `else: ⏎         write_mode = "error"` -> `else: ⏎         write_mode = "overwrite"` | `TestCreateCommand::test_create_record_exists_error_json` | PASSED | `TestCreateHarness::test_create_refuses_to_replace_an_existing_record[json]` | **FAILED** | `E   AssertionError: {"result": "success", "mission_id": "01KS049J4V9CSWBKJHTY2FB69H", "mission_slug": "test-completed-mission", "record_path": "/tmp/spec-kitty-pytest-tmp/run-29525/test_create_refuses_to_replace0/repo/ki` |
| 3 | `src/specify_cli/retrospective/writer.py:578` | `elif mode == "overwrite": ⏎         final_record = record` -> `elif mode == "overwrite": ⏎         final_record = _merge_gen_records(_dict_to_gen_record(YA` | `TestCreateCommand::test_create_overwrite_flag` | PASSED | `TestCreateHarness::test_create_overwrite_replaces_the_existing_record` | **FAILED** | `E   assert 2 == 1` |
| 4 | `src/specify_cli/retrospective/writer.py:606` | `final_record = _merge_gen_records(existing, record)` -> `final_record = record` | `TestCreateCommand::test_create_update_flag` | PASSED | `TestCreateHarness::test_create_update_merges_into_the_existing_record` | **FAILED** | `E   AssertionError: assert ['research.md absent'] == ['lane bounce...ch.md absent']` |
| 5 | `src/specify_cli/cli/commands/retrospect.py:564` | `f"gaps={counts['gaps']} proposals` -> `f"gaps={counts['not_helpful']} proposals` | `TestCreateCommand::test_create_success_rich_output` | PASSED | `TestCreateHarness::test_create_without_json_renders_the_authored_panel` | **FAILED** | `E   AssertionError: assert 'helped=0 not_helpful=0 gaps=1 proposals=0' in '╭───────────────────────────────────────────────────────── spec-kitty retrospect create ─────────────────────────────...─────────────────────────` |
| 6 | `src/specify_cli/cli/commands/agent_retrospect.py:314` | `kind="synthesize_fabricate", ⏎             invoked_at=now,` -> `kind="explicit_create", ⏎             invoked_at=now,` | `TestSynthesizeFabricateEmpty::test_fabricate_empty_creates_record_when_missing` | PASSED | `TestCreateHarness::test_fabricate_empty_writes_and_reports_an_empty_record` | **FAILED** | `E   AssertionError: assert 'explicit_create' == 'synthesize_fabricate'` |
| 7 | `src/specify_cli/cli/commands/retrospect.py:412` | `policy, source_map = resolve_policy(repo_root) ⏎     except PolicyResolutionError` -> `policy, source_map = resolve_policy(repo_root.parent) ⏎     except PolicyResolutionError` | `TestCreateCmdErrorPaths::test_create_policy_resolution_error_json` | PASSED | `TestCreateHarness::test_create_blocks_on_a_malformed_retrospective_policy[json]` | **FAILED** | `E   AssertionError: {"result": "success", "mission_id": "01KS049J4V9CSWBKJHTY2FB69H", "mission_slug": "test-completed-mission", "record_path": "/tmp/spec-kitty-pytest-tmp/run-30390/test_create_blocks_on_a_malfor0/repo/ki` |
| 8 | `src/specify_cli/cli/commands/retrospect.py:412` | `policy, source_map = resolve_policy(repo_root) ⏎     except PolicyResolutionError` -> `policy, source_map = resolve_policy(repo_root.parent) ⏎     except PolicyResolutionError` | `TestCreateCmdErrorPaths::test_create_policy_resolution_error_non_json` | PASSED | `TestCreateHarness::test_create_blocks_on_a_malformed_retrospective_policy[rich]` | **FAILED** | `E   AssertionError: ╭───────────────────────────────────────────────────────── spec-kitty retrospect create ─────────────────────────────────────────────────────────╮` |
| 9 | `src/specify_cli/cli/commands/retrospect.py:449` | `Could not find mission artifacts: {exc}` -> `Could not find mission artifacts.` | `TestCreateCmdErrorPaths::test_create_generator_file_not_found` | PASSED | `TestCreateHarness::test_create_reports_a_generator_failure_and_writes_nothing[missing-artifacts]` | **FAILED** | `E   AssertionError: assert 'Error: Could...on artifacts.' == 'Error: Could...s.md vanished'` |
| 10 | `src/specify_cli/cli/commands/retrospect.py:452` | `Generator failed: {exc}` -> `Generator failed` | `TestCreateCmdErrorPaths::test_create_generator_generic_exception` | PASSED | `TestCreateHarness::test_create_reports_a_generator_failure_and_writes_nothing[generator-crash]` | **FAILED** | `E   AssertionError: assert 'Error: Generator failed' == 'Error: Gener...rator crashed'` |
| 11 | `src/specify_cli/cli/commands/retrospect.py:494` | `Failed to write record: {exc}` -> `Failed to write record` | `TestCreateCmdErrorPaths::test_create_write_gen_record_generic_exception` | PASSED | `TestCreateHarness::test_create_reports_a_record_write_failure` | **FAILED** | `E   AssertionError: assert False` |
| 12 | `src/specify_cli/cli/commands/retrospect.py:489` | `f"A retrospective record already exists at {exc.path}. "` -> `"A retrospective record already exists. "` | `TestCreateCmdErrorPaths::test_create_record_exists_non_json` | PASSED | `TestCreateHarness::test_create_refuses_to_replace_an_existing_record[rich]` | **FAILED** | `E   AssertionError: assert False` |
| 13 | `src/specify_cli/cli/commands/retrospect.py:855` | `kind="backfill", ⏎                     invoked_at` -> `kind="explicit_create", ⏎                     invoked_at` | `TestBackfillDiscovery::test_backfill_process_candidate_real_run_success` | PASSED | `TestBackfillHarness::test_backfill_authors_commits_and_reports_the_record` | **FAILED** | `E   AssertionError: assert 'explicit_create' == 'backfill'` |
| 14 | `src/specify_cli/cli/commands/retrospect.py:891` | `"missing": [str(exc)],` -> `"missing": [],` | `TestBackfillDiscovery::test_backfill_process_candidate_file_not_found` | PASSED | `TestBackfillHarness::test_backfill_reports_a_mission_without_artifacts[no-emit]` | **FAILED** | `E   IndexError: list index out of range` |
| 15 | `src/specify_cli/cli/commands/retrospect.py:916` | `"remediation_hint": str(exc),` -> `"remediation_hint": None,` | `TestBackfillDiscovery::test_backfill_process_candidate_generic_exception` | PASSED | `TestBackfillHarness::test_backfill_reports_a_generator_crash[no-emit]` | **FAILED** | `E   AssertionError: assert None == 'crash'` |
| 16 | `src/specify_cli/cli/commands/retrospect.py:906` | `missing_artifacts=[str(exc)], ⏎                         actor=_cli_actor(), ⏎                 ` -> `missing_artifacts=[str(exc)], ⏎                         actor=_cli_actor(), ⏎                 ` | `TestBackfillDiscovery::test_backfill_emit_failures_flag` | PASSED | `TestBackfillHarness::test_backfill_reports_a_mission_without_artifacts[emit-failures]` | **FAILED** | `E   ValueError: not enough values to unpack (expected 1, got 0)` |
| 17 | `src/specify_cli/cli/commands/retrospect.py:985` | `f"Created: {len(created)} \| "` -> `f"Created: {len(skipped)} \| "` | `TestBackfillDiscovery::test_backfill_no_json_rich_output` | PASSED | `TestBackfillHarness::test_backfill_without_json_renders_the_summary_panel` | **FAILED** | `E   AssertionError: assert 'Scanned: 1 \| Created: 1 \| Skipped: 0 \| Failed: 0' in '╭───────── spec-kitty retrospect backfill ─────────╮ │ Backfill complete │ │ │ │ Window: 2026-04-02 to 2026-05-02 │ │ Scanned: 1 \| Created` |
| 18 | `src/specify_cli/cli/commands/retrospect.py:998` | `f"{f_entry['failure_category']} — {f_entry.get('remediation_hint', '')}"` -> `f"{f_entry['failure_category']}"` | `TestBackfillDiscovery::test_backfill_no_json_with_failures_shows_failure_list` | PASSED | `TestBackfillHarness::test_backfill_without_json_lists_the_failures` | **FAILED** | `E   AssertionError: assert 'Failures (1)...tor_exception' == 'Failures (1)...ption — crash'` |
| 19 | `src/specify_cli/cli/commands/retrospect.py:879` | `"reason": "already_exists", ⏎                 "record_path": str(exc.path),` -> `"reason": "already_exists",` | `TestSummaryCmdExtended::test_backfill_process_candidate_record_exists_error` | PASSED | `TestBackfillHarness::test_backfill_skips_a_record_that_appeared_after_the_prescreen` | **FAILED** | `E   AssertionError: assert [{'mission_id...eady_exists'}] == [{'mission_id...ective.yaml'}]` |
| 20 | `src/specify_cli/cli/commands/retrospect.py:925` | `failure_category="generator_exception", ⏎                         failure_message` -> `failure_category="other", ⏎                         failure_message` | `TestSummaryCmdExtended::test_backfill_generic_exception_with_emit_failures` | PASSED | `TestBackfillHarness::test_backfill_reports_a_generator_crash[emit-failures]` | **FAILED** | `E   AssertionError: assert 'other' == 'generator_exception'` |
| 21 | `src/specify_cli/cli/commands/agent_retrospect.py:192` | `"status": status, ⏎         "outcome": outcome,` -> `"status": status, ⏎         "outcome": "synthesized",` | `test_existing_record_json_includes_synthesized_outcome` | FAILED | `TestCreateHarness::test_synthesize_reads_the_created_record_and_reports_its_outcome` | **FAILED** | `E   AssertionError: assert 'synthesized' == 'retrospective_synthesized'` |

Break 21 is the fold of `test_agent_retrospect_missing_record.py::test_existing_record_json_includes_synthesized_outcome`
(a RETIRE): both go red; the replacement is `TestCreateHarness::test_synthesize_reads_the_created_record_and_reports_its_outcome`
on a real generator-shaped record instead of a MagicMock record + stubbed apply.

Injected faults kept (no real fixture reaches them): generator FileNotFoundError on create (the handle resolver rejects an
unreadable mission first), generator RuntimeError (create and backfill), writer RecordExistsError race in backfill.
Real faults: malformed `.kittify/config.yaml` retrospective block (PolicyResolutionError), seeded record
(RecordExistsError), a directory squatting on the record path (writer failure), a registered mission without
kitty-specs (backfill FileNotFoundError).
