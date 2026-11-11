---
affected_files: []
cycle_number: 3
mission_slug: runtime-status-read-door-01M73HHB
reproduction_command:
reviewed_at: '2026-11-11T09:45:43Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP06
---

# WP06 cycle 3 (acceptance verification)

The acceptance verifier found a test made red by this Mission (NFR-003):
`tests/specify_cli/next/test_runtime_bridge_composition.py::test_decision_shape_unchanged_for_composed_action` pins the `Decision` field set. WP06 added `Decision.remediation` (additive, default None), and the pin was not updated. The test passes on the base.

Fix: add `remediation` to `expected_fields`, with a comment in the style of the `guard_failure_paths` / `error_code` entries. List the re-pin in the PR. Re-run that file plus the WP06 strategy files.
