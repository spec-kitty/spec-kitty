---
work_package_id: WP04
title: Reconcile table-edge classification tests (#6543)
dependencies: []
requirement_refs:
- FR-009
- NFR-001
planning_base_branch: tidy-charter-6539-followups
merge_target_branch: tidy-charter-6539-followups
branch_strategy: Planning artifacts for this mission were generated on tidy-charter-6539-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into tidy-charter-6539-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-followups-tidy-01M5CCYJ
base_commit: b80ce6569919ae1e44fe9bede0e7ee0a891f1786
created_at: '2026-10-20T11:47:26.746638+00:00'
subtasks:
- T017
- T018
phase: Phase 1 - Parallel work packages
history:
- at: '2026-10-20T11:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/synthesizer/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/charter/synthesizer/test_synthesize_reconcile.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Reconcile table-edge classification tests (#6543)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`). Behave according to it before reading the rest of this prompt. If the skill is unavailable, read `packs/built-in/agent_profiles/python-pedro.agent.yaml` directly.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log. If this WP came back from review, every feedback item is your TODO list. Record what you changed with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Objectives & Success Criteria

Issue #6543. Test-only. FR-009, User Story 5.

- **Resolved edge:** a project overlay carries a table styleguide edge (`directive --suggests--> styleguide`) whose source is a **shipped directive that is not selected**, for example `directive:DIRECTIVE_034`. Synthesis reconciliation reports **no** `preserved_dangling_endpoint` conflict for that edge.
- **Dangling edge:** an overlay edge naming a URN that **no layer ships**, for example `directive:NOT_SHIPPED_999`, **is** reported as `preserved_dangling_endpoint`.
- **Non-vacuity is proven:** with the shipped-endpoint folding temporarily disabled, the resolved-edge test goes red. Record the result in `add-history`, and revert the mutation.

## Context & Constraints

- Code under test:
  - `src/charter/activation/synthesizer/reconcile.py`: `_classify_conflicts`, at about :671-707;
  - `reconcile_synthesis`;
  - `validation_gate.below_project_base` → `_with_shipped_endpoints`, at about :141-168.
- Existing tests to model on:
  - `tests/charter/synthesizer/test_synthesize_reconcile.py`, at about :631 and :649 (org-base cases);
  - the gate-level pair in `tests/charter/synthesizer/test_styleguide_reach_only.py`, at about :201: a positive `validate()` and a `NOT_SHIPPED_999` negative. Reuse its `_overlay` / `_shipped_graph` helpers by import, or copy them minimally if importing a test module is not the local style.
- Prefer driving `_classify_conflicts` directly. Its keyword-only signature takes `merged_overlay`, `built_in_drg`, `fresh_overlay`, `urn_to_path` and `org_drg`. Optionally add one case through `reconcile_synthesis`, if the existing tests already have a cheap harness for it.
- **No source change in this WP.** If you find a real bug, stop and report it with `add-history` instead of fixing it here.

## Branch Strategy

- **Strategy**: lanes_with_coord (populated by finalize-tasks)
- **Planning base branch**: tidy-charter-6539-followups
- **Merge target branch**: tidy-charter-6539-followups

Start with `spec-kitty agent action implement WP04 --agent claude --mission charter-followups-tidy-01M5CCYJ`.

## Subtasks & Detailed Guidance

### Subtask T017 – The test pair

- Add two tests to `test_synthesize_reconcile.py`, named for the behaviour, for example:
  - `test_classify_conflicts_table_edge_from_shipped_unselected_directive_is_not_dangling`;
  - `test_classify_conflicts_edge_to_unshipped_urn_is_dangling`.
- **Built-in graph:** use the shipped graph that the reach-only tests use, or a minimal built-in graph that contains the directive node. The directive must **not** be in the project's selection.
- **Overlay:** the synthesized styleguide node, plus the edge.
- **Assertions:**
  - The resolved-edge test asserts that no conflict of kind `preserved_dangling_endpoint` names that edge.
  - The dangling-edge test asserts exactly one such conflict for the unshipped edge, and checks its `target_id`/kind.
- Keep each test focused, with no sleeps or file I/O beyond what the existing helpers use.

### Subtask T018 – Non-vacuity proof

- Temporarily make `_with_shipped_endpoints`, or `below_project_base`, return the base without folding.
- Run the two tests. The resolved-edge test must fail; the dangling-edge test must still pass.
- Revert the mutation, re-run, and confirm both pass.
- Record the mutation and both runs in `add-history`. **Commit no mutation.**

## Test Strategy

- `uv run --frozen pytest tests/charter/synthesizer/ -n 4 --dist loadfile`
- Baseline: `make test-fast`.
- Static checks: ruff and `ruff format --check --force-exclude` on the test file.

## Risks & Mitigations

- **A helper import from another test module is not the local style:** copy the minimal helpers instead.

## Review Guidance

- Both tests sit on the same fixture shape.
- The mutation proof is recorded.
- No source file changed.

## Progress & Status

Record progress with `mark-status` and `add-history`.
