# Implementation Plan: charter consistency-check honours the project layer

**Branch**: `issue-6749-charter-consistency-project-layer` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/charter-consistency-project-layer-01M67J5F/spec.md`
**Input**: Mission specification from `kitty-specs/charter-consistency-project-layer-01M67J5F/spec.md`

## Summary

`charter.activation.consistency_check` decides "is this activated token known?" with
one catalog built by `_collect_all_offering_ids`, which calls
`ActiveCharterManager.list_available(..., org_root_chain=...)` and never passes the
canonical project layer roots. After #6433 artifact kinds resolve through the run's
`IdentityIndex` (which does cover the project layer), so only `mission-type` still
reads that catalog — and a project-layer mission type that the runtime roster and
`charter mission-type list` resolve is reported `mission-type/<id>: Not found in
doctrine`, exit 1.

The technical approach: make the catalog stop being structurally blind
(`layer_roots=resolve_layer_roots(repo_root)` alongside the existing org chain), and
make the `mission-type` membership answer come from
`charter.missions.resolve_layered_mission_types` — the same layered roster the
runtime, `charter mission-type list` and `charter activate`'s preflight already use.
One authority per kind, no re-derived directory walk, no second membership rule.
Unknown tokens still refuse; an unreadable roster fails closed into
`verification_errors`.

## Technical Context

**Language/Version**: Python 3.11 (repo floor; `pyproject.toml` requires-python)
**Primary Dependencies**: `typer`, `ruamel.yaml`, `pydantic`; internal layers `charter` / `specify_cli` / `kernel` / `doctrine`
**Storage**: files on disk — `.kittify/charter/activation.yaml` (activation ledger),
`.kittify/charter-packs/` (project pack root), `.kittify/missions/mission_types/` (project mission types), `packs/built-in/` (built-in pack)
**Testing**: pytest; unit/integration markers per directory; CLI acceptance through `typer.testing.CliRunner` on `charter_app`
**Target Platform**: CLI, Linux/macOS/Windows (path handling via `pathlib` only)
**Project Type**: single project (`src/` layout)
**Performance Goals**: no measurable regression of `run_consistency_check`; the existing 6.0 s budget test (`tests/charter/test_consistency_check.py`) bounds it
**Constraints**: fail-closed on unreadable input; layer ratchet `kernel <- doctrine <- charter <- specify_cli` (charter must not import `specify_cli`); no second membership rule; no full heavy suites in-mission
**Scale/Scope**: one predicate module (`src/charter/activation/consistency_check.py`), ~40 net lines plus tests; one user-facing changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict | Evidence |
|------|---------|----------|
| Single canonical authority (Governing Principle) | PASS | Membership for `mission-type` moves onto the existing `resolve_layered_mission_types` roster; the catalog keeps one `list_available` call, now given the canonical `resolve_layer_roots` map. Nothing re-derives a directory walk. |
| Architectural alignment (layers, C-001/C-007/C-008) | PASS | `charter.activation.*` reaches the roster through the `charter.missions` facade re-export; no `specify_cli` import; roots stay data passed into `pack_manager` (C-008). |
| DDD + tiered rigour | PASS | The change is inside the charter activation bounded context; no new domain type, no schema change. |
| ATDD-first (DIRECTIVE_034) | PASS | Acceptance tests drive the production entry point (`charter consistency-check` via the CLI) and the project-layer fixture fails first. |
| Terminology adherence | PASS | "project layer" = `.kittify/charter-packs/` pack root; "project mission types" = `.kittify/missions/mission_types/`; "coordination/identity index" used as in `docs/context/`. |
| DIRECTIVE_024 locality of change | PASS | Two functions in one module plus their call sites; the activation writer and `pack_manager` are untouched. |
| DIRECTIVE_025 boy scout | PASS | The stale `_collect_all_offering_ids` docstring (org-only rationale) is corrected in place; no unrelated cleanup. |
| DIRECTIVE_041 tests as scaffold | PASS | Every added test guards a standing invariant (reader agreement, refusal, fail-closed) and none pins line numbers or private wiring. |
| No false green | PASS | The malformed-roster arm asserts `coherent is False` **and** a `verification_errors` entry; the unknown-token arm is a same-fixture control. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-consistency-project-layer-01M67J5F/
├── plan.md              # This file
├── research.md          # Phase 0 output (grounding evidence, decisions D-001..D-006)
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output
└── traces/              # tooling-friction.md, approach.md, design-decisions.md
```

### Source Code (repository root)

