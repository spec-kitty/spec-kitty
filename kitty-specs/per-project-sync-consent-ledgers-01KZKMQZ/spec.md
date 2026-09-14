# Mission Specification: Per-Project Sync Consent Ledgers

**Mission Branch**: `feat/per-project-sync-consent`  
**Created**: 2026-08-09  
**Status**: Draft  
**Input**: Implement Priivacy-ai/spec-kitty#3262 as the CLI half of the consent-incident program: explicit per-project opt-in, physically separate project sync state, no default-on inheritance, and the global environment setting only as a deny-only kill switch. Consume the SaaS admission boundary tracked by Priivacy-ai/spec-kitty-saas#585. Historical disposition of the 1,322 already-ingested events remains a separate Human-in-Charge decision.

## Intent and scope

Hosted sync consent belongs to one immutable project identity, not to a login, service URL, checkout path, repository slug, remote URL, active target, or machine-wide switch. Each canonical `project_uuid` owns a physically isolated sync store containing its consent decision, event journal, delivery results and retries, body/offline queue, target binding, and migration/cutover metadata. No live operation for one project may open or mutate another project's store.

Local project-isolated capture is allowed without hosted consent so that offline durability is not coupled to commercial-service use. Each captured row belongs to a consent epoch. Opt-in starts a fresh eligible epoch at the current capture tail; older pre-consent or revoked-period rows remain sealed and are never automatically redrained. A separate explicit, previewed history action is required to include them. Hosted egress remains default-denied and requires the global kill switch, a current local grant, a ready exact target/account/Private-Teamspace binding, and that binding's current SaaS admission generation. This deliberately supersedes the shared-store capture restriction recorded by predecessor mission #3030 while preserving #3030's consent-bearing batches, final transmit checks, SQL identity checks, and terminal refusal handling as defense in depth.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep every project's sync state physically isolated (Priority: P1)

As a developer working on multiple projects, I want each canonical project UUID to own a separate sync store, so that an operation for one project cannot observe, acknowledge, retry, migrate, purge, or deliver another project's data even if filtering is defective.

**Why this priority**: Shared journals and delivery ledgers created the structural blast radius behind the consent incident; query predicates alone are containment, not isolation.

**Independent Test**: Create projects A and B on one machine, including identical slugs with different UUIDs. Trap all store opens while capturing, draining, acknowledging, migrating, and opting out A. Only A's deterministic store paths are touched, and an unfiltered query of A's databases cannot return B. Pause every current-version writer around the layout-generation check and prove it either commits to the inventoried legacy generation or redirects exactly once to the project store.

**Acceptance Scenarios**:

1. **Given** projects A and B with events on one machine, **When** their sync contexts are resolved, **Then** journal, delivery, body/offline, consent, target, and migration state resolve to distinct UUID-owned stores.
2. **Given** an operation scoped to A, **When** it captures, selects, sends, acknowledges, retries, migrates, diagnoses, or purges, **Then** it performs zero opens, locks, reads, writes, or deletes against B's stores.
3. **Given** the same repository slug but different project UUIDs, **When** stores are resolved, **Then** the projects remain distinct and no slug collision can merge their state.
4. **Given** two legitimate worktrees that share the same canonical project UUID, **When** they capture locally on the same machine, **Then** they use the same project-owned store and the same consent decision with safe concurrency.

---

### User Story 2 - Opt in explicitly without implicit inheritance (Priority: P1)

As a project owner, I want one clear project-scoped opt-in action, so that neither another checkout nor global configuration can silently enable hosted sync.

**Why this priority**: Consent must be attributable, explicit, and absent by default.

**Independent Test**: Combine truthy environment settings, login, a configured URL, route metadata, a repo-slug default, a path record, and an old UUID cache without running the new opt-in. The project remains denied. Run opt-in once and exactly one versioned project decision is recorded, even while offline or while the kill switch is off.

**Acceptance Scenarios**:

