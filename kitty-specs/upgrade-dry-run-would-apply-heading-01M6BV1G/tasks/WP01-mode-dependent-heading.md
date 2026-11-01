---
work_package_id: WP01
title: The mode-dependent heading and its corrected goldens
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6234-upgrade-dry-run-would-apply-heading
merge_target_branch: issue-6234-upgrade-dry-run-would-apply-heading
branch_strategy: Planning artifacts for this mission were generated on issue-6234-upgrade-dry-run-would-apply-heading. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6234-upgrade-dry-run-would-apply-heading unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Renderer and assertions
history:
- at: '2026-11-01T15:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/upgrade.py
- tests/upgrade/test_upgrade_outcome_rendering.py
- tests/upgrade/test_dry_run_sequenced_verdict_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6234'
---

# Work Package Prompt: WP01 – The mode-dependent heading and its corrected goldens

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

`spec-kitty upgrade --dry-run` prints `DRY RUN - No changes were made`, then an unconditional
green `Migrations applied:` heading with a green `✓` on every migration it would have applied
(#6234). The output says nothing was applied and that something was. The reporter offered two
acceptable resolutions: rename the section (e.g. `Migrations that would be applied:`) with a
non-success marker, or drop the section. This WP takes the first — the list is useful, the claim
is wrong.

Done when:

- In a dry run the migration list is headed `Migrations that would be applied:` in yellow and
  each entry carries a yellow `→` marker.
- In a real run the list is still headed `Migrations applied:` in green with green `✓`, and the
  captured output equals the unedited `_GOLDEN_APPLIED` byte for byte.
- The heading and marker are chosen **once**, from `result.dry_run`, in
  `_display_upgrade_results` — the function that already gates the `DRY RUN` panel on it.
- `_GOLDEN_APPLIED_DRY_RUN` and the sequenced-verdict CLI assertion hold the corrected text,
  with `#6234` cited where the reason belongs; no assertion is deleted, skipped or xfailed.
- An empty applicable list still renders no heading at all (selection, not force-printing).

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/6234>
- Spec / plan / research / quickstart:
  `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/{spec,plan,research,quickstart}.md`
- Current renderer:
  `src/specify_cli/cli/commands/upgrade.py::_display_upgrade_results` prints the panel
  (`if result.dry_run:`), then `_print_upgrade_section("[green]Migrations applied:[/green]",
  result.migrations_applied, "  [green]✓[/green] ")`, then the skipped section, then
  `_print_predicted_verdicts(result)`.
- `_print_upgrade_section(header, items, item_prefix)` emits nothing when *items* is empty.
- Assertions that mention the heading today:
  - `tests/upgrade/test_upgrade_outcome_rendering.py` — `_GOLDEN_APPLIED` (real run, **do not
    edit**) and `_GOLDEN_APPLIED_DRY_RUN` (preview, **edit on purpose**).
  - `tests/upgrade/test_dry_run_sequenced_verdict_cli.py:80` — `assert "Migrations applied:" in
    result.output` on a `--dry-run` run, plus the module docstring at line 8.
- Comment/docstring mentions that must not be left stale: the `_print_predicted_verdicts`
  docstring says "the operator cannot tell the two apart in ``Migrations applied:``" and
  `src/specify_cli/upgrade/runner.py:620` refers to `Migrations applied:` by name. The runner
  comment is only a comment; reword it to the mode-neutral "the applied list" so it cannot go
  stale (no behaviour change in that file — it is **outside** this WP's owned files; if you
  decide it is worth touching, record the one-line rationale and keep it to the comment).

Constraints:

- **C-001 / C-002**: presentation only. Selection (`MigrationRegistry.get_applicable`, the
  ledger), `order_manifest.txt`, `detect()`/`apply()` bodies, `--json`, `--plan-json` and the
  frozen `compat-planner.json` contract are untouched. No new JSON key, no exit-code change.
- **C-004**: never weaken a gate. Retarget assertions, never delete or xfail them.
- **C-005**: the closing line stays `Dry run complete — no changes applied. (<from> -> <to>
  previewed)` (ADR `docs/adr/4.x/2026-10-04-3-upgrade-reports-one-outcome.md`).
- **NFR-002**: `_display_upgrade_results` still never raises and does no I/O beyond
  `console.print`.
- The skipped section (`Migrations skipped (already applied or not needed):` with `○`) keeps its
  wording: it is accurate on the pre-run tree (research D5). Do not "fix" it in this WP.

## Branch Strategy

- **Strategy**: single checkout; planning artifacts were generated on
  `issue-6234-upgrade-dry-run-would-apply-heading`, and completed changes merge into the same
  branch, which is the PR head.
- **Planning base branch**: `issue-6234-upgrade-dry-run-would-apply-heading`
- **Merge target branch**: `issue-6234-upgrade-dry-run-would-apply-heading`

## Subtasks & Detailed Guidance

### Subtask T001 – Red first

- **Purpose**: The failure must exist through the pre-existing entry point before the fix
  (DIRECTIVE_034).
- **Steps**: In `tests/upgrade/test_upgrade_outcome_rendering.py`, first add the corrected
  expectations (T003's text) **without** touching the source, run
  `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q`
  and capture the failure diff (it must show `-Migrations applied:` /
  `+Migrations that would be applied:`). Keep that capture in the WP history note. If a full
  run of the module is slow (it is: the fixture inits a git project per test), `-k` narrows it.
- **Files**: `tests/upgrade/test_upgrade_outcome_rendering.py`
- **Notes**: Do not hand-build expected output from the source; read the captured diff and fix
  only what the change is supposed to change.

### Subtask T002 – The one decision site

- **Purpose**: Make the dry run say what it is, without a second source of truth.
- **Steps**: In `_display_upgrade_results`, extend the existing `if result.dry_run:` branch to
  also choose `applied_header` and `applied_prefix`; keep the real-run pair in the `else`.
  Target shape:

  ```python
  if result.dry_run:
      console.print(Panel("[yellow]DRY RUN[/yellow] - No changes were made", border_style="yellow"))
      applied_header = "[yellow]Migrations that would be applied:[/yellow]"
      applied_prefix = "  [yellow]→[/yellow] "
  else:
      applied_header = "[green]Migrations applied:[/green]"
      applied_prefix = "  [green]✓[/green] "

  _print_upgrade_section(applied_header, result.migrations_applied, applied_prefix)
  ```

- **Files**: `src/specify_cli/cli/commands/upgrade.py`
- **Notes**: Keep the function's docstring accurate (it says it renders "the dry-run panel and
  the migration lists"); extend it with the mode-dependent heading in one clause. Keep the
  function below the cyclomatic ceiling of 15 — it gains one `if/else`.

### Subtask T003 – The golden becomes an oracle

- **Steps**: Change exactly two lines of `_GOLDEN_APPLIED_DRY_RUN` (`Migrations applied:` →
  `Migrations that would be applied:`, `  ✓ ` → `  → `). Update the comment above it and
  `test_golden_applied_dry_run`'s docstring to say the golden now rules on the wording with
  `#6234` cited, rather than merely characterising pre-existing behaviour. Leave
  `_GOLDEN_APPLIED` and `test_golden_applied_run` untouched.
- **Files**: `tests/upgrade/test_upgrade_outcome_rendering.py`

### Subtask T004 – The sequenced-verdict CLI assertion

- **Steps**: In `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`, retarget
  `assert "Migrations applied:" in result.output` to the dry-run heading and add
  `assert "Migrations applied:" not in result.output`, so the test proves both the corrected
  word and the absence of the contradiction. Update the module docstring (line 8) to match.
- **Files**: `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`
- **Notes**: This module's fixture registers two real migrations and asserts a predicted
  verdict; keep its existing assertions intact, only the heading word changes.

### Subtask T005 – Stale comment

- **Steps**: Reword the `_print_predicted_verdicts` docstring sentence that names
  ``Migrations applied:`` to "the run's applied list", so it is true in both modes.
- **Files**: `src/specify_cli/cli/commands/upgrade.py`

### Subtask T006 – Verification

- **Steps**:
  - `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -q`
  - `uv run --frozen pytest tests/upgrade/test_dry_run_sequenced_verdict_cli.py -q`
  - `uv run --frozen pytest tests/architectural/test_upgrade_outcome_single_rendering.py -q`
  - `uv run --frozen ruff check src/specify_cli/cli/commands/upgrade.py tests/upgrade/test_upgrade_outcome_rendering.py tests/upgrade/test_dry_run_sequenced_verdict_cli.py`
  - `uv run --frozen ruff format --check --force-exclude` on the same files
  - `uv run --frozen mypy src/specify_cli/cli/commands/upgrade.py` (repo config)
- **Notes**: `tests/upgrade/test_upgrade_outcome_rendering.py` takes ~3 minutes — it inits a git
  project per test. Do not run `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Test Strategy

Both modes are already pinned end to end by the same fixture and the same stubbed migration, so
the golden pair **is** the positive control: if a change renames the heading in both modes,
`_GOLDEN_APPLIED` fails and the edit is caught. The dry-run assertions additionally assert the
absence of `Migrations applied:`, so a revert fails even if someone regenerates the golden from
the bad output (half-by-half proof: the positive half is the real-run golden, the negative half
is the absence assertion).

## Risks & Mitigations

- **Renaming both modes** → caught by the unedited `_GOLDEN_APPLIED`.
- **Regenerating the golden from whatever the code printed** → the T001 diff capture is the
  guard: the two changed lines must be the only differences, and they must match the spec's
  wording.
- **Tidying the skipped heading** → out of scope; the review checks for it.
- **Adding a second heading source** (e.g. a helper parameter a caller passes) → the design is
  one `if/else`; a parameter would let a caller mismatch heading and marker.
- **Slow suite** → `-k` filters for the inner loop, one full module run at the end.

## Review Guidance

- Is the heading/marker pair chosen once, from `result.dry_run`, in the renderer?
- Does `_GOLDEN_APPLIED` remain byte-identical to its pre-mission text?
- Does any test now skip, xfail, or lose an assertion instead of retargeting it?
- Does the dry-run output still end on the ADR's closing line, and still write nothing?
- Are the two changed golden lines the only golden change?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done` and add
history notes as you go (`spec-kitty agent tasks add-history WP01 --note "..."`).
