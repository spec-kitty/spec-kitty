# Discovery — golden dry-run order independence (#7030)

## Decisions

### D1. Fix the test seam, not the production preview

The defect is in the golden's inputs, not in `_supporting_repair_preview`'s output. The preview
correctly reports the repair inventory of the isolated home it is asked about; an empty home
genuinely has more to create. The golden must not read that inventory at all. Fixing production
code to make the count "nicer" would be a behaviour change for a test-only defect, and changing
the shared per-worker home fixture (`tests/conftest.py::_isolated_worker_home`) would move an
autouse, whole-suite fixture for one test's convenience.

- Evidence: `src/specify_cli/cli/commands/upgrade.py:1203` (`_supporting_repair_preview`) calls
  `prepare_upgrade_repairs(project_path)` and counts `prepared.effects`; the count is a property of
  the home, not of the render path.
- Evidence: `tests/conftest.py:400` `_isolated_worker_home` is keyed by xdist worker
  (`_worker_home_base(request.config)`), so the home outlives a single test inside one worker —
  exactly the leak the issue measured.

### D2. Stub `upgrade_module._supporting_repair_preview` in the dry-run golden

This is the seam the same module already uses: the matrix rows stub it through
`_stub_incomplete_preview` (`tests/upgrade/test_upgrade_outcome_rendering.py:343`) and
`test_step_dry_run_with_a_complete_preview_prints_the_notice_and_reports_nothing` (:655) returns a
fixed complete-preview sentence, and `tests/upgrade/test_upgrade_integration.py:552` stubs it too.
Using the existing seam keeps one way to make the preview deterministic in this module and adds no
test-only hook to `src/`.

- Consequence: the golden becomes a pure rendering oracle, which is what it already is for the
  migration list and the commit (`_stub_applied_migration`). The live count currently has **no**
  test anywhere — every call site in `tests/` stubs it — so nothing observable is lost.

### D3. Keep the pinned text byte-identical

The expected constant `_GOLDEN_APPLIED_DRY_RUN` does not change. The stub returns the exact
complete-preview sentence the pinned text already contains, so the assertion stays an exact-match
golden and the diff stays one test plus its input.

### D4. Keep a non-vacuous proof that the preview line is still covered

A stubbed preview that the run never consults would silently drop coverage. The golden records the
stub's calls and asserts it was consulted exactly once, so a future refactor that stops previewing
during a dry run fails the golden instead of quietly passing (acceptance-criteria-non-vacuity:
exercise the production path; pair the assertion with a positive control on the same fixture).

## Evidence (grounding on current `main`)

- Clone at `main` = `9aed3a80` (`test(charter): pin the deactivate cascade hint #6873 added to the
  text golden`); issue's base `287a226cfe` is an ancestor, so nothing has superseded it.
- Reproduced the issue's red on this base:
  `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q`
  → `1 failed, 48 deselected` with `- Would repair 1 ...` / `+ Would repair 125 ...`.
- `git log -S"_supporting_repair_preview" --oneline` and the changelog show no merged fix for this
  order dependency; open PR #7023 (#6234) touches `upgrade.py`'s dry-run heading, not this line —
  the issue states so itself, and `git log` on the test file shows no related re-pin.
- No test in `tests/` exercises the live preview count: `rg -n "_supporting_repair_preview" tests/`
  finds only stubs (`test_upgrade_outcome_rendering.py:343,655,669`,
  `test_upgrade_integration.py:552`).

## Open questions (for plan/tasks)

- None blocking. Decide in plan whether the recording stub is a small helper shared by the golden
  and the existing `_stub_incomplete_preview` row, or inline in the golden (prefer the smaller diff
  unless it duplicates logic).
