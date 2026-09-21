# Quickstart / Verification: Auth token-target issuer guard (#4755)

All checks are network-free (fake loopback server / monkeypatched resolver + clients).

## Red-first repros (must be RED before the fix)
1. **Consequence 1 — self-hosted mis-target**: session `issuer_url = http://127.0.0.1:PORT` set only via
   `config.toml [sync].server_url`, access token expired → drive refresh → assert `/oauth/token` targets
   the configured host and the refresh token never reaches `team.spec-kitty.ai`. Same shape for logout →
   `/oauth/revoke`.
2. **Consequence 2 — hostile-checkout exfil**: session `issuer_url = https://team.spec-kitty.ai`,
   `SPEC_KITTY_SAAS_URL = http://127.0.0.1:ATTACKER` → drive logout / refresh / rehydrate → assert every
   flow refuses and no token reaches the attacker host.

Both pinned `@pytest.mark.regression` on #4755, through the pre-existing entry points. After the fix they
become focused unit tests (not left marked `regression`).

## Post-fix unit assertions
- `resolve_token_endpoint`: issuer==target → normalized endpoint; issuer≠target → `IssuerTargetMismatchError`;
  `issuer_url=None` and `session=None` → resolved target, no raise, never packaged default.
- refresh: mismatch raises and is in `_dead_session_errors()`; `saas_client._usable_access_token`
  held-token fast path does NOT return the token on mismatch (M4).
- revoke: mismatch → `RevokeOutcome.ISSUER_MISMATCH`, no POST; `_auth_logout` still deletes local creds
  and warns revoke was skipped.
- rehydrate: mismatch → `False` + a warning naming hosts + remedy (token-free).
- ws: mismatch → `WebSocketProvisioningError` (direct invocation).
- diagnostics: token fixture value absent from every refusal message/warning (NFR-006).
- normalizer: `me_fetch` URL and the guard comparison agree byte-for-byte.

## Unification / arch checks
- Positive-membership: the decision lives in one module; the four flows + `saas_client._guard_session_issuer`
  + `_auth_saas_target.format_saas_mismatch_warning` import it (SC-003).
- `auth status`/`auth doctor` still render the mismatch as a string (no raise).
- Fence: mutate a token-send module to call `get_saas_base_url()` → gate RED; add a token-send module to
  the allowlist → gate RED; legitimate non-token callers → green.

## Campsite folds
- #4053: `_auth_saas_target.py` no dead `except ConfigurationError` / import; provenance label correct.
- #4265: `auth login` issuer mismatch exits non-zero; custom-endpoint label uses canonical-host compare.

## Static gates
`ruff check` + `ruff format --check` clean; `mypy` zero warnings; complexity ≤ 15; blast-radius tests
(`tests/auth/`, `tests/saas_client/`, `tests/cli/`, plus `tests/architectural/test_egress_consent_boundary.py`)
green.
