---
type: reference
updated: 2026-10-13
mission: derived-consumer-census-01M4V5P5
issue: 6173
---

# CI-cost delta — census-derived vs hand fan-out (#6173 FR-009 / SC-004)

Measured with `python -m scripts.ci.consumer_census_cost --recent 30`. Shard counts
are the registry's measured `shard_count`. "hand" = the live human-validated
`GROUP_MODULE_FANOUT`; "derived" = `derive_group_module_fanout()` (the census's own
answer, the cost full value-derivation WOULD add — not live today).

## Representative pack-edit types (where the derivation differs)

| Edit type | hand shards | derived shards | delta |
|---|---|---|---|
| `mission-steps/*/prompt.md` | 15 | 20 | +5 |
| `*/expected-artifacts.yaml` | 9 | 25 | +16 |
| `mission_types/*.yaml` | 16 | 24 | +8 |
| `*/mission.yaml` | 15 | 20 | +5 |
| `cli/commands/lifecycle.py` | 10 | 13 | +3 |
| pack `README.md` (control) | 0 | 0 | +0 |

## Real recent diffs (last 30 landed commits on `origin/main`)

Total: **hand 53 shards, derived 53 shards, delta +0.** None of the last 30 landed
commits edits a mission-pack path, so the derived fan-out would have changed the
selected-shard count on **zero** of them. Pack-content edits are infrequent; the
derivation's extra cost only lands on those rare edits.

## Reading

- The census-derived fan-out is **wider** than the hand fan-out on pack-content
  edits (+3…+16 shards; `expected-artifacts.yaml` worst at 9→25). The census finds
  real consumers the hand list omits (e.g. `core_misc`/`upgrade`/`unit` tests that
  reference resolver entry points), but static analysis cannot tell a test that
  asserts on the REAL shipped pack from one that drives the same entry point against
  a temp project — so a blind derivation over-routes. That is why `GROUP_MODULE_FANOUT`
  stays human-validated and full value-derivation is a tracked follow-up (needs
  real-pack-vs-temp precision, which requires running the tests — infeasible in a
  freshness-checked census build).
- On the active (hand) routing this PR changes **nothing** about cost: the census +
  gate are additive (the committed durable map + the drift gate). The delta above is
  the *forecast* for the follow-up, recorded so the operator can weigh it.
- **`charter` is the long pole** (7 shards) in every pack-content edit under either
  fan-out. Within-module file selection to shrink it (FR-010) is **carved to a
  follow-up** (see #6189): it is a distinct mechanism (selecting
  test *files* within a module's shard from the census) larger than this PR's scope,
  and it only pays off once the derived routing is live.
