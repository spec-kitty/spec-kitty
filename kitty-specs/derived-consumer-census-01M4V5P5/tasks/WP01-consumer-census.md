---
work_package_id: WP01
title: 'Consumer census: model, static + runtime capture, committed artifact'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-6173-derived-consumer-census
merge_target_branch: issue-6173-derived-consumer-census
branch_strategy: Planning artifacts for this mission were generated on issue-6173-derived-consumer-census. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6173-derived-consumer-census unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Census
history:
- timestamp: '2026-10-13T17:50:39Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: scripts/ci/consumer_census.py
create_intent:
- scripts/ci/consumer_census.py
- tests/ci/test_consumer_census.py
- .github/ci-consumer-census.json
execution_mode: code_change
owned_files:
- scripts/ci/consumer_census.py
- scripts/ci/gate_selection.py
- tests/ci/test_consumer_census.py
- .github/ci-consumer-census.json
- .gitignore
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Consumer census: model, static + runtime capture, committed artifact

Build `scripts/ci/consumer_census.py` producing, per registry test module, the
`src/**`/`packs/**` paths its tests consume — static (AST import + file-read +
path string-literal scan over the module's `test_dirs`) AND runtime (bounded,
offline audit-hook capture of resolver-driven opens the static scan misses, the
`tests/next` prompt case canonical). Emit the deterministic, committed
`.github/ci-consumer-census.json` (schema: data-model.md). Module universe +
attribution reuse `gate_selection._registry_module_names` /
`_modules_for_test_paths` so a #6164 module-set change flows through (NFR-002).

ATDD: commit T001 (determinism + three-consumer) red-first before T002–T005.
Validation: `.venv/bin/python -m pytest tests/ci/test_consumer_census.py -q`.
