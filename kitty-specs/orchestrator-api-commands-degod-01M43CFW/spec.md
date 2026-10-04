# Mission Specification: Split the orchestrator-api commands god-module

**Mission Branch**: `claude/funny-cannon-2kiwuz` (single_branch, commit-to-target)
**Created**: 2026-10-04
**Status**: Draft
**Input**: GitHub issue #5628, "Investigate & refactor: orchestrator_api/commands.py god-module (4,175 LOC)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - External orchestrators see no change (Priority: P1)

An external orchestrator drives Spec Kitty through `spec-kitty orchestrator-api <verb> --json`. After the refactor, every verb accepts the same options, prints the same `--help`, appears in the same order, and returns the same JSON envelope for the same inputs.

**Independent Test**: Snapshot `--help` for the group and for every subcommand before and after the split; the snapshots are byte-identical. The existing contract and integration suites pass unchanged in assertion content.

**Acceptance Scenarios**:

1. **Given** the pre-refactor help snapshot, **When** the help snapshot is regenerated after the split, **Then** the two files are byte-identical.
2. **Given** the orchestrator-api contract and integration suites, **When** they run after the split, **Then** they pass. The only edits are test patch targets that move with the code they patch.

### User Story 2 - Maintainers find a verb by concern (Priority: P2)

A maintainer changing the consolidate path, a decision verb or a design-phase delegate opens one cohesive module of a few hundred lines, not a 4,191-line file.

**Independent Test**: `commands.py` holds only the Typer app, the JSON error group, the command table and the two readers left to #5532. Each concern lives in its own module.

### Edge Cases

- Tests that monkeypatch `commands._get_main_repo_root` (77 sites) or `commands._build_merge_preflight` / `_execute_lane_merge` must keep their seam: the patched name has to be the one the handler looks up at call time.
- Architectural gates that name `orchestrator_api/commands.py` by path (destructive-op routing, terminology allow-list, write-side rederivation) must follow the code to its new home rather than go vacuous.
- Typer registers commands in decoration order; moving handlers must not reorder `--help`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Per-concern modules | As a maintainer, I want the subcommands grouped into per-concern modules (workspace and transitions, acceptance and consolidation, design-phase delegates, decisions, design status) so that each concern can be read and changed alone. | High | Open | build | no |
| FR-002 | Façade keeps the contract | As an orchestrator author, I want `commands.py` to stay the single `app` and register every verb in today's order so that the contract is unchanged. | High | Open | build | no |
| FR-003 | Shared helpers in one place | As a maintainer, I want envelope, failure and mission/WP resolution helpers in one shared module so that no concern module redefines them. | Medium | Open | build | no |
| FR-004 | Leave #5532 readers alone | As the #5532 implementer, I want `mission-state` and `list-ready` left byte-for-byte as they are so that they are refactored once. | High | Open | build | yes |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Contract identity | Help snapshot of the group and all 21 subcommands is byte-identical before and after. | Compatibility | High | Open |
| NFR-002 | Quality gates | ruff check, ruff format and mypy are clean on all touched files; no new suppressions. | Maintainability | High | Open |
| NFR-003 | Module size | No resulting orchestrator_api module exceeds 1,200 LOC. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Pure move | Function bodies move verbatim except for import and module-qualified seam references. No behaviour change. | Technical | High | Open |
| C-002 | No size gate | The issue asks for engineering discipline, not a new LOC gate; none is added. | Technical | Medium | Open |
| C-003 | Gates follow the code | Path-scoped architectural gates are re-pointed to the new modules and stay non-vacuous. | Technical | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `commands.py` drops from 4,191 LOC to under 800.
- **SC-002**: The orchestrator-api blast-radius suite (every test file that names `orchestrator_api`, plus `tests/orchestrator_api`) passes with the same count as the baseline (1197 passed, 2 skipped, 2 xfailed).
- **SC-003**: The help snapshot diff is empty.
