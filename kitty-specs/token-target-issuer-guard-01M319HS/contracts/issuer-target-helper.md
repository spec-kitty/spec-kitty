# Contract: Issuer-target decision helper

## Decision (single authority, `auth/server_target.py`)

Inputs: a `StoredSession | None` (carries `issuer_url: str | None`), plus the process environment /
`config.toml` read by `resolve_server_target(process_wide_override=False)`.

Algorithm:
1. `target = resolve_server_target(process_wide_override=False)` — may raise
   `ServerTargetSplitBrainError` (fail-closed on ambiguous env/config).
2. If `session is None` or `session.issuer_url is None` → **legacy/no-compare**: the endpoint is
   `_normalize_url(target.resolved_server_url)`; no mismatch verdict.
3. Else compare `_normalize_url(session.issuer_url)` vs `_normalize_url(target.resolved_server_url)`:
   - equal → endpoint is the normalized resolved target.
   - differ → **mismatch verdict** (issuer host, resolved host, source name, stable remedy id).

The one `_normalize_url` (whitespace-strip + single-trailing-slash) is used for BOTH the comparison and
the endpoint returned; no other normalizer participates in a token-bearing comparison or URL build.

## Reaction surfaces

| Consumer | Reaction on mismatch | Reaction on split-brain |
|---|---|---|
| `resolve_token_endpoint(session) -> str` (refresh, ws, saas_client guard) | raise `IssuerTargetMismatchError` | propagate `ServerTargetSplitBrainError` (caller maps) |
| `revoke.py` | return `RevokeOutcome.ISSUER_MISMATCH` (no POST) | same non-leak refusal outcome |
| rehydrate (`token_manager`) | caught → `False` + specific warning (no send) | caught → `False` + warning |
| `_auth_saas_target.format_saas_mismatch_warning` | return display string | (unchanged: login already handles resolver errors) |
| `saas_client._guard_session_issuer` | raise (maps to `SaasAuthError` at `_oauth_session_context`) | existing split-brain→`SaasAuthError` translation |

`IssuerTargetMismatchError(AuthenticationError)`:
- `issuer_url: str`, `resolved_url: str`, `remedy: str` (stable id, e.g. `"auth login --force"`).
- `str(exc)` names issuer host, resolved host, source, remedy — **zero token material** (NFR-006).
- Member of `saas_client.auth._dead_session_errors()` so the held-token fast path cannot demote it.

## Null-session contract (M7)
`resolve_token_endpoint(None)` follows the legacy branch (returns the normalized resolved target) — it
never falls back to `get_saas_base_url()`. Callers that must have a session guard upstream and never pass
`None` into a *send*; the helper's null path exists only so a missing session cannot degrade to the
unsafe accessor.

## Architectural fence contract (`test_egress_consent_boundary.py`, extends E18)
- **Forbidden**: `get_saas_base_url` referenced by any token-send module —
  `auth/flows/refresh.py`, `auth/flows/revoke.py`, `auth/token_manager.py` (send paths),
  `auth/websocket/token_provisioning.py`.
- **Allowlist (floor)**: `auth/config.py` (definition), `auth/flows/device_code.py`,
  `auth/flows/authorization_code.py`, `auth/flows/client_credentials.py` (minting — no session/issuer to
  compare), `auth/http/transport.py` (host-resolution, no session), and display/doctor surfaces already
  on `resolve_server_target`.
- **Non-vacuity**: (a) self-mutation test — the gate fails if a token-send module regains the call;
  (b) exclusion test — the gate fails if any of the four token-send modules is added to the allowlist.
