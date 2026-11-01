# Mission Specification: `upgrade --dry-run` names its migration list for what it is

**Mission Branch**: `issue-6234-upgrade-dry-run-would-apply-heading`
**Created**: 2026-11-01
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#6234 — `upgrade --dry-run` lists would-run migrations under `Migrations applied: ✓`, directly below its `DRY RUN - No changes were made` banner. Put the preview's list under a heading that says it would be applied, keep the real run's heading as it is, and deliberately re-pin the dry-run characterization golden."

**Governing issue**: [#6234](https://github.com/spec-kitty/spec-kitty/issues/6234) (`priority:P3`, `usability`, `from:qa`, `domain:upgrade`).

### Intent Summary (confirmed before this spec was written)

The operator named the issue and the intended shape: reproduce through the existing CLI
entry point, then make the human dry-run summary stop claiming that migrations were
applied — one heading and one marker chosen from `result.dry_run`, with no change to which
migrations are selected, ordered, or recorded.

- **Primary actor**: the operator previewing an upgrade with `spec-kitty upgrade --dry-run`,
  most often on Windows where a partway failure is expensive.
- **Trigger**: a dry run that would apply at least one migration.
- **Desired outcome**: the dry-run output names the section for what it is
  (`Migrations that would be applied:`), marks entries with a non-success marker, and the
  `DRY RUN - No changes were made` banner is never contradicted six lines later.
- **Invariant**: the real run's output, and every migration's `detect()`/`apply()`
  behaviour, is unchanged; the dry run still writes nothing.
- **Boundary**: this is presentation only. Selection (`MigrationRegistry.get_applicable`,
  the ledger), execution order (`order_manifest.txt`), the JSON payloads and the frozen
  `compat-planner.json` contract are untouched.

## Problem

`spec-kitty upgrade --project --dry-run` prints a `DRY RUN - No changes were made` panel,
then, unconditionally, `Migrations applied:` in green with a green `✓` beside each
migration the run would have applied, then closes with
`Dry run complete — no changes applied.` Read together the output asserts both that nothing
was applied and that two migrations were.

`_display_upgrade_results` (`src/specify_cli/cli/commands/upgrade.py`) adds the dry-run
panel when `result.dry_run` is set, but the heading and the `✓` prefix are not conditioned
on it. The characterisation test
`tests/upgrade/test_upgrade_outcome_rendering.py::test_golden_applied_dry_run` pins the
contradictory text verbatim (`_GOLDEN_APPLIED_DRY_RUN`); its own docstring says it freezes
existing behaviour rather than ruling on the wording, so correcting the wording is a
deliberate update to that golden, not a broken contract.

The reporter could not tell from the human output whether the preview wrote anything, and
offered two acceptable resolutions: rename the section (`Migrations that would be applied:`)
with a non-success marker, or omit it and rely on the Migration Plan table above. This
mission takes the first: the list is useful, it is the judgement that is wrong.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The preview reports what it would apply, not what it applied (Priority: P1)

An operator runs `spec-kitty upgrade --project --dry-run` on a project with pending
migrations. The migration section is headed `Migrations that would be applied:`, its
entries carry a non-success marker rather than a green `✓`, and nothing in the output
claims an application happened. The closing line
`Dry run complete — no changes applied.` now agrees with everything above it.

**Why this priority**: the contradiction is the reported defect; on Windows a partially
applied upgrade is the case an operator previews for, and the preview must not be
ambiguous about whether it wrote.

**Independent Test**: invoke the CLI with `--dry-run` on the stubbed-migration fixture and
assert the rendered output contains the new heading and marker, contains neither
`Migrations applied:` nor a green `✓` line, and still ends on the unchanged closing line.

**Acceptance Scenarios**:

1. **Given** a project with one applicable migration, **When** `upgrade --dry-run` runs,
   **Then** the section heading is `Migrations that would be applied:` and the entry is
   marked with a non-success marker, below the unchanged `DRY RUN` panel.
2. **Given** the same project, **When** the run completes, **Then** the closing line is
   still `Dry run complete — no changes applied. (<from> -> <to> previewed)` and the
   migration is not reported as applied anywhere in the human output.

---

### User Story 2 - The real run's report is unchanged (Priority: P1)

An operator runs the same upgrade for real. `Migrations applied:` with `✓` is still the
heading above the migrations that were applied, because in a real run that is exactly what
happened.

**Why this priority**: the fix must not trade one lie for another. The real run applied
those migrations; its heading is correct and is pinned by `_GOLDEN_APPLIED`.

**Independent Test**: `test_golden_applied_run` passes without touching `_GOLDEN_APPLIED`;
the real-run and dry-run goldens differ only in the sections the two modes genuinely differ
in.

**Acceptance Scenarios**:

1. **Given** a project with one applicable migration, **When** `upgrade` runs without
   `--dry-run`, **Then** the output equals `_GOLDEN_APPLIED` byte for byte.

---

### User Story 3 - The dry-run pins become an explicit, correct oracle (Priority: P2)

A maintainer reads the dry-run characterisation golden and the sequenced-verdict CLI test
and sees the corrected text asserted on purpose, with the reason recorded, so the next
change to this surface has an honest baseline to diff against.

**Why this priority**: the old golden froze the contradiction. Leaving it edited without
saying why re-creates the same trap for the next agent.

**Independent Test**: the two dry-run assertions name the new heading, and the golden's
docstring states that it now rules on the wording (with the issue reference) rather than
merely characterising it.

**Acceptance Scenarios**:

1. **Given** the updated golden, **When** someone reverts the heading choice, **Then**
   `test_golden_applied_dry_run` fails with a diff naming the old heading.
2. **Given** the updated test module docstrings, **When** a reader opens the file, **Then**
   they find the issue number and why the wording is deliberate.

---

### Edge Cases

- **A dry run with no applicable migrations**: the migration lists are empty and
  `_print_upgrade_section` emits nothing — no heading appears in either mode. Unchanged.
- **A dry run where every candidate is skipped**: `Migrations that would be applied:` is
  absent (empty list), the skipped section still renders with its neutral `○` marker, and
  no green `✓` appears anywhere. The heading is only chosen, never force-printed.
- **Predicted verdicts (`#6552`)**: the `Predicted by an earlier migration in this run
  (dry run):` block is a dry-run-only section and keeps its place under the corrected
  heading; its own `•` markers are untouched.
- **`--json` / `--plan-json`**: machine payloads are unchanged; `migrations_applied` keeps
  its key and meaning. This mission touches human rendering only.
- **Markup and `--no-color`**: the heading uses existing rich markup only; no new style is
  introduced, so the no-color rendering changes only in the literal words.
- **Width**: the new heading is longer than the old one; it is a `console.print`ed line (not
  a sized panel), so no width maths changes and the wrap width is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Dry-run heading names the preview | As an operator, I want the dry-run migration list headed `Migrations that would be applied:`, so the section says what it is instead of what did not happen. | High | Open | [build] | no — today the dry run prints `Migrations applied:` |
| FR-002 | Dry-run entries carry a non-success marker | As an operator, I want each predicted migration marked with a non-success marker rather than a green `✓`, so the list cannot read as a record of applied work. | High | Open | [build] | no — today every entry is a green `✓` |
| FR-003 | The real-run report is byte-identical | As an operator, I want a real upgrade's `Migrations applied:` section unchanged, so the fix does not blur the distinction in the other direction. | High | Open | [ratchet] | no — a change that renames both modes fails `_GOLDEN_APPLIED` |
| FR-004 | The dry-run goldens become a deliberate oracle | As a maintainer, I want `_GOLDEN_APPLIED_DRY_RUN` and the sequenced-verdict CLI assertions updated to the corrected text with the reason recorded, so the pinned baseline is right on purpose. | High | Open | [build] | no — reverting the heading breaks the golden |
| FR-005 | One decision site for the heading | As a maintainer, I want the heading and marker chosen once, from `result.dry_run`, in the renderer, so the two modes cannot drift apart through a second source of truth. | Medium | Open | [build] | no — hard-coding two call sites leaves the next edit able to reintroduce the bug |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | The dry run still writes nothing | After a dry run of the fixture project, the tree digest is identical before and after; this change adds no write path and no filesystem access. | Reliability | High | Open |
| NFR-002 | Rendering stays pure | `_display_upgrade_results` still never raises and performs no I/O beyond `console.print`; no new branch may raise or exit. | Reliability | High | Open |
| NFR-003 | Complexity ceiling | The touched functions stay at or below the repository's cyclomatic ceiling of 15; the change adds at most one conditional. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Presentation only | Selection, ordering, ledger records, `detect()`/`apply()` bodies and the exit-code derivation are untouched; nothing in `upgrade/runner.py` or `upgrade/registry.py` changes behaviour. | Technical | High | Open |
| C-002 | No JSON or contract change | `--json`, `--plan-json` and the frozen `compat-planner.json` contract keep their keys, shapes and values; this is the human text renderer only. | Technical | High | Open |
| C-003 | Same-fixture control | The dry-run and real-run goldens are produced by the same fixture and the same stubbed migration, so the pair is a positive control for "only the dry-run wording changed". | Technical | High | Open |
| C-004 | No gate weakening | No test is deleted, skipped or xfailed: the two dry-run assertions are updated to the new expected text, and the real-run goldens are untouched. | Business | High | Open |
| C-005 | ADR 2026-10-04-3 is honoured | The one-outcome dry-run contract in `docs/adr/4.x/2026-10-04-3-upgrade-reports-one-outcome.md` (exit 0, unchanged closing line) still holds; the change makes the body agree with the tail that ADR describes. | Technical | High | Open |

### Key Entities

- **Upgrade outcome rendering**: the migrations-only renderer
  (`_display_upgrade_results`) that draws the dry-run panel, the applied/would-apply list,
  the skipped list and the predicted-verdict block. It reads `UpgradeResult.dry_run`.
- **Dry-run summary**: the human text an operator reads immediately below the
  `DRY RUN - No changes were made` panel: heading, per-migration markers, and the closing
  line rendered by the shared outcome tail.
- **Characterisation golden**: a verbatim expected-output string in
  `tests/upgrade/test_upgrade_outcome_rendering.py` that pins a rendering path end to end;
  `_GOLDEN_APPLIED` (real) and `_GOLDEN_APPLIED_DRY_RUN` (preview).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the golden fixture, the dry-run output contains `Migrations that would be applied:`, contains no `Migrations applied:` and no green `✓`, and keeps the unchanged closing line (today: 1 heading wrong, 1 green `✓` present) — [build] · no-op passable: no
- **SC-002**: The real-run golden `_GOLDEN_APPLIED` and its test pass unedited (0 diffs to that string) — [ratchet] · no-op passable: no
- **SC-003**: Every test file that asserted the dry-run applied heading (`test_upgrade_outcome_rendering.py`, `test_dry_run_sequenced_verdict_cli.py`) asserts the corrected heading; 0 tests are skipped, xfailed or deleted — [ratchet] · no-op passable: no
- **SC-004**: A dry run of the fixture leaves the project tree digest unchanged before and after (today: already true; pinned so the wording fix cannot be bought with a write) — [ratchet] · no-op passable: no
