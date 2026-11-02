---
description: "Work package task list for #6954 — three upgrade migrations and the operator's home"
---

# Work Packages: upgrade — three migrations read the operator's home directly

**Inputs**: Design documents from `kitty-specs/upgrade-empty-home-command-migrations-01M6EJQR/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: Required. This mission exists to add a regression test; every code change is
red-first through the pre-existing `upgrade` entry point.

**Organization**: Three work packages: the red-first tests, the fix they prove, and the
changelog fragment (which needs the PR number, so it lands after the draft PR exists).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Red-first measurement of the three migrations

**Goal**: A new test module that measures all three migrations at the real `upgrade`
entry point under an empty `SPEC_KITTY_HOME`, fails on the current code for the
home-dependent one, and pins the two that are not home-dependent.
**Independent Test**: `uv run pytest tests/upgrade/test_empty_home_command_migrations.py -q`
fails on `main` (file kept under an empty home) and passes after WP02.
**Prompt**: `tasks/WP01-red-first-measurement.md`
**Requirement Refs**: FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, SC-001, SC-002

### Included Subtasks

T001 Create the module skeleton with the `upgrade` command harness (`typer.Typer` test app
plus `CliRunner`), a minimal stamped project fixture, and a ledger seeder that records the
three migrations as `skipped` and everything else as `success`.
T002 [P] Add the converged-project regression: converge, un-bootstrap the home, run
`upgrade --project`, assert empty porcelain and an unchanged `HEAD`.
T003 Add the red test: a stamped project with one version-marked project-local command
file must have that file removed under an empty home, and the removal auto-committed.
T004 Add the home-equivalence test: the same commit run under a bootstrapped home and an
empty home leaves identical tracked state (positive control for T003).
T005 [P] Add the hold-rule test: a project-local file with no version marker is preserved
for manual review in both homes (NFR-003).
T006 [P] Add the template-source pin for `m_2_1_3` and `m_2_1_4`: the resolver returns a
packaged-doctrine path, not a path below `SPEC_KITTY_HOME`, and the answer is unchanged
when the home is bootstrapped.
T007 Run the module against `main`'s source and record the failing assertions in the
mission's tracer files (red evidence).

### Implementation Notes

- Copy the harness shape from `tests/upgrade/test_upgrade_integration.py`
  (`_test_app`/`_runner`), not from an older mission.
- Use the `canonical_home` fixture for `SPEC_KITTY_HOME` (R1a owner); request it, never pin
  the variable locally and never patch `Path.home`.
- Seed the three records as `skipped`: `success` settles a migration and the ledger never
  re-evaluates it, so a `success` fixture cannot measure these three.
- No `pytest.mark.skip`/`xfail` anywhere; a red test stays red until WP02.

### Parallel Opportunities

- T002/T003/T004 share the harness but touch distinct tests; T005/T006 are independent
  files-or-functions once the harness exists.

### Dependencies

- None (starting package).

### Risks & Mitigations

- `Path.home()` is not controllable here: assert tracked state, not the operator home.
- Slow fixture setup: keep git operations batched; no extra `upgrade` runs per test.

---

## Work Package WP02: Stamp-first classification in the globalization migration

**Goal**: `_SafeGlobalizeCommandsBase` decides `keep` vs `remove` from the project's own
stamp for stamped projects, keeping the home checks for unstamped/legacy shapes and using
the canonical global command directory where the home is still consulted.
**Independent Test**: WP01's module goes green; existing migration tests stay green.
**Prompt**: `tasks/WP02-stamp-first-classification.md`
**Requirement Refs**: FR-001, FR-002, FR-006, NFR-001, NFR-003, SC-001, SC-003, SC-004

### Included Subtasks

T008 Add a stamp reader/decision helper in `m_3_1_2_globalize_commands.py` that answers
"is this project past the command-globalization boundary" from `ProjectMetadata` and
`self.target_version`, treating an unparseable or non-string stamp as "not dated".
T009 Wire the helper into `apply()`/`_classify()` so a dated project skips the
`_global_runtime_present()` and exact-global-file checks, while an undated one keeps them.
T010 Route the exact-global-file check through
`specify_cli.runtime.agent_commands.get_global_command_dir()` (agent key from
`AGENT_DIR_TO_KEY`), keeping the historical path shape only for roots with no agent key.
T011 Add unit tests for the helper (dated, undated, legacy-dated, numeric stamp) and for
`_classify` ignoring the home on a dated project; run the `tests/upgrade/` targets for the
three migrations and `compat`.

### Implementation Notes

- Threshold is `self.target_version`, so `3.2.0a4_safe_globalize_commands` inherits the
  same rule without a second constant.
- Never raise on a bad stamp: `InvalidVersion` and `TypeError` both mean "cannot date".
- The `_HOLD` rule stays first: no marker means user-authored, in every case.

### Parallel Opportunities

- T008/T010 are independent; T009 depends on T008.

### Dependencies

- WP01 (the red tests must exist and fail first).

### Risks & Mitigations

- Removing based on the stamp deletes project-local generated copies on a machine whose
  home has no global tree yet; the CLI recreates them at the next command. State the
  trade-off in the changelog fragment.
- Shared base class: check both subclasses' tests.

---

## Work Package WP03: Changelog fragment and PR-surface closeout

**Goal**: A per-PR changelog fragment in the required shape, naming the behaviour change
and the trade-off.
**Independent Test**: `uv run python -m scripts.docs.check_changelog_style` (or the CI
changelog gate) accepts the fragment; the PR body validates.
**Prompt**: `tasks/WP03-changelog-fragment.md`
**Requirement Refs**: C-003, FR-001
**Owned paths**: `docs/changelog/unreleased/`

### Included Subtasks

T012 Write `docs/changelog/unreleased/<pr>.fixed.md` with the PR number once the draft PR
exists: bold impact-first lead with `(#6954)`, before/after, the accepted trade-off, and
"what to do: nothing".
T013 Confirm no `[Unreleased]` entry was added to `docs/changelog/CHANGELOG.md`, and run
the changelog style gate plus `check_docs_freshness --ci`.

### Implementation Notes

- Read `docs/changelog/unreleased/README.md` for the required shape before writing.
- The fragment filename uses the PR number, not the issue number.

### Dependencies

- WP01, WP02, and a created draft PR (the number).

### Risks & Mitigations

- The old `[Unreleased]` shape is rejected by `check_changelog_style`; never edit
  `CHANGELOG.md` directly.
