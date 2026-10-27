# Tasks: Activate output and identity

**Mission**: `activate-output-and-identity-01M5ZA9X` · **Planning base / merge target**: `issue-6457-activate-output-identity`
**Inputs**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Tidy-first: preservation step returns a value object carrying the unresolved reason (no output change) | WP01 | |
| T002 | Red-first CLI/engine tests for #6457 (mission-type, unresolved kind, "Now listed" line) | WP01 | |
| T003 | `--only` replaces preservation warnings; mission-type absent key = nothing in force; reasoned unresolved warning | WP01 | |
| T004 | `ActivationResult.listed` + CLI "Now listed for <kind> (N): ..." line | WP01 | |
| T005 | Red-first tests for the skill freeze warning (plain absent, plain present, `--only`, toolguide control) | WP01 | |
| T006 | Engine: org-required freeze warning for "required"-when-absent kinds on both paths; drop `--only` advice for them | WP01 | |
| T007 | WP01 gates: ruff, format, mypy, complexity, targeted + blast radius tests | WP01 | |
| T008 | Resolver test pinning stem-first gating with positive control | WP02 | [P] |
| T009 | Doc note in `org-doctrine-layer.md` §Precedence: a file name beats a declared id regardless of layer | WP02 | [P] |
| T010 | Link the note from `_gated` docstring in `resolver.py` | WP02 | [P] |
| T011 | Fix `PACK_LEVEL_MISSING` clause in `docs/context/governance.md` (Pack Level) | WP03 | [P] |
| T012 | Fix `PACK_LEVEL_MISSING` clause in `docs/context/charter.md` (Charter Pack) | WP03 | [P] |
| T013 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entries for #6457, #6458, #6459, #6403; `make docs-lint` | WP03 | |
| T014 | Red-first all-writers stem test (org + project stem≠id fixtures, built-in directive) | WP04 | |
| T015 | `IdentityIndex`: accept URNs; index built-in step contracts | WP04 | |
| T016 | Effective set emits stems (#6435); re-pin `test_effective_set.py` carve-out | WP04 | |
| T017 | Presets + org-required normalisation store stems; no-stem token kept with warning | WP04 | |
| T018 | Remove compensating stem mappings (`_narrow_inputs`, interview `_stem_spelled_effective`); re-pin `_ORG_ID` carve-outs | WP04 | |
| T019 | WP04 gates (changelog line for #6527/#6435 added at closeout; CHANGELOG is WP03-owned) | WP04 | |
| T020 | Red-first tests: compile accepts URN/declared id/project layer, still fails on unknown; consistency-check false unknowns | WP05 | |
| T021 | Compile resolves through `IdentityIndex` (#6433) | WP05 | |
| T022 | Consistency check through one `IdentityIndex`; warn-and-keep; single report per unknown; reverse paradigm parity | WP05 | |
| T023 | Retire `resolve_artifact_urn` fallbacks the index now covers; WP05 gates (changelog line at closeout) | WP05 | |

## WP01 — `charter activate` output: `--only` consistency and org-required freeze warning

- **Prompt**: [tasks/WP01-activate-output.md](./tasks/WP01-activate-output.md)
- **Goal**: FR-001..FR-007. `--only` prints only narrow lines plus what it wrote; skill activation warns that org-required skills are frozen.
- **Priority**: P1 · **Independent test**: the CLI tests in T002/T005.
- **Subtasks**:

T001 Tidy-first preservation value object (WP01)
T002 Red-first #6457 tests (WP01)
T003 `--only` warning selection (WP01)
T004 "Now listed" line (WP01)
T005 Red-first #6458 tests (WP01)
T006 Freeze warning in the engine (WP01)
T007 Gates (WP01)

- **Sketch**: T001 commit first (behaviour-preserving, existing tests green) → T002 red → T003/T004 green → T005 red → T006 green → T007.
- **Dependencies**: none. **Risks**: written lists must not change (assert them in every test).

## WP02 — Pin and document stem-first activation gating (#6459)

- **Prompt**: [tasks/WP02-stem-first-gating.md](./tasks/WP02-stem-first-gating.md)
- **Goal**: FR-008, FR-009.
- **Subtasks**:

T008 Resolver pinning test (WP02)
T009 Layering doc note (WP02)
T010 Docstring link (WP02)

- **Dependencies**: none. **Parallel** with WP01 and WP03.

## WP03 — Glossary `PACK_LEVEL_MISSING` correction and changelog (#6403)

- **Prompt**: [tasks/WP03-glossary-and-changelog.md](./tasks/WP03-glossary-and-changelog.md)
- **Goal**: FR-010 plus the mission's changelog entry.
- **Subtasks**:

T011 governance.md Pack Level (WP03)
T012 charter.md Charter Pack (WP03)
T013 Changelog + docs-lint (WP03)

- **Dependencies**: none (changelog text describes the agreed behaviour; reviewer checks it against WP01/WP02 at consolidation).

## WP04 — One stored activation spelling: stems (#6527 local, #6435)

- **Prompt**: [tasks/WP04-stem-spelling.md](./tasks/WP04-stem-spelling.md)
- **Goal**: FR-011..FR-015.
- **Subtasks**:

T014 All-writers test (WP04)
T015 IdentityIndex URN + step contracts (WP04)
T016 Effective set stems (WP04)
T017 Presets and org-required stems (WP04)
T018 Remove compensations (WP04)
T019 Gates + changelog (WP04)

- **Dependencies**: WP01 (shared `pack_manager.py`).

## WP05 — Compile and consistency check through the identity index (#6433)

- **Prompt**: [tasks/WP05-compile-consistency-identity.md](./tasks/WP05-compile-consistency-identity.md)
- **Goal**: FR-016, FR-017.
- **Subtasks**:

T020 Red-first tests (WP05)
T021 Compile (WP05)
T022 Consistency check (WP05)
T023 Fallback retirement, gates, changelog (WP05)

- **Dependencies**: WP04.

## MVP

WP01 (the operator-visible defect).
