# Mission Specification: Subtask completion recipes name their work package

**Mission Branch**: `issue-7108-subtask-recipe-wp-scoping`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#7108 — "Subtask IDs are mission-global: mark-status attributes completions to the wrong WP, then move-task takes the refusal"

## Overview

Subtask ids (`T001`, `T002`, …) are scoped to the **mission**, not to the work
package. The normal case — every WP authors its own short `T001..T00n` list —
therefore has the same id owned by several WPs. `mark-status` now resolves that
honestly: `--wp` selects the owner, and an unscoped id with more than one owner
is refused rather than silently attributed.

The remaining defect is downstream of that refusal, and it reproduces on
`main` today: every surface that **prints a subtask-completion recipe** still
prints it *unscoped*, so on a mission whose WPs share ids the printed command is
itself refused. The operator's only way forward is `--force` — the workaround
issue #7108 calls out. The two surfaces are:

1. `move-task`'s unchecked-subtasks refusal
   (`cli/commands/agent/tasks_transition_core.py::_guard_subtasks`), which
   prints `spec-kitty agent tasks mark-status T001 --status done`.
2. The runtime's generated "WHEN DONE" completion blocks
   (`runtime/next/prompt_builder.py::_completion_lines` and three sites in
   `cli/commands/agent/workflow_executor.py`), which print the same unscoped
   command even though the work package id is in scope at every site.

This mission makes every emitted subtask-completion recipe name the work
package that owns the subtask, so the advice is executable in the case that
motivated the report.

**Out of scope**: namespacing subtask ids (`WP02.T001`) in the data model. Issue
#7108 offers that as one of two alternatives; `main` took the other (`--wp`), and
renaming ids would change authored `subtasks:` frontmatter, the event log and
every roster reader. This mission finishes the alternative that was chosen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A blocked implementer is handed a command that works (Priority: P1)

An implementer finishes WP02, whose subtask roster repeats ids that WP01 also
authors. They run `move-task WP02 --to for_review` and are refused because the
subtasks are not recorded done. The refusal tells them exactly which command to
run, and that command runs: it names WP02, so `mark-status` records the
completion against WP02 and the retried `move-task` succeeds — no `--force`.

**Why this priority**: this is the dead end in the issue report. Without it the
refusal actively misdirects the operator toward `--force`, which is how the
mis-attribution stays hidden.

**Independent Test**: call the refusal guard for a WP whose roster is
incomplete and assert the emitted `mark-status` line carries `--wp <that WP>`;
then run that exact command line through `mark-status` on a mission whose two
WPs share ids and assert it exits 0 and records against the named WP.

**Acceptance Scenarios**:

1. **Given** a mission where WP01 and WP02 both author `T001`, and WP02 has an
   incomplete roster, **When** the operator runs `move-task WP02 --to
   for_review`, **Then** the refusal's "Mark these complete first" recipe reads
   `spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission
   <slug>`.
2. **Given** that same recipe, **When** the operator runs it verbatim,
   **Then** it exits 0, records `T001` against WP02, and a retried
   `move-task WP02 --to for_review` no longer reports `T001` unchecked.
3. **Given** a mission where only WP01 authors `T001`, **When** the recipe is
   emitted for WP01, **Then** it still names `--wp WP01` (uniform, not
   conditional on ambiguity).

### User Story 2 - The generated implement prompt is executable (Priority: P2)

An agent driving a work package through `spec-kitty next` reads the "WHEN DONE"
block and runs it verbatim. Because the block names the WP, the completion is
attributed to the work package the agent is implementing, not to whichever WP
happened to be authored first.

**Why this priority**: two lane agents finishing in the same window is the
impact the issue names. The prompt is the normal path, so it must be correct
without the operator editing it.

**Independent Test**: build the implement completion lines for a WP with shared
subtask ids and assert every `mark-status` line carries `--wp <WP>`; assert the
owned-checkout variant still carries both `--wp` and `--owned-checkout`.

**Acceptance Scenarios**:

1. **Given** an implement prompt for WP02 with subtasks `T001 T002`,
   **When** the completion block is rendered, **Then** it reads
   `spec-kitty agent tasks mark-status T001 T002 --wp WP02 --status done
   --mission <slug>`.
2. **Given** an owned-checkout mission, **When** the block is rendered,
   **Then** the line carries `--wp WP02` and `--owned-checkout <root>` in an
   order `mark-status` parses.

