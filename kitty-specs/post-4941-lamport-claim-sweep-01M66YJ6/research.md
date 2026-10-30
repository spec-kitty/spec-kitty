# Discovery findings — post-#4941 "Lamport-ordered status path" claim sweep

Mission: `post-4941-lamport-claim-sweep-01M66YJ6` (issue #6604).
Grounded on `main` at `512567eee71e31bb39f580c4f7acf8b865e9d1b2`.

## What the code does now (the fact every claim must match)

- `src/specify_cli/status/reducer.py:17-18` imports `reduce_parsed` from
  `spec_kitty_events.diary` and `reduce as reduce_shared_state` from
  `spec_kitty_events.status`.
- `status.reducer.reduce` (`:205`) calls `reduce_parsed` directly.
- `materialize_snapshot` (`:401`) calls
  `reduce_shared_state(read_events_raw(...))`. `reduce_shared_state` is a
  re-export of `diary.reduce` (parse, then `reduce_parsed`).
- So there is **one** reducer reached through **one** fold
  (`spec_kitty_events` 11.3.0 in this tree), not a "Lamport wrapper" next to a
  wall-clock reducer.
- Ordering key: `diary._order_transitions` sorts by `(at, event_id)`, with the
  approved-departure lift — a non-seed event leaving `approved` has its *sort*
  `at` lifted to the approval it departed (`_approved_departure_sort_at`,
  `_carry_lifted_sort_at`). Docstring names spec-kitty-events#101 /
  spec-kitty#4941. Stored `at` is untouched.
- CLI lane rows carry **no** Lamport clock; `spec_kitty_events.status.reduce_status_events`
  is absent from the CLI status path (the `reduce_status_events` names under
  `src/` are local aliases of `specify_cli.status.reduce`).
- Residual that is still true: a **non-approval** transition minted on a clock
  behind the event it follows (e.g. `in_review -> in_progress`) still sorts
  before that event; the lift covers departures from `approved` only.
- The consolidation gate has no separate protection: `build_approved_wp_set`
  reads WP membership through `materialize_snapshot`, i.e. the same fold.

## Decisions

1. **Correct claims; do not re-decide ordering.** ADR bodies are historical
   records. ADR `2026-01-27-11`, `2026-01-27-12`, `2026-10-22-1`, `2026-10-13-2`
   and the shipped amendments to `2026-02-09-3` / `2026-10-14-1` are correct as
   they stand and are left alone. ADR `2026-10-01-2` keeps its original text and
   gains a new factual amendment (same shape as its `2026-10-03`, `2026-10-12`
   and `2026-10-29` amendments), crediting the 2026-10-22 ruling. Rationale: the
   issue's scope line says "the remaining ADR wording work is the factual
   amendment to ADR 2026-10-01-2 (no new ordering decision)", and its
   2026-10-23 refresh checklist says "Preserve original ADR history and its
   amendment."
2. **Living pages get edited in place, not amended.** A living C4 page or a
   domain plan that describes the current read path must simply be right.
   Affected: `docs/architecture/diagrams/01_context/README.md` (prose + mermaid
   node label), `02_containers/README.md` (prose + alt-text + mermaid node
   label), `docs/plans/domains/api-dashboard-domain-plan.md` (§4 known gap 2).
3. **`AGENTS.md` "Status Model Patterns" is stale in three ways, not one.**
   It still says the `consolidation/` docstrings call the reducer "the Lamport
   wrapper" and that `#6213` tracks fixing them (they were corrected in
   `reconciliation.py:26-34` / `:1464-1471`); it still describes the gate as
   unprotected against a clock-behind rejection (the lift closed that case); and
   it describes `#4941` as the live residual rather than the narrower
   non-approval skew. `CLAUDE.md` is a **symlink** to `AGENTS.md`, so one edit
   covers both — the guard test must read the symlink target rather than assume
   two files.
4. **One code comment is in scope.** `consolidation/preflight.py:524`
   (`_latest_actor_for_transition`) claims ADR `2026-02-09-3` "orders events
   causally (Lamport-primary)" as the rule it follows. The ADR was amended on
   2026-10-22 to wall clock; the docstring must cite the amended record and
   still keep its real reason for reading append order (a `StatusEvent` has no
   clock to sort on and the append-only log *is* the causal order available).
5. **Gap G-3 closes.** `docs/architecture/event-ledger-writers-and-readers.md`
   is the evidence page the issue cites; its G-3 row ("file new (#6213 closed
   after step 1 only)") is the tracker line for exactly this sweep and must
   record the closure and the residual, not stay "file new".
6. **The guard test asserts absence of retired wording plus presence of the
   sharper residual**, and is written to fail if this mission's wording is
   reverted. Design: a table of retired phrases (the exact strings removed, per
   file) over a named living corpus; a corpus-wide regex for the affirmative
   `Lamport (reducer|reduction|wrapper)` phrasing with an explicit negation
   allowance (the corrected `status-model.md` legitimately says "not
   Lamport-ordered" and "no Lamport clock"); and an ADR-shape assertion that
   `2026-10-01-2` still carries its original decision text *and* a current
   amendment recording wall clock. Non-vacuity: the detector is fed a synthetic
   stale line and a synthetic negated line and must classify both correctly.

## Explicitly out of scope (recorded so a reviewer does not think it was missed)

- Editing the #5528 / #6117 issue bodies — the issue says this pass coordinates
  them and does not edit them.
- Any change making ordering truly Lamport-primary (#6609, post-GA, needs its own
  ADR and a clock on CLI rows: spec-kitty-events#72).
- Historical artifacts: `docs/archive/`, `docs/reports/`, `research/`,
  `kitty-specs/**` (past missions), and ADR bodies.
- `docs/operations/manual-test-plan.md` §2.2 (`Verify Lamport clock ordering`,
  `lamport_clock` envelope field): it documents the retired SaaS sync surface
  (`queue.jsonl`, WebSocket), not the CLI status path. Pre-existing staleness of
  a different subsystem; reported, not swept here.
- `docs/context/system-events.md` "Lamport Clock" glossary entry: a definition
  of the envelope field (status canonical for `1.x`/`2.x`), not a claim that the
  status path is Lamport-ordered. Lamport fields genuinely still exist on other
  logs (retrospective lifecycle events tick a Lamport counter).
