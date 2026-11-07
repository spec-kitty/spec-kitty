---
work_package_id: WP01
title: Canonical coordination status custody
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6788-owned-charter-status-custody
merge_target_branch: issue-6788-owned-charter-status-custody
branch_strategy: Planning artifacts for this mission were generated on issue-6788-owned-charter-status-custody. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6788-owned-charter-status-custody unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Owned Mission custody
history:
- at: '2026-11-07T13:36:25Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/core/
create_intent:
- docs/changelog/unreleased/6788.fixed.md
execution_mode: code_change
model: kimi-k3
owned_files:
- src/specify_cli/core/owned_charter.py
- tests/integration/test_owned_prompt_charter_scope.py
- docs/changelog/unreleased/6788.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Canonical coordination status custody

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` through `spec-kitty agent tasks status --mission owned-charter-status-custody-01M6TZKC`.
- Address every feedback item and record progress through `spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

Deliver FR-001 through FR-004: a materialized canonical coordination status directory for the validated owned Mission succeeds through the real prompt path, the primary same-path admission remains direct, every foreign path remains refused, and charter governance remains anchored to the owned primary Mission.

Success requires SC-001 through SC-003 locally: green focused evidence plus an honest draft-PR/issue handoff that marks all 20 parameters and umbrella recovery as pending merged-commit nightly verification.

## Context & Constraints

- Read `kitty-specs/owned-charter-status-custody-01M6TZKC/spec.md`, `plan.md`, and `research.md`.
- #6788's matrix row is `in-mission` for WP01. This WP owns only the 20-node custody class; it does not own startup, #7206, or recovered failures.
- Use `mission_context_for(owned.repository_root, owned.mission_slug, owned=owned, tolerate_unmaterialized_coord=True)` and `MissionArtifactKind.STATUS_STATE` only on the unequal-path arm.
- Keep `CharterScope.resolve(owned.owned_root, owned.mission_dir)` unchanged.
- Do not hardcode worktree paths or alter runtime function signatures.

## Branch Strategy

- **Strategy**: single_branch in the operator-prepared owned checkout; no additional lane worktree.
- **Planning base branch**: `issue-6788-owned-charter-status-custody`
- **Merge target branch**: `issue-6788-owned-charter-status-custody`
- **Final publication**: topic branch push and draft PR targeting `main`; the operator merges.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent opencode --mission owned-charter-status-custody-01M6TZKC --owned-checkout /home/stijn/.t3/worktrees/spec-kitty/t3-bfbad01c
```

## Subtasks & Detailed Guidance

### T001 – Reconfirm the public red reproduction

- **Purpose**: establish that current main still fails through the pre-existing installed CLI entry point before any product edit.
- **Steps**: run `SPEC_KITTY_RUN_PERFORMANCE=1 PWHEADLESS=1 .venv/bin/python -m pytest 'tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated[0]' -q`; capture the exact count and `MISSION_CONTEXT_CONFLICT` signature.
- **Files**: none; do not change the e2e.
- **Notes**: if the environment cannot build/run the immutable wheel, record the limitation honestly and use T002 as the mandatory red-first gate.

### T002 – Add red-first canonical-status integration coverage

- **Purpose**: pin the valid unequal-path behavior and its non-vacuous negative control.
- **Steps**: beside `TestOwnedPromptCharterScope`, use `make_owned_checkouts(topology="lanes_with_coord")`, the real owned validator, canonical coordination branch/worktree helpers, and `mission_context_for` to obtain the actual status directory. Assert it differs from `owned.mission_dir`. Call `build_prompt("specify", status_dir, mission_slug, None, "codex", repository_root, "software-dev", owned=fact)` and assert prompt production, owned charter authority, no primary marker, and unchanged primary snapshot. Add a same-fixture foreign-directory refusal.
- **Files**: `tests/integration/test_owned_prompt_charter_scope.py` only.
- **Commit boundary**: run the new positive before production edits, confirm `MISSION_CONTEXT_CONFLICT`, and commit the red test separately from the fix.

### T003 – Implement exact canonical status admission

- **Purpose**: repair the custody comparison without changing status placement or charter anchoring.
- **Steps**: preserve the existing first equality check. In its unequal arm, resolve canonical status through the mandated call and compare resolved paths exactly. Raise the unchanged error for every mismatch. Do not catch and ignore resolution errors.
- **Files**: `src/specify_cli/core/owned_charter.py` only.
- **Notes**: keep imports lazy as in the existing helper; avoid a new public API or top-level import cycle.

### T004 – Add the changelog fragment

- **Purpose**: describe the user-visible repair narrowly.
- **Steps**: create `docs/changelog/unreleased/6788.fixed.md`; state that owned `lanes_with_coord` advances accept the same Mission's canonical coordination status directory while foreign paths remain refused. Reference #6788 without saying the whole umbrella or startup issue is fixed.
- **Files**: only the new fragment; never edit `CHANGELOG.md`.

### T005 – Validate and record evidence

- **Purpose**: prove red→green and bound residual risk.
- **Steps**: rerun T002's file, `tests/integration/test_owned_next_runtime.py`, T001's exact e2e, then `make test-fast`. Run scoped ruff/format/mypy on changed Python files and the changelog style check if available. Append tracer findings and exact counts.
- **Files**: no planned source changes; tooling-owned tracer/status artifacts are committed through canonical surfaces.
- **Notes**: do not run the 20-node matrix, full e2e, performance suite, full architectural sweep, or `make test-full`.

## Test Strategy

Mandatory commands:

```bash
.venv/bin/python -m pytest -q -p no:randomly tests/integration/test_owned_prompt_charter_scope.py
.venv/bin/python -m pytest -q -p no:randomly tests/integration/test_owned_next_runtime.py
SPEC_KITTY_RUN_PERFORMANCE=1 PWHEADLESS=1 .venv/bin/python -m pytest \
  'tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated[0]' -q
make test-fast
```

Scoped quality gates must include ruff check, `ruff format --check --force-exclude`, and mypy on both changed Python files. Use `.venv/bin/python -m mypy` if the venv has no standalone mypy executable.

## Risks & Mitigations

- **Fast-path lookup regression**: equality remains the first branch; existing primary tests stay unchanged.
- **Custody bypass**: exact canonical match plus foreign negative and no exception swallowing.
- **Wrong charter root**: assert owned content and unchanged primary snapshot.
- **Umbrella overclaim**: explicitly leave merged-commit nightly and startup verification pending.

## Review Guidance

Verify the test commit predates the production commit and its failure uses the same production prompt entry point. Review the whole focused diff, both positive and negative controls, the lack of changes to runtime/e2e/startup files, exact test counts, and scoped type/format/lint results. Reject any broad path matching or foreign-path weakening.

## Operations

1. T001 public red → T002 focused red test commit → T003 one-function fix.
2. T004 fragment → T005 validation and evidence.
3. Independent reviewer role validates the aggregate diff before the draft PR.

## Safeguards / WP Boundaries

Do not modify `src/runtime/next/runtime_bridge.py`, the owned-worktree e2e, startup/performance files, packs, workflows, #7206 assets, or any neighboring PR branch. No second WP owns these paths.

## Progress & Status

Status and history live only in `status.events.jsonl`; do not tick reference rows manually.
