# Implementation Plan: post-#4941 status-path claim sweep (#6604)

**Branch**: `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6` |
**Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/post-4941-lamport-claim-sweep-01M66YJ6/spec.md`

## Summary

Correct every surviving affirmative claim that the CLI status path is Lamport-ordered, in
the places #6604 names: ADR `2026-10-01-2` (by a factual amendment, history preserved), the
two living C4 pages, the API/dashboard domain plan, the `AGENTS.md`/`CLAUDE.md` "Status
Model Patterns" section, and one `consolidation/preflight.py` docstring. Close gap G-3 in
`docs/architecture/event-ledger-writers-and-readers.md`. Add a bounded guard test that
fails when the retired phrasing returns to a covered file, and a changelog entry.

The code is not touched (other than one docstring). The one statement that must survive is
the narrower residual: a **non-approval** transition minted on a clock behind the event it
follows still sorts before that event; the approved-departure lift (#4941 / PR #6261,
`spec-kitty-events` 10.5.1) covers departures from `approved` only.

## Technical Context

**Language/Version**: Python 3.11 (repo floor), Markdown; no runtime code change except a
docstring.
**Primary Dependencies**: `spec-kitty-events` 11.3.0 (pinned `>=11.3.0,<12`) — the reducer
lives there (`spec_kitty_events.diary.reduce_parsed`, `_order_transitions`).
**Storage**: n/a (docs + one docstring + one test).
**Testing**: pytest. New guard test is a pure filesystem/text test (no git subprocess, no
network), `pytest.mark.architectural` + `pytest.mark.docs_scoped` so it runs on the
docs-only CI trim.
**Target Platform**: repo CI (Linux).
**Project Type**: single project (CLI + docs).
**Performance Goals**: guard test under 5s; bounded corpus (about 10 files).
**Constraints**: no behaviour change; no ordering decision; ADR bodies preserved; the
guard must not ban the word `Lamport` where other logs legitimately carry it.
**Scale/Scope**: 1 ADR amendment, 3 living pages, 2 agent-guideline spots (one file via
symlink), 1 docstring, 1 gap-table row, 1 guard test, 1 changelog entry.

### The facts the corrected wording must state

| Fact | Where it comes from |
|---|---|
| One reducer, two parsers | `status/reducer.py:17-18` (`reduce_parsed`, `reduce as reduce_shared_state`), `:205` (`reduce`), `:401` (`materialize_snapshot`) |
| Ordering key `(at, event_id)` | `diary._order_transitions` docstring + key tuple |
| Approved-departure lift | `diary._order_transitions` → `_approved_departure_sort_at`, `_carry_lifted_sort_at`; names spec-kitty-events#101 / spec-kitty#4941 |
| CLI lane rows have no Lamport clock | `status/models.py` `StatusEvent` (no clock field); `spec-kitty-events` 11.3.0 |
| `reduce_status_events` is off the CLI path | no import of it in `src/`; the `src/` names are aliases of `specify_cli.status.reduce` |
| Narrower residual survives | non-approval departure (e.g. `in_review -> in_progress`) has no approve-anchor to be lifted against |
| Consolidation gate has no separate protection | `consolidation/reconciliation.py::build_approved_wp_set` reads through `materialize_snapshot` |

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this mission satisfies it |
|---|---|
| Single canonical authority (DIRECTIVE_044) | Each fact is stated once from the code; the guard test is the single enforcement point for the wording. |
| Canonical sources / docs freshness | Living pages edited in place; ADR corrected by amendment (its own Amendment Process); docs index / ADR inventory / freshness gates re-run. |
| Locality of change (DIRECTIVE_024) / smallest viable diff | Only the sentences that carry the retired claim change; no page is restructured. |
| ATDD-first (DIRECTIVE_034) | The guard test is written first and shown red against the *unmodified* tree, then the wording is corrected until it is green. |
| Tracker Ticket Assignment Rule | #6604 claimed (comment + assignee + `status:claimed` + `taken-by-human`) before any planning artifact. |
| Pre-existing Failure Reporting Rule | Any red outside the diff is reproduced on pristine `origin/main` and reported, not silenced. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only the new guard test, the docs gates, and the touched-area tests run. |
| Bulk-edit practice | Not a bulk edit: different sentences in different files, no shared identifier. `meta.json` stays `change_mode: normal`; no `occurrence_map.yaml`. |
| Supply-chain security | No dependency added, upgraded or removed. |

No violations. No `[NEEDS CLARIFICATION]` markers: the issue's 2026-10-23 scope refresh and
the 2026-10-22 operator ruling fix the scope, and the code pins the facts.

## Project Structure

### Documentation (this mission)

```
kitty-specs/post-4941-lamport-claim-sweep-01M66YJ6/
├── plan.md       # this file
├── research.md   # discovery + Phase 0 findings
├── spec.md
├── tasks/        # work-package prompts (from /spec-kitty.tasks)
└── tasks.md
```

No `data-model.md`, `contracts/` or `quickstart.md`: the mission defines no entity, no
interface and no runnable surface. `meta.json` records `"contracts": "none"` with a
rationale so `accept` waives the directory.

### Source Code (repository root)

```
docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md   # + amendment
docs/architecture/diagrams/01_context/README.md                                 # prose + mermaid node
docs/architecture/diagrams/02_containers/README.md                              # prose + alt-text + mermaid node
docs/architecture/event-ledger-writers-and-readers.md                           # G-3 row
docs/plans/domains/api-dashboard-domain-plan.md                                 # §4 gap 2
AGENTS.md                                                                       # Status Model Patterns (CLAUDE.md is a symlink)
src/specify_cli/consolidation/preflight.py                                      # _latest_actor_for_transition docstring
docs/changelog/CHANGELOG.md                                                     # [Unreleased]
tests/architectural/test_status_path_ordering_claims.py                         # new guard
```

**Structure Decision**: Documentation and one docstring in their existing homes; the guard
test joins the architectural gate family because it enforces a durable invariant over a
named corpus, and carries `docs_scoped` because it reads `docs/`.

## Exact change set (wording, per site)

1. `docs/architecture/diagrams/01_context/README.md`
   - `:105` "owns the event ledger and the Lamport reducer" → "owns the event ledger and
     the wall-clock status reducer (`(at, event_id)`, with the approved-departure lift)".
   - `:139` mermaid node "owns event ledger + Lamport reducer" → "owns event ledger +
     wall-clock status reducer".
2. `docs/architecture/diagrams/02_containers/README.md`
   - `:251` "owns the append-only event ledger and the Lamport reducer" → the wall-clock
     fold, naming `status.reducer.materialize_snapshot` → `diary.reduce_parsed`.
   - `:266` alt-text "the Lamport reducer" → "the wall-clock status reducer".
   - `:285` mermaid node `<b>Lamport reducer</b><br/>status.reducer.materialize` →
     `<b>Status reducer</b><br/>status.reducer.materialize_snapshot<br/>wall clock (at,
     event_id)`.
3. `docs/plans/domains/api-dashboard-domain-plan.md` §4 gap 2: replace the two-reducer
   sentence with the one-reducer fact plus the residual and the #6609 direction.
4. `AGENTS.md` "Status Model Patterns": the paragraph becomes today's truth — one reducer;
   the shipped lift (spec-kitty-events 10.5.1, PR #6261); the corrected `consolidation/`
   docstrings (`reconciliation.py:26-34`, `:1464-1471`); the narrow non-approval residual;
   the gate caveat kept; ADRs cited as amended. The `reduce()` table row loses
   "Not Lamport-ordered and not the ADR `2026-02-09-3` model; see `#4941`" in favour of
   the amended-ADR reference and the residual.
