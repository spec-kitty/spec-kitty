---
title: Per-Project Sync Consent
description: 'Per-project hosted-sync consent in Spec Kitty 3.2: opting in and out, the deny-only kill switch, SaaS admission pairing, and migrating legacy shared sync state.'
doc_status: deprecated
updated: '2026-08-31'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/guides/how-to/collaboration/sync-workspaces.md
- docs/api/environment-variables.md
- docs/adr/3.x/2026-08-09-1-project-sync-store-boundary.md
- docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
- docs/adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md
- docs/context/team-kitty.md
---
# Per-Project Sync Consent

> **Removed in 3.2.6; kept as historical record.** The per-project hosted-sync
> consent and store model described here was removed with the CLI→SaaS sync
> transport. This page is scheduled for deletion in 3.2.7.

*Guidance dated 2026-08-13, covering the consent model shipped by mission
`per-project-sync-consent-ledgers-01KZKMQZ` (core `#3262`, companion SaaS
mission `project-sync-admission-boundary-01KZKMQ7` / SaaS `#585`).*

Hosted sync consent belongs to **one immutable project identity** — the
canonical `project_uuid` minted by `spec-kitty init` — not to a login, a
service URL, a checkout path, a repository slug, a remote URL, or a
machine-wide environment switch. Each project owns a **physically separate
sync store** holding its consent decision, consent epochs, event journal,
delivery ledger, body/offline queue, target binding, and migration state. No
live operation for one project can open or mutate another project's store.

---

## The model in one table

| Layer | Who writes it | What it can do | What it can never do |
|-------|---------------|----------------|----------------------|
| **Project consent decision** | You, via `spec-kitty sync opt-in` / `opt-out` | Grant or refuse hosted egress for exactly one `project_uuid` | Be created by login, URL, slug, path, env var, or another checkout |
| **Consent epoch** | The consent authority, transactionally | Scope which captured rows are eligible (eligibility starts at the opt-in tail) | Automatically re-drain pre-consent or revoked-period rows |
| **Kill switch** (`SPEC_KITTY_ENABLE_SAAS_SYNC`) | You, in the environment | **Deny only**: suppress all hosted egress machine-wide | Create, copy, revive, or delete a project grant |
| **SaaS admission** | The server, per exact target/account/Private-Teamspace + `project_uuid` | Authorize delivery for one target binding via an opaque generation | Substitute for, or be substituted by, local consent |

---

## Opt a project in

```bash
spec-kitty sync opt-in
```

This records **one versioned, attributable grant keyed by the project's
UUID** in that project's own store. It works offline and while the kill
switch is disabled — the local decision is recorded and remote admission is
reported as *pending* rather than being discarded.

What opt-in deliberately does **not** do:

- It does not make rows captured **before** the opt-in eligible. Eligibility
  starts at the current capture tail; older rows stay in sealed epochs. The
  command previews that excluded cohort so you know it exists.
- It does not grant any other checkout, clone, or re-initialized copy of the
  same repository. A fresh clone gets a new UUID, a separate store, and
  starts denied.
- It does not touch SaaS admission. Delivery additionally requires the
  target-scoped server admission described below.

If the checkout has no project identity yet, opt-in fails loudly and tells
you to run `spec-kitty init` first — it never writes a half-grant keyed only
by path.

## Opt a project out

```bash
spec-kitty sync opt-out
```

Opt-out is an **immediate local barrier**: it advances and seals the consent
epoch, serializes with every in-flight transport, cancels work that has not
reached the transport-start barrier, waits for already-started work to record
its truthful bounded outcome under the old generation, and returns only when
no later network write or success record can begin.

- Locally captured rows are **sealed, not deleted**. Deletion remains the
  separate explicit `spec-kitty sync purge` / `sync gc` workflow.
- Remote revocation is attempted or queued, and the CLI distinguishes
  *acknowledged server revocation* from *locally complete, remotely pending*.
  Offline opt-out still stops all local egress immediately.
- A later re-opt-in starts a **new** epoch. Sealed, purged, and terminally
  refused rows are never silently resurrected.

## What the kill switch does — and does not do

`SPEC_KITTY_ENABLE_SAAS_SYNC` is a **deny-only** emergency control:

- **Unset or disabled**: no hosted egress happens for any project on the
  machine, regardless of recorded grants. Local project-isolated capture
  continues, and recorded decisions are untouched.
- **Enabled**: nothing is granted. Arming the switch is *not* consent — every
  project still needs its own explicit opt-in, and enabling the switch for a
  machine full of unconsented projects sends nothing.

No value of the switch can create, copy, revive, or delete a project grant.

**Where to set it.** A shell `export SPEC_KITTY_ENABLE_SAAS_SYNC=1` arms every
project that shell subsequently touches — there is no project-scoped shell
form. To scope the switch to exactly one checkout, set it in that repo's
`.kittify/.kitty.env` instead:

