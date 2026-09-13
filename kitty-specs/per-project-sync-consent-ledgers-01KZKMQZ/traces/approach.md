> Hostname cleanup: `retired-host.example` redacts the former Team Kitty hostname in historical evidence; the current endpoint is `https://team.spec-kitty.ai`.

# Approach Trace

## 2026-08-09 — Planning approach

1. Freeze the live connection, grant-writer, sender, result, and current-writer
   census. WP01 remains green: it supplies instrumentation, positive controls,
   and mutation-harness self-tests, while each implementing WP owns its red-first
   behavior assertion.
2. Introduce one UUID-owned `sync.db`, one connection-owning unit of work, one
   consent writer, sequenced capture epochs, and one early layout-generation
   authority/write-permit API.
3. Move every journal/ledger/outbox/body writer behind the project aggregate and
   require every current writer to acquire the layout permit immediately before
   insert, before migration begins.
4. Select the SaaS WP04 candidate through explicit checkout path, exact commit,
   and canonical contract SHA-256; move target interfaces/registry/exports into
   the project boundary and consume the pinned per-write admission contract.
5. Establish the durable attempt and cross-process transport/result lease first;
   then converge interactive transports and daemon/background paths in separate
   WPs; finally run one aggregate all-family revocation/crash matrix.
6. Partition legacy state through read-only WAL-aware snapshots, exact copy and
   verification, quarantine, and atomic advancement of the existing layout
   authority. WP10 owns migration/cutover only and does not edit WP04 writers or
   claim source disjointness.
7. Force the compound kill-during-response -> immediate opt-out -> late-recovery
   ordering. Opt-out must terminalize an orphan before returning, and late
   recovery cannot promote success or resend.
8. Coordinate acceptance in the explicit order SaaS WP04 -> core WP05 -> core
   WP06-WP09 plus reviewed SaaS WP02/WP08 -> core WP11. Core and SaaS
   evidence claims are non-overlapping.
9. Emit a schema-versioned immutable evidence bundle binding exact commits,
   contract digest, command/test/mutant results, raw benchmark artifacts,
   checksums, producer/claim ownership, retention coordinates, and issue-to-WP
   mappings before integration handoff.

Production `retired-host.example` remains read-only without separate authorization,
and the historical 1,322-event cohort remains outside this mission.
