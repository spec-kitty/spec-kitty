---
title: CLI-to-SaaS Authentication Is Browser-Mediated OAuth, Not Password Login
description: 'Replaced CLI password login with browser-mediated OAuth (PKCE plus loopback callback, device flow headless); later superseded on local session persistence.'
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-04-09'
---

## Context and Problem Statement

> Superseded on 2026-04-19 by
> `2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md`.
> Keep this ADR for historical context only; do not implement from it.

The current CLI-to-SaaS authentication implementation drifted into a password
login flow:

1. `spec-kitty auth login` prompts for username and password,
2. the CLI exchanges those credentials for JWTs through SaaS endpoints intended
   only for the CLI,
3. refresh and token reuse are implemented independently in multiple CLI paths,
4. long-running sync and tracker clients can hold stale bearer tokens,
5. the implementation no longer matches the product direction that the SaaS is
   the human authentication surface.

This is the wrong architectural seam for human users.

Spec Kitty already has browser-based authentication on `spec-kitty-saas`. Human
CLI authentication should reuse that existing SaaS identity surface, not bypass
it with a second password step. The CLI should open the browser onto the
SaaS, let the user authenticate using normal SaaS login methods, and then store
renewable session credentials locally in a host-owned store.

The new design must also correct the current token freshness problem. A logged
in CLI should remain authenticated until one of two things happens:

1. the user explicitly logs out, or
2. the SaaS invalidates the session.

## Decision Drivers

* **One human authentication surface** — SaaS browser auth is the source of
  truth for human identity.
* **No password handling in the CLI** — CLI must not prompt for or transmit SaaS
  passwords.
* **Renewable long-lived CLI sessions** — interactive CLI auth must stay fresh
  without repeated login prompts during normal operation.
* **Host-owned secret persistence** — CLI session storage remains in
  `spec-kitty`, but with a centralized token manager and OS-backed secret
  storage.
* **Compatibility with existing SaaS auth** — the solution should build on the
  current SaaS/browser stack unless buying identity infrastructure materially
  improves the result.
* **Headless support** — remote shells and SSH sessions still need a supported
  login path.

## Considered Options

* **Option 1:** Keep password-based CLI login and patch refresh bugs
* **Option 2:** Build first-party OAuth/OIDC on `spec-kitty-saas` and use browser-mediated CLI login with PKCE (chosen)
* **Option 3:** Migrate human auth to an external identity platform now

## Decision Outcome

**Chosen option: Option 2**, because it restores the intended product model,
reuses the SaaS as the single human authentication surface, and avoids the cost
and migration risk of moving the whole identity system to a third party before
that is justified.

### Core Decision

1. Human CLI authentication to `spec-kitty-saas` MUST use browser-mediated
   OAuth/OIDC, not username/password entry in the CLI.
2. The default interactive flow MUST be Authorization Code with PKCE using a
   localhost loopback callback opened from the CLI into the SaaS.
3. The CLI MUST also support a headless fallback. Device Authorization Flow is
   the preferred fallback for SSH and non-browser environments.
4. `spec-kitty-saas` MUST issue renewable CLI session credentials whose lifetime
   is effectively indefinite under normal use and rotation, ending only on
   explicit logout or server-side invalidation.
5. `spec-kitty` MUST centralize all access-token acquisition, refresh, retry,
   and invalidation handling behind one token manager. Callers MUST NOT read raw
   access tokens directly from storage.
6. CLI secret material MUST be stored in a host-owned store backed by the OS
   keychain where available. Plain-file metadata may remain for non-secret
   session state, but bearer or refresh credentials are not the primary storage
   location.
7. Existing password-based CLI token endpoints and command flows are deprecated
   immediately and MUST be removed after the browser-based flow is fully cut
   over.

### Buy-vs-Build Interpretation

1. The default implementation path is first-party OAuth/OIDC on the existing
   SaaS stack.
2. If Spec Kitty later chooses to buy rather than build for human identity,
   Auth0 is the preferred external option for CLI/native-app semantics because
   it has stronger fit for PKCE, device flow, and rotating renewable sessions.
