# Decision Moment `01M3GSY0ZHFVXK540NN721Y628`

- **Mission:** `consolidate-canonical-terminology-01M3GSSV`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.lanes-merge-filename`
- **Input key:** `lanes_merge_filename`
- **Status:** `resolved`
- **Created:** `2026-09-27T06:48:09.969929+00:00`
- **Resolved:** `2026-09-27T06:51:55.776597+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Rename the lanes/merge.py file (and MergeState-style module names) physically, or rename only the lane-consolidation-sense symbols in place and keep filenames?

## Options

- symbols-in-place-keep-filenames
- physically-rename-files
- Other

## Final answer

Physically rename files (lanes/merge.py, merge/state.py module names) to consolidation, updating all importers + tests; re-export shims only where an external consumer requires one.

## Rationale

_(none)_

## Change log

- `2026-09-27T06:48:09.969929+00:00` — opened
- `2026-09-27T06:51:55.776597+00:00` — resolved (final_answer="Physically rename files (lanes/merge.py, merge/state.py module names) to consolidation, updating all importers + tests; re-export shims only where an external consumer requires one.")
