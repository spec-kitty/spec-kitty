# Implementation Plan: The ledger cutover preserves the retired project command files it inherits

**Branch**: `issue-6547-upgrade-cutover-preserves-retired-commands` | **Date**: 2026-10-31 | **Spec**: [kitty-specs/upgrade-cutover-preserves-retired-commands-01M68J8W/spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/upgrade-cutover-preserves-retired-commands-01M68J8W/spec.md`

## Summary

`spec-kitty upgrade` must not restore the per-project `spec-kitty.*` command files that 3.1.2
retired. Two pre-globalize migrations still *write* them and are re-selected under ledger-diff
selection whenever the ledger does not settle them: `2.1.4_enforce_command_file_state` (writes all
files unconditionally) and `3.0.2_restore_prompt_commands` (writes when any prompt file is
missing). On a project whose ledger settles the two retiring migrations
(`3.1.2_globalize_commands`, `3.2.0a4_safe_globalize_commands`), the writers fire, the retirees are
skipped, and the project gains 14 files it must not have.

The technical approach is the existing supersession seam (#6589,
`src/specify_cli/upgrade/supersession.py`): declare both writers superseded by
`3.2.0a4_safe_globalize_commands`, so `MigrationRegistry.register` substitutes a
`SupersededMigration` whose `detect()` is always `False` and which the runner records `skipped`
with a `superseded_by` note. Selection, the runner, the backfill, `upgrade --dry-run` and
`migrate ledger` all read that table; no second authority is introduced. The shipped modules stay
byte-identical, so `content_hash` and every existing ledger record stay stable.

## Technical Context

**Language/Version**: Python 3.11+ (`uv run`, `from __future__ import annotations`)
**Primary Dependencies**: existing only — `kernel` (clock/atomic), `packaging.version`; no new dependency
**Storage**: `.kittify/migration-ledger.jsonl` (tracked) and `.kittify/migrations/clone-local.jsonl`
**Testing**: pytest, `tests/specify_cli/upgrade/`; `pytest -m "not heavy"` on the touched modules;
CI owns the full sweep
**Target Platform**: CLI (`spec-kitty upgrade`), macOS/Linux/Windows
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: the two superseded entries add zero filesystem writes and zero subprocess
calls to an upgrade run (NFR-001)
**Constraints**: declare once in `upgrade/supersession.py`; never edit a shipped migration module
(DIRECTIVE_044); do not touch `get_applicable`, the runner or the adoption baseline
**Scale/Scope**: one declaration file + one regression test module + one existing invariant test
extended + changelog + upgrade doc paragraph

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The supersession table is the one declaration; selection/runner/backfill keep their existing reads. |
| Architectural alignment | Stays inside `upgrade/`; no new module, no new migration id, no schema change. |
| ATDD-first / red-first | The reproduction is written and fails through `MigrationRunner.upgrade` before the table entry exists (DIRECTIVE_034). |
| Glossary & terminology | Mission uses "superceded migration", "successor", "settled", "cutover" exactly as the charter and `supersession.py` define them. |
| DIRECTIVE_044 (shipped migrations never edited) | Both writer modules and both retiring modules stay byte-identical; asserted by test. |
| Change-apply-smallest-viable-diff / locality of change | Two dict entries, one comment, one test module, one table enumeration, changelog, doc line. |
| Standing order: no fake green | No marker, gate, skip or allowlist is touched. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/upgrade-cutover-preserves-retired-commands-01M68J8W/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Work-package outline (/spec-kitty.tasks)
├── tasks/               # Work-package files
├── issue-matrix.md      # Issue #6547 claim and verdict
└── traces/              # approach.md, design-decisions.md, tooling-friction.md
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── supersession.py                                  # EDIT: two entries + comment
└── migrations/
    ├── m_2_1_4_enforce_command_file_state.py        # UNCHANGED (asserted)
    ├── m_3_0_2_restore_prompt_commands.py           # UNCHANGED (asserted)
    └── m_3_2_0a4_safe_globalize_commands.py         # UNCHANGED (successor, named only)

tests/specify_cli/upgrade/
├── test_gitignore_backfills_superseded_6589.py      # EDIT: extend SHIPPED_SUPERSEDED enumeration
└── test_retired_command_writers_6547.py             # NEW: the red-first regression

docs/
├── changelog/CHANGELOG.md                           # EDIT: [Unreleased] entry
└── (upgrade-reference page touching this behaviour) # EDIT: one paragraph
```

**Structure Decision**: single Python package; the fix lives in the upgrade subsystem that owns
migration selection, and its regression test lives beside the other supersession tests.

## Complexity Tracking

No charter violations. No new abstraction: the supersession table is the established seam for
"a later migration replaced what this older one wrote", used five times already.

## Implementation Concern Map

### IC-01 — The declaration and its table invariants

- **Purpose**: Make both pre-globalize writer migrations recorded no-ops, with the successor and the
  table invariants (registered, manifest-ordered, hash-stable, direct import unchanged) covering them.
- **Relevant requirements**: FR-002, FR-006, C-001, C-002, C-003, SC-003, SC-004
- **Affected surfaces**: `src/specify_cli/upgrade/supersession.py`;
  `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`
- **Sequencing/depends-on**: none
- **Risks**: the existing test enumerates the shipped classes behind the table and asserts exact key
  coverage; it must gain the two classes (an extension, not a relaxation). The successor must be
  later in `order_manifest.txt` than both writers (2.1.4 @79, 3.0.2 @82 < 3.2.0a4 @91) and must not
  itself be superseded.

### IC-02 — Red-first proof across ledger shapes

- **Purpose**: Prove through the production entry point that a post-cutover project gains no command
  files, that every ledger shape nets to the same end state, that a legacy project's stale local
  copies are still retired, and that user files are untouched.
- **Relevant requirements**: FR-001, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, SC-001, SC-002
- **Affected surfaces**: `tests/specify_cli/upgrade/test_retired_command_writers_6547.py`
- **Sequencing/depends-on**: the test is authored and observed red *before* IC-01 lands; it does not
  import the helper under test in place of the runner.
- **Risks**: the fixture must not depend on `~/.claude` state of the machine. Build the "generated
  local file" by content with a version marker rather than by running a writer first, and do not
  assert on `~/.kittify` presence; the retirement path's "keep" branch is what FR-004 pins.

### IC-03 — Operator-facing documentation

- **Purpose**: Tell a project owner that an upgrade no longer reintroduces the retired project-local
  commands and that no local action is needed, referencing #6547.
- **Relevant requirements**: FR-007
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` `[Unreleased]`; the upgrade reference doc that
  describes project-global command installation
- **Sequencing/depends-on**: IC-01
- **Risks**: the changelog lead must be impact-first, bold, `(#6547)`, before/after, under 1,200
  characters; root `CHANGELOG.md` is a symlink, do not add a second file.

## Testing Strategy

| Level | What | Command |
|---|---|---|
| Red-first regression | `test_retired_command_writers_6547.py` through `MigrationRunner.upgrade` | `uv run pytest tests/specify_cli/upgrade/test_retired_command_writers_6547.py -q` |
| Table invariants | existing `test_gitignore_backfills_superseded_6589.py` extended | `uv run pytest tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py -q` |
| Neighbouring upgrade suite | ledger, backfill, order manifest, migration robustness | `uv run pytest tests/specify_cli/upgrade -q -m "not heavy"` |
| Lint/type | ruff + mypy on the touched files | `uv run ruff check …`, `uv run mypy src/specify_cli/upgrade/supersession.py` |

No heavy suite is run locally; CI owns the full sweep (NO_FULL_HEAVY_SUITES_IN_MISSION).
