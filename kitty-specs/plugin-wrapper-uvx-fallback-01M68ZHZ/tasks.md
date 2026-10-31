---
description: "Work package task list for the plugin wrapper uvx fallback fix"
---

# Work Packages: Fix the plugin bundle wrapper's uvx fallback

**Inputs**: Design documents from `kitty-specs/plugin-wrapper-uvx-fallback-01M68ZHZ/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required — the mission spec demands a red-first test through the generated
wrapper (SC-001, SC-003, SC-005) before the template change lands.

**Organization**: Two work packages, split along the only ownership boundary that
matters here: source + tests are a `code_change` surface; the install how-to and the
changelog are a `planning_artifact` surface.

**Prompt Files**: `kitty-specs/plugin-wrapper-uvx-fallback-01M68ZHZ/tasks/WP01-*.md`,
`.../WP02-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/`, `tests/` — this mission follows that layout.

---

## Work Package WP01: Wrapper fallback fix and its tests (Priority: P1) 🎯 MVP

**Goal**: Both generated wrappers invoke a CLI that exists, prefer the pinned build's
series over an incompatible PATH binary, retry the uvx resolution inside that series,
and print the uv/pipx remedy.
**Independent Test**: `uv run pytest tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py -q`
runs the generated bash wrapper under a hermetic PATH and asserts the `--from` argv, the
series gate and the remedy text.
**Prompt**: `/tasks/WP01-wrapper-fallback-and-tests.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, NFR-004, C-002, C-003, SC-001, SC-002, SC-003, SC-004, SC-005

### Included Subtasks

T001 Add the pure version→series helper and its range spec to `claude_wrapper.py`
T002 Rewrite the POSIX template: series-gated PATH probe, `uvx --from` pinned, series-range retry, uv/pipx remedy
T003 Rewrite the CMD template with the same resolution order, quoting the range so `<`/`>` are not redirection, keeping the #623 exit-code invariant
T004 Rewrite the wrapper tests red-first: failing `--from` argv assertion, series in/out gate, retry, remedy text, `--from` content pins for both wrappers

### Implementation Notes

- Red first: land T004's failing assertions against the current template, run them, and
  show the red before touching T001–T003.
- The series helper is the single authority: the templates receive the pinned spec and
  the range spec from it; do not re-derive `<major>.<minor>` inside a template.
- Keep `wrapper_bash_content` / `wrapper_cmd_content` pure and offline (NFR-004).
- Do not add a `spec-kitty-cli` console script (C-002).

### Parallel Opportunities

- T001–T003 touch one file and must be sequential; T004 can be drafted while T001 lands.

### Dependencies

- None (root).

### Risks & Mitigations

- `set -euo pipefail` plus a failed `--version` probe can abort the script → the probe
  sits in an `if`/`|| true` context and an unparseable version means "no compatible CLI".
- CMD `>`/`<` are redirection operators → the range requirement must be quoted.
- A test that relies on the developer's real `uvx` or on network → use stub executables
  in a temp `PATH` (existing test already models this).

---

## Work Package WP02: Operator docs and changelog (Priority: P2)

**Goal**: The install how-to and the `[Unreleased]` changelog describe the resolution
order that actually ships.
**Independent Test**: The how-to's "How the runtime wrapper works" steps match the
generated templates verbatim in behaviour, and the changelog entry is present under
`[Unreleased]` with the `(#6476)` reference.
**Prompt**: `/tasks/WP02-operator-docs-and-changelog.md`
**Requirement Refs**: FR-006, FR-007, SC-004

### Included Subtasks

T005 Rewrite the wrapper/troubleshooting sections of `install-claude-code-plugin.md`
T006 Add the `[Unreleased]` changelog entry for #6476

### Implementation Notes

- Document the three-step resolution order: PATH CLI inside the supported series →
  `uvx --from` pinned → `uvx --from` series range → error with uv/pipx remedy.
- Changelog: bold impact-first lead with `(#6476)`, before/after, under 1,200 characters.

### Parallel Opportunities

- T005 and T006 are independent files and may proceed in parallel.

### Dependencies

- Depends on WP01 (documents the shipped behaviour).

### Risks & Mitigations

- Docs index drift → keep headings stable; run the docs freshness check for the touched
  surface only.
- Over-long changelog entry → keep under 1,200 characters.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: T005/T006 in parallel; WP01 is the root.
- **MVP Scope**: WP01 (the fix and its tests).

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| NFR-004 | WP01 |
| C-002 | WP01 |
| C-003 | WP01, WP02 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01, WP02 |
| SC-005 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Version→series helper and range spec | WP01 | P1 | No |
| T002 | POSIX template rewrite | WP01 | P1 | No |
| T003 | CMD template rewrite | WP01 | P1 | No |
| T004 | Red-first wrapper tests | WP01 | P1 | Yes |
| T005 | Install how-to resolution order | WP02 | P2 | Yes |
| T006 | Changelog `[Unreleased]` entry | WP02 | P2 | Yes |
