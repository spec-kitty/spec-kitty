---
title: 'ADR: One Project UUID Owns One Sync Store and One Consent Decision'
description: 'Hosted-sync state is isolated by project UUID behind one ProjectSyncStore unit of work; ambient checkout, identity, target, or environment cannot select another project.'
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-08-09'
superseded_by: docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md
---

> **Superseded (2026-09-06)** by
> [`2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`](2026-09-06-1-convergence-retirement-and-client-repo-inversion.md).
> The `ProjectSyncStore` / `sync/project_store.py` boundary this ADR governs was deleted with the sync
> transport by the Convergence (#3881 / #3824). Retained as historical record.

## Context and Problem Statement

The hosted-sync implementation currently spreads one project's journal, delivery
ledger, delivery targets, body queue, legacy outbox, and consent index across
several SQLite files under a machine-global runtime root. Components open those
files directly and commit independently. The arrangement makes a correspondence
between rows rather than an ownership boundary between projects.

That correspondence failed during the #3030 confidentiality incident. A filter
defect selected records belonging to five never-opted-in projects alongside the
intended project's records. On 2026-07-27, **1,322** events from those projects
were delivered with 7,811 events from the consenting project. The server, login,
team, target, and transport were valid. The authorization question was answered
about one project while the shared store supplied another project's data.

This is not primarily a slug-collision defect. A path can move, a slug can be
reused, a login can cover many projects, a target can serve a whole team, and an
environment variable is machine-wide. None is a durable project identity. The
only isolation key for hosted-sync state is the canonical project UUID.

The current direct-open/direct-commit architecture also prevents one action from
being atomic. A result can be recorded in the ledger while the journal or body
queue update fails, or a target can change between selection and transmit. Tests
can validate each file independently and still miss an incoherent cross-file
attempt.

## Decision Drivers

* Confidentiality must not depend on every reader remembering a project filter.
* A grant must authorize exactly the UUID whose data is selected and sent.
* Selection, target resolution, final eligibility, and result recording need one
  transaction owner and one coherent project context.
* Existing #3030 protections remain security boundaries, not migration debris.
* Migration must preserve recoverability without sustaining two live truths.
* Refused historical data must remain locally inspectable and explicitly
  purgeable, without becoming eligible merely because it exists.

## Decision Outcome

### 1. One UUID owns one `sync.db`

Each canonical project UUID owns exactly one hosted-sync SQLite database:

```text
<runtime-root>/projects/<lowercase-hyphenated-uuid>/sync/sync.db
```

The database has a sibling `egress.lock` at
`<runtime-root>/projects/<lowercase-hyphenated-uuid>/sync/egress.lock`. The lock
serializes the final transport/cutover boundary for that same UUID; it is not a
machine-global substitute for project ownership.

The database holds that project's journal, delivery results, targets, body-upload
work, refusal/parking state, consent decision, and migration provenance. A project
slug may be stored as descriptive metadata but never participates in the path or
the key. Two checkouts with the same slug and distinct UUIDs necessarily open
different files. Two checkouts that truthfully carry the same UUID necessarily
address the same project store.

### 2. `ProjectSyncStore` is the unit-of-work boundary

`ProjectSyncStore.unit_of_work()` owns every live connection to a project's
`sync.db`, the outer transaction, schema/version checks, and repository objects
used inside that transaction. Journal, ledger, target, body-queue, and outbox
components receive a store-owned connection or cursor. They do not open the live
database and do not commit it.

One project-store action owns a hosted-sync attempt from request start through
result write. The attempt carries one immutable project UUID and a target snapshot.
It cannot pair project A's journal with project B's target, ledger, consent record,
or body queue. Nested components may use savepoints where needed, but cannot end
the outer transaction.

Direct SQLite access outside `ProjectSyncStore` is permitted only in the migration
reader, against a legacy snapshot opened read-only/immutable. That reader cannot
be used by live dispatch or write a legacy file.

### 3. Consent is a project-store decision, not ambient state

There is one authoritative consent decision for each project UUID, and the
explicit project-store action is its only grant writer. Project-local records and
the pre-existing UUID index are migration inputs until cutover; checkout defaults,
repository defaults, backfill inference, login state, host, target, project
discovery, aliases, the existence of rows, and a truthy environment variable are
not grants.

Legacy refusal records remain distinct from grants. Migration or reconciliation
may preserve or strengthen a refusal, but may not turn absence, unreadability, or
an inferred legacy default into permission. Machine-global arming can disable
transport globally; it cannot grant a project permission.

### 4. The #3030 egress boundary is preserved and strengthened

Per-project storage removes the cross-project selection class, but it does not
replace defense in depth. All of these #3030 properties remain required:

* consent-bearing batches carry the decision made for their own project UUID;
* SQL selection includes an explicit UUID predicate even inside a per-project
  file, so schema or path mistakes fail closed;
* every HTTP, WebSocket, daemon, foreground, reconnect, history-import, tracker,
  and generic SaaS sender performs a **final transmit recheck** against the
  canonical attempt context immediately before bytes leave the process;
* a refusal is terminal for that attempt and is parked with a structured reason,
  rather than retried as a transient transport failure;
* retained/refused records have explicit project-scoped and all-project purge
  operations with differential evidence.

Authentication proves who the operator is. Target resolution proves where a
request would go. Neither substitutes for consent by the project that owns the
payload.

### 5. Shared live stores are retired by copy, verify, and cutover

The migration is a three-stage operation:

1. **Copy:** open each legacy source as a read-only snapshot and copy attributable
   records into the destination UUID store. Unattributable or conflicting records
   are quarantined, never assigned by slug/path guesswork.
2. **Verify:** compare exact identifiers, counts, hashes/bytes where defined,
   consent/refusal semantics, delivery state, and cross-project differentials.
3. **Cutover:** atomically publish the project-store manifest/marker only after all
   required verification passes. Live code then reads and writes only the UUID
   store.

There is **no dual-read** and no dual-write interval. A run uses either the
verified project store or the pre-cutover legacy snapshot; it never merges answers
from both. Failure before cutover leaves the legacy snapshot authoritative and the
partial destination disposable/restartable. Failure after cutover is recovered
from the project store and migration audit, never by silently consulting legacy
state.

Legacy live stores are retired after verification and an explicit retention
window. Retirement is not deletion of evidence: migration provenance and operator
chosen backups make the operation auditable and recoverable.

### 6. Historical inspection is an explicit capability

Operators may need to inspect, export, reconcile, or purge historical local data.
Those actions are separate read-only or explicitly destructive capabilities; the
mere ability to inspect a legacy snapshot never makes it a live dispatch source.
This keeps forensic history available without reopening the shared-store boundary.

## Supersession and Relationship to #3030

This ADR **supersedes #3030's final consent-gated capture decision** and its
shared-live-store assumption, while preserving its egress policy. #3030's final
FR-002, amended NFR-005, and C-006 required an unconsented project never to reach
the shared journal. This mission deliberately changes that collection decision:
local capture may occur without hosted consent only inside the owning UUID's
store, where capture sequence and epoch assignment are atomic. Pre-consent rows
remain in sealed epochs and cannot become ordinary delivery candidates after a
later opt-in; only an explicit preview/confirm history capability can select
them. Shared journals and outboxes cease being live capture destinations.

The egress-consent ADR remains authoritative for the sender-side question. This
ADR makes the at-rest and transaction boundary match it: the record, consent
decision, target, and result all name the same UUID.

## Consequences

### Positive

* A missing filter cannot expose another project's records because that project
  has no rows in the opened database.
* Ownership is deterministic under checkout relocation, duplicate slugs, multiple
  logins, team-wide targets, and different environment configurations.
* One outer transaction makes delivery/result state coherent and testable.
* The connection, commit, consent-writer, sender, and local-writer censuses create
  ratchets: growth fails while migration-driven shrinkage is visible.
* Historical inspection remains available as a named capability rather than an
  accidental live fallback.

### Negative and operational cost

* Existing machines need a potentially long-running, restartable migration with
  disk-space preflight and verification evidence.
* Components that currently own SQLite lifecycle or commit behavior must accept a
  store-owned unit of work.
* Multi-project status/reporting must enumerate project stores rather than query
  one aggregate database.
* Incident response and support tooling must state which project UUID store was
  inspected; a slug-only report is insufficient.

### Risks retained deliberately

* A caller can still construct the wrong UUID context. The named sender matrix,
  coherent-attempt type, UUID SQL predicates, and final gate are independent
  checks against that failure.
* Filesystem permissions and local-disk confidentiality remain operating-system
  concerns. Per-project databases reduce correspondence risk; they do not encrypt
  local state by themselves.
* An explicit all-project historical operation is necessarily powerful and must
  remain visibly distinct from normal project-scoped operation.

## Rejected Alternatives

### Keep shared databases and add more UUID predicates

Rejected because one missed or widened predicate recreates the incident, and
independent commits still permit incoherent result state. UUID predicates remain
as defense in depth, not the primary isolation boundary.

### Partition by slug, repository path, checkout path, login, team, or target

Rejected because each is mutable, reusable, many-to-many, or ambient. None is the
identity of the project whose record is being sent.

### Make the machine-global environment flag a grant

Rejected because it cannot distinguish projects. It may arm or disable the
feature globally, but cannot express per-project permission.

### Use a shared database with one connection manager

Rejected because connection ownership would improve atomicity while retaining the
cross-project row pool whose filter failure caused the incident.

### Dual-read old and new stores during a compatibility window

Rejected because two authorities make absence/refusal ambiguous, hide incomplete
migrations, and allow a legacy record to re-enter the live path. Compatibility is
provided by deterministic copy/verify/cutover and an explicit read-only historical
capability instead.

## Scope Exclusions

This decision does not combine unrelated remediation merely because it touches a
nearby transport:

* #3108/PR #3135 remains separate work.
* The historical **1,322 SaaS events** incident classification and downstream
  handling remain **Human-in-Charge (HiC)** controlled. This ADR supplies local isolation
  and evidence mechanics; it does not decide notification, deletion, or any
  server-side legal/operational action.

No production call site changes are made by the WP01 evidence package. Later work
packages own the store implementation, schema, migration, component rewiring,
sender conversion, cutover gate, and operator documentation.

## Verification and Enforcement

WP01 establishes executable inventories rather than line-number allowlists:

* `tests/architectural/test_project_store_boundary.py` records qualified SQLite
  open, commit, and transaction-context sites, classifies legacy read-only and
  live debt, rejects growth, and exposes the final strict predicate.
* `tests/architectural/test_sync_writer_census.py` records grant writers and every
  legacy grant input while proving ambient operator state and a truthy environment
  are not permission.
* `tests/architectural/test_egress_consent_boundary.py` names request-start and
  result-write sites for every project-data sender, plus the current local writer
  inventory that later WPs must route through the store layout.
* `tests/sync/test_project_consent_incident_baseline.py` provides same-slug A/B
  fixtures, store-open and exact-byte spies, differential counters,
  cross-process barriers, coherent-context assertions, and synthetic mutants for
  the incident's four principal regression shapes.

The census baseline may shrink without being rewritten. New direct store owners,
grant writers, unnamed senders, or layout writers are failures. WP11 activates the
strict final-state predicate only after all migration work packages remove the
recorded debt.
