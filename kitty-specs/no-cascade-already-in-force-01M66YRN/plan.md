# Implementation Plan: `charter activate` names referenced artifacts that are already in force

**Branch**: `issue-6742-no-cascade-already-in-force` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/no-cascade-already-in-force-01M66YRN/spec.md`

**Note**: This plan covers the mission's single, small technical slice; the discovery
findings and their rationale are in [research.md](./research.md).

## Summary

`charter activate` without `--cascade` reports every referenced artifact of the activated
source as `Warning: referenced <kind>/<id> was not activated (no --cascade).`, whether or
not the artifact is in force. On a project with no `activated_<kind>` keys every artifact
of an "all" kind *is* in force, so the warning is both noise (~150 lines) and the opposite
of the truth. This mission splits the no-cascade report into "already in force" and "not
in force", using the activation layer's existing membership rule, and mirrors the split in
the `--json` change report.

## Technical Context

**Language/Version**: Python 3.11 (repository baseline)
**Primary Dependencies**: Typer + Rich (CLI), `charter.activation` (membership, ledger), no new dependency
**Storage**: `.kittify/charter/activation.yaml` / `.kittify/config.yaml` activation ledger (read only here)
**Testing**: pytest, `pytest.mark.fast`; CLI-level tests through `typer.testing.CliRunner`
**Target Platform**: CLI (all platforms the CLI ships on)
**Project Type**: single (Python CLI)
**Performance Goals**: no measurable change; at most one extra `PackContext.from_config` and one extra ledger read per invocation (NFR-004)
**Constraints**: report-only change — activation writes and exit codes must not move (spec NFR-002)
**Scale/Scope**: 3 source files (`activate.py`, `_activation_report.py`, `_cascade_shared.py`-adjacent), 1 doc page, 1 changelog entry, 4 test modules

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (`DIRECTIVE_044`): the in-force verdict reads the existing
  membership accessor `PackContext.admits` and the existing three-state ledger read; no
  second "what is in force" rule is introduced (NFR-001).
- **Locality of change** (`DIRECTIVE_024`): the change stays inside the charter CLI output
  layer. `charter.activation.cascade` (pure graph logic) and the activation engine are not
  touched.
- **ATDD-first** (`DIRECTIVE_034`): the red test drives the pre-existing entry point
  (`charter_app` via `CliRunner`) and fails on `main` with the current wording.
- **Terminology canon**: "in force" is the charter's own term for effective activation
  (`charter list`'s `_REQUIRED_IN_FORCE`, `No longer in force`); the new lines reuse it.
- **Tests as scaffolding, not friction** (`DIRECTIVE_041`): the existing golden-text ratchet
  already pins this output; it is updated where the behaviour intentionally changes and
  extended with one focused class, not duplicated.
- **No full heavy suite** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run the four affected test
  modules plus ruff/mypy on the touched files.

## Project Structure

### Documentation (this mission)

```
kitty-specs/no-cascade-already-in-force-01M66YRN/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery findings)
├── spec.md              # Mission specification
├── checklists/          # Spec quality checklist
├── tasks.md             # Phase 2 output (tasks step)
└── tasks/               # Per-WP task files
```

### Source Code (repository root)

```
src/
├── charter/activation/
│   ├── pack_context.py          # PackContext.admits — the membership authority (read only)
│   └── cascade.py               # engine NoCascadeReport — unchanged (pure graph logic)
└── specify_cli/cli/commands/charter/
    ├── activate.py              # _no_cascade_report + render_no_cascade_warning (changed)
    ├── _activation_report.py    # NoCascadeReport bucket + to_json (changed)
    └── _cascade_shared.py       # neighbouring non-warning line style (reference only)

tests/specify_cli/cli/commands/charter/
├── test_activation_text_golden.py                    # goldens updated where wording changes
├── test_activation_json_6525.py                      # JSON shape updated + new key
├── test_charter_activate_commands_cascade_output.py  # new red-first class
└── test_activate_include_deactivated.py              # deactivated-line regression stays

