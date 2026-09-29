# Decision Moment `01M3PJWGGKTRT9W03MJHFV44Q2`

- **Mission:** `consolidation-claim-rollback-integrity-01M3PD1T`
- **Origin flow:** `plan`
- **Slot key:** `plan.planning-lane.self-heal-v2`
- **Input key:** `planning_self_heal_fix_v2`
- **Status:** `resolved`
- **Created:** `2026-09-29T12:40:26.899857+00:00`
- **Resolved:** `2026-09-29T12:40:29.921987+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Refusing the planning claim deadlocks (consolidate requires all WPs approved; no per-lane consolidate). What should a planning-lane claim do when its self-heal would merge code lanes onto the target checkout?

## Options

- Skip merge, waive ancestry
- Refuse at finalize-tasks
- Cut FR-008 to follow-up
- Other

## Final answer

Skip merge, waive ancestry: when the planning lane worktree is the repository root checkout on the target branch, the dependency self-heal does not merge code lanes and the claim-ancestry gate waives code-lane ancestry; claim proceeds, target untouched; code arrives via consolidation's attribution window. Supersedes DM 01M3PD41NQ6J6EX8V2HYDDRGPZ.

## Rationale

_(none)_

## Change log

- `2026-09-29T12:40:26.899857+00:00` — opened
- `2026-09-29T12:40:29.921987+00:00` — resolved (final_answer="Skip merge, waive ancestry: when the planning lane worktree is the repository root checkout on the target branch, the dependency self-heal does not merge code lanes and the claim-ancestry gate waives code-lane ancestry; claim proceeds, target untouched; code arrives via consolidation's attribution window. Supersedes DM 01M3PD41NQ6J6EX8V2HYDDRGPZ.")
