# Independent review: #5353 slice 3, `tests/cli` test-quality pass

Reviewer: reviewer-renata (Op 01M3RGWHEWXFNW77BVVVHT567C), Opus 5.5, isolated worktree, detached at
`issue-5353-cli-test-quality` = `582498df0`. Diff under review: `a091fc489..HEAD` (15 commits: 1 `fix(cli)`, 12 `test(cli)`,
1 format-ratchet `test(cli)`, 1 `op(...)` record). Env: `uv sync --frozen --all-extras`.

## Verdict: APPROVE WITH NITS

The one product fix is correct and was red first. Every re-run FIX break turns the new test red while the old test stays
green. Every re-run RETIRE guard goes red on its break. No new skips or xfails. No new mocks of CLI collaborators. Lint,
format, mypy and complexity are clean. The nits below are not blocking.

## Planted breaks I re-ran

Each break was planted in `src/`, then reverted with `git checkout -- src/ tests/`. `git status --porcelain` was empty after
every revert and is empty at the end. To run an "old" test, I wrote the test file from `a091fc489` into place temporarily
(`git show a091fc489:<file> > <file>`) and reverted it the same way.

### Product fix, red-first

| src | mutation | test | result |
|---|---|---|---|
| `cli/commands/retrospect.py` | whole file replaced by the `a091fc489` version | `TestAutoCommitFailureIsSurfaced::test_create_warns_on_stderr_and_keeps_json_parseable_when_auto_commit_fails[commit-rejected-by-hook, add-blocked-by-index-lock]` and `test_auto_commit_of_file_outside_repo_root_warns_and_commits_nothing` | **RED** ×3, for the right reason: `assert 'auto-commit failed' in ''`. The `_auto_commit_failure_detail` cases fail with ImportError, as expected. |

### FIX breaks: 7 (5 from Bundle B, plus implement from Bundle A/B)

| # | src path:line | mutation | new test | new | old test @a091fc489 | old |
|---|---|---|---|---|---|---|
| F1 | `cli/commands/consolidate.py:691` | `strategy=resolved_strategy` → `MergeStrategy.MERGE` | `test_consolidate_strategy_decides_whether_lane_history_reaches_the_target` | **RED** 3/5 (default-is-squash, flag-squash, flag-beats-config); the merge cases pass, as expected | `TestStrategyFlagFlowsThrough` ×2 + `TestLaneToMissionUsesMergeCommit` | GREEN (3 passed) |
| F2 | `cli/commands/agent_retrospect.py:618` | drop `if p.state.status == "accepted"` | `test_synthesize_default_is_a_dry_run…`, `test_synthesize_apply_applies_only_accepted_proposals` | **RED** 2/2 | whole old file | GREEN (25 passed) |
| F3 | `cli/commands/_auth_login.py:210` | `saas_base_url=saas_url` → a hard-coded other URL | `test_missing_env_uses_configured_sync_server_url`, `test_warns_on_retired_first_party_target_without_rejecting`, `test_force_mints_fresh_credentials_on_mismatch` | **RED** 3/3 | whole old file | GREEN (30 passed) |
| F4 | `cli/commands/_auth_login.py:239` | `tm.set_session(session)` → `pass` | same 3 | **RED** 3/3 | whole old file | GREEN (30 passed) |
| F5 | `migration/mission_state.py:402` | `"quarantine_root_path": self.quarantine_root_path` → `None` | `TestFixModeCharacterization::test_fix_names_audit_trail_and_quarantine_with_json_parity` | **RED** | whole old file | GREEN (22 passed) |
| F6 | `cli/commands/events.py:150` | after `log_path = …`, add `(resolved.feature_dir / "status.json").touch()`. This is my own variant: a non-`Path.open` write route, different from S's builtin-`open` append. | `test_events_tail_leaves_mission_tree_byte_identical_on_every_code_path` | **RED** | whole old file (Path.open spy) | GREEN (10 passed). The old spy was blind to it. |
| F7 | `cli/commands/implement.py:1623` | `_raise_base_ref_unresolved(base)` → `return None, lanes_manifest` | `test_implement_base_flag_invalid_ref_fails_clearly` | **RED** | old `-k invalid_ref` | GREEN (3 passed) |

### RETIRE guards: 5 (4 planted together at distinct sites, plus 1 separately)

