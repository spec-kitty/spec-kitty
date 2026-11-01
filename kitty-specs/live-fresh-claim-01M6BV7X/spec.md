# Mission Specification: Live Fresh-Claim Coverage (#6311)

**Mission Branch**: `issue-6311-live-fresh-claim`
**Created**: 2026-11-01
**Status**: Ready
**Input**: Issue #6311 — "agent action implement refuses its own fresh compact-actor claim as 'already claimed' (4.0.0rc2, same as #4665)".

## Context (grounding, before this mission)

The reported refusal **does not reproduce on current `origin/main`** (`287a226cfe`, `spec-kitty-cli 4.0.0rc8`). Retested live on a real lanes-topology mission with real `git worktree add` lane allocation and no monkeypatched git: `spec-kitty agent action implement WP01 --mission <slug> --agent claude:opus-5.5:python-pedro:implementer` exits 0, claims the WP and renders the prompt in one invocation; `mark-status`, `move-task`, `agent action review` and the approve move all pass with compact actors too.

The bug is held off by two shipped fixes: the CLI-local comparison layer parses a compact `tool:model:profile:role` string down to the same bare-tool key a structured dict yields (`status/work_package_lifecycle.py::_actor_key`, #4665 / `e455ce26c1`), and the claim emit sites now agree on the structured actor shape (#6400). Restoring the pre-`e455ce26c1` verbatim projection in-process reproduces the report exactly: `Error: WP WP01 is already claimed for implementation by 'claude:opus-5.5:python-pedro:implementer'`, exit 1.

What is genuinely missing is **coverage of the live path**. Every existing test of this defect seeds the status event log, pre-fakes the lane worktree, and monkeypatches git and `safe_commit` (`tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py` says so in its own header). The documented end-to-end flow — a real allocator-created lane worktree, a real claim, a rendered prompt — can therefore regress silently, which is why the issue stayed open behind `triage:repro-needed`.

This mission is **verified-already-fixed** on the production path: it adds the missing live guard, and changes no production behaviour.

## User Scenarios & Testing

### User Story 1 - Fresh compact-actor claim is guarded end to end (Priority: P1)

An implementer agent claims a freshly finalized work package on a lanes mission
with its documented compact `--agent` identity. The documented flow must complete
in one invocation and render the prompt — and a future change that reintroduces
the two-representation split must fail this guard rather than ship.

**Why this priority**: It is the only unguarded seam in a bug that has already
been reopened once (#4665 → #6311).

**Independent Test**: Run the new test module alone; it drives the real
`agent action implement` CLI against a real git repository with a real lanes
manifest and asserts the claim completes and the prompt is rendered.

**Acceptance Scenarios**:

1. **Given** a finalized lanes mission whose WP01 sits in `planned` and whose lane worktree does not exist, **When** `agent action implement WP01 --agent claude:opus-5.5:python-pedro:implementer` runs once, **Then** it exits 0, prints no "already claimed", renders the prompt, and leaves WP01 in `in_progress` claimed by the compact identity.
2. **Given** the same mission after scenario 1, **When** the same compact identity re-runs the command, **Then** it exits 0 again (idempotent resume, no conflict).
3. **Given** the same mission, **When** a different tool claims WP01, **Then** the command exits non-zero and reports "already claimed" — so scenario 1 cannot pass by admitting everyone.
4. **Given** scenario 1, **When** the lane worktree is inspected, **Then** it is a real git worktree (`git -C <path> rev-parse --is-inside-work-tree` succeeds) created by the allocator, not a pre-faked directory.

### Edge Cases

- The compact identity carries a model and profile; the claim must still reconcile with the structured actor the start step records in the same invocation.
- The negative scenario (3) must fail for the ownership reason, not because the command could not resolve a workspace.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Live fresh claim completes once | As an implementer, I want the documented fresh compact-actor claim to complete in one invocation so that the documented flow is guarded end to end. | High | Open | [build] | no |
| FR-002 | Recorded claim names the compact tool | As a maintainer, I want the claim event to record the compact identity's tool so that the log and the resume agree. | Medium | Open | [build] | no |
| FR-003 | Same-identity resume stays idempotent | As an implementer, I want a second identical invocation to resume so that retries are safe. | Medium | Open | [build] | no |
| FR-004 | A different tool is refused | As a maintainer, I want a different tool refused with "already claimed" so that the positive scenario cannot pass vacuously. | High | Open | [ratchet] | no |
| FR-005 | Real git, no pre-faked workspace | As a maintainer, I want the guard to use a real allocator-created worktree so that the assertion covers the live plumbing rather than a fixture. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Runtime budget | The module adds no delay of its own: five real CLI invocations in total, no sleeps, no retries, no network. Measured 12-20 s on an idle host and 45-560 s on the 20-agent shared mission host used for this run (load average >= 200 on 40 cores, 6x oversubscribed); the variance is host contention, not the module. | Performance | Medium | Open |
| NFR-002 | Deterministic | The module is green on repeated runs and on any host checkout path (no machine-local absolute paths). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No production change | No production module, gate, or check may be modified, disabled, skipped, or xfailed. | Technical | High | Open |
| C-002 | No duplicated coverage | Only the live path is covered; the existing unit/seeded coverage is not re-litigated (DIRECTIVE_041). | Technical | High | Open |
| C-003 | Charter vocabulary | Use the canonical terms for actor, claim, lane and work package. | Business | Medium | Open |

## Success Criteria

- **SC-001**: The new module passes on `main` and, with the pre-`e455ce26c1` comparison layer restored in-process, fails with the reported "already claimed" refusal — the guard discriminates. — [ratchet] · no-op passable: no
- **SC-002**: Changed-line coverage in the diff stays above the 90% diff-cover bar without weakening any gate. — [build] · no-op passable: no
