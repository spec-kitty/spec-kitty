# Work Packages: Synthesize Commit Reminder Names the Whole Write Surface

**Inputs**: Design documents from `kitty-specs/synthesize-commit-reminder-write-surface-01M66FQX/` (spec.md, plan.md, research.md)
**Prerequisites**: plan.md (required), spec.md, research.md

**Tests**: This is a defect fix — the red-first regression test and the seam tests are in scope (FR-003), per the ATDD-first discipline and DIRECTIVE_034.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first e2e regression test: run real synthesize, execute printed safe-commit line, assert `git status --porcelain .kittify/` empty | WP01 | no (first, red) |
| T002 | `append_synthesized_activations` returns warnings + written paths (record path when `_record()` fires; activation target when `_promote` fires) | WP01 | no |
| T003 | Re-export the result type through `charter.activation.api`; adapt `synthesize.py` and `resynthesize.py` callers | WP01 | no |
| T004 | `_print_synthesis_commit_reminder` accepts extra written paths; `_emit_real_run_report` threads them; dedup, stable order | WP01 | no |
| T005 | Seam tests: written-paths reporting matches disk changes (record written, target written, nothing written) | WP01 | yes (after T002) |
| T006 | Adapt existing callers' tests to the new result shape; extend reminder CLI assertions | WP01 | yes |
| T007 | Update governance skill step 7 and `charter-artifact-structure.md` tables to name the record | WP02 | yes |
| T008 | Changelog `[Unreleased]` entry for #6631 | WP02 | yes |

---

## Work Package WP01: Derive the synthesize commit reminder from the write surface (Priority: P1) 🎯 MVP

**Goal**: The activation-append seam reports the paths it wrote; `charter synthesize`'s printed safe-commit recipe names every path the run wrote; an end-to-end regression test pins that invariant generically.
**Independent Test**: On the canonical fixture (explicit `activated_tactics`, `FixtureAdapter`), running the printed command leaves `git status --porcelain .kittify/` empty; a run that writes no activation-surface path names none.
**Prompt**: `/tasks/WP01-reminder-write-surface.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-005, SC-001, SC-002

### Included Subtasks

T001 Red-first e2e regression test (write first, confirm it fails on main's behavior)
T002 Structured append result with written paths in `reach_only.py`
T003 api re-export + adapt the two production callers
T004 Reminder derivation in `_synthesis.py`
T005 Seam tests for written-paths reporting
T006 Adapt existing tests to the new shape; extend reminder assertions

### Implementation Notes

- Red-first: T001 before T002-T004; commit the red test only together with the fix (single PR; the regression test carries `@pytest.mark.regression` once green — see pytest.ini's marker docs).
- T002: track writes inside the synthesis lock; the record path is reported only when `_record()` actually wrote (content changed); the activation target only when `_promote` fired. Repo-relative POSIX paths.
- T004: `_SYNTHESIS_ARTIFACT_PATHS` stays the base list; extra paths append, deduplicated, stable order. The fresh-project seed call site passes no extra paths.
- C-003: `--json` envelopes unchanged.

### Parallel Opportunities

- T005 and T006 can proceed in parallel once T002-T004 land.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Return-shape change breaks warning-assertion tests → keep warnings content byte-identical; adapt shape only.
- The e2e test executes `safe-commit` in-process → follow `tests/specify_cli/cli/commands/test_safe_commit_cli.py` (non-protected initial branch, identity config, `SPEC_KITTY_TEST_MODE` deleted).

---

## Work Package WP02: Skill, doc tables and changelog name the record (Priority: P2)

**Goal**: The governance skill's step 7, the artifact-structure authority and git-tracking tables, and the changelog all name `.kittify/charter/synthesized-artifacts.yaml`, so the CLI reminder and the hand-followed text cannot diverge again.
**Independent Test**: The three surfaces name the record; the changelog entry is under `[Unreleased]`, bold impact-first lead with `(#6631)`, under 1,200 characters.
**Prompt**: `/tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-004, FR-005, C-004, SC-003

### Included Subtasks

T007 Skill step 7 + artifact-structure tables
T008 Changelog entry

### Implementation Notes

- C-004: edit the committed source under `src/charter/offering/skills/spk-charter-governance/references/`; no pack pin bump (the references are not fetched pack content).
- Step 7 should point at the printed command as the authority ("run the command `charter synthesize` printed") rather than restating a path list, so the text cannot drift either.

### Parallel Opportunities

- T007 and T008 are independent of each other; both depend on WP01's final path naming only for review consistency.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Docs-only change tripping a docs gate → run the docs freshness/terminology checks named in the delivery procedure if any doc page (not a skill reference) is added; skill references are not in the docs index.
