---
affected_files: []
cycle_number: 1
mission_slug: hosted-opt-in-drain-ledger-01M3FFEV
reproduction_command:
reviewed_at: '2026-09-27T04:20:50Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review, cycle 1: changes requested (reviewer-renata)

The matrix (f9bbac65) and the T018 cross-reference are sound and need no change. Rejection is
limited to two soundness gaps in the drain gate's classifier, `tests/architectural/test_hosted_drain_gate.py`.
Standing Order 5 applies: a gate that reports "gated" for code that is not gated is worse than
having no gate at all.

## BLOCKING 1: a `try` whose handler swallows `DrainDisabled` is classified as gated

`_unconditional_gate_lines` treats any `require_drain(...)` in a `try` body as unconditional and
never looks at the handlers. This source classifies `gated: True`:

```python
def fetch(req):
    try:
        require_drain("relay")
    except DrainDisabled:
        pass            # or: log and fall through
    return budget.NoRedirects.build().open(req)
```

It also affects a real floor edge. In `transport.py`, `ZeitgeistClient.offer` has
`except DrainDisabled: return OfferResult(...DRAIN_DISABLED...)`. I replaced that `return` with
`pass`, which leaves the edge ungated while drain is off. The arch gate stayed fully green:
every `test_hosted_drain_gate` test passed, including the NFR-002 floor and the self-mutation
tests. Only the behavioural tests `test_drain_relay_edges.py` (3) and the matrix's
D3 test caught it. For a new edge written this way, the arch gate is the only check, and it
would pass.

**Fix:** count a gate inside `try` only when every handler that can catch `DrainDisabled`
terminates. That means handlers of type `DrainDisabled`, a bare `except`, `Exception` or
`BaseException`, and possibly a tuple containing one of them, and each such handler body must
end in `return`/`raise`. Also consider `finally`/`orelse` shapes. Add these bite params:
`try-handler-swallows` (pass), `try-handler-logs-and-falls-through` and `broad-except-swallows`.
The existing `aliased-module-require-in-try` positive control must stay gated. Extend
`_StripDrainGates` (or add a second mutation) so that the self-mutation for `transport.py` also
covers "neutralise the handler" and shows it red-first.

## BLOCKING 2: the discovery sweep misses an import-aliased relay opener

`_is_relay_opener` matches on the dotted-name tail `("NoRedirects", "build")` / `("open_bounded",)`.
Both of these go undetected:

```python
from specify_cli.zeitgeist_client.budget import NoRedirects as NR
def alias_leak(req): return NR.build().open(req)          # not discovered
```

I planted this in `src/specify_cli/zeitgeist_client/rogue_alias.py` in a scratch copy.
`test_no_unregistered_hosted_edge_exists` and the whole of `test_egress_consent_boundary.py`
stayed green. The plain unaliased form (`budget.NoRedirects.build()` in a new function in
`history.py`) is caught correctly.

**Fix:** resolve per-module import bindings for the opener, the same way `_authority_bindings`
already does for the gate. That covers `from ...budget import NoRedirects as X`,
`from ...budget import open_bounded as Y` and `from ...zeitgeist_client import budget as b`, and
match against the resolved names. Add a `TestGuardBites` discovery case for each aliased form.

## Non-blocking: record only, follow-up ticket
- A raw `urllib.request.build_opener().open(req)` in `zeitgeist_client/` is invisible to both
  gates (checked in the scratch copy). This is the egress-boundary gate's vocabulary, so it
  predates this WP. Open a follow-up. Do not widen scope here.
- The drain gate covers only the 7 network edges. The caller-side pre-flights are all pinned
  behaviourally: I stripped 11 single sites and each one went red in its own suite. The sites
  were the adapters fan-out ×3, resolve_credentials pre-cache, resolve_focus_capability, the
  runtime producer, retrospective, the live_work publisher, the live_work CLI hook, the MCP tool,
  zeitgeist CLI, and the charter and plan interview. Acceptable as is. If you like, add one
  docstring line saying they are behaviourally (not structurally) gated.

## Verified OK (no action needed)
- The registry of 7 edges matches the live code. The NFR-002 floor of 5 counts named edges and
  checks each one is gated in the live source, so it is not circular. The plain unregistered
  opener goes red. The existing evasion bites all hold: branch, after-opener, look-alike,
  wrong module, ignored `drain_posture()`, `if False and not ...`, and inverted test.
- The allowlist is empty and pinned at 0 in `_baselines.yaml`. The `test_ratchet_baselines.py`
  registration is required by `test_no_unregistered_baseline_keys_are_added`, so it is justified
  even though it is out of the WP's map.
- In `test_egress_consent_boundary.py`, only text was appended. No kind, seam_symbol or
  membership changed.
