# Decision Moment `01M728CRFH19TBCFK799KSKQTR`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `plan`
- **Slot key:** `plan.locator.home`
- **Input key:** `locator_home`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:15:03.665988+00:00`
- **Resolved:** `2026-11-10T08:15:04.989137+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does the shared WP task-file locator live?

## Options

- New core module src/specify_cli/core/wp_task_files.py imported at module scope by subtask_rows, status/emit and status/wp_view
- Inside core/subtask_rows.py
- Other

## Final answer

A new core-layer module src/specify_cli/core/wp_task_files.py (stdlib + kernel._safe_re only) exposing one public matcher returning every name match, plus the separator pattern. core/subtask_rows.py, status/emit.py (_match_wp_files becomes a thin delegate or is replaced at its two call sites) and status/wp_view.py import it; the duplicate _WP_FILE_SEP in wp_view.py is removed. Keeps core free of status imports (C-007) and keeps emit's lazy subtask_rows import untouched.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:15:03.665988+00:00` - opened
- `2026-11-10T08:15:04.989137+00:00` - resolved (final_answer="A new core-layer module src/specify_cli/core/wp_task_files.py (stdlib + kernel._safe_re only) exposing one public matcher returning every name match, plus the separator pattern. core/subtask_rows.py, status/emit.py (_match_wp_files becomes a thin delegate or is replaced at its two call sites) and status/wp_view.py import it; the duplicate _WP_FILE_SEP in wp_view.py is removed. Keeps core free of status imports (C-007) and keeps emit's lazy subtask_rows import untouched.")
