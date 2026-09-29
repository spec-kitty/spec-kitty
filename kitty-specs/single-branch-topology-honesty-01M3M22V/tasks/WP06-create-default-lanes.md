---
work_package_id: WP06
title: Create default becomes lanes (#2602)
dependencies:
- WP04
requirement_refs:
- FR-013
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-28T23:27:58.372112+00:00'
subtasks:
- T025
- T026
- T027
phase: Phase 5 - Create default
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission_create.py
- tests/specify_cli/cli/commands/agent/test_mission_create.py
- tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
- tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py
- tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Create default becomes lanes (#2602)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, `implementer`, `claude`) and follow its guidance.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`; address every item.

---

## Objectives & Success Criteria

This WP implements decision item 2, FR-013, US4 and SC-005. `_resolve_default_topology_phase` in `cli/commands/agent/mission_create.py:373-420` has two implicit `SINGLE_BRANCH` returns, and both become `MissionTopology.LANES`:

- `:417`: the pr-bound arm when `coord_topology_reachable(...)` is false.
- `:420`: the non-primary branch without `--pr-bound`.

After the change, `single_branch` is produced only by an explicit `--topology single_branch` or by `--owned-checkout`. Check how `--owned-checkout` currently derives topology, and keep it resolving to `single_branch`.

**Done when:**
- a default-matrix test covers every combination (primary / non-primary × pr-bound / not × coord reachable / not × explicit topology / owned-checkout) and asserts the resulting topology;
- the pinned tests are updated with a one-line rationale each;
- help text and docstrings describe the new default.

## Context & Constraints

- Read first: `spec.md` US4; `research.md` R-11; the #2602 issue text (the pinned test `test_create_pr_bound_on_non_primary_branch_still_defaults_to_coord` is referenced there).
- **Minimal golden edits (C-005).** Update only the assertions whose expected topology legitimately changes. Do not touch unrelated expectations.
- **Branch discipline.** Never write `main` as a generic default name (charter, Branch-Intent Terminology).

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`. Run `spec-kitty implement WP06 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Red-first (charter C-011; analysis finding C1)

Before any implementation commit in this WP, commit the new behaviour tests **alone**, and show that they are RED against the WP's planning base.

- The failure must be an assertion failure. An ImportError, or a crash in a fixture, does not count as red.
- Record the red run (command plus the failing test names) in the Activity Log.
- The reviewer verifies red→green.

The red set for this WP is `test_mission_create_default_topology_matrix.py`, together with the CLI-level default test from T026. The `LANES` rows fail on the planning base.


### Subtask T025 – Default derivation

- Change the two returns to `LANES`.
- Rewrite the function docstring (`:380-397`) so it describes the new policy: `single_branch` is explicit-only, per decision #5100 (comment 5870360497) and #2602.
- Keep the fail-safe `COORD` for an unresolvable repo root. Keep the primary-branch `COORD` default.

### Subtask T026 – Pinned tests and the default matrix

- New test file `tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py`: a parametrized unit test of `_resolve_default_topology_phase`. Monkeypatch `resolve_primary_branch`, `ProtectionPolicy.resolve` and `coord_topology_reachable`, covering at least:

  | Case | Expected topology |
  |---|---|
  | non-primary, no pr-bound | `LANES` |
  | pr-bound, unreachable | `LANES` |
  | pr-bound, reachable | `COORD` |
  | primary | `COORD` |
  | explicit `single_branch` | `SINGLE_BRANCH` |
  | explicit `lanes` | `LANES` |
  | unresolvable repo | `COORD` |
  | `--owned-checkout` (no `--topology`) | `SINGLE_BRANCH` |

- Also add one CLI-level test through `CliRunner` that asserts `meta.json` `topology == "lanes"` for a create on a feature branch without `--topology`.
- `tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py:131-153` pins pr-bound on an unprotected primary → `single_branch`; update it to `lanes` (post-tasks fold M-4).
- Update the pinned assertions:
  - grep `SINGLE_BRANCH\|single_branch` in `tests/specify_cli/cli/commands/agent/test_mission_create*.py`, `tests/specify_cli/test_mission_create_retention.py` and `tests/core/test_mission_create_*.py`;
  - change only the expectations that relied on the implicit default;
  - where a test meant to exercise single_branch behaviour, add `--topology single_branch` instead of changing its expectation.

### Subtask T027 – Help text

- The `--topology` option help (`:712-722`) should say: "Default: context-derived — coord on the primary branch or with --pr-bound when coordination is reachable; lanes otherwise. single_branch only when requested explicitly (or via --owned-checkout)."
- Grep the docs for the old wording (`single_branch on a non-primary`) and leave a note for WP09 rather than editing docs here.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py tests/specify_cli/cli/commands/agent/test_mission_create.py tests/specify_cli/cli/commands/agent/test_mission_create_phases.py tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py tests/specify_cli/test_mission_create_retention.py -q
.venv/bin/python -m pytest tests/core/test_mission_create_activation_gate.py tests/core/test_mission_create_idempotency_guard.py tests/core/test_mission_create_scaffold_rollback.py tests/core/test_mission_create_checkout_restore.py tests/core/test_issue_2693_mission_create_clean_scaffold_guard.py tests/e2e/test_mission_create_clean_output.py -q
grep -rl "_resolve_default_topology_phase\|defaults_to_coord\|single_branch" tests/ --include=*.py | xargs -r grep -l "mission_create\|mission create" | head   # run each listed file
.venv/bin/mypy --strict src/specify_cli/cli/commands/agent/mission_create.py ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

Also re-run the e2e workflow test named in the plan folds (`TestFullCLIWorkflow::test_full_workflow_sequence`). Its default-topology mission now gets `lanes`, so the `lane-a` assertion stays valid.

## Risks & Mitigations

- **Hidden callers relying on the old default** in test fixtures that create missions on feature branches, then assume no lanes. The grep above finds them. Fix a fixture by making its topology explicit, not by weakening its assertions.

## Review Guidance

- Every changed pinned assertion has a rationale.
- The matrix covers all arms.
- Nothing produces `single_branch` implicitly.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
