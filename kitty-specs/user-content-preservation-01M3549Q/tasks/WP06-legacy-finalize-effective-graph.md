---
work_package_id: WP06
title: Legacy finalize validates the persisted dependency graph (#4890)
dependencies: []
requirement_refs:
- FR-009
- FR-010
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: bf4583e83c145ed96d27cf189ba7007619bfe62d
created_at: '2026-09-22T18:44:26.527392+00:00'
subtasks:
- T020
- T021
- T022
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_finalize.py
create_intent:
- tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- src/specify_cli/cli/commands/agent/tasks_finalize_validation.py
- tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (profile YAML), then return.

## Objective

The legacy `spec-kitty agent tasks finalize-tasks` runs cycle detection on the graph parsed
from `tasks.md`, but persists whatever `dependencies:` the WP **frontmatter** already carries,
unvalidated (#4890). A WP01↔WP02 cycle (or an unknown-WP / self-ref) living only in frontmatter
therefore passes: exit 0, a falsified `dependencies` payload, canonical status seeded, both WPs
permanently unclaimable. Validate the **effective persisted** graph, reusing the canonical
validator that `agent mission finalize-tasks` already uses (single authority — do NOT fork).

## Ground truth (verified on main@d57619a900)

- `cli/commands/agent/tasks_finalize.py:213-230` `_ft_validate` runs `detect_dependency_cycles(st.dependencies_map)` on the **tasks.md** map only.
- `cli/commands/agent/tasks_finalize_validation.py:300-305` `compute_wp_frontmatter_updates`: `if not parsed_deps and existing_deps: deps = existing_deps; plan.preserved_wps.append(wp_id)` — preserved frontmatter deps never re-validated.
- `core/dependency_graph.py:251-311` `validate_dependencies` (self-dep, malformed id, "Dependency WPxx not found in graph") — never called here; its only prod call site is `mission_finalize.py:1149`.
- Contrast `cli/commands/agent/mission_finalize.py:1133-1158` `_validate_dependency_graph` runs BOTH `detect_cycles` and `validate_dependencies` over the effective graph → the canonical command correctly refuses.

## Subtasks

### T020 — [RED FIRST] Regression repro
`tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py` (`@pytest.mark.regression`),
real CLI (single_branch), tasks.md declaring NO deps, frontmatter carrying the graph:
- WP01↔WP02 cycle in frontmatter → `agent tasks finalize-tasks` exits non-zero (`Circular dependencies`), seeds NO canonical status, does not report success. (RED on base: exit 0 + falsified payload.)
- frontmatter dep on unknown `WP99` → exit non-zero "unknown dependency". (RED on base.)
- self-dependency `WPnn → WPnn` → exit non-zero via `validate_dependencies` self-dep branch. (RED on base.)
- **anchor (green-on-base)**: a valid acyclic frontmatter graph finalizes with exit 0 and `dependencies` payload == the persisted frontmatter graph.
Use `agent mission finalize-tasks` on the identical repo as the control (it already refuses).
Capture RED output; commit tests first.

### T021 — Validate the effective persisted graph
- Compute the effective graph = tasks.md-parsed deps merged with preserved frontmatter deps (the graph actually written). Run BOTH `detect_dependency_cycles` and `core.dependency_graph.validate_dependencies` over it, reusing `mission_finalize._validate_dependency_graph` (or the same underlying functions) — do not write a second validator.

### T022 — Fail closed; honest payload
- On any cycle/self-ref/unknown-WP: exit non-zero with the same error class as `agent mission finalize-tasks`, and seed NO canonical status (do not run bootstrap).
- On success: the JSON `dependencies` payload must equal the effective persisted graph (not the empty tasks.md map).

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Worktree per lane from `lanes.json`.

## Definition of Done

- Regression RED on base, GREEN on fix (cycle + unknown + self-ref); valid-graph anchor green with correct payload.
- No second validator authored; reuse the canonical one.
- No canonical status seeded on rejection.
- mypy --strict + ruff clean; complexity ≤ 15.
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/regressions/test_issue_4890_*.py tests/cli/test_tasks_finalize_lanes_minting.py -q` — record counts.

## Reviewer guidance (reviewer-renata, opus)

- Validator is the canonical one (single authority), run over the EFFECTIVE graph.
- Payload equals what was persisted; no status seeded on rejection.
