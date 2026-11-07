# Decision Moment `01M6QY3XQJ5NAYVF3GMZ7ZPPRE`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `specify`
- **Slot key:** `specify.escalation.ruling3-restated`
- **Input key:** `ruling3_implementation`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:03:04.050172+00:00`
- **Resolved:** `2026-11-06T08:03:06.399714+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Escalation: physically deleting status files from lane branches would be carried onto the coordination/Mission branch by consolidation, trips auto-rebase and conflicts with ADR 2026-07-29-1 Assert A'. How is ruling 3 implemented?

## Options

_(none)_

## Final answer

Restate it: lane checkouts never show the status files (sparse exclusion at every lane-checkout creation site, lanes topology included), lanes never change them (a write-check refuses), readers never read them (S1). A migration applies the exclusion to existing lane worktrees and reports, never drops, lane-only events. The fork-time blob stays in lane history.

## Rationale

Operator ruling, stijn-dejongh, 2026-11-06 (epic #7276). Quoted as given.

## Change log

- `2026-11-06T08:03:04.050172+00:00` - opened
- `2026-11-06T08:03:06.399714+00:00` - resolved (final_answer="Restate it: lane checkouts never show the status files (sparse exclusion at every lane-checkout creation site, lanes topology included), lanes never change them (a write-check refuses), readers never read them (S1). A migration applies the exclusion to existing lane worktrees and reports, never drops, lane-only events. The fork-time blob stays in lane history.")
