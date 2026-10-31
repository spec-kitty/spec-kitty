# Tasks: Plugin-owned surfaces report truthfully

**Mission**: `plugin-owned-surfaces-report-truthfully-01M68JAV` · **Branch**: `issue-6493-plugin-owned-surfaces-report-truthfully`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Issue**: #6493

One work package: the whole change is a read-path reporting change in four CLI
modules behind one predicate, so a multi-WP decomposition would be artificial
sequencing of a single commit-sized edit. Red-first is inside the WP (T001 before
T002–T006).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first CLI tests for the six stated-empty reports + legacy shape + #4425 ratchet | WP01 | |
| T002 | `no_cli_managed_agents` predicate in `core/agent_config.py` | WP01 | |
| T003 | `agent config list`: both empty shapes truthful | WP01 | |
| T004 | `init`: stated-empty re-run claims no verification; `--ai` respects the stated list | WP01 | |
| T005 | `doctor skills` / `tool-surfaces` / `command-files`: no vacuous "all healthy" | WP01 | |
| T006 | Targeted test sweep, ruff/mypy, changelog + docs | WP01 | |

## Work Package WP01: Truthful reports for the stated-empty project shape

**Prompt**: `tasks/WP01-truthful-stated-empty-reports.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003
**Dependencies**: none

### Included Subtasks

T001 Red-first CLI tests for the six stated-empty reports + legacy shape + #4425 ratchet (WP01)
T002 `no_cli_managed_agents` predicate in `core/agent_config.py` (WP01)
T003 `agent config list`: both empty shapes truthful (WP01)
T004 `init`: stated-empty re-run claims no verification; `--ai` respects the stated list (WP01)
T005 `doctor skills` / `tool-surfaces` / `command-files`: no vacuous "all healthy" (WP01)
T006 Targeted test sweep, ruff/mypy, changelog + docs (WP01)