1. **Given** a project with no new-format decision, **When** the user logs in, configures `https://team.spec-kitty.ai`, enables the global environment setting, or shares a remote with a consented project, **Then** the project remains denied.
2. **Given** the global kill switch is off or the network is unavailable, **When** the user explicitly opts in, **Then** the local project grant is recorded and remote admission is reported as pending rather than discarding the decision.
3. **Given** an explicitly consented project, **When** the global kill switch is disabled, **Then** no egress occurs but the project decision remains recorded.
4. **Given** a fresh clone or re-initialized project with the same remote and a new UUID, **When** it starts, **Then** it is denied and receives a separate store.
5. **Given** only a legacy granting record, **When** the new resolver evaluates consent, **Then** it requires explicit re-consent and never promotes that record automatically.
6. **Given** rows captured before opt-in, **When** the user opts in, **Then** the command previews that excluded cohort, starts eligibility at the current capture tail, and sends no older row without a separate explicit history action.
7. **Given** a legacy grant-writing option such as checkout-only/default inheritance or consent-index backfill, **When** it is invoked, **Then** it returns non-zero migration guidance and creates no grant.

---

### User Story 3 - Stop egress predictably on opt-out (Priority: P1)

As a project owner, I want opt-out to be an immediate local barrier with visible remote-revocation status, so that no local sender can race my decision and offline failure cannot be mistaken for server acknowledgement.

**Why this priority**: Revocable consent requires a precise concurrency boundary across interactive, daemon, WebSocket, body, history, and tracker-hosted senders.

**Independent Test**: Exercise two orderings per sender with real transport and ledger seams. Work paused before transport is canceled by opt-out. Work already past the transport-start barrier must settle its bounded result/ledger lease before opt-out returns. After return, no network write or success record can begin or appear; another project continues. If SaaS is unreachable, only the revocation control action is retried.

**Acceptance Scenarios**:

1. **Given** a selected project batch, **When** opt-out increments the local consent generation before transport starts, **Then** the stale batch is refused locally and not acknowledged as delivered.
2. **Given** an active daemon outside every checkout, **When** project A opts out, **Then** the daemon stops opening or draining A while continuing consented project B.
3. **Given** SaaS is reachable, **When** opt-out requests remote revocation, **Then** the CLI records the acknowledged server generation and reports complete revocation.
4. **Given** SaaS is unreachable, **When** opt-out completes locally, **Then** local egress is stopped, remote revocation is visibly pending, and no claim of server-side completion is made.
5. **Given** a transport began before opt-out, **When** its acknowledgement arrives, **Then** opt-out waits for the truthful result to be recorded under the old generation before returning; genuine success is never discarded and cannot create later eligibility.
6. **Given** the user later opts in again, **When** a new consent epoch and target-scoped admission are established, **Then** stale, sealed, purged, and terminal rows are not silently resurrected.
7. **Given** pending locally captured rows, **When** opt-out completes, **Then** it seals rather than deletes them; explicit purge remains separate.

---

### User Story 4 - Migrate shared legacy state without granting consent (Priority: P1)

As an existing user, I want legacy shared state partitioned safely into project-owned stores, so that upgrading neither loses delivery history nor manufactures consent.

**Why this priority**: The current shared journal, delivery ledger, and offline/body queue contain mixed-project state and cannot remain on a live delivery path.

**Independent Test**: Seed a mixed shared store with A/B events, acknowledgements, retries, terminal refusals, malformed identities, and an injected interruption at each phase. The migration is previewable, crash-safe, repeatable, preserves exact identifiable row sets and status, leaves unknown rows in non-deliverable quarantine, and cuts live readers over exclusively to project stores.

**Acceptance Scenarios**:

1. **Given** identifiable legacy rows, **When** migration runs, **Then** each row and its delivery/body history move only to the store named by its canonical UUID with IDs and status preserved.
2. **Given** missing, malformed, conflicting, nil, or identity-less rows, **When** migration runs, **Then** they remain in a named local quarantine that no live sender can drain.
3. **Given** legacy refusals and grants, **When** consent records are migrated, **Then** refusals remain refusals while grants require a new explicit opt-in.
4. **Given** an interruption or rerun, **When** migration resumes, **Then** it neither duplicates nor redelivers rows and reports verifiable before/after identities, counts, and hashes.
5. **Given** cutover is complete, **When** any live capture or delivery path runs, **Then** it cannot open the shared legacy journal, ledger, or offline queue; those remain diagnostic/purge-only.
6. **Given** project A invokes opt-in, **When** migration is still needed, **Then** A's action cannot inspect, assign, delete, acknowledge, or migrate B's rows as a side effect.
7. **Given** a recognized daemon is running, **When** cutover begins, **Then** migration quiesces it through a protocol/restart handshake; any later old-style write becomes diagnosed non-deliverable residue and is never dual-read.
8. **Given** any current-version foreground, background, journal, event-outbox, or body/offline writer is paused before its insert, **When** layout cutover wins, **Then** the shared layout authority makes that same write retry or redirect exactly once; no writer may privately infer the active layout.

