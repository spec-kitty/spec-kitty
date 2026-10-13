---
work_package_id: WP01
title: Red-first router-parity gate
dependencies: []
requirement_refs:
- FR-001
- SC-001
planning_base_branch: issue-6125-ci-router-charter-dossier-routing
merge_target_branch: issue-6125-ci-router-charter-dossier-routing
branch_strategy: Planning artifacts for this mission were generated on issue-6125-ci-router-charter-dossier-routing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6125-ci-router-charter-dossier-routing unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
phase: Phase 1 - Red-first gate
history:
- at: '2026-10-13T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_manifest_edit_routes_charter_and_dossier.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_manifest_edit_routes_charter_and_dossier.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first router-parity gate

## Objectives & Success Criteria

- A new architectural gate asserts, through the single routing authority
  `scripts.ci.gate_selection.select_modules`, that each of the four
  `packs/built-in/missions/*/expected-artifacts.yaml` paths selects a **superset of**
  `{"charter", "dossier"}` (FR-001, SC-001).
- The gate is **non-vacuous**: it includes a self-break assertion (a manufactured drift must flip
  it red) and a file-specific-glob guard (`packs/built-in/missions/foo.md` still selects zero code
  shards, so the fix cannot be a broad `packs/**` over-match).
- Proven **RED on `origin/main`** and recorded (command + output) in the tracer and PR.

## Context & Constraints

- Grounding: `kitty-specs/ci-router-charter-dossier-routing-01M4SW1A/research/code-grounding.md`.
- Import the authority; never re-encode a hand path→group map (the #2476 hazard).
- Co-locate with the sibling gates (`tests/architectural/test_gate_selection_authority.py`,
  `test_ci_router_transcription_guards.py`); set `pytestmark = pytest.mark.architectural`.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T001 – Add the parity gate

- **Purpose**: Pin the #6125 contract as an executable gate.
- **Steps**: Create `tests/architectural/test_manifest_edit_routes_charter_and_dossier.py` with:
  - a parametrized test over the four manifest paths asserting
    `select_modules([path]) >= {"charter", "dossier"}`;
  - a self-break / non-vacuity test proving the assertion flips when the glob is absent;
  - a guard that `select_gates(["packs/built-in/missions/foo.md"]).selected_code_shards` is empty
    and `unmatched_src` is False (file-specific glob only).
- **Files**: `tests/architectural/test_manifest_edit_routes_charter_and_dossier.py`.

### Subtask T002 – Prove RED on origin/main

- **Purpose**: ATDD evidence (charter C-011).
- **Steps**: Run the new test against the `origin/main` content of the routing authorities; capture
  the failing output; record it in the tracer (`spec-kitty agent tracer-append`) and the PR.

## Test Strategy

- `pytest tests/architectural/test_manifest_edit_routes_charter_and_dossier.py -q` — RED on base,
  GREEN after WP02.
- `ruff check` + `ruff format --check --force-exclude` on the new file; mypy-clean.

## Risks & Mitigations

- Vacuous gate → self-break assertion + proven RED on base.

## Review Guidance

- Reviewer verifies: the test imports the real authority; RED on `origin/main`; GREEN on final; the
  non-vacuity and file-specific-glob guards are present.

## Progress & Status

Progress/status live in `status.events.jsonl` (`spec-kitty agent tasks ...`).
