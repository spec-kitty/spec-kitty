---
title: 'Team Kitty (SaaS): the end-to-end hosted-sync flow'
description: 'The opt-in-to-delivery flow for hosted Team Kitty sync — consent, store migration, admission, auth, history disclosure, and the 3-gate drain — with a Mermaid diagram.'
doc_status: deprecated
updated: '2026-08-31'
related:
- docs/operations/sync-drain.md
- docs/guides/project-sync-consent.md
- docs/operations/internal-hosted-readiness.md
- docs/adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md
- docs/adr/3.x/2026-08-09-1-project-sync-store-boundary.md
- docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
- docs/api/environment-variables.md
---

> **Superseded (2026-09-07).** This page describes the retired "sync" transport
> (opt-in, project store, drain, `sync now`), which was deleted on both the CLI
> and SaaS sides in August 2026. The live model is Zeitgeist; read
> [Context: Team Kitty and Zeitgeist](../context/team-kitty.md). Kept only as a
> historical record.
# Team Kitty (SaaS): the end-to-end hosted-sync flow

> **Removed in 3.2.6; kept as historical record.** This architecture page
> describes the deleted CLI→SaaS sync flow, not the current Team Kitty dossier
> reader. It is scheduled for deletion in 3.2.7.

This page was written because the hosted-sync flow kept being reasoned about one gate at a
time — a `sync doctor` false-green, a stale `sync enable` message, a consent-vs-admission
mix-up — with no single place showing how opt-in, migration, admission, auth, and delivery
actually fit together. Each of these mechanics already has its own operator-facing runbook
(linked throughout); this page is the missing map that ties them into one flow, in delivery
order.

## Scope and ownership

Everything here keys off **one `project_uuid`-owned `ProjectSyncStore`**
(`src/specify_cli/sync/project_store.py`) holding the project's consent decision, consent
epochs, event journal, delivery ledger, body/offline queue, and target/admission binding — no
cross-project reads, no ambient identity from cwd, login, or repository URL. That invariant is
recorded in [ADR: One Project UUID Owns One Sync Store and One Consent
Decision](../adr/3.x/2026-08-09-1-project-sync-store-boundary.md) and [ADR: The Egress-Consent
Boundary](../adr/3.x/2026-08-04-1-egress-consent-boundary.md).

This page documents the **consumer-side CLI flow**. The Team Kitty SaaS backend itself lives
in the sibling `spec-kitty-saas` repository and is out of scope here.

## The six stages, in delivery order

1. **Opt-in / consent** — `spec-kitty sync opt-in` records a local, versioned grant keyed by
   the project's UUID. Purely local: no network call, no auth, no history import.
2. **Project-store migration** (existing installations only) — the previewable, copy-only,
   resumable cutover from the legacy shared store to this project's own UUID-owned store.
3. **Admission / delivery-target resolution** — the server-side authorization for one exact
   `(target, account/Private-Teamspace, project_uuid)` binding, independent of local consent.
4. **Auth (login / refresh)** — the browser-mediated OAuth flow that establishes and refreshes
   the session token every hosted call needs.
5. **History disclosure (drain-to-ledger)** — previewing, confirming, and applying the
   disclosure of already-migrated **sealed** legacy history into the delivery ledger.
6. **`sync now`** — the 3-gate drain (`saas_disabled` → `missing_auth` → `missing_team`) that
   actually ships journaled events to the hosted API.

Two commands both cover "history" and are easy to conflate — they are **not** the same
operation:

- **`sync import-history`** *synthesizes* a fresh `MissionCreated → WPCreated[] →
  WPStatusChanged[]` backfill stream from the project's **live** local mission/WP state, for a
  first-sync SaaS materializer. See `src/specify_cli/sync/history_import/`.
- **`sync project-store-history`** *discloses* rows that are **already sealed** by the
  project-store migration (stage 2) into the delivery ledger. This is stage 5 in the flow
  below.

Both follow the same `preview → confirm → --apply` three-step shape, deliberately, so an
operator only has to learn the pattern once.

## Interaction diagram: opt-in → sync

