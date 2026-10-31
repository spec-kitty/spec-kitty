# Data Model — System status actor

Mission `system-status-actor-01M67HTR`. The model is small on purpose: this mission changes
the *value* of one existing field, not the shape of any record.

## Entities

### StatusActor (wire value of `StatusEvent.actor` / `InnerStateChanged.actor`)

The `actor` field is `str` **or** a dict of exactly four keys (`status/models.py`,
`ActorField`). The 5-key variant that adds `profile_source` is reader-accepted only and is
#6721's; no writer may emit it.

| Variant | Written by | Keys |
| --- | --- | --- |
| legacy string | any log written before #6400, and every system writer before this mission | — |
| agent/operator actor | `move-task`, `mark-status`, `add-history`, `action implement/review`, `status emit`, `orchestrator-api` (#6400) | `tool`, `role`, `profile`, `model` |
| **system actor (new)** | the 9 system writers listed below | `tool`, `role`, `profile`, `model` |

**Invariants**

1. `role ∈ {implementer, reviewer, system}` — the closed vocabulary of `status/actor.ActorRole`.
2. A system actor has `profile is None` and `model is None`, always. There is no code path
   that can pass a value (the builder takes only `tool`).
3. `tool` of a system actor is the identity the writer recorded before this mission — never a
   derived, shortened or defaulted name.
4. The dict has exactly the four keys; adding a fifth is a wire change and out of scope.
5. `actor_identity_str(actor)` is the same string for a system actor and for the string it
   replaces. This single property is what keeps every reader in place.

### ActorRole (closed vocabulary)

| Value | Meaning | Set by |
| --- | --- | --- |
| `implementer` | the actor claims, implements, annotates or marks subtasks | `role_for_hop` / `role_for_wp` from the lanes |
| `reviewer` | the actor claims review, approves, completes, or leaves review | same |
| `system` | the program wrote the event itself, with no agent dispatch behind it | the system builder only; never derived from a hop |

`role_for_hop` continues to answer only `implementer`/`reviewer`: a hop's role is a statement
about the lanes, and a system writer is not on a hop the lanes describe. Nothing in this
mission routes a hop through the system role.

### SystemWriter (the emit sites)

| # | Module | Event | `tool` | Family |
| --- | --- | --- | --- | --- |
| 1 | `status/bootstrap.py` | `genesis -> planned` seed per uninitialized WP | `finalize-tasks` | bootstrap |
| 2 | `lanes/recovery.py` | catch-up transitions after a crash | `recovery` | recovery |
| 3 | `consolidation/done_bookkeeping.py` | approval replay before the done mark | `merge` | bookkeeping |
| 4 | `consolidation/done_bookkeeping.py` | `-> done` after merge | `merge` | bookkeeping |
| 5 | `consolidation/preflight.py` | the done-write refusal probe (no write; same shape as #4) | `merge` | bookkeeping |
| 6 | `consolidation/preflight.py` | `InnerStateChanged` recording a `--skip-review-artifact-check` bypass | resolved operator identity | override |
| 7 | `consolidation/approved_attestation.py` | the `--attest-approved-reviewed` attestation | resolved operator identity | attestation |
| 8 | `consolidation/canceled_attestation.py` | the `--attest-canceled-superseded` attestation | resolved operator identity | attestation |
| 9 | `migration/wp_status_backfill.py` (×2) | `genesis -> planned` and `planned -> done` seeds | `migration:backfill_wp_status` | seed |
| 10 | `migration/backfill_runtime_state.py` (×2) | claim/runtime seed transitions and annotations | `migration:backfill_runtime_state` | seed |
| 11 | `migration/verdict_provenance_backfill.py` | historical `review_result` seed | `migration:verdict_provenance_backfill` | seed |

(Rows 3/4 and 9/10 are two emits each; the table has 11 rows naming 13 emits across nine writer modules —
SC-001's count.)

### SeedIdentity

The string that names an in-process reconstruction: `migration:<id>`. It survives as the
actor's `tool`, so:

| Predicate | Question | Answer for a string seed | Answer for a structured seed |
| --- | --- | --- | --- |
| `status.models.is_migration_actor` | is this *any* seed? | true (prefix) | true (prefix of the projected `tool`) |
| `migration.backfill_runtime_state._is_migration_actor` (Seam A) | is this *this* backfill's seed? | true (identity equality) | true (identity equality on the projected `tool`) |

The second is deliberately narrower than the first so that the ordering/verify guards stay
scoped to their own backfill; it is made shape-blind by projecting, not by widening.

### SeedRow

An immutable line in `status.events.jsonl`. Verified byte-semantically by
`backfill_runtime_state._seed_row_mismatch` against a rebuilt expectation.

| Difference from the rebuilt expectation | Verdict |
| --- | --- |
| none | sound |
| `at` only, and older than the current floor | sound (existing tolerance) |
| the pre-#2985 carrier payload | sound (existing tolerance) |
| **actor shape only** — same projected identity, string vs 4-key dict | **sound (Seam B, new)** |
| actor identity different (`migration:other`) | mismatch (unchanged) |
| any other slot | mismatch (unchanged) |

## State transitions

None. This mission adds no lane, no event type and no state-machine edge; it changes the
value of the `actor` field on events that already exist.

## Reader compatibility matrix

| Reader | Input: string seed | Input: structured seed | Kind of proof |
| --- | --- | --- | --- |
| `actor_identity_str` | identity verbatim | identity from `tool` | unit, both shapes |
| `is_migration_actor` | true | true | unit, both shapes |
| reducer seed arm (`status/reducer.py`) | seed | seed | reduction of a constructed log, both shapes |
| `validate_timestamp_continuity` | exempt | exempt | unit, both shapes |
| consolidation work-window rule (`wp_attribution.py`) | no window | no window | unit, both shapes |
| implementer-of-record (`review_roles.latest_implementer_event`) | skipped | skipped | unit, both shapes |
| `_latest_actor_for_transition` (consolidation preflight) | skipped | skipped | unit, both shapes |
| snapshot `actor` slot | same string | same string | reduction, byte-compare |
| `spec_kitty_events.diary.decode_actor` | str kept | dict copied, role `system` kept | contract pin |
| Java `Actor` handle (frozen; not edited) | `tool` = identity | same `tool`, `role` = `system` | reasoned from `Actor.java` + `ActorOracleCases` `structured-colon-joined-tool`; no Java run in this mission |