---

### User Story 5 - Use one project context across every sender (Priority: P2)

As a maintainer, I want all hosted senders to carry one immutable project sync context, so that current working directory, daemon scope, active target, or independently paired stores cannot redirect data.

**Why this priority**: The application has multiple transports and background drains; closing only `sync now` would leave alternate routes around consent.

**Independent Test**: For each sender, set the working directory and active target to project B while the envelope/task belongs to A. The decision, store, target, admission, and transport all follow A's canonical context, or the operation fails before network I/O.

**Acceptance Scenarios**:

1. **Given** direct dispatch, emitter WebSocket, daemon publish, event relay, body drain, final sync, reconnect flush, history import, tracker-hosted, and generic SaaS paths, **When** they attempt egress, **Then** each requires a matching immutable project context and current consent generation.
2. **Given** a journal from A and delivery ledger or target from B, **When** a caller tries to construct a live delivery operation, **Then** it fails before selection or network I/O.
3. **Given** the global daemon runs outside a checkout, **When** it enumerates projects, **Then** a narrowing-only cached denial may skip payload state, but every missing, stale, unknown, pending, or possibly granted entry opens and re-reads project-owned authority before eligibility; no cache entry grants.
4. **Given** target configuration changes, **When** a project next drains, **Then** target readiness is evaluated separately from consent and historical rows are not automatically redrained.
5. **Given** local consent for target/account/Private-Teamspace X, **When** any of those target attributes change to Y, **Then** local consent remains recorded but Y is ineligible until it has its own current SaaS admission.

---

### User Story 6 - Interoperate with SaaS admission and terminal refusal (Priority: P2)

As a user of hosted sync, I want the CLI to establish and use the SaaS project's admission generation and understand stable refusal, so that local consent cannot be confused with server authorization.

**Why this priority**: Core recurrence prevention must compose with the independent SaaS pre-write boundary.

**Independent Test**: Run a conforming real CLI with six local projects and prove only admitted A appears in request bytes. Separately use a bypass/legacy client to prove SaaS refuses B–F, and force a stale-generation race so the real CLI receives `project_not_admitted` and parks the affected row.

**Acceptance Scenarios**:

1. **Given** a recorded local opt-in and valid target, **When** admission is requested, **Then** the client stores the returned opaque server generation without treating the event channel as admission.
2. **Given** admission is pending or refused, **When** delivery runs, **Then** no event egress occurs and diagnostics name the required operator action.
3. **Given** SaaS returns `project_not_admitted`, **When** the delivery result is recorded, **Then** the event is parked terminally and not retried as transient.
4. **Given** tracker-specific Channel 2 permission is granted, **When** hosted-service consent is absent, **Then** tracker permission cannot grant or substitute for project sync consent.
5. **Given** a LocalCommit, body upload, event, or history/preflight write, **When** the client sends it, **Then** it carries the same source UUID and target-scoped admission generation required by the canonical contract.

### Edge Cases

