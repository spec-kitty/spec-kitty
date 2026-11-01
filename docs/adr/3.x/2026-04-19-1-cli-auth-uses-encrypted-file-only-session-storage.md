---
title: CLI Auth Uses Browser-Mediated OAuth With Encrypted File-Only Session 
  Storage
description: 'Keeps browser-mediated OAuth but drops OS keyring persistence: CLI sessions live in an encrypted file, giving one cross-platform recovery and test surface.'
status: Accepted
date: '2026-04-19'
doc_status: active
kind: ADR
updated: '2026-04-19T00:00:00Z'
---

## Context and Problem Statement

The April 9 auth ADR made the correct high-level product call and the wrong
local persistence call.

The correct parts remain true:

1. human CLI auth must use the SaaS browser identity surface, not password
   prompts in the terminal,
2. the CLI must use a centralized token manager,
3. long-running sync, tracker, transport, and websocket paths must share one
   renewable session model.

The part we are reversing is local session persistence. The prior ADR chose
OS-backed secret stores where available:

- macOS Keychain
- Windows Credential Manager
- Linux Secret Service / GNOME Keyring / KWallet

That storage direction proved to be the wrong product fit for Spec Kitty:

1. on macOS the requesting identity is often an unstable Python process rather
   than a stable signed app, causing repeated friction and trust prompts,
2. background sync, websocket startup, and other non-interactive runtime paths
   can touch auth storage outside an explicit `auth login` moment,
3. Linux and Windows users should not need desktop credential infrastructure
   for a normal CLI session model,
4. multiple backend paths create more test matrix, more support surface, and
   more ambiguous recovery instructions.

The team also confirmed there is no compatibility burden worth preserving here:
the new browser-auth rollout has had zero user adoption, so we do not need to
migrate or preserve keychain-backed local state. Developers can re-authenticate.

## Decision Drivers

- **Keep the browser-auth product model** — the CLI continues to authenticate
  through the SaaS, not by collecting passwords locally.
- **One durable local storage model on every OS** — macOS, Linux, and Windows
  should all persist sessions the same way.
- **No dependency on desktop credential infrastructure** — runtime auth must
  work in terminals, SSH, CI-like shells, and long-lived background flows
  without keychain/credential-manager integration.
- **Centralized token management remains mandatory** — callers still do not
  read raw tokens directly.
- **No backend-selection knob** — storage mode is a product decision, not a
  runtime preference.
- **No migration layer** — stale local auth state may be discarded.
- **Cross-platform predictability** — Linux and Windows are first-class targets,
  not macOS exceptions.

## Considered Options

- **Option 1:** Keep browser-mediated OAuth but continue OS-keychain-first local storage
- **Option 2:** Keep browser-mediated OAuth and move all persisted session storage to one encrypted file-backed store (chosen)
- **Option 3:** Keep browser-mediated OAuth but store tokens in plaintext local files
- **Option 4:** Introduce a signed native helper/app solely to stabilize keychain identity

## Decision Outcome

**Chosen option: Option 2**, because it preserves the correct browser-auth and
token-manager architecture while removing the wrong dependency on OS secret
stores. It gives the CLI one recovery model, one testable persistence surface,
and one cross-platform behavior profile.

### Core Decision

1. Human CLI authentication to `spec-kitty-saas` MUST continue to use
   browser-mediated OAuth/OIDC, not username/password entry in the CLI.
2. The default interactive flow remains Authorization Code + PKCE via a local
   loopback callback.
3. The headless fallback remains Device Authorization Flow.
4. `spec-kitty` MUST continue to centralize access-token acquisition, refresh,
   retry, and invalidation behind one token manager. Callers MUST NOT read raw
   access tokens directly from storage.
5. Persisted CLI session material MUST be stored only in an encrypted local
   file-backed store rooted at `Path.home() / ".spec-kitty" / "auth"` on all
   supported platforms.
6. The canonical persisted files are:
   - `~/.spec-kitty/auth/session.json`
   - `~/.spec-kitty/auth/session.salt`
   - `~/.spec-kitty/auth/session.lock`
7. OS secret stores are not supported runtime backends for CLI auth:
   - no macOS Keychain
   - no Windows Credential Manager
   - no Linux Secret Service / GNOME Keyring / KWallet
8. The encrypted file format continues to use AES-256-GCM with a scrypt-derived
   key and a random per-store salt.
9. The scrypt passphrase remains bound to `f"{hostname}:{uid}"`; on platforms
   without `os.getuid()` support, the UID component resolves to `0`.
