---
title: 'ADR: the archive-freeze gate verifies reducer OUTCOME reproduction, not byte-identity'
description: 'Archived status.json is a frozen derived snapshot; a correct reducer improvement may re-assign a WP terminal-transition id without it counting as archive drift.'
status: Accepted
date: '2026-10-11'
---

**Status:** Accepted

**Date:** 2026-10-11

**Deciders:** Stijn Dejongh (owner), during the maintainer landing of PR [#6039](https://github.com/spec-kitty/spec-kitty/pull/6039) (adopt `spec-kitty-events` 10.4.2).

**Technical Story:** [#5967](https://github.com/spec-kitty/spec-kitty/issues/5967) and its upstream reducer fixes `spec-kitty-events#77` (10.4.1) / `#78` (10.4.2). Amends the historical-preservation gate `tests/architectural/test_archive_root_byte_identical.py` (M1 NFR-002, WP12 FR-007–011).

## Context

Each archived mission dossier under `kitty-specs/` carries a `status.json` — a **derived** projection of that mission's immutable `status.events.jsonl` through the canonical status-diary reducer (`specify_cli.status.reducer.materialize_snapshot`). The historical-preservation gate `test_no_preexisting_archived_file_was_modified` pins three per-pinned-snapshot (the WP11 reviewed-recovery `SNAPSHOTS`) guarantees:

1. **Frozen bytes** — the committed `status.json` blob equals an independently reviewed git blob (`_exact_candidate` against the `RECOVERED` commit) and the recovery receipt's `after_sha256`.
2. **Byte-identical canonical replay** — `materialize_snapshot(dir)` re-emitted *byte-for-byte* equal to the committed file (`assert canonical == candidate`).
3. **Terminal-state preservation** — the per-WP `lane`/`verdict` (and historically `last_event_id`/`last_transition_at`) match the reviewed history.

Guarantee (2) silently assumed the canonical reducer's output for a given event log is **stable for all time**. It is not: the reducer is allowed to be *fixed*. Adopting `spec-kitty-events` 10.4.2 (the `#78` reconstruction-seed fix, built on 10.4.1's generalized from-lane continuity, `#5967`) changes the materialized output of `reject-cyclic-lane-graphs-01M0QCK4` — but **only** the identity of a work package's terminal transition. WP01/WP02/WP03 each carry a duplicate terminal `approved -> done` merge re-emit; the corrected reducer keeps the *first* `done` event and drops the causally-stale second one, so each WP's recorded `last_event_id`/`last_transition_at` moves to the earlier event. Every outcome — `lane`, `review_result.verdict`, the summary, actors, subtasks, top-level identity — is unchanged. Guarantee (2) failed the gate on a reducer improvement that changed no outcome.

Re-materialising the frozen file to the new bytes was rejected: it would mutate an archived artifact and break guarantee (1)'s git-provenance pins (the reviewed `RECOVERED` blob is immutable).

## Decision

**Archived `status.json` bytes are frozen at the canonical reducer generation that authored them.** The archive-freeze gate verifies that the *current* reducer **reproduces the archived OUTCOME**, not that it reproduces byte-identical output forever.

Concretely, guarantee (2) is relaxed from raw byte-equality to an outcome-equality (`_assert_replay_preserves_outcome`) that tolerates exactly the reducer-generation-sensitive per-WP terminal-transition identity fields — `last_event_id` and `last_transition_at` (`_EVENT_POINTER_KEYS`). Every other field (lane, review_result, summary, actor, agent, subtasks, force_count, and the top-level identity) must still match the frozen snapshot exactly, so the gate stays non-vacuous: a changed lane or verdict, a different summary, an added/dropped WP, or a shifted actor/subtask still fails. As a further non-vacuity guard, any **moved** `last_event_id` must name a real event in that mission's `status.events.jsonl` (`_logged_event_ids`) — a fabricated or missing-log pointer fails — so the tolerated drift can only re-point within the mission's own recorded events. Guarantees (1) frozen bytes and (3) terminal-state preservation are **unchanged** — the committed file is never rewritten, and the reviewed git-provenance pins stand.

## Consequences

- A correct reducer evolution that preserves every mission's outcome lands without rewriting any archived dossier or re-pinning the reviewed-recovery blobs.
- The gate no longer protects "the reducer's output for these snapshots is byte-stable forever" — that guarantee was over-strict (it forbade fixing the reducer). It still protects "the reducer reproduces every archived mission's outcome," which is the property that actually matters for historical fidelity.
- A reducer change that would alter a frozen mission's **outcome** (not just terminal-transition identity) still fails the gate — correctly, because that *is* archive drift and demands a conscious decision.
- The tolerance set is deliberately minimal (two fields). Widening it later requires amending this ADR, keeping the gate honest.
- The tolerance is **gate-wide across every work package of every pinned snapshot**, not scoped to the three WPs that drifted under 10.4.2. The residual coverage boundary this draws: a future live-replay regression that re-points a currently-non-drifting WP's terminal transition to a *wrong but same-lane, same-verdict* event id would not be caught by this live-replay check. It is still bounded on four sides — the frozen committed bytes (which record the original terminal event id) stay pinned byte-exact by `_exact_candidate` + the receipt `after_sha256`; any wrong event that shifts lane or verdict is still caught by the preserved terminal-state pins; a moved pointer must still name a real logged event (`_logged_event_ids`), so it cannot be fabricated; and the frozen-vs-`SOURCE` historical loop still pins both tolerated fields between the two frozen blobs. A per-(mission, WP) tolerance would close the remaining same-lane/same-verdict residual but is brittle; the outcome guarantee plus the byte pin cover the property that matters for historical fidelity. A focused self-mutation test (`test_replay_outcome_check_tolerates_only_logged_pointer_drift`) pins the rejection floor — lane/verdict/membership drift and a ghost pointer both raise — so the relaxation cannot drift vacuous.

## Alternatives considered

- **Re-materialise the frozen snapshots to the new reducer output.** Rejected: mutates archived artifacts and breaks the reviewed `RECOVERED`-blob / receipt provenance pins (those commits are immutable), trading a strong historical guarantee for churn on every future reducer fix.
- **Add the path to `_OPERATOR_SANCTIONED_CORRECTIONS`.** Rejected: that allowlist is consulted only by the ordinary-history violations loop, *after* `_check_snapshot`'s hard pins run, so it cannot lift the reducer-replay assertion for a pinned snapshot; and it is for sanctioned *byte corrections*, not for a derived-snapshot reducer evolution.
