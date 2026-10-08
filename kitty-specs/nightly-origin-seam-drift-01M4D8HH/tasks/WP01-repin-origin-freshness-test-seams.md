---
work_package_id: WP01
title: Re-pin the test seams that drifted with origin freshness
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
planning_base_branch: issue-5888-nightly-test-seam-drift
merge_target_branch: issue-5888-nightly-test-seam-drift
branch_strategy: Planning artifacts for this mission were generated on issue-5888-nightly-test-seam-drift. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5888-nightly-test-seam-drift unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Remediation
history:
- at: '2026-10-08T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- tests/specify_cli/doctrine/test_sources.py
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- tests/specify_cli/cli/commands/test_accept_decomposition.py
- tests/integration/test_explicit_checkout_commands.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Re-pin the test seams that drifted with origin freshness

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objectives & Success Criteria

- All 16 node ids in #5886, #5887, #5888 and #5889 pass. Each one fails on the merge base (red first).
- The four owned test files pass in full. Nothing under `src/` changes, and no test is skipped or xfailed.

## Context & Constraints

- `research.md` has the reproduction, the bisected culprits (`dc4524a5`, `73682930`, `9ed59d9c`, `460ba7c8`, all from PR #5845) and the verdict for each group: the test is wrong.
- Charter Standing Orders #4 (judge the test, red first) and #9 (never green-wash). #5891 is out of scope.

## Branch Strategy

- **Strategy**: single_branch. The work lands directly on `issue-5888-nightly-test-seam-drift` in the repository root checkout.
- **Planning base branch**: issue-5888-nightly-test-seam-drift
- **Merge target branch**: issue-5888-nightly-test-seam-drift

## Subtasks

- **T001** `tests/specify_cli/doctrine/test_sources.py`: `_GitRunRecorder` answers `git config … --get core.sshCommand` reads with "unset" (rc 1). It does not consume the script and does not record them in `calls`/`envs`. The empty-script fallback honours `text=`.
- **T002** `tests/specify_cli/cli/commands/test_merge_cli_golden.py`: add `--origin-check` to `EXPECTED_PARSER_LONG_FLAGS`, citing #5780 / PR #5845 / ADR 2026-10-06-3.
- **T003** `tests/specify_cli/cli/commands/test_accept_decomposition.py`: the harness patches `accept_module.run_origin_gate` with a clean fake that records `owned`. `test_stamp_receives_the_cli_edge_fact` also asserts that the gate received the same fact.
- **T004** `tests/integration/test_explicit_checkout_commands.py`: parse `result.stdout` instead of `result.output`. `test_accept_diagnosis_reads_owned_documents_without_writes` asserts the "no remote is configured" note is on stderr and in `advisories`.

## Definition of Done

- Red-first evidence recorded: the node ids fail on the merge base and pass on the branch.
- `ruff check`, `ruff format --check --force-exclude` and mypy are clean on the four files.
- `make test-fast` and the four files pass.

## Reviewer Guidance

- Confirm each change re-pins a seam and does not loosen an assertion.
- Confirm the recorder filter cannot swallow any git call other than the `core.sshCommand` read.
