---
title: 'ADR 1 (2026-05-10): Deterministic Historical Mission-State Repair Identity'
description: 'Repairing legacy missions derives absent identifiers from a deterministic ULID seeded by on-disk mission material, and never rewrites an existing valid identity.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-05-10'
---

## Context

Historical `kitty-specs/` directories may predate `mission_id`. TeamSpace import
requires stable mission identity, but public migration must be safe in
distributed Git: two clones of the same historical repository must produce the
same repaired artifacts without consulting a server, a clock, or randomness.

New missions still use creation-time ULIDs as decided in
`2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md`. This ADR
only governs deterministic repair for historical missions that lack a valid
`mission_id`.

## Decision

Historical repair derives missing `mission_id` values deterministically from
repository-local mission material:

1. Existing valid `mission_id` values are authoritative and are never changed.
2. Missing or invalid IDs are replaced by `deterministic_ulid(seed)`, where the
   seed is JSON serialized with sorted keys from:
   - canonical mission slug,
   - `slug`,
   - `friendly_name`,
   - `created_at`,
   - `target_branch`,
   - `mission_type`,
   - first status-event `event_id`, when present,
   - first status-event `at`, when present.
3. When historical material is sparse, repair still uses deterministic defaults
   already written by the canonicalizer, including the mission directory name
   and the Unix epoch fallback for missing `created_at`.
4. The generated identifier must be ULID-compatible in shape: 26 Crockford
   Base32 characters accepted by the current `ULID_PATTERN`.
5. Timestamp bits are not interpreted as wall-clock time for repaired IDs. The
   full 128-bit value is derived from SHA-256 seed material, so the encoded
   prefix is deterministic hash material, not a chronological claim.
6. Fork behavior is content-based: two clones with byte-identical historical
   mission material produce the same repaired ID; forks that change seed
   material before repair can produce different repaired IDs. Once a valid
   `mission_id` exists, later forks preserve it unchanged.

## Consequences

- Repair is reproducible across clones and CI runners.
- Repair does not need hosted TeamSpace, tracker, auth, or sync configuration.
- Sparse historical missions remain repairable, but the manifest and audit
  output show what was defaulted.
- Operators must coordinate the repair commit before TeamSpace import so forked
  branches inherit the same persisted `mission_id`.

## Confirmation

This ADR is implemented when tests prove:

- two cloned historical fixtures produce byte-identical repair diffs;
- running repair twice yields no second diff;
- existing valid IDs are preserved;
- divergent pre-repair seed material produces different deterministic IDs;
- TeamSpace dry-run refuses audit-blocking historical shapes before import.
