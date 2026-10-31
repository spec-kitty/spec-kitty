# WP01 review — cycle 2 (APPROVE) — reviewer-renata

Cycle-1 finding (stdout/json-channel) is fixed and pinned:

- `print(stale_base_warning, file=sys.stderr)` in the FRESH_COORD arm, with a comment naming
  `_json_safe_output` and why stdout must stay machine-readable.
- `test_stale_coord_base_is_reported` now asserts `captured.out == ""` AND reads the report from
  `captured.err` — the stale scenario proves both the emission and the clean stdout.
- The three silence controls now assert `"WARNING" not in captured.out + captured.err`; moving the
  channel had made them unable to observe the thing they assert is absent (vacuous), and that is
  repaired rather than left as-is.

Re-verified after the fix: 6/6 in
`tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py`; ruff + `ruff format --check
--force-exclude` clean. No change to the probe, the message text, the parentage or the refusal
routes. Approved.