### Edge Cases

- A WP that declares no subtasks: the completion block keeps saying "No subtask
  completion command is needed" — no `--wp` is invented for a command that is
  not printed.
- A `mark-status` invocation whose `--wp` names a WP that does not own the id:
  unchanged behaviour, refused by `_resolve_task_owners` with the existing
  owner-naming message.
- The refusal path when `mission_slug` is `None` (direct `MoveTaskRequest`
  construction in tests and third-party callers): the recipe must degrade to a
  still-valid command, not print `--mission None`.
- Subtasks already recorded `skipped`: not reported as unchecked (existing
  behaviour, must not regress).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | move-task refusal names the WP | As an implementer refused by `move-task` for unchecked subtasks, I want the suggested `mark-status` command to name the WP being moved, so that running it verbatim records the completion against the right work package. | High | Open | [build] | no — a recipe without `--wp` is the pre-fix string; the same fixture is asserted both ways |
| FR-002 | refusal recipe is accepted by mark-status | As an operator, I want the refusal's recipe to run successfully on a mission whose WPs share subtask ids, so that I never need `--force` to get past the gate. | High | Open | [build] | no — proven by executing the emitted command through `mark-status` on a shared-id fixture |
| FR-003 | implement prompt recipe names the WP | As an agent implementing a work package, I want the generated "WHEN DONE" `mark-status` command to name my WP, so that two lanes finishing together cannot cross-attribute. | High | Open | [build] | no — asserted on the rendered prompt text |
| FR-004 | owned-checkout variant stays parseable | As an operator on an owned-checkout mission, I want the recipe to carry both `--wp` and `--owned-checkout`, so that the scoped command still targets the owned root. | Medium | Open | [build] | no — asserted on the owned render |
| FR-005 | workflow runbook recipe names the WP | As an operator following the printed runbook after `agent action implement`, I want the same scoped command as the prompt, so that the two surfaces cannot teach different invocations. | Medium | Open | [build] | no — all three emitter sites asserted |
| FR-006 | no recipe is invented for a subtask-less WP | As a maintainer, I want a WP with no authored subtasks to keep its "no completion command is needed" text, so that the fix does not print a command with nothing to mark. | Medium | Open | [build] | no — asserted on an empty-roster render |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new I/O on the refusal path | `_guard_subtasks` stays a pure decision over facts the shell already resolved: adding `--wp` must add no file read, no event read and no mission-state lookup. p95 added latency under 1 ms per refusal. | Performance | High | Open |
| NFR-002 | Recipe text stays a single source | The exact recipe string is produced in one place per surface (helper or shared constant); no test asserts a hand-typed duplicate of production text. | Maintainability | High | Open |
| NFR-003 | Docs and golden fixtures agree | Every documented or byte-frozen example of the completion recipe matches what the code now emits — `check_docs_freshness` errors=0. | Documentation | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No subtask-id renaming | Subtask ids stay mission-scoped `T###`; no `WP02.T001` namespacing, no authored-frontmatter migration, no event-schema change. | Technical | High | Open |
| C-002 | `mark-status` owner resolution unchanged | `_resolve_task_owners` / `_owners_for_task` and their refusal texts are the authority for ownership; this mission only makes emitted recipes pass `--wp`, never relaxes a refusal. | Technical | High | Open |
| C-003 | No gate weakened | No refusal is removed, no `--force` default changed, no test skipped or xfailed to obtain green. | Governance | High | Open |

### Key Entities

- **Subtask roster**: the authored `subtasks:` list in a WP file; static design intent, mission-scoped ids.
- **Completion recipe**: the printed `mark-status … --status done` command an operator or agent is told to run. Now carries the owning WP.
- **Unchecked-subtasks refusal**: the `move-task` guard that reports a WP's incomplete roster and prints the recipe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a mission where two WPs author the same `T001`, the command printed by the `move-task` refusal runs to exit 0 and clears the gate on retry — 100% of the fixture, asserted by executing the emitted string — [build] · no-op passable: no
- **SC-002**: 0 of the completion recipes emitted by the four emitter sites (`_guard_subtasks`, `_completion_lines`, three `workflow_executor` sites) omit `--wp` — [build] · no-op passable: no
- **SC-003**: A WP with an empty authored roster emits 0 `mark-status` lines (unchanged "no completion command is needed" text) — [ratchet] · no-op passable: no
