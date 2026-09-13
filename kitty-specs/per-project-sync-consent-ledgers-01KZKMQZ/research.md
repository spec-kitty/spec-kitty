> Hostname cleanup: `retired-host.example` redacts the former Team Kitty hostname in historical evidence; the current endpoint is `https://team.spec-kitty.ai`.

# Research: Per-Project Sync Consent Ledgers

## Decision 1 — One transactionally coherent database per project

**Decision**: Resolve `get_runtime_root().base / projects / <canonical-uuid> / sync` from one strict canonical UUID parser. The directory owns one `sync.db` containing control, epoch/sequence, journal, attempt/result, outbox/body, target/admission-operation, history-action, and migration tables, plus `egress.lock` and non-sensitive reports. `ProjectSyncStore.unit_of_work()` is the only live connection/outer-transaction owner; component repositories receive it and may not connect or commit independently.

**Rationale**: A single SQLite transaction can bind capture, epoch assignment, delivery state, and control generation. Separate database files would recreate cross-component partial commits and make migration/cutover verification harder. A UUID-owned physical database closes the cross-project class even if a SQL predicate regresses.

**Alternatives rejected**:

- One machine-shared database with UUID columns: repeats #3030 containment rather than #3262 isolation.
- Multiple databases inside the project directory: physical isolation improves, but atomic control/journal/delivery transitions remain impossible.
- Path- or slug-owned stores: moves, aliases, clones, and collisions become security identities.

## Decision 2 — Existing consent module becomes the sole grant authority

**Decision**: Refactor `sync/consent.py` so one versioned project row in `sync.db` is the only local grant/refusal authority. Project config, checkout records, repo defaults, login, URL, target, machine indexes, and environment values cannot return grant. Legacy grant-writing flags such as checkout-only/default inheritance and consent-index backfill are removed or fail non-zero with migration guidance.

**Rationale**: Adding a new record while preserving old writers creates competing authorities. The architecture inventory must prove only the explicit project-store action can grant.

## Decision 3 — Capture epochs separate local durability from egress consent

**Decision**: Project-isolated local capture is allowed without hosted consent. Every row receives a monotonic store-local capture sequence atomically with epoch assignment. Explicit opt-in records the current inclusive tail and starts a new eligible epoch strictly after it; pre-consent and revoked-period epochs remain sealed. Opt-out seals but does not purge. Only a confirmed immutable HistoryDisclosureAction—exact row IDs, preview hash/count, source epochs, actor, idempotency key, and current authority generations—may send selected sealed rows. Ordinary selection cannot mint it.

**Rationale**: Local durability is not disclosure, but retroactively interpreting opt-in as consent for accumulated history is. Epochs make the boundary durable and testable.

**Supersession**: This replaces #3030 C-005/C-006 only where they require a shared live store or consent-gated local capture. #3030's default denial, consent-bearing batch, final transmit check, project predicate, purge, and terminal parking remain defense in depth.

## Decision 4 — Local consent and hosted admission have different scope

**Decision**: Local consent is project-wide. SaaS admission is separately keyed by canonical project UUID plus normalized server origin and authenticated account/canonical Private Teamspace, verified by the server-returned opaque binding audience or canonical authenticated metadata. Changing any identity invalidates eligibility without mutating local consent or redraining history. Admit/revoke/readmit is a durable operation outbox: persist immutable operation key, expected generation, audience tuple, and request state before I/O; retry the same key after uncertainty and retain the original result.

**Rationale**: Consent answers whether this project may use hosted sync; admission answers whether a particular authenticated destination currently accepts it. Letting target selection grant would reintroduce implicit consent.

## Decision 5 — Every outbound write carries project and admission proof

**Decision**: Event, mixed-batch item, WebSocket Event, LocalCommit, dossier/body, and history/preflight writes carry the source UUID and the target-scoped current admission generation defined by the SaaS-owned contract. Correlated `project_not_admitted` is terminal and parks only the affected write.

**Rationale**: Request-wide proof fails for mixed batches and multiplexed transports. The client cannot infer successful admission from an event channel or repository-share state.

## Decision 6 — Opt-out waits for truthful in-flight settlement

