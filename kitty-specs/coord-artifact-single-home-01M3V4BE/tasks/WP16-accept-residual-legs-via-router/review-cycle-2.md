---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T14:41:28Z'
reviewer_agent: cursor
wp_id: WP16
---

Cycle 2 review of WP16 (lane-n, HEAD f8cc9b812a) requested changes.

Blocking:
- target_branch must not retarget every PRIMARY group. Accept's unprotected HEAD is the only caller that should select the primary commit ref. spec-commit --target-branch and write-seam callers keep the previous meaning. Pin that with a test.
- Add a test whose refused/error surface diagnostic is a HEAD-mismatch checkout instruction, and assert that instruction appears in the residual failure text.
- Add a text-mode failure test that _report_error receives a message containing [/red] and does not raise MarkupError.
- write_seam.py still names accept.py::_commit_primary_residuals_on_head and a direct safe_commit path. That function is not in the tree. Name commit_for_mission with the accept-only primary ref.
