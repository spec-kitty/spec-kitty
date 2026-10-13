---
affected_files: []
cycle_number: 2
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T16:38:19Z'
reviewer_agent: reviewer-renata
wp_id: WP06
---

# WP06 review cycle 2: REJECT (reviewer-renata), one blocker

The full evidence is in wp06-review-verdict.md (orchestrator scratchpad). Every cycle-1 item is verified as fixed. The reviewer's own lost-row test now passes, and the actor decision (a) is confirmed against the real projector. The decision on a Mission found while another subscriber is listening (b) is sound.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| C2-1 | medium | domain/model/Actor.java (`handle`); ActorOracleCases.java | The real oracle `Projector.actor`/`handle` (tests/contract/_mission_status_payloads.py, about lines 470-481) returns null for four resolver sentinels: `__resolved_model_absent__`, `__resolved_profile_absent__`, `__resolved_profile_version_absent__` and `__resolved_provider_absent__`. Real structured actors carry them (src/specify_cli/status/resolved_binding.py, about lines 37-40), but `Actor.handle` accepts them, so the Java would serve a sentinel to SSE consumers. The 54 cases were generated from `decode_actor` plus the contract regex, not from the projector, so none of them contains a sentinel. | Treat the sentinels as null in `Actor.handle`. Read the exact list from the projector source rather than from this table. Regenerate `ActorOracleCases` from the real `Projector.actor` (the served projection), not from `decode_actor` plus a regex. Add at least 3 sentinel cases: a string actor that equals a sentinel, a record whose `profile` is a sentinel, and a record whose `tool` is a sentinel. Add a revert row in which the sentinel check is removed and the tests go red. |

Recorded, no code change (orchestrator DD notes):
- C2-2: `"claude\n"` gives null in Java, where Python's `$` accepts a trailing newline. Java follows the contract pattern; this is a known divergence.
- C2-3: if B joins while a Mission no subscriber has found yet has a bad line in its history, the replay faults that Mission for every subscriber, giving `Dropped` plus one diagnostic. No row is lost or duplicated. Accepted.
