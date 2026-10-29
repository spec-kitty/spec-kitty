# Implementation Plan: Charter CLI typed errors and JSON

**Branch**: `issue-6557-charter-cli-typed-errors-json` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/spec.md`

## Summary

`charter status` gains the existing charter soundness gate and moves every error onto the canonical coded
JSON envelope (#6557). Positional `charter activate` / `charter deactivate` gain `--json`, serializing a
change report that a tidy-first refactor extracts from today's print-as-you-go cascade code (#6525, local
slice). `charter status --json` gains a local, snake_case `activation` block read through the activation
seam (#6526, local slice). Contract mapping, revision and contract codes stay with epic #6518.

Engineering alignment confirmed by the operator (decision `01M5ZCNN5MDNY0AJDA38A6DQG2`).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing); no new dependency
**Storage**: N/A (reads `.kittify/` activation files; writes only through the existing activation manager)
**Testing**: pytest; CLI tests via typer `CliRunner` against tmp-path fixture projects; golden-text tests for the tidy step; snapshot tests (JSON files under the test package) for the payloads; architectural gate `tests/architectural/test_json_contract_enumeration.py`
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single
**Performance Goals**: `charter status --json` stays within the charter's < 2 s CLI budget (NFR-002: ≤ 200 ms added)
**Constraints**: canonical envelope `{ok:false, error:{code,message}}`; local UPPER_SNAKE codes only; human output unchanged except refusal/coded error lines; complexity ≤ 15; no new suppressions
**Scale/Scope**: 3 commands, ~5 source files, ~6 test files

### Supply chain

No dependency is added, upgraded or removed; `DIRECTIVE_051` controls are not triggered.

## Charter Check

| Gate | Result |
|------|--------|
| Single canonical authority | Pass: status reuses `assert_charter_yaml_sound` (C-004); envelope reuses `json_contract.json_error` via `render_coded_error`; "in force" reuses `required_not_in_force` |
| Architectural alignment | Pass: report types in the CLI adapter layer; activation read through `charter.activation.api` (all needed symbols are already exported: `load_activation_ledger`, `required_not_in_force`, `read_org_required_provenance`, `ActiveCharterConfigError`); no seam/offering change |
| ATDD-first | Each WP starts with a failing acceptance test committed first (WP01: golden text captured green-before/green-after as its ratchet) |
| Terminology | Mission/charter canon; no "feature" wording; codes named per research.md §4 |
| Standing order #2 (tidy-first) | WP01 is the behaviour-preserving extraction |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Targeted tests + named gate files only |
| Pack tiers | No pack content touched |

Post-design re-check: pass (no new gaps).

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-cli-typed-errors-json-01M5ZC9Z/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/cli-json.md       # payload + error schemas, local code table
└── tasks.md                    # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/charter/
├── _activation_report.py   # NEW: ActivationChangeReport, CascadeReport, ArtifactRef, to_json(); text renderer helpers move here or stay, rendering from the report
├── _coded_errors.py        # codes table (local) next to render_coded_error
├── activate.py             # positional --json; errors via render_coded_error
├── deactivate.py           # --json; errors via render_coded_error
├── status.py               # soundness gate first; canonical envelope; activation block
└── _status_collectors.py   # NEW collector: _collect_activation_status
docs/api/charter-commands.md          # schemas + codes
docs/changelog/CHANGELOG.md           # [Unreleased] entry (breaking status error envelope)
tests/specify_cli/cli/commands/charter/
├── test_status_broken_charter_6557.py
├── test_activation_json_6525.py (+ snapshots/)
├── test_status_activation_block_6526.py (+ snapshots/)
└── test_activation_text_golden.py    # WP01 ratchet
tests/architectural/test_json_contract_enumeration.py  # reclassify status/activate, add deactivate
```

## Implementation Concern Map

| IC | Concern | WP |
|----|---------|----|
| IC-01 | Separate collection from rendering in activate/deactivate (direct + cascade), byte-identical text | WP01 |
| IC-02 | Status: soundness gate before the bundle check; all errors via `render_coded_error` with local codes | WP02 |
| IC-03 | Activate/deactivate `--json`: lift the preset-only restriction for positional use, captured console, success payload, coded refusals with unchanged exit codes | WP03 |
| IC-04 | Status `activation` block (ledger/legacy, required with in_force) | WP04 |
| IC-05 | Docs, enumeration gate, CHANGELOG | spread: each WP updates the docs and the gate for its surface; CHANGELOG in WP04 |

Dependencies: WP03 → WP01; WP04 → WP02. WP01 and WP02 are independent.

## Design notes

- **Status ordering**: call `assert_charter_yaml_sound(repo_root)` before `_assert_bundle_compatible`, so a list-rooted file never reaches the bundle-schema message. Absent `charter.yaml` passes the gate (unchanged behaviour).
- **Status error mapping**: `KittyInternalConsistencyError` → its own `code` + `body`; `ConfigShapeError` → `CHARTER_CONFIG_SHAPE_INVALID`; `TaskCliError` → `CHARTER_STATUS_FAILED`; other `Exception` → `INTERNAL_ERROR` with text `Error (INTERNAL_ERROR): Unexpected error: …` (keeps "unexpected" only for real crashes). Exit 1 everywhere, as today.
- **Activate/deactivate JSON**: `--json` allowed with the positional form (the preset-only guard keeps `--pack`/`--force` preset-only). In JSON mode the human console is captured (`console.capture()`, as `_activate_preset` does), then one payload is emitted. `ctx.fail` usage errors stay exit 2 and are not JSON (Click usage path, unchanged).
- **Cascade failures**: today a failing cascade target prints a warning and continues; the report records it under `failed` with the message, and the exit code stays 0.
- **Activation block**: `load_activation_ledger(repo_root, report_stray=False)` gives source/path/allow/deny; `read_org_required_provenance` per org-requirable kind gives the required ids with packs; `required_not_in_force` decides `in_force`. Absent allow list → `selected[kind] = null` (unrestricted), distinct from `[]`. On an activation read error the block is `{"error": {"code", "message"}}` rather than failing the whole status (status still reports other sections) — see data-model.md.
