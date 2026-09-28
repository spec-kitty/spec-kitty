---
affected_files: []
cycle_number: 1
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T13:41:28Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback (cycle 1): request changes, tests only

The production fix is correct and I verified it end to end. Do not change `src/`. All three items below are about test assertions that the WP explicitly requires (T024 item 5 "every refusal assertion checks the file path AND the 're-save as UTF-8' remedy text"; T024-3 "CLI test: spec-kitty upgrade"; the review guidance "refusals assert path + remedy"; the contract row in contracts/failure-surface.md). At the moment no test pins the operator-visible CLI message, so a change to the root error presenter could drop the path or remedy and nothing would go red.

## Required changes

1. **NFR-003 at the true CLI surface.** `tests/specify_cli/session_presence/test_settings_encoding_4940.py:302`: `test_cli_subprocess_true_exit_code_for_sync_hooks` asserts only `returncode != 0`, the absence of "Sync complete" and the bytes. Make it assert `result.returncode == 1` (the contract says exit 1, and I observed exactly 1). Also assert that `result.stdout + result.stderr` contains the settings path (`str(_settings_path(project))`, or at least `.claude/settings.json`) and the literal `re-save it as UTF-8`. I observed this output on the lane: `Error: <abs>/.claude/settings.json is not valid UTF-8 and has no byte-order mark; re-save it as UTF-8`.

2. **NFR-003 on every refusal.** Add one helper, for example `_assert_refusal(excinfo, path)`, that checks `str(path) in str(excinfo.value)` and `"re-save it as UTF-8" in str(excinfo.value)`, and use it in every `pytest.raises(SettingsNotDecodableError)` block. That means lines 166 and 170 (today it checks only `"re-save"`, not "UTF-8"), 178 (`is_registered`), 185 (`unregister`), 255 (sync enable, which checks the path only), 266 (sync disable), 330 (live-work install), 340 (live-work uninstall), 381 (`prepare_commands`), 397 (`ClaudeCodeWriter.write`), 442 (upgrade runner) and 475 (`has_presence`). Bind `as excinfo` where it is missing.

3. **T024-3: a CLI-level `spec-kitty upgrade` assertion.** `test_upgrade_migration_refuses_non_zero_settings_untouched` (line 402) exercises `MigrationRunner.upgrade()` directly. I confirmed that `upgrade.py:1834` does not swallow the error: a real `spec-kitty upgrade --project --yes --target 3.2.0rc39 --no-worktrees` in a scratch project exits 1, prints the path and remedy, leaves the file byte-identical and does not record the migration. But no test locks that the command layer keeps propagating. Add one command-level assertion. It can be a `CliRunner` invoke of the real `upgrade` command with `isinstance(result.exception, SettingsNotDecodableError)` and `result.exit_code != 0`, or a subprocess test asserting exit 1 and the path and remedy text. In both cases assert that the file is byte-identical and that the output contains no success line for `3_3_0_session_presence_claude_code`. A recipe that works: take a project with `.kittify/metadata.yaml` at `version: 3.2.0rc38` and `agents.available: [claude]`, run `upgrade --project --yes --target 3.2.0rc39 --no-worktrees`, and use a cp1252 `.claude/settings.json`. The existing runner-level test can stay.

## Behavioural red-first evidence, so the Activity Log records more than the import error

These runs were on a `git archive` of 1f4a914c (merge-base 45785d2d plus WP01), with a local stub for `SettingsNotDecodableError`: 20 failed and 3 passed (the 3 are the controls). The behavioural reds:
- cp1252 `agent config sync --sync-hooks` (subprocess): exit 0, `✓ Sync complete`, the file was replaced by `{"hooks":{"PostToolUse":…}}` and there was no backup.
- UTF-16-LE-BOM `register` / sync: permissions, env and all hooks were lost, with no backup (`KeyError: 'permissions'`).
- UTF-8-BOM: the live file was reduced to lint-only (the only copy is in `.invalid.<uuid>`).
- UTF-16 `prepare_commands`/`apply_prepared`: rewritten as UTF-8 with no byte backup (FR-012).
- The `has_presence` cp1252 check returned False instead of raising, and the doctor probe reported a false `missing` instead of `unsafe`.
