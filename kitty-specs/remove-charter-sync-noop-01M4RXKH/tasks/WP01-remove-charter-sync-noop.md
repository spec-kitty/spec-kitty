---
work_package_id: WP01
title: Remove the charter sync command surface + references
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-001
- NFR-002
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-5828-remove-charter-sync-noop
merge_target_branch: issue-5828-remove-charter-sync-noop
branch_strategy: Planning artifacts for this mission were generated on issue-5828-remove-charter-sync-noop. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5828-remove-charter-sync-noop unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Removal
history:
- at: '2026-10-12T20:44:00Z'
  actor: system
  action: Prompt authored for the remove-charter-sync-noop mission
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/sync.py
- src/specify_cli/cli/commands/charter/__init__.py
- src/specify_cli/cli/commands/charter/status.py
- src/specify_cli/charter_runtime/preflight/cli.py
- src/specify_cli/charter_runtime/preflight/references_refresh.py
- src/charter/activation/schemas.py
- src/specify_cli/_completion_manifest.json
- docs/api/cli-commands.md
- docs/api/charter-commands.md
- src/charter/offering/skills/spk-charter-governance/SKILL.md
- src/charter/offering/skills/spk-charter-governance/references/charter-command-map.md
- src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md
- src/charter/offering/skills/spk-charter-governance/references/charter-artifact-structure.md
- docs/guides/how-to/governance/synthesize-doctrine.md
- .kittify/charter/charter.md
- tests/agent/cli/commands/test_charter_cli.py
- tests/agent/cli/commands/test_next_preflight.py
- tests/architectural/test_no_retired_subsystems.py
- tests/architectural/test_json_contract_enumeration.py
- tests/architectural/test_remediation_effectiveness.py
- tests/charter/test_retrospective_governance_emit.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5828'
---

# Work Package Prompt: WP01 — Remove the charter sync command surface + references

## Objectives & Success Criteria

- `spec-kitty charter sync` no longer resolves; invoking it returns the standard Typer
  unknown-command error with a non-zero exit (FR-001, FR-002, SC-001).
- The `charter.activation.sync` **module** and every other `charter` subcommand are unchanged
  and green (FR-007, SC-004, C-002).
- The completion manifest, generated CLI reference, and the two command-enumerating
  architectural gates reflect the smaller surface (FR-004, FR-005, SC-002).
- No live `spec-kitty charter sync` reference or recovery hint remains in shipped source;
  only rationale comments explaining *why the sequence is no longer `charter sync`* persist
  (FR-006, SC-003).
- Changelog records the breaking removal (FR-008).
- Zero new suppressions / gate-allowlist widenings (NFR-001); terminology canon preserved
  (NFR-002).

## Context & Constraints

- Follow `plan.md` (IC-01/IC-02/IC-03) and the grounded surface map there.
- **Out of scope**: the `charter.activation.sync` module; the `charter status` STALE verdict
  (open bug #4042 — only neutralize the dangling `charter sync` recommendation); #2992 (mooted
  by removal — flag for closure, do not self-close).
- Edit canonical SOURCES only; regenerate derived artifacts (manifest, CLI reference) from the
  live CLI — never hand-edit the manifest.

## Subtasks & Detailed Guidance

### Subtask T001 — Delete the command module + wiring
Remove `src/specify_cli/cli/commands/charter/sync.py`. In `charter/__init__.py`, drop the
`from specify_cli.cli.commands.charter.sync import sync` import and the `"sync"` entry in
`__all__`. Leave `_collect_charter_sync_status` (a `charter status` collector, not the command).

### Subtask T002 — Red-first unknown-command assertion
Add/convert a test that invokes `charter sync` and asserts the standard unknown-command error +
non-zero exit (the positive control for the removal, replacing the deleted no-op tests).

### Subtask T003 — Remove dedicated tests; move pins
Delete `test_sync_command_success`, `test_sync_command_is_an_explicit_noop`,
`test_sync_command_json_output`, `test_sync_command_missing_charter` from
`tests/agent/cli/commands/test_charter_cli.py`; drop the now-pointless `runner.invoke(app, ["sync"])`
setup lines from `test_status_command_synced` / `test_status_command_json_output`. Update the
`YAML_HEADER` pin in `tests/charter/test_retrospective_governance_emit.py` and the default reason
string in `tests/agent/cli/commands/test_next_preflight.py`.

### Subtask T004 — Regenerate derived artifacts + enumerating gates
`python -m specify_cli.completion --regenerate` → `_completion_manifest.json`.
`scripts/docs/build_cli_reference.py` → `docs/api/cli-commands.md`.
`test_no_retired_subsystems.py`: drop `("charter","sync")` from `_REQUIRED_CLI_PATHS`.
`test_json_contract_enumeration.py`: drop the `"charter sync"` row.
Verify `tests/architectural/test_remediation_effectiveness.py` does not break on removal; adjust
historical references only as needed to keep it honest.

### Subtask T005 — Strip live references/hints
`status.py` stale-hint; `preflight/cli.py` `--auto-refresh` help + `references_refresh.py`
docstring (align to the live `generate`/`upgrade`-based sequence); `schemas.py` `YAML_HEADER`
regen hint → `charter generate`; skill sources under `spk-charter-governance/`;
`docs/guides/how-to/governance/synthesize-doctrine.md`; `docs/api/charter-commands.md`;
`.kittify/charter/charter.md` prose. Keep rationale comments in `preflight/runner.py` /
`freshness/computer.py`.

### Subtask T006 — Changelog
Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`: bold impact-first lead with the
`(#5828)` ref, the removal, and the new unknown-command behaviour.

## Testing (record commands + counts in the PR)
- `make test-fast`
- the charter/CLI dirs covering the command (`grep -rl "charter sync\|charter_sync" tests/ src/`)
- `tests/architectural/test_no_legacy_terminology.py`, `test_docs_cli_reference_parity.py`,
  `test_completion_manifest_freshness.py`, `test_no_retired_subsystems.py`,
  `test_json_contract_enumeration.py`
- `ruff check`, `ruff format --check --force-exclude` (changed files), mypy-clean.
