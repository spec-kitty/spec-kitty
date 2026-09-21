# Mission Specification: Auth token-target issuer guard

**Mission Branch**: `issue-4755-token-target-issuer-guard`
**Created**: 2026-09-21
**Status**: Draft
**Input**: GitHub issue #4755 — "auth: token refresh/revoke/rehydrate ignore the resolved server target and session issuer — refresh token POSTed to the wrong host (default or attacker via .kittify/.kitty.env), then local session wiped" (P0, `reliability`, `domain:hosted`).

## Summary *(context)*

Four token-bearing auth flows build their target URL from the packaged-default accessor
(`get_saas_base_url()`, which answers only "env override or packaged default") instead of the
canonical server resolver and the session's own issuer. As a result they transmit long-lived
credentials to a host the session was never authenticated against:

- **Token refresh** (`/oauth/token`) — transmits the **refresh token**.
- **Token revoke / `auth logout`** (`/oauth/revoke`) — transmits the **refresh token**.
- **Membership rehydrate** (`/api/v1/me`) — transmits the **access token**.
- **WebSocket token provisioning** (`/api/v1/ws-token`) — transmits the **access token** (currently
  dormant: no caller since the sync transport was retired, so this is defence-in-depth rather than a
  live exploit path, but it remains a latent leak if resurrected).

