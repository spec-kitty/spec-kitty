---
title: 'ADR: No Legacy-Compat Branches in Resolvers — Require Canonical Identity, Migrate Legacy'
description: 'Resolvers never grow a legacy branch to rescue degraded input: make the field nullable or migrate the data, and fix stale fixtures instead of the product.'
status: Proposed
date: '2026-07-01'
doc_status: active
kind: ADR
updated: '2026-07-01T00:00:00Z'
---

## Context and Problem Statement

The mission-identity model (083+) mints a canonical ULID `mission_id` for **every**
mission at `mission create`; `mission_id` is the sole runtime identity for lookup,
locking, and routing. Pre-083 missions are the only artifacts that can lack one, and
the sanctioned remedy for them is a one-time migration (`spec-kitty migrate
backfill-identity`), audited by `spec-kitty doctor identity`.

When a fix is provoked by an input that lacks its canonical field — most concretely a
mission with no `mission_id` — there is a standing temptation to make that degraded
input "just work" by adding a branch inside a **resolver** (identity resolution,
surface resolution, topology classification, mission-id resolution):

```python
mission_id = identity.mission_id or identity.mission_slug   # slug into a ULID field
# or
if identity.mission_id is None:
    <legacy fallback path>
```

Both shapes reintroduce exactly the split-brain the SSOT / dedup line of work is
removing (see the SSOT ADR family below). Each such branch is a *second* code path for
the same operation, permanently: it must be carried, tested, and kept in sync forever,
and it silently accepts a non-canonical value (a slug, an empty id) where a canonical
one is contractually required — the #2138 defect class.

**Motivating incident (PR #2277, reliability-papercut-sweep).** WP04 correctly made the
identity path *fail closed* — `mission_id` is a ULID or `None`, never a slug. CI then
surfaced two failures in shards the per-WP reviews had not run: `next` output that would
not parse as JSON, and a lifecycle event that never queued to the SaaS outbox — both for
scaffolds lacking a canonical identity. The tempting, reflexive read was "WP04's
fail-closed over-reached; add a `mission_id is None` branch to the resolver so the no-id
case works again." That branch is the anti-pattern this ADR forbids, and the guardrail
was issued **before** any fix was written.

Steered by the guardrail toward *require-canonical + migrate* (option 2 below), the
investigation then found the reflexive read was wrong: the two failures were **not** a
WP04 regression at all. They reproduce identically on the base commit and pre-date this
mission (introduced by the #2263 non-persisting-identity change), and their root was
**stale test fixtures** that never minted a project/mission identity. The correct fix was
to make the fixtures canonical-shaped — mint a real identity, exactly as `spec-kitty init`
does — with **zero product change and zero new resolver branch**. The principle both
prevented a wrong resolver fallback and produced the right fix.

## Decision Drivers

- **SSOT / no split-brain.** One canonical path per operation; a legacy branch in a
  resolver is a second authority for the same decision — the recurring N+1 bug family.
- **Fail-closed on the canonical contract**, not fall-open to a degraded value. A
  `mission_id` field must never hold a slug or an empty string.
- **Migration converts legacy once; a runtime branch carries it forever.** Cost belongs
  at the one-time migration boundary, not in every hot resolver.
- **Realistic, canonical-shaped fixtures.** Test data should mirror production (every
  mission has an id); an id-less fixture is not a supported runtime state to be
  accommodated, it is stale test data.

## Decision

**Do not add a legacy / missing-canonical-field branch to a resolver to make a degraded
input succeed.** When a resolver or a path fronting it encounters a missing canonical
identity, resolve it in this preference order:

1. **Remove an over-broad raise / make the field nullable** — *only* when the failure is
   an over-aggressive `raise` in a path that does not need the identity (e.g. an
   observability, output, or event-emit path). Letting the `mission_id` **field** be
   `None` is permitted; a nullable field is not a legacy branch and adds **zero**
   conditional logic to any resolver. The command must still run and the event must
   still emit, carrying `mission_id=None`.
2. **Require the canonical shape; fix the tests, not the product.** Update stale fixtures
   to mint a realistic ULID `mission_id` so they exercise the real canonical path. Where
   a test genuinely models a pre-083 legacy mission, it must assert a **clean,
   structured fail-closed error that points to `spec-kitty migrate backfill-identity`** —
   never silent success, never an ugly empty-output crash. "Allow only canonical
   identities + provide a migration" is an explicitly endorsed resolution.
3. **Forbidden:** `if <canonical field> is None: <legacy fallback>` (or the
   `<field> or <slug>` degrade) inside any resolver / surface-resolution /
   identity-resolution / topology seam. If a fix appears to need this, choose option 2.

The distinction is **where** the change lands: removing a raise or nulling a field in a
non-resolver path is fine; adding a conditional *inside a resolver* to accept a
non-canonical identity is not.

## Considered Options

- **A — Runtime legacy-compat branch (rejected).** `mission_id or slug`, or an
  `is None` fallback, in the resolver. Restores old behavior at the cost of a permanent
  second path and a slug leaking into a ULID field. This is the defect, not the fix.
- **B — Require canonical + migrate (chosen).** Fail closed on the contract; migrate
  legacy once via the existing `backfill-identity`; keep fixtures canonical-shaped.
- **C — Nullable field, no branch (chosen where applicable).** For paths that don't need
  the identity, stop raising and carry `mission_id=None`. Adds no resolver logic.

## Consequences

- **Positive:** resolvers stay single-path and handle-blind by contract; no slug ever
  lands in a `mission_id` field; the legacy cost is paid once at migration; fixtures
  document the real (id-bearing) production shape.
- **Negative / cost:** pre-083 missions must be migrated before they run cleanly (by
  design, with a clear error + command pointer); some stale fixtures must be updated to
  mint an id.
- **Enforcement (follow-up):** the prohibition on option-3 branches is a candidate for
  the AST call-site gate mechanism already used for resolution boundaries (see the
  single-authority-seam ADR) — a gate that flags `<field> or <slug>` and
  `if <id> is None` degrade patterns inside the resolver allowlist. Until then it is a
  review-time invariant and a recorded operator directive.

## Related

- `docs/adr/3.x/2026-06-26-1-single-authority-seam-and-call-site-gate.md` (resolution boundaries; AST call-site gate)
- `docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md` (topology single source of truth)
- `docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md`
- Mission Identity Model (083+); runbook `docs/migrations/mission-id-canonical-identity.md`
- Incident: PR #2277 (reliability-papercut-sweep) — guardrail issued against a resolver `mission_id is None` fallback; real root was pre-existing stale fixtures (#2263 non-persisting identity), fixed canonically. Defect class #2138 (slug-in-mission_id-field).
