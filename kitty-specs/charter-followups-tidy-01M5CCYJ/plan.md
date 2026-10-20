# Implementation Plan: Charter follow-ups tidy-up (#6539-#6543)

**Branch**: `tidy-charter-6539-followups` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)
**Input**: `kitty-specs/charter-followups-tidy-01M5CCYJ/spec.md`

## Summary

This plan closes the five #6511 follow-ups with small, local changes.

**#6539, migration repository requirement.** `BaseMigration` gains a declared `requires_git_repository` ClassVar. The runner checks it once, before `detect()`. The `apply()`-level `NotInsideRepositoryError` catch goes, so a raise inside `apply()` becomes a recorded `failed`.

- An execution-based audit decides which shipped migrations declare the flag: the full registry upgrade on a non-git project with the catch removed.
- The audit runs because `charter.activation.sync` reaches `resolve_canonical_repo_root` transitively, and grep misses such callers.

**#6540 + #6542, language settlement.**
- The settlement moves to a new module, `charter.activation.language_settlement`. It imports `language_authority` and `evidence.code_reader` at module level, which removes the deferred import and the hidden cycle.
- `settle_project_languages` becomes pure: it decides and returns, and writes nothing.
- A new `store_language_settlement` performs the write. `charter interview` calls it immediately after `write_interview_answers`.

**#6541, seam.** A derived `LANGUAGE_TOKENS: tuple[str, ...]` (plain tokens, declared in `language_catalog`) goes on `charter.offering.api`, with a `PUBLIC` census disposition and a facade re-export.

**#6543, reconcile tests.** A test pair covers reconcile's table-edge classification.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, ruamel.yaml, pytest (existing; no new dependencies)
**Storage**: files: `.kittify/config.yaml`, the interview answers file, `.kittify/migration-ledger.jsonl`
**Testing**: pytest with red-first, issue-pinned repro tests, converted to focused unit tests; architectural gates (pytestarch, AST)
**Target Platform**: the spec-kitty CLI (Linux, macOS, Windows)
**Project Type**: single project (`src/` layered: kernel ← charter ← … ← specify_cli)
**Performance Goals**: none new. Interview and upgrade wall-clock are unchanged.
**Constraints**:
- Zero new suppressions.
- Complexity ≤ 15.
- Existing single-language evidence and bundle hashes are byte-identical.
- Settled operator decisions (C-001 to C-005).
**Scale/Scope**: about 8 source files and about 10 test files. No dependency changes, so the supply-chain controls are not applicable.

## Charter Check

- **Single canonical authority:**
  - one settlement module owns the decide-and-write flow;
  - the language vocabulary stays in `language_catalog`;
  - the repository requirement is declared on the migration (one fact, one place). PASS.
- **Architectural alignment:**
  - the new module sits in `charter.activation` (layer unchanged);
  - the seam widening goes through the facade, per C-001 of `api.py`;
  - `specify_cli` keeps importing only via `charter.activation.api`. PASS.
