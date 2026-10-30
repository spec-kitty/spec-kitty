---
description: "Work package task list for agent-string-parser-hardening-01M6699F"
---

# Work Packages: Agent String Parser Hardening

**Inputs**: Design documents from `kitty-specs/agent-string-parser-hardening-01M6699F/`
**Prerequisites**: plan.md (required), spec.md, research.md, data-model.md, contracts/agent-boundary-parser.md, quickstart.md

**Tests**: Required — this is a defect fix; every row of #6755's table gets a failing-first test (FR-004).

**Organization**: One work package; the mission is a single bounded defect fix.

## Subtask Format: `[Txxx] [P?] Description`

- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the sole subtask-completion authority.

---

## Work Package WP01: Harden the compact agent-string parser (Priority: P1) 🎯 MVP

**Goal**: `parse_agent_boundary_string` strips every segment, treats a blank-after-strip segment as absent, and refuses more than four segments; the explicit `--agent` paths refuse such values with the existing clean refusal; the lenient paths keep whole-value storage.
**Independent Test**: The commands in `kitty-specs/agent-string-parser-hardening-01M6699F/quickstart.md` pass: the parser unit rows, the three CLI refusal paths, and mypy --strict.
**Prompt**: `/tasks/WP01-harden-agent-boundary-parser.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Write failing-first parser tests for the three issue rows in `tests/status/test_actor_boundary_normalize.py` (whitespace segment → None; unstripped segment → stripped; >4 segments → ValueError), run them RED on the planning base, and commit the red state
T002 Write failing-first CLI refusal tests for `--agent "a:b:c:d:e"` on the three explicit paths (`mark-status`, `add-history`, `move-task`) alongside the existing #6400 tests, run them RED, and commit
T003 Implement the hardening in `src/specify_cli/status/models.py` (`parse_agent_boundary_string`): strip each segment, blank-after-strip is `None` (or the existing empty-tool `ValueError` for the tool), and >4 segments raises a `ValueError` naming the count; update the docstring contract
T004 Run the targeted test surface (`tests/status/test_actor_boundary_normalize.py` plus the two #6400 CLI test files) and `mypy --strict` on the touched module; verify red→green and record commands + counts
T005 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead with `(#6755)`, before/after, under 1,200 characters)

### Implementation Notes

- Red-first (ATDD, DIRECTIVE_034): T001 and T002 land as a commit before T003's production edit; the reviewer verifies red on the planning base and green on the final commit.
- No call-site changes: the refusal on the three explicit paths comes from the parser's `ValueError` flowing through the existing seams (`_ms_status_actor`, `_refuse_unparseable_agent`). Do not add per-command checks.
- Do not touch `wp_metadata._resolve_agent_from_colon_string` (separate authority) or `actor_from_option` (lenient path, pre-checks the count).
- Opening campsite check: record a no-enabler conclusion (function is 9 lines, single-purpose) in the mission traces.

### Parallel Opportunities

- None; single WP, strictly ordered.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A caller silently relying on truncation → ruled out by the call-site survey in research.md; the reviewer re-verifies with `grep -rn "parse_agent_boundary_string" src/`.
- Identity comparison drift for recorded whitespace-bearing strings → `actor_full_identity` already strips each projected part; add a regression assertion if the reviewer finds a gap.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **Parallelization**: none.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red parser tests for the three issue rows | WP01 | P1 | No |
| T002 | Red CLI refusal tests for the three explicit paths | WP01 | P1 | No |
| T003 | Parser hardening in models.py | WP01 | P1 | No |
| T004 | Targeted test surface + mypy evidence | WP01 | P1 | No |
| T005 | Changelog entry | WP01 | P1 | No |