| # | src path:line | mutation | guard | guard | retired test (old) |
|---|---|---|---|---|---|
| R1 | `cli/commands/charter/interview.py:414` | `write_interview_answers(...)` → `pass` | `tests/agent/cli/commands/test_charter_cli.py::test_interview_defaults_writes_answers` | **RED** | `test_interview_defaults_exits_zero_and_writes_answers`, `test_interview_defaults_json_output`: GREEN (blind), so retiring them is justified |
| R2 | `consolidation/done_bookkeeping.py:303` (`_mark_wp_merged_done`) | early `return` | `test_merge_status_commit.py::TestRealMergeCommitsBookkeeping::test_status_pair_with_done_event_is_committed_on_target` | **RED** ("merged WPs did not reach done") | n/a |
| R3 | `cli/commands/_auth_logout.py:87` | `raise typer.Exit(code=1)` → `return` | `test_auth_logout.py::TestAuthLogoutCommand::test_logout_storage_delete_failure_propagates` | **RED** | n/a |
| R4 | `cli/commands/doctrine.py:1118` | `check_drg_root=True` → `False` | `test_doctrine_org_commands.py::test_doctrine_org_validate_catches_drg_only_fragment_after_init` | **RED** | n/a |
| R5 | `cli/commands/implement.py:2171` | `base=effective_base` → `base=None` | `tests/specify_cli/lanes/test_lane_base_honoring.py::TestAC1SeamLevelRedFirst::test_explicit_base_replaces_coord_parent_on_no_dep_lane` | **RED** | This independently re-verifies the retirement that S committed before running its guard (process slip noted in red-proofs-S). |

## Checklist results

1. **Breaks**: see the tables above. All results match the implementers' red-proofs.
2. **Oracle quality**:
   - The new oracles are real outcomes: git HEAD/log/`show --name-only`/porcelain status, the `RetrospectiveCaptured` row read
     back from `status.events.jsonl`, on-disk glossary/provenance files, a byte-identical tree snapshot, `--json` stdout
     parsed, the product's own `RepairReport.to_json`, and branch reachability after a real `consolidate`.
   - No self-constructed oracle: in the doctor test, the JSON half now comes from the product's serializer, not from a
     test-authored payload.
   - New patches sit only at true edges:
     - auth login: `StateManager` (PKCE randomness), `CallbackServer` (socket), `BrowserLauncher.launch` (browser),
       `PublicHttpClient` (network), `SecureStorage.from_environment` (keyring → `FakeSecureStorage`);
     - retrospect: `_fanout_live_work_retrospective` (Zeitgeist fan-out).
   - Every other `patch(...)` in the diff is pre-existing and only reformatted, e.g. `resolve_mission_handle` in
     events-tail and the implement-context patches.
3. **Coverage**:
   - Every deleted test either has a replacement in the same file or a named guard that exists at HEAD. I checked this
     with `--collect-only` over the browser/headless e2e guards, `test_bundle_validate_cli::test_validate_fails_on_missing_tracked_file`
     (plus `test_validate_passes_on_compliant_bundle` for the exit-0 case), `test_charter_cli::{test_status_command_synced,
     test_context_bootstrap_then_compact}`, `test_context_org_chain::…test_pack_two_directive_present_in_cli_text_output`,
     and `test_lane_base_honoring::TestAC1…`.
   - The guards I re-ran are not vacuous (tables above).
   - `test_invalid_ref_error_message_contains_remediation` and `test_doctrine_org_init_from_bitbucket_ssh_at_ref` show
     as deleted and re-added in the diff; that is only reformatting.
4. **Skips/xfails**: none added. The `skip` matches in the diff are prose and test names. The 2 skips in the run are the
   pre-existing root-uid EACCES guards.
5. **Product fix** (`retrospect._maybe_auto_commit`):
   - It is non-fatal (exit 0, record written) and prints to stderr only via `_err_console`, the module's existing
     diagnostics seam. `--json` stdout still parses (the tests assert `json.loads(result.stdout)`).
   - The detail and paths are `rich.markup.escape`d, and the line is `soft_wrap`ped. Git's stderr/stdout lines are
     joined, and the fallback is ``cmd` exited N`.
   - C901 stays ≤15 (clean even at ≤10 for the three touched functions). mypy is clean.
   - The edit to `tests/specify_cli/retrospective/test_generator_traces_ingest.py` (`result.output` → `result.stdout`)
     is correct and minimal: the JSON contract lives on stdout, and Click's `result.output` now interleaves the
     legitimate stderr warning. Approved.
6. **History**:
   - `fix(cli)` (`beef45491`) comes first and holds only `retrospect.py`, its red-first tests, and the one-line
     ingest-test edit.
   - Trailers match authorship: Opus 5.5 on O's commits, the orchestrator's `b8dd581a3` and the op record; Sonnet 5 on
     S's 7 commits. All 15 carry the `Claude-Session:` line.
   - No `red-proofs-*`, `work-evidence/` or `test_zz_*` probe file is in the diff, and no planted break was committed.
7. **Lint**: see below. The `ruff.toml` per-file-ignore shrink and the removal of 5 files from the `pyproject.toml`
   format-exclude are shrink-only, and the ratchet tests pass.
8. **Touched test files**: see below.

## Findings

