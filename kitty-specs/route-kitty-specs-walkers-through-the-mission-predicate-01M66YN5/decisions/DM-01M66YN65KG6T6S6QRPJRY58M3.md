# Decision Moment `01M66YN65KG6T6S6QRPJRY58M3`

- **Mission:** `route-kitty-specs-walkers-through-the-mission-predicate`
- **Origin flow:** `specify`
- **Step id:** `specify.problem_statement`
- **Input key:** `problem_statement`
- **Status:** `resolved`
- **Created:** `2026-10-30T17:45:24.403956+00:00`
- **Resolved:** `2026-10-30T17:46:46.265925+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What problem does this Mission solve?

## Options

_(none)_

## Final answer

Six kitty-specs/ walkers still decide 'is this a Mission?' for themselves instead of using the shared read-side predicate is_selectable_mission_dir: doctor topology (_collect_topology_rows), _coordination_doctor._resolve_mission_dirs, _review_cycle_reconcile_doctor._mission_dirs_for, materialize._mission_dirs_to_process, charter_activate._collect_inflight_missions and release.changelog.build_changelog_block. Residue folders (no meta.json, or an untracked id-less meta.json) are therefore listed, scanned or processed as Missions, and each walker's local rule can drift from the one authority (#6758, follow-up to #5875).

## Rationale

_(none)_

## Change log

- `2026-10-30T17:45:24.403956+00:00` — opened
- `2026-10-30T17:46:46.265925+00:00` — resolved (final_answer="Six kitty-specs/ walkers still decide 'is this a Mission?' for themselves instead of using the shared read-side predicate is_selectable_mission_dir: doctor topology (_collect_topology_rows), _coordination_doctor._resolve_mission_dirs, _review_cycle_reconcile_doctor._mission_dirs_for, materialize._mission_dirs_to_process, charter_activate._collect_inflight_missions and release.changelog.build_changelog_block. Residue folders (no meta.json, or an untracked id-less meta.json) are therefore listed, scanned or processed as Missions, and each walker's local rule can drift from the one authority (#6758, follow-up to #5875).")
