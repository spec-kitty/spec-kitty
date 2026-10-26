# Implementation Plan: charter list shows org-required ids in force (#6417)

**Branch**: `issue-6417-charter-list-org-required` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/charter-list-org-required-in-force-01M5WZVP/spec.md`;
discovery in `kitty-specs/charter-list-org-required-research-01M5WZQH/research.md`.

## Summary

`charter list` builds its rows from the raw allow keys, so a kind with no allow key of its own
prints "All built-ins" and never names an org-required id that is in force. Add one reader to the
activation layer, `required_in_force(repo_root)`, that returns, per org-requirable kind whose allow
key is absent, the org-required ids `PackContext.effective_ids` admits over what the layers provide.
Re-export it through `charter.activation.api`; `list_cmd` names those ids on the row and in
`--json` (`activated` = the ids; new `allow_list_present` per row; `schema_version: "2"`). Fix the
acceptance fixture so its rule sits where an org layer provides it, and un-`@wip` the scenario.

## Technical Context

**Language/Version**: Python 3.11+ (CLI); Java 25 / Cucumber-JVM 7 for the acceptance scenario
**Primary Dependencies**: typer, rich, ruamel.yaml (no new dependency; supply-chain check: n/a)
**Storage**: files — `.kittify/charter/activation.yaml` (activation ledger), org pack `org-charter.yaml`
**Testing**: pytest (CliRunner CLI-level + focused unit tests), Cucumber-JVM scenario (nightly)
**Target Platform**: Linux, macOS, Windows 10+
**Project Type**: single project (`src/charter`, `src/specify_cli`)
**Performance Goals**: `charter list` under 2 s on the fixture; no extra scans without a required floor
**Constraints**: `specify_cli` imports the activation layer only via `charter.activation.api`;
core activation semantics unchanged; complexity ≤ 15; ruff/mypy clean
**Scale/Scope**: one reader (~60 lines), one CLI command, one JSON contract, one scenario fixture

## Charter Check

- Single canonical authority: the in-force answer comes from `PackContext.effective_ids` (the
  effective-set authority) over the `list_available_detailed` availability the `--all` view uses;
  no second membership computation. PASS.
- Architectural alignment: the reader lives in `charter.activation`, reached through
  `charter.activation.api` (layer rule, `test_charter_activation_api_reexport.py`). PASS.
- ATDD-first: the CLI-level test and the un-`@wip`'d scenario are committed red before the fix. PASS.
- Terminology: Mission vocabulary; no `feature` aliases. PASS.
- Tests policy: targeted + blast radius; no full heavy suites. PASS.

## Design decisions

- **D-P1 Placement.** `required_in_force` and `RequiredInForce` live in
  `src/charter/activation/activation_ledger.py`, next to `required_not_in_force` /
  `RequiredOmission` (the FR-023 sibling). Both entry types share one private base for
  `pack_names` / `describe_packs`. `PackContext`, `ActiveCharterManager` and the layer roots are
  imported lazily inside the function (`pack_context` imports this module; existing pattern in
  this file).
- **D-P2 Availability.** Per kind with an absent key and a non-empty floor:
  `ActiveCharterManager.list_available_detailed(ctx, token, layer_roots=resolve_layer_roots(..),
  org_root_chain=resolve_pack_chain(.., strict=False))` — the same scan `charter list --all`
  shows, across every org pack in the chain. Kinds with no floor scan nothing (NFR-001).
- **D-P3 In force.** `in_force = floor ∩ PackContext.effective_ids(kind, available)`. Floor beats
  deny (`load_denied` already subtracts the floor); an unprovided id is not in `available`; for
  `skill` the materialised floor is the allow state, intersected with availability by
  `effective_ids` — listed once.
- **D-P4 Leniency.** The floor is read with `strict=False`, as FR-023 does; an unreadable floor
  yields nothing, never an exit.
- **D-P5 CLI rendering.** Absent-key row with ids: `"(All built-ins — no explicit activation)"`
  plus one line per id `"<label> (required by <describe_packs>)"`; `label` is the existing
  `stem (declared_id)` identity label. JSON: `activated` = sorted ids or `null`;
  `allow_list_present` on every row; top-level `schema_version: "2"`. Extract row building out of
  `list_cmd` into helpers to keep complexity ≤ 15.
- **D-P6 Fixture.** `CharterSteps`: the rule moves to `directives/team-rule.directive.yaml` with
  a valid directive body (`id: TEAM_RULE`, `intent`, `enforcement: required`); the DRG node
  `body_path` follows. One constant for the file path.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-list-org-required-in-force-01M5WZVP/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/charter-list-json.md
└── tasks.md            (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/activation/activation_ledger.py     # RequiredInForce, required_in_force
src/charter/activation/api.py                   # re-export + __all__
src/specify_cli/cli/commands/charter/list_cmd.py
tests/charter/activation/                       # reader unit tests
tests/specify_cli/cli/commands/charter/test_charter_list_commands.py
tests/architectural/test_charter_activation_api_reexport.py   # identity row
acceptance-jvm/src/test/java/kitty/acceptance/steps/CharterSteps.java
tests/scenarios/charter/governance-in-force/governance-in-force.feature
tests/scenarios/charter/PROMISES.md
docs/api/charter-commands.md
docs/changelog/CHANGELOG.md
```

**Structure Decision**: single project; changes stay in the files above.

## Implementation Concern Map

### IC-01 — Red-first acceptance

- **Purpose**: pin the user-visible behaviour before the fix.
- **Relevant requirements**: FR-001, FR-003, FR-004, FR-005, FR-008
- **Affected surfaces**: CLI-level test module, the feature file, `CharterSteps.java`, `PROMISES.md`
- **Sequencing/depends-on**: none
- **Risks**: the JVM suite cannot run here (Java 25 missing); the Python CLI test is the local witness.

### IC-02 — In-force reader in the activation layer

- **Purpose**: one reader that answers "which org-required ids are in force on a default row".
- **Relevant requirements**: FR-002, FR-007, NFR-001, NFR-003, C-001, C-002
- **Affected surfaces**: `activation_ledger.py`, `api.py`, reader unit tests, api re-export gate
- **Sequencing/depends-on**: IC-01
- **Risks**: import cycle (`pack_context` imports `activation_ledger`): lazy imports.

### IC-03 — Listing and contract

- **Purpose**: render the ids and version the JSON contract.
- **Relevant requirements**: FR-001, FR-003–FR-006, FR-009, NFR-004
- **Affected surfaces**: `list_cmd.py`, its tests, `docs/api/charter-commands.md`, changelog
- **Sequencing/depends-on**: IC-02
- **Risks**: `list_cmd` complexity; existing tests pin `activated: null` — update deliberately.
