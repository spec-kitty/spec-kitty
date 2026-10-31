# Discovery — system status actor (#6722)

Grounding run on `main` at `512567eee7`, branch `issue-6722-system-status-actor`.
Everything below was read from the tree, not remembered.

## 1. The issue still reproduces

`git grep -n 'actor="' -- src/` (system writers, all still bare strings on current `main`):

| Site | Identity recorded today |
| --- | --- |
| `src/specify_cli/status/bootstrap.py:194` | `"finalize-tasks"` |
| `src/specify_cli/lanes/recovery.py:817` (constant `RECOVERY_ACTOR`) | `"recovery"` |
| `src/specify_cli/consolidation/done_bookkeeping.py:273`, `:425` | `"merge"` |
| `src/specify_cli/consolidation/preflight.py:1240` (done-write refusal probe) | `"merge"` |
| `src/specify_cli/consolidation/preflight.py:449` (review-artifact override annotation) | resolved operator identity (`_resolve_merge_actor`, `done_bookkeeping.py:88`) |
| `src/specify_cli/consolidation/approved_attestation.py:237` | resolved operator identity |
| `src/specify_cli/consolidation/canceled_attestation.py:165` | resolved operator identity |
| `src/specify_cli/migration/wp_status_backfill.py:279`, `:302` (`WP_STATUS_BACKFILL_ACTOR`) | `"migration:backfill_wp_status"` |
| `src/specify_cli/migration/backfill_runtime_state.py:873`, `:1022` (`BACKFILL_ACTOR`) | `"migration:backfill_runtime_state"` |
| `src/specify_cli/migration/verdict_provenance_backfill.py:394` (`BACKFILL_ACTOR`) | `"migration:verdict_provenance_backfill"` |

