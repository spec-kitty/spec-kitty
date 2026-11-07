# Implementation Plan: upgrade — three migrations read the operator's home directly

**Branch**: `issue-6954-upgrade-empty-home-command-migrations` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-empty-home-command-migrations-01M6EJQR/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

## Summary

Issue #6954 asks for one measurement, not a refactor: converge a project, re-run
`upgrade --project` under an empty `SPEC_KITTY_HOME`, and assert no tracked change and no
auto-commit — applied to the three migrations that read the home directly instead of
through `uses_centralized_runtime()`. Grounding (see `research.md`) shows two of the three
(`m_2_1_3`, `m_2_1_4`) reach the home only as a last-resort template fallback and are not
home-dependent in observable behaviour, while `m_3_1_2` (`_SafeGlobalizeCommandsBase`)
genuinely is: it decides `keep` vs `remove` from `~/.kittify/missions` and from
`Path.home()/<agent_root>/<subdir>`.

The technical approach is therefore: (1) a regression module at the real `upgrade` entry
point in the ledger shape that actually re-evaluates the three (`skipped` records), with a
home-equivalence assertion and same-fixture positive controls; (2) a small fix in
`_SafeGlobalizeCommandsBase` that classifies from the project's own `metadata.yaml` stamp
first and consults the home only for projects with no readable stamp or one below the
migration's target version; (3) canonical `get_global_command_dir()` for the
exact-global-file check where the home is still consulted.

## Technical Context

**Language/Version**: Python 3.11 (repo floor; `.python-version` pins 3.11)
**Primary Dependencies**: `typer` (CLI entry point), `packaging.version` (stamp compare),
`pytest` + `typer.testing.CliRunner` (test harness)
**Storage**: `.kittify/metadata.yaml` and `.kittify/migration-ledger.jsonl` inside the
project under test; git for the auto-commit assertion
**Testing**: `pytest`, `tests/upgrade/` shard; real `upgrade` command via a
`typer.Typer` test app (mirrors `tests/upgrade/test_upgrade_integration.py`), real `git`
in `tmp_path`
**Target Platform**: POSIX and Windows; no platform-specific branch is added
**Project Type**: single Python project (CLI)
**Performance Goals**: the new test module stays under 180 s on one shard (NFR-002); no
session-scoped fixtures are added
**Constraints**: must not depend on unmerged PR #6946 (C-001); no change to
`compat.py`, the ledger, or the migration framework (C-002)
**Scale/Scope**: 1 source module touched (`m_3_1_2_globalize_commands.py`), 1 new test
module, 1 possibly-extended existing test module, 1 changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
| --- | --- | --- |
| Single canonical authority | pass | the fix removes a second derivation of the global command directory and routes it through `runtime/agent_commands.get_global_command_dir()`; the stamp is read through the existing `ProjectMetadata` owner |
| ATDD / red-first (DIRECTIVE_034) | pass | the classification test and the end-to-end removal test are authored first and must fail on the current code (`keep` under an empty home) before the fix |
| DDD / tiered rigour | pass | one bounded context (`upgrade` migrations); a contained change to one base class |
| Terminology canon | pass | "migration", "project stamp", "converged", "operator home" used as the repo's `docs/context/` defines them |
| User customisation preservation | pass | the `hold` rule for files without a version marker is unchanged and is re-asserted by a test (NFR-003) |
| Changelog fragments (C-003) | pass | one `docs/changelog/unreleased/<pr>.fixed.md` fragment |
| No full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION) | pass | only `tests/upgrade/` targets plus the docs freshness check |

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-empty-home-command-migrations-01M6EJQR/
├── plan.md              # This file
├── spec.md              # Mission specification
├── research.md          # Phase 0 output (discovery + measured evidence)
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks - NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/upgrade/migrations/
├── m_2_1_3_restore_prompt_commands.py   # pin only — no behaviour change
├── m_2_1_4_enforce_command_file_state.py# pin only — no behaviour change
└── m_3_1_2_globalize_commands.py        # the fix: stamp-first classification