- Same slug with different UUIDs, renamed repositories, symlinked/case-variant paths, and remote URL aliases never affect store or consent identity.
- Braced, dashless, uppercase, nil, missing, or malformed UUIDs are canonicalized once or rejected; they cannot create colliding stores.
- Storage tokens are deterministic ASCII on Linux, macOS, and Windows even when display names contain accented Latin or other non-ASCII characters.
- Corrupt, locked, partially migrated, or schema-incompatible stores fail closed and preserve source evidence.
- Concurrent worktrees sharing a UUID serialize migrations and consent-generation updates without losing locally captured events.
- An event captured before opt-in belongs to a sealed epoch and cannot enter ordinary delivery; only a separate explicit, previewed history action can include it.
- Disabling the kill switch never deletes the local grant or queue; enabling it never grants a project.
- Changing active target never makes another project's store eligible and never triggers implicit historical redelivery.
- Changing server URL, authenticated account, or canonical Private Teamspace invalidates only the target-scoped SaaS admission binding; it does not silently change project-wide local consent.
- A stale deny-only hint may delay liveness and must be diagnosable, but a cached or stale grant can never bypass opening project-owned authority.
- Re-opt-in behavior preserves terminal refusals, purges, and explicit user choices; it does not manufacture a retry backlog.
- Unknown legacy rows remain local and non-deliverable until a separate explicit Human-in-Charge disposition.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Canonical project identity | All sync storage, consent, routing, and delivery authority shall be keyed by one canonical immutable `project_uuid`. | High | Open |
| FR-002 | ProjectSyncStore boundary | Each project shall own one physically separate, transactionally coherent sync store containing consent, journal, delivery, body/offline, target/admission, epoch, and migration state; no live project operation may open another project's store. | High | Open |
| FR-003 | One consent authority | One versioned project-owned decision shall be the only local grant authority; path, slug, remote, login, URL, environment, target, store presence, and machine indexes shall never grant. | High | Open |
| FR-004 | Explicit offline-capable opt-in | The named opt-in action shall record an attributable project grant even when offline or while the global kill switch is disabled, then report remote admission as active, pending, or refused. | High | Open |
| FR-005 | Deny-only kill switch | `SPEC_KITTY_ENABLE_SAAS_SYNC` shall only suppress egress; no value shall create, copy, revive, or delete a project grant. | High | Open |
| FR-006 | Capture/egress separation | Project-isolated local capture may occur without hosted consent, while selection and every final transport require current project consent and matching project context. | High | Open |
| FR-007 | Separate target-scoped admission | Project-wide local consent shall be separate from a SaaS admission keyed by immutable resolved target identity, authenticated account/canonical Private Teamspace, and project UUID; target changes invalidate eligibility without granting or redraining. | High | Open |
| FR-008 | Local opt-out barrier | Opt-out shall serialize with each project transport/result lease, wait for already-started bounded outcomes to be recorded, advance/seal the consent epoch, and return only when no later network write or success record can begin or appear. | High | Open |
| FR-009 | Remote revocation truth | Opt-out shall attempt or queue SaaS revocation and distinguish acknowledged server revocation from locally complete but remotely pending state. | High | Open |
| FR-010 | Sender-context integrity | Every live sender shall consume one immutable project context whose UUID, store, consent generation, target, and server admission agree; mismatches fail before network I/O. | High | Open |
| FR-011 | Daemon isolation | Background discovery may use only a narrowing deny-only hint: denied/revoked may skip payload-store open, while missing/stale/unknown/pending/possibly granted must re-read project-owned authority; no hint, cwd, or machine index can grant. | High | Open |
| FR-012 | Legacy partition migration | A previewable, copy-only, idempotent migration shall partition identifiable shared journal, delivery, and offline/body state by canonical UUID, preserve exact identities/status, verify durably, and atomically activate a project-store-only cutover marker. | High | Open |
| FR-013 | Legacy quarantine | Missing, malformed, conflicting, and identity-less legacy rows shall remain in a named non-deliverable local quarantine with diagnostics and no synthetic project assignment. | High | Open |
| FR-014 | No legacy grant promotion | New-format refusals may be derived from legacy refusals, but every legacy grant lacking current explicit provenance shall require re-consent. | High | Open |
| FR-015 | Exclusive live cutover | After migration, live capture and delivery shall read only project stores; shared stores shall be diagnostic/purge-only with no dual-read delivery fallback. | High | Open |
| FR-016 | Stable SaaS refusal | The CLI shall consume correlated canonical SaaS `project_not_admitted` refusals for event, LocalCommit, body, and history/preflight writes and park affected work without transient retry. | High | Open |
| FR-017 | Structural diagnostics | Diagnostics shall report store identity, local decision, kill-switch state, target readiness, server-admission state, pending revocation, migration/quarantine state, and the blocking reason without secrets or payloads. | Medium | Open |
| FR-018 | Predecessor preservation | Consent-bearing batches, final transmit rechecks, project SQL identity predicates, purge, and terminal-refusal controls from #3030 shall remain as independent defense in depth. | High | Open |
| FR-019 | Cross-repository proof split | A conforming six-project CLI run shall prove only A appears in request bytes and shall own client-side terminal-parking evidence; separately attested SaaS evidence shall own bypass refusal and zero-server-side-effect proof, with neither repository duplicating or substituting for the other's evidence. | High | Open |
| FR-020 | Incident evidence separation | Core #3262 closure evidence shall not claim SaaS #585 is closed; historical disposition remains a separate Human-in-Charge gate. | High | Open |
| FR-021 | Consent epochs | Every captured row shall carry an epoch; opt-in starts eligibility at the current tail, opt-out seals the epoch without deleting rows, and re-opt-in never auto-eligibilizes older epochs. | High | Open |
| FR-022 | Explicit history action | Pre-consent, revoked-period, and other sealed rows may egress only through a separate previewed explicit history action under current consent, target, and admission. | High | Open |
| FR-023 | Legacy writer retirement | Checkout-only/default inheritance, consent-index backfill, and every other legacy grant writer/flag shall be removed or fail non-zero with migration guidance and shall create no grant. | High | Open |
| FR-024 | Old-process cutover safety | Migration shall quiesce recognized daemons through a protocol/restart handshake; post-cutover writes to legacy stores are diagnosed as non-deliverable residue and never read live. | High | Open |
| FR-025 | Truthful in-flight outcomes | A genuine result from a transport started before opt-out shall be recorded under its original generation before opt-out returns; it is never discarded or used to revive later eligibility. | High | Open |
| FR-026 | Connection-owned unit of work | One ProjectSyncStore unit-of-work shall own live SQLite connections and transaction boundaries; component-local live connections/commits shall be prohibited so control, epoch, journal, outbox, attempt, and result changes can be atomic. | High | Open |
| FR-027 | Durable admission operations | Admit/revoke/readmit shall persist an operation record before network I/O containing immutable key, action, expected generation, exact target/account/Private-Teamspace tuple, request state, and original server result so uncertain retries reuse the same key. | High | Open |
| FR-028 | Explicit history disclosure capability | A history action shall bind an immutable preview cohort/hash/count, source epochs, confirmation identity, current consent/target/admission generations, idempotency key, and terminal results; ordinary selection cannot mint or consume it. | High | Open |
| FR-029 | Migration-generation writer barrier | ProjectSyncStore shall own one layout-generation authority and writer API; every current-version legacy journal, delivery, event-outbox, body/offline, foreground, and background writer shall acquire/check it immediately before insert and retry or redirect safely; recognized old daemons shall quiesce, and unrecognized old binaries may create only diagnosed non-deliverable residue. | High | Open |
| FR-030 | Crash-aware transport attempts | Each transport shall persist its attempt before network I/O, use bounded timeout/idempotency or status reconciliation for uncertain outcomes, and recover after process death without inventing success or silently resending disclosed data. Opt-out shall reconcile, cancel, or irrevocably terminalize every orphaned old-generation attempt while holding the project barrier before it acknowledges; later recovery may not promote that terminal state to success. | High | Open |
| FR-031 | Stable admission audience | The client shall normalize server origin and persist a stable account/Private-Teamspace binding or opaque server audience returned by authenticated metadata; a generation is reusable only when that audience and project UUID match exactly. | High | Open |
| FR-032 | Monotonic capture sequence | Each local capture shall receive a monotonic store-local sequence in the same transaction as epoch assignment; opt-in records an inclusive tail and ordinary eligibility begins strictly after that tail. | High | Open |
| FR-033 | Candidate contract attestation | Core compatibility and acceptance shall consume an explicitly selected SaaS candidate checkout and commit, verify the canonical contract digest from that checkout, and record the path/ref/digest in evidence; ambient relative sibling paths or version strings shall not choose authority. | High | Open |
| FR-034 | Immutable closure evidence | Acceptance shall emit a schema-versioned manifest binding core/SaaS/tombstone commits, canonical contract digest, test and mutant results, raw benchmark artifacts, environment evidence when authorized, checksums, and retention coordinates; issue-matrix rows shall name their owning WPs. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Physical isolation proof | Store-open instrumentation shall observe zero cross-project file opens, locks, reads, writes, acknowledgements, schema operations, or deletes across the required A/B matrix. | Privacy | High | Open |
| NFR-002 | Migration fidelity | For identifiable data, before/after IDs, targets, delivery states, attempts, timestamps, and content hashes shall match exactly; subprocess termination before/after every durable phase and both layout-generation writer orderings for every current writer class shall add zero duplicates/redeliveries and leave sources unchanged. | Reliability | High | Open |
| NFR-003 | Revocation race proof | Per sender, real transport/ledger tests shall cover pause-before-start and start-before-opt-out: opt-out cancels the former, waits for truthful bounded settlement of the latter, and permits zero post-return write/success. | Concurrency | High | Open |
| NFR-004 | Mutation strength | Mutants that restore a shared store, grant from environment or repo defaults, remove the final consent check, or cross-pair project context shall each make named acceptance tests fail. | Test integrity | High | Open |
| NFR-005 | Cross-platform identity | Project store resolution shall produce deterministic ASCII-safe paths and pass the identity matrix on Linux, macOS, and Windows, including accented and non-ASCII display names. | Portability | High | Open |
| NFR-006 | Performance | On the documented local SSD profile, 200 warm scans of 100 projects (80 valid deny hints, 20 authority reads) shall complete within 500 ms p95; 30 fresh-process scans shall complete within 1 s p95; raw randomized samples shall be retained and no denied payload table may open. | Performance | Medium | Open |
| NFR-007 | Credential and payload safety | Diagnostics, migration reports, logs, fixtures, and errors shall expose zero access tokens and zero raw event bodies outside their owning project store. | Security | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Supersede shared-store non-goal | This mission explicitly supersedes predecessor #3030 C-005/C-006 where they preserve shared live stores or forbid project-owned local capture; the reason and replacement boundary must be recorded in an ADR/Decision Moment. | Architecture | High | Open |
| C-002 | Preserve #3030 safety | Default denial, consent-bearing selection, final transmit checks, identity filtering, terminal parking, and purge behavior remain mandatory defense in depth. | Compatibility | High | Open |
| C-003 | No implicit consent | Repo slug, checkout path, remote URL, login, configured host, target readiness, daemon startup, or environment variables shall never create consent. | Privacy | High | Open |
| C-004 | Canonical hosted contract | Admission and refusal behavior shall consume `contracts/cli-saas-current-api.yaml` from the explicitly attested SaaS candidate checkout; core shall not use an ambient sibling path or define an incompatible parallel contract. | Architecture | High | Open |
| C-005 | Tracker Channel 2 separate | Core #3108/PR #3135 remains separate; its tracker permission may narrow egress but can never grant hosted-service consent. | Scope | High | Open |
| C-006 | Historical events excluded | This mission shall not inspect, delete, move, reassign, or decide the disposition of the 1,322 historical SaaS events. | Operational | High | Open |
| C-007 | No production mutation | Implementation, testing, review, and retrospective shall use local/test environments and shall not alter production configuration, data, consent, or admission state. | Safety | High | Open |
| C-008 | No silent compatibility fallback | Old shared stores and legacy consent records may support diagnosis, explicit migration, or purge only; they shall never silently re-enter live delivery. | Architecture | High | Open |
| C-009 | No automatic opt-out purge | Opt-out seals eligibility but does not delete captured events or bodies; deletion requires the existing explicit purge workflow. | Data lifecycle | High | Open |
| C-010 | Admission target identity | An opaque server generation is valid only for the exact resolved server, authenticated account/canonical Private Teamspace, and project UUID that produced it. | Security | High | Open |

