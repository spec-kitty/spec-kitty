---
title: 'zeitgeist_client WP01 — remaining scope'
description: 'Status note for the bundled Zeitgeist client (Bead Z1-T1): the committed source of truth for what is left in WP01 after the Z4/Z6/Z7/Z8/O1-C client stack landed.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---

# zeitgeist_client WP01 — remaining scope

> **Reading this page.** The codes are work-item handles from the Zeitgeist programme plan,
> kept so the page lines up with commit messages and module docstrings. `Z<n>` items are
> Zeitgeist client/relay work items and `-T1`/`-C` mark the task or client slice (for
> example `Z1-T1` is this WP01, `Z7-C` the CLI/MCP subscription slice). `F<n>` items are
> producer-side schema work in other repos (`spec-kitty-events`, `zeitgeist`). `O1-C` is the
> client operability slice. `FIX-M2-15` is a numbered fix from the M2 integration review.
>
> **Status (re-checked against the code 2026-09-30).** Still open: item 1 (there is no
> `validator.py`), item 2 (`ZeitgeistClient.status()`/`.watch()` in `transport.py` still raise
> `NotImplementedError` and point here) and item 7 (no `docs/zeitgeist-client.md`). Largely
> overtaken: item 5. `zeitgeist_client/resolution.py` now resolves and stores a checkout's relay
> credential automatically (cached credential, else mint from Team Kitty), and
> `spec-kitty zeitgeist status` derives `repo` from the checkout's origin remote. There is
> still no explicit `checkout` command. Later work, including the #4216 moment delivery, added
> modules and commands not listed below (for example `agent_delivery.py`, `moments.py`,
> `own_filter.py`, `receipts.py`, `history.py`, `session_identity.py`, and the `activity`,
> `send`, `reply`, `read` and `inbox` commands); see
> [Agent moment delivery policy](agent-moment-delivery-4216.md). Item 6 was not re-checked.
> The body below is the 2026-08-22 text.

Status note for `src/specify_cli/zeitgeist_client/` (Bead `Z1-T1`). This is the
committed source of truth that in-code comments and error messages point to
for "what's left in WP01" — mirrors the ordered task list from the Z1
drafting note (`Z1.md §5`, an out-of-repo scratchpad draft, items 2-6), kept
current in this repo instead of in a document that never lands here.

Landed so far: `grammar.py`, `sanitizer.py`, `budget.py`, `transport.py`
(`offer()`/`focus_start()`/`focus_heartbeat()`/`focus_pause()`/`focus_end()`/
`presence()`/`ClientConfig.for_repository()`), `credentials.py` (local
storage primitive: `store()`/`load()`/`revoke()`), `repo_identity.py`
(`Deadline`, `repo_name()`, `branch_name()`, `commit_oid()`, `identity()` —
landed by Z6-C, NOT a literal port of `zeitgeist/integrations/
repo_identity.py`; see its module docstring for the deliberate divergence:
no directory-basename fallback, fail-closed on ambiguity).

**Z4-C** (a separate Bead, branched from this WP01 base at `afa4020d`) added
`live_frame.py` (pure `LiveFrame` parsing + `StreamState`: gap/epoch/revoke
handling via full local-state reset, <=90s TTL clamp enforced client-side
regardless of what a relay sends, closed `focus.state=="ended"` signals
dropped rather than queued) and `filtered_stream.py`
(`FilteredStream.watch()`/`.check()`/`.current_focus()` — one SSE
subscription per team-bound `X-Zeitgeist-Capability` credential against F3's
managed-runtime `GET /managed/stream`, landed separately by Z3-T1 in the
`zeitgeist` repo). This does **not** resolve item 1/2 below: Z4-C's own
frame parsing is a deliberately narrower, hand-checked shape gate (exactly
the fields `StreamState` reads), not a general JSON-Schema validator run
against a bundled/pinned `managed_live.schema.json` — `ZeitgeistClient.
watch()`/`.status()` on `transport.py` are untouched by Z4-C and still raise
`NotImplementedError`; Z4-C's surfaces live on the new
`filtered_stream.FilteredStream` class instead, deliberately not folded into
`transport.ZeitgeistClient` (see `zeitgeist_client/__init__.py`'s module
docstring for why the two stay independent).