Not superseded: no merged PR moves them. `git log --oneline -30 --grep="6400\|6755\|actor"` ends at `991739f88b` (#6400, the agent/operator paths) and `1727c325ef` / `20201ff356` (its completion manifest and docs). `docs/architecture/status-model.md:428` still says "**Still strings.** System writers keep writing a string actor: migrations (`migration:...`), consolidation bookkeeping, bootstrap, recovery and the consolidation attestations." — the boundary #6400's spec carved out on purpose (spec.md:16 of `status-contract-readers-01M5ZAAC`).

## 2. What the surrounding machinery already accepts

- `status/models.py:166` — `ActorField: str | dict[str, str | None]`; `TransitionRequest.actor` is already `ActorField | None` (`models.py:1074`) and `emit_inner_state_changed(actor=...)` already documents "a string or the structured actor" (`status/emit.py:1254`). A dict actor needs no plumbing.
- `status/models.decode_actor` accepts the 4-key `{role, profile, tool, model}` dict, every value `str | None`; it does **not** enumerate `role`.
- `spec-kitty-events` pin is `>=11.3.0,<12` (`pyproject.toml:80`); the installed `spec_kitty_events/diary.py:267` `decode_actor` carries the identical rule (keys + `str | None`), with no `role` vocabulary.
- Java `Actor` (`services/mission-status-api/domain-model/.../Actor.java:20`) is a record of three handles validated by `^[A-Za-z0-9._:-]{1,128}$` and a four-entry resolver-sentinel set; it does not enumerate `role` either, and `ActorOracleCases.java` already pins `structured-colon-joined-tool` (`tool: "claude:opus:implementer"` → kept whole), which is the shape a `migration:<id>` tool takes.
- Therefore `role: "system"` crosses the CLI reader, the events decoder and the Java write core with **no** release bump and **no** frozen-path edit. ADR `4.x/2026-10-29-1` D-9 freezes `services/`, `contracts/mission-status`, `contracts/mission-write`, `contracts/_shared`, `contracts/tools`, `contracts/lint` and `docs/architecture/event-ledger-writers-and-readers.md`; enforced by `tests/architectural/test_events_import_frozen.py`.

## 3. Reader projections, and the one asymmetry found

- `actor_identity_str` (`models.py:244`) projects a dict to its `tool` and a string to itself → **identical for both shapes**, so `is_migration_actor` (`models.py:260`), the reducer's seed arm (`status/reducer.py:170`), `validate_timestamp_continuity` (routed through `is_migration_actor` since #6271, `2f249123d9`), `wp_attribution.py:253` and the reduced snapshot's `actor` slot all keep their exact rule.
- `actor_full_identity` (`models.py:301`) **would** differ for a colon-carrying format: structured `{tool: "migration:backfill_runtime_state"}` → `migration:backfill_runtime_state::`; the string → `migration:backfill_runtime_state:` (the string is split by `parse_agent_boundary_string`). Audited every caller: `consolidation/preflight.py:561` (`_latest_actor_for_transition`, skips seeds at `:554` and attestations), `:594` (`latest_implementer_event`, `review_roles.py:58` excludes seeds), `cli/commands/agent/tasks_move_task.py:1102` (same helper), `status/work_package_lifecycle.py:282` (implementer-of-record label, only reached for a non-seed). **No reader compares a seed's full identity**, so the projection is left as #6400/#6715 pinned it and the property is proven by a mixed-shape reduction test instead of changed.

## 4. The two places that *do* break if the writers change shape

1. `src/specify_cli/migration/backfill_runtime_state.py:331` — `_is_migration_actor(actor)` is `actor == BACKFILL_ACTOR`. With `BACKFILL_ACTOR` structured, every string seed already in a log stops matching, and `_stream_without_migration` (`:1085`) then treats those rows as authentic history. Must become shape-blind.
2. `src/specify_cli/migration/backfill_runtime_state.py:1672` — `_seed_row_mismatch` compares `actual.to_dict() == expected.to_dict()`, and the payload includes `actor`. Seed rows are immutable and deduplicated on `event_id`, so a corpus seeded before this change holds string-actor rows that the new code would rebuild as structured: every one would report "deterministic seed payload diverged" and `verify_backfill` would fail closed on a healthy mission. The function already tolerates two legitimate pre-existing shapes (a pre-floor `at` at `:1674`, the pre-#2985 carrier at `:1676`); the actor's shape is the same kind of tolerated difference.

`wp_status_backfill` (idempotent by `initialized_wp_ids`) and `verdict_provenance_backfill` (idempotent by the `slot_present` read, `:330`) compare no payloads, so they need no tolerance.

## 5. Decisions taken

- **D-1 — the shape.** `{tool: <the identity recorded today>, role: "system", profile: null, model: null}`. Same 4 keys; one new role value; `tool` unchanged so every projection and every gate keeps its rule.
- **D-2 — `tool: "spec-kitty"` rejected.** It collapses six auditable identities into one and makes `is_migration_actor` false for every newly written seed, which is exactly the "gates must keep classifying seeds" bar the issue sets.
- **D-3 — the `migration:` prefix stays in `tool`.** Stripping it would re-decide #6093/#6271 around `role` and leave old and new rows classified by two different rules.
- **D-4 — no fifth key.** `profile_source` is #6721's, gated on an events release.
- **D-5 — the `ReviewOverride` delta slot stays a string.** Its four `str` fields are a pinned shape (`models.py:633`); only the *event's* `actor` becomes structured at that site, so the operator identity still lands in `policy_metadata`/delta evidence and in `tool`.
- **D-6 — `contracts/` and `services/` untouched.** ADR `2026-10-29-1` D-9; nothing there needs to change anyway (§2).

## 6. Sibling work and boundary

- **#6754 / PR #6838 (open)** refuses a caller-supplied `actor` starting with `migration:` on `agent status emit`, the four `orchestrator-api` verbs and `implement`, and makes `actor_from_option` fail closed unless `recorded=True`. It edits `status/models.py`, `status/actor.py`, `status/__init__.py` and the CLI/orchestrator surfaces. This mission depends on none of it, duplicates none of it, and leaves the emit shell alone: the three backfills build their rows directly, which is exactly the "the only seed producers" set #6838 names. Overlap with #6838 is limited to additive lines in `status/actor.py` (a new builder) and `status/models.py` (docstrings).
- **#6721** adds `profile_source` and the frontmatter fill after an events release. Untouched here.
- **#6755** hardens `parse_agent_boundary_string`. Untouched here; the system builder deliberately does **not** route a system identity through that parser (a `migration:<id>` tool would be split).

## 7. Open questions

- None blocking. Two recorded as decided-not-asked: the role value is `system` (not a fourth `operator`); the attestation actor's human identity stays in `tool` rather than being mapped to `spec-kitty` + `profile`.
