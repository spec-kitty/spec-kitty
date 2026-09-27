---
affected_files: []
cycle_number: 1
mission_slug: hosted-opt-in-drain-ledger-01M3FFEV
reproduction_command:
reviewed_at: '2026-09-26T23:53:25Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review, cycle 1: changes requested

The core behaviour is correct and I verified it live. The retired-target migration now deletes the key, and the R-4 canonical value is left untouched. The D-6 backfill has its own `migration_id`, is auto-discovered, never calls `read()`, and leaves the auth dir byte-unchanged. It skips a retired issuer and does not touch `[hosted]`. The red-first commit is honest, and the 6 WP06 residual reds are now green.

The requests below are small. They are mostly tests that the WP explicitly asked for, plus two places where the code does not match the canonical source.

## Blocking

**Issue 1: the unparseable-config no-clobber path has no tests.** T031 step 3 says to "treat unparseable as 'not configured' but do **not** clobber the file". The branches that enforce this have no coverage. Coverage run: 93% overall, but these lines are all missing: `_configured_server_url` L131-134, `_load_home_config_for_write` L214-215, `apply()` L259, and the non-dict `sync` branch at L269. Add these tests:
- (a) `config.toml` is invalid TOML and a valid session exists. Assert that `apply()` succeeds, the file is byte-identical afterwards, and `changes_made` names the unparseable case.
- (b) `sync = "not-a-table"`. Assert and pin whatever you decide the behaviour is. Right now it silently replaces a non-table `sync` value. I recommend treating it as a file you "cannot safely understand" and refusing, the same way the unparseable case does.

**Issue 2: the two migrations have no test that runs them in sequence.** The WP's Risks section says: "add an integration-style test exercising both in sequence within one upgrade run to confirm the end state is 'backfilled from session,' not 'stuck deleted.'" No such test exists. I checked it by hand: the config has the retired `app.spec-kitty.ai`, a v3 session holds a self-host issuer, and I ran `get_applicable("3.2.6","4.0.0rc5")`. The delete migration ran before the backfill, and the end state was `server_url = selfhost` with `[hosted]` preserved. So the behaviour is correct, but it needs a test. Use `MigrationRegistry.get_applicable` ordering, or the real `spec-kitty upgrade` entry point in `TestUpgradeEntryPoint`.

**Issue 3: the decrypt mirror skips the key-permission check.** The WP says to decrypt "exactly as `_decrypt`'s v3 branch does". That v3 branch calls `_check_file_permissions(self._key_file)` (NFR-013) and refuses a `session.key` that is group- or world-readable. The mirror skips that check. As a result, the upgrade would configure an endpoint from a session the CLI itself refuses to decrypt. On POSIX, when `session.key` (and `session.json`) has `mode & 0o077`, make it a silent no-op, the same as the other failure modes. Add a test that chmods the key to 0644 and asserts no backfill and a byte-unchanged dir.

**Issue 4: `_configured_server_url` copies the canonical resolver's private reader (DIRECTIVE_044 Rule 2).** "Is a hosted endpoint configured?" already has one canonical answer: `specify_cli.auth.server_target.resolve_server_target_or_none()`. It returns `None` exactly when neither the env nor `[sync].server_url` names a target. With the default `process_wide_override=True` it cannot raise split-brain. The local copy has already drifted: the canonical code accepts a non-str `server_url` via `str(value)`, while the copy treats it as unset, so the backfill would overwrite it. Replace `_is_endpoint_configured()` with `resolve_server_target_or_none() is not None`, and delete `_configured_server_url`. That also removes the uncovered L131-134.

**Issue 5: the D6 byte-unchanged proof has gaps.**
- The `_write_session` fixture goes through `FileFallbackStorage.write()`, which creates `session.lock` **before** the "before" snapshot. So "no `session.lock` created" is never actually shown. Unlink `session.lock` (and `session.hot-path.json` if you want a minimal dir) before snapshotting, then assert it is still absent afterwards.
- T031 says to take the snapshot "in **every** backfill test (success and no-op)". The detect tests, and the apply tests for missing key, wrong-length key and no session file, do not take it. For the no-session case, also assert that the auth dir was not created, since there is no `mkdir`.
- Add a case with the wrong key at the correct length (32 random bytes). That is the real `InvalidTag` decrypt-failure path, and today only the wrong-length and missing-key cases are covered.

## Non-blocking (fix while there)

6. `tests/architectural/_baselines.yaml` `category_1_auto_discovered_migrations` justification still says "105->106 (#4259): adds m_4_0_0_retired_hosted_target". That module has now left the set, so the sentence is stale. The count is still correct at 106, since one entry was swapped for another. Reword it to note the swap. The allowlist swap itself is correct: the bidirectional ratchet forces removal once `home_config_path` gains a src caller.
7. An unparseable config combined with a session makes `detect()` return True while `apply()` does a successful no-op. The runner then records the migration as applied, so the machine is never backfilled even after the config is fixed. Consider returning False from `detect()` in that case, which falls out naturally from Issue 1(b) and Issue 4. Or document it as intended.
8. The T033 sweep disposition belongs in the PR body. Hits outside WP06/WP07 ownership: `tests/cli/test_auth_login_mismatch_exit.py` and `tests/cli/test_auth_logout_mismatch.py`. Both are legitimate explicit fixtures and need no change. `test_held_token_non_demotion.py` keeps its `_LEGIT_ISSUER` fixture constant and needs no change. `test_decision_widen_ownership_3111.py` has no hits.
9. Follow-up issue (do not do this here, because `auth/secure_storage/**` is outside this WP's ownership): extract a non-mutating v3 peek, for example `peek_session_readonly(store_dir)`, into `file_fallback.py`. Then `read()` and this migration can share one decrypt core, and the migration can drop its redefined `_SESSION_FORMAT_VERSION`, `_SESSION_KEY_BYTES` and filename constants. The duplication is acceptable for now for three reasons: the WP plan mandated a local helper, the fixtures encrypt through production `write()`, and any format bump turns `test_apply_backfills_server_url_from_issuer` red.

## Process finding (for the orchestrator and retrospective; no code action)

`git stash` was used in the lane-g worktree twice, at 23:09:09 and 23:13:39. The dangling stash commits are `15372409` / `d37e9301` and `159c55c6` / `9ddf7666`, both "WIP on …lane-g: a9964666". This breaks the repo rule against `git stash` in lane worktrees. `15372409` already held the finished `m_4_0_0_retired_hosted_target.py` implementation and the allowlist edit together with the test re-pins. So the "red-first" commit b00de504 was assembled after the implementation existed, not written first. The red state itself is genuine: at b00de504, 10 migration tests fail and the backfill test module fails at collection. Nothing was lost: the stashed implementation is identical to fab82b4c. Do not use `git stash` in the next cycle. Use a scratch worktree or a WIP commit on the lane.