src/specify_cli/runtime/agent_commands.py # canonical get_global_command_dir (read only)

tests/upgrade/
├── test_empty_home_command_migrations.py    # NEW: entry-point regression + equivalence
├── migrations/                              # existing per-migration tests (may be extended)
└── test_upgrade_integration.py              # harness shape this module copies

docs/changelog/unreleased/<pr>.fixed.md      # NEW fragment
```

**Structure Decision**: single project. The behaviour change is confined to
`m_3_1_2_globalize_commands.py`; the other two migrations are pinned by tests rather than
edited, because grounding showed their home access is a last-resort fallback that a
working install never reaches.

## Complexity Tracking

*No charter violations.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — Measurement at the real entry point

- **Purpose**: produce the regression the issue asks for, in the ledger shape that
  actually re-evaluates the three migrations, and prove the probe can see a change.
- **Relevant requirements**: FR-003, FR-004, NFR-001, NFR-002, SC-001, SC-002
- **Affected surfaces**: `tests/upgrade/test_empty_home_command_migrations.py`,
  `tests/upgrade/test_upgrade_integration.py` (harness pattern, read only)
- **Sequencing/depends-on**: none
- **Risks**: `Path.home()` is owned by the test harness's home isolation, so the module
  must not pin it; the equivalence half must therefore compare *tracked state*, not
  "global file exists". The `skipped`-record seeding must not silently settle the
  migrations it claims to re-evaluate (assert the ledger result after the run).

### IC-02 — Stamp-first classification in the globalization migration

- **Purpose**: make `keep` vs `remove` a function of the project's own stamp for stamped
  projects, keeping the historical home checks for unstamped/legacy shapes.
- **Relevant requirements**: FR-001, FR-002, FR-006, SC-001, SC-003
- **Affected surfaces**: `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py`,
  `src/specify_cli/runtime/agent_commands.py` (`get_global_command_dir`, read only),
  `src/specify_cli/upgrade/metadata.py` (`ProjectMetadata`, read only)
- **Sequencing/depends-on**: IC-01 (the red tests come first)
- **Risks**: the base class is shared by `3.1.2_globalize_commands` and
  `3.2.0a4_safe_globalize_commands`; the stamp threshold must come from
  `self.target_version`, not a constant. An unparseable or numeric stamp must fall back to
  the legacy answer rather than raising (`InvalidVersion` and `TypeError`).

### IC-03 — Template-source pin for the two command-file migrations

- **Purpose**: pin that `_get_runtime_command_templates_dir()` resolves the packaged
  doctrine tree first and is unaffected by an empty home, in both migrations.
- **Relevant requirements**: FR-005, SC-003, SC-004
- **Affected surfaces**: `tests/upgrade/test_empty_home_command_migrations.py` (unit
  section), `m_2_1_3_restore_prompt_commands.py`,
  `m_2_1_4_enforce_command_file_state.py` (read only)
- **Sequencing/depends-on**: none
- **Risks**: the resolver's first tier is `MissionTemplateRepository.default_missions_root()`;
  the assertion must be "inside the installed package / doctrine tree, and stable across
  both homes", not a hard-coded absolute path.

### IC-04 — Changelog and PR surface

- **Purpose**: a user-facing fragment in the required shape, and a PR body whose
  `## Deferred` names the #6946 ordering dependency.
- **Relevant requirements**: C-003, NFR-003
- **Affected surfaces**: `docs/changelog/unreleased/<pr>.fixed.md`, PR body
- **Sequencing/depends-on**: IC-01..IC-03 (the PR number is needed for the filename)
- **Risks**: `check_changelog_style` rejects the retired `[Unreleased]` entry shape; the
  fragment must not touch `docs/changelog/CHANGELOG.md`.
