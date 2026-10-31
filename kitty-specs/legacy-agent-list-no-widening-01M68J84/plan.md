# Implementation Plan: A legacy agent list resolves to the agents the project has

**Branch**: `issue-6501-legacy-agent-list-no-widening` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/legacy-agent-list-no-widening-01M68J84/spec.md`

## Summary

`get_agent_dirs_for_project()` reads `.kittify/config.yaml` through `load_agent_config()` and, when
the config states no `available` list (`explicit_agent_list` is `False`), returns the whole
`AGENT_DIRS` registry. Every migration, `doctor` surface audit, shim generator and `.gitignore`
repair that asks "which agents are in play?" therefore acts on all 12 slash-command agents, even in a
project that has exactly one. The fix narrows that one branch to the **observed set**: the
`AGENT_DIRS` entries whose project surface directory (`<agent_root>/<subdir>`, e.g.
`.claude/commands`) already exists. The read logs one warning naming `.kittify/config.yaml`, the
`agents.available` key and the remedy, so "no list" is never silently read as "every agent". Stated
lists — `[claude]` and `[]` — and the corrupt-config refusal keep their current behaviour untouched.

## Technical Context

**Language/Version**: Python 3.11 (`src/specify_cli`), Typer CLI
**Primary Dependencies**: `ruamel.yaml`, `pytest`; no new dependency
**Storage**: `.kittify/config.yaml` (YAML); read-only for this mission
**Testing**: `pytest` (`tests/agent/`), plus the existing doctor and migration tests that consume the
helper; `uv run pytest <paths>` per work package — never a full suite (NO_FULL_HEAVY_SUITES_IN_MISSION)
**Target Platform**: Linux/macOS/Windows CLIs, any project directory
**Project Type**: single Python package with a Typer CLI
**Performance Goals**: N/A — one directory-existence probe per registry entry, on a path that already
opens and parses a YAML file
**Constraints**: no filesystem writes on the read path; no `$HOME` / user-global probe (NFR-001);
warning is log-only and bounded to one line per read (NFR-002); no exception on the legacy branch
(C-001)
**Scale/Scope**: ~40 changed lines in one module, one doc page, one changelog entry, tests in the two
suites that already own the contract

## Charter Check

*GATE: passed for planning; re-checked after design.*

- **Single canonical authority** (C-002): the observed set is a *filter over* `AGENT_DIRS` /
  `AGENT_DIR_TO_KEY`; no parallel agent registry is introduced.
- **ATDD-first / red-first**: the two red tests (no config file; config without an `agents` section)
  are written against the pre-existing entry point `get_agent_dirs_for_project()` and fail on `main`
  before the module changes.
- **Locality of change** (`DIRECTIVE_024`, `change-apply-smallest-viable-diff`): one module's legacy
  branch, plus the two doc surfaces that describe it. `load_agent_config`, `explicit_agent_list`,
  `save_agent_config` and `ignored_agent_keys` semantics are not restructured.
- **No weakened gates**: no test is skipped or xfailed; the existing fallback tests are rewritten to
  the new contract, not deleted.
- **ADR alignment**: `docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md` requires legacy
  projects not to break on upgrade, which is why the read narrows instead of refusing (see
  `design-decisions.md`).

## Project Structure

### Documentation (this mission)

```
kitty-specs/legacy-agent-list-no-widening-01M68J84/
├── plan.md              # This file
├── spec.md              # Mission specification
├── issue-matrix.md      # #6501 claim + terminal verdict
├── tasks/               # Work packages
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/
├── agent_utils/
│   ├── directories.py       # the fix: legacy branch resolves the observed set + warning
│   └── ignore_entries.py    # docstring only: why .gitignore repair stays broad
└── core/
    └── agent_config.py      # UNCHANGED (explicit_agent_list is the input, not the target)

tests/
└── agent/
    └── test_agent_config_migration.py   # red-first tests for both legacy shapes

docs/
├── api/configuration.md     # documented default (was "the full slash-command agent set")
└── changelog/CHANGELOG.md   # [Unreleased] entry, impact-first, (#6501)
```

**Structure Decision**: single-package Python CLI; the change stays inside the module that owns the
agent-directory registry and its existing tests.

## Complexity Tracking

*No charter violations: the change removes a branch rather than adding an abstraction.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — The observed-set resolution and its warning

- **Purpose**: Replace the registry-wide fallback with a filter over the agents the project already
  has, and say so in the log.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002
- **Affected surfaces**: `src/specify_cli/agent_utils/directories.py`
- **Sequencing/depends-on**: none
- **Risks**: a second surface definition (root vs `root/subdir`) would drift from
  `AGENT_DIRS`; the probe must stay project-local so tests and upgrades are deterministic; the
  warning must be `logger.warning`, never `print` (the CLI owns stdout), and must not fire when a
  list is stated.

### IC-02 — The red-first proof and the consumer guarantees

- **Purpose**: Pin both legacy shapes and the unchanged stated-list behaviour at the entry point the
  migrations and `doctor` use, so a later "consistency" change cannot re-widen it.
- **Relevant requirements**: FR-001, FR-003, FR-004, SC-001, SC-003
- **Affected surfaces**: `tests/agent/test_agent_config_migration.py`,
  `tests/cli/commands/test_doctor_slash_commands.py` (regression guard only if it needs no change)
- **Sequencing/depends-on**: IC-01 (the tests are written first and fail before it lands)
- **Risks**: the suite owns both the #6494 empty-list rule and this legacy rule; the new tests must
  not weaken the empty-list or corrupt-config assertions while replacing the two `list(AGENT_DIRS)`
  expectations.

### IC-03 — The documented default

- **Purpose**: Make the documentation state the rule the code now follows, so the contract has one
  description.
- **Relevant requirements**: FR-005, FR-006, SC-004
- **Affected surfaces**: `docs/api/configuration.md`, `docs/changelog/CHANGELOG.md`,
  docstring of `ignored_agent_keys` (asymmetry note)
- **Sequencing/depends-on**: IC-01 (documents the shipped behaviour)
- **Risks**: the docs index freshness check reads a globally cached asset surface; regenerate only
  the touched page's entry and verify with `check_docs_freshness --ci`.
