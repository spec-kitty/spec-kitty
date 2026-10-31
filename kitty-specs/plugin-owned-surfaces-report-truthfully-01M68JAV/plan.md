# Implementation Plan: Plugin-owned surfaces report truthfully

**Branch**: `issue-6493-plugin-owned-surfaces-report-truthfully` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/spec.md`

## Summary

One predicate — "this project states that Spec Kitty manages no agent surfaces"
(`agents.available: []`, #6494) — replaces the three ad-hoc emptiness checks in
`init`, `agent config list` and `doctor`, and each surface reports the state it can
actually see: no CLI-managed agents (stated empty), every agent (legacy absent
list), or the stated list. No ownership record, plugin probe or schema change is
added; that stays with #6472.

## Technical Context

**Language/Version**: Python 3.11 (repo floor), `from __future__ import annotations` style
**Primary Dependencies**: Typer + Rich (CLI), ruamel.yaml (config read/write), pytest
**Storage**: `.kittify/config.yaml` (project config, read through `specify_cli.core.agent_config`)
**Testing**: pytest, targeted files only (charter: no full heavy suites in mission work)
**Target Platform**: CLI on Linux/macOS/Windows
**Project Type**: single package (`src/specify_cli`)
**Performance Goals**: no new I/O; the predicate is a field read on the already-loaded `AgentConfig`
**Constraints**: existing human strings and JSON envelopes are frozen surfaces (NFR-002)
**Scale/Scope**: 4 source files, 3 commands, 1 predicate, ~6 test files

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the predicate is defined once in
  `core/agent_config.py` next to the `explicit_agent_list` field it reads; every
  caller imports it (C-002). No second YAML parse.
- **Single canonical authority (ownership)** — this mission deliberately adds no
  ownership record; #6472 owns it (C-001).
- **ATDD-first / red-first** — every changed message has a test that fails on
  `35318ef51c` through the real CLI command (`CliRunner` on the pre-existing
  `init`, `agent config list`, `doctor` entry points), not through a helper.
- **User Customization Preservation** — no mutating flow changes: `init --ai` in the
  stated-empty shape writes nothing (SC-002 asserts the tree is unchanged), and
  `agent config add` keeps its behaviour.
- **Non-vacuity** — each "does not say X" assertion is paired on the same fixture
  with a positive control that the command still says X when it should (FR-007 for
  the missing-skills path, FR-002 for the stated-list path).
- **`NO_FULL_HEAVY_SUITES_IN_MISSION`** — targeted test files only.

No charter violations, so Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/plugin-owned-surfaces-report-truthfully-01M68JAV/
├── spec.md
├── plan.md              # this file
├── tasks.md             # /spec-kitty.tasks output
├── tasks/
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/
├── core/agent_config.py                    # + no_cli_managed_agents(config) predicate
├── cli/commands/init.py                    # - _validated_agent_selection, - the Already-Initialized panel
├── cli/commands/agent/config.py            # - list_agents: both empty shapes truthfully
└── cli/commands/
    ├── _command_surface_doctor.py          # - run_skills_audit / run_tool_surfaces_audit wording
    └── doctor.py                           # (shells unchanged; command-files path in _command_surface_doctor)

tests/
├── agent/cli/commands/test_agent_config.py            # agent config list wording
├── specify_cli/cli/commands/test_init_*.py            # init re-run + --ai wording (find owner)
└── specify_cli/cli/commands/test_doctor_slash_commands.py / test_doctor_skills*.py
```

**Structure Decision**: single package; the change is a read-path reporting change
inside the existing CLI modules, with no new module. The predicate lives with the
`AgentConfig` dataclass so the config contract keeps one owner.

## Implementation Concern Map

- **Config predicate (FR-001)** — add `no_cli_managed_agents(config: AgentConfig) -> bool`
  to `core/agent_config.py`; docstring names #6494 (stated empty) vs #6501 (absent
  list) so the two shapes cannot be conflated. Export through `__all__`.
- **`agent config list` wording (FR-002, FR-006)** — one branch per shape:
  stated-empty → "no CLI-managed agents", legacy → "no stated agent list; every
  supported agent is available"; the stated-list path is unchanged.
- **`init` re-run (FR-003, FR-004, FR-007)** — `_validated_agent_selection` grows the
  stated-empty case (the stated list wins over `--ai`, no raise);
  `_check_initialized_command_skills` keeps its #4425 gap diagnosis for listed
  agents; the Already-Initialized panel gets a third body for the stated-empty
  shape that claims no verification.
- **Doctor wording (FR-005, NFR-002)** — human output only; `skills` and
  `tool-surfaces` and `command-files` each print a "nothing CLI-managed to check"
  line in the stated-empty shape. JSON payloads unchanged (asserted by key set).
- **Tests (FR-001..FR-007, SC-001..SC-004)** — red-first through the CLI runners on
  a fixture project whose `.kittify/config.yaml` is written by the test.

## Risks

| Risk | Mitigation |
| --- | --- |
| Swallowing the #4425 missing-skills diagnosis | FR-007 ratchet test on the same fixture with `available: [claude]`; the new branch keys off `explicit_agent_list and not available`, which that fixture cannot satisfy. |
| Frozen-string churn in unrelated tests | grep every changed literal across `tests/` before editing; update only assertions about the changed wording. |
| JSON envelope drift | `doctor skills --json` key-set test; `tool-surfaces`/`command-files` touched on the human path only. |
| Docs index churn from a new changelog entry | changelog only (no new ADR/doc page), so no `docs_index --write` run; verify with `check_docs_freshness --ci`. |
