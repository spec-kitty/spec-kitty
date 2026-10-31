# Work Packages: Retry a residue-safe successor when its predecessor did not settle

**Inputs**: Design documents from `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

**Prompt Files**: `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/tasks/WP0x-*.md`

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows, not checkboxes. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`

---

## Work Package WP01: The retry rule and the red-first pins (Priority: P1)

**Goal**: A residue-safe successor is settled only when its superseded predecessor's recorded
outcome proves the repair ran, in selection and in the runner's skip gate, through one predicate;
the pinned `C-006` case passes without `xfail`, and runner-level coverage proves the retry applies
once and never replays a completed repair.
**Independent Test**: `uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py tests/specify_cli/upgrade/test_successor_retry_6688.py -q` passes, and the same suite is red for the retry cases with the rule reverted.
**Prompt**: `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/tasks/WP01-retry-rule-and-pins.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003

### Included Subtasks

T001 Record the red: run the pinned `C-006` case with `--runxfail` on the mission branch and keep the failure output
T002 Add `predecessor_id` to `BaseMigration` (documented ClassVar) and qualify `reselect_when_recorded` through one registry helper, with an empty-id guard before any ledger read
T003 Add the predecessor conjunct to `registry._settled_in_view` and the public `predecessor_outcome_settled` helper that mirrors `settled_in_selection_view`'s adoption projection
T004 Declare `predecessor_id = PREDECESSOR_ID` on the 2.0.6 and 3.1.1 successors; confirm the 0.9.0/0.9.1 lane mixin already declares it
T005 Remove the strict `xfail` from `test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run` and confirm both parameters pass
T006 Add runner-level coverage for all four pairs: pre-ledger at 3.2.0, predecessor `failed` and `skipped`, dirty Mission, successor applied and Mission repaired
T007 Add the never-replay case on the same fixture: second `upgrade` applies nothing, `changes_made == []`, tree byte-identical
T008 Add the non-vacuity control: a migration with no `predecessor_id` keeps its settlement, and a settled predecessor keeps the successor inert

### Dependencies

- None (starting package).

### Risks & Mitigations

- The rule must not widen beyond declared successors: T008 pins the empty-`predecessor_id` path.
- The pinned test's second assertion reads the selection-view helper, so T003 (not only T002) is required; a half-fix leaves it red.

---

## Work Package WP02: Record the rule in the ADR and the changelog (Priority: P2)

**Goal**: ADR `2026-10-17-1` carries the retry rule and no longer lists `C-006` as an accepted
residual, and the changelog records the user-facing effect of #6688 under `[Unreleased]`.
**Independent Test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0, the changelog entry names `(#6688)` and is under 1,200 characters, and the ADR amendment states the rule and the revised residual list.
**Prompt**: `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/tasks/WP02-adr-and-changelog.md`
**Requirement Refs**: FR-007, SC-003

### Included Subtasks

T009 Add the ADR amendment for the retry rule (decision, routes rejected, revised residual list) to `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
T010 Add the `[Unreleased]` changelog entry with the impact-first lead and `(#6688)`, before/after, under 1,200 characters
T011 Run the docs freshness check and the legacy-terminology gate

### Dependencies

- WP01 (the rule the documentation describes must exist as implemented).

### Risks & Mitigations

- The ADR is a decision record: the amendment must state what changed and why, not restate the implementation.
- Changelog length and terminology are gated; T011 proves both.

---

## Dependency Graph

```text
WP01 ──► WP02
```
