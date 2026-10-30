# Data model: caller-supplied identities vs reconstruction seeds (#6754)

## Entities

### Reconstruction seed

An event row whose actor is classified as a migration-synthesized identity: a
best-effort restatement of history the log already records, produced in-process by a
migration module. It is never a governed decision.

| Attribute | Value |
| --- | --- |
| Classifier | `specify_cli.status.models.is_migration_actor` — exact, case-sensitive `migration:` prefix on `actor_identity_str(actor)` |
| Structured form | `{"tool": "migration:<module>", "role": …, "profile": null, "model": null}` |
| Bare form | `"migration:<module>"` |
| Semantic weight | yields to live history in the reducer's seed arms; skipped by `validate_timestamp_continuity`; never opens or closes a consolidation work window (FR-011, ADR `2026-09-29-1`); exempt from the review-exit force-note rule (#5446) |
| **Only producers** | `migration/wp_status_backfill.py`, `migration/backfill_runtime_state.py`, `migration/verdict_provenance_backfill.py` — all inside `src/specify_cli`, none reachable from a CLI option |

### Caller-supplied identity

The value of an `--actor` (or `--agent`) option as typed on a command line. Two
recording shapes exist, and only one can produce a seed:

| Recorder | Shape | Seed possible? |
| --- | --- | --- |
| Verbatim (`actor_from_option`, bare-string `implement --actor`) | keeps the typed text whole | **yes, today** |
| Strict compact parse (`build_status_actor` via `--agent` on move-task / mark-status / add-history / action implement / action review) | `tool` is the segment before the first `:` | no — `migration:x` becomes tool `migration` |

### Recorded identity

An identity read back out of the event log (a recorded reviewer or implementer) and
re-recorded by a later command that was given **no** caller identity option. It is not a
caller-supplied value; when it is seed-shaped it must keep its seed status (FR-006).

### Refusal

The outcome when a caller-supplied identity is seed-shaped.

| Attribute | Value |
| --- | --- |
| Trigger | the value, as typed, starts with `migration:` |
| Effect | the command exits non-zero with the canonical message; 0 events appended, 0 snapshots materialized, 0 worktrees created, no write lock taken |
| Message shape | names the option, states that seeds are written in-process by migrations only, points at the remedy (pass the live identity) |
| Never | the value is never stripped, escaped, re-parsed or otherwise rewritten into a live-looking actor (FR-010) |

## Invariants

1. **Only in-process migrations produce a seed.** After this Mission no CLI option value,
   on any surface, can result in an event whose actor is classified by
   `is_migration_actor`.
2. **The refusal is total.** A refused invocation leaves the event log byte-identical
   (NFR-001).
3. **Recorded seeds survive.** An existing seed re-recorded with no caller option keeps
   its actor and its seed status unchanged (#6400's pinned behaviour, FR-006).
4. **`--agent` never seeds.** A strictly parsed compact value yields tool `migration`,
   which `is_migration_actor` does not classify as a seed (operator ruling 2026-10-29,
   FR-007).
5. **One authority.** The prefix, the classifier and the refusal predicate live in
   `status/models.py`; surfaces call them (NFR-005).
6. **Reader side frozen.** `is_migration_actor`, the reducer's seed arms, timestamp
   continuity and the consolidation window rule are not modified (C-003).

## State rules

| Situation | Before | After |
| --- | --- | --- |
| `status emit --actor migration:x` | event appended, actor `{"tool": "migration:x"}` (a seed) | refused, exit 1, nothing appended |
| `orchestrator-api <verb> --actor migration:x` | event appended (a seed) on all four verbs | refused, `error_code: USAGE_ERROR`, nothing appended |
| `implement --actor migration:x` (hidden) | claim appended with bare-string actor `migration:x` (a seed) | refused, exit 1, no workspace, no claim |
| `move-task --agent migration:x` | tool `migration`, not a seed | unchanged |
| `mark-status`/`add-history --agent migration:x` | tool `migration`, not a seed | unchanged |
| `move-task` with a recorded seed identity and no `--agent` | re-recorded seed | unchanged |
| `add-history` with a recorded seed identity and no `--agent` | re-recorded seed | unchanged |
| a migration backfill writing its own rows | seed | unchanged |
| reading a legacy log that already holds a caller-produced seed | reduces as a seed | unchanged |

## Out of scope

An explicit seed field on the event payload (the issue's Option 2). It changes the
`spec_kitty_events` contract and the Java write core, both frozen by ADR `2026-10-29-1`;
tracked as spec-kitty-events#92 and named in the PR's `## Deferred` section.
