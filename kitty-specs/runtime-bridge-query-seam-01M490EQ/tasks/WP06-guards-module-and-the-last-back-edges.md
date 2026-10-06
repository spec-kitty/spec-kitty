---
work_package_id: WP06
title: Guards module and the last back-edges
dependencies:
- WP04
requirement_refs:
- FR-010
- FR-004
- FR-006
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
phase: Phase 2 - Extraction
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_guards.py
create_intent:
- src/runtime/next/runtime_bridge_guards.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge_guards.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_identity.py
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_composition.py
- src/runtime/next/decision.py
- tests/next/**
- tests/runtime/**
- tests/specify_cli/next/**
- tests/integration/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Guards module and the last back-edges

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission runtime-bridge-query-seam-01M490EQ`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2560-runtime-bridge-query-seam` (rebased onto `main` after #5822 merged).
- Final merge target: `issue-2560-runtime-bridge-query-seam`.
- Topology `single_branch`: the WP runs in the repository root checkout.

## Shared rules

Same as WP02–WP04: verbatim moves, `<alias>.<name>` call sites, drop unused bridge imports, the patch review rule (repoint by call path and prove the fake ran), complexity ≤ 15, ruff/format/mypy clean, and no change outside `src/runtime/next/` except tests.

## Objective

Remove the last seam→bridge back-edges (plan D-7, spec FR-010). After this WP, no `runtime_bridge_*` module imports `runtime_bridge`.

## Subtasks

### T023 — Guards module

Create `src/runtime/next/runtime_bridge_guards.py` and move these verbatim: `SPEC_ARTIFACT`, `TASKS_ARTIFACT`, `_should_advance_wp_step`, `_wp_blocks_step`, `_occurrence_gate_failures`, `_log_requirement_extraction_warnings`, `_log_requirement_extraction_warnings_safely`, `_load_wps_manifest_findings`, `_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_has_raw_dependencies_field`. It imports mapping and cores and never io, the bridge, composition or the engine. The bridge calls these as `_guards.<name>`.

### T024 — `_resolve_runtime_feature_dir` to identity

Move it verbatim to `runtime_bridge_identity.py`; its resolver imports stay function-local, so identity stays a leaf. The bridge calls `_identity_seam._resolve_runtime_feature_dir`; `src/runtime/next/decision.py`'s deferred import points at identity.

### T025 — io and composition

io imports the guards module at the top level (`_guards`) and identity's function directly; composition imports the guards module. Delete their deferred `from runtime.next import runtime_bridge as _rb` imports and update the docstrings that describe the back-edges.

### T026 — Tests

Repoint the loud failures and apply the patch review rule.

### T027 — Gates

- `tests/runtime/test_bridge_no_compat_delegates.py`: add seam rows for decision_mapping, decision_log, query, guards and identity (`_resolve_runtime_feature_dir`), using the owning-module lookup the gate already has. The public re-exports (`query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError`, `MissionNotFoundError`, `DecisionGitLogUnavailable`) join the kept-re-export identity check.
- Layout gate: add the empty-set invariant "no `runtime_bridge_*` module imports `runtime_bridge`". Remove the layout rows the canonical gate now owns (no definition / no attribute on the bridge, re-export identity), so each property has one authority.

## Definition of Done

- `grep -n "import runtime_bridge\b" src/runtime/next/runtime_bridge_*.py` finds nothing; both gates green; targeted surface green.
