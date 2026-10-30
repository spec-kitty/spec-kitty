# Research: caller-supplied `migration:` actors are not seeds (#6754)

Grounded 2026-10-30 on `main` @ `567ee` (`512567eee7`) in `/home/exedev/work/sk-6754`.
Scope guidance from the operator's dispatch: close the seed-spoofing hole without
breaking legitimate reconstruction; pin the refusal/allowed matrix with tests; state
the compatibility consequence in the changelog.

## D-1 — The defect still reproduces on current `main` (not superseded)

`tests/status/test_status_emit_structured_actor_6400.py::test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed`
**passes on the base** and asserts exactly the defect: `agent status emit WP01 --to claimed
--actor migration:backfill` stores `{"tool": "migration:backfill", "role": "implementer",
...}`, and the stored actor is a reconstruction seed for (a) `is_migration_actor`, (b) the
package reducer `spec_kitty_events.diary._is_reconstruction_seed`, and (c) the public
`diary.reduce` behaviour probe (`tests/_support/reconstruction_seed.py`).

- `git log --all --grep=#6754` → nothing; `grep -rn 6754 src tests docs` → nothing. Only
  `[#6400]` (PR #6774, merged) touches this code, and it deliberately *kept* the behaviour
  ("A `migration:` `--actor` is stored whole as `tool` so it keeps its seed status", its own
  test docstring). Not superseded, not fixed.
- Issue is OPEN, unassigned, no labels, no comments before our claim.

## D-2 — Where a seed can enter the log today, and why the string alone classifies it

`is_migration_actor` (`src/specify_cli/status/models.py:260`) classifies on
`actor_identity_str(actor).startswith("migration:")` — a plain string prefix, projected
through `tool` for a structured actor. Nothing else marks a seed, so *any* writer that
records a caller-chosen string beginning with `migration:` creates one.

In-process producers all construct their rows directly and never go through the emit shell:

| Producer | Seam | Actor |
| --- | --- | --- |
| `migration/wp_status_backfill.py` | builds `StatusEvent` rows directly | `migration:backfill_wp_status` |
| `migration/backfill_runtime_state.py` | `status._unsafe.append_event_stream_atomic_verified` | `migration:backfill_runtime_state` |
| `migration/verdict_provenance_backfill.py` | `status._unsafe.append_events_atomic_verified` | `migration:verdict_provenance_backfill` |

`status._unsafe.ALLOWED_CALLERS` is an enumerated, shrink-only allowlist guarded by
`tests/architectural/test_status_unsafe_allowlist.py`; no CLI command module is (or may
become) an entry. So "in-process, allowlisted, non-CLI module" is already an enforced
structural property we can lean on.

## D-3 — The spoofable surfaces are exactly the ones that record the value verbatim

Survey of every `--actor` / `--agent` option that reaches a status write:

| Surface | Builder | `--actor migration:x` today | Seed? |
| --- | --- | --- | --- |
| `agent status emit --actor` | `actor_from_option` (lenient, keeps whole) | stored `{"tool": "migration:x"}` | **yes** |
| `orchestrator-api {start-implementation,start-review,transition,append-history} --actor` | `actor_from_option` | stored `{"tool": "migration:x"}` | **yes** |
| `spec-kitty implement --actor` (hidden, programmatic) | bare string `effective_actor` | stored `"migration:x"` | **yes** |
| `move-task --agent/--actor`, `mark-status --agent`, `add-history --agent`, `agent action implement|review --agent` | `build_status_actor` (strict compact parse) | stored `{"tool": "migration", "model": "x"}` | no |
| recorded identity re-recorded with **no** caller flag (`_mt_structured_actor`, `_add_history_actor` → `actor_from_option`) | lenient | stored `{"tool": "migration:backfill"}` | **yes, deliberately** |

The last row is #6400's pinned behaviour and the operator's 2026-10-29 ruling for the
`--agent` row (`test_explicit_migration_agent_is_parsed_strictly_and_is_not_a_seed`,
`test_recorded_migration_reviewer_identity_stays_a_reconstruction_seed`). Both must survive.

## D-4 — Decision: refuse at the boundary, do not rewrite, do not touch the wire (Option 1)

The issue offers two options. Option 2 (an explicit seed field on the events contract) needs
a `spec-kitty-events` release plus the Java write core (spec-kitty-events#92) and is frozen
by ADR `2026-10-29-1` (events domain moves out of core). **Option 1 is implemented here**:
refuse a caller-supplied seed-shaped identity at the surfaces that would record it verbatim,
leaving in-process migration writers as the only producers.

Rejected alternatives, with reasons:

- **Silently strip/re-parse the prefix into a live actor** (what `actor_from_option` already
  does for `--agent`): it records an identity the caller never wrote and never meant, which
  is worse for a security-shaped change than a loud refusal.
- **Refuse inside `emit_status_transition` unconditionally**: it would break the two
  legitimate recorded-identity re-record paths (D-3, last row) and #6400's pinned
  behaviour. The refusal belongs where the *caller* is, not where a recorded value is
  replayed.
- **Refuse the `--agent` row too**: it cannot spoof (strict parse yields tool `migration`,
  never a seed) and the operator ruled it allowed on 2026-10-29; refusing it would be a
  second behaviour change with no security gain. The asymmetry is documented and pinned.

## D-5 — Decision: make the lenient builder fail closed

`actor_from_option` has six call sites: four are caller-supplied (refuse), two are
recorded-identity replays (allow). Defaulting the builder to *refuse* and letting the two
replays opt in with `recorded=True` makes a future call site fail closed instead of
silently re-opening the hole, and keeps the rule in one place (charter, single canonical
authority). The three surface guards remain, so the user-facing refusal message does not
depend on catching a `ValueError` from deep inside an emit.

## D-6 — Compatibility consequence (goes in the changelog)

Any caller that today passes `--actor migration:…` (or the hidden `implement --actor`) gets
a loud refusal (exit 1, no write) instead of a silently-seeded event. No shipped code path
does this (`grep` of `src/`, `scripts/`, `docs/`, `tests/`, packs), so the practical impact
is on third-party orchestrators that invented a seed actor; the remedy is to pass the live
identity they actually are. Stored logs are unaffected: the change is write-side only.

## Open questions

- None blocking. The deferred Option 2 is tracked by spec-kitty-events#92; this Mission's PR
  cites it in `## Deferred`.
- Whether the `--actor` refusal should also apply to non-status writers (consolidation
  acceptance records, decision verbs, tracer lines) — out of scope here (C-004); those
  actors never reach `is_migration_actor`.
