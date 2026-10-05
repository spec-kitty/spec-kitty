---
description: "Work package task list for the feedback slash command and input hardening mission"
---

# Work Packages: Feedback slash command and input hardening

**Inputs**: Design documents from `kitty-specs/feedback-slash-command-validation-01M3VZBD/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/agent-check-on-demand.md, quickstart.md

**Tests**: Required. Every work package is red-first (ATDD): write the failing test, then the code.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Prompt files live flat in `kitty-specs/feedback-slash-command-validation-01M3VZBD/tasks/`.

**Test policy reminder**: run the specific test files a package owns plus its subsystem directory `tests/specify_cli/feedback/`. Do not run whole-repo suites.

## Work Package WP01: Hardened shared validator (Priority: P1) 🎯 MVP

**Goal**: Strict rating, sanitized comment and strict email in the one shared validator, with structured errors and no send on invalid input.
**Independent Test**: A parametrized table of valid and hostile inputs passes through `parse_rating`, `normalize_comment`, `parse_email` and `agent_submit`, with the expected accept/reject results and no network call on invalid input.
**Prompt**: `tasks/WP01-hardened-shared-validator.md`
**Requirement Refs**: FR-006, FR-007, FR-008, FR-009, FR-011, FR-012, FR-013, FR-015, FR-016

### Included Subtasks

T001 Write the red input table tests in `tests/specify_cli/feedback/test_validation_table.py`
T002 Pin strict rating behavior in `parse_rating` with table coverage
T003 Implement the comment sanitizer in `normalize_comment`
T004 Implement strict single-address `parse_email`
T005 Make `agent_submit` aggregate field errors and prove no send on invalid input
T006 Update existing payload and agent-protocol tests affected by the stricter rules

### Implementation Notes

- Tests first (T001), then T002 to T005, then fix fallout (T006).
- Sanitizer: NFC, remove Cc and Cf categories and ANSI/OSC escape sequences, newline and tab become ordinary whitespace, strip, cap at `COMMENT_MAX_LENGTH` characters without splitting a character. Markup is untouched.
- Keep the shipped error codes `rating_out_of_range` and `email_malformed`.

### Parallel Opportunities

- Runs in parallel with WP02 (disjoint files).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Over-stripping legitimate text: include a markup and symbol preservation case.
- Complexity ceiling 15: extract small helpers for escape stripping and truncation.

---

## Work Package WP02: Comment limit shown before typing (Priority: P1)

**Goal**: Every comment prompt states the 2000-character limit before the user types, built from `COMMENT_MAX_LENGTH`.
**Independent Test**: The comment question text contains the limit in the terminal form and in the agent check payload, and the terminal form shows it before reading input.
**Prompt**: `tasks/WP02-comment-limit-shown-first.md`
**Requirement Refs**: FR-010

### Included Subtasks

T007 Write red tests that the comment prompt states the limit before input in each flow
T008 Build the comment question text in `wording.py` from `COMMENT_MAX_LENGTH`
T009 Ensure `terminal_form.py` shows the new text before reading and update its tests
T010 Confirm the agent check payload carries the new text and update contract tests

### Implementation Notes

- The limit is per comment. It is unrelated to the weekly offer throttle.
- No literal `2000` in prompt text; interpolate the constant.

### Parallel Opportunities

- Runs in parallel with WP01 (disjoint files).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Existing tests pin the old question text: update them deliberately, do not loosen them.

---

## Work Package WP03: On-demand `/spec-kitty.feedback` command (Priority: P1)

**Goal**: Ship `/spec-kitty.feedback`, authored once in the pack source and generated for all 13 slash-command agents and the 4 Agent Skills agents.
**Independent Test**: The command exists for every agent surface after generation; its prompt drives `--agent-check --trigger on_demand` then `--agent-submit` and re-asks only failing questions; the throttle is not consumed.
**Prompt**: `tasks/WP03-on-demand-feedback-command.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005

### Included Subtasks

