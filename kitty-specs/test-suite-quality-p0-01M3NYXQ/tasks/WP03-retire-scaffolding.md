---
work_package_id: WP03
title: Retire dev-assist scaffolding (#5346-adjacent audit items)
dependencies: []
requirement_refs:
- FR-004
- FR-005
planning_base_branch: claude/p0-5353-test-suite-quality-g3tt8f
merge_target_branch: claude/p0-5353-test-suite-quality-g3tt8f
branch_strategy: Planning artifacts for this mission were generated on claude/p0-5353-test-suite-quality-g3tt8f. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/p0-5353-test-suite-quality-g3tt8f unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-quality-p0-01M3NYXQ
base_commit: 598abdfcb5fb123ffe354cf587f4617c9dde9fce
created_at: '2026-09-29T06:55:03.345848+00:00'
subtasks:
- T012
- T013
- T014
- T015
- T016
- T017
history: []
agent_profile: implementer-ivan
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- tests/missions/test_resolution_convergence.py
- tests/unit/test_symbol_identity_spike.py
- tests/architectural/_symbol_identity.py
- tests/coordination/test_surface_authority_goldens.py
- tests/architectural/test_charter_owner_map_executed.py
- tests/adversarial/test_infrastructure.py
tags: []
tracker_refs: []
---

# WP03: Retire dev-assist scaffolding (#5346-adjacent audit items)

See `tasks.md` for subtasks and `spec.md` for requirements.

For each retirement, VERIFY the named covering guard exists and passes (run it), grep for consumers
of any helper/fixture before deleting, and only then delete. One commit per retirement; commit
message names the covering guard file:line. If the covering guard cannot be verified, do NOT delete;
record in research/retirement-ledger.md. Audit source: /mnt/project-files/test-
review/2026-09-29-dev-assist-test-audit.md (or issue #5353 comment).

Constraints: NO_FULL_HEAVY_SUITES_IN_MISSION; ruff + ruff format clean; commit messages end with the session attribution trailer.