3. Clerk is not the preferred path for this CLI problem because current product
   constraints are a weaker fit for scoped CLI/API authorization.

## Consequences

### Positive

* Human users authenticate once through the same SaaS browser surface they
  already use.
* Password handling is removed from the CLI.
* Token freshness becomes a centralized concern instead of a scattered
  implementation detail.
* Long-running sync, tracker, and websocket flows can share one renewable
  session model.
* The decision aligns the implementation with the original OAuth-first product
  intent.

### Negative

* Coordinated changes are required across both repositories.
* SaaS must expose an authorization surface intended for public/native CLI
  clients.
* CLI auth, websocket, sync, and tracker clients all need migration away from
  direct token usage.

### Neutral

* Service-account or machine-to-machine automation may still require a separate
  auth model; this ADR only governs human CLI authentication.
* Host-owned persistence remains the architectural rule; only the credential
  model changes.

### Confirmation

This decision is validated when:

1. `spec-kitty auth login` opens the browser and no longer asks for username or
   password,
2. the CLI can remain authenticated across long-running sync and tracker usage
   without re-login under normal operation,
3. all HTTP and websocket callers obtain credentials through a centralized token
   manager rather than reading raw tokens directly,
4. explicit logout and server-side invalidation both terminate the local CLI
   session cleanly,
5. the legacy `/api/v1/token/` and `/api/v1/token/refresh/` CLI password/JWT
   path is removed.

## Pros and Cons of the Options

### Option 1: Keep password login and patch refresh bugs

Continue prompting for SaaS credentials in the CLI and incrementally harden the
current JWT refresh model.

**Pros:**

* Lowest immediate implementation cost.
* Minimal short-term protocol change.

**Cons:**

* Preserves the wrong product and security boundary.
* Leaves the CLI responsible for password collection.
* Encourages continued token-handling sprawl across callers.

### Option 2: First-party browser-mediated OAuth/OIDC on the SaaS

Use SaaS browser auth as the human login surface, with CLI-native PKCE and
headless device flow semantics.

**Pros:**

* Matches the intended product experience.
* Reuses existing SaaS identity surface.
* Solves login UX and refresh architecture together.

**Cons:**

* Requires server and client implementation work.
* Requires a migration path off existing CLI token endpoints.

### Option 3: Migrate identity to an external platform now

Adopt a third-party identity provider for both SaaS and CLI login before
addressing the local architecture.

**Pros:**

* Offloads part of the identity implementation burden.
* May provide mature token/session features.

**Cons:**

* Larger migration scope than required for the immediate problem.
* Couples a CLI auth redesign to a broader SaaS identity platform decision.
* Still requires CLI transport and storage cleanup locally.

## More Information

**This ADR supersedes the password-era human CLI auth direction encoded in:**

* `spec-kitty/kitty-specs/027-cli-authentication-module-commands/spec.md`
* `spec-kitty/kitty-specs/059-saas-mediated-cli-tracker-reflow/spec.md`

**This ADR clarifies and extends, but does not replace, the following accepted ADRs:**

* `2026-02-27-2-host-owned-tracker-persistence-boundary.md`
* `2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md`
* `architecture/1.x/notes/adr-connector-auth-binding-separation.md`

**Implementation seams this ADR governs:**

* `spec-kitty/src/specify_cli/cli/commands/auth.py`
* `spec-kitty/src/specify_cli/sync/auth.py`
* `spec-kitty/src/specify_cli/tracker/saas_client.py`
* `spec-kitty/src/specify_cli/sync/background.py`
* `spec-kitty/src/specify_cli/sync/batch.py`
* `spec-kitty/src/specify_cli/sync/body_transport.py`
* `spec-kitty/src/specify_cli/sync/client.py`
* `spec-kitty-saas/spec_kitty_saas/urls.py`
* `spec-kitty-saas/apps/sync/jwt_views.py`
* `spec-kitty-saas/apps/sync/views.py`
