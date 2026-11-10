# Decision Moment `01M7286ZAMNZ9S1E0CA4MZNG27`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.roster.map-form`
- **Input key:** `roster_map_form`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:54.068712+00:00`
- **Resolved:** `2026-11-10T08:11:55.386899+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7442: what happens to a subtasks: entry that is not a task id (a map, list, float, date, boolean or null)?

## Options

- Refuse with SubtaskRosterResolutionError naming the WP file and the expected list form; repair Mission 058 once in the same PR
- Read the id key from maps
- Other

## Final answer

Refuse: the roster accepts only string or integer (not boolean) entries; anything else, and an integer too long to convert (more than 4300 digits), raises SubtaskRosterResolutionError naming the WP file and the expected list form (e.g. '- T001'). The WP view catches it and shows an empty authored subtask list. The spec states that mark-status then refuses for the whole Mission until the file is fixed. Mission 058's 28 map entries in its six WP files are repaired once in the same PR via a dated _OPERATOR_SANCTIONED_CORRECTIONS entry in tests/architectural/test_archive_root_byte_identical.py; removing that entry after merge is a follow-up named in the PR body. Operator decision 2026-11-10.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:54.068712+00:00` - opened
- `2026-11-10T08:11:55.386899+00:00` - resolved (final_answer="Refuse: the roster accepts only string or integer (not boolean) entries; anything else, and an integer too long to convert (more than 4300 digits), raises SubtaskRosterResolutionError naming the WP file and the expected list form (e.g. '- T001'). The WP view catches it and shows an empty authored subtask list. The spec states that mark-status then refuses for the whole Mission until the file is fixed. Mission 058's 28 map entries in its six WP files are repaired once in the same PR via a dated _OPERATOR_SANCTIONED_CORRECTIONS entry in tests/architectural/test_archive_root_byte_identical.py; removing that entry after merge is a follow-up named in the PR body. Operator decision 2026-11-10.")