```mermaid
sequenceDiagram
    participant Op as Operator
    participant CLI as spec-kitty CLI
    participant Store as ProjectSyncStore (SQLite, project_uuid-scoped)
    participant Browser as System browser
    participant Auth as Hosted Auth (/oauth/*, /api/v1/me)
    participant Admission as Hosted Admission (/api/v1/sync/projects/{uuid}/sync-admission/)
    participant Events as Hosted Events API (/api/v1/events/batch/)

    Note over Op,CLI: 1. Opt-in / consent (local only, no egress)
    Op->>CLI: spec-kitty sync opt-in
    CLI->>CLI: is_saas_sync_enabled() gate + resolve project_uuid
    CLI->>Store: record_project_opt_in(project_uuid, actor)
    Store-->>Store: seal active epoch; INSERT project_consent_decisions(GRANTED); open new consent_epochs row
    Store-->>CLI: opt-in recorded

    Note over Op,Store: 2. Legacy → project-store migration (existing installs only)
    Op->>CLI: spec-kitty sync project-store-preview --source legacy.db
    CLI-->>Op: read-only inventory (no writes)
    Op->>CLI: spec-kitty sync project-store-migrate --source legacy.db --migration-id ID
    CLI->>Store: quiesce running daemon (cutover protocol handshake)
    CLI->>Store: copy -> verify -> atomic cutover into project_uuid-owned store
    Op->>CLI: spec-kitty sync project-store-status --migration-id ID
    CLI-->>Op: durable migration phase (manifest read only)

    Note over Op,Auth: 3. Auth: browser-mediated OAuth login
    Op->>CLI: spec-kitty auth login
    CLI->>CLI: get_saas_base_url() (SPEC_KITTY_SAAS_URL must be set)
    CLI->>Browser: open PKCE authorize URL on local loopback callback
    Browser->>Auth: GET /oauth/authorize (user authenticates)
    Auth-->>Browser: redirect with code + state
    Browser-->>CLI: loopback callback delivers code
    CLI->>Auth: POST /oauth/token (grant_type=authorization_code)
    Auth-->>CLI: access_token, refresh_token, expires_in
    CLI->>Auth: GET /api/v1/me
    Auth-->>CLI: user_id, email, teams[]
    CLI->>Store: persist StoredSession (OS keyring / file-fallback)

    Note over CLI,Admission: 4. Admission / delivery-target resolution
    CLI->>CLI: resolve_sync_target(user_id, team_slug) (descriptive, no network)
    CLI->>CLI: build_admission_audience(target, account, private_teamspace_id, project_uuid)
    CLI->>Store: AdmissionOperationService.perform: persist PREPARED DeliveryTarget
    CLI->>Admission: PUT sync-admission/ (Idempotency-Key)
    Admission-->>CLI: AdmissionResponse(state=admitted, generation, binding_audience)
    CLI->>Store: record ACKNOWLEDGED DeliveryTarget

    Note over Op,Store: 5. History disclosure (sealed migrated rows -> ledger)
    Op->>CLI: spec-kitty sync project-store-history (preview)
    CLI->>Store: preview_sealed_history() -> HistoryDisclosurePreview (no egress)
    Op->>CLI: sync project-store-history --confirm-by ... --idempotency-key ...
    CLI->>Store: confirm_history_disclosure() -> HistoryDisclosureCapability (still no egress)
    Op->>CLI: sync project-store-history --apply --history-action-id ID
    CLI->>Store: consume_history_disclosure() revalidates the confirmed cohort
    CLI->>Events: POST batch endpoint (migrated envelopes)
    Events-->>CLI: per-event delivery result
    CLI->>Store: SqliteDeliveryLedger records delivered/duplicate/pending/rejected

    Note over Op,Events: 6. sync now — the 3-gate drain
    Op->>CLI: spec-kitty sync now
    CLI->>CLI: run_preflight() (daemon-owner coherence)
    CLI->>CLI: Gate 1 saas_disabled? is_saas_sync_enabled() + per-project consent
    CLI->>Store: Gate 2 missing_auth? _event_sync_access_token()
    CLI->>Auth: refresh_if_needed() if access token near/at expiry
    Auth-->>CLI: rotated session (or RefreshTokenExpiredError -> "run auth login")
    CLI->>CLI: Gate 3 missing_team? strict Private-Teamspace resolver
    alt any gate blocked
        CLI-->>Op: print blocked gate name(s); zero-delivery summary
    else all gates clear
        CLI->>Store: select_consented() re-checks per-event project_uuid consent
        CLI->>Events: POST /api/v1/events/batch/ (Bearer token, <=1000 events/batch)
        Events-->>CLI: per-event outcome
        CLI->>Store: SqliteDeliveryLedger records outcome
        CLI-->>Op: DispatchSummary (delivered/duplicate/pending/rejected counts)
    end
```