T011 Spike: choose the lowest-impact registration (prompt-backed step directory versus extending the CLI-wrapper mechanism) and record it in the WP Activity Log
T012 Write red tests for registration and generation across agent surfaces and for on-demand non-throttling
T013 Author the pack source prompt for `feedback`
T014 Register `feedback` in `shims/registry.py` and `skills/command_installer.py`
T015 Pin the surface count tests, regenerate the doctrine graph and freshness artefacts

### Implementation Notes

- Edit only pack source. Agent copies come from generation.
- Use `--trigger on_demand`; add no new flag (constraint C-005).
- The prompt reads the comment limit from the check response, never hardcodes it.

### Parallel Opportunities

- None; depends on WP01 and WP02.

### Dependencies

- Depends on WP01 and WP02.

### Risks & Mitigations

- Command classification sets must stay disjoint and complete.
- Pack edits trip the pack-manifest gate: run `spec-kitty doctrine regenerate-graph` and `--check`.
- Visible CLI count band: a prompt-only command should not change it; verify.

---

## Work Package WP04: Flow parity, docs and verification (Priority: P2)

**Goal**: Prove all flows agree, update user docs and changelog, and run the targeted gates.
**Independent Test**: The shared input table yields identical outcomes through every entry point; docs describe the command, validation rules and limit; gates pass.
**Prompt**: `tasks/WP04-flow-parity-docs-verification.md`
**Requirement Refs**: FR-014

### Included Subtasks

T016 Write the flow-parity test running the shared table through validator, terminal form and `agent_submit`
T017 Update `docs/guides/how-to/collaboration/give-feedback.md` and `docs/context/feedback.md`
T018 Add the changelog entry in `docs/changelog/CHANGELOG.md`
T019 Run targeted gates and record commands and counts

### Implementation Notes

- Docs are vendor-neutral; examples use `example.test` or loopback only.
- Run the terminology guard when touching prose.

### Parallel Opportunities

- T017 and T018 can proceed alongside T016.

### Dependencies

- Depends on WP01, WP02 and WP03.

### Risks & Mitigations

- Parity test gives false comfort if one flow skips the validator: assert each flow calls the shared parsers.

---

## Dependency & Execution Summary

- **Sequence**: WP01 and WP02 in parallel, then WP03, then WP04.
- **Parallelization**: WP01 and WP02 touch disjoint files.
- **MVP Scope**: WP01 and WP02 deliver the validation and limit-notice requirements; WP03 delivers the command.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP03 |
| FR-002 | WP03 |
| FR-003 | WP03 |
| FR-004 | WP03 |
| FR-005 | WP03 |
| FR-006 | WP01 |
| FR-007 | WP01 |
| FR-008 | WP01 |
| FR-009 | WP01 |
| FR-010 | WP02 |
| FR-011 | WP01 |
| FR-012 | WP01 |
| FR-013 | WP01 |
| FR-014 | WP04 |
| FR-015 | WP01 |
| FR-016 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red input table tests | WP01 | P1 | No |
| T002 | Strict rating pinned | WP01 | P1 | Yes |
| T003 | Comment sanitizer | WP01 | P1 | Yes |
| T004 | Strict email | WP01 | P1 | Yes |
| T005 | agent_submit aggregation, no send | WP01 | P1 | No |
| T006 | Fix affected existing tests | WP01 | P1 | No |
| T007 | Red limit-before-typing tests | WP02 | P1 | No |
| T008 | Wording from COMMENT_MAX_LENGTH | WP02 | P1 | No |
| T009 | Terminal form shows limit first | WP02 | P1 | No |
| T010 | Agent check payload and contracts | WP02 | P1 | Yes |
| T011 | Registration spike | WP03 | P1 | No |
| T012 | Red surface and throttle tests | WP03 | P1 | No |
| T013 | Pack source prompt | WP03 | P1 | No |
| T014 | Registry and installer registration | WP03 | P1 | No |
| T015 | Count pins, graph regen, freshness | WP03 | P1 | No |
| T016 | Flow-parity test | WP04 | P2 | Yes |
| T017 | Docs update | WP04 | P2 | Yes |
| T018 | Changelog | WP04 | P2 | Yes |
| T019 | Targeted gates | WP04 | P2 | No |
