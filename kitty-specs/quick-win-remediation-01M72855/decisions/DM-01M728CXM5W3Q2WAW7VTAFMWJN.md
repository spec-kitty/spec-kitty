# Decision Moment `01M728CXM5W3Q2WAW7VTAFMWJN`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `plan`
- **Slot key:** `plan.tests.red-first`
- **Input key:** `red_first`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:15:08.933255+00:00`
- **Resolved:** `2026-11-10T08:15:10.280754+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where do the red-first tests live and how is the Windows newline proven on Linux?

## Options

- New unit/fast tests/status/test_store_line_framing.py for #7439/#7441 (newline asserted via an os.fdopen spy plus a no-CRLF byte pin); existing files for the rest
- Extend test_store.py only
- Other

## Final answer

New tests/status/test_store_line_framing.py (unit, fast; no git fixture) for #7439 and #7441, asserting the temp-file newline argument through an os.fdopen spy plus a portable no-CRLF byte pin and a parity pin against spec_kitty_events serialize_record. #7440 in tests/specify_cli/events/test_sanitizer.py; #7443 in tests/status/test_dependency_guard.py, tests/specify_cli/core/test_subtask_rows_snapshot.py and tests/specify_cli/status/test_reconstruct_wp_view.py; #7442 in test_subtask_rows_snapshot.py, test_reconstruct_wp_view.py and the mark-status tests; #7445 in tests/specify_cli/test_mission_metadata.py; #7463 in tests/agent/cli/commands/test_glossary.py. Each test commit precedes its fix commit.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:15:08.933255+00:00` - opened
- `2026-11-10T08:15:10.280754+00:00` - resolved (final_answer="New tests/status/test_store_line_framing.py (unit, fast; no git fixture) for #7439 and #7441, asserting the temp-file newline argument through an os.fdopen spy plus a portable no-CRLF byte pin and a parity pin against spec_kitty_events serialize_record. #7440 in tests/specify_cli/events/test_sanitizer.py; #7443 in tests/status/test_dependency_guard.py, tests/specify_cli/core/test_subtask_rows_snapshot.py and tests/specify_cli/status/test_reconstruct_wp_view.py; #7442 in test_subtask_rows_snapshot.py, test_reconstruct_wp_view.py and the mark-status tests; #7445 in tests/specify_cli/test_mission_metadata.py; #7463 in tests/agent/cli/commands/test_glossary.py. Each test commit precedes its fix commit.")