```bash
# .kittify/.kitty.env — this checkout only
SPEC_KITTY_ENABLE_SAAS_SYNC=1
```

The pre-import loader seeds this before any `spec-kitty` module is imported,
so behavior is identical to exporting it — just resolved from a file whose
scope you control per repo, instead of a shell session whose scope you don't.
See [Environment Variables Reference § The `.kitty.env`
file](../api/environment-variables.md#the-kittyenv-file) and [ADR: operator
config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md).
Even scoped this way, the switch remains deny-only and grants nothing by
itself — per-project consent (`sync opt-in`) is still required.

## How admission pairs with the SaaS boundary

Egress for a batch requires **all four** of, evaluated against one immutable
per-operation project context:

1. the kill switch armed,
2. a current local project grant (current consent generation/epoch),
3. a ready exact target binding (server origin, authenticated account,
   canonical Private Teamspace), and
4. that binding's **current SaaS admission generation** — an opaque value the
   server issues per `(target, account/Private Teamspace, project_uuid)`.

Local consent and server admission are independent recurrence-prevention
layers: the CLI proves it only ever *sends* admitted projects, while the SaaS
admission boundary independently *refuses* non-admitted writes server-side —
including from bypass or legacy clients the CLI cannot vouch for. Changing
the server URL, account, or Private Teamspace invalidates only the
target-scoped admission (the project must be readmitted for the new
audience); the project-wide local grant remains recorded. When the server
answers `project_not_admitted`, the affected row is **parked terminally** —
it is not retried as a transient failure and a later readmission does not
silently revive it.

## Migrating legacy shared state (operators)

Installations older than this model kept a shared journal, delivery ledger,
and offline/body queue mixing several projects' rows. The cutover is a
previewable, **copy-only**, idempotent partition of that state into
UUID-owned project stores. Migration never manufactures consent: migrated
refusals stay refusals, and every legacy grant requires a fresh explicit
opt-in.

```bash
# 1. Inventory the legacy sources (read-only, WAL-aware):
spec-kitty sync project-store-preview

# 2. Copy, verify, and atomically cut over (resumable after interruption):
spec-kitty sync project-store-migrate --source <legacy.db> --migration-id <id>

# 3. Check the durable migration phase without reopening legacy sources:
spec-kitty sync project-store-status

# 4. Inspect rows that could not be attributed safely (non-deliverable):
spec-kitty sync project-store-quarantine

# 5. Optionally disclose migrated sealed history — explicit, previewed,
#    confirmed, and idempotent; ordinary sync can never send sealed rows:
spec-kitty sync project-store-history
```

After cutover, live capture and delivery read **only** project stores. The
shared legacy stores become diagnostic/purge-only; a recognized running
daemon is quiesced through a protocol handshake, and any late write by an
old process is diagnosed as non-deliverable residue rather than delivered.
The retired shared-store `spec-kitty sync migrate` path refuses with
migration guidance pointing at the commands above.

Rows that are missing, malformed, conflicting, or identity-less land in the
named **quarantine** with diagnostics — no synthetic project assignment, and
no sender can drain them.

## Where the evidence lives

Coordinated acceptance for the consent program emits an immutable,
schema-versioned checksum manifest at:

```
build/evidence/project-sync-consent/<core-commit>/manifest.json
```

It binds the exact core and SaaS candidate commits, the canonical contract
digest (`contracts/cli-saas-current-api.yaml` from the explicitly attested
SaaS checkout — never an ambient sibling path), test and mutant results, raw
benchmark samples with runtime metadata, a SHA-256 for every raw artifact,
per-artifact producer ownership (`core` or `saas`, never overlapping), and
the retention coordinate. CI uploads the bundle as an immutable artifact
retained for at least 90 days
(`.github/workflows/project-sync-consent-evidence.yml`); release and tracker
closure records cite that persistent coordinate and checksum. The
per-criterion status is tracked in the mission's
`kitty-specs/per-project-sync-consent-ledgers-01KZKMQZ/acceptance-matrix.json`.

Two things the core evidence deliberately does **not** claim: it never
asserts the SaaS incident (`#585`) is closed, and the disposition of the
1,322 historical events remains a separate Human-in-Charge decision outside
this program's scope.

## Related reading

- [ADR: One Project UUID Owns One Sync Store and One Consent Decision](../adr/3.x/2026-08-09-1-project-sync-store-boundary.md)
- [ADR: Egress Consent Boundary](../adr/3.x/2026-08-04-1-egress-consent-boundary.md)
- [ADR: Operator config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
- [Team Kitty](../context/team-kitty.md) — the hosted surfaces removed in #6164 and what stays
- [Environment variables reference](../api/environment-variables.md)
