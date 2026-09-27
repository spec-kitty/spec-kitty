---
affected_files: []
cycle_number: 1
mission_slug: hosted-opt-in-drain-ledger-01M3FFEV
reproduction_command:
reviewed_at: '2026-09-26T21:39:37Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (cycle 1): reviewer-renata

**Verdict: changes requested.** The core design is correct and I confirmed it by running the code: the resolver raises `HostedEndpointUnconfigured(ConfigurationError)`, `_or_none` is used in `transport.py`, the split-brain guard is intact, `DEFAULT_HOSTED_SAAS_URL` is not renamed, and `auth status`/`login`/`logout`/`doctor` print no traceback when unconfigured. What blocks approval is one architectural red caused by this WP, new ruff violations, and missing tests for new branches. These are small, mechanical fixes.

## Blocking

**Issue 1: `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` is RED and this WP caused it.** It is green on the base (a9545dc9: 6 passed). The WP reformatted six files that are still listed in `[tool.ruff.format].exclude`, so the ratchet asks for them to be removed:
`src/specify_cli/auth/flows/authorization_code.py`, `src/specify_cli/auth/flows/device_code.py`, `src/specify_cli/auth/http/transport.py`, `src/specify_cli/cli/commands/_auth_login.py`, `tests/cli/commands/test_auth_login.py`, `tests/cli/commands/test_auth_logout.py`.
Fix: remove those 6 entries from `[tool.ruff.format].exclude` in `pyproject.toml`. This WP already touches that file for the mypy override. Then re-run the ratchet and `tests/architectural/test_ruff_format_enforcement.py`.

**Issue 2: `ruff check` fails with 10 × E501 in the new file `tests/auth/test_endpoint_opt_in.py`, lines 17–30.** These are the census table rows in the module docstring, which run 166–324 characters against a limit of 164. On the base, `ruff check` over the same directories passes. Fix: reflow the table, for example as a bullet list or with wrapped cells. Do not add a `noqa`.

**Issue 3: several new code branches have no test.** This breaks T028 validation, the DoD line "every flow above has at least one direct test", and the Sonar rule that every new branch needs a test. Deleting any of the branches below leaves the suite green. I checked each behaviour live and it works, but it is not pinned:
- **Item 13, `auth/http/transport.py::_targets_configured_saas` (D4).** The WP explicitly requires tests (a) endpoint only in the runtime-root `config.toml` gives `True` for a matching URL, (b) unconfigured gives `False`, and (c) env set leaves behaviour unchanged. No test references `_targets_configured_saas`. Add all three, for example in `tests/auth/test_http_transport.py` or `test_endpoint_opt_in.py`.
- **Item 3, `SaaSTrackerClient.__init__`: unconfigured raises `SaaSTrackerClientError(error_code="hosted_endpoint_unconfigured")`.** No test asserts this `error_code`. The only coverage is the WP07-owned red test. Add a positive test in a WP06-owned file such as `tests/tracker/test_physical_request_helpers.py` or `tests/auth/test_endpoint_opt_in.py`.
- **Item 8, `_auth_logout.py::_print_issuer_mismatch_warning`, new `except HostedEndpointUnconfigured` branch.** Assert that the "Server-side revocation skipped: No hosted endpoint configured…" line appears and that no traceback is printed. It is best exercised through `spec-kitty auth logout` with a stored session, no endpoint, and a real (unmocked) `RevokeFlow.revoke`.
- **Item 9, `RevokeFlow.revoke` folding `HostedEndpointUnconfigured` into `RevokeOutcome.ISSUER_MISMATCH`.** Add it to `tests/auth/test_revoke_issuer_mismatch.py` or the opt-in module.
- **Item 10, the `token_manager.rehydrate_membership_if_needed` gap fix.** Assert it returns `False` and logs, and does not raise, when the endpoint is unconfigured. This is the path WP07's backfill relies on.

## Non-blocking (fix while you are in there)

4. The comment at `_auth_login.py` ~L108–110 still says "even when it equals the packaged default". Reword it to the canonical host identity (T028 row 2 asked for these stale comments to be reworded).
5. `"the default endpoint"` is left as dead code with `# pragma: no cover` in both `auth/server_target.py::_source_name_for_target` and `tracker/saas_readiness.py::_saas_source_name`. The WP allowed either keeping it or removing it. The charter's no-dead-code rule favours removing it, since no caller can produce that shape. At minimum, do not rely on a coverage suppression.
6. The census table claims are more generous than the tests. Row 12 says "direct-construction test added", but the test calls `resolve_token_endpoint(None)` and does not touch `token_provisioning`. Rows 6 and 7 are covered only by a generic-exception helper test (`test_any_other_resolution_failure_is_saas_url_not_configured`). Either add a `HostedEndpointUnconfigured`-specific case or reword those rows.
7. WP07 residual list: also name `tests/integration/test_spec_kitty_home_cli.py::test_absent_config_resolves_to_packaged_default`. I ran it and it is RED on this lane; it asserts the old packaged-default resolution. The commit message only says the file was "not exercised".

## Verified OK (no action)
- Red-first: at 657ac11d, `tests/cli/commands/test_auth_endpoint_unconfigured.py` gives 3 failed (behavioural), and `tests/auth/test_endpoint_opt_in.py` fails at collection with an ImportError. At lane tip both pass.
- The campsite commit e0cf94d4 preserves behaviour. C901 goes from 15 to 2 for `_physical_request_with_retry` and from 14 to 5 for `_check_server_session`. The egress census edits are a re-attribution of the same three `self._request` sinks, with no growth. The T034 mutant still proves exact-count detection.
- Of the 2 removed tests (`saas_source_name`/`format_saas_provenance` "neither set"), both pinned the retired `PACKAGED_DEFAULT` mode, which is now unconstructible, so removing them is acceptable under DIRECTIVE_041. The other 15 were re-pinned, not deleted.
- The mypy override for `specify_cli.auth.errors` is sound. `test_pyproject_shape` is green and mypy results equal the base (2 pre-existing errors in untouched files).
- Pre-existing reds, confirmed red on the base: 4 charter tests and `test_agent_commands.py::TestFreshnessShortCircuitOSErrorFallthrough::test_destination_health_check_oserror_falls_through_to_render`.
- Six auth test files flagged by `ruff format --check` are unformatted on the base too and are in the format exclude list, so they are not this WP's problem.
