---
work_package_id: WP02
title: Unstub gates in legacy harnesses (#5345)
dependencies: []
requirement_refs:
- FR-002
- FR-003
planning_base_branch: claude/p0-5353-test-suite-quality-g3tt8f
merge_target_branch: claude/p0-5353-test-suite-quality-g3tt8f
branch_strategy: Planning artifacts for this mission were generated on claude/p0-5353-test-suite-quality-g3tt8f. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/p0-5353-test-suite-quality-g3tt8f unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-quality-p0-01M3NYXQ
base_commit: 598abdfcb5fb123ffe354cf587f4617c9dde9fce
created_at: '2026-09-29T06:54:48.197271+00:00'
subtasks:
- T008
- T009
- T010
- T011
history: []
agent_profile: implementer-ivan
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- tests/integration/test_post_merge_unrelated_untracked.py
- tests/cli/commands/test_merge_status_commit.py
- tests/specify_cli/acceptance/test_acceptance_cores.py
tags: []
tracker_refs: []
---

# WP02: Unstub gates in legacy harnesses (#5345)

See `tasks.md` for subtasks and `spec.md` for requirements.

Move stubbed-gate harnesses to real-git fixtures, or delete tests with proof that coverage survives
(name the covering real-git test and run it green). Each retained/reworked test needs planted-break
proof (remove/neuter the gate in production scratch edit -> RED, revert -> GREEN) recorded in
research/red-proofs-wp02.md. Prefer existing real-git fixtures (grep tests/ for conftest git
helpers) over new infrastructure. Targeted runs only.

Constraints: NO_FULL_HEAVY_SUITES_IN_MISSION; ruff + ruff format clean; commit messages end with the session attribution trailer.
