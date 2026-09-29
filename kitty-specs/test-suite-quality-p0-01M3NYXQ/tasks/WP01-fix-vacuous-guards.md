---
work_package_id: WP01
title: Fix vacuous guards (#5344)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
planning_base_branch: claude/p0-5353-test-suite-quality-g3tt8f
merge_target_branch: claude/p0-5353-test-suite-quality-g3tt8f
branch_strategy: Planning artifacts for this mission were generated on claude/p0-5353-test-suite-quality-g3tt8f. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/p0-5353-test-suite-quality-g3tt8f unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-quality-p0-01M3NYXQ
base_commit: 598abdfcb5fb123ffe354cf587f4617c9dde9fce
created_at: '2026-09-29T06:54:21.191386+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
history: []
agent_profile: implementer-ivan
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- tests/acceptance/test_post_consolidation.py
- tests/charter/test_context_bootstrap_markers.py
- tests/architectural/test_execution_context_parity.py
- tests/zeitgeist_client/test_drain_capability.py
- tests/specify_cli/live_work/test_drain_live_work.py
- tests/specify_cli/cli/commands/test_upgrade_command.py
tags: []
tracker_refs: []
---

# WP01: Fix vacuous guards (#5344)

See `tasks.md` for subtasks and `spec.md` for requirements.

For each subtask T001–T006 in tasks.md: make the test's oracle fail on the broken product. Protocol:
apply a planted break (scratch edit to production or guarded input), run the test and see it FAIL,
revert, see it PASS. Record each proof (command, red output line, green output line) in
research/red-proofs-wp01.md. If a baselined file is fixed, drop its PT entry in the same commit (but
never edit ruff.toml PT block or test_ruff_pytest_style_baseline.py — PR #5355 owns them; if
unavoidable, list it in the proofs file). Targeted runs only.

Constraints: NO_FULL_HEAVY_SUITES_IN_MISSION; ruff + ruff format clean; commit messages end with the session attribution trailer.
