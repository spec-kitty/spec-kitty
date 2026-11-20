---
affected_files: []
cycle_number: 2
mission_slug: skill-surfaces-converge-01M7VRS0
reproduction_command:
reviewed_at: '2026-11-20T11:53:59Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review feedback: changes requested (aggregate finding A1)

Reviewer: claude::reviewer-renata (independent). Found in the aggregate integration run, after WP05 was approved at
98afbf9bf0.

## Blocking

### A1. The frozen `doctor skills --json` contract baseline was not updated

WP05 added two top-level keys to `doctor skills --json`: `outdated` (#5281) and `old_root_leftovers` (#7723). The
frozen schema baseline `tests/specify_cli/tool_surface/integration/fixtures/doctor_skills_baseline.json`, which
`src/specify_cli/tool_surface/contracts/migration-compatibility.md` governs, was neither regenerated nor documented.
These fail on lane-e itself and on the merged tree:

- `tests/specify_cli/tool_surface/integration/test_migration_compat.py::test_doctor_skills_json_schema_matches_baseline`
- `tests/specify_cli/tool_surface/integration/test_doctor_tool_surfaces_cli.py::test_migration_compat_still_passes`

Fix: regenerate the baseline (additive: both keys as empty lists) and add both fields to the frozen-field table in
migration-compatibility.md, marked additive and not changing `ok`. Run
`tests/specify_cli/tool_surface/integration` with the lane's own sources: these tests run `python -m specify_cli` in
a subprocess, so use the lane worktree's own venv or `PYTHONPATH=<lane>/src`.

Earlier WP05 evidence stands. Only this contract file and its document change.
