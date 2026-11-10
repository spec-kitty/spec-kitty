---
title: Zeitgeist publisher and lease identity
doc_status: deprecated
kind: Explanation
updated: '2026-11-04T00:00:00Z'
audience:
- profile: internal/system-architect
  guidance_text: Written for the System Architect reader.
description: How logical agents, SaaS leases, and relay session references related before the hosted surfaces were removed.
---

# Zeitgeist publisher and lease identity

> **Deprecated (2026-11-03).** The Zeitgeist publisher, its session identity and the
> `SPEC_KITTY_ZEITGEIST_SESSION_ID` variable were removed from this repository in #6164. No
> `src/` code reads this variable; the page is retained only as a record of the retired design.

## Historical design before #6164

The following sections record the retired protocol, not current command or
deployment instructions.

A logical agent could invoke several CLI commands and run a separate reader.
Its `logical_session_id` selected its capability cache and SaaS lease scope;
it neither identified the authenticated human nor granted authorization.
Agents sharing an account and repository needed distinct selectors.

The retired CLI used `SPEC_KITTY_ZEITGEIST_SESSION_ID` when supplied, requiring
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. Otherwise, `CODEX_THREAD_ID` supplied a
namespaced, SHA-256-derived selector. Without either, processes shared a stable
default selector for the credential cache and the retired `spec-kitty zeitgeist
watch`/`status` and MCP readers. Per-process selectors would have stranded stored
credentials between commands. Concurrent harnesses therefore propagated a
distinct selector across each agent's related processes; unidentified agents
shared the default partition, so own-agent filtering could not separate them.

## Issuer and relay boundaries

The SaaS CLI mint accepted and echoed the selector. The retired CLI rejected
responses without the exact selector or a valid `session_ref`; an older server
left local work functional but could not support managed publication. The
historical rollout required the SaaS contract first. Clients neither computed
nor needed the relay's private salt.

| Identity | Owner | Use |
| --- | --- | --- |
| `logical_session_id` | Harness/CLI | Cache partition and SaaS supersession scope; shared across related processes |
| SaaS `session_ref` | SaaS lease issuer | Immutable raw ingress `session_id` for a particular lease generation and kind |
| Relay `actor.session_ref` | Relay | Opaque salted egress reference for that raw ingress ID within the relay's lifetime |

A presence lease's raw reference accompanied events and presence. A focus lease
had its own raw reference, stored with its capability. Each SaaS revoke used the
corresponding lease's raw reference. The relay removed only that session's state
in the authenticated team/deployment/repository scope and emitted its opaque
reference.

Reminting changed the raw lease reference, so a delayed revoke could not delete
its replacement. Presence and focus reminted independently; a presence remint
preserved an unexpired focus lease only within the same scope. The relay keyed
focus by session, repository and focus reference, allowing two agents to work on
the same mission/WP without overwriting each other.

## Cache, reconnects, and restart

The retired locked, owner-only TOML store lived under
`<runtime_state_root>/zeitgeist-sessions/<logical_session_id>/zeitgeist-credentials`.
Repository keys were `host/owner/repo`. Related processes shared a cache while
other agents, negative admissions and repositories stayed separate. Legacy
shared credential files were left untouched: their bearer could not prove which
logical agent owned the lease. A fresh mint populated the new partition.

The retired watch/MCP credential reader used the same partition. Zeitgeist
issue #295's own-event filtering bound the logical agent to its per-kind lease
references, including replacements, while the relay derived opaque references.
Comparing human account IDs would have hidden other agents; comparing ingress
and egress references would never have matched. The reader used the relay-owned
`filterOwn` option for this identity boundary.

A relay restart cleared volatile state and changed its private salt. The retired
CLI could republish a cached lease's raw ID while its authority remained valid;
revoke then targeted the new representation without knowing either salt.

## Cleanup is separate from authority

In this design, removing presence/focus state did not invalidate a signed
capability. SaaS issue #1634 and its relay companion owned authority lifetime and
revocation validation. The identity change made directed cleanup accurate; it
did not claim to prevent reuse of an otherwise-valid revoked token.

## Issue traceability

| Issue | Delivery |
| --- | --- |
| [CLI #4217](https://github.com/spec-kitty/spec-kitty/issues/4217) | Agent cache partition, lease-reference preservation, producer integration, regression tests |
| [Zeitgeist #295](https://github.com/spec-kitty/spec-kitty-zeitgeist/issues/295) | Reader forwards cached publisher identities and requires relay filtering acknowledgment |
| [SaaS #1634](https://github.com/spec-kitty/spec-kitty-saas/issues/1634) | Authority invalidation remains separate from state cleanup |

## Reader own-session suppression

The retired `zeitgeist watch`, `zeitgeist status`, `zeitgeist activity` and MCP
readers requested `filterOwn=true`. Each read loaded the credential cache and
forwarded presence/focus issuer session refs in `X-Zeitgeist-Own-Sessions`.
Only the relay derived opaque scoped references; readers did not reproduce its
salt or compare human accounts. Related commands shared refs through their
logical-session selector; other agents retained separate partitions and stayed
visible.

Readers required `X-Zeitgeist-Filter-Own: true`; missing identity or an older
relay without acknowledgment failed explicitly. The retired `watch --raw` and
`status --raw` commands requested `filterOwn=false`, and MCP accepted
`filter_own=false` for a complete feed. History replay filtered own frames unless
explicitly opted out. Reconnects resolved credentials again. Global sequence
jumps were intentional; only relay gap/epoch signals reset continuity. Own
suppression preceded subscriber queue and receipt/rate budgets, while transport
signals remained visible.