### Key Entities

- **Project sync store**: One transactionally coherent physical hosted-sync boundary for one canonical UUID, holding consent/epochs, target/admission, journal, delivery, body/offline, and migration state.
- **Project sync context**: An immutable operation-scoped binding of project UUID, store identity, consent epoch/generation, exact target/account/Private-Teamspace binding, and SaaS admission generation.
- **Project consent decision**: A versioned, attributable local grant or refusal written only by an explicit project action.
- **Target binding**: The hosted destination for a project; necessary for delivery but never a consent source.
- **SaaS admission**: The independent server authorization for `(team, project_uuid)`, represented locally by an opaque current generation and state.
- **Legacy quarantine**: A non-deliverable store for rows that cannot be attributed safely during migration.
- **Discovery index**: Optional non-authoritative metadata used to find project stores; it can never grant consent or supply the decision itself.
- **Consent epoch**: A capture interval whose rows share an eligibility generation; denied and revoked periods are sealed and never automatically redrained.
- **Deny-only hint**: Non-authoritative discovery metadata that may suppress work only; it can never assert a grant.
- **Admission operation**: Durable admit/revoke/readmit request identity and original server result for uncertain retry.
- **History disclosure action**: Immutable previewed and explicitly confirmed sealed-row cohort; ordinary selection cannot create it.
- **Delivery attempt**: Durable pre-I/O record carrying native idempotency, authority generations, bounded deadline, and reconciliation state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For two projects on one machine, every capture, delivery, acknowledgement, migration, diagnostic, purge, and opt-out test observes zero access to the other project's sync stores.
- **SC-002**: Every combination of login, host configuration, target, repo/path legacy records, old UUID cache, daemon state, and global environment setting leaves an unconsented project denied; only the explicit new opt-in creates a grant.
- **SC-003**: Mixed-store migration preserves 100% of attributable event identities and delivery states, quarantines 100% of unknown identities, and remains idempotent after injected interruption at every phase.
- **SC-004**: Across all sender classes, pre-start work is canceled, already-started work settles truthfully before opt-out returns, and zero new network writes or success records occur afterward while another project continues.
- **SC-005**: The global flag suppresses 100% of hosted egress when disabled and grants zero projects when enabled.
- **SC-006**: A conforming six-project run sends only A and records client-owned exact-byte/parking evidence; an attested SaaS candidate independently refuses B–F with zero server effects. A shared manifest binds both proof sets to exact commits and one canonical contract digest without duplicating evidence ownership.
- **SC-007**: Each required shared-store, implicit-grant, missing-final-gate, and cross-context mutant causes a named test to fail.
- **SC-008**: Core #3262 has implementation, contract, test, and review evidence, while SaaS #585 remains explicitly gated on the Human-in-Charge's historical-event disposition.
- **SC-009**: Initial opt-in, opt-out, target change, and re-opt-in demonstrate zero automatic eligibility for pre-consent, revoked-period, old-target, purged, or terminal rows.
- **SC-010**: The legacy grant-writer inventory contains zero callable path that can create a grant outside the project-store command; every removed or blocked flag has an executable negative test.
- **SC-011**: Connection instrumentation finds zero component-local live `sqlite3.connect()` calls, and transaction fault tests prove control/epoch/journal/outbox/attempt/result changes cannot partially commit.
- **SC-012**: Killing each sender before send, during response, and before result commit converges through the persisted attempt/idempotency protocol without false success or duplicate disclosure; kill-during-response followed immediately by opt-out terminalizes or reconciles the orphan before acknowledgement, and a late recovery cannot record success afterward.
- **SC-013**: Capture-versus-opt-in in both transaction orderings proves rows at or below the recorded tail remain sealed and rows strictly after it enter only the new eligible epoch.
- **SC-014**: Foreground legacy writers paused before insert or completing before cutover are redirected or migrated exactly once; an unrecognized old binary's late write is diagnosed and never delivered.

