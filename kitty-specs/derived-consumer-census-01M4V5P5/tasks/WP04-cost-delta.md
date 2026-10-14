---
work_package_id: WP04
title: Cost delta + charter within-module selection
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- SC-004
planning_base_branch: issue-6173-derived-consumer-census
merge_target_branch: issue-6173-derived-consumer-census
branch_strategy: Planning artifacts for this mission were generated on issue-6173-derived-consumer-census. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6173-derived-consumer-census unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
phase: Phase 4 - Cost
history:
- timestamp: '2026-10-13T17:50:39Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: scripts/ci/consumer_census_cost.py
create_intent:
- scripts/ci/consumer_census_cost.py
- tests/ci/test_consumer_census_cost.py
execution_mode: code_change
owned_files:
- scripts/ci/consumer_census_cost.py
- tests/ci/test_consumer_census_cost.py
role: implementer
tags: []
tracker_refs: []
---

# WP04 — Cost delta + charter within-module selection

`scripts/ci/consumer_census_cost.py`: selected-shard count per recent merged PR
diff and the delta vs. pre-census routing; record in `analysis/cost-delta.md` and
the PR (FR-009). Charter within-module file selection
(`tests/charter_offering/missions/*` + `test_*prompt*`) to cut the 7-shard cost
on a `mission_pack_content` edit — land if tractable within this PR, else carve
to a named follow-up issue and record the decision (FR-010).

Validation: `.venv/bin/python -m pytest tests/ci/test_consumer_census_cost.py -q`.
