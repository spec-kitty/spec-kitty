---
work_package_id: WP01
title: Safe report-only transaction
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: fix/analysis-report-transaction
merge_target_branch: fix/analysis-report-transaction
branch_strategy: Planning artifacts for this mission were generated on fix/analysis-report-transaction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/analysis-report-transaction unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli
create_intent:
- src/specify_cli/analysis_inputs.py
- src/specify_cli/git/report_transaction.py
- tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py
- tests/specify_cli/test_analysis_inputs.py
- tests/git/test_report_transaction.py
- docs/development/analysis-report-transactions.md
execution_mode: code_change
owned_files:
- src/specify_cli/analysis_report.py
- src/specify_cli/analysis_inputs.py
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/git/report_transaction.py
- tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py
- tests/specify_cli/test_analysis_inputs.py
- tests/git/test_report_transaction.py
- docs/development/analysis-report-transactions.md
role: implementer
tags: []
tracker_refs: []
---

# WP01: Safe report-only transaction

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` to load `python-pedro` and apply its boundaries before implementation.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: codex

## Objective

Deliver a report-only recording transaction that preserves unrelated operator work, refuses dirty material inputs and unsafe Git state, and reports actual commit outcomes. Preserve the conservative default and canonical PRIMARY placement.

## Context

Approved plan cb353dcf0e23e5822d013dfb276c3241893bf03b reuses current `safe_commit` path-scoped staging. Do not recreate stash or commit-tree machinery. Root owns independent review. You are not alone in this repository; preserve unrelated primary and other branch state. Existing source lane is the only admitted checkout.

Implementation command: `spec-kitty agent action implement WP01 --mission 01M38YDXPADJA9431Z5A3KMBCV --owned-checkout /Users/sam/git/crucible/spec-kitty/.worktrees/review-thread-closure-upstream --agent codex`.

### Subtask T001: Reproduce transaction acceptance failures

**Purpose**: Establish real behavior through the existing command before changes.

**Steps**:

1. Create a real temporary Git repository with committed mission metadata/spec/plan/tasks and local governance.
2. Leave an unrelated file partially staged, another untracked, and capture staged blob, index flags, and bytes.
3. Invoke `record-analysis --report-only` through CliRunner; initially reproduce missing opt-in behavior.
4. Add negative dirty-input, wrong/protected/detached target, and commit-hook failure cases.
5. Commit failing tests separately and record exact failure evidence.

**Files**: New recorder acceptance tests; focused Git tests where needed.

**Validation**: Red failure must be the missing behavior, not bad fixtures/imports.

### Subtask T002: Resolve a complete material input manifest

**Purpose**: One dependency authority serves preflight and freshness.

**Steps**:

1. Extend report input ownership with a typed manifest, including absent sentinels.
2. Include mission definitions and declared governance/configuration/reference files through canonical resolvers.
3. Conservatively cover resolved local governance trees and pack inputs where exact provenance is unavailable.
4. Exclude known runtime, status, and cache output; normalize existing tasks status using its current authority.
5. Reject symlinks/escapes or unsupported external mutable roots rather than silently drop them.
6. Opt-in reports carry expanded-manifest evidence; default/legacy freshness retains compatibility.
7. Test adding/removing/changing material inputs, generated context churn, and actual read-only Aletheia config closure.

**Files**: `analysis_inputs.py`, `analysis_report.py`, dedicated manifest tests.

**Validation**: Changed selected definition, WP, authority, or declared reference stales a recorded opt-in report. Incidental runtime output does not.

### Subtask T003: Implement guarded report-only recording

**Purpose**: Preserve state while committing only qualified evidence.

**Steps**:

1. Add explicit CLI opt-in; retain the current broad default preflight.
2. Resolve canonical PRIMARY report home and declared commit target before writes.
3. Call canonical commit preflight; reject active operations, conflicted/unsupported indexes and dirty material/report paths using NUL status with rename endpoints.
4. Capture HEAD, material digests, and unrelated staged entries/flags. Render/validate before destination mutation.
5. Recheck immediately before canonical `commit_for_mission` and its existing `git commit --only` mechanics.
6. Verify parent, report-only changed paths, report content, input digests, and unrelated index state after commit.
7. Distinguish failures before write, written-uncommitted, and committed-unqualified outcomes. Never reset or overwrite concurrent state.
8. Keep arbitrary external-writer serializability outside the claim; detect races at observed seams and qualify recovery truthfully.

**Files**: Recorder and bounded Git snapshot/verification module.

**Validation**: Real Git partial staging, flags, unusual paths, linked-origin placement, race injections, and rejecting hooks. No test may stub the commit authority in the main success proof.

### Subtask T004: Qualify, document, and review

**Purpose**: Produce review-ready evidence without claiming an untested unblock.

**Steps**:

1. Run every new test and complete owning recorder/report/Git suites plus required fast baseline.
2. Measure new-code coverage against the 90% requirement.
3. Run lint, formatting, type checks appropriate to touched modules, and diff checks.
4. Document opt-in semantics, dirty authority refusal, compatibility, unsupported states, and recovery outcomes.
5. Update tracer files with implementation decisions and actual evidence.
6. Request independent review at a committed source pin; resolve findings before publication.
7. Inspect review threads/comments/actionable annotations before handoff; publish only a coherent validated non-draft PR.

**Files**: Owned documentation and tests; mission evidence through supported commands.

**Validation**: Record exact commands/counts and baseline dispositions; never call incomplete broad tests a pass.

## Definition of Done

All four subtasks have supported event-sourced completion records. All functional requirements have behavioral proof. Independent implementation review clears the exact pin. Dirty governed inputs still block. No unrelated operator content is committed or restored over concurrent work.

## Risks

Dependency closure, false freshness, and concurrent writers are the principal risks. Conservative declared closure is preferable to an incomplete guessed set. Failures after a real commit must identify that commit and demand recovery, not claim rollback.

## Reviewer Guidance

Try changing authority/reference files absent from the standard charter folder; adding an override after recording; partial staging with index flags; renamed material inputs; a hook or injected seam moving HEAD/index/inputs; and linked invocation with dirty primary authority. Confirm canonical commit/protection policy is not duplicated and the default behavior stays compatible.
