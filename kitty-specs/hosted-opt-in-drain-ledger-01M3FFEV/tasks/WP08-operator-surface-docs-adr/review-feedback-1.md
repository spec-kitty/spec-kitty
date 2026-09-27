# WP08 review 1: changes requested (reviewer-renata)

Verified and working: red-first commit 13bfdf58 comes before 4a387294. The implementation commit changed the test file only by reformatting it; no assertion was weakened. The personal write goes to `get_runtime_root().base/config.toml` and the repo write goes to `.kittify/config.yaml`, with other keys preserved. The D7 path exits 1 and leaves the bytes unchanged. `status`/`--json` read only through `core.hosted_posture`. Dead-symbol use is genuine. I ran an E2E check in a temporary SPEC_KITTY_HOME and repo: off -> on (personal) is still off with the repo reason -> on --repo makes it effective on; NO_MOMENT_HANDLERS=1 turns it off; `zeitgeist status` prints the guidance line. ruff, format and mypy are clean. test_moments_drain, test_moments_command, test_no_dead_symbols and test_no_legacy_terminology: 164 passed. tests/docs: 1684 passed, 8 skipped. check_docs_freshness --ci: 0 errors. docs_index --strict: drift=False.

## Blocking: CLI

**Issue 1: the `--repo` help on `drain on/off` describes the wrong files.** The command reuses `_REPO_SCOPE_OPTION`, so `spec-kitty moments drain on --help` says: "Write the per-repo override (<repo>/.kittify/config.toml) instead of the global home .kittify config." Both halves are wrong for drain. `--repo` writes `.kittify/config.yaml` `hosted.drain`, and the default writes the runtime-root `config.toml`, not `~/.kittify`. This is the WP's own top-named risk, and it shows up in operator-facing help. Fix: add a drain-specific option constant and a test that asserts `config.yaml` appears in `drain on --help`.

**Issue 2: Rich markup swallows `[hosted]` in the help text.** `drain --help` and `drain on --help` render "personal runtime-root config.toml ( drain)". Escape it as `\\[hosted]`, or turn off markup for that help, and assert `[hosted] drain` in the help test. The current test only checks "both" and "environment variable".

**Issue 3: the unparseable-config UX has two problems.**
(a) `drain on|off --repo` against a malformed `.kittify/config.yaml` prints a full Rich traceback. The file is unchanged and the exit code is 1, but the output is not one line. Catch ruamel's `YAMLError` in `_drain_set`, print one line naming the file ("left unchanged"), exit 1, and add a test.
(b) The D7 personal error prints the literal text `[red]Error:[/red]` because the call uses `markup=False`. Either drop the tag or keep markup and escape the path.

**Issue 4: mutation survivors in test_moments_drain.py.**
- M1: removing `narrowers.append(posture.narrowed_by)` still gives 19/19 passing, because the env-var name also appears in `reason`. Assert `payload["narrowers"]` through `--json` with SPEC_KITTY_NO_MOMENT_HANDLERS=1.
- M7: removing the `"personal (hosted.drain)"` entry from the files map still passes. The "all four files" test checks only 2 of the 4 paths and never checks the labelled `files` entries. Assert all four keys and paths through `--json`, including when they are absent.

## Blocking: docs fidelity (the docs must match shipped behaviour)

**Issue 5: docs/api/environment-variables.md, section `SPEC_KITTY_SAAS_URL`.**
- The paragraph you edited still says "(`spec-kitty upgrade` migrates a saved retired first-party address to the canonical one; self-hosted values are never rewritten.)" That is false in this lane. `m_4_0_0_retired_hosted_target` now deletes `app.spec-kitty.ai` and prints guidance (FR-013). `m_4_0_0rc5_hosted_endpoint_session_backfill` backfills `[sync].server_url` from a stored session's `issuer_url` (D-6/FR-016). Document both.
- The "See also" bullets still say the override is "a dev / staging tool used by internal operators, not user behavior" and "remains internal-only after launch". Both contradict the new opening line: this variable is now one of the only two ways to configure an endpoint.
- The "Purpose" line says "sync clients". Rename it (dead term).

**Issue 6: docs/context/team-kitty.md still contains claims that are now false.**
- In "What `SPEC_KITTY_ENABLE_SAAS_SYNC` still gates": "Moments go out by default whenever a credential resolves." Wrong now: drain is off by default.
- Vocabulary row **Admission**: "Membership plus admission is the whole gate." Wrong now: drain is a client-side gate too.
- The sequence diagram and its alt text show `fire_saas_fanout`, then credential/mint, then publish, unconditionally. Add the drain check (drain off means a clean skip before any credential read) and update the alt text.
- "an endpoint can be configured with drain fully off, in which case explicit hosted commands work but nothing fires automatically" is wrong for relay commands. Under R-3, `zeitgeist status/watch/activity/read/inbox/send/reply/outbox approve` and the MCP relay tools are drain-gated. Only auth and tracker work without drain.
- "Drain is **this mission's** canonical term": a context glossary page is not scoped to a mission. Reword.
- The Sources section still says "Read at these heads on 2026-09-07", while the page says it mirrors code at the cited heads. Refresh it or add this lane's head.

**Issue 7: the ADR (2026-09-26-2) leaves out shipped decisions.**
- Widen and interview gating is missing. `widen/prereq.py` plus the charter, specify and plan interview startups skip the hosted prereq probe when drain is off (FR-004).
- FR-013/#4259 is missing: the retired-target migration changed from rewrite-to-canonical to delete-and-guide. R-4 covers only the `team.spec-kitty.ai` keep case.
- R-1 lists `[moments] agents = "off"` under "Env vars may only narrow it further ... still win when drain is on". It is not an env var, and `DrainPosture` does not consult it: it narrows inbound agent-context delivery, not outbound drain. Reword so it is not presented as a drain narrower, or state the axis precisely, as `moments.py::_drain_narrowers` already does. Optionally also list `SPEC_KITTY_SYNC_MINIMAL_IMPORT`, the third env narrower in `MOMENT_HANDLER_DISABLE_ENV_VARS`.

**Issue 8: the CHANGELOG entry leaves out the migration behaviour changes.** The retired `app.spec-kitty.ai` value is now deleted, not rewritten. That silently reverses the earlier bullet "A new 4.0.0 upgrade migration rewrites exactly the retired first-party address ... to the canonical hosted target", which sits in an earlier release section. The D-6 `issuer_url` backfill for already-logged-in machines is also missing. Add both to **After:** or as a companion bullet in the same `### Changed` list.

## Non-blocking notes
- `_drain_set` recomputes `get_runtime_root().base / "config.toml"` in the D7 branch. It would be cleaner to take the path from `hosted_posture`, for example a small `personal_config_path()` helper, so the path is not resolved in two places.
- ADR D-3 says explicit commands exit non-zero when unconfigured, but `auth status` exits 0 with guidance. The wording came from the contract, so this is optional: add "(status commands exit 0)".
- `docs/development/3-2-docs-retrieval-index.yaml` is outside owned_files, but `scripts.docs.docs_index --write` generated it and `--strict` reports drift=False. That is acceptable; mention the regeneration in the resubmission note.