1. **Nit, follow-up, outside `tests/cli`:**
   - `tests/integration/test_implement_review_retrospect_smoke.py:171` parses `json.loads(result.output)` from a
     `retrospect ... --json` CliRunner call.
   - It passes today (5 passed) because auto-commit succeeds there. But it is now latently fragile in the same way the
     ingest test was: any auto-commit failure puts the new warning on stderr and breaks the parse.
   - Proposed edit: change line 171 to `payload = json.loads(result.stdout)`. Fold it in or file it with the D1 harness
     follow-up.
2. **Nit, product residual, already acknowledged in red-proofs-O:**
   - The warning now also fires for (a) `git commit` refusing with "nothing to commit" and (b) any non-git project where
     `auto_commit` is on ("not a git repository").
   - Both are honest, but (a) may be noise.
   - Optional follow-up edit in `src/specify_cli/cli/commands/retrospect.py::_maybe_auto_commit`: before
     `git commit`, run `git diff --cached --quiet -- <rel_files>` and return silently when it exits 0. Keep the warning
     for real failures.
   - Not required for this PR. Ruling 1 asked only for "never silent".
3. **Nit, deferred-hazard dependency:**
   - The retirement of `test_headless_dispatches_to_device_flow` relies on
     `tests/auth/integration/test_headless_login_e2e.py::…test_full_device_flow_happy_path`.
   - That guard only goes red after a ~301 s callback timeout (P8).
   - The guard is valid, but make sure the P8 follow-up issue is filed before or with this PR, so the guard does not
     rot into a CI-timeout flake.
4. **Nit, oracle scope note, no action:**
   - The events-tail snapshot oracle cannot see an open-for-append that writes zero bytes, which the old `Path.open`
     spy did catch.
   - That is not a state change, and the new oracle catches strictly more real write routes (touch/`os.open`/replace/
     temp files; F6 shows the old spy was blind to one). This is the right trade.
5. **Nit, process, no action:**
   - S committed the implement-base retirement before running its guard (disclosed in red-proofs-S).
   - I re-verified that guard independently (R5, RED), so the retirement stands.
6. **Nit, cosmetic:**
   - `test_agent_retrospect_synthesize.py` `_glossary_proposal` uses a hand-rolled `definition_hash="sha256:feedc0de"`.
   - It does not affect the accepted-only oracle.
   - If this file is touched again, derive the hash from the definition with the production hasher (directive 041,
     production-shaped data).

No blocking findings.

## Commands and counts

- Touched test files (17, named only):
  `uv run --frozen pytest <17 files from git diff --name-only a091fc489..HEAD -- tests> -q -n auto --dist loadfile`
  → **306 passed, 2 skipped** (the pre-existing root-uid EACCES guards) in 431 s.
- Blast radius of the warning:
  `pytest tests/architectural/test_no_read_side_bypass.py tests/architectural/test_json_contract_enumeration.py tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py tests/retrospective/test_record_committable_1771.py -n auto --dist loadfile`
  → 171 passed.
- `pytest tests/integration/test_implement_review_retrospect_smoke.py tests/cli/test_agent_retrospect_missing_record.py`
  → 5 passed.
- `uv run --frozen ruff check <18 touched .py>` → All checks passed.
- `uv run --frozen ruff format --check .` → 2796 files already formatted.
- `uv run --frozen mypy src/specify_cli/cli/commands/retrospect.py` → Success: no issues found in 1 source file.
- `ruff check --select C901 --config lint.mccabe.max-complexity=15` over `tests/cli/`, the ingest test and
  `retrospect.py` → clean. At ≤10, none of `_maybe_auto_commit`/`_auto_commit_failure_detail`/`_warn_auto_commit_failed`
  is flagged.
- `pytest tests/architectural/test_ruff_pytest_style_baseline.py tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_cli_console_single_seam.py`
  → 17 passed.
- Final `git status --porcelain` in the review worktree → empty.

## Orchestrator dispositions (2026-09-30)

| Nit | Disposition |
|---|---|
| 1 smoke test parses `result.output` | **Folded** in the final `test(cli)` commit (`json.loads(result.stdout)`); 25 passed. |
| 2 warning on "nothing to commit" / non-git | **Deferred** (PR Deferred): honest today; optional follow-up to skip when nothing is staged. |
| 3 headless-login guard 301 s timeout (P8) | **Deferred** (PR Deferred); per operator, no new issue filed. |
| 4 events-tail snapshot blind to zero-byte open-for-append | **Declined**: catches strictly more real writes than the old spy; a zero-byte open changes no state. |
| 5 S's commit-before-guard slip | **No action**: reviewer independently re-verified the guard (R5). |
| 6 `sha256:feedc0de` placeholder | **Folded**: 64-hex digest literal (TID251 bans hashlib in tests). |
