# Implementation Plan: mark-status owner authority

**Branch**: `issue-6463-mark-status-owner-authority` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/mark-status-owner-authority-01M68JA8/spec.md` (issue #6463)

## Summary

`agent tasks mark-status` decides which work package a subtask id belongs to, then
writes a completion event to it. Today that decision is made twice: once during
resolution (which now refuses a shared id, #5953) and again during the write, by
first match. Three reproduced cases show a silent wrong-WP write or a bogus
subtask event on `main@35318ef51c`:

1. an id claimed by an authored roster in one WP and by a structured `tasks.md`
   row in a legacy WP resolves as *unique* (roster-or-history, not the union);
2. a bare `WP<digits>` id skips the ownership check entirely and is claimed by the
   pipe-table/inline resolvers before the lane-transition rejection runs;
3. the emit falls back to `_resolve_history_wp_id` / `owning_wp_from_authored_roster`
   when the resolution phase recorded no owner, so document order picks the target.

The fix: one ownership authority (roster ∩ union structured `tasks.md` claims),
`WP`-shaped ids scoped like any other subtask id and otherwise rejected before
legacy row shapes, and an emit that attributes only from the resolved owner map —
refusing loudly, before any event, when it cannot.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: typer, pytest, `specify_cli` (this repo), no new dependency
**Storage**: mission status event log (`status.events.jsonl`) + WP frontmatter; no schema change
**Testing**: pytest CLI-level tests through the pre-existing `agent tasks mark-status` Typer command (`typer.testing.CliRunner`), targeted suites only
**Target Platform**: CLI (Linux/macOS/Windows), cross-platform paths only
**Project Type**: single project (CLI)
**Performance Goals**: no measurable cost change; the owner map is already built once per invocation
**Constraints**: no `--wp` contract change, no change to the shipped `software-dev` task shape's behaviour, every refusal before any write, no new ownership derivation
**Scale/Scope**: 3 source files (`tasks_mark_status.py`, `tasks_outline.py` untouched unless needed, tests under `tests/specify_cli/cli/commands/agent/`)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | The authored-roster owner map (`core/subtask_rows.authored_roster_owner_map`) stays the one authority; `tasks.md` contributes structured claims only, never a second lookup on the write path (C-002). |
| ATDD-first (C-011) | Every FR lands with a test that is red on `main@35318ef51c` through the pre-existing CLI entry point (FR-001/002/003) or the emit seam (FR-004/005). |
| Smallest viable diff (tactic) | Edits stay inside `tasks_mark_status.py` plus its test module; no resolver is rewritten. |
| Locality of change (DIRECTIVE_024) | No change to `move-task`, `accept`, the `--json` envelope, or the `--wp` flag surface. |
| Red-main discipline | Pre-existing reds are cited, never skipped or weakened (see `## Deferred`). |
| Test policy | Only the `mark-status`/tasks-agent suites run; no full heavy tree (`NO_FULL_HEAVY_SUITES_IN_MISSION`). |

No violations; no justification required.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mark-status-owner-authority-01M68JA8/
├── plan.md              # This file
├── research.md          # Phase 0 (discovery + plan evidence)
├── research/evidence/   # reproduced transcripts
├── data-model.md        # Phase 1 (owner map / scoped mark / completion event)
├── quickstart.md        # Phase 1 (how to verify by hand)
├── tasks.md             # Phase 2
└── traces/              # mission tracer files
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── tasks_mark_status.py     # ownership decision + emit attribution (the change)
├── tasks_outline.py         # bare-WP-id rejection + history resolution (consulted, unchanged)
├── tasks_materialization.py # legacy row resolvers (unchanged; order is the fix)
└── tasks.py                 # Typer surface + compat re-exports (unchanged)

src/specify_cli/core/subtask_rows.py   # authored roster owner map (unchanged)