`auth login`, `auth status`, and `auth doctor` were already migrated to the canonical resolver plus an
issuer guard (#3406 / #234 / #4259); the code paths that actually **transmit** the tokens were skipped.
This mission closes that gap and prevents the class from recurring.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Self-hosted operator keeps a working, private session (Priority: P1)

A self-hosted operator configures their own Team Kitty server via `config.toml [sync].server_url`
(no environment override). Today, every token refresh and every logout POSTs their refresh token to
the packaged default host `team.spec-kitty.ai` instead of their configured server: the refresh never
reaches their server, the public host rejects the foreign token, and their local session is wiped —
an endless forced-re-login loop, plus their refresh token exposed to a server they never chose.

**Why this priority**: This is the P0 credential-exposure and availability defect the mission exists to
fix. Without it, self-hosting is unusable and refresh tokens leak to the public host on every refresh.

**Independent Test**: Configure a session whose `issuer_url` is a self-hosted URL set only in
`config.toml`; drive a refresh with the access token expired; assert the outbound request targets the
configured/issuer host and the refresh token never reaches the packaged default host. Fully testable
with a fake loopback server and no real network egress.

**Acceptance Scenarios**:

1. **Given** a session issued against a self-hosted server named only in `config.toml [sync].server_url`
   and an expired access token, **When** the CLI refreshes the token, **Then** the `/oauth/token`
   request targets the session's issuer host and the refresh token is never sent to the packaged
   default host.
2. **Given** the same session, **When** the operator runs `auth logout`, **Then** the `/oauth/revoke`
   request targets the session's issuer host, so the real server receives the revocation and rotates
   the token.
3. **Given** the same session, **When** a refresh succeeds, **Then** the local session is preserved
   (not wiped by a foreign host's `invalid_grant`).
4. **Given** a legacy session with `issuer_url = None` and a self-hosted host named only in
   `config.toml`, **When** any token-bearing flow runs, **Then** it routes to the resolved (config) host
   with **no** mismatch refusal (nothing to compare) and never falls back to the packaged default.

### User Story 2 - A hostile checkout cannot exfiltrate a credential (Priority: P1)

A victim clones or opens a repository that ships a committed `.kittify/.kitty.env` containing
`SPEC_KITTY_SAAS_URL=<attacker-host>`. The bootstrap env-file tier seeds that value into the process
environment. Today, `auth logout` (and any near-expiry refresh, and any rehydrate) then POSTs the
victim's token to the attacker's host — even though the issuer guard that `auth login` already enforces
exists precisely to stop a bearer minted for one server from being forwarded to another.

**Why this priority**: This is the active exfiltration vector; it is a credential-theft path reachable
from an ordinary "open this repo" action.

**Independent Test**: With a session whose `issuer_url` is host A and an environment override pointing
at host B, drive logout / refresh / rehydrate and assert every flow refuses (no token leaves for host
B) rather than transmitting the credential.

**Acceptance Scenarios**:

1. **Given** a session issued against host A and an environment (`SPEC_KITTY_SAAS_URL`) or config that
   resolves to a different host B, **When** the CLI refreshes, revokes, rehydrates, or provisions a WS
   token, **Then** the flow **refuses** and no token is transmitted to host B.
2. **Given** the refusal, **When** the operator inspects the outcome, **Then** it exposes a **stable
   structured remedy identifier** (e.g. `auth login --force`) — the same identifier `auth login`, the
   four flows, and rehydrate all surface — rather than free-text, and never a silent success.
3. **Given** the refusal on the refresh path, **When** the refusal propagates through the non-interactive
   credential-mint bridge, **Then** it is classified as a terminal/dead-session error and is **not**
   demoted to "use the held token" — the held token is never sent to the mismatched host.
4. **Given** a session with a *still-valid* access token whose issuer ≠ resolved target (so no refresh is
   triggered), **When** a held-token fast path is consulted for a token to send, **Then** the refusal
   fires at the send point and the still-valid held token is not returned for transmission.
5. **Given** an issuer/target mismatch (or a split-brain), **When** the operator runs `auth logout`,
   **Then** the remote `/oauth/revoke` is skipped (nothing sent to the wrong host) but the **local
   session teardown still proceeds**, and the operator is warned that server-side revocation did not
   occur so they can rotate the token via the real server.

### User Story 3 - The defect class cannot silently recur (Priority: P2)

A future contributor adds or edits a token-bearing flow. The unsafe accessor must not be reachable from
any session-token send path, and the issuer/target rule must live in exactly one place so a change to
precedence, normalization, or the remedy message propagates everywhere at once.

**Why this priority**: Single-canonical-authority + an architectural gate is what keeps this from being
a whack-a-mole re-leak the next time someone touches auth. It hardens the fix rather than merely patching
the four current sites.

**Independent Test**: A self-mutating architectural test that fails if any token-bearing module regains a
`get_saas_base_url()` call; a unit test proving all consumers (the four flows plus the pre-existing
`auth login` / `saas_client` guards) route through the one shared helper.

**Acceptance Scenarios**:

1. **Given** the shared issuer-target authority, **When** the module set is examined, **Then** the
   compare + normalize + remedy decision is defined in exactly one module and each named consumer (the
   four flows, `saas_client`'s guard, `auth login`, `auth status`/`auth doctor` display, rehydrate)
   imports it (positive-membership assertion, not a negative "no copies" search).
2. **Given** the unified authority, **When** `auth status` / `auth doctor` render an issuer mismatch,
   **Then** they still receive a display string and continue rendering — the unification does not turn
   the display surface into a raising one.
3. **Given** the architectural gate, **When** a token-bearing module is made to call `get_saas_base_url()`,
   **Then** the gate fails, while legitimate non-token callers (token-minting flows, transport
   host-resolution, the accessor definition, display/doctor surfaces) remain allowed.
4. **Given** the architectural gate's allowlist, **When** one of the four token-send modules is added to
   it, **Then** the gate fails (the allowlist provably excludes the token-send paths — no vacuous
   whitelist).

### Edge Cases

- **Legacy session (`issuer_url = None`)**: sessions minted before issuer recording carry no issuer to
  compare. The flow must **not** refuse; it must still route to the **resolved** target (honouring
  `config.toml`), never the packaged default — otherwise legacy self-hosted sessions keep leaking.
- **Ambiguous env/config split-brain (all flows)**: when environment and config name different hosts
  without a clean whole-process override, the resolver fails closed (a *resolver* refusal, distinct from
  an issuer *mismatch*). Every flow collapses this into the same non-leak posture as a mismatch: refresh /
  revoke / ws refuse with the token-free diagnostic; rehydrate fail-closes to a no-op plus its specific
  warning. No flow sends a token and none crashes with an unhandled resolver error.
- **Session is `None`**: the shared helper must define a null-session path explicitly (fail-safe — raise a
  clear error, or callers guard upstream and never pass `None`); it must never degrade to the packaged-default
  accessor.
- **Chained refresh (ws pre-connect refresh, post-refresh membership hook)**: when a nested refresh inside
  ws provisioning or the post-refresh rehydrate hook raises the mismatch refusal, it propagates out through
  the outer flow's own contract (no swallow, no send) because the nested call reuses the same guarded
  authority.
- **In-lock refresh**: refresh runs inside a machine-wide lock; the target resolution/guard must be
  positioned so a mismatch or split-brain does not introduce an error type the in-lock refresh contract
  cannot express, and does not leave the lock held abnormally.
- **Rehydrate is best-effort**: a mismatch on the membership rehydrate path fail-closes to "no
  rehydrate" (access token never sent to the wrong host); it must not be upgraded to a hard failure that
  breaks otherwise-working sessions, but the warning must name the mismatch and remedy.
- **URL normalization**: issuer/target equality and the URL actually placed on the request must be
  normalized identically (trailing slash, surrounding whitespace); a looser comparison anywhere re-opens
  the leak.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Refresh targets the issuer | As a self-hosted operator, I want token refresh to POST `/oauth/token` to the host my session was issued against so my refresh token never reaches a host I did not authenticate with. | High | Open |
| FR-002 | Revoke/logout targets the issuer | As an operator logging out, I want `/oauth/revoke` to go to the issuing host so the real server rotates my token and no host other than the issuer receives my refresh token. | High | Open |
| FR-003 | Rehydrate targets the issuer | As an authenticated user, I want membership rehydrate (`/api/v1/me`) to send my access token only to the issuing host. | High | Open |
| FR-004 | WS provisioning targets the issuer | As a user, I want WebSocket token provisioning (`/api/v1/ws-token`) to send my access token only to the issuing host, closing the latent leak even while the path is dormant. | Medium | Open |
| FR-005 | Refuse on issuer/target mismatch | As a victim of a hostile checkout, I want every token-bearing flow to refuse and transmit nothing when the resolved target differs from the session's issuer, exactly as `auth login` already refuses. | High | Open |
| FR-006 | Legacy null-issuer routes to resolved target | As a user with a pre-issuer session, I want token-bearing flows to route to the resolved server target (honouring `config.toml`), without a mismatch refusal and without falling back to the packaged default. | High | Open |
| FR-007 | Single canonical decision, per-consumer reaction | As a maintainer, I want one shared authority to own the *decision* (normalize → compare issuer vs resolved target → structured mismatch verdict carrying issuer host, resolved host, and remedy), consumed by every current authority, while each consumer keeps its own *reaction*: the four token-send flows and `saas_client`'s guard **raise**; `auth login` / `auth status` / `auth doctor` **render a display string** (the existing `format_saas_mismatch_warning` surface must keep returning, not start raising); rehydrate **warns and no-ops**. | High | Open |
| FR-008 | Refusal gates the send, not only the refresh | As a security stakeholder, I want the mismatch refusal to gate the point where a token is actually transmitted (so a still-valid access token returned by a held-token fast path is blocked too, not just an expiring one), and to surface through each flow's own contract such that no catch site can demote it into transmitting the held token. The refresh-path refusal must classify as a terminal/dead-session auth error so the held-token fallback treats it as a hard refusal, never a transient. | High | Open |
| FR-009 | Diagnosable refusal on the best-effort path | As an operator, I want the fail-closed rehydrate refusal to emit a specific warning naming the mismatch and the `auth login --force` remedy, rather than a mute no-op. | Medium | Open |
| FR-010 | Fold #4053 — remove dead resolver branch | As a maintainer, while unifying the resolver consumers I want the now-unreachable `except ConfigurationError` branch and its import removed from `_auth_saas_target.py` and the no-opinion-default provenance label corrected, so the file stops carrying dead security-relevant paths. | Low | Open |
| FR-011 | Fold #4265 — correct auth login mismatch legibility | As a scripter, while the shared helper is extracted from the `auth login` exemplar I want the issuer-mismatch refusal to return a non-zero exit code and the custom-endpoint label to use the canonical-host comparison, so `login && …` chains and endpoint provenance are correct. | Low | Open |
| FR-012 | Null-session contract | As a maintainer, I want the shared helper's behaviour for a null session defined explicitly (fail-safe, never a silent packaged-default fallback), so a missing session cannot degrade a token-bearing path back to the unsafe accessor. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No credential to a non-issuer host | Across all four flows, for any session with a non-null issuer, zero bytes of any token are transmitted to a host other than the session's issuer (verified by tests that assert the outbound target and refusal, with no real network egress). | Security | High | Open |
| NFR-002 | Identical normalization | Issuer/target equality and the request URL are computed with the one canonical normalizer (whitespace-strip + single-trailing-slash), with zero divergent normalization on any token-bearing comparison or URL build. | Security | High | Open |
| NFR-003 | Non-vacuous architectural gate (both directions) | The gate forbidding `get_saas_base_url()` on token-bearing send paths has a concrete floor and a self-mutation test proving it fails when a token-bearing module regains the call, **and** a second assertion proving the allowlist provably excludes the four token-send modules (fails if any of them is added to the allowlist). | Reliability | High | Open |
| NFR-004 | Red-first reproduction | The two live consequences (self-hosted mis-target/wipe on refresh+revoke; hostile-checkout exfiltration on logout+refresh+rehydrate) land issue-pinned regression tests that are RED through the pre-existing entry point before the fix and green after. The dormant ws flow (FR-004) is verified by direct unit invocation, not an integration reproduction. | Reliability | High | Open |
| NFR-005 | No behavioural regression for correctly-configured users | For a session whose issuer matches the resolved target, all four flows behave exactly as before (same requests, same outcomes); the change is observable only on mis-target/mismatch/legacy/split-brain paths. | Reliability | High | Open |
| NFR-006 | Token-free refusal diagnostics | Every refusal diagnostic — the `IssuerTargetMismatchError` message, the FR-009 rehydrate warning, and any log/breadcrumb on a refusal — names the issuer host, the resolved-target host, and a stable remedy identifier, and contains zero token material (verified network-free by asserting the token fixture value is absent from the emitted text). | Security | High | Open |
| NFR-007 | Static-gate compliance | All new and edited code passes `ruff` and `mypy` with zero warnings and holds cyclomatic complexity ≤ 15, with no new blanket suppressions (CLAUDE.md / Sonar gates). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mirror the existing guard semantics | The refusal rule must match the semantics `auth login` / `saas_client._guard_session_issuer` already enforce (compare normalized issuer vs resolved target; pass through null issuer; same remedy), reconciled into one authority rather than a second parallel one. | Technical | High | Open |
| C-002 | Resolver precedence unchanged | Target resolution uses `resolve_server_target(process_wide_override=False)` (env over `config.toml` over packaged default; fail-closed on split-brain); this mission does not change that precedence or the packaged default. | Technical | High | Open |
| C-003 | Fence excludes token-minting and non-token callers | The architectural gate must allow token-minting flows (device-code, authorization-code, client-credentials), transport host-resolution, the accessor definition itself, and display/doctor surfaces; only session-token *send* paths are forbidden from calling `get_saas_base_url()`. | Technical | High | Open |
| C-004 | Structural close, bounded to the seam | This mission closes #4755 **structurally**: it unifies the resolve-target-and-guard-issuer rule into one authority (retiring the parallel copies), fences the accessor, and folds the two P3 same-seam findings on the files the unification already rewrites — #4053 (dead `except ConfigurationError` branch in `_auth_saas_target.py`) and #4265 (`auth login` issuer-mismatch exit code + canonical-URL comparison in `_auth_login.py`). A fold is dropped only if its specific lines turn out untouched by the extraction. Unrelated hosted/security issues (#2941, #3279, the local-write-safety siblings, the dashboard-trust epic) stay separate; genuinely broader work is noted as a PR follow-up, not ticketed. | Business | High | Open |
| C-005 | Auth is security-critical core domain | Apply high (core-domain) rigour: focused unit tests on the helper and each per-flow adapter, deterministic and network-free, executing every new branch. | Regulatory | High | Open |

### Key Entities

- **Stored session**: the persisted authenticated session; carries `issuer_url` (the host it was minted
  against, `None` for legacy sessions), the access token, and the refresh token.
- **Resolved server target**: the canonical resolution of "which server are we hitting?" from environment
  and `config.toml` with a fail-closed split-brain guard.
- **Issuer-target helper**: the single authority that resolves the target, compares it to the session's
  issuer, and either returns the normalized endpoint to use or refuses on mismatch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a self-hosted session configured only via `config.toml`, 100% of refresh and logout
  requests target the issuing host and 0% reach the packaged default host.
- **SC-002**: For a session whose issuer differs from the resolved target (hostile-checkout override),
  100% of the four flows refuse and 0 tokens are transmitted to the mismatched host — including through
  the non-interactive credential-mint bridge and the held-token fast path. The three live flows are
  measured through their pre-existing entry points; the dormant ws flow is measured by direct invocation.
- **SC-003**: The compare + normalize + remedy decision is defined in exactly one module, and all six
  named consumers (four flows + the two pre-existing guards) import it (verified by positive-membership
  assertion), with the display surface still returning a string rather than raising.
- **SC-004**: The architectural gate fails both when any token-bearing module is mutated to call
  `get_saas_base_url()` and when a token-send module is added to its allowlist, and passes for every
  legitimate non-token caller; both live-consequence reproduction tests are RED before the fix and green
  after, and refusal diagnostics contain zero token material.
