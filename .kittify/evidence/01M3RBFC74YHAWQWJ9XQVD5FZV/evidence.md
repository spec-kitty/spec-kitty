# red-proofs-O — Implementer O, #5353 slice 3 (`tests/cli`)

Branch `bundle-o-cli` off `issue-5353-cli-test-quality` (a091fc489). Env: `uv sync --frozen --all-extras`.
UNTRACKED — never committed.

## Ruling 1 — `retrospect._maybe_auto_commit` silent failure (product fix, red-first)

### Reproduction (scratch, real git, real `retrospect create --json`, only the Zeitgeist fan-out patched)
- Plain repo, auto_commit on: record committed (`chore(retrospective): author retrospective for …`). Baseline OK.
- Same, with a rejecting `pre-commit` hook: exit 0, JSON `result: success`, **stderr empty**, `git log` = only `init`,
  `git status` = `A retrospective.yaml`, `M status.events.jsonl` (staged, never committed). Silent.

### Red-first test (pre-existing entry point: `retrospect create` via CliRunner, real tmp git repo)
`tests/cli/commands/test_retrospect.py::TestAutoCommitFailureIsSurfaced::test_create_warns_on_stderr_and_keeps_json_parseable_when_auto_commit_fails`
params: `commit-rejected-by-hook` (pre-commit exits 1), `add-blocked-by-index-lock` (held `.git/index.lock`).
Oracle: exit 0 + stdout JSON parses with `result: success` + record on disk + HEAD unchanged + stderr contains
`auto-commit failed`, git's own error fragment, and `retrospective.yaml`.

- On base (no src change): `uv run --frozen pytest tests/cli/commands/test_retrospect.py -q -k TestAutoCommitFailureIsSurfaced`
  → **2 failed** (`AssertionError: assert 'auto-commit failed' in ''`) — red for the right reason (stderr empty).

