---
title: Zeitgeist publisher and lease identity
type: explanation
doc_status: active
updated: '2026-09-14'
audience: agentic-framework-core-team
description: How logical agents, SaaS leases, and relay session references relate.
---

# Zeitgeist publisher and lease identity

A logical agent can invoke several CLI commands and run a separate reader. Its
`logical_session_id` selects its own capability cache and SaaS lease scope.
It does not identify the authenticated human and is not an authorization grant.
Two agents using one account and repository need different selectors.

The CLI uses `SPEC_KITTY_ZEITGEIST_SESSION_ID` when supplied. Its value must match
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. Otherwise, `CODEX_THREAD_ID` supplies a
namespaced, SHA-256-derived selector. Without either, every process on the
account shares one stable default selector: the credential cache and the
reader surface (`spec-kitty zeitgeist watch`/`status`, the MCP stdio tools)
are keyed by this selector, so a per-process value would leave a stored
credential unreachable by the next command or reader. A harness running
genuinely concurrent agents under one account must propagate an explicit,
distinct `SPEC_KITTY_ZEITGEIST_SESSION_ID` to each agent's related command,
watch, and MCP processes if it does not expose a Codex thread identifier;
unidentified agents all share the default partition, so own-agent filtering
cannot separate them — `NotCheckedOut` and the CLI hint name the variable
that pins one.

## Issuer and relay boundaries

The SaaS CLI mint accepts the selector and echoes it. The CLI rejects responses
without the exact selector or a valid `session_ref`; an older server therefore
leaves local work functional but cannot support managed publication. Deploy the
SaaS contract first. No client computes or needs the relay's private salt.

| Identity | Owner | Use |
| --- | --- | --- |
| `logical_session_id` | Harness/CLI | Cache partition and SaaS supersession scope; shared across related processes |
| SaaS `session_ref` | SaaS lease issuer | Immutable raw ingress `session_id` for a particular lease generation and kind |
| Relay `actor.session_ref` | Relay | Opaque salted egress reference for that raw ingress ID within the relay's lifetime |

A presence lease's raw reference accompanies events and presence. A focus lease
has its own raw reference, stored together with its focus capability. Each SaaS
revoke uses the corresponding lease's raw reference. The relay removes only
that session's state in the authenticated team/deployment/repository scope and
emits its matching opaque reference.

Reminting changes the raw lease reference. A delayed revoke of an old generation
therefore cannot delete its replacement. Presence and focus remint independently;
a presence remint preserves an unexpired focus lease only within the same scope.
The relay keys focus by session as well as repository and focus reference, so two
agents can work on the same mission/WP without overwriting each other.

## Cache, reconnects, and restart

The existing locked, owner-only TOML store lives under
`<runtime_state_root>/zeitgeist-sessions/<logical_session_id>/zeitgeist-credentials`.
Repository keys remain `host/owner/repo`. Related processes use the same cache;
other agents, negative admissions, and repositories remain separate. Legacy
shared `zeitgeist-credentials` files are not imported: their bearer cannot prove
which logical agent should own the lease. They are left untouched and a fresh
mint populates the new partition.

The watch/MCP credential reader uses this same partition. Zeitgeist issue #295's
own-event filtering binds the logical agent to its current per-kind lease
references, including replacements, and lets the relay derive opaque references.
Comparing human account IDs would hide other agents. Comparing an ingress ID to
an egress reference would never match. The reader consumes this identity boundary through the relay-owned `filterOwn` option.

Relay restart clears volatile state and changes its private salt. The CLI can
republish with a cached lease's raw ID while its authority remains valid; revoke
then targets the new relay's representation without knowing either salt.

## Cleanup is separate from authority

Removing presence/focus state does not invalidate a signed capability. SaaS
issue #1634 and its relay companion own authority lifetime and revocation
validation. This identity change makes directed cleanup accurate; it does not
claim to prevent further use of an otherwise-valid revoked token.

## Issue traceability

| Issue | Delivery |
| --- | --- |
| [CLI #4217](https://github.com/spec-kitty/spec-kitty/issues/4217) | Agent cache partition, lease-reference preservation, producer integration, regression tests |
| [Zeitgeist #295](https://github.com/spec-kitty/spec-kitty-zeitgeist/issues/295) | Reader forwards cached publisher identities and requires relay filtering acknowledgment |
| [SaaS #1634](https://github.com/spec-kitty/spec-kitty-saas/issues/1634) | Authority invalidation remains separate from state cleanup |

## Reader own-session suppression

CLI `zeitgeist watch`, `zeitgeist status`, retained `zeitgeist activity`, and their
MCP tools request `filterOwn=true`. Each read loads the current credential cache
and forwards its presence and focus issuer session refs in
`X-Zeitgeist-Own-Sessions`. Only the relay derives opaque scoped references;
readers never reproduce its salt or compare human accounts. Separate commands
with the same logical session selector share these refs; another agent under
the same account retains a separate cache partition and remains visible.

Readers require `X-Zeitgeist-Filter-Own: true` before consuming any response.
Missing identity or an older relay without acknowledgment fails explicitly.
CLI `watch --raw` and `status --raw` request `filterOwn=false`; MCP tools accept
`filter_own=false` for an intentional complete feed. Agent history replay still
filters own frames unless explicitly opted out through MCP. Reconnects resolve
credentials again. Global sequence jumps are intentional; only explicit relay
gap/epoch signals reset continuity. Own suppression precedes subscriber queue
and agent receipt/rate budgets, while transport signals remain visible.
