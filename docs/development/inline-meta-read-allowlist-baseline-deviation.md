---
title: 'Deviation: inline-meta-read allow-list governed without a count baseline'
description: 'Why the inline-meta-read allow-list is governed by equality + shrink-only controls rather than a _baselines.yaml count baseline (C-006 deviation; #3240).'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
type: explanation
related:
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---

# Deviation: inline-meta-read allow-list governed without a `_baselines.yaml` count baseline

**Status:** Accepted deviation (operator-confirmed).
**Tracker:** [#3240](https://github.com/spec-kitty/spec-kitty/issues/3240).
**Governing constraint:** C-006 (ratchet-baseline governance).
**Recorded by:** mission `meta-json-fail-closed-routing-01KZPJ1F`, WP05 / T025.
**Governed surface:** `tests/architectural/inline_meta_read_allowlist.yaml`
(the `inline_meta_read` composite-key allow-list) and its gate
`tests/architectural/test_inline_meta_read_gate.py`.

## Summary

`#3240` asks whether the inline-meta-read allow-list should be registered in
[`tests/architectural/_baselines.yaml`](../../tests/architectural/_baselines.yaml)
under its §(a) count-baseline schema, the way other `tests/architectural/*`
gated allow-lists are.

**Decision:** it is deliberately **not** registered there. The allow-list already
carries two compensating controls that are *strictly stronger* than a
`_baselines.yaml` `<=` count ratchet, so adding a count baseline would duplicate
governance while adding nothing the existing controls lack. This document is the
deviation record `#3240` closes (C-006 requires the deviation be recorded, not
that the baseline be added).

## What a `_baselines.yaml` §(a) baseline gives you

The `_baselines.yaml` ratchet is a single scalar per gate: the live allow-list
size must stay **`<=` baseline** (growth fails, shrinkage warns). It is a
*ceiling on the count*. It does **not** know which entries exist, and it does not
notice an entry that has become stale (its underlying call site was routed away)
as long as the total count stays under the ceiling.

## Why the existing controls are strictly stronger

The inline-meta-read gate governs the allow-list with two controls that
together dominate a count ratchet:

1. **`test_allowlist_matches_floor` — exact equality, not `<=`.**
   The seeded allow-list must have *exactly* `INLINE_META_READ_FLOOR` entries
   (`len(load_allowlist(...)) == INLINE_META_READ_FLOOR`), and the floor itself
   is pinned to the live inline-read census with a `FLOOR_MARGIN` band. Equality
   is a two-sided bound: it catches growth (like the `<=` baseline would) **and**
   catches a silently-shrinking floor that a one-sided ceiling would let drift.
   A `<=` count baseline is the weaker half of what this already enforces.

2. **`test_allowlist_shrink_only` + stale-entry eviction (`staleness_twin_guard`).**
   Entries may only be *removed* (routed away), never added
   (`len(keys) <= baseline` against the recorded pre-sweep scalar in the
   allow-list file itself), and `test_allowlist_entries_are_still_live` fails the
   build when any allow-list key no longer matches a live call site. That
   **stale-entry eviction is something a `_baselines.yaml` count baseline cannot
   express at all**: a count ratchet is satisfied by *any* set of entries summing
   under the ceiling, so a routed-away entry can sit forever masking a re-added
   read at the same location. The composite-key allow-list + twin-guard closes
   exactly that hole.

Because equality (control 1) subsumes the `<=` ceiling and stale-entry eviction
(control 2) adds a guarantee the baseline schema has no way to represent,
registering a second count baseline in `_baselines.yaml` would be redundant
governance — two mechanisms answering the same question, one strictly weaker.

## Consequence / re-evaluation trigger

If the equality control (`test_allowlist_matches_floor`) or the staleness twin
guard (`test_allowlist_entries_are_still_live`) is ever weakened or removed, this
deviation must be re-evaluated: at that point a `_baselines.yaml` §(a) baseline
would no longer be strictly dominated and should be added. As long as both
controls stand, the allow-list is governed more tightly *without* the baseline
than it would be with one.

An issue comment on `#3240` pointing at this document is posted at mission merge
(not from the implementation WP).
