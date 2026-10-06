---
affected_files: []
cycle_number: 1
mission_slug: skill-surface-upgrade-integrity-01M482Z3
reproduction_command:
reviewed_at: '2026-10-06T08:49:46Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review: changes requested

Core coalesce work (operations.py, managed_skills delegation, red-first 4275 test, negative tests with the owner/field message) is sound. One blocking gap and one soundness tightening:

1. Out-of-ownership edit to `src/specify_cli/tool_surface/providers/agent_profiles.py` has NO focused unit tests (only the slow 4275 integration test reaches it). Charter/Sonar: every new branch needs tests in the same PR. Add tests in `tests/specify_cli/tool_surface/providers/test_agent_profiles.py` covering: (a) recheck accepts an absent->directory destination that a sibling created with the planned mode; (b) recheck still refuses when the observed directory mode differs from the planned mode; (c) recheck still refuses a destination that is not a planned directory create (e.g. a file appeared); (d) `_write_profile_effect` skips an already-present identical directory; (e) `_write_profile_effect` still raises `FileExistsError` when a file / different-mode directory appears.
2. `_write_profile_effect`'s early return is broader than the recheck: it skips ANY `create`->directory effect whose destination exists as a directory of the same mode, without requiring `effect.before.kind == "absent"`. Add that condition so the write-time guard matches the recheck's "planned absent->directory create, same mode" shape, and test it (item 1e).
3. Minor: the recheck line `observed = state if ... else observed` and the long `planned_dirs` comprehension are dense; extract a small named helper (e.g. `_sibling_created_planned_dir(path, state, observed, planned_dirs)`) so the branch is unit-testable directly.