**Reading notes on the diagram:**

- Stages 1, 2, and the preview/confirm parts of stage 5 are **local-only** — no network
  participant is touched. Only the auth exchange, the admission `PUT`, and the two actual
  batch `POST`s (stage 5's `--apply` and stage 6) cross the wire.
- This diagram describes the retired sync architecture; see [Team Kitty and Zeitgeist](../context/team-kitty.md) for the current transport.
  The current hosted default is `https://team.spec-kitty.ai`. OAuth login resolves its target through
  `src/specify_cli/auth/server_target.py`; a saved `config.toml [sync].server_url` can select another host.
  Remove stale saved targets or set them to the canonical Team Kitty URL.
- The admission client/outbox machinery (`AdmissionOperationService`, `SaasAdmissionClient`)
  is fully built and is what the diagram's step 4 shows, but at the time this page was
  written no traced CLI command path actually *invokes* `.perform()` — live command paths
  only *read* an already-registered target via `ProjectDeliveryTargetRegistry.get_current()`.
  Treat step 4's `PUT` as the designed contract, not a confirmed call site of every command
  shown around it.
- The **3-gate order is deliberate and fixed**: `saas_disabled` before `missing_auth` before
  `missing_team`, so an operator whose checkout is simply opted out sees that diagnosis first,
  not a downstream auth or teamspace symptom. Full gate-by-gate remediation:
  [Sync-Drain Runbook](../operations/sync-drain.md).

## Where to go for the operator-facing detail on each stage

| Stage | Runbook |
|---|---|
| 1. Opt-in / consent | [Per-Project Sync Consent](../guides/project-sync-consent.md) |
| 2. Project-store migration | [Per-Project Sync Consent § Migrating legacy shared state](../guides/project-sync-consent.md#migrating-legacy-shared-state-operators) |
| 3. Admission / delivery-target | [Per-Project Sync Consent § How admission pairs with the SaaS boundary](../guides/project-sync-consent.md#how-admission-pairs-with-the-saas-boundary) |
| 4. Auth | [Internal Hosted-Readiness Mode](../operations/internal-hosted-readiness.md); [Recovery: Logged out on a connected teamspace](../operations/logged-out-teamspace.md) |
| 5. History disclosure | `spec-kitty sync project-store-history --help` (no dedicated runbook yet — the CLI's own preview/confirm/apply prompts are the primary UX) |
| 6. `sync now` / the 3-gate drain | [Sync-Drain Runbook](../operations/sync-drain.md) |

## Operator configuration for this flow

Every knob in this flow that previously needed a per-shell `export` now has a single
`.kitty.env` home (two-tier: `${SPEC_KITTY_HOME}/.kitty.env` machine-wide, overridden by
`<repo>/.kittify/.kitty.env` per-repo) — see [ADR: operator config
env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md) and the
[Environment Variables Reference](../api/environment-variables.md). Run `spec-kitty doctor
env-file` to see which tier is supplying which governed var, and `spec-kitty sync doctor` /
`spec-kitty sync status` to see consent, admission, queue, and journal state together (the
[Sync-Drain Runbook](../operations/sync-drain.md) explains why `doctor`'s legacy Queue-size
row can read green while the real journal has a backlog — always cross-check against the
Per-Project Event Journal block).

## See also

- [Sync-Drain Runbook: the 3-Gate Order and the Doctor False-Green Trap](../operations/sync-drain.md)
- [Per-Project Sync Consent](../guides/project-sync-consent.md)
- [Internal Hosted-Readiness Mode (Pre-Launch)](../operations/internal-hosted-readiness.md)
- [ADR: Operator configuration resolves through one kernel env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
- [ADR: One Project UUID Owns One Sync Store and One Consent Decision](../adr/3.x/2026-08-09-1-project-sync-store-boundary.md)
- [ADR: The Egress-Consent Boundary](../adr/3.x/2026-08-04-1-egress-consent-boundary.md)
- [Environment Variables Reference](../api/environment-variables.md)
