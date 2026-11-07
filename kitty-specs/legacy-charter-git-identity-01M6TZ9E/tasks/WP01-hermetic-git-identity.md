---
work_package_id: WP01
title: Hermetic Git identity fixtures
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7061-legacy-charter-git-identity
merge_target_branch: issue-7061-legacy-charter-git-identity
branch_strategy: Planning artifacts for this mission were generated on issue-7061-legacy-charter-git-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7061-legacy-charter-git-identity unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Fixture remediation
pre_review_test_scope: tests/specify_cli/migration/test_legacy_charter_gate.py
history:
- at: '2026-11-07T12:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/specify_cli/migration/
create_intent:
- docs/changelog/unreleased/7319.internal.md
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/migration/test_legacy_charter_gate.py
- docs/changelog/unreleased/7319.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Hermetic Git identity fixtures

## Objectives & Success Criteria

- Reproduce the exact three #7061 nodes red before changing the fixture.
- Add repository-local Git identity to the two affected setups and nothing else in production-tree code.
- Prove 3/3 reported nodes and 4/4 behavior-matrix cases green, then pass the owning file and targeted Ruff checks.
- Preserve production behavior and all existing assertions; record nightly closure as a hand-off caveat, not a WP acceptance criterion.

## Context & Constraints

Read `.kittify/charter/charter.md`, `kitty-specs/legacy-charter-git-identity-01M6TZ9E/spec.md`, `plan.md`, and `tasks.md`. Follow the operator's narrow scope: no #7206, #6788, startup-performance, recovered-failure, #7273, or #7287 work. Do not change `safe_commit`, global CI identity, or intended assertions.

## Branch Strategy

- **Strategy**: single_branch in the isolated owned checkout
- **Planning base branch**: issue-7061-legacy-charter-git-identity
- **Merge target branch**: issue-7061-legacy-charter-git-identity

## Subtasks & Detailed Guidance

### Subtask T001 – Capture red-first evidence

Run the three exact pytest node IDs recorded below before any edit. Require three failures with `Author identity unknown` from the later Mission-creation `safe_commit`, proving the tests reach the same production path as the nightly.

### Subtask T002 – Persist repository-local identity

In `test_cli_creates_in_migrated_owned_checkout_when_primary_is_legacy` and `test_cli_startup_claim_is_not_reused_by_later_commands`, extend the existing setup loop immediately after `["init", "-q", "-b", "main"]` with `["config", "user.name", "t"]` and `["config", "user.email", "t@t"]`. Leave the bootstrap `git -c ... commit` and every assertion unchanged. Do not alter similar loops in other tests.

### Subtask T003 – Prove focused green and record the change

Re-run T001's nodes, then both affected functions' complete matrix, then the owning file. Run targeted Ruff lint/format. Add only `docs/changelog/unreleased/7319.internal.md`, named for draft PR #7319 per `docs/changelog/unreleased/README.md`.

## Test Strategy

Red first, expecting **3 failed**:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:randomly \
  'tests/specify_cli/migration/test_legacy_charter_gate.py::test_cli_creates_in_migrated_owned_checkout_when_primary_is_legacy[primary]' \
  'tests/specify_cli/migration/test_legacy_charter_gate.py::test_cli_creates_in_migrated_owned_checkout_when_primary_is_legacy[owned]' \
  'tests/specify_cli/migration/test_legacy_charter_gate.py::test_cli_startup_claim_is_not_reused_by_later_commands[False]'
```

After the fixture edit, the identical command must report **3 passed**. Then require **4 passed**, including the intentional `[True]` sibling:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:randomly \
  tests/specify_cli/migration/test_legacy_charter_gate.py \
  -k 'test_cli_creates_in_migrated_owned_checkout_when_primary_is_legacy or test_cli_startup_claim_is_not_reused_by_later_commands'
```

Owning blast radius and style gates:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:randomly \
  tests/specify_cli/migration/test_legacy_charter_gate.py
.venv/bin/ruff check tests/specify_cli/migration/test_legacy_charter_gate.py
.venv/bin/ruff format --check --force-exclude \
  tests/specify_cli/migration/test_legacy_charter_gate.py
```

## Risks & Mitigations

- Ambient developer identity can hide the defect: use the captured red run, not inference, as the baseline.
- A green local run is not main recovery: explicitly leave #7061 open pending the relevant merged-commit nightly.
- Unrelated broad-suite red is out of scope: do not run or chase it.

## Review Guidance

Confirm the diff adds exactly four setup commands across two loops and does not change assertions or production files. Verify the exact red/green counts and that `[True]` remains an early schema refusal. Check the changelog fragment naming/content and the final nightly caveat.

## Progress & Status

Progress, history, and status live in `status.events.jsonl`; do not hand-edit a history section here.
