---
title: Agent moment delivery policy
description: 'Agent moment delivery for #4216: team-scoped default for unfamiliar peer activity, identity-scoped receipts as the novelty policy, bounded catch-up shared by CLI and MCP.'
doc_status: draft
updated: '2026-09-15'
type: explanation
audience: automation-agent
---

# Agent moment delivery policy

Issue: #4216. Governed Op: `01M2808ND3ATY3DGYTG470R04A`.
Draft delivery: [PR #4224](https://github.com/spec-kitty/spec-kitty/pull/4224).
The original Op closed with outcome `failed` while the relay contract was pending.
The continuation integrates relay #295 using the merged #4217 issuer identity
contract; the original Op log remains unchanged.

An agent should discover unfamiliar missions and mission-less activity in the
single repository it requested. `team` changes admission within that scope; it
does not enumerate credentials or subscribe to additional repositories.
`mine` means locally known missions, not authenticated assignment.

## Approach and boundaries

One delivery service applies the same settings, canonical event identity,
receipt checks and event budget to CLI and MCP. The relay suppresses own-session activity before subscriber queueing; the
explicit raw mode requests the complete transport feed. Retained history is an explicit catch-up/replay source, using the
relay's existing `/managed/events` endpoint and its coverage metadata.

A receipt means the logical consumer acknowledged the returned batch. MCP
clients pass the previous `receipt` back as `acknowledge` on their next call;
this avoids recording failed tool delivery as read. CLI acknowledges only after
successful output and flush. Unacknowledged batches may be offered again.
Receipts store identities and timestamps, never event prose. Outstanding batches
reserve rolling-minute quota without being marked read; an atomic reservation
check prevents concurrent polls from multiplying that quota. A stable consumer
identifier is shared across reconnects and CLI/MCP processes through the
canonical publisher/credential session selector (#4217). Explicit `--consumer`
can select a separate receipt context; the default never derives from the
authenticated human account or mints a second process identity.

Receipt contexts include the consumer, requested repo, relay admission metadata and
effective filters. Legacy credentials without team/host/repo metadata start a
fresh context on rotation conservatively;
no opaque credential is decoded or treated as proof of authorization. The relay
continues to enforce the actual authorization boundary. No account-wide mark-read
flag exists. Source event IDs are normalized through the event contract package;
frames without a source event ID use relay epoch and sequence. Replay ignores
receipts intentionally, but still respects settings and context bounds.

## Design decisions and limitations

- Receipts are acknowledged explicitly, not on frame selection or rate rejection.
- A bounded receipt store fails explicitly when full instead of forgetting old
  identities silently. It contains no local event archive.
- Withheld frames do not advance a delivery cursor. Catch-up re-reads retained
  history and suppresses receipts before spending the context budget.
- Existing history is bounded and volatile. `gap`/`reset` and truncation remain
  visible; an empty result does not establish that nothing ever happened.
- Relay #295 owns own-publisher suppression. Agent stream and history readers
  request `filterOwn=true`, forward both cached issuer session refs, and require
  the relay acknowledgment before consuming frames. They never derive opaque
  references locally or filter by human account. Missing identity fails loudly.
  CLI raw mode and MCP `filter_own=false` explicitly include own activity.
  The relay acceptance suite exercises real command publication and a separate
  CLI reader process against these candidates.
- Relay #296 owns race-safe history/live handoff. Explicit history and live watch
  here remain separate reads, with overlap deduplicated after acknowledgement;
  this implementation does not claim a gap-free initial snapshot/live handoff.

## Issue matrix

| Issue | Claim | Delivery |
|---|---|---|
| spec-kitty/spec-kitty#4216 | Assigned and `status:claimed`; Op above | Client defaults/policy/receipts/catch-up and relay-backed own-identity integration |
| spec-kitty/spec-kitty-zeitgeist#295 | External dependency | Verified publisher/subscriber identity and relay own-event suppression |
| spec-kitty/spec-kitty-zeitgeist#296 | External dependency | Initial snapshot and race-safe history/live handoff |

## Tooling friction

The prep inventory rejects the current owner-qualified CLI name. Its historical
`spec-kitty` entry follows GitHub's redirect to `spec-kitty/spec-kitty` correctly.
`uv sync --frozen --all-extras` warmed the checkout; pytest separately constructs
its own cached subprocess environment. The installed Spec Kitty dispatch opened
the Op and loaded governance; no mission or fabricated workflow state was created.

The installed `profile-invocation complete --artifact` coerced the PR URL to a
filesystem path (`https:/...`). The canonical Op log is preserved verbatim;
its evidence document is this file, which carries the correct PR link above.
