---
work_package_id: WP03
title: Non-project context test hardening (#5989)
dependencies: []
requirement_refs:
- FR-005
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 923890724b3ee69efb601e7ab3e7956fc1103002
created_at: '2026-10-10T06:17:15.552606+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Test hardening
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_cli_boundary_context.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Non-project context test hardening (#5989)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `python-pedro` (implementer, claude).

## Objectives & Success Criteria

`test_non_project_context_errors_are_json[args0..3]` (nightly `interpreter-3.13-shard-3`, #5989) expects every context subcommand run outside a project to answer `not_in_project`. It PASSES on local 3.11 but fails on the nightly because pytest's basetemp there sits **inside the repo checkout**: the CLI project walk-up (`task_utils/support.py:48` `find_repo_root` / `core/paths.py:197` `locate_project_root`, called with **no `stop=` boundary**) finds the enclosing spec-kitty project, so detection *succeeds* and the per-command codes (`no_worktree` / `context_not_found` / `context_resolution_failed`) surface instead.

Done when: the 4 cases pass regardless of where basetemp lives, because the test guarantees its "clean" cwd has no enclosing project ancestor. Production resolution is unchanged (FR-005).

## Context & Constraints
- **C-002**: this is a CI-env artifact — fix the TEST, not the production codes. The walk-up succeeding on a real enclosing project is correct behavior for a real user.
- Do NOT relax the expected codes.
- **Mis-classification guard (adversarial finding F4)**: the operator's steer blames the reworks. BEFORE hardening, PROVE the per-command codes (`no_worktree`/`context_not_found`/`context_resolution_failed`) are unchanged vs the pre-#5883 merge-base — i.e. the rework did NOT change the walk-up ordering so `not_in_project` stopped surfacing. If the codes DID change at the merge-base, this is a real guard-ordering regression (fix production), not a test artifact — STOP and surface it. Record the merge-base evidence in the Activity Log.

## Subtasks
- **T009** — Red-first + classification: reproduce the nightly failure locally by pointing pytest basetemp inside the repo (`--basetemp=<repo>/.tmp_sim`), confirming the per-command codes appear. THEN confirm (git show / checkout the merge-base) that those same codes are produced by the pre-#5883 code for a genuinely-inside-a-project cwd — proving the taxonomy is long-standing, not rework-introduced. If it IS rework-introduced, stop and escalate (do not harden).
- **T010** — Harden the test: build/assert the non-project cwd has no project ancestor — e.g. `assume`/skip or hard-assert when `locate_project_root(cwd) is not None`, or construct the clean cwd under a guaranteed-outside-repo root, or pass a `stop` boundary consistent with production. Keep all four subcommands asserting `not_in_project`.
- **T011** — Verify all 4 cases green under both a normal basetemp and an in-repo basetemp.

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  "tests/specify_cli/cli/commands/test_cli_boundary_context.py::test_non_project_context_errors_are_json"
# and re-run with --basetemp=<repo>/.tmp_sim to prove the hardening holds
```

## Definition of Done
4 cases green under both basetemp placements; no production code changed; expected codes unchanged; `ruff` clean.

## Reviewer Guidance (opus)
Confirm the fix hardens the fixture (no enclosing-project ancestor) rather than weakening expected codes, and that it holds under an in-repo basetemp.
