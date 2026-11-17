---
work_package_id: WP06
title: Default-topology retarget end-to-end
dependencies:
- WP02
requirement_refs:
- FR-003
- FR-004
- FR-006
- C-006
- SC-001
planning_base_branch: issue-7692-consolidate-retarget
merge_target_branch: issue-7692-consolidate-retarget
branch_strategy: Planning artifacts for this mission were generated on issue-7692-consolidate-retarget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7692-consolidate-retarget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-retarget-01M7M5JA
base_commit: 1c713064dfbba94d45876acb06b641dfd8240516
created_at: '2026-11-17T11:49:10.271714+00:00'
subtasks:
- T025
- T026
- T027
phase: Phase 4 - Acceptance
history:
- at: '2026-11-17T09:30:00Z'
  actor: system
  action: 'Prompt generated via /spec-kitty.tasks (operator ruling: default-topology Missions in scope)'
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent:
- tests/integration/test_default_mission_consolidate_retarget.py
execution_mode: code_change
owned_files:
- tests/integration/test_default_mission_consolidate_retarget.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Default-topology retarget end-to-end

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Any review feedback is your TODO list.

---

## Objectives & Success Criteria

**Operator ruling (2026-11-17, relayed by the core triager):** `--retarget` must work for default-topology Missions in this PR. These are Missions created without `--topology`, with `topology_source: default`. "I am tired of deferrals."

This WP proves it through the REAL CLI on two settlement outcomes:
- `lanes_with_coord`: three code lanes. The topic branch is the Mission branch and the coordination branch.
- `single_branch`: at most two WPs. The topic branch is the Mission branch and the write branch.

On each, `spec-kitty consolidate --mission <m> --target develop --retarget` must:
- exit 0;
- land the work on `develop`;
- leave `develop:kitty-specs/<slug>/meta.json` with `target_branch == "develop"` and one `retarget_history` entry;
- carry every WP as `done` on `develop`;
- leave the old target (`work`) untouched;
- leave a clean `kitty-specs/` in the root checkout.

Each arm has a same-fixture control: a run without the retarget onto the recorded `work` lands there.

Red first:
1. Run the file against the planning base, before WP01–WP03.
2. Expect `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE` on the plain `--target`, and exit 2 (unknown option) on `--retarget`.
3. Record that evidence with `add-history`.

## Context & Constraints

- Reuse the existing default-Mission end-to-end fixture: `tests/integration/test_default_mission_consolidate_lands_primary.py` (`build`, `cli`, `consolidate`, `_ok`, `target_meta`, `_quiet`, the `_TARGET = "work"` convention) and `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py` (`make_default_mission`, `THREE_LANES`, `run_finalize`).
- Import those helpers. Do not copy them.
- If `build` cannot express a two-WP `single_branch` Mission, add a small local builder in this file that calls `make_default_mission` with two owned files, following `build`'s implement / approve steps. Read how a default `single_branch` Mission implements: WPs run in the write checkout on the topic branch.
- Mark the module like its sibling: `pytestmark = [integration, git_repo, non_sandbox, slow]`.
- `develop` is cut from `work` after the Mission was created. Check it out in the repository root checkout before `consolidate`, because the off-target preflight requires the root checkout on the effective target. A default Mission's record lives on its topic branch, so `develop` does not carry the Mission directory. That is the shape the plan's holder rule handles (record written on the topic branch only, carried to `develop` by the landing).

## Branch Strategy

- **Planning base branch**: `issue-7692-consolidate-retarget`
- **Merge target branch**: `issue-7692-consolidate-retarget`

`spec-kitty agent action implement WP06 --agent claude --mission consolidate-retarget-01M7M5JA`

## Subtasks & Detailed Guidance

### Subtask T025 – Default `lanes_with_coord` retarget

1. Run `build(tmp)` from the sibling module (settled `lanes_with_coord`, approved).
2. Run `git checkout -b develop work` in the root checkout.
3. Run `consolidate --target develop --retarget --retarget-reason e2e-default`.
4. Assert:
   - exit 0;
   - `develop` carries the three owned files;
   - `meta.json` on `develop` has `target_branch == "develop"`, `retarget_history[-1]` from `work` to `develop`, `mission_number == 1`, and no `coordination_branch`;
   - the topic branch and the coordination worktree are removed;
   - `work`'s tip is unchanged;
   - `git status --porcelain -- kitty-specs` is empty in the root checkout.
5. Control (a separate build): a plain `consolidate` with no `--target` lands on `work`. The sibling module already proves this, so cite it in the docstring rather than re-running it, to save time.

### Subtask T026 – Default `single_branch` retarget

Same assertions on a two-WP default Mission settled to `single_branch`:
1. Retarget to `develop`; expect exit 0, the work on `develop`, and the meta assertions.
2. Assert the write checkout is clean afterwards.

If the run needs the root checkout on the topic branch rather than on `develop` (single_branch landings switch the write checkout after landing; see `executor._switch_write_checkout_after_single_branch_landing`), drive it the way the product requires and document it in the test docstring.

If this shape genuinely cannot be retargeted:
- capture the exact refusal;
- STOP and report it to the orchestrator, with the output, as evidence for the operator;
- do not silently mark the arm `xfail`.

### Subtask T027 – Failure and plain-override controls on the default shape

1. **Injected failure** (`lanes_with_coord`). Use the sibling shim's `WP20_FAIL_BEFORE=_phase_merge_lanes` hook, then run `--target develop --retarget`. Assert:
   - exit ≠ 0;
   - the topic branch tip is back at its pre-run tip;
   - `git show <topic>:kitty-specs/<slug>/meta.json` names `work`;
   - `develop` is unchanged.

   A re-run lands with exactly ONE `retarget work -> develop` commit in `develop`'s history.
2. **Plain `--target develop`** without `--retarget` on the default shape: `TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE`, nothing moved, and the remedy names `--retarget`.

## Test Strategy

```
.venv/bin/python -m pytest tests/integration/test_default_mission_consolidate_retarget.py -n 3 --dist loadfile -q --durations=10
```
These are slow integration tests, outside NFR-003's terminus budget. Keep them to the arms above, and use module-scoped fixtures where an arm only reads.

## Risks & Mitigations

- **Fixture cost:** each `build` drives implement, review and approve through the CLI. Share builds through module-scoped fixtures where the arms do not mutate.
- **An unknown single_branch landing shape:** report rather than guess.

## Review Guidance

- Both settlement outcomes are covered.
- The record is on `develop` after the landing.
- The plain override still refuses.
- There is red evidence in the history.

## Progress & Status

`spec-kitty agent tasks add-history WP06 --note "..."`; `spec-kitty agent tasks mark-status T0xx --status done --mission consolidate-retarget-01M7M5JA`.