**Decision**: Every sender first commits a durable attempt with its transport-native idempotency identity, audience/generations, payload hash/reference, deadline, and reconciliation policy, then obtains a project-scoped cross-process transport/result lease and validates context before transport start. Opt-out cancels work not started, waits for started transport plus its genuine bounded result record, and inspects durable old-generation attempts whose process lease disappeared. Each orphan is reconciled with its original identity or irrevocably parked `terminal_unknown` before opt-out seals/advances and returns; a later recovery cannot promote that terminal state to success or resend. Remote revoke remains separately truthful.

**Rationale**: Discarding a genuine result lies about what crossed the boundary. An unlocked recheck or in-process mutex cannot establish the required happens-before relation across CLI and daemon processes.

## Decision 7 — Daemon hints can deny but never grant

**Decision**: Daemon discovery reads atomic per-UUID denial files under `<runtime-root>/projects/.deny-hints/`. The project unit of work publishes deny/revoke after commit and removes the hint after opt-in commit. The versioned schema has no grant value and a bounded TTL. Missing, expired, malformed, generation-mismatched, pending, or possibly granted entries open `sync.db`; a stale denial only delays liveness and is diagnosable.

**Rationale**: Treating discovery or cache as grant authority recreates the machine-global consent path. A narrowing hint provides the performance optimization without widening eligibility.

## Decision 8 — Migration is copy, verify, atomically cut over

**Decision**: ProjectSyncStore owns one machine layout-generation authority and writer API before migration work begins. Every current-version foreground/background journal, delivery, event-outbox, and body/offline writer calls that API immediately before insert; it either commits against the inventoried legacy generation or retries/redirects exactly once to the UUID-owned store when cutover wins. Under the same machine lock, migration quiesces recognized daemons through a versioned handshake, snapshots legacy SQLite through a strictly read-only/immutable connection or backup API with explicit WAL/SHM treatment, inventories exact logical IDs/status/attempt/target/timestamp/hash state, copies into staged project stores, verifies, and atomically records cutover. Live code never dual-reads. Unrecognized old binaries may create diagnosed non-deliverable residue only.

**Rationale**: Crash-safe copy preserves the only source evidence. Exact verification prevents status drift. A daemon protocol closes the old-writer window; unrecognized or post-cutover legacy writes become diagnosed non-deliverable residue.

**Fault model**: Hard-kill before/after daemon quiesce, source snapshot, staging, verification, marker publication, writer redirect, and restart. Add pause-before-legacy-insert and insert-before-cutover orderings plus an unrecognized-old-binary fixture. Every rerun converges without duplication, redelivery, or lost current-version capture.

## Decision 9 — ProjectSyncContext is an immutable capability

**Decision**: One context binds canonical UUID, verified store, consent epoch/generation, exact target/account/Private-Teamspace binding, admission generation, and kill-switch result. Every sender and local status mutation consumes that context or a store-derived capability; independently pairing A's journal with B's delivery/target is unrepresentable or rejected before I/O.

**Rationale**: Loose UUID/path/target arguments permit correct components to be combined incorrectly. The context keeps identity continuous through selection, transport, and result recording.

## Decision 10 — Proof is split between conforming and bypass clients

**Decision**: The real six-project CLI run proves only admitted A appears in HTTP/WebSocket request bytes. Separate bypass/legacy server tests submit B–F and prove typed refusal with zero side effects. A real stale-generation race lets the conforming CLI receive the refusal and verifies terminal parking.

**Rationale**: A correct client should never send ordinary unadmitted B–F payloads, so one scenario cannot honestly prove both client omission and server refusal.

## Decision 11 — Benchmarks are reproducible gates

**Decision**: Benchmark fixtures generate 100 deterministic UUID stores: 80 fresh deny hints and 20 authority reads. Record OS/filesystem/storage/CPU/Python/SQLite/commit/seed. Define warm as repeated scans in one process after fixture warm-up and process-cold as a fresh process without claiming OS cache eviction. Run 200 warm and 30 process-cold scans in randomized order, retain raw JSON samples/p95, and instrument opens so denied payload tables are never opened. CI is advisory; the documented local SSD profile is the release gate.