- **ATDD / red-first:** every `[build]` FR has a failing test first (NFR-003). PASS.
- **Canonical sources:** the spec, plan and tasks come from the CLI. PASS.
- **Shipped-migration edit (DIRECTIVE_044):** justified by operator decision `migration_flag_ledger_drift`. The drift is audit-only and documented (C-002).

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-followups-tidy-01M5CCYJ/
├── spec.md
├── plan.md
├── research.md
├── checklists/requirements.md
├── decisions/
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/upgrade/
├── migrations/base.py                       # + requires_git_repository ClassVar
├── migrations/m_3_2_0rc35_unified_bundle.py # declares the flag (+ any audited migration)
└── runner.py                                # pre-detect gate; apply() catch removed
src/charter/activation/
├── language_settlement.py                   # NEW: settle (pure) + store
├── language_authority.py                    # loses settlement code + the deferred import
├── evidence/code_reader.py                  # unchanged imports (authority only)
└── api.py                                   # re-exports moved symbols + store
src/charter/offering/api.py                  # + LANGUAGE_TOKENS
src/charter/offering/shared/language_catalog.py # + LANGUAGE_TOKENS
src/charter/<facade>                         # + LANGUAGE_TOKENS re-export (facade chosen in the WP)
src/specify_cli/cli/commands/charter/interview.py  # store after write_interview_answers
tests/specify_cli/upgrade/test_runner_not_a_git_repository.py
tests/charter/test_language_settlement.py (new) / test_configured_languages.py
tests/specify_cli/cli/commands/charter/test_interview_languages.py
tests/architectural/test_charter_activation_api_reexport.py, test_doctrine_census.py
tests/charter/synthesizer/test_synthesize_reconcile.py
```

**Structure Decision**: single project. New code lives beside the code it replaces.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Editing shipped migration modules (DIRECTIVE_044) | The repository requirement is a fact about the migration; operator decision `migration_flag_ledger_drift` | A runner-side id list keeps the fact apart from the migration, so there are two places to keep in step |

## Implementation Concern Map

### IC-01: Migration repository requirement

- **Purpose**: A migration that needs a git repository declares it. The runner skips it before any step outside a repository. An `apply()`-time repository error is a recorded failure.
- **Relevant requirements**: FR-001, FR-002, FR-003; C-002, C-004; SC-001, SC-002
- **Affected surfaces**:
  - `src/specify_cli/upgrade/migrations/base.py`
  - `src/specify_cli/upgrade/runner.py` (main loop; the worktree loop is out of scope, since a worktree is always inside a repository)
  - shipped migrations flagged by the audit, at minimum `m_3_2_0rc35_unified_bundle.py`
  - `tests/specify_cli/upgrade/`
  - docs: `CLAUDE.md`/`AGENTS.md` "Writing Migrations" (operator-owned text; propose the line in the PR rather than editing if a gate forbids it), the ADR 2026-10-17-1 note, the changelog
- **Sequencing/depends-on**: none
- **Risks**:
  - Missing a transitive raiser would bring #6437 back as a recorded `failed`. The full-registry non-git audit is the guard and becomes a permanent test.
  - The `content_hash` drift is accepted.

### IC-02: Language settlement: one-way dependency and deferred write

- **Purpose**: Remove the hidden import cycle, and write `languages:` only together with the interview answers.
- **Relevant requirements**: FR-004, FR-005, FR-006; C-005; SC-003, SC-005
- **Affected surfaces**:
  - new `src/charter/activation/language_settlement.py`
  - `language_authority.py`, `charter/activation/api.py`
  - `src/specify_cli/cli/commands/charter/interview.py`
  - tests: `tests/charter/test_configured_languages.py`, `tests/specify_cli/cli/commands/charter/test_interview_languages.py`
  - gate: `tests/architectural/test_charter_activation_api_reexport.py`
- **Sequencing/depends-on**: none. #6540 and #6542 must be one concern because both rewrite `settle_project_languages`.
- **Risks**:
  - Every abort path between the language step and the answers write: `typer.Abort`, Decision Moment errors, `--defaults`, JSON mode.
  - Ordering when the config write fails after the answers are written: surface it, never swallow it.

### IC-03: `LANGUAGE_TOKENS` on the offering seam

- **Purpose**: Make the plain token list a public offering contract; keep `LANGUAGES`, `LanguageSpec` and the family expansion internal (decision `seam_language_export_shape`).
- **Relevant requirements**: FR-007, FR-008; C-003; SC-004
- **Affected surfaces**:
  - `src/charter/offering/shared/language_catalog.py` (`LANGUAGE_TOKENS`)
  - `src/charter/offering/api.py`
  - a charter facade
  - `tests/architectural/test_doctrine_census.py` (DISPOSITION)
  - `tests/architectural/test_charter_offering_public_surface.py`
  - ADR `docs/adr/4.x/2026-10-03-1-*` amendment note
- **Sequencing/depends-on**: none. It must not edit `language_authority.py` (owned by IC-02).
- **Risks**:
  - The seam is called frozen, so the amendment note is required.
  - The corpus case is filed against #6099, not built here.

### IC-04: Reconcile table-edge classification tests

- **Purpose**: Prove that reconcile classifies table edges the same way the validation gate does.
- **Relevant requirements**: FR-009
- **Affected surfaces**: `tests/charter/synthesizer/test_synthesize_reconcile.py`
- **Sequencing/depends-on**: none
- **Risks**: none (test-only)
