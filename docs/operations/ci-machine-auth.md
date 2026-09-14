---
title: CI Machine Authentication
description: 'Non-interactive machine authentication for hosted operations: the OAuth client_credentials mode, and the provisioning, rotation, and revocation runbook.'
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-09-14'
related:
- docs/operations/internal-hosted-readiness.md
- docs/api/environment-variables.md
- docs/adr/3.x/2026-04-09-2-cli-saas-auth-is-browser-mediated-oauth-not-password.md
---
# CI Machine Authentication

A CI runner — a GitHub Actions job, an E2E harness, any unattended
environment — can authenticate to the Spec Kitty SaaS with **no browser, no
TTY, and no human approval step**, using a machine credential instead of a
person's OAuth session. This page is the CLI-side runbook; the server-side
contract (identity, blast radius, scope vocabulary, issuance, revocation)
lives in the SaaS repo's machine-credential work.

## The three authentication modes

| Mode | Command | Credential | Who it is for |
|---|---|---|---|
| Developer OAuth (browser) | `spec-kitty auth login` | Your SaaS user session, minted via Authorization Code + PKCE in a browser | A person at a workstation — the default |
| Device flow (headless) | `spec-kitty auth login --headless` | Same human session, minted via RFC 8628 — still needs a **human** to open a browser and approve the device code | A person on SSH / a no-browser machine |
| Machine / CI | `spec-kitty auth login --machine` | A **ServicePrincipal** `client_id` + `client_secret` exchanged via the OAuth `client_credentials` grant — no human anywhere in the loop | CI runners, E2E harnesses, unattended automation |

The device flow is *headless*, not *unattended*: it still requires a person
to approve. That is precisely the gap the machine mode closes.

## Configuring a CI runner

The machine credential arrives as environment variables (the usual CI
secret mechanism), and the target server is selected by the same variable
every hosted surface reads:

```bash
export SPEC_KITTY_SAAS_URL=https://team.spec-kitty.ai   # select the target
export SPEC_KITTY_MACHINE_CLIENT_ID=<principal client id>
export SPEC_KITTY_MACHINE_CLIENT_SECRET=<secret>          # or use the file form below
spec-kitty auth login --machine
```

For runners that materialize secrets as files (mounted credential files,
`gh secret` file mounts), point at the file instead — its contents are read
once and stripped; the path wins over a stale inline value:

```bash
export SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE=/run/secrets/machine_client_secret
```

After login, the credential is an ordinary stored session tagged
`auth_method="client_credentials"`: every hosted command, the
`TokenManager` refresh path, and the Zeitgeist capability mint all work
unchanged, and the SaaS attributes every write to the machine principal in
its audit log.

## What a runner can verify without a TTY

- `spec-kitty auth status` — prints the auth mode
  (`Machine / CI (Client Credentials Grant)`) and session lifetime; exit 0
  whether or not authenticated.
- `spec-kitty auth doctor --json` — deterministic JSON (schema v3) that now
  includes `session.auth_method`; contains no token or secret material,
  ever.
- `spec-kitty auth whoami` — exits 0/1 on authentication state alone.

## Fail-closed behavior

A misconfigured machine login **never** degrades into a device-flow or
browser prompt. Missing or blank credentials exit 1 with the exact
variables to set; a rejected credential exits 1 with the operator
remediation (check/re-provision the principal) — the server deliberately
does not distinguish an unknown client id, a revoked principal, and a wrong
secret, and the CLI mirrors that indistinguishability. The secret value is
never printed, logged, or embedded in an error.

## Provisioning, rotation, and revocation (server side)

A team admin provisions a scoped principal per environment — develop and
production get **separate** principals, each scoped to its target team and
to the `sync:ingest` / `sync:read` scope vocabulary:

```bash
# in the SaaS repo's environment
make manage ARGS='provision_service_principal <name> --team <slug> --scope sync:ingest,sync:read'
make manage ARGS='revoke_service_principal <client-id>'
```

The provisioning command prints the client secret **once**; it is stored
only as a hash server-side. To rotate, revoke the old principal, provision
a new one, and re-run `spec-kitty auth login --machine --force` on the
runner with the new pair. Revocation takes effect on the next request (the
SaaS test suite proves the still-signature-valid token is refused
immediately).

## Security constraints

- The client secret is supplied via environment or secret file only —
  never committed to a repository, never in `.kitty.env`, never in test
  YAML, never in generated artifacts.
- A personal user's refresh token is never the CI credential.
- The env-file doctor and secret-redaction allowlist treat
  `SPEC_KITTY_MACHINE_CLIENT_SECRET` as secret-shaped: provisioning emits
  at most a commented blank template, diagnostics report name/presence
  only.
- Every authenticated write is attributable to the machine principal in
  the SaaS audit log (`service_principal_token_issued`), so E2E writes are
  attributable and revocable as a unit.
