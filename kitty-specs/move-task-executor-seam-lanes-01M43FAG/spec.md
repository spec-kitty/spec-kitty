# Mission Specification: Move-task executor seam and test-friction cleanup

**Mission Branch**: `claude/move-task-degod-slice-2`
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "Run the next slice of #5629 as a full governed mission, including the related move-task test-suite cleanup (DIRECTIVE_041, development-assist test-cleanup procedure)."

## Context

Slice 1 of #5629 (PR #5661) moved the transition-gate family out of
`src/specify_cli/cli/commands/agent/tasks_move_task.py`, which went from 3,786 to 2,734 LOC.
What's left in the module still mixes three kinds of code:

- **Pure hop-decision builders:** `_binding_role_for_lane`, `_mt_hop_*`, `_mt_plan_review_result`, `_mt_approval_policy_metadata`, `_mt_reassignment_binding_fields`, `_build_claim_review_override`.
- **Emission and recovery orchestration:** `_mt_emit_transitions`, `_mt_emit_runtime_state`, `_mt_execute`, `_mt_persist_wp_file`, `_mt_release_review_lock`, the rollback summary/reset helpers, and `_mt_finalize_plan` / `_mt_persist_rejection_cycle`.
- **CLI parsing and presentation.**

Separately, the move-task test surface carries development-assist scaffolding:

- a hand-maintained list of about 81 private names with a count ratchet;
- a parity oracle pinned to a commit hash;
- tests that patch private helpers on the CLI module.

Each piece of that scaffolding turns red on every behaviour-neutral move.

Grounding: the code-grounding scout (architect profile) and the ticket/test-friction scout (planner profile), both run 2026-10-04.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintainer changes move-task decision logic in one place (Priority: P1)

A maintainer fixing a move-task decision bug can find the hop-decision builders in a dedicated pure module, test them on their own, and change them without touching the CLI module. Examples of such bugs: #5447 (a done WP regressing without `--force`) and #5151.

**Why this priority**: This is the core ask of #5629, and the prerequisite for red-first fixes of the adjacent bugs.

**Independent Test**: Import the hop module and run its table tests without invoking the CLI.

**Acceptance Scenarios**:

1. **Given** the hop module, **When** a test calls `_binding_role_for_lane` / `_mt_hop_review_ref` with plain inputs, **Then** they return the same values the CLI path used before the move.
2. **Given** any existing `move-task` invocation, **When** it runs after the move, **Then** its events, exit code and output are identical to before.

---

### User Story 2 - Emission and recovery live behind an executor seam (Priority: P1)

The steps that write state live in one executor module with focused tests for revert-on-failure and lock release: emitting lane hops through the coordination shell, the runtime-state annotation, persisting the WP file, the rollback reset, and releasing the review lock.

**Why this priority**: These are the recovery paths named in #2555 and #5468. They need to be reasoned about in isolation.

**Independent Test**: Run the executor tests with fake ports.

**Acceptance Scenarios**:

1. **Given** a hop emit fails after a verdict write, **When** `_mt_execute` raises, **Then** the committed verdict write is reverted exactly as before.
2. **Given** a move whose decision carries a review lock, **When** execution finishes, **Then** the lock is released after the emits.

---

### User Story 3 - Runtime-annotation emitter choice owned by the coordination shell (Priority: P2)

`move-task` and `mark-status` each choose between the transactional and the plain inner-state emitter. The precedence is: owned checkout first, then `auto_commit`, then plain. mark-status uses only the owned branch today, which is the same as passing `auto_commit=False`. That choice moves into one coordination-shell helper they both call.

**Why this priority**: It removes a parallel authority, but it touches two commands.

**Independent Test**: Unit-test the helper's choice for `auto_commit` set and unset.

**Acceptance Scenarios**:

