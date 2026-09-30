# Review: #5353 slice-3 follow-up A (auth e2e fail-fast + device-flow fake)

Reviewer: reviewer-renata. Op 01M3SRH7FZDCRSYRRDGYDS5YEE. Branch `issue-5353-a-followup` @ e14515e1.

## Verdict: APPROVE-WITH-NITS

## Diff
The change touches only tests; `git diff origin/main...HEAD -- src/` is empty. It adds one autouse fixture to each of
`tests/auth/integration/test_headless_login_e2e.py` (fakes `AuthorizationCodeFlow.login`) and
`tests/auth/integration/test_browser_login_e2e.py` (fakes `DeviceCodeFlow.login`). The branch also carries the
implementer's Op evidence commits.

## Key question: does an autouse fake make a test vacuous?
No. Every test in the headless file invokes `login --headless`, so none of them needs `AuthorizationCodeFlow`. None of the
5 tests in the browser file reaches the device flow: 3 exercise the browser flow, 1 short-circuits as already logged in,
and 1 refuses because no URL is set. Break 4 below confirms the headless tests still drive the real `DeviceCodeFlow`.

## Is `login` the right seam?
Yes. `DeviceCodeFlow.__init__` makes no network call. All three of its `httpx.AsyncClient` calls (`device_code.py:165`,
`:215` and `:289`) are reached only from `login()`. `tm.set_session` makes no HTTP call. The choice matches the ledger's
note that the flow class is the true boundary (evidence 01M3R9VE, around L396).

## Breaks re-run (each reverted with `git checkout -- src/`, then `git status` confirmed clean)
| # | Mutation | Target | Result | Timing |
|---|---|---|---|---|
| 1 | `_auth_login.py:160` `elif headless:` -> `elif False:` | headless e2e | RED 3/3 at :171 `assert result.exit_code == 0`, exception=AssertionError('--headless dispatched to the browser (authorization-code) flow') | 3 failed in 1.34 s (wall 3.41 s). A cold first run took 203 s, all of it the one-time pip-install session fixture; every test call took under 1 s. |
| 2 | same line -> `elif True:` | browser e2e | RED 3 failed / 2 passed at :225, :392, :433 ('login dispatched to the device flow...'); no 403/network text | 1.91 s (wall 4.33 s) |
| 2-old | same break, origin/main copy of the browser file | old behaviour | RED only via real network: "Device flow failed: Network error requesting device code: 403 Forbidden" | 125.9 s for 1 test (`-x`) |
| 3 (own) | `if machine:` -> `if machine or headless:` | headless e2e | RED 3/3 at :171/:250/:288 (the machine flow fails because config is missing) | 1.27 s |
| 4 (own, masking) | `poller.format_user_code` returns the raw code | headless e2e | RED 1/3 at :177 `assert "ABCD-1234" in result.stdout` | 1.37 s |

## Gates
`pytest tests/auth/integration/ tests/architectural/test_ruff_pytest_style_baseline.py tests/architectural/test_ruff_format_exclude_ratchet.py`
gave 50 passed in 9.49 s. `ruff check` on the 2 files passed. `mypy` on the 2 files reported 1 error, in the pre-existing,
unchanged `conftest.py:30` (subclassing an Any-typed `SecureStorage`), not in the diff.

## Nits
1. (low) The new hunks use the legacy wrapped style. Both files are on the ruff-format exclude ratchet
   (`pyproject.toml:995-996`), so this is allowed. A campsite fix would run `ruff format` on both files and drop the two
   ratchet entries.
2. (low) Neither fixture calls `mock_login.assert_not_called()` at teardown. If a future broad `except Exception` in
   the CLI swallowed the AssertionError, the fixture would say nothing on its own. The existing `exit_code` and `auth_method`
   assertions still catch that today. A one-line teardown assertion would make the sentinel self-sufficient.
3. (info) The machine-flow direction (break 3) is caught only because the machine credentials are absent. `_isolate_auth_env`
   does not clear the `SPEC_KITTY_MACHINE_*`-style env vars, so on a runner that exports them, a headless->machine mis-dispatch
   would make a real `client_credentials` request. Optional: delenv them in the integration conftest.
