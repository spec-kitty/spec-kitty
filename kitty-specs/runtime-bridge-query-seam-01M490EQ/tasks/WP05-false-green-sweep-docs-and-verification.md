---
work_package_id: WP05
title: False-green sweep, docs and verification
dependencies:
- WP06
requirement_refs:
- FR-006
- NFR-002
- NFR-003
- NFR-004
- SC-003
- SC-004
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
- T022
phase: Phase 3 - Close-out
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_*.py
- tests/next/**
- tests/runtime/**
- tests/specify_cli/next/**
- tests/integration/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – False-green sweep, docs and verification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission runtime-bridge-query-seam-01M490EQ`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2560-runtime-bridge-query-seam` (stacked on `issue-2561-retire-runtime-bridge-delegates`, PR #5822).
- Final merge target: `issue-2560-runtime-bridge-query-seam`.
- Topology `single_branch`: the WP runs in the repository root checkout; there is no lane worktree.

## Shared rules (all WPs)

- Behaviour-preserving (spec C-001). The one accepted delta is logger names for moved code (plan "Accepted deltas").
- Source changes stay inside `src/runtime/next/` (C-002). No forwarding delegate or self-alias in `runtime_bridge.py` (C-003). New modules follow the `runtime_bridge_<name>.py` convention.
- Moved code is moved **verbatim** (cut/paste plus import fix-ups only). Do not "improve" moved bodies.
- The bridge calls a moved name as `<alias>.<name>` (`_mapping`, `_decision_log`, `_query`). Drop every import the bridge no longer uses (ruff F401), so a stale `runtime_bridge.<name>` patch raises AttributeError.
- **Patch review rule (squad T-1/T-2):** when a test's import or patch of a moved name is repointed, review every other patch in the same test and `with` block by call path. A patch that steered moved code via the bridge must target the owning module now, and the test must assert its fake ran (`.assert_called()`, a call counter, or an observable effect only the fake produces).
- Complexity ≤ 15, no new `noqa`/`type: ignore`. `ruff check`, `ruff format --check --force-exclude <changed files>`, mypy over `src/runtime/next/` adds no error beyond the 21 on the base.

## Objective

Prove the move created no dead patch, document the new layout, and run the full targeted verification.

## Subtasks

### T019 — Probe after the move

Re-run the scratch dead-patch probe (plan D-5) over the 111-path surface. Diff against the baseline by `(test nodeid, patched name)`, summing call counts across modules so a repoint is matched. Every pair whose count dropped (including to zero) is either repointed (with a fake-ran assertion) or explained (e.g. the test deliberately no longer needs it). Record the before/after numbers in `traces/approach.md` (orchestrator writes the kitty-specs side).

### T020 — Static go-silent cross-check

Compute S (names the moved code reads that the slimmed bridge still binds) by AST over the final files. Grep the tests for patches of `runtime_bridge.<S>` and give every hit a disposition (live via a kept bridge caller / repointed / already dead on base). This catches patches the probe cannot see, such as raising fakes, `assert_not_called` and `== []`.

### T021 — Header docs

Rewrite the bridge's `#2531 DECOMPOSITION` comment block for the new layout (add the three modules, drop the stale "KEEP-IN-PLACE" note about `_wrap_with_decision_git_log`), and update the engine and io docstrings that mention the bridge back-edges.

### T022 — Verification

`make test-fast`; the 111-path surface (`-n 8 --dist loadfile`); the gate files `test_no_dead_symbols`, `test_layer_rules`, `test_bridge_cores_import_boundary`, `test_runtime_emitter_seam`, `test_coord_read_residuals_closeout`, `test_no_write_side_rederivation`, `test_read_surface_placement_guard`, `test_topology_inference_retired`, `test_owned_checkout_single_authority`, `test_runtime_charter_doctrine_boundary`; ruff check + format check on changed files; mypy `src/runtime/next/` (≤ 21 errors, none new); `wc -l`. Classify any red against the base.

## Definition of Done

- The probe diff and the static cross-check leave no unexplained dead patch; all checks above pass or are classified as pre-existing.
