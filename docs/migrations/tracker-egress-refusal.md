---
title: 'Migration: Tracker Egress Refusal'
description: 'Why every existing beads/fp tracker binding now needs a recorded consent decision, what the two channels are, and how to remediate each refusing state.'
doc_status: active
updated: '2026-08-04T00:00:00Z'
related:
- docs/migrations/index.md
kind: How-To
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: Tracker Egress Refusal

**Status**: Shipped with mission `tracker-egress-refusal-3108-01KYWF1R`.
**Issue**: [Priivacy-ai/spec-kitty#3108](https://github.com/Priivacy-ai/spec-kitty/issues/3108)
**Audience**: Operators with an existing `beads`- or `fp`-bound project
(`spec-kitty tracker bind --provider beads` / `--provider fp`) upgrading past
this mission.

## What Changed and Why It Breaks You

Before this mission, a `beads` or `fp` tracker binding reached the tracker
binary with **no consent question asked at all**. `LocalTrackerService` held
zero consent references, so `spec-kitty tracker sync pull` / `push` / `run`
shipped issue titles, bodies, labels and assignees as `argv` of an
operator-named executable even on a project whose committed
`.kittify/config.yaml` said `sync: {enabled: false}` — the hosted-sync refusal
did not stop the local one, because nothing local was ever gated.

That gap is now closed, and closing it is a **breaking change**: a local
tracker binding now requires a **recorded decision at one of two consent
channels**, and **absence of both channels denies**. If your project has
never recorded hosted-sync consent (no `sync.enabled`, no
`spec-kitty sync opt-in`) and has never recorded a `tracker.egress` decision,
`sync pull` / `sync push` / `sync run` on that binding **stop working on
upgrade** until you record one of the two. Nothing about your binding itself
changed — the `tracker:` block, the provider, the workspace, the mapped
issues, are all untouched. Only the consent decision is new, and it is
mandatory.

## The Two Consent Channels, and What Absence Means at Each

Two channels are consulted, and they are **not parallel switches** — absence
means something different at each one:

- **Channel 1 — hosted-sync consent.** The existing consent chain, recorded
  via `sync.enabled: true` in this project's own `.kittify/config.yaml`, or by
  running `spec-kitty sync opt-in`. Keyed on this project's identity.
  **Absence denies.**
- **Channel 2 — `tracker.egress`.** A new key in the `tracker:` block of this
  **project's own committed** `.kittify/config.yaml`. It holds **exactly one
  of two strings**: `refused` or `permitted`. **Absence is the key being
  missing** — nothing is recorded, and the decision **defers to Channel 1**
  instead of denying on its own.

  ```yaml
  tracker:
    egress: permitted   # or: refused
  ```

  A malformed `tracker:` block — `tracker: "yes"`, `tracker: [a, b]`,
  `tracker: 3`, or a bare `tracker:` with nothing under it — is treated as
  **absence, not a fault**: the block is not the key, so the key is simply
  missing and Channel 2 still defers to Channel 1.

Absence of **both** channels denies. Recording a decision at either one is
enough to stop the refusal — you do not need both.

**The coercion this two-way design removes.** Both routes to a Channel-1
record — hand-authoring `sync.enabled: true`, or running
`spec-kitty sync opt-in` — grant **hosted-sync** consent, nothing narrower.
Without a Channel-2 grant that stands on its own, the only way to keep a
`beads`/`fp` binding alive after this upgrade would have been *"consent to
hosted sync, or lose your local tracker."* That is not what this mission
ships. Recording `tracker.egress: permitted` keeps your local tracker binding
working and grants **nothing** to anyone else — the subprocess it authorizes
is the one already named in your own machine-global tracker credential file,
never spec-kitty's hosted service. You record one key in a file you already
own, and you consent to hosted sync exactly as much as you did before writing
it: not at all, unless you separately say so.

## How to Tell Which Channel Is Refusing You

Run:

```bash
spec-kitty sync doctor
```

Every checkout prints a **Tracker egress** block with **one row per
destination** — the local subprocess destination (`beads`/`fp`) and the
hosted service destination (`jira`/`linear`/`github`/`gitlab`) — naming which
channel is refusing on each row, plus the exact remedy text. Check this
first, before guessing.

`sync doctor` is the diagnostic surface for this, deliberately, rather than a
`spec-kitty tracker`-side command: the `spec-kitty tracker` command group is
**conditionally registered** and does not exist at all unless hosted SaaS
sync is armed on the machine (`SPEC_KITTY_ENABLE_SAAS_SYNC=1`). A
`tracker`-side diagnostic would be unreachable in exactly the configuration
where an operator refusing hosted sync most needs it. `sync doctor` has no
such precondition.

## The Three Channel-1 States and Their Remedies

Channel 1 can be in exactly one of three states, and each has its own,
distinct remedy:

| Channel-1 state | Meaning | Remedy |
|---|---|---|
| **No record** | Nothing was recorded for this project at Channel 1. | Record `sync.enabled: true` in this project's own `.kittify/config.yaml`; **or** run `spec-kitty sync opt-in`; **or** record `tracker.egress: permitted` (needs no project identity). |
| **Recorded refusal** | A Channel-1 refusal exists (for example, a committed `sync: {enabled: false}`). | Change the recorded decision to `sync.enabled: true`; **or** record `tracker.egress: permitted`. |
| **Not consentable** | This checkout has no project identity at all, so hosted-sync consent cannot be recorded for it. | Run `spec-kitty init` in this checkout first — see the next section; **or** record `tracker.egress: permitted`, which needs no identity at all. |

**Record `tracker.egress: permitted` is the only remedy that works in every
one of these three states without a project identity.** If you want the
shortest path back to a working local binding and do not want to think about
which of the three states you are in, this is it.

## The Identity-less Checkout

This state deserves its own callout, because the hosted refusal text still
points an identity-less checkout at the wrong command.

If `spec-kitty sync opt-in` fails, or you hand-author `sync.enabled: true`
and the binding **still** denies, this checkout has no project identity —
there is no `project.uuid` for a consent decision to attach to. In this
state, **`sync.enabled: true` on its own does nothing**: Channel 1 cannot
record a decision for a project that does not yet have an identity to record
one against.

The remedy is **`spec-kitty init`**, run in this checkout, which mints that
identity. Once it exists, the "no record" remedies above become available —
record `sync.enabled: true` or run `spec-kitty sync opt-in`. Or skip identity
entirely and record `tracker.egress: permitted`, which needs no project
identity at all and is the faster path if hosted sync was never something you
wanted.

Without this state named on its own, the operator-facing advice would tell
this checkout to do exactly what it just tried and failed at — an outage the
operator cannot act on. `spec-kitty sync doctor` names this state explicitly
as **not consentable** so you do not have to guess which of the three states
above you are in.

## What `permitted` Does and Does Not Do

`tracker.egress: permitted` behaves differently depending on which
destination is asked, and this is a deliberate, decided design, not an
inconsistency:

- **At the local subprocess destination** (`beads`/`fp`), `permitted` is an
  **affirmative grant** that works **independently of hosted-sync consent**.
  You can keep a local tracker binding alive without ever opting this
  repository into spec-kitty's hosted SaaS.
- **At the hosted service destination** (`jira`, `linear`, `github`,
  `gitlab`, and anything reached with `--provider <saas>`), `permitted`
  **grants nothing**. It can only narrow an already-permitted path further —
  it can never be the reason a hosted-service request is allowed through.
  Hosted-sync consent (Channel 1) remains a hard prerequisite there, because
  that transport sends to **spec-kitty's own hosted service** — bearer-token
  `/api/v1/tracker/...` endpoints holding the connector and relaying to the
  provider — not to anything local to your machine.

**This is a decided limitation, not an oversight.** A SaaS tracker binding
without hosted-sync consent is **not delivered** by this mission, and is not
planned as an accidental gap to be closed later without a separate decision:
recording a local, project-owned key must never be able to authorize traffic
to spec-kitty's own service on its own.

## The `map list` Split

On the same refusing project, `spec-kitty tracker map list` (no `--provider`)
**succeeds**, while `spec-kitty tracker map list --provider jira` **refuses**.
Both are correct. `issue-search --provider` and `list-tickets --provider`
behave the same way.

This is not a bug: **the gate follows the destination, not the subcommand
name.** `map list` with no provider reads local state and touches no
transport at all; `map list --provider jira` crosses the hosted transport,
so it is gated exactly as any other hosted-destination call is.

## A Typo Refuses

The Channel-2 value set is closed to exactly two strings: `refused` and
`permitted`. There is **no case-folding and no synonym list** — not
`Refused`, not `REFUSED`, not `refuse`, not `deny`, not `yes`/`on`/`1`/`true`,
not a number, not `null`, not an empty string, not a mapping, not a list.

**Anything else present at the `tracker.egress` key is a fault, and a fault
refuses tracker egress at both destinations.** This is intended, not a side
effect: on a confidentiality control, the only safe reading of a value nobody
defined is refusal — the alternative is that a mis-spelling silently
permits. The cost is that a typo can take a previously-working local binding
offline; the refusal message names the offending value verbatim, together
with both legal values, and `spec-kitty sync doctor` renders the same
wording, so fixing the typo does not require reading source.

## Which Commands Are Gated

Only `spec-kitty tracker sync pull`, `sync push`, and `sync run` consult the
Channel-1/Channel-2 join described above. `tracker status`, `tracker bind`,
`tracker unbind`, and `tracker map add` construct no connector, run no
subprocess, and reach no transport at all — they are **not** gated, so a
refusing project keeps its local-only commands fully working.

`tracker bind --provider beads` / `--provider fp` also does not require
**hosted readiness** (auth, `SPEC_KITTY_SAAS_URL`, reachability) — a distinct
pre-flight from the Channel-1/Channel-2 gate above, but one that a local bind
must equally not be blocked by for this section's promise to hold. An
unauthenticated project can `tracker bind` a local provider and keep working;
only a SaaS-provider bind (`--provider jira`/`linear`/`github`/`gitlab`) still
requires it.

## A Recorded Decision Outlives Its Binding

`tracker bind`, `rebind`, and `unbind` all preserve a committed
`tracker.egress` decision. Unbinding a provider does not erase a recorded
`permitted` any more than it erases a recorded `refused` — both survive an
`unbind` exactly the same way, so re-binding later does not silently reset
your decision back to absence.

## Related Documentation

- [Migrations index](index.md)
