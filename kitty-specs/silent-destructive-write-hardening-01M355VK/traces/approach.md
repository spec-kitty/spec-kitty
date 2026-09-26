# Approach — Silent Destructive-Write Hardening

Three disjoint-seam bug fixes under one acceptance bar (no silent data loss).

- WP01 (#4908): read recorded mission type from the SSOT in the recompile fallback
  (`generate.py:249`), threaded from `activate.py` + `pack.py`. Preserve the #2940
  malformed-answers guard (do not flip `from_interview=True`).
- WP02 (#4897): introduce ONE authoritative-non-lane-event-type registry; make both
  `status/store.py:is_non_lane_event` and `mission_state._is_preserved_non_lane_row`
  consult it. Repair must not report errors=0 while quarantining canonical rows.
- WP03 (#4894): section/block-level union in `union_trace_texts`; preserve repeated
  lines within distinct sections; consider 3-way base-awareness like sibling drivers.

Red-first per defect; single_branch topology (mission fixes the traces driver).