```
src/
├── charter/
│   ├── activation/
│   │   ├── consistency_check.py     # _collect_all_offering_ids, _is_known, run_consistency_check
│   │   ├── identity_index.py        # artefact-kind authority (unchanged)
│   │   ├── layer_roots.py           # resolve_layer_roots / resolve_pack_chain (reused)
│   │   └── pack_manager.py          # list_available(layer_roots=..., org_root_chain=...) (unchanged)
│   ├── missions.py                  # facade re-export of resolve_layered_mission_types (reused)
│   └── offering/missions/mission_type_repository.py   # the roster implementation (unchanged)
└── specify_cli/cli/commands/charter/consistency_check.py   # the CLI command (unchanged, tested)

tests/
├── charter/
│   ├── test_consistency_check.py                      # catalogue + implicit-all-active invariant
│   └── activation/test_compile_check_identity_6433.py # sibling identity-index tests (unchanged)
└── specify_cli/cli/commands/charter/
    └── test_charter_consistency_check.py              # CLI acceptance for #6749
```

**Structure Decision**: single project, existing `src/` layout. The production
change is confined to `src/charter/activation/consistency_check.py`; tests are added
where their kind already lives (charter unit/integration tests, CLI acceptance
tests). No new module and no new package.

## Complexity Tracking

*No Charter Check violations. No row.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — Project-aware known-id catalogue

- **Purpose**: Stop the check's catalogue from being structurally blind to the project layer, so no future consumer of it re-introduces the same omission.
- **Relevant requirements**: FR-003, NFR-001, C-001, C-003
- **Affected surfaces**: `src/charter/activation/consistency_check.py` (`_collect_all_offering_ids`), `src/charter/activation/layer_roots.py` (reused as-is), `tests/charter/test_consistency_check.py`
- **Sequencing/depends-on**: none
- **Risks**: `resolve_layer_roots` is a filesystem resolution per run — it is cheap (two `is_dir` probes plus the org registry read) and the explicit-activation branch already does comparable work; must be resolved **once** per run and reused for every kind (NFR-001). A `list_available` `ValueError` keeps its existing per-kind empty-set fallback.

### IC-02 — Mission-type membership from the layered roster

- **Purpose**: Make the one kind that still consults the catalogue agree with every reader by taking its membership from the roster those readers use.
- **Relevant requirements**: FR-001, FR-002, FR-004, FR-005, NFR-002, NFR-004, C-002
- **Affected surfaces**: `src/charter/activation/consistency_check.py` (`_collect_all_offering_ids` / `_is_known` call path, `run_consistency_check`), `src/charter/missions.py` (facade, reused), `src/charter/offering/missions/mission_type_repository.py` (roster, unchanged)
- **Sequencing/depends-on**: IC-01 (same function; IC-01 lands first so the two changes are independently reviewable)
- **Risks**: the roster loud-fails on a malformed layer (by design) — `run_consistency_check` must catch it and emit a `verification_errors` entry rather than crashing; the read must be lazy (only when a `mission_type_activations` list exists) so the implicit-all-active path performs no roster read at all.

### IC-03 — Acceptance evidence at the production entry point

- **Purpose**: Prove the behaviour through `charter consistency-check` (the command operators run), with the positive control on the same fixture, and pin the already-fixed directive/styleguide path against regression while this catalogue changes.
- **Relevant requirements**: FR-006, FR-007, SC-001, SC-002, SC-003, SC-005
- **Affected surfaces**: `tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py`, `tests/charter/test_consistency_check.py`
- **Sequencing/depends-on**: IC-01, IC-02 (the tests must fail before, pass after; the red-first proof is captured in the implementation commit messages)
- **Risks**: the fixtures must build the project layer the way production writes it (`charter new` layout for artefacts, `.kittify/missions/mission_types/<id>.yaml` for mission types, `tests/_factories/activation_ledger.seed_activation_ledger` for the ledger) — never a hand-invented shape.

## Phase 1 Design Notes

- **Data model**: no new persisted entity. The catalogue stays
  `dict[str, frozenset[str]]` (CLI kind → known ids). The mission-type entry's
  source changes from `list_available` to the roster's keys; its type is unchanged.
- **Contracts**: no wire-format change. `ConsistencyReport` fields, the `--json`
  shape and the exit codes are unchanged. The one behavioural contract change is
  that a malformed mission-type file moves from "reported unknown" to "could not
  verify" (`verification_errors`), which is still `coherent: false` / exit 1.
- **Failure modes**: roster raise → `verification_errors` entry, coherent false;
  `list_available` `ValueError` → per-kind empty set (unchanged); no activation keys
  → no catalogue and no roster read (unchanged).
- **Quickstart** (manual verification, used in the PR's Tests-run section):
  1. `git init` a scratch project; write
     `.kittify/missions/mission_types/proj-mission.yaml`
     (`schema_version: 1`, `id: proj-mission`, `display_name: ...`, `extends: software-dev`);
  2. `mission_type_activations: [proj-mission]` in `.kittify/charter/activation.yaml`;
  3. `spec-kitty charter mission-type list --json` → activated, `source_layer: project`;
  4. `spec-kitty charter consistency-check --json` → `coherent: true`, exit 0.
