# Implementation Plan: Skill surface and upgrade integrity

**Branch**: `ccr-11788f1f-qu75jg` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/skill-surface-upgrade-integrity-01M482Z3/spec.md`

## Summary

Three defects, one invariant ("never report success over absent work"):

1. `coalesce_effects` treats identical directory creates from different owners as a
   conflict, so `upgrade` aborts when a configured tool folder is absent (#4275).
2. A failed upgrade leaves `metadata.yaml` stamped with the target version (#4275).
3. `doctor skills` has no `missing` pack-skill finding, `--fix` never projects pack
   skills, and nothing fails when no configured tool folder exists (#5801 + operator
   addition, DM `01M482ZZ73BDZYM0K2R1CD0SE3`).

Approach: widen the coalescer's merge rule to the structurally identical directory-create
case (one authority, managed_skills delegates); snapshot-and-restore the metadata version
fields around the whole upgrade (extending the existing #3334 restore pattern); add a
`missing` kind computed from the existing in-force resolver plus a no-tool-folder finding,
and wire `--fix` to `project_pack_skills`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing; no dependency change)
**Storage**: files — `.kittify/metadata.yaml`, `.kittify/skills-manifest.json`, tool skill roots
**Testing**: pytest; red-first `@pytest.mark.regression` repro per FR (ADR `2026-07-17-1`), converted to focused unit tests at WP close; mypy --strict, ruff, ruff format
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single (`src/specify_cli/`)
**Performance Goals**: doctor and upgrade stay within the charter's <2 s typical-project budget (no new full-catalog scans beyond the one the drift check already does)
**Constraints**: complexity ≤15 per function; diff coverage ≥90%; user-owned files never overwritten (C-002); migrations keep skipping absent agent dirs (C-005)
**Scale/Scope**: ~6 source modules, 3 concerns

No dependency is added, upgraded or removed: the supply-chain section does not apply.

## Charter Check

| Gate | Status |
|------|--------|
| Single canonical authority | PASS — merge rule moves into `coalesce_effects`; `managed_skills` delegates (C-001). `missing` predicate lives in `pack_skill_drift`, which already owns pack-skill findings; verifier untouched (C-003, follow-up). |
| ATDD / red-first | PASS — every FR gets a failing repro through the pre-existing entry point (`upgrade`, `doctor skills`) before the fix. |
| User customization preservation | PASS — `--fix` uses `project_pack_skills`, which honours manifest ownership; drifted copies stay refuse-only. |
| Terminology canon | PASS — Mission, no `feature*` names introduced. |
| No full heavy suites in mission | PASS — targeted tests per concern (listed in each IC). |
| Agent-config single source (ADR #6) | PASS — tool set from `get_agent_dirs_for_project`; upgrade's surface finalizer (not a migration) recreates configured folders. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/skill-surface-upgrade-integrity-01M482Z3/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/doctor-skills-json.md
└── tasks.md (next phase)
```

### Source Code (repository root)

```
src/specify_cli/
├── tool_surface/operations.py              # coalesce_effects merge rule + diagnostic
├── tool_surface/providers/managed_skills.py # delegate local merge
├── upgrade/runner.py                       # version writers (snapshot participants)
├── cli/commands/upgrade.py                 # snapshot/restore around runner + finalizer
├── skills/pack_skill_drift.py              # KIND_MISSING
└── cli/commands/_command_surface_doctor.py # --fix projection, no-tool-folder finding
docs/development/how-to/create-a-pack-skill.md
docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md (amendment)
docs/changelog/CHANGELOG.md
tests/specify_cli/tool_surface/, tests/upgrade/, tests/specify_cli/skills/, tests/specify_cli/cli/commands/
```

**Structure Decision**: single project; edits stay in the listed modules.

## Implementation Concern Map

### IC-01 — Coalesce identical directory creates

- **Purpose**: Let upgrade plan a missing tool folder once, while real conflicts still fail with an actionable message.
- **Relevant requirements**: FR-001, FR-002, NFR-001, C-001
- **Affected surfaces**: `tool_surface/operations.py:176-189`, `tool_surface/providers/managed_skills.py:125-140`, `tool_surface/providers/agent_profiles.py:766-775` (read-only)
- **Sequencing/depends-on**: none
- **Risks**: Masking real conflicts — merge only when `action=create`, `before` absent, same `phase` and identical `after` (kind+mode); negative tests for mode/phase/content divergence. Fixtures: (a) claude profiles+commands+skills with `.claude/` absent, (b) two Agent Skills tools on `.agents/skills`.

### IC-02 — Restore recorded version on failed upgrade

- **Purpose**: A failed upgrade leaves `version`, `last_upgraded_at` and schema version as they were.
- **Relevant requirements**: FR-003, C-004, NFR-001
- **Affected surfaces**: `cli/commands/upgrade.py` (`_stamp_no_migrations_metadata` ~711-728, runner call ~1855, `finalize_upgrade` ~1884-1911), `upgrade/runner.py` (~180, `_finalize_main_metadata` ~737-742), existing #3334 restore helper
- **Sequencing/depends-on**: IC-01 (same upgrade flow; serial to avoid conflicts)
- **Risks**: Per-migration `record_migration` writes stay (they record what ran); only the version trio is restored. Keep the #1158 schema-stamp repair reachable.

### IC-03 — Doctor reports and repairs missing pack skills

- **Purpose**: `doctor skills` never reports healthy over absent pack skills or an absent tool surface; `--fix` installs.
- **Relevant requirements**: FR-004, FR-005, FR-006, FR-007, C-002, C-005, C-006
- **Affected surfaces**: `skills/pack_skill_drift.py`, `cli/commands/_command_surface_doctor.py` (~660-700), `skills/installer.py:1282` (call only), docs/ADR/CHANGELOG; tests pinning the JSON payload (`test_doctor_skills.py`, `test_doctor_cli_surface_golden.py`, `tests/cli_gate/test_doctor_modes.py`, `test_pack_skill_drift.py`)
- **Sequencing/depends-on**: none (parallel to IC-01/IC-02)
- **Risks**: false `missing` for tools that do not accept skill files (reuse installer's installable-agent filter); `--fix` retiring orphaned copies must be reported; golden updates must be additive only.