1. **Given** an owned checkout, **When** the helper emits, **Then** it uses the transactional emitter and threads `owned=` (#3866).
2. **Given** no owned checkout and `auto_commit=True`, **Then** it uses the transactional emitter.
3. **Given** no owned checkout and `auto_commit=False`, **Then** it uses the plain emitter, with no worktree or transaction resolution before the branch (#3460).

---

### User Story 4 - Refactors no longer turn the move-task suite red for no reason (Priority: P1)

Moving a private helper between seam modules no longer needs hand edits to symbol lists or count comments, and no test pins a commit hash.

**Why this priority**: It applies DIRECTIVE_041 and the development-assist test-cleanup procedure, and every later slice depends on it.

**Independent Test**: Move one symbol between seam modules and check that the compat-surface test needs no edit.

**Acceptance Scenarios**:

1. **Given** the compat-surface guard, **When** a symbol moves from `tasks_move_task` to a seam module and is re-exported, **Then** the guard stays green with no list edit.
2. **Given** the parity oracle, **When** the suite runs, **Then** no test asserts a pinned base-commit hash, and the decision-table coverage still exists as named contract tests.

### Edge Cases

- Tests patch `tasks.<name>` and expect calls inside the family to be intercepted: `_mt_finalize_plan`, `_mt_hop_review_result`, `_mt_execute`, `_mt_resolve_targets`, `_mt_current_event_lane`. Those calls must keep going through the lazy `_tasks.` bridge.
- An import cycle between the new modules and `tasks_move_task` at module scope. This is forbidden; use type-only or lazy imports.
- The shell helper's plain branch must not build a `BookkeepingTransaction` or resolve the coordination worktree (#3460 regression test kept). The `status` → `coordination` import direction stays unchanged: imports inside the helper are lazy.
- A test that patches a moved name on a module that no longer calls it stays green while the patch silently stops intercepting. Re-homed patches therefore need an assert-called check or must be covered by the grep gate.
- Architectural gates hard-code `tasks_move_task.py` paths and line numbers (the untrusted-path inventory, the status-events writes gate allow-list). New emitting modules must be added to the allow-list, not exempted.

## Symbol → module map

| Symbol | Target module |
|--------|---------------|
| `_binding_role_for_lane`, `_mt_hop_review_ref`, `_mt_hop_reason_source`, `_mt_hop_policy_metadata`, `_mt_approval_policy_metadata`, `_mt_hop_actor`, `_mt_hop_review_result`, `_mt_plan_review_result`, `_mt_reassignment_binding_fields`, `_build_claim_review_override`, `_mt_shell_pid_baseline` | `tasks_move_task_hops.py` |
| `_mt_finalize_plan`, `_mt_persist_rejection_cycle`, `_mt_emit_transitions`, `_mt_emit_runtime_state`, `_mt_persist_wp_file`, `_mt_release_review_lock`, `_mt_execute`, `_RollbackResetSummary`, `_mt_build_rollback_summary`, `_mt_rollback_subtasks_reset` | `tasks_move_task_executor.py` |
| `_mt_apply_rollback_signal`, `_mt_rollback_signal_lines` (presentation) | stay in `tasks_move_task.py` |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Hop-decision module | As a maintainer, I want the pure hop builders in `tasks_move_task_hops.py` so that decision logic is isolated from the CLI. | High | Open | [build] | no — the seam test asserts the native module of each builder |
| FR-002 | Executor module | As a maintainer, I want emission/recovery orchestration in `tasks_move_task_executor.py` so that write paths are isolated. | High | Open | [build] | no — the seam test asserts the native module |
| FR-003 | Identity re-exports | As an existing caller, I want every moved name to still resolve as `tasks_move_task.<name>` and `tasks.<name>` by identity so that the compat surface is unchanged. | High | Open | [ratchet] | no — the identity test runs over each moved symbol |
| FR-004 | Shell-owned runtime-annotation emit | As a maintainer, I want one coordination-shell helper, `emit_runtime_annotation(owned, auto_commit, ...)`, choosing the transactional or plain inner-state emitter (owned first, then auto_commit, then plain), used by move-task and mark-status. | Medium | Open | [build] | no — a unit test pins all three branches |
| FR-005 | Derived compat keysets | As a maintainer, I want the compat-surface guard to derive each seam's keyset from native definitions instead of a hand list. | High | Open | [build] | no — the guard fails on a shadow copy, proven by a negative control |
| FR-006 | Generalised no-shadow guard | As a maintainer, I want one parametrised seam test that covers every move-task seam module (gates, hops, executor). | Medium | Open | [build] | no |
| FR-007 | Parity oracle provenance retirement | As a maintainer, I want `test_fixture_provenance_is_machine_emitted_base_commit` and the spent `fixtures/parity/_capture.py` harness retired. The golden fixtures, the replay tests and both non-empty-scope coverage guards stay as named contract tests. `test_baseline_head_parity.py` is untouched. | Medium | Open | [build] | no — the replay tests still assert outcome, exit and metadata per fixture |
| FR-008 | Patch-site re-homing | As a maintainer, I want tests that intercept calls inside a moved family to patch the owning module. | Medium | Open | [folded] | no — every re-homed patch must hit a live call site (grep gate plus assert-called checks where there are none) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behaviour identity | 0 test assertions about move-task behaviour change. Every pre-existing behaviour test passes unmodified except for patch-target repointing. | Reliability | High | Open |
| NFR-002 | Module size | `tasks_move_task.py` is at most 2,050 LOC after the mission (2,734 at start; about 808 LOC of targets less the re-export blocks). | Maintainability | Medium | Open |
| NFR-003 | Quality gates | New and changed code passes ruff, ruff format and mypy with 0 issues; complexity is at most 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Sole authority | The status event log stays the sole authority for lane state. | Architecture | High | Open |
| C-002 | Single validation | Authoritative transition validation runs once, in `status/transition_pipeline`. The existing force-free planning probes in `tasks_transition_core.py` (~254, ~360) are advisory queries; they stay where they are and are neither moved nor duplicated. No new `validate_transition` call sites (grep count of `validate_transition(` under `src/` unchanged). | Architecture | High | Open |
| C-003 | Verbatim moves | Moved bodies are verbatim apart from import plumbing. Behaviour fixes for #5447, #5468, #5151 and #2555 are out of scope. | Process | High | Open |
| C-004 | No ledger widening | Architectural gate ledgers move their entries to the new modules; they gain no new exemptions. | Architecture | High | Open |

### Key Entities

- **Seam module**: a sibling of `tasks_move_task` that natively owns a symbol family and is re-exported by identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tasks_move_task.py` is at most 2,050 LOC — build · no-op passable: no
- **SC-002**: The `_TASKS_MOVE_TASK` hand list is removed; the guard derives its keysets — build · no-op passable: no
- **SC-003**: `tests/specify_cli/cli/commands/agent tests/review tests/status tests/cli tests/tasks` pass. Baseline counts are recorded in `traces/approach.md` at mission start; the final counts differ only by retired scaffolding, each retirement listed by name in the PR — ratchet · no-op passable: no
- **SC-004**: A follow-up ticket is filed for the same seam-pin pattern in the other `tasks_*` seams — folded · no-op passable: yes

## Issue matrix

| Issue | Verdict |
|-------|---------|
| #5629 | In scope (slice 2) |
| #2561 | Partial fold: patch re-homing for the move-task seams |
| #5447, #5468, #5151, #2555, #3563 | Adjacent: not fixed here; the relocation enables red-first fixes |
