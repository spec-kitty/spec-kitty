---
title: 'Sync-Drain Runbook: the 3-Gate Order and the Doctor False-Green Trap'
description: 'Work the 3-gate sync-drain order (flag/consent, auth, teamspace) and avoid the `sync doctor` false-green trap.'
doc_status: deprecated
updated: '2026-08-31'
related:
- docs/operations/internal-hosted-readiness.md
- docs/operations/logged-out-teamspace.md
- docs/operations/recovery-index.md
- docs/api/environment-variables.md
- docs/architecture/team-kitty-saas.md
---

# Sync-Drain Runbook: the 3-Gate Order and the Doctor False-Green Trap

> **Status (2026-10-06):** Team Kitty is no longer actively supported
> ([ADR 2026-10-06-1](../adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md)).
> This page describes code that still ships but is off by default; do not build
> toward it unless the operator asks for hosted work.


> **Removed in 3.2.6; kept as historical record.** The CLI→SaaS sync transport
> described here is gone. This page is scheduled for deletion in 3.2.7.

An event captured locally does not ship to a Teamspace until it clears three
gates, evaluated **in this order** by the drain (see
[`_classify_drain_blocked_reason`](https://github.com/Priivacy-ai/spec-kitty/blob/main/src/specify_cli/sync/emitter.py)
in `src/specify_cli/sync/emitter.py`, `DRAIN_BLOCKED_REASONS`). The order is
deliberate: an operator whose checkout is opted out should see "the checkout
is opted out" (gate 1), not a downstream symptom like "no Private Teamspace"
(gate 3).

**To find which gate is blocking an event, run `spec-kitty sync status` (Event Sync section) or `spec-kitty sync doctor` (Per-Project Event Journal block).** The three reason tokens live in `DRAIN_BLOCKED_REASONS`; a "Drain Blockers" renderer (`_render_drain_blockers`) exists but is not yet wired into any command, so don't look for that table in `sync status`.

## Gate 1 — is hosted sync on, and does this project consent?

This gate is already documented — cite it, do not restate it:
[Internal Hosted-Readiness Mode](internal-hosted-readiness.md) (L35–158)
covers `SPEC_KITTY_ENABLE_SAAS_SYNC` (the rollout flag — **not**
`SPEC_KITTY_ENABLE_SAAS_SYNC_ENABLED`, no such variable exists) and
`spec-kitty sync doctor` as the diagnostic entry point.

The one addition specific to the drain: gate 1 also fails when the flag is on
machine-wide but *this event's own project* has not consented to hosted sync.
Both failures render as the same blocked reason, `saas_disabled`. Consent is
per project:

```bash
spec-kitty sync opt-in     # record consent for this checkout
spec-kitty sync opt-out    # withdraw it
```

(Some in-repo messages point at a `sync enable` command — that command does
not exist; the real one is `sync opt-in`.)

## Gate 2 — is this machine authenticated?

Blocked reason: `missing_auth`. No valid session (access or refresh token) is
on hand, so the drain cannot ship to a Teamspace even though it wants to.

```bash
spec-kitty auth login
```

## Gate 3 — does the session resolve a Private Teamspace?

Blocked reason: `missing_team`. The operator is authenticated, but the
strict Private-Teamspace resolver returned nothing for this event, so
ingress refuses the batch rather than routing it somewhere unintended. This
is the same "no Private Teamspace available" state
[Internal Hosted-Readiness Mode](internal-hosted-readiness.md#readiness-states-the-coordinator-surfaces)
lists as a readiness bucket; remediation is to refresh Teamspace membership
in the dashboard. If the CLI session itself is logged out on a *connected*
Teamspace (a distinct state from "no Teamspace at all"), see
[Recovery: Logged out on a connected teamspace](logged-out-teamspace.md).

Each blocked reason is re-evaluated on every drain tick, not cached — an
event stuck on `missing_team` today ships automatically once the Teamspace
resolves, with no re-emit required.

## The `sync doctor` false-green trap

`spec-kitty sync doctor`'s **Queue size** row reads
`OfflineQueue().get_queue_stats()` — a legacy, machine-local queue store.
That store can read `0 / <max> (0%)`, in green, while the **canonical event
journal** — the store the drain actually dispatches from — holds a real
backlog. This is not hypothetical: it is the exact shape of the 2026-07-27
incident, where `doctor` reported a healthy empty queue while 9,133 events
sat in the journal, 1,322 of them from projects that had never opted in.

Two sections exist specifically so this cannot happen silently again:

- **`sync doctor`**'s **Per-Project Event Journal** block, rendered
  immediately below the Queue Health table, reads the journal itself and
  reports per-project composition and consent state. It answers "whose data
  is actually in here?" — a question the Queue-size row cannot answer.
- **`spec-kitty sync status`**'s **Event Sync** section reports `Retained
  events` and `Delivered (cur/prev)`, both sourced from the same
  journal-backed report, independent of the legacy queue.

**Never trust "Queue size: 0" alone.** If `doctor`'s Queue size disagrees
with the Per-Project Event Journal block or with `status`'s `Retained
events` / `Delivered (cur/prev)` rows, treat the disagreement as the finding
— investigate before you conclude sync is caught up.

## A name you may see and can ignore: `sync migrate`

`spec-kitty sync migrate` is **not** part of the day-to-day drain. It is the
retired shared-store→per-project migration path; the command now refuses
unconditionally and points at the explicit, scoped
`sync project-store-preview` / `sync project-store-migrate` pair instead. If
older notes describe a "gate 2: run `sync migrate`" step, that description
no longer matches the shipped drain order above — gate 2 is authentication,
not this command.

## `SPEC_KITTY_HOME` and the drain

`SPEC_KITTY_HOME` repoints the whole runtime state root — including the
offline queue, the event journal, and the sync daemon's owner record (see
[Environment Variables Reference](../api/environment-variables.md#spec_kitty_home)).
If the shell running `sync doctor` / `sync status` has a different
`SPEC_KITTY_HOME` than the shell (or daemon) that is actually draining
events — for example, one shadow-clone checkout diagnosing against another's
state root — the diagnostic reads an entirely different queue and journal
than the one with the backlog. The drain will look idle or empty simply
because you asked the wrong store. Confirm `SPEC_KITTY_HOME` (or its
default, `~/.spec-kitty`, when unset) matches between the daemon and the
diagnostic shell before trusting either reading.

`SPEC_KITTY_HOME` also locates the home-tier `.kitty.env` file
(`${SPEC_KITTY_HOME}/.kitty.env`) — a different `SPEC_KITTY_HOME` between two
shells means each one reads a *different* `.kitty.env` too, not just a
different state root. Run `spec-kitty doctor env-file` alongside `sync
doctor` to see which tier is actually supplying gate-relevant vars like
`SPEC_KITTY_ENABLE_SAAS_SYNC` in the shell you are diagnosing from.

## Related

- [Internal Hosted-Readiness Mode](internal-hosted-readiness.md) — gate 1's
  home: `SPEC_KITTY_ENABLE_SAAS_SYNC`, `sync doctor`, readiness states.
- [Recovery: Logged out on a connected teamspace](logged-out-teamspace.md) —
  the gate-3-adjacent logged-out recovery path.
- [Environment Variables Reference](../api/environment-variables.md) —
  `SPEC_KITTY_HOME`, `SPEC_KITTY_ENABLE_SAAS_SYNC`, and [The `.kitty.env`
  file](../api/environment-variables.md#the-kittyenv-file) for setting either
  once instead of per-shell.
- [Team Kitty (SaaS) architecture](../architecture/team-kitty-saas.md) — how
  this drain fits into the full opt-in → sync flow.
- [Recovery guides](recovery-index.md)
