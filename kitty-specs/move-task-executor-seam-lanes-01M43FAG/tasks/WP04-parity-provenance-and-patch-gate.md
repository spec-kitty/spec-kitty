---
work_package_id: WP04
title: Parity-oracle provenance retirement and patch-site gate
dependencies:
- WP03
requirement_refs:
- FR-007
- FR-008
planning_base_branch: claude/move-task-degod-slice-2
merge_target_branch: claude/move-task-degod-slice-2
branch_strategy: Planning artifacts for this mission were generated on claude/move-task-degod-slice-2. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/move-task-degod-slice-2 unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/review/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_patch_targets_live.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/review/test_transition_gate_parity.py
- tests/review/fixtures/parity/_capture.py
- tests/specify_cli/cli/commands/agent/test_move_task_patch_targets_live.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Parity-oracle provenance retirement and patch-site gate

## Do This First: Load Agent Profile

Load `packs/built-in/agent_profiles/python-pedro.agent.yaml` and follow it. Read `.kittify/charter/charter.md`, then `kitty-specs/move-task-executor-seam-lanes-01M43FAG/spec.md` and `plan.md`.

## Objective

DIRECTIVE_041 and the development-assist test-cleanup procedure apply. Retire spent scaffolding without losing decision coverage, and add a gate that keeps re-homed patch targets live (FR-008).

## Subtasks

- **T011**: In `tests/review/test_transition_gate_parity.py`, delete `test_fixture_provenance_is_machine_emitted_base_commit`. It pins a base-commit hash, not behaviour.
  - KEEP the golden fixtures, the replay tests (`test_aggregation_reproduces_base_decision_and_surface`, `test_through_the_inverted_hook_reproduces_base`) and both non-empty-scope coverage guards.
  - Rewrite their docstrings so they read as named contract tests on the decision table, with no "incumbent"/"WP08 parity" language.
  - Delete `tests/review/fixtures/parity/_capture.py` (the spent capture harness), but first `grep -rn "_capture" tests src`. If the replay tests import helpers from it, move just those helpers into the test module rather than deleting coverage.
  - Do not touch `tests/review/test_baseline_head_parity.py`.
- **T012**: Add `tests/specify_cli/cli/commands/agent/test_move_task_patch_targets_live.py`.
  - AST-scan `tests/**/*.py` for `patch.object(<mod>, "<name>")` / `monkeypatch.setattr(<mod>, "<name>", ...)` where `<mod>` is an alias bound to one of `tasks_move_task`, `tasks_move_task_gates`, `tasks_move_task_hops`, `tasks_move_task_executor`. Resolve aliases from the file's imports.
  - Also scan string targets `"specify_cli.cli.commands.agent.<module>.<name>"` in `patch(...)` calls, including f-strings over a `_MODULE`-style constant when it resolves statically. Skip what you cannot resolve.
  - Liveness rule (post-tasks squad fold): a name is live only if the module's source contains an `ast.Call` whose `func` is `Name(id=<name>)`, outside the name's own `def` and outside `ImportFrom` nodes. Re-export lines do NOT count.
    - For `tasks_move_task`, names reached through the `_tasks.` bridge are live only for the patched module `tasks`.
  - Unresolvable targets are counted and printed. Fail if the count exceeds the recorded baseline constant.
  - Negative control: a synthetic in-memory test source that patches `tasks_move_task._mt_emit_runtime_state` (moved by WP03) must be reported as dead.
  - Report offenders with file:line. If the scan finds real dead intercepts, fix them (re-point) in the same commit and list them. If a case is legitimately non-intercepting (it patches a re-export only to assert identity), add an explicit allowlist entry with a reason.
  - Keep the test fast (<2s) and mark it `pytest.mark.unit, pytest.mark.fast`.

- **SC-004**: draft the follow-up ticket text (the same seam-pin and patch-path pattern in the other `tasks_*` seams, #2561) in `traces/design-decisions.md`. The orchestrator files it at closeout.

## Validation

Run `.venv/bin/python -m pytest -q tests/review tests/specify_cli/cli/commands/agent/test_move_task_patch_targets_live.py`, plus ruff and format. Commit citing #5629.