## Dependencies and assumptions

- Every participating repository has a canonical immutable `project_uuid`; two worktrees with that same UUID represent one logical project and share one machine-local project store.
- The companion SaaS mission `project-sync-admission-boundary-01KZKMQ7` completes WP04 first and exposes an explicit candidate checkout/ref plus the digest of its generated `contracts/cli-saas-current-api.yaml`; core WP05 records and consumes that exact authority.
- Coordinated acceptance begins only after the core transport/revocation packages and the reviewed SaaS WP02 anti-rematerialization plus WP08 server/effect boundaries are present on named candidate commits. Core owns conforming-client bytes, local isolation, and terminal parking; SaaS owns bypass refusal, zero server effects, hosted performance, and any authorized Upsun canary.
- SaaS admission is bound to the exact resolved server, authenticated account/canonical Private Teamspace, and source UUID; local consent remains project-wide when target attributes change.
- Predecessor #3030 remains the defense-in-depth baseline except where this mission explicitly supersedes its shared-store and capture-coupling decisions.
- The global environment setting remains available for emergency deny-only control, but users can record project consent while it is disabled.
- Cross-repository acceptance may add or update the end-to-end-testing repository if the existing harness cannot prove the six-project matrix.
- Historical #585 remediation is unavailable to automation until the Human-in-Charge records a disposition; it does not block core recurrence prevention but does block closing the SaaS incident.

## Out of Scope

- Deleting, moving, inspecting, or approving retention of the 1,322 historical SaaS events.
- Using repository slug, checkout path, remote URL, or current working directory as a security identity.
- Automatically granting a fresh clone or new UUID because another checkout is consented.
- General tracker connector redesign or completion of core #3108/PR #3135.
- Restoring retired shared-queue senders or shared-store delivery compatibility.
- Automatically redraining historical rows when a target changes or a project opts in again.
- Silently deleting locally captured rows during opt-out; explicit purge remains separate.
- Production deployment or production data/configuration mutation.
