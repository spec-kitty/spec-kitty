# Decision Moment `01M81KT9DA4XS2E156YB0QBBJZ`

- **Mission:** `single-branch-planning-pin-rebase-01M81KRS`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.rulings`
- **Input key:** `scope_rulings`
- **Status:** `resolved`
- **Created:** `2026-11-22T12:31:08.714715+00:00`
- **Resolved:** `2026-11-22T12:31:16.415634+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What scope and behaviour should the single_branch planning pin follow across a rebase (#7793, #7297 items 1-6)?

## Options

_(none)_

## Final answer

Operator rulings ('Bigger: items 1-6', relayed by the dispatcher, verified in the research squad transcript, ledger R68): (1) a re-pin follows the recorded planning commit by patch-id (reuse consolidation/git_probes.patch_id_of and lanes/planning_base.resolve_finalize_planning_base); (2) it refuses with a named code when there is no match, and never lands on a tip that empties the evidence window; (3) a derived pin is frozen against a later plain finalize; (4) derivation walks the mission branch; (5) #7297 items 3-6 are in scope (message mismatches, too-early pin, too-late pin after a rename, doctor gaps), each grounded before planning; (6) amend ADR 2026-10-04-5. Runner recommendation pending dispatcher confirmation: the single_branch pin's branch line is meta.mission_branch for capture, refresh/repin and derivation alike.

## Rationale

_(none)_

## Change log

- `2026-11-22T12:31:08.714715+00:00` - opened
- `2026-11-22T12:31:16.415634+00:00` - resolved (final_answer="Operator rulings ('Bigger: items 1-6', relayed by the dispatcher, verified in the research squad transcript, ledger R68): (1) a re-pin follows the recorded planning commit by patch-id (reuse consolidation/git_probes.patch_id_of and lanes/planning_base.resolve_finalize_planning_base); (2) it refuses with a named code when there is no match, and never lands on a tip that empties the evidence window; (3) a derived pin is frozen against a later plain finalize; (4) derivation walks the mission branch; (5) #7297 items 3-6 are in scope (message mismatches, too-early pin, too-late pin after a rename, doctor gaps), each grounded before planning; (6) amend ADR 2026-10-04-5. Runner recommendation pending dispatcher confirmation: the single_branch pin's branch line is meta.mission_branch for capture, refresh/repin and derivation alike.")
