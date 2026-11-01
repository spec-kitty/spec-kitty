# Tasks — centralized-runtime detection is project local

Mission: `centralized-runtime-detection-is-project-local-01M68ZFE`
Issue: #6551 · Spec: [spec.md](./spec.md) · Plan: [plan.md](./plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Add the red production-path regression test (`upgrade --project --yes` under an empty `SPEC_KITTY_HOME`) | WP01 | |
| T002 | Add helper-level pins: 4.x metadata + no home ⇒ `True`/`False`/`False` | WP01 | |
| T003 | Add the pre-2.0 metadata positive control (still repairs) | WP01 | |
| T004 | Confirm all three new tests fail on the pre-fix predicate | WP01 | |
| T005 | Reorder `uses_centralized_runtime` so project metadata decides first | WP01 | |
| T006 | Re-run the new tests and the existing `tests/upgrade/` suite | WP01 | |
| T007 | Write the `[Unreleased]` changelog entry with the #6551 reference | WP02 | [P] |
| T008 | Record the deferred follow-ups (repair path, other home-reading migrations) | WP02 | [P] |
| T009 | Append the close-out tracer entries | WP02 | [P] |

## WP01 — Project-stamped detection, red-first

**Goal**: A project stamped `>= 2.0.0` answers "centralized runtime" the same way
on a machine with no `~/.kittify`, so `spec-kitty upgrade` stops re-running the
legacy mission migrations and stops committing frozen overrides.

**Priority**: P1 (the whole of #6551)
**Independent test**: `tests/upgrade/test_upgrade_empty_home_noop.py` alone — it
drives the real `upgrade` command with an empty `SPEC_KITTY_HOME` and asserts the
tracked tree is unchanged.
**Dependencies**: none

**Included subtasks**: T001, T002, T003, T004, T005, T006

**Implementation sketch**

1. Write `tests/upgrade/test_upgrade_empty_home_noop.py`, modelled on the
   `tests/upgrade/test_upgrade_integration.py` harness (`typer.Typer` test app +
   `CliRunner`, real git repo, `contextlib.chdir`). The fixture is a project at
   `4.0.0rc8` whose ledger carries the converged `skipped` records for
   `0.6.7_ensure_missions` and `0.12.0_documentation_mission`, with
   `SPEC_KITTY_HOME` pointing at an empty directory. Assert: exit 0,
   `git status --porcelain` empty, `.kittify/missions/` and
   `.kittify/overrides/` absent, and — as the same-fixture positive control — that
   the ledger still records both ids (so "no change" is not "the probe saw
   nothing").
2. Extend `tests/upgrade/test_compat.py` with the 4.x-metadata/no-home case and
   the pre-2.0 positive control.
3. Run the three new tests on the unmodified `compat.py` and capture the red.
4. Reorder `uses_centralized_runtime`: read `ProjectMetadata` first; a readable
   stamp `>= 2.0.0` returns `True`; `InvalidVersion` and missing metadata fall
   through to today's home-based logic unchanged.
5. Re-run: the new tests go green, and the existing `test_compat.py`,
   `migrations/test_m_0_6_7_ensure_missions.py`,
   `test_m_0_12_0_documentation_mission_unit.py` cases stay green.

**Risks**: Reordering must not change the metadata-less answers (FR-005) — the
existing four `test_compat.py` cases are the guard. The integration fixture must
be genuinely converged; a project whose ledger is empty would exercise a
different code path and prove nothing.

## WP02 — Changelog, deferrals and tracers

**Goal**: Record the user-facing fix and the explicitly out-of-scope halves of
the issue.

**Priority**: P2
**Independent test**: `docs/changelog/CHANGELOG.md` contains a `[Unreleased]`
entry citing `#6551`; the three tracer files exist and are appended.
**Dependencies**: WP01

**Included subtasks**: T007, T008, T009

**Implementation sketch**

1. Add the `[Unreleased]` entry: bold impact-first lead ending `(#6551)`, then
   before/after, under 1,200 characters. Root `CHANGELOG.md` is a symlink —
   edit `docs/changelog/CHANGELOG.md`.
2. Record the deferred items in the mission notes for the PR's `## Deferred`:
   repair of already-affected projects (#6548 territory); the
   `2.1.3`/`2.1.4`/`3.1.2` migrations that read the global home directly; the
   ledger-settlement alternative from the issue.
3. Append tracer entries with
   `spec-kitty agent tracer-append --mission <slug> --category ...`.

**Risks**: None material; keep the changelog entry terse so it stays under the
character cap.
