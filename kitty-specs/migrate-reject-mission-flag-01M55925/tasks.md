# Tasks: Reject `--mission` on non-mission-scoped migrate commands

**Mission**: migrate-reject-mission-flag-01M55925
**Branch**: `fix/migrate-reject-mission-flag` → PR to `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

One cohesive concern (IC-01) → one code work package. Tests ship in the same WP.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression repro: five commands reject `--mission` (RED before fix) | WP01 | |
| T002 | Add `CorpusWideCommand(TyperCommand)` to `migrate_cmd.py` (reuses #4964 helpers) | WP01 | |
| T003 | Retarget the five `@app.command` decorators to `cls=CorpusWideCommand` | WP01 | |
| T004 | Amend two tree-wide invariant tests + add positive reject/equals/normal-run tests | WP01 | |
| T005 | Convert transitional repro to focused test; verify `--help` byte-stable; run blast radius | WP01 | |

## Work Packages

### WP01 — Reject `--mission` on non-mission-scoped migrate commands

- **Goal**: Make `backfill-provenance`, `charter-encoding`, `rebaseline-dossier-hashes`, `rewrite-opposed-by`, and `repin-hooks` reject `--mission` (exit 2, scope-neutral message) instead of silently accepting-and-ignoring it, without regressing the #3953 accept-and-ignore invariant for other commands.
- **Priority**: P1 (4.0.0 release scope, #5294).
- **Independent test**: Invoke each of the five with `--mission <h>` → exit 2 + "not mission-scoped"; invoke each without `--mission` → unchanged behavior; walk the tree → only the five reject.
- **Prompt**: [tasks/WP01-reject-mission-flag.md](./tasks/WP01-reject-mission-flag.md)
- **execution_mode**: code_change
- **owned_files**: `src/specify_cli/cli/commands/migrate_cmd.py`, `tests/cli/test_mission_agnostic_flag.py`
- **Dependencies**: none
- **Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002, C-003, SC-001, SC-002

**Included subtasks**:

T001 Red-first regression repro: five commands reject `--mission` (WP01)
T002 Add `CorpusWideCommand(TyperCommand)` to `migrate_cmd.py` (WP01)
T003 Retarget the five `@app.command` decorators to `cls=CorpusWideCommand` (WP01)
T004 Amend tree-wide invariant tests + add positive reject/equals/normal-run tests (WP01)
T005 Convert transitional repro; verify `--help` byte-stable; run blast radius (WP01)

**Implementation sketch**: red-first repro (T001) → add rejecting class reusing the #4964 click-era-agnostic helpers (T002) → retarget the five decorators (T003) → make the tree-wide invariant tests express the reject-set and add positive controls (T004) → convert the transitional repro, verify `--help` stability and run the blast radius (T005).

**Risks**: two-click-era traceback (reuse `_usage_error_class`); invariant tests staying mechanically green but lying; over-rejecting default `--dry-run`/`--json` paths. See the prompt's Risks section.