**Rationale**: A threshold without fixture, warm/cold definition, sample count, and open instrumentation is not repeatable evidence.

## Decision 12 — SaaS contract is upstream, pinned authority

**Decision**: After SaaS WP04 publishes the generated shape, core receives an explicit SaaS candidate checkout path and commit, reads `contracts/cli-saas-current-api.yaml` from that checkout, verifies the expected SHA-256 digest, and records path/ref/digest in its compatibility evidence. Ambient `../spec-kitty-saas` resolution, package version strings, and branch names are not authority. Use local/test SaaS or a dynamically discovered Upsun branch environment for mutation; `retired-host.example` is production and read-only absent separate authorization.

**Rationale**: Core cannot safely invent a server protocol, and production is not an acceptable candidate-branch test target.

## Decision 13 — Cross-repository evidence has one owner per claim

**Decision**: Core owns conforming-client request bytes, per-project local store/open isolation, stale-generation terminal parking, the project-discovery benchmark, and core mutation results. SaaS owns bypass/legacy refusal, zero server-side effects, admission overhead, tombstone precedence, and any authorized Upsun canary. A schema-versioned manifest binds exact core/SaaS/tombstone commits, the canonical contract digest, raw artifact checksums, CI/run coordinates, and retention metadata. Neither repository recreates the other's proof.

**Rationale**: Duplicated harnesses drift and can appear mutually confirming while exercising different commits. An immutable manifest makes the coordinated proof auditable without creating a second contract or touching production.

## Supply-chain disposition

No new dependency is planned. Reuse SQLite, `get_runtime_root`, existing cross-platform locking, and current transport libraries. Existing lockfile authenticity, lifecycle-script, and Node LTS gates remain in force.

## Adversarial evidence disposition

The pre-spec and post-spec squad findings are incorporated:

- **Accepted**: one SQLite database per UUID provides physical and transactional isolation.
- **Accepted**: a connection-owning ProjectSyncStore unit of work, not the filename alone, provides transaction coherence.
- **Accepted**: exactly one explicit grant writer; all legacy flags and records are non-granting.
- **Accepted**: local capture uses epochs; opt-in starts at the tail and opt-out seals without purge.
- **Accepted**: capture sequence and inclusive tail define both capture/opt-in orderings; history requires an immutable confirmed capability.
- **Accepted**: local consent is project-wide while SaaS admission is exact-target/account/Private-Teamspace scoped.
- **Accepted**: every project-bearing write carries its own UUID and admission generation.
- **Accepted**: opt-out cancels pre-start work and waits for truthful already-started settlement.
- **Accepted**: durable attempts and native idempotency/status reconciliation define hard-kill uncertainty.
- **Accepted**: the daemon cache is a narrowing-only deny hint and never a grant.
- **Accepted**: migration quiesces recognized old daemons, copies/verifies without source mutation, survives hard kills, and never dual-reads.
- **Accepted**: all current-version legacy writers participate in layout generation; source verification is a read-only logical snapshot with WAL/SHM semantics.
- **Accepted**: the layout-generation authority and writer API land with ProjectSyncStore before payload writers migrate; migration consumes that authority rather than introducing it late.
- **Accepted**: old post-cutover writes are non-deliverable residue.
- **Accepted**: the six-project evidence splits conforming-client omission, bypass refusal, and stale-generation parking.
- **Accepted**: core and SaaS own non-overlapping evidence sets tied by exact candidate commits and one contract digest.
- **Accepted**: kill-during-response followed immediately by opt-out is a required ordering; orphan attempts settle or become irrevocably terminal before acknowledgement.
- **Accepted**: benchmarks specify fixtures, repetitions, warm/cold treatment, hardware/runtime record, and store-open evidence.
- **Accepted**: deny hints have a physical atomic location, TTL, post-commit writer, and no grant representation.
- **Accepted**: #3030 is partially superseded while its egress defenses remain.
- **Accepted**: #3108/PR #3135 is separate and can narrow but never grant.
- **Accepted**: historical #585 data remains outside automation and cannot be silently remediated.
