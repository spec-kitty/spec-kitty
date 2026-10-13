---
work_package_id: WP01
title: Scenario contract documentation and ADR acceptance
dependencies: []
requirement_refs:
- FR-001
- FR-002
- C-001
- C-003
- C-006
planning_base_branch: ccr-002603b2-bip646
merge_target_branch: ccr-002603b2-bip646
branch_strategy: Planning artifacts for this mission were generated on ccr-002603b2-bip646. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-002603b2-bip646 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
history: []
agent_profile: curator-carla
authoritative_surface: docs/development/testing/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/scenarios/README.md
- docs/development/testing/acceptance-scenarios.md
- docs/adr/4.x/2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md
- docs/adr/4.x/index.md
- docs/development/page-inventory.yaml
role: curator
tags: []
tracker_refs: []
---

# WP01: Scenario contract documentation and ADR acceptance

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission acceptance-scenario-contract-01M4T9GC`

---

## Objective

Write the scenario contract where scenario authors read it, and record ADR 2026-10-13-1 as Accepted.

## Context

Design: `docs/architecture/acceptance-scenario-contract.md` section A. The per-PR check (WP04) enforces exactly this vocabulary, so the wording here is the human-readable source for it. Issue #6134. Public repository: neutral engineering language only, no promise wording.

### Subtask T001: Tag vocabulary in `tests/scenarios/README.md`

- **Purpose**: replace the three-line Tags section with the full vocabulary.
- **Steps**: add a table: `@promise:<id>` (`[A-Za-z0-9][A-Za-z0-9._-]*`, not repeated on one scenario, shape-checked only), `@wip` (needs `@wip-owner:<handle>` and `@wip-since:<YYYY-MM-DD>`), `@manual`, `@defect:<issue>` (positive integer), `@qa:<ref>` (identifier character set), bare tags. State which scenarios gate the nightly (everything except `@wip` and `@manual`). Note that Feature and Rule tags apply to the scenarios under them.
- **Validation**: every tag form in data-model.md appears.

### Subtask T002: Contributor guide `docs/development/testing/acceptance-scenarios.md`

- **Purpose**: same vocabulary plus the boundary and the drafted-scenario flow.
- **Steps**: update the Tags section; add "Linking a scenario to a promise" (identifier only; this repository checks shape only; resolution happens in the QA repository); add "Drafted scenarios" (lands as `@wip` with promise tag, owner and date; may use unbound steps; an engineer binds steps, adds a positive control and removes `@wip`; tooling never invents an identifier); mention the per-PR check by file name (`tests/architectural/test_scenario_contract.py`) and how to run it; bump `updated:`.
- **Validation**: `uv run --frozen pytest -q tests/docs -n auto --dist loadfile`.

### Subtask T003: Mark ADR 2026-10-13-1 Accepted

- **Steps**: front matter `status: Accepted`; body `**Status:** Accepted` with "accepted by the owner on 2026-10-13"; run `uv run --frozen python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/2026-10-13-1-acceptance-scenarios-link-to-promises-by-identifier-only.md` and keep the regenerated index/inventory.
- **Validation**: `freshen_adr_inventory --check` clean.

## Definition of Done

- T001 to T003 recorded done with `spec-kitty agent tasks mark-status`.
- Docs tests and the terminology guard (`tests/architectural/test_no_legacy_terminology.py`) pass.

## Risks

- SEO description band 50 to 180 characters; keep descriptions short.

## Reviewer Guidance

- Check the vocabulary matches data-model.md exactly; no promise wording in examples (use `PR-CLI-INIT-001`-style identifiers only).