- Fix applied (`_maybe_auto_commit` → `_warn_auto_commit_failed` / `_auto_commit_failure_detail`, `_err_console`
  yellow `Warning:` line, `soft_wrap=True`, rich-escaped; stderr only, so `--json` stdout stays parseable; this
  module's existing convention for diagnostics is `_err_console`).
  Same command → **7 passed** (2 CLI params + 5 pure `_auto_commit_failure_detail` cases for Sonar new-code coverage).
- Blast radius of the warning: `tests/specify_cli/retrospective/test_generator_traces_ingest.py` (outside tests/cli,
  unowned) parsed `--json` from CliRunner's merged `result.output`; its non-git tmp project now correctly gets the
  warning on stderr → 4 JSONDecodeError. Minimal fix: parse `result.stdout` (the JSON contract's channel). 4 passed.
  Other invokers checked: `test_no_read_side_bypass.py`, `test_lazy_command_module_imports.py`,
  `test_retrospect_doctor_surface_4090.py`, `test_json_contract_enumeration.py`, `test_record_committable_1771.py` → green.
- Known residual (not fixed, noted): a `git commit` refusing with "nothing to commit" now also warns (detail falls
  back to stdout). Pre-fix it was silent; it is honest but could be noise if records were ever byte-identical.
- Commit: `053aa4e80 fix(cli): surface a failed retrospect auto-commit as a stderr warning` (src diff only
  `src/specify_cli/cli/commands/retrospect.py`, +43/-4).

### Coord-topology claim (CHECKED, not fixed — routing commits per checkout is deferred)
Probe: `tests.terminus.conftest.build_coord_mission` (real coord mission, materialized `.worktrees/<slug>-coord`,
`.worktrees/` gitignored), WP01 walked approved→done on the canonical surface, `auto_commit: true`, real
`retrospect create --json` (fan-out patched).
- `_canonical_events_path` → `<repo>/.worktrees/terminus-01M5001A-coord/kitty-specs/terminus-01M5001A/status.events.jsonl`
  (inside the coord worktree) — **claim CONFIRMED**.
- The single `git add -- kitty-specs/<slug>/retrospective.yaml .worktrees/…/status.events.jsonl` from repo root exits 1:
  `The following paths are ignored by one of your .gitignore files: .worktrees`. git stages the record, then fails, so
  nothing is committed: `git status` = `A  kitty-specs/<slug>/retrospective.yaml`, HEAD unmoved. Pre-fix: exit 0,
  stderr empty (silent). Post-fix: the stderr warning names git's message.
- **Second finding:** `emit_captured` writes `RetrospectiveCaptured` to the PRIMARY `kitty-specs/<slug>/status.events.jsonl`
  (`resolve_retrospective_home`), while auto-commit stages the COORD surface. So even with a working add, the file
  carrying the new event is not the one staged (` M kitty-specs/<slug>/status.events.jsonl` left dirty on primary).
  Deferred with the per-checkout commit routing (ruling 1).

## A-G2 / B-G7 — `tests/cli/commands/test_retrospect.py`
Old tests were run from an untracked verbatim copy of the base file (`tests/cli/commands/test_zz_old_retro_probe.py`,
deleted afterwards, never committed). Each break reverted with `git checkout -- src/`; `git diff --stat src/` empty after.

| Test (old → new) | Planted break | Old | New |
|---|---|---|---|
| `test_auto_commit_disabled` → `test_auto_commit_disabled_in_config_commits_nothing` (real git, `auto_commit: false`) | `retrospect.py:255` `get_auto_commit_default(repo_root)` → `(repo_root.parent)` | PASSED | FAILED |
| `test_auto_commit_enabled_calls_git` → `test_auto_commit_enabled_commits_exactly_the_files_with_the_message` | `retrospect.py:272` `["git","commit","-m",message]` → `["git","commit","--dry-run","-m",message]` | PASSED | FAILED (`'init' == 'chore(retrospective)…\ninit'`) |
| `test_auto_commit_file_outside_repo_root` → `test_auto_commit_of_file_outside_repo_root_warns_and_commits_nothing` | drop the `except ValueError: rel_files.append(str(f))` fallback | PASSED | FAILED (`'outside repository' in …is not in the subpath…`) |
| `test_discover_missions_skips_non_dirs` → `test_discover_missions_skips_a_file_and_keeps_discovering_later_missions` | `retrospect.py:568` `continue` → `break` | PASSED | FAILED (`[] == [('01KS049J…','not_completed')]`) |

**Verdict changed (A-G2 2.4 + full-argv tightening):** A-G2 asked to keep the `subprocess.run` mock and pin full argv;
B-G7 (same tests) asked for real git. Implemented real git, which supersedes the argv pin. Evidence that argv pinning
would be structure-sensitive friction: break `rel_files.append(str(f))` (always absolute paths, "lost relative-path
conversion") → all 8 TestMaybeAutoCommit tests PASS under real git — git accepts absolute in-tree paths, so the
behaviour is identical; an argv pin would go red on a behaviour-neutral change. The outside-root test now pins the
product decision from ruling 1 (warn, commit nothing), not the dead fallback, and is renamed to what it asserts.
`test_auto_commit_failure_is_nonfatal` / `test_auto_commit_raises_is_nonfatal`: unchanged (KEEP; not in scope).

## B-G7 — `tests/cli/commands/test_retrospect_update_persisted.py`
`test_emit_captured_spy_matches_persisted_record_on_disk` → `test_captured_event_row_matches_persisted_record_and_report`
(real emitter, only `_fanout_live_work_retrospective` patched; reads the `RetrospectiveCaptured` row from
`kitty-specs/<slug>/status.events.jsonl`; asserts findings_status / proposal_count / evidence_ref_count / record_path /
mission_id == on-disk YAML == reported JSON). Old run from untracked base copy `test_zz_old_update_probe.py`.
- Break `lifecycle_events.py:459` `findings_status=record.findings_status` → `"ran_no_findings"`: old spy test PASSED,
  new FAILED.
- Extra (original #3320 shape): `retrospect.py:458` `emit_captured(persisted, …)` → `emit_captured(record, …)`: new FAILED.
- Sibling `test_update_result_and_event_agree_with_persisted_record` untouched (D1).

Runs: `uv run --frozen pytest tests/cli/commands/test_retrospect.py tests/cli/commands/test_retrospect_update_persisted.py -q -n auto --dist loadfile`
→ 100 passed, 2 skipped (root-uid EACCES guards, pre-existing KEEPs).
Commits: `6c9f3ff9a`, `14e7266cd`.

Formatting note: `src/specify_cli/cli/commands/retrospect.py`, `tests/cli/commands/test_retrospect.py`,
`test_retrospect_update_persisted.py`, `test_agent_retrospect_synthesize.py`, `test_generator_traces_ingest.py` are in
the `[tool.ruff.format].exclude` debt ratchet (pyproject.toml). Not whole-file reformatted (would churn thousands of
lines and, for src, violate "only the ruling-1 change"). Every def I added/changed was verified format-stable by
formatting a scratch copy and comparing the def source (fmtcmp).

## B-G1 — `tests/cli/commands/test_auth_login.py` (commit `e3dc3fee1`)
Old tests run from an untracked verbatim base copy `tests/cli/commands/test_zz_old_auth_probe.py` (deleted after).
All breaks in `src/specify_cli/cli/commands/_auth_login.py`, reverted with `git checkout -- src/` (diff empty after each).

RETIRE (guard red on the same break before deletion):
| Retired test | Break | Guard | Guard result |
|---|---|---|---|
| `test_default_dispatches_to_browser_flow` | `:160` `elif headless:` → `elif True:` | `tests/auth/integration/test_browser_login_e2e.py::TestBrowserLoginE2E::test_full_browser_login_happy_path` | FAILED (exit 1, "Device flow failed") — not vacuous |
| `test_headless_dispatches_to_device_flow` | `:160` → `elif False:` | `tests/auth/integration/test_headless_login_e2e.py::TestHeadlessLoginE2E::test_full_device_flow_happy_path` | FAILED (`launch` called once) after **301.45 s** (P8, deferred) |
| `test_force_reauthenticates_even_when_logged_in` | `:156` `tm.clear_session()` → `pass` | `test_browser_login_e2e.py::TestBrowserLoginE2E::test_login_force_resets_session` | FAILED (`assert 0 >= 1` deletes) |
(The old tests also went red on those breaks; irrelevant to RETIRE, recorded for completeness.)
Observation (not mine to fix): under the `elif True:` break the browser e2e guard's device path made a real HTTP
request that reached the egress proxy ("Network error requesting device code: 403 Forbidden") — the browser e2e
harness does not fake the device-flow edge. Harmless here (fails closed), noted for the auth-harness owner.

FIX (real `AuthorizationCodeFlow`; faked edges only: `StateManager` randomness, `CallbackServer` socket,
`BrowserLauncher.launch`, `PublicHttpClient`; keyring = `FakeSecureStorage` imported from
`tests/auth/integration/conftest.py`, unedited):
| Test | Break | Old | New |
|---|---|---|---|
| `test_missing_env_uses_configured_sync_server_url` | `:210` `saas_base_url=saas_url,` → `saas_base_url=DEFAULT_HOSTED_SAAS_URL,` | PASSED | FAILED |
| `test_warns_on_retired_first_party_target_without_rejecting` | same | PASSED | FAILED |
| `test_force_mints_fresh_credentials_on_mismatch` | same | PASSED | FAILED |
| all three | `:239` `tm.set_session(session)` → `pass` | PASSED ×3 | FAILED ×3 |
| `test_force_mints_fresh_credentials_on_mismatch` | `:156` `tm.clear_session()` → `pass` | (old sibling red) | FAILED (`0 >= 1`) |

Oracles: browser URL + every HTTP URL == `<configured>/oauth/authorize|token|api/v1/me`; persisted
`issuer_url` (set by the real flow from its constructor arg) == configured; `--force`: deletes ≥ 1, exactly one write
`(issuer_url, access_token) == ("https://saas.test", "at_fresh_login")`, it is the live session, old token not in stdout.

Isolation: autouse fixture now requests `canonical_home` (SPEC_KITTY_HOME per test; HOME/XDG are already per-worker
via tests/conftest.py) and patches `SecureStorage.from_environment` → per-test `FakeSecureStorage` (fixture
`storage`). `test_login_proceeds_even_if_teamspace_mission_state_is_blocked` no longer reads the worker's real auth
store/OS keyring (P7). Nothing skipped.

Runs: `uv run --frozen pytest tests/cli/commands/test_auth_login.py tests/auth/integration/test_browser_login_e2e.py -q -n auto --dist loadfile`
→ 32 passed. File alone: 27 passed. `ruff format` (file not in the format-debt exclude): unchanged; `ruff check`: clean.

## B-G5 — `tests/cli/commands/test_merge_strategy.py` (commit `61e2b6bf2`)
Shape probe first (scratch `strategy_probe.py`, real `build_coord_mission` 2 WPs + real `consolidate --keep-branch`):
- default / `--strategy squash`: target gains a single-parent "squash merge of mission" commit; lane tips NOT
  ancestors of target; lane tips ARE ancestors of the retained mission (coord) branch (lane-b merged via a 2-parent
  "Merge …lane-b into …").
- `--strategy merge`: target fast-forwarded (no mission→target merge commit when target did not move) — so the
  verdict's "two parents" oracle is WRONG for this fixture; **changed** to "every lane tip is an ancestor of the
  target" (history-reachability), which holds for both FF and true merges.
New test `test_consolidate_strategy_decides_whether_lane_history_reaches_the_target` (slow, 5 cases:
default-is-squash, flag-squash, flag-merge, config-merge, flag-beats-config). Oracles: rc 0; every WP file blob on
target; squash ⇒ no lane tip reachable from target and no merge commit in before..target; merge ⇒ every lane tip
reachable; all cases ⇒ every lane tip reachable from the mission branch (FR-007).
Old tests (`TestStrategyFlagFlowsThrough` ×2, `TestLaneToMissionUsesMergeCommit`) run from untracked base copy
`test_zz_old_strategy_probe.py` (deleted after).

| Break | Old (3 tests) | New |
|---|---|---|
| F1 `consolidate.py:691` `strategy=resolved_strategy` → `MergeStrategy.MERGE` | 3 PASSED | default/flag-squash/flag-beats-config FAILED (`{'WP01': True,…} == {'WP01': False,…}`); merge cases pass |
| F2 `:691` → `MergeStrategy.SQUASH` | (not re-run; mocks bypass the CLI entirely) | flag-merge/config-merge FAILED (`{…False} == {…True}`) |
| F3 `:789` `explicit or config or SQUASH` → `config or explicit or SQUASH` | 3 PASSED | flag-beats-config FAILED |
| F4 `lanes/consolidation.py:297` lane→mission `_merge_branch_into(…, strategy=MergeStrategy.SQUASH)` | `test_lane_to_mission_does_not_receive_strategy` PASSED | flag-merge FAILED (ancestry), default-is-squash FAILED (consolidate rc 1, gate refused) |
All breaks reverted with `git checkout -- src/`; `git diff --stat src/` empty after each.
Removed: `_make_mock_lanes_manifest`, `_write_meta`, `_seed_wp_done_events`, `_patched_lane_based_merge_dependencies`,
`_run_lane_based_consolidation` import, unused `MagicMock/patch/json/ExitStack`. Non-flagged config/hint/linear-history
tests unchanged. `ruff.toml`: the file's `F841` per-file-ignore was already stale (base copy has no F841 hit) → removed
(shrink-only). NB adjacent to S's `test_implement_base_flag.py` line — possible textual conflict if S edits that line.
Run: `uv run --frozen pytest tests/cli/commands/test_merge_strategy.py -q` → 30 passed (201.9 s).

## B-G8 — `tests/cli/test_agent_retrospect_synthesize.py` (commit `315df1ca7`)
Replaced `test_proposal_id_filter_passed_to_apply_proposals`, `test_dry_run_is_true_by_default_in_apply_call`,
`test_apply_flag_sets_dry_run_false` with two real-record tests (real `locate_project_root`/`resolve_mission_handle`/
`read_record`/`apply_proposals`; nothing patched; record written by `retrospective.writer.write_record` with
accepted/pending/rejected `add_glossary_term` proposals, evidence event id present in the mission event log;
real 26-char ULIDs):
- `test_synthesize_default_is_a_dry_run_of_accepted_proposals_that_touches_nothing`: exit 0, `dry_run: true`,
  planned ids == [accepted], applied == [], whole project tree byte-identical before/after.
- `test_synthesize_apply_applies_only_accepted_proposals`: exit 0, applied ids == [accepted], `.kittify/glossary/*.yaml`
  == [accepted-term.yaml], provenance == [accepted-term.yaml].
Ruling 2: `--proposal-id` bypass NOT pinned either way (the removed filter test pinned id pass-through, i.e. the bypass).
Old run from untracked base copy `tests/cli/test_zz_old_synth_probe.py` (deleted after).

| Break | Old (3) | New |
|---|---|---|
| `agent_retrospect.py:618` drop `if p.state.status == "accepted"` | 3 PASSED | both FAILED (planned/applied ids include pending+rejected) |
| `doctrine_synthesizer/apply.py:553` `if dry_run:` → `if False:` (dry run writes) | 3 PASSED | dry-run test FAILED (`applied` non-empty); apply test PASSED (expected) |
Reverted each; `git diff --stat src/` empty. KEEPs untouched (`test_generator_record_*`, `test_actor_id_forwarded`).
`ruff.toml`: F401 for this file already stale on base (only F841 `mock_ambig` fires) → dropped F401, kept F841.
Run: `uv run --frozen pytest tests/cli/test_agent_retrospect_synthesize.py tests/cli/test_agent_retrospect_missing_record.py -q -n auto --dist loadfile` → 28 passed.

## Final gates
- `uv run --frozen ruff check <7 touched .py>` → All checks passed.
- `uv run --frozen ruff format --check --force-exclude <touched>` → 2 files already formatted (the other 5 are in the
  format-debt exclude; new/changed defs verified format-stable); repo-wide `ruff format --check .` → 2791 files already formatted.
- `uv run --frozen mypy src/specify_cli/cli/commands/retrospect.py` → Success: no issues.
- `uv run --frozen pytest tests/architectural/test_ruff_pytest_style_baseline.py tests/architectural/test_ruff_format_exclude_ratchet.py -q` → 13 passed.
- Combined: `uv run --frozen pytest tests/cli/commands/test_retrospect.py tests/cli/commands/test_retrospect_update_persisted.py
  tests/cli/commands/test_auth_login.py tests/cli/commands/test_merge_strategy.py tests/cli/test_agent_retrospect_synthesize.py
  tests/cli/test_agent_retrospect_missing_record.py tests/specify_cli/retrospective/test_generator_traces_ingest.py
  tests/auth/integration/test_browser_login_e2e.py tests/architectural/test_no_read_side_bypass.py
  tests/cli/test_lazy_command_module_imports.py tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py
  tests/architectural/test_cli_console_single_seam.py -q -n auto --dist loadfile` → **245 passed, 2 skipped** (EACCES root guards).
- `git diff --stat issue-5353-cli-test-quality..HEAD -- src/` → only `retrospect.py` (+43/-4), only in `053aa4e80`.
