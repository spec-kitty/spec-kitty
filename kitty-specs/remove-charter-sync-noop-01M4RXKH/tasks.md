# Tasks: Remove the charter sync no-op compatibility command

**Mission**: remove-charter-sync-noop-01M4RXKH
**Branch**: `issue-5828-remove-charter-sync-noop`
**Input**: [spec.md](./spec.md) · [plan.md](./plan.md)

Delete the inert `spec-kitty charter sync` CLI command and every live reference/recovery
hint that points at it (#5828, ADR `2026-10-06-2` §7). The removal is behaviour-preserving
for every other `charter` subcommand; the load-bearing `charter.activation.sync` **module**
is out of scope. One cohesive work package: the enumerating/parity/freshness gates must flip
red→green together, so the removal lands as one coherent slice rather than split WPs that
leave an intermediate commit red on a gate.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Delete `charter sync` command module + its wiring (`charter/__init__.py` import + `__all__`) | WP01 | — |
| T002 | Assert the removed name now fails with the standard Typer unknown-command error (red-first) | WP01 | — |
| T003 | Remove the 4 dedicated `test_sync_command_*` tests; drop the pointless `["sync"]` setup in the `charter status` tests; move the `YAML_HEADER` + preflight-reason pins | WP01 | — |
| T004 | Regenerate the completion manifest + generated CLI reference; update the two command-enumerating architectural gates | WP01 | — |
| T005 | Strip every live `charter sync` reference/hint (status stale-hint, preflight `--auto-refresh` help + `references_refresh` docstring, `YAML_HEADER`, `spk-charter-governance` skill sources + command-map, synthesize-doctrine how-to, `charter-commands.md`, project-charter prose) | WP01 | — |
| T006 | Add the `[Unreleased]` CHANGELOG entry for the breaking removal | WP01 | — |

---

## WP01 — Remove the charter sync command surface + references

**Prompt**: [tasks/WP01-remove-charter-sync-noop.md](tasks/WP01-remove-charter-sync-noop.md)

**Summary**
- **Goal**: Remove the `charter sync` Typer command and every live reference/hint; regenerate derived artifacts; update the gates that enumerate the command — all honestly green, zero suppressions. Preserve the `charter.activation.sync` module and every other `charter` subcommand.
- **Priority**: P2 — usability / domain:cli tidy-up; behaviour-preserving for real commands.
- **Independent test**: Invoke `spec-kitty charter sync` → standard unknown-command error, non-zero exit; `make test-fast` + the charter/CLI test dirs + `test_no_legacy_terminology.py` + the completion-manifest freshness gate + the CLI-reference parity gate all green; grep shows no live `spec-kitty charter sync` reference remaining in shipped source.

**Tracking**
- [ ] T001 Delete `charter sync` command module + wiring (WP01)
- [ ] T002 Red-first unknown-command assertion for the removed name (WP01)
- [ ] T003 Remove dedicated CLI tests; drop `["sync"]` setup; move pins (WP01)
- [ ] T004 Regenerate manifest + CLI reference; update enumerating gates (WP01)
- [ ] T005 Strip live references/hints across CLI, skills, docs, charter prose (WP01)
- [ ] T006 CHANGELOG `[Unreleased]` entry (WP01)

**Implementation sketch**
- `src/specify_cli/cli/commands/charter/sync.py` deleted; `charter/__init__.py` drops the `from …charter.sync import sync` import and the `"sync"` entry in `__all__`. The `_collect_charter_sync_status` collector (used by `charter status`) is NOT the command and stays.
- `python -m specify_cli.completion --regenerate` rebuilds `_completion_manifest.json`; `scripts/docs/build_cli_reference.py` rebuilds `docs/api/cli-commands.md`.
- `test_no_retired_subsystems.py`: drop `("charter","sync")` from `_REQUIRED_CLI_PATHS`. `test_json_contract_enumeration.py`: drop the `"charter sync"` row.
- Hints: `status.py` stale-hint line; `preflight/cli.py` `--auto-refresh` help + `references_refresh.py` docstring (align to the live `generate`/`upgrade`-based sequence, which they already describe downstream); `schemas.py` `YAML_HEADER` regen hint → `charter generate` (+ its pin in `test_retrospective_governance_emit.py`); `test_next_preflight.py` default reason string.
- Skills/docs sources: `spk-charter-governance/{SKILL.md,references/*}`, `docs/guides/how-to/governance/synthesize-doctrine.md`, `docs/api/charter-commands.md`, `.kittify/charter/charter.md`.
- Keep rationale comments that explain *why the refresh sequence is no longer `charter sync`* (`preflight/runner.py`, `freshness/computer.py`) — they stay true after removal.
- Scope fences: no `charter status` STALE-verdict rework (#4042); flag #2992 for closure as superseded; no module changes (#C-002).