**Z7-C** (a separate Bead, branched from Z4-C's tip at `7fac07d1`) added
`subscription.py` (the shared, explicit-`repo`-only `status()`/`watch()`
surface both adapters below call — no `relay_url`/`token` parameter exists on
it, the credential comes solely from `credentials.py`'s existing store,
`NotCheckedOut` on a missing one rather than auto-provisioning), `mcp_stdio.py`
(the official-SDK — `mcp>=1.27.1,<2.0.0` — stdio MCP adapter: two tools,
`zeitgeist_status`/`zeitgeist_watch`), and
`cli/commands/zeitgeist.py` (`spec-kitty zeitgeist status`/`watch` plus a
hidden `mcp-serve` command, registered in `cli/commands/__init__.py`). This
resolves item 3, most of item 4, and item 8 below — but deliberately not all
of item 4: `checkout`/`focus` are still absent (see the updated item 4/5 notes).

**Z8-C** (a separate Bead) added `outbox_approval.py` (the bundled,
human-gesture-gated outside-model approval surface for locally queued
Zeitgeist prose — content-addressed, TTL-bounded, default-deny) and the
`outbox` sub-group on `cli/commands/zeitgeist.py`, deliberately NOT wired
into `mcp_stdio.py` (a model over MCP has no tool that reaches it).

**O1-C** (program-graph handle O1-C, "Spec Kitty client operability", built
on Z7-C's subscription adapters + Z8-C's approval surface) added
`operability.py`: seven payload-free signals (offer/drop/lease/revoke/mcp/
repair, each carrying its own denominator where one applies — 750ms for
offer, 90s for lease) built entirely from state `transport`/`credentials`/
`outbox_approval`/`mcp_stdio` already own (no second data store), plus
three local, network-free drills (`timeout_drill`/`rotation_drill`/
`rollback_drill` — relay-unreachable, auth-expiry, and revoke-fails-closed
respectively), and the `spec-kitty zeitgeist operability` CLI sub-group
(`report`, `drill-timeout`, `drill-rotation`, `drill-rollback`) over it.
`subscription.status()`/`.watch()` themselves are untouched by this —
O1-C reports on the client's own operational health, it does not add a
new subscription surface.

## Not yet implemented

1. **`validator.py` + bundled schemas + `DIGESTS.json`** — blocked on F1-T1
   and F3-T1 landing as producer candidates in `spec-kitty-events` /
   `zeitgeist` (no real JSON Schema files or `registry_digest()` /
   `support_matrix_digest()` exist yet to pin against). Until this lands,
   `ZeitgeistClient.offer()` performs only the sanitizer gate, not the
   schema-validation gate.
2. **`ZeitgeistClient.status()` / `.watch()`** — both raise
   `NotImplementedError`; both depend on `validator.py` above (no LiveFrame
   streaming, no version-skew or unknown-kind rejection yet).
3. ~~`mcp_stdio.py`~~ — **landed by Z7-C**: the official-SDK (`mcp>=1.27.1,
   <2.0.0`, FastMCP-based) stdio adapter, two tools
   (`zeitgeist_status`/`zeitgeist_watch`) over `subscription.py`. In-process
   client/server coverage via `mcp.shared.memory` in
   `tests/zeitgeist_client/test_mcp_stdio.py`.
4. **CLI adapter** — `src/specify_cli/cli/commands/zeitgeist.py`. **`status`/
   `watch` plus a hidden `mcp-serve` command landed by Z7-C**, registered in
   `cli/commands/__init__.py`. `checkout`/`focus` remain unimplemented (see
   item 5) — Z7-C's own node criterion ("no administration/human approval")
   forbids a credential-writing command on this surface; `focus` belongs to
   `transport.ZeitgeistClient`'s control-envelope path, not the
   `FilteredStream` subscription surface Z7-C scoped ("watch/status/
   subscribe").
5. **`checkout`/auth network half** — `spec-kitty zeitgeist checkout
   <relay-url>` (health-reachability probe + canary `offer`, per
   `install.py`'s `cmd_verify` precedent). `credentials.py`'s storage
   primitive is implemented and tested; nothing calls it from a CLI flow yet.
    `repo_identity.identity()` (landed, Z6-C) is what this future CLI flow
    should call to get the canonical `repo` key to store against — tests use
    a literal `"spec-kitty"` string today because no CLI flow exists to wire
    it through yet, not because the derivation is missing.
    `subscription.py`/`status`/`watch` (Z7-C) still require the caller to
    name `repo` explicitly (Z7-C's own "one explicit authorized team context"
    criterion); wiring `repo_identity.identity()` into those flows is
    deferred follow-up work (integration note, M2 canonical integration).

    **FIX-M2-15**: `credentials.py`'s storage primitive (and
    `transport.ClientConfig`/`filtered_stream.TeamStreamConfig`, the two
    wire-facing configs it feeds) now carry a SECOND, optional
    `capability_credential` field alongside `token` — a real
    SaaS-provisioned per-team relay signs `Authorization`'s shared
    bearer and `X-Zeitgeist-Capability`'s per-actor JWT with two
    INDEPENDENT secrets, and one value can no longer satisfy both gates
    (see the three modules' own FIX-M2-15 docstring notes). On the
    `spec-kitty-saas` side, `apps.live_capability.views.
    mint_cli_credential` (`POST /api/v1/live/capability/cli/`) is the
    new member-facing surface that returns `relay_url`/`relay_token`/
    `capability_credential` together — exactly the triple this
    not-yet-built `checkout` flow should call `credentials.store()` with
    once it exists. This item's own remaining gap is unchanged by
    FIX-M2-15: there is still no CLI flow that calls either endpoint or
    `credentials.store()`.
6. **Harness-asset staging** — `.mcp.json` companion asset, the
   `ClaudeCodeHookRegistrar` `PostToolUse` event-constant extension, per-harness
   hook re-homing under `zeitgeist_client/assets/hooks/<harness>/`, and
   `tool_surface.repair` registration.
7. **`docs/zeitgeist-client.md`** — not written (`CHANGELOG.md` now carries a
   Z7-C entry).
8. ~~CLI/MCP wiring for Z4-C's `FilteredStream`~~ — **landed by Z7-C**:
   `subscription.py` is the one shared surface both the CLI (item 4) and the
   MCP adapter (item 3) call — neither re-derives bounded-read/bounded-watch
   logic independently. Still not covered: any server-side
   capability-credential issuance flow (Z2a/Z2b's job, not this client's) — a
   caller must already hold a valid `X-Zeitgeist-Capability` token, stored via
   `credentials.py`, before `status()`/`watch()` (or their CLI/MCP callers)
   can do anything; nothing here mints or requests one.

See the module docstrings of `transport.py`, `credentials.py`,
`live_frame.py`, `filtered_stream.py`, `subscription.py`, `mcp_stdio.py`,
`outbox_approval.py`, `operability.py`, and `cli/commands/zeitgeist.py` for
the specific contract clauses each gap corresponds to.
