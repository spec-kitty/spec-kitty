---
work_package_id: WP02
title: Correct the living pages, agent guidelines and preflight docstring
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- FR-006
- SC-001
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Living surfaces
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/architecture/diagrams/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- AGENTS.md
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/event-ledger-writers-and-readers.md
- docs/plans/domains/api-dashboard-domain-plan.md
- src/specify_cli/consolidation/preflight.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6604'
---

# Work Package Prompt: WP02 – Correct the living pages, agent guidelines and preflight docstring

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: your harness

## Objective

Replace every surviving **affirmative** claim that the CLI status path is Lamport-ordered in
the living surfaces #6604 names, and record the gap-table closure — so WP01's guard goes
green for everything except its ADR assertion. Do not touch the ADR (WP03 does that) and do
not touch `tests/` (WP01 owns it).

## Context & Constraints

Read first: [spec.md](../spec.md) FR-001/FR-002/FR-004/FR-005/FR-006, C-003;
[plan.md](../plan.md) "Exact change set (wording, per site)"; [research.md](../research.md)
"What the code does now".

The corrected fact, stated once (use this wording consistently; `CLAUDE.md` is a **symlink**
to `AGENTS.md`, so edit `AGENTS.md` only):

> The status path is ordered by wall clock `(at, event_id)`. `status.reducer.reduce` and
> `materialize_snapshot` both reach `spec_kitty_events.diary.reduce_parsed`; CLI lane rows
> carry no Lamport clock and `spec_kitty_events.status.reduce_status_events` is not on the
> CLI path. Since `spec-kitty-events` 10.5.1 a non-seed departure from `approved` sorts
> after the approval it followed (the #4941 fix, PR #6261). What remains is narrower: a
> **non-approval** transition minted on a clock behind the event it follows still sorts
> before that event. ADR `2026-02-09-3` Amendment 2026-10-22 records the ordering; ADR
> `2026-10-14-1` Amendment 2026-10-22 withdraws the "Lamport wrapper" claim;
> Lamport-primary ordering is a post-GA direction (#6609).

Constraints:

- **Locality of change (DIRECTIVE_024):** change the sentences that carry the claim. Do
  not restructure a page, renumber a section, or "improve" neighbouring prose.
- **No new ordering decision** (C-001): never write that the CLI "should" be
  Lamport-ordered, and never propose a clock on CLI rows here.
- **Do not touch** `docs/adr/**`, `docs/changelog/**`, `tests/**`, `docs/archive/**`,
  `docs/reports/**`, `research/**`, `kitty-specs/**`.
- Keep the narrower residual visible everywhere the old blanket claim was: deleting the
  caveat is not a fix.

## Branch Strategy

Planning artifacts were generated on `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`.
Execution worktrees are allocated per computed lane from `lanes.json`; completed changes
merge back into `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`.

## Subtasks

### T004 — `docs/architecture/diagrams/01_context/README.md`

- Prose (~`:105`): "owns the event ledger and the Lamport reducer" → the event ledger and
  the wall-clock status reducer (`(at, event_id)` with the approved-departure lift), one
  clause, no paragraph growth.
- Mermaid node (~`:139`): `owns event ledger + Lamport reducer` → `owns event ledger +
  wall-clock status reducer`. Keep the node's `<i>open-core · producer · exists</i>` marker.
- Check the surrounding alt-text for the same claim (grep the file for `Lamport`).

### T005 — `docs/architecture/diagrams/02_containers/README.md`

Three places must agree: the prose paragraph (`:251`), the alt-text (`:266`) and the mermaid
node label (`:285`, `<b>Lamport reducer</b><br/>status.reducer.materialize`).

- Node label: `<b>Status reducer</b><br/>status.reducer.materialize_snapshot<br/>wall clock
  (at, event_id)` — the diagram's point is that the ledger is folded by one reducer, not
  which library.
- Keep the edge labels (`folded by`, `snapshots`) unchanged; they are still true.
- Grep the page for `Lamport` afterwards: only a negation (if any) may remain.

### T006 — `docs/plans/domains/api-dashboard-domain-plan.md`

§4 "Known gaps" item 2 currently ends: "The orchestrator-api reads use the wall-clock
reducer, `reduce()`. The dashboard uses the Lamport reducer, `materialize_snapshot()`. So two
read surfaces can disagree today."

Replace with the fact that both surfaces reach the same wall-clock fold, that the dashboard
is deleted (so there is no second surface), that the real gap is the missing versioned
contract, and note the surviving ordering residual plus the #6609 direction. Keep the
item's title ("The mission-data contract is unenumerated") and its tracking sentence.

### T007 — `AGENTS.md` "Status Model Patterns"

Rewrite the blockquote paragraph and the `reduce()` table row:

- Say one reducer, two parsers, wall clock `(at, event_id)`, no Lamport clock on CLI rows,
  `reduce_status_events` off the CLI path.
- Credit the shipped lift: `spec-kitty-events` 10.5.1 / PR #6261 fixes the clock-ahead
  `approved -> in_progress` case (#4941); from-lane continuity is #4990 (closed).
- Credits the corrected docstrings: `consolidation/reconciliation.py:26-34` and
  `:1464-1471` no longer call it the Lamport wrapper — remove the "they are wrong; #6213
  tracks correcting them" sentence entirely.
- Keep the gate caveat: `build_approved_wp_set` has no separate protection; it reads through
  `materialize_snapshot`.
- Keep the residual, narrowed: a **non-approval** transition minted on a clock behind the
  event it follows still sorts before it.
- Cite ADR `2026-02-09-3` **Amendment 2026-10-22** (not the unamended decision) and #6609
  for the post-GA direction. The table row loses "Not Lamport-ordered and not the ADR
  `2026-02-09-3` model; see `#4941`".
- Do not edit `CLAUDE.md`: it is a symlink; `git status` must show only `AGENTS.md`.

### T008 — `src/specify_cli/consolidation/preflight.py`

`_latest_actor_for_transition`'s docstring says: "ADR `2026-02-09-3` (event-log merge
semantics) orders events causally (Lamport-primary) and rejects last-writer-wins by
timestamp…". Correct it to cite the amended record (Amendment 2026-10-22: wall clock, from
the writer's `at`, tie-broken by `event_id`), while keeping the real reason the function
reads append order: a lane `StatusEvent` carries no clock to sort on, and the append-only
log's own order is the causal order available here — the same order
`review_roles.latest_implementer_event` reads. Docstring only: no code change, no rename, no
signature change.

### T009 — `docs/architecture/event-ledger-writers-and-readers.md`

- The G-3 row becomes **Closed (#6604)**: name the files corrected (the two C4 pages, the
  domain plan, `AGENTS.md`, `preflight.py`, the ADR amendment), the guard test that keeps
  them honest, and the surviving residual (non-approval clock skew). The `Tracker` cell
  stops saying "file new (#6213 closed after step 1 only)".
- Update the "Ordering: wall clock for 4.0.0." bullet so its G-3 pointer reads as closed
  while keeping the #6609 direction.
- Keep G-1/G-2/G-4.. unchanged; their evidence lines are not this mission's.

## Test strategy

- `uv run pytest tests/architectural/test_status_path_ordering_claims.py -q` (WP01's guard):
  only the ADR assertions may still fail.
- `uv run pytest tests/docs/test_architecture_docs_consistency.py tests/docs/test_diagram_drift_guard.py -q`.
- `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` (docs prose touched).
- `uv run python -m scripts.docs.check_docs_freshness --ci` after the edits.
- Do **not** run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- [ ] No affirmative `Lamport (reducer|reduction|wrapper)` claim about the status path
      remains in the six owned files; negations that teach the fact are fine.
- [ ] The residual (non-approval clock skew) is stated in `AGENTS.md` and in the closed G-3
      row.
- [ ] The container page's prose, alt-text and node label agree; the context page's prose
      and node label agree.
- [ ] `AGENTS.md` edited, `CLAUDE.md` untouched (symlink).
- [ ] `preflight.py` change is docstring-only (`git diff --stat` shows no code hunk outside
      the docstring).
- [ ] WP01's guard fails only on its ADR assertions.
- [ ] No file outside `owned_files` is modified.

## Risks

- Turning "two read surfaces can disagree" into a false claim in the other direction: with
  the dashboard deleted and one fold, they cannot disagree *about ordering*; the real gap is
  the unenumerated contract. Keep that distinction.
- Losing the residual while removing the blanket claim — the guard checks for it.
- Regenerating `docs/` index pages as a side effect: don't; the freshness check only reads.

## Reviewer guidance

Read the diff against the code facts above, not against the old prose. Reject any edit that
(a) removes the residual, (b) claims the CLI *is* Lamport-ordered, (c) restructures a page,
or (d) touches the ADR/changelog/tests. Verify the diagram node, its alt-text and the prose
now tell the same story.