5. `docs/adr/4.x/2026-10-01-2-…md`: new `## Amendment 2026-10-30 (Accepted): the ordering
   is wall clock` after the 2026-10-29 amendment; frontmatter `updated: '2026-10-30'`;
   the Status block gains a one-line pointer. Body untouched.
6. `src/specify_cli/consolidation/preflight.py` `_latest_actor_for_transition`: cite ADR
   `2026-02-09-3` Amendment 2026-10-22 (wall clock, and why a `StatusEvent` carries no
   clock to sort on) instead of "orders events causally (Lamport-primary)".
7. `docs/architecture/event-ledger-writers-and-readers.md`: G-3 becomes **Closed (#6604)**
   with the files corrected, the guard test, and the surviving residual; the "Ordering:
   wall clock for 4.0.0" bullet's G-3 pointer follows.

## Implementation Concern Map

### IC-01 — Living pages and domain plan

- **Purpose**: make the pages that describe today's read path state the wall-clock fold,
  in prose, alt-text and diagram node labels alike.
- **Relevant requirements**: FR-001, FR-002, SC-001
- **Affected surfaces**: `docs/architecture/diagrams/01_context/README.md`,
  `docs/architecture/diagrams/02_containers/README.md`,
  `docs/plans/domains/api-dashboard-domain-plan.md`
- **Sequencing/depends-on**: none
- **Risks**: prose and the mermaid node/alt-text drift apart — each diagram edit must move
  all three together; the domain plan's gap entry must keep its "two read surfaces can
  disagree" *possibility* only if it is still true (it is not; the readers share one fold).

### IC-02 — ADR amendment and gap-table closure

- **Purpose**: record the accepted current ordering in the ADR that owns the read API,
  without rewriting its decision, and close the gap row that tracks this sweep.
- **Relevant requirements**: FR-003, FR-006, SC-003, SC-004
- **Affected surfaces**: `docs/adr/4.x/2026-10-01-2-…md`,
  `docs/architecture/event-ledger-writers-and-readers.md`
- **Sequencing/depends-on**: none (the wording established in IC-01 must match)
- **Risks**: an amendment that reads as a new decision instead of a factual record;
  forgetting the `updated:` frontmatter; leaving G-3's tracker cell saying "file new".

### IC-03 — Agent guidelines, code comment, guard test, changelog

- **Purpose**: teach agents the corrected model, keep the surviving residual visible, and
  make regression of the wording impossible to miss.
- **Relevant requirements**: FR-004, FR-005, FR-007, FR-008, FR-009, SC-002, SC-004
- **Affected surfaces**: `AGENTS.md` (and `CLAUDE.md` through the symlink),
  `src/specify_cli/consolidation/preflight.py`,
  `tests/architectural/test_status_path_ordering_claims.py`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02 — the guard asserts the corrected wording, so it
  is written first (red), then satisfied by IC-01/IC-02 plus this concern.
- **Risks**: a guard that greps the word `Lamport` and bans legitimate mentions (the
  retrospective lifecycle clock, `kernel/clock.py`'s "distinct from a Lamport logical
  clock"); a guard that passes vacuously when a covered path is missing; a guard that only
  checks absence and never proves it can detect the phrase.

### Guard test design (reference for tasks)

Module: `tests/architectural/test_status_path_ordering_claims.py`.

- `COVERED_PATHS`: the living pages, the domain plan, `AGENTS.md`, the gap-table page, and
  `src/specify_cli/consolidation/preflight.py`. Every path must exist (missing ⇒ failure,
  not skip). `docs/adr/**`, `docs/archive/**`, `docs/reports/**`, `research/**`,
  `kitty-specs/**`, `docs/changelog/**` are excluded from the *phrase* scan by
  construction (they are not in the list at all).
- `RETIRED_PHRASES`: the exact strings this mission removed, e.g.
  `"owns event ledger + Lamport reducer"`,
  `"the Lamport `reduce_shared_state`"`,
  `"ports the Lamport reduction"`,
  `"The dashboard uses the Lamport reducer"`,
  `"still call this the Lamport wrapper"`,
  `"`#6213` tracks correcting them"`.
- `AFFIRMATIVE_RE = re.compile(r"Lamport[\s-]+(reducer|reduction|wrapper)", re.I)` applied
  per line, skipped when the same line carries a negation marker (`not`, `never`, `no`,
  `NOT`) — the corrected `status-model.md` and gap-table lines say "not Lamport-ordered",
  "carry no Lamport clock", "is NOT the Lamport `reduce_status_events`".
- ADR assertions on `2026-10-01-2`: the original D-5 sentence
  `"moves them onto the Lamport reducer"` is still present (history preserved) **and** a
  `## Amendment 2026-10-30 (Accepted)` section exists that contains `(at, event_id)`,
  `lift`, and `#6609`.
- Non-vacuity: `_violations(text)` is fed a synthetic stale line (must report exactly one)
  and a synthetic negated line (must report none); a scan of zero covered files fails.

## Phase 0 / Phase 1 outputs

- Phase 0: `research.md` (already created in discovery; extended with the wording decisions
  and the guard design above).
- Phase 1: none — no entity, contract or runnable surface. `meta.json` gets
  `"contracts": "none"` and a `contracts_rationale`.

## Complexity Tracking

No charter violations.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| The amendment is read as a new ordering decision | Open with "factual amendment; the decision does not change", credit the 2026-10-22 operator ruling and #6609, and change no decision text. |
| Changelog clippings/spelling gates red on the entry | Follow the `[Unreleased]` format (bold impact-first lead, `(#6604)`, before/after, under 1,200 characters) and run the changelog tests. |
| The guard goes red on a legitimate Lamport mention elsewhere | Bounded corpus, affirmative-only regex with negation allowance, non-vacuity test. |
| Docs index / ADR inventory stale after the ADR edit | Run `docs_index --write`, `freshen_adr_inventory`, `check_docs_freshness --ci`. |
| Diagram text and alt-text drift | One pass per diagram touching prose, alt-text and node label together; `test_diagram_drift_guard` and the docs structural lint re-run. |