tests/specify_cli/cli/commands/agent/
├── test_tasks_mark_status.py            # existing #5953 regression + new collision pins
├── test_mark_status_authored_roster.py  # roster resolver tests (extended if needed)
└── test_mark_status_owner_authority.py  # new: the three collision cases + emit invariant
```

**Structure Decision**: single project; the change is localized to the mark-status
command family and its tests.

## Implementation Concern Map

| IC | Concern | Files | FRs |
| --- | --- | --- | --- |
| IC-01 | **Ownership decision is a union, refuse ambiguity.** `_owners_for_task` returns the deduped union of authored-roster owners and structured `tasks.md` owners; `_resolve_task_owners` refuses an id claimed by more than one WP when `--wp` is absent and refuses a `--wp` that owns none of the requested ids. | `tasks_mark_status.py` | FR-001 |
| IC-02 | **`WP`-shaped ids are scoped, not exempt.** Drop the blanket `WP\d+` skip: when a WP authors the id as a subtask, the same ambiguity/`--wp` rules apply (message names both readings); when no WP authors it, run the existing lane-transition rejection *before* the legacy row resolvers so a WP index row cannot claim it. | `tasks_mark_status.py` (`_resolve_task_owners`, resolution chain) | FR-002, FR-003 |
| IC-03 | **The emit has one authority.** `_ms_emit_subtask_state` attributes only from `st.task_wps`; it collects every unattributable updated id and raises before the first event, so a partial batch never lands. | `tasks_mark_status.py` (`_ms_emit_subtask_state`) | FR-004, FR-005 |

Ordering: IC-01 → IC-02 → IC-03. IC-01/IC-02 populate the owner map the emit
consumes; IC-03 removes the fallback that would otherwise mask a missed owner.

## Design decisions

- **D-1 Union, not precedence.** `roster or history` → `roster | history` (sorted,
  deduped). Rationale: #5953's "authored roster decides" rule exists to keep
  *prose* mentions out; `history_wp_ids` already admits only structured rows, so
  unioning cannot reintroduce the prose false positive, while it does stop a
  legacy WP's structured claim from being hidden. Rejected alternative: make the
  roster strictly authoritative and refuse when *any* other WP mentions the id in
  `tasks.md` — broader blast radius (would refuse cross-references that resolve
  fine today), and the union already closes the silent case.
- **D-2 `WP`-shaped ids.** Keep `_resolve_wp_id`'s message (it is the documented
  behaviour) but gate it on "no WP authors this id as a subtask". When one does,
  unscoped input is ambiguous between "the lane" and "the subtask" and is refused
  with both readings; `--wp <owner>` selects the subtask.
- **D-3 Emit refusal, not heuristic.** With IC-01/IC-02 in place an updated id
  without an owner means the resolution and the write disagree. Refusing is the
  only honest outcome; the alternative (today) writes to a WP nobody selected.
- **D-4 No new message strings for existing paths.** The #5953 messages
  (`pass --wp to select one`, `<id> is not a subtask of <WP> (owners: …)`) are kept
  verbatim; the new strings only cover the `WP`-shaped ambiguity.

## Testing strategy (red-first)

Each new test is written and run against `main@35318ef51c` (this branch's base)
before the fix and must fail for the documented reason:

| Test | Fixture | Red today because |
| --- | --- | --- |
| mixed-source ambiguity refused | WP01 roster `[T001]`; legacy WP02 (`tasks.md` `## WP02` + `Subtasks: T001`) | writes `{'T001': 'done'}` on WP01, exit 0 |
| scoped marks stay scoped | same fixture, `--wp WP01` / `--wp WP02` | WP02 scoped mark is refused ("not a subtask of WP02 (owners: WP01)") |
| WP index row cannot claim a WP id | `tasks.md` WP index table, no roster authors `WP02` | `{'WP02': 'done'}` recorded on WP02, exit 0 |
| `WP`-shaped subtask is only marked when scoped | WP01 roster authors `WP02` | unscoped writes, `--wp WP01` resolves through the fallback |
| emit refuses an unattributable id | state with an updated id absent from `task_wps` | fallback attributes by first match |

Compatibility pins (must stay green, unchanged): the #5953 regression
(`test_repeated_subtask_requires_wp_and_scoped_mark_is_idempotent`), the skip
alias round-trip, and the inline/checkbox/pipe-table resolution tests.

Targeted verification commands:

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py \
              tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py \
              tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py -q
uv run mypy --strict src/specify_cli/cli/commands/agent/tasks_mark_status.py
```

## Risks

- **R-1** A caller relying on the old lenient behaviour for a `WP`-shaped subtask id
  (unscoped) now gets a refusal. Accepted: the old behaviour wrote a WP id as a
  subtask with no way to know the target; the message names `--wp`.
- **R-2** A mixed-source mission gains a refusal for an unscoped mark that used to
  "succeed" on the wrong WP. This is the intended fix (NFR-001 covers the shipped
  single-authority shape, which is unchanged).
- **R-3** Emit refusal could surface on a path where the owner map is unreadable —
  already fail-closed before resolution, so the new refusal cannot mask it.
