# Tasks: `charter activate` names referenced artifacts that are already in force

**Mission**: `no-cascade-already-in-force-01M66YRN`
**Branch**: `issue-6742-no-cascade-already-in-force`
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)
**Issue**: spec-kitty/spec-kitty#6742

## Overview

Two work packages. WP01 is the behaviour: split the no-cascade report into
already-in-force and not-in-force, print the former as a `Note`, and expose it in
`--json`. WP02 is the operator-facing documentation and the changelog entry.

Red-first is mandatory for WP01: the failing test drives the pre-existing entry point
(`charter_app` through `CliRunner`) and reproduces the issue's own wording before the fix.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first test: absent activation key reports already in force | WP01 | |
| T002 | Split the referenced artifacts into an already-in-force bucket | WP01 | |
| T003 | Render the bucket as a `Note` line and re-gate the hint | WP01 | |
| T004 | Add `referenced_already_in_force` to the `--json` change report | WP01 | |
| T005 | Update the golden-text, JSON and cascade-output tests | WP01 | |
| T006 | Verify no activation behaviour changed (writes, exit codes) | WP01 | |
| T007 | Update the `charter activate` CLI reference | WP02 | [P] |
| T008 | Add the `[Unreleased]` changelog entry | WP02 | [P] |
| T009 | Run the docs freshness check | WP02 | |

---

## Phase 1 — Behaviour (WP01)

### WP01 — Split the no-cascade report into "already in force" and "not in force"

- **Goal**: `charter activate` without `--cascade` names a referenced artifact that is in
  force as in force, keeps the warning for artifacts that are not, and reports both groups
  in `--json`.
- **Priority**: P1 (the only behaviour change in the mission)
- **Independent test**: `charter activate --no-compile mission-type software-dev` on a
  project whose activation keys are absent prints no `was not activated (no --cascade)`
  line for an in-force artifact; the same command on a project with an explicit omitting
  list still prints it.
- **Included subtasks**: T001, T002, T003, T004, T005, T006
- **Prompt**: [tasks/WP01-in-force-split.md](./tasks/WP01-in-force-split.md)
- **Dependencies**: none
- **Risks**: the `--only` narrowing case (verdict must follow the post-write state); a
  fixture that seeds an explicit empty list must keep its warnings, or the split over-reaches.

---

## Phase 2 — Documentation (WP02)

### WP02 — Document the new line and JSON field

- **Goal**: the CLI reference and the changelog describe the already-in-force note and the
  `referenced_already_in_force` key, and the docs freshness gate passes.
- **Priority**: P2
- **Independent test**: `docs/api/charter-commands.md` names the new line and the new key in
  the change-report table, and `check_docs_freshness --ci` reports `errors=0`.
- **Included subtasks**: T007, T008, T009
- **Prompt**: [tasks/WP02-docs-and-changelog.md](./tasks/WP02-docs-and-changelog.md)
- **Dependencies**: WP01 (the documented behaviour must exist first)
- **Risks**: the changelog entry must lead with impact and stay under 1,200 characters;
  the JSON examples in the reference must match the real payload.

---

## Dependency Graph

```
WP01 ──> WP02
```

## MVP

WP01 alone delivers the issue: the report stops claiming a failed activation, and the JSON
partitions truthfully.

## Coverage

| Requirement | Work package |
|-------------|--------------|
| FR-001 … FR-007 | WP01 |
| FR-008 | WP02 |
| NFR-001 … NFR-004 | WP01 |
| C-001, C-003 | WP01 |
| C-002 | WP02 |
| SC-001 … SC-004 | WP01 |
