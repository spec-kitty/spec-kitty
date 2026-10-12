# Implementation Plan: Remove the charter sync no-op compatibility command

**Mission**: `remove-charter-sync-noop-01M4RXKH`
**Branch**: `issue-5828-remove-charter-sync-noop`
**Spec**: `kitty-specs/remove-charter-sync-noop-01M4RXKH/spec.md`

## Summary

Delete the inert `spec-kitty charter sync` CLI command and remove every live reference and
recovery hint that points at it, so the surface stops contradicting itself (ADR
`2026-10-06-2` §7). The load-bearing `charter.activation.sync` **module** is untouched; the
removal is behaviour-preserving for every other `charter` subcommand. The removed name then
fails with the standard Typer unknown-command error.

## Technical Context

- **Language/runtime**: Python 3.11+, Typer CLI, pytest.
- **Removed surface**: the `charter sync` Typer command only.
- **Preserved surface**: `charter.activation.sync` module (`load_governance_config`,
  `load_directives_config`, `ensure_charter_bundle_fresh`, `require_canonical_governance`,
  `SyncResult`, `sync()`), consumed by the resolver, compiler, and `charter generate`.
- **Generated artifacts** regenerated from the live CLI after the edit:
  `src/specify_cli/_completion_manifest.json` (`python -m specify_cli.completion --regenerate`)
  and `docs/api/cli-commands.md` (`scripts/docs/build_cli_reference.py`).
- **Gates implicated**: `test_completion_manifest_freshness.py`,
  `test_docs_cli_reference_parity.py` (incl. `test_offering_source_snippets_are_registered`),
  `test_no_retired_subsystems.py` (`_REQUIRED_CLI_PATHS`), `test_json_contract_enumeration.py`,
  `test_no_legacy_terminology.py`.

## Charter Check

- **Single canonical authority** — removing a shim that gives one concept a second, inert name. ✅
- **Canonical sources, no improvise** — edit sources (`src/charter/offering/skills/**`, generators), regenerate derived artifacts; never hand-edit generated agent copies. ✅
- **Terminology canon (Mission)** — no `feature`-for-Mission wording introduced. ✅
- **Red-main / honest gates** — gates updated to reflect the real surface; zero suppressions. ✅
- **Locality of change / smallest-viable-diff** — scoped to the command surface + its references; `#4042`'s STALE-verdict rework and `#2992`'s closure are explicitly fenced out. ✅

No charter violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)
- `kitty-specs/remove-charter-sync-noop-01M4RXKH/{spec,plan,tasks}.md`
- `docs/changelog/CHANGELOG.md` — `[Unreleased]` entry.

### Source Code (repository root)

```
src/specify_cli/cli/commands/charter/
  sync.py                      # DELETE (the no-op command)
  __init__.py                  # drop `from …charter.sync import sync` + "sync" in __all__
  status.py                    # drop the "Run: spec-kitty charter sync" stale-hint line
src/specify_cli/charter_runtime/preflight/
  cli.py                       # --auto-refresh help: drop "charter sync" from the sequence
  references_refresh.py        # docstring: sequence no longer starts with charter sync
src/charter/activation/schemas.py   # YAML_HEADER: regen hint → `charter generate`
src/specify_cli/_completion_manifest.json  # REGENERATE
docs/api/cli-commands.md             # REGENERATE
docs/api/charter-commands.md         # drop the `charter sync` section (hand-authored)
src/charter/offering/skills/spk-charter-governance/
  SKILL.md, references/charter-command-map.md,
  references/charter-governance-workflow.md,
  references/charter-artifact-structure.md   # drop charter sync entries/snippets
docs/guides/how-to/governance/synthesize-doctrine.md  # drop charter sync hint
.kittify/charter/charter.md          # two incidental prose mentions → corrected
tests/
  agent/cli/commands/test_charter_cli.py       # remove 4 sync-command tests; drop ["sync"] setup
  agent/cli/commands/test_next_preflight.py     # update default reason hint string
  architectural/test_no_retired_subsystems.py   # drop ("charter","sync") from _REQUIRED_CLI_PATHS
  architectural/test_json_contract_enumeration.py # drop "charter sync" entry
  charter/test_retrospective_governance_emit.py  # update pinned YAML_HEADER string
```

## Complexity Tracking

*No charter violations — none.*

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` slices these into WPs.

### IC-01 — Remove the command surface + wiring

- **Purpose**: Delete the `charter sync` Typer command so it no longer resolves; the name falls through to the standard unknown-command error.
- **Relevant requirements**: FR-001, FR-002, FR-007.
- **Affected surfaces**: `cli/commands/charter/sync.py` (delete), `cli/commands/charter/__init__.py` (import + `__all__`).
- **Sequencing/depends-on**: none (first).
- **Risks**: Must not disturb the `charter.activation.sync` module or the `_collect_charter_sync_status` collector used by `charter status`.

### IC-02 — Regenerate derived artifacts + update enumerating gates

- **Purpose**: Bring the completion manifest, generated CLI reference, and the two command-enumerating architectural gates in line with the smaller surface.
- **Relevant requirements**: FR-004, FR-005.
- **Affected surfaces**: `_completion_manifest.json`, `docs/api/cli-commands.md`, `test_no_retired_subsystems.py`, `test_json_contract_enumeration.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: Regenerate from the live CLI (don't hand-edit the manifest); the parity gate compares exact command sets.

### IC-03 — Remove live references, hints, tests, docs, changelog

- **Purpose**: Strip every live `charter sync` recovery hint / reference from CLI help, preflight text, the emitted YAML header, skill sources, docs, and the project charter prose; remove the command's dedicated tests and the pointless `["sync"]` setup; add the changelog entry. Keep rationale comments that explain *why the sequence is no longer `charter sync`*.
- **Relevant requirements**: FR-003, FR-006, FR-008, NFR-001, NFR-002, C-001, C-003.
- **Affected surfaces**: `status.py`, `preflight/cli.py`, `preflight/references_refresh.py`, `schemas.py`, the `spk-charter-governance` skill sources, `synthesize-doctrine.md`, `charter-commands.md`, `.kittify/charter/charter.md`, the three test files, `CHANGELOG.md`.
- **Sequencing/depends-on**: IC-01 (offering-snippet parity gate reds only once the command is gone).
- **Risks**: `charter-commands.md` is hand-authored (not regenerated); the `test_retrospective_governance_emit.py` pin must move with the `YAML_HEADER` change; do NOT touch the `charter status` STALE verdict (#4042).
