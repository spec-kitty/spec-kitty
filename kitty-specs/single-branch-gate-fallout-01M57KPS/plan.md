# Implementation Plan: single_branch gate fallout (#6370, #6369)

**Branch**: `issue-6370-single-branch-gate-fallout` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/single-branch-gate-fallout-01M57KPS/spec.md`

## Summary

Two P0 nightly reds are consumers that the fail-closed single_branch gate (#5939) left stale. The gate stays as it is. The plan:

1. **#6370**: complete the out-of-matrix e2e fixture so it records the planning commit and a distinct implementer and reviewer.
2. **#6369 scenario 6**: align the move-side `SINGLE_BRANCH_IMPLEMENTATION_MISSING` message with the "no implementation commit" vocabulary of `lanes/for_review_gate.py` and the consolidate axis. The plan records why this was chosen over asserting the code.
3. **Audit**: sweep other #5939 consumers for the same drift.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, pytest; acceptance scenarios on Cucumber-JVM 7 (`acceptance-jvm/`)
**Storage**: N/A (git + `kitty-specs/` files)
**Testing**: targeted pytest files plus `make test-fast`. The scenario-6 behavior is reproduced through a shell port of its builder, because Cucumber-JVM needs JDK 25 and the cloud session has JDK 21.
**Target Platform**: Linux / macOS / Windows CLI
**Project Type**: single
**Performance Goals**: N/A
**Constraints**: the #5939 decision logic, codes and fail-closed behavior stay unchanged (C-001). The non-owned move-task JSON envelope stays unchanged (C-002).
**Scale/Scope**: one test fixture, one message string, one focused unit test

## Charter Check

- **Single canonical authority**: the change reuses the existing gates and unifies wording on the phrase `for_review_gate` already uses. It adds no new authority. PASS
- **ATDD / red-first (DIRECTIVE_041/034)**: both reds were reproduced through their pre-existing entry points before any fix: pytest for #6370, and for scenario 6 a CLI-level shell port of the builder. The new unit test pins the phrase and is red against the old wording. PASS
- **Gate discipline / no green-washing (Standing Orders #5, #9)**: no gate is relaxed and no test is skipped or retagged `@wip`. PASS
- **Test policy (`NO_FULL_HEAVY_SUITES_IN_MISSION`)**: targeted files plus `make test-fast` only. PASS
- **Terminology**: Mission / work package. Nothing "feature"-named is introduced. PASS

## Decision record: scenario 6 assertion

| Option | Effect | Verdict |
|--------|--------|---------|
| Assert `SINGLE_BRANCH_IMPLEMENTATION_MISSING` in the scenario | The code is not in the non-owned `move-task --json` output, which is `{"error": msg}`; `error_code` is opt-in to owned checkouts, pinned by `test_context_error_envelope_is_opt_in`. This needs an envelope contract change for every move-task `ActionContextError`. | Rejected: wider than this P0 fallout |
| Align the message wording | One string in `_mt_require_single_branch_implementation`. It joins the vocabulary of `for_review_gate` ("cannot move to for_review: no implementation commit …") and the consolidate axis ("no implementation commit touching its owned_files"). The scenario and the absorption-ledger note stay true, and the code is unchanged. | **Chosen** |

## Project Structure

### Documentation (this mission)

```
kitty-specs/single-branch-gate-fallout-01M57KPS/
├── spec.md
├── plan.md
├── traces/            # tooling-friction / approach / design-decisions
├── tasks.md           # /spec-kitty.tasks
└── tasks/WP01-*.md
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/tasks_move_task.py     # message text only
tests/specify_cli/test_specify_topology_flag.py           # #6370 fixture
tests/specify_cli/cli/commands/agent/                     # focused unit test for the phrase
docs/changelog/CHANGELOG.md                               # [Unreleased] entry
```

## Implementation Concern Map

### IC-01 — e2e fixture completeness (#6370)

- **Purpose**: make `_finalize_single_branch_lanes` and `_seed_wp_approved` build the state the supported flow builds.
- **Relevant requirements**: FR-001, FR-002
- **Affected surfaces**: `tests/specify_cli/test_specify_topology_flag.py`
- **Sequencing/depends-on**: none
- **Risks**: the planning commit must come before every WP code commit, or axis (a) refuses. `HEAD` at compute time is the create commit, which is before the finalize commit and both code commits. The implementer actor must be the *latest* implementing claim: the seed's `claimed`/`in_progress` hops come after the real `implement()` claims.

### IC-02 — move-side refusal vocabulary (#6369 scenario 6)

- **Purpose**: the move-side refusal for a single_branch WP with no implementation names "no implementation commit".
- **Relevant requirements**: FR-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_move_task.py::_mt_require_single_branch_implementation`, plus a focused unit test
- **Sequencing/depends-on**: none
- **Risks**: none of the gate's decision logic changes. Any test that asserts the old prose must be updated; the audit found none in `tests/`.

### IC-03 — #5939 consumer audit

- **Purpose**: find other tests or scenarios #5939 left stale.
- **Relevant requirements**: FR-004
- **Affected surfaces**: out-of-matrix test dirs, single_branch fixtures, `tests/scenarios/**`
- **Sequencing/depends-on**: none
- **Risks**: findings outside this mission's scope are reported in the PR, not widened into it.
