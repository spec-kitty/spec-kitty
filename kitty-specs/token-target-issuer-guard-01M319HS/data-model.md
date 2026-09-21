# Data Model: Auth token-target issuer guard (#4755)

No persisted schema change and no migration. The relevant state already exists.

## StoredSession (existing, unchanged)
- `issuer_url: str | None` — the host the session was minted against (`None` for pre-#176 legacy
  sessions). Already persisted (`session.py:145,203,230`) and already preserved across refresh
  (`refresh.py:181`). This mission *consumes* it for target selection; it does not modify the field.
- `access_token`, `refresh_token` — the credentials that must reach only the issuer.

## ResolvedServerTarget (existing, unchanged)
- From `resolve_server_target(process_wide_override=False)`: `resolved_server_url`,
  `configured_server_url`, `env_server_url`, `override_mode`. Used as the comparison RHS and the
  endpoint source.

## IssuerTargetMismatchError (new)
`AuthenticationError` subclass in `auth/errors.py`:
- `issuer_url: str` — normalized issuer endpoint.
- `resolved_url: str` — normalized resolved target endpoint.
- `remedy: str` — stable remedy identifier (`"auth login --force"`).
- Message: names issuer host, resolved host, source, remedy; contains no token material.
- Membership: added to `saas_client.auth._dead_session_errors()`.

## RevokeOutcome (existing enum, extended)
- `+ ISSUER_MISMATCH` — revoke refused because the resolved target differs from the session issuer; no
  POST issued; local logout teardown still proceeds.

## Invariants
- For any session with a non-null issuer, no token is transmitted to a host ≠ the issuer.
- The comparison endpoint and the request URL are byte-identical after the one canonical normalization.
- Refusal diagnostics carry zero token material.
