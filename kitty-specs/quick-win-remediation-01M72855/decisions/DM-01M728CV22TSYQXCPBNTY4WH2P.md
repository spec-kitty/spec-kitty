# Decision Moment `01M728CV22TSYQXCPBNTY4WH2P`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `plan`
- **Slot key:** `plan.roster.view-contract`
- **Input key:** `roster_view`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:15:06.306863+00:00`
- **Resolved:** `2026-11-10T08:15:07.626680+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How do the gate and the WP view share one roster-entry rule while keeping their different failure contracts?

## Options

- normalize_authored_subtask_roster raises a SubtaskRosterResolutionError subclass; authored_subtask_roster adds the WP file name; _authored_group catches it and yields an empty tuple
- Validate only in authored_subtask_roster
- Other

## Final answer

One rule in normalize_authored_subtask_roster: accept str and int (not bool), convert inside the guard so an over-limit int also refuses; raise a typed SubtaskRosterResolutionError subclass naming the entry position and the expected list form. authored_subtask_roster calls it inside its existing try and re-raises with the WP file name; status/wp_view._authored_group catches the typed error and yields an empty subtasks tuple. owning_wp_from_authored_roster already catches SubtaskRosterResolutionError and stays advisory.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:15:06.306863+00:00` - opened
- `2026-11-10T08:15:07.626680+00:00` - resolved (final_answer="One rule in normalize_authored_subtask_roster: accept str and int (not bool), convert inside the guard so an over-limit int also refuses; raise a typed SubtaskRosterResolutionError subclass naming the entry position and the expected list form. authored_subtask_roster calls it inside its existing try and re-raises with the WP file name; status/wp_view._authored_group catches the typed error and yields an empty subtasks tuple. owning_wp_from_authored_roster already catches SubtaskRosterResolutionError and stays advisory.")
