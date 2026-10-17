# Implementation Plan: Reject `--mission` on non-mission-scoped migrate commands

**Branch**: `fix/migrate-reject-mission-flag` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/migrate-reject-mission-flag-01M55925/spec.md`

## Summary

Five `migrate` subcommands (`backfill-provenance`, `charter-encoding`,
`rebaseline-dossier-hashes`, `rewrite-opposed-by`, `repin-hooks`) mutate
corpus-/repo-wide state but are not mission-scoped. Today they silently
accept-and-ignore `--mission` (via `MissionAgnosticCommand`), so an agent that
follows Spec Kitty's own "pass `--mission` everywhere" instruction gets an
unscoped rewrite at exit 0. The fix makes those commands **reject** `--mission`
with a scope-neutral usage error (exit 2), reusing the existing #4964
click-era-agnostic refusal machinery, implemented as a `TyperCommand` subclass
that the mission-agnostic walker leaves alone by its documented contract.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `typer>=0.24.1,<0.28` (two click eras: real `click` ≤0.25, vendored `typer._click` 0.26+), `click` (indirect). No new dependency added, upgraded, or removed — **supply-chain controls N/A** (no dependency decision in this mission).
**Storage**: N/A (CLI parse-layer change only)
**Testing**: pytest; `tests/cli/test_mission_agnostic_flag.py` (existing invariant suite) + new focused reject tests; blast radius `tests/cli/test_mission_agnostic_flag.py`, `tests/cli/test_migrate_group_flags_4964.py` (#4964 sibling — group-flag forwarding into these five subs), `tests/architectural/test_json_contract_enumeration.py`, `tests/migrate/`, `tests/migration/`.
**Target Platform**: Linux/macOS/Windows CLI (the control plane `src/specify_cli/cli/`)
**Project Type**: single (the spec-kitty CLI package)
**Performance Goals**: N/A — parse-layer branch; no measurable runtime budget
**Constraints**: exit code exactly 2 (parsed `UsageError`, never a traceback) under both click eras; `--help` byte-identical (option stays `hidden=True`); cyclomatic complexity ≤15; no blanket `# noqa`/`# type: ignore`.
**Scale/Scope**: 1 new command class + 5 decorator retargets in one module; 2 existing tests amended; new reject tests added. One code WP.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / no improvisation**: the rejection reuses the one existing refusal mechanism (#4964 helpers in `migrate_cmd.py`) and the one walker contract (`cli/helpers.py`), not a parallel hand-rolled path. ✅
- **Architectural alignment / no parallel authority**: the generic mission-agnostic walker is NOT edited; the new class rides its documented left-alone escape hatch (`test_walker_leaves_custom_command_classes_alone`). ✅
- **ATDD / red-first (ADR 2026-07-17-1)**: the reject behavior lands an issue-pinned `@pytest.mark.regression` repro that is RED through the CLI entry point before the fix; converted to focused unit tests after. ✅
- **Tiered rigour**: control-plane CLI surface, consumer-facing → built-in/consumer tier; standard rigour, tests in same PR (Sonar new-code gate). ✅
- **Terminology**: this is a `migrate` CLI surface; no Mission/feature terminology concern introduced. ✅

No charter violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/migrate-reject-mission-flag-01M55925/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── spec.md              # Mission spec
├── checklists/          # requirements.md
├── trace/               # decisions.md, surprises.md, narrative.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

(No `contracts/`, `data-model.md`, or `quickstart.md`: this mission defines no
interfaces or entities — a CLI parse-layer refusal. `meta.json` will carry
`"contracts": "none"` with a rationale so strict `accept` waives them.)

### Source Code (repository root)

```
src/specify_cli/cli/
├── commands/
│   └── migrate_cmd.py      # ADD CorpusWideCommand; retarget 5 @app.command(cls=...)
└── helpers.py              # UNCHANGED (walker left-alone contract relied on, not edited)

tests/cli/
└── test_mission_agnostic_flag.py   # amend 2 tree-wide invariant tests; add reject tests
```

**Structure Decision**: Single-package change confined to
`src/specify_cli/cli/commands/migrate_cmd.py` (the one module that owns both the
five commands and the #4964 refusal helpers). `cli/helpers.py` is read-but-not-written.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

### IC-01 — Reject `--mission` on non-mission-scoped migrate commands

- **Purpose**: Turn the silent accept-and-ignore of `--mission` on the five non-mission-scoped `migrate` commands into an explicit scope-neutral usage-error rejection (exit 2), without regressing the #3953 accept-and-ignore invariant elsewhere.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005; NFR-001, NFR-002; C-001, C-002, C-003; SC-001, SC-002.
- **Affected surfaces**:
  - `src/specify_cli/cli/commands/migrate_cmd.py` — new `CorpusWideCommand(TyperCommand)` with a `parse_args` post-check raising `_usage_error_class(ctx)(...)` when `_given_on_command_line(ctx, "mission")`; retarget the five `@app.command(..., cls=CorpusWideCommand)` decorators (`charter-encoding`, `backfill-provenance`, `rewrite-opposed-by`, `rebaseline-dossier-hashes`, `repin-hooks`). Reuse `_with_ignored_mission_option` from `cli/helpers.py` in `get_params` so the option is still parsed (then rejected), keeping `--help` unchanged.
  - `tests/cli/test_mission_agnostic_flag.py` — amend `test_every_leaf_command_accepts_mission` and `test_reregistration_keeps_the_invariant` to carve out the five-command reject-set; add positive tests that each of the five rejects `--mission <v>` and `--mission=<v>` (exit 2 + message) and still runs normally without the flag.
- **Sequencing/depends-on**: none (single concern).
- **Risks**:
  - Two-click-era hazard: the rejecting class must be typer-native and resolve `UsageError` from the ctx's click universe, or exit 2 degrades to a traceback (NFR-001). Mitigation: reuse `_usage_error_class` verbatim; no new real-`click` class.
  - Known test collision: the two tree-wide invariant tests may stay mechanically green (the hidden option is still declared) yet become intent-lies — they must be *actively* amended, not left. Captured in `trace/surprises.md`.
  - Over-rejection risk: the post-check must fire only on command-line `--mission` (`parameter_source == COMMANDLINE`), never on the `--dry-run`/`--json` default paths (FR-003 positive control guards this).