10. There is no backend-selection flag, env var, or config option.
11. There is no migration layer for pre-cutover keychain-backed state. Recovery
    guidance is to run `spec-kitty auth login --force`.
12. User-facing status surfaces MUST present this as the canonical encrypted
    session file backend, not as a fallback or degraded mode.

## Consequences

### Positive

- Browser auth remains the sole human login surface.
- Password handling remains out of the CLI.
- All supported platforms use the same persistence behavior.
- Runtime and background paths no longer depend on OS credential daemons.
- Support and troubleshooting simplify to one local-state model.
- Test coverage can focus on one persistence mechanism instead of a backend
  matrix.

### Negative

- The CLI no longer benefits from OS-native secret-store UX where those stores
  are well-behaved.
- File-permission enforcement differs by platform; Windows cannot rely on the
  same POSIX-mode checks used on Unix.
- Existing mission-080 docs/tests that described keychain-backed behavior must
  be rewritten or removed.

### Neutral

- This does not change the SaaS OAuth contract.
- This does not introduce a machine/service-account auth model.
- Host-owned persistence remains the rule; only the storage substrate changes.

## Confirmation

This decision is validated when:

1. `spec-kitty auth login` persists only to `~/.spec-kitty/auth/...`,
2. `spec-kitty auth status` reports the encrypted session-file backend,
3. `pyproject.toml` no longer depends on `keyring`,
4. runtime, sync, tracker, transport, and websocket code paths do not touch OS
   secret stores in steady state,
5. Linux and Windows continue to work without Secret Service or Credential
   Manager,
6. stale local state is recoverable by re-running
   `spec-kitty auth login --force`.

## Pros and Cons of the Options

### Option 1: Keep OS-keychain-first storage

Retain the browser-auth/token-manager architecture but store secrets in the OS
keystore when possible.

**Pros:**

- Reuses native OS facilities.
- Avoids on-disk bearer-token ciphertext files on machines with a usable
  keychain.

**Cons:**

- Reintroduces backend-specific behavior and support burden.
- Performs badly for Python-launched CLI processes on macOS.
- Keeps Linux and Windows tied to desktop credential services.
- Leaves runtime behavior dependent on infrastructure the user may not expect.

### Option 2: Encrypted file-only storage

Keep browser-mediated OAuth and the token manager, but persist sessions only in
the encrypted file-backed store under `~/.spec-kitty/auth/`.

**Pros:**

- One storage model across macOS, Linux, and Windows.
- Predictable runtime behavior for background and non-interactive flows.
- Simpler docs, tests, and recovery guidance.

**Cons:**

- Requires careful file-locking and permission handling.
- Gives up OS-keychain integration entirely.

### Option 3: Plaintext files

Persist renewable sessions in an unencrypted local file.

**Pros:**

- Simplest possible implementation.

**Cons:**

- Unacceptable security posture for bearer and refresh credentials.
- Rejected.

### Option 4: Signed helper for keychain stabilization

Keep OS keychains, but add an additional native component to stabilize process
identity.

**Pros:**

- Could reduce macOS prompt friction.

**Cons:**

- Solves only one platform symptom, not the broader product mismatch.
- Adds packaging, signing, and distribution complexity.
- Still leaves a multi-backend persistence model.

## More Information

**This ADR supersedes and replaces:**

- `2026-04-09-2-cli-saas-auth-is-browser-mediated-oauth-not-password.md`

**Issue lineage:**

- [Priivacy-ai/spec-kitty#559](https://github.com/Priivacy-ai/spec-kitty/issues/559)
- [Priivacy-ai/spec-kitty#562](https://github.com/Priivacy-ai/spec-kitty/issues/562)
- [Priivacy-ai/spec-kitty#603](https://github.com/Priivacy-ai/spec-kitty/issues/603)

**Implementation seams this ADR governs:**

- `src/specify_cli/auth/secure_storage/`
- `src/specify_cli/auth/token_manager.py`
- `src/specify_cli/auth/flows/authorization_code.py`
- `src/specify_cli/auth/flows/device_code.py`
- `src/specify_cli/cli/commands/_auth_status.py`
- `src/specify_cli/tracker/saas_client.py`
- `src/specify_cli/sync/client.py`
- `src/specify_cli/sync/body_transport.py`
- `src/specify_cli/sync/background.py`
- `src/specify_cli/auth/websocket/token_provisioning.py`
