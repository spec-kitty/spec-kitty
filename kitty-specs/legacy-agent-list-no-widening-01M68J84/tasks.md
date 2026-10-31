# Tasks: A legacy agent list resolves to the agents the project has

**Mission**: `legacy-agent-list-no-widening-01M68J84` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-6501-legacy-agent-list-no-widening`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: no `config.yaml` + one agent surface returns only that agent (with a two-agent control) | WP01 | |
| T002 | Red-first: config with no `agents` section, and `agents:` with no `available`, return only the present surface | WP01 | |
| T003 | `get_agent_dirs_for_project` legacy branch resolves the observed set + one-line warning naming file, key and remedy | WP01 | |
| T004 | Green + consumer proof: agent suites, doctor audit, migration suite, manual temp-project check | WP01 | |
| T005 | `docs/api/configuration.md`: documented default, warning, remedy, unchanged stated-list rule | WP02 | [P] |
| T006 | `ignored_agent_keys` docstring: record the deliberate broad-ignore asymmetry | WP02 | [P] |
| T007 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry with `(#6501)` | WP02 | [P] |

## Phase 1 — Story 1/2 (P1)

### WP01 — Legacy agent list resolves to the observed set ([tasks/WP01-legacy-agent-list-observed-set.md](tasks/WP01-legacy-agent-list-observed-set.md))

- **Goal**: a config that states no `available` list yields only the agent surfaces the project already has, with a warning that names the file, the key and the remedy; stated lists and the corrupt-config refusal are untouched.
- **Priority**: P1 (MVP)
- **Independent test**: a temp project with `.kittify/` (no `config.yaml`) and `.claude/commands/` returns exactly `[(".claude", "commands")]`, and a second surface joins it only when created; `available: []` still returns `[]`.
- **Requirements**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003
- **Included subtasks**:

T001 Red-first no-config shape (WP01)
T002 Red-first no-agents-section shape (WP01)
T003 The fix (WP01)
T004 Green + consumer proof (WP01)

- **Sketch**: red tests on the existing entry point → narrow the one branch → green, then prove the `doctor` audit and the migration suite see the narrowed list.
- **Dependencies**: none
- **Risks**: replacing two tests that pin the widening must not weaken the #6494 empty-list or corrupt-config assertions; keep the probe project-local so no test reads `$HOME`.

## Phase 2 — Story 3 (P2)

### WP02 — Document the documented default and record the change ([tasks/WP02-documented-default-and-changelog.md](tasks/WP02-documented-default-and-changelog.md))

- **Goal**: the configuration reference and the changelog state the rule the code now follows.
- **Priority**: P2
- **Independent test**: `docs/api/configuration.md` no longer promises "the full slash-command agent set"; `CHANGELOG.md` has one `[Unreleased]` entry citing `(#6501)`; `check_docs_freshness --ci` reports errors=0.
- **Requirements**: FR-005, FR-006, SC-004
- **Included subtasks**:

T005 Configuration reference (WP02)
T006 `ignored_agent_keys` docstring asymmetry note (WP02)
T007 Changelog entry (WP02)

- **Dependencies**: WP01 (documents the shipped behaviour)
- **Risks**: the docs freshness check reads a globally cached asset surface shared with 19 other agents; verify, do not rebuild the whole reference.

## Parallelization

WP02 depends on WP01. Inside WP02, T005–T007 touch separate files and can land in one commit.
