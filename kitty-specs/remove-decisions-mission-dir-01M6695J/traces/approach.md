# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · Approach: single-WP dead-code removal. Delete decisions/service.py::_mission_dir (no src caller since #6762), drop its two read-seam leniency pins, re-point stale docstrings, and add a red-first AST guard test asserting service.py holds no read-side placement_seam read_dir(STATUS_STATE) call. emit.py's live _mission_dir is explicitly out of scope.

2026-10-30 · claude · Dev-assist test cleanup verdict (wrap-up step): the mission's single new test file tests/specify_cli/decisions/test_service_status_state_access.py is KEEP — it pins a standing architectural invariant (no read-side read_dir(STATUS_STATE) in the decisions service), is named after the contract (not the issue), carries no WP##/NFR-### labels, and includes a write_dir positive control so it cannot pass vacuously. No development-assist tests to retire; no issue-named (test_issue_NNNN*) files were added.