docs/
├── api/charter-commands.md      # no-cascade section + change-report table + examples
└── changelog/CHANGELOG.md       # [Unreleased] entry
```

**Structure Decision**: single-project layout. Everything the change needs already exists
in the charter CLI command package; no new module is warranted (the helper that decides one
line is ~20 lines and belongs beside the renderer that prints it).

## Design decisions

### D-1 — Where the verdict is computed

`_no_cascade_report(source_urn, repo_root, layer_roots, deactivated)` already builds the CLI
`NoCascadeReport` from the engine's kind-bucketed walk. It gains the split: after the
engine returns, ask, per referenced artifact, whether the project admits it.

- Membership: `PackContext.from_config(repo_root).admits(kind, config_id, available=frozenset({config_id}))`.
  The single-token `available` set is honest: the artifact exists (it is a node of the
  merged DRG whose file resolved to a config stem), and `admits` only consults `available`
  in the absent-`all` branch.
- Reason for the text: the ledger's three-state allow (`load_activation_ledger(repo_root).allow`),
  `None` ⇒ "no explicit list", otherwise "listed in `activated_<plural>`" (`allow_key`).
- Read after the direct write, so `--only` narrowing is reflected (FR-004).

### D-2 — Where the bucket lives

The CLI `NoCascadeReport` (`_activation_report.py`) gains
`already_in_force: tuple[ArtifactRef, ...]`, next to `skipped`/`deactivated`/`kind_filtered`.
The engine's `NoCascadeReport` (pure graph, no project state) is untouched, so the
activation layer keeps having no opinion about "in force".

`warned` stays `skipped + deactivated` — it is documented as "every artifact a
`Warning: referenced …` line names", and the new lines are not warnings.

### D-3 — Text

`render_no_cascade_warning` prints the notes first, in the position the removed warnings
occupied:

```text
Note: referenced <kind>/<id> is already in force (<reason>); not added by this command.
```

Then the unchanged deactivated warnings, then the hint (gated on the remaining `skipped`),
then the unchanged kind-filtered lines.

### D-4 — JSON

`ActivationChangeReport.to_json()` adds `referenced_already_in_force` (list of
`{kind, id, urn}`). `referenced_not_cascaded` keeps its name and meaning and simply no
longer contains in-force artifacts. Both surfaces read the same value, as before.

## Complexity Tracking

No charter violations; the table is intentionally empty.

## Implementation Concern Map

### IC-01 — The in-force split and its text rendering

- **Purpose**: compute the already-in-force bucket from the project's own membership rule
  and print it as a `Note` instead of a warning.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-006, FR-007, NFR-001, NFR-003, NFR-004
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/activate.py`
  (`_no_cascade_report`, `render_no_cascade_warning`, `_activation_change_report`),
  `src/specify_cli/cli/commands/charter/_activation_report.py` (`NoCascadeReport`)
- **Sequencing/depends-on**: none
- **Risks**: the `--only` case (verdict must follow the post-write state); the hint must
  not survive as a dangling "re-run with --cascade" when nothing is left to activate.

### IC-02 — The `--json` field

- **Purpose**: expose the new bucket as `referenced_already_in_force` and keep
  `referenced_not_cascaded` truthful.
- **Relevant requirements**: FR-005, C-002
- **Affected surfaces**: `_activation_report.py` (`ActivationChangeReport.to_json`),
  `tests/specify_cli/cli/commands/charter/test_activation_json_6525.py`
- **Sequencing/depends-on**: IC-01 (it reads the same value)
- **Risks**: the JSON contract doc is a historical mission artifact; only
  `docs/api/charter-commands.md` is the live surface.

### IC-03 — Evidence, docs and changelog

- **Purpose**: prove the behaviour red-first and keep the operator-facing docs true.
- **Relevant requirements**: FR-008, SC-001, SC-002, SC-003, SC-004
- **Affected surfaces**: `tests/specify_cli/cli/commands/charter/` (golden, json, cascade
  output, include-deactivated modules), `docs/api/charter-commands.md`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the golden ratchet encodes the old wording on purpose; each changed line must
  be justified in the test diff, and the `test_mission_type_without_cascade_warns_about_its_references`
  fixture (explicit empty `activated_directives`) must stay a warning, proving the split
  does not over-reach.
