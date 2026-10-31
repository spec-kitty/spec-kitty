# Contract — the system status actor

Mission `system-status-actor-01M67HTR` (issue [#6722](https://github.com/spec-kitty/spec-kitty/issues/6722)).
Internal Python contract only: no wire schema, no frozen path, no public CLI surface changes.

## 1. The builder

```python
# src/specify_cli/status/actor.py
class ActorRole(StrEnum):
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    SYSTEM = "system"          # new: the program wrote the event

def build_system_actor(tool: str) -> dict[str, str | None]:
    """{"tool": tool, "role": "system", "profile": None, "model": None}"""
```

**Guarantees**

- G-1 `set(result) == {"tool", "role", "profile", "model"}` — exactly the 4-key shape #6400 ships.
- G-2 `result["role"] == "system"`, `result["profile"] is None`, `result["model"] is None`.
- G-3 `result["tool"]` is the argument, unchanged. It is **not** split on `:` and not routed
  through `parse_agent_boundary_string`.
- G-4 A blank (`""` or whitespace-only) `tool` raises `ValueError`; an actor that names nobody
  is refused rather than recorded.
- G-5 The result survives `status.models.decode_actor` and
  `spec_kitty_events.diary.decode_actor` unchanged (all values `str | None`; `role` not enumerated).

**Non-goals**: this builder does not take a role, profile or model; it does not consult a
dispatch binding; it does not fall back to a default identity.

## 2. The writer obligation

Every emit site in the table below MUST pass `build_system_actor(<identity>)` as the event's
`actor`. No module may hand-assemble the four keys, and none may pass a bare string.

| Module | Site | Identity argument |
| --- | --- | --- |
| `status/bootstrap.py` | `emit_status_transition_transactional` seed | `"finalize-tasks"` |
| `lanes/recovery.py` | `emit_status_transition_transactional` catch-up | `RECOVERY_ACTOR` (built from `"recovery"`) |
| `consolidation/done_bookkeeping.py` | approval replay | `SYSTEM_MERGE_ACTOR` (built from `"merge"`) |
| `consolidation/done_bookkeeping.py` | done mark | `SYSTEM_MERGE_ACTOR` |
| `consolidation/preflight.py` | done-write refusal probe | `SYSTEM_MERGE_ACTOR` (same shape as the real write) |
| `consolidation/preflight.py` | override annotation event | `build_system_actor(_resolve_merge_actor(repo_root))` |
| `consolidation/approved_attestation.py` | attestation | `build_system_actor(actor)` at the `TransitionRequest` |
| `consolidation/canceled_attestation.py` | attestation | `build_system_actor(actor)` |
| `migration/wp_status_backfill.py` | both seeds | `WP_STATUS_BACKFILL_ACTOR` |
| `migration/backfill_runtime_state.py` | both seeds | `BACKFILL_ACTOR` |
| `migration/verdict_provenance_backfill.py` | review_result seed | `BACKFILL_ACTOR` |

Where a named constant already exists (`RECOVERY_ACTOR`, `WP_STATUS_BACKFILL_ACTOR`,
`BACKFILL_ACTOR`, and a new merge constant), the constant holds the built dict and its
identity string is kept beside it, so the seams and the data-plane tests compare identities.

## 3. The reader contract (unchanged, pinned by test)

| Reader | Contract |
| --- | --- |
| `actor_identity_str` | A dict projects to its `tool`; a string is returned verbatim. A system actor and the string it replaces project to the same text. |
| `is_migration_actor` | True iff the projected identity starts with `migration:`. True for a string seed and for a structured seed. |
| `status.reducer` seed arm | A seed claim counts only when no other claim exists — for either shape. |
| `validate_timestamp_continuity` | A `migration:` actor is exempt, for either shape. |
| `consolidation.wp_attribution` | A `migration:` event never opens, closes or extends a consolidation work window, for either shape. |
| `status.review_roles.latest_implementer_event` | A `migration:` event is never the implementer of record, for either shape. |
| `consolidation.preflight._latest_actor_for_transition` | A `migration:` event and an operator attestation are skipped, for either shape. |
| `actor_full_identity` / `actor_compact_identity` | **Not changed.** No caller consults a seed's full identity (audited), and the mixed-shape reduction test pins that the difference is unobservable. |

## 4. Compatibility contract for stored rows

1. Rows are never rewritten, reordered or compacted by this mission.
2. A stored string-actor row keeps its meaning: `decode_actor` returns `str` unchanged and the
   readers in §3 answer exactly as they did before.
3. `backfill_runtime_state.verify_backfill` accepts a stored seed row whose **only** difference
   from the rebuilt expectation is the actor's shape (same projected identity; both shapes
   allowed). A different identity, or any other slot, stays a hard, fail-closed mismatch.
4. A corpus that mixes shapes in one log must reduce to the same snapshot as the all-string
   corpus. This is the acceptance bar for the whole change.

## 5. Out of contract

- `profile_source` (fifth key) — #6721.
- The refusal of a caller-supplied `migration:` actor — #6754 / PR #6838.
- The role of a lane hop (`role_for_hop`) — still `implementer`/`reviewer` only.
- Any edit under `services/`, `contracts/`, `acceptance-jvm/` (ADR `2026-10-29-1` D-9).
- The three non-status actor strings that never reach a status event: `"status-read"` (a
  read-only request identity), `"cli"` (a throwaway wire probe), `"finalize-scaffold"` (an
  issue-matrix commit actor).
