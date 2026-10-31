# Work Packages: A clean consolidation rollback leaves no stale baseline (#6770)

**Inputs**: Design documents from `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (grounding + decisions)

**Tests**: Required. This is a defect fix: the failing regression is authored and observed red
before the fix lands (charter, ATDD-First Discipline; DIRECTIVE_034), and it is kept as a
`regression` test afterwards.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable in order.

**Prompt Files**: `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/tasks/WPxx-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/specify_cli/`, `tests/`, `docs/`.

---

## Work Package WP01: Red-first regression for the stale baseline (Priority: P1)

**Goal**: Pin the reported behaviour as an executable regression — a reconciliation FAIL that
rolls back fully leaves a record, the next run reuses the stale window base and rolls the
target back over an intervening commit, and a plain `--abort` refuses — and re-pin the two
tests that currently assert the opposite ("a fully rolled-back run keeps its record").
**Independent Test**: `uv run pytest tests/terminus/test_rollback_record_rebaseline.py -x` runs and **fails**
on the un-fixed tree with the assertions described in each subtask (record present, second run
raises, window base is `T0`), and the two re-pinned assertions fail on the same tree.
**Prompt**: `tasks/WP01-red-first-regression.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, SC-001, SC-002, SC-003

### Included Subtasks

T001 Author `tests/terminus/test_rollback_record_rebaseline.py` with a one-shot reconciliation FAIL on a real LANES mission, then a target commit, then a re-run whose window base is asserted through `phase_claim.build_approved_wp_set`
T002 Add the plain `--abort` assertion to the same fixture: after the clean rollback it must exit 0 and report no active merge state
T003 Re-pin `tests/terminus/test_rollback_door.py::test_record_is_truthful_after_rollback_and_a_rerun_succeeds` to the new expectation (record cleared, re-run still lands both lanes)
T004 Re-pin `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py::_assert_failed_run_restored_the_snapshot` and its docstring to the same expectation
T005 Record the red run (command + the exact failure lines) in the WP history and in the mission's tracer files

### Implementation Notes

- Build on the existing fixtures (`tests/terminus/lanes_fixture.build_lanes_mission`,
  `tests/terminus/conftest.run_terminus`, `tests/terminus/rollback_harness.state_path`) —
  no new fixture library, no mocks of git.
- The gate must fail **once**: wrap the real `MergeOutcomeVerifier.verify` and return a FAIL
  for the first call only, delegating afterwards. A permanently patched verifier would make
  attempt 2 vacuous.
- Assert the window base by wrapping `specify_cli.consolidation.phase_claim.build_approved_wp_set`
  and capturing `excluded_window_base`; the call itself stays the production one.

### Parallel Opportunities

- T001/T002 are one file and sequential; T003/T004 are two different files and can follow in
  either order after T001.

### Dependencies

- None (starting package). WP02 depends on this.

### Risks & Mitigations

- A test that passes on the un-fixed tree proves nothing: run it on the un-fixed tree first and
  paste the failure into the WP history.

---

## Work Package WP02: The rollback door clears a record it has fully undone (Priority: P1)

**Goal**: A rollback whose report says the attempt was undone clears the transaction record
(`state.json` + its post-fix marker) through `clear_state`, so the next run is genuinely fresh
and derives its reconciliation window base from the target's current tip. A partial rollback
keeps the record unchanged. The clear never replaces the original error.
**Independent Test**: `uv run pytest tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_rollback_door.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_executor_rollback_wiring.py tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py -x` passes.
**Prompt**: `tasks/WP02-door-clears-undone-record.md`
**Requirement Refs**: FR-001, FR-002, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Add the "was the attempt undone?" verdict to `RollbackReport` in `src/specify_cli/consolidation/rollback.py`, reusing `fully_restored` semantics and documenting why a verified-landing refusal and a `NOT_RESTORED` branch both keep the record
T002 Clear the record from `_report_rollback` in `src/specify_cli/consolidation/executor.py` when that verdict holds, guarded so a failed clear warns and never replaces the re-raised error, and print one operator line saying the record is gone and the next run starts from the target's current tip
T003 Confirm the partial-rollback shape is unchanged (dirty-target-checkout fixture keeps the record with attempt 1's `pre_mutation_target_sha`)
T004 Run the WP's targeted suites and record command + counts in the WP history; confirm `ruff`/`mypy` on the two changed modules

### Implementation Notes

- `rollback.py` is the single rollback authority; do not add a second rollback or a second
  failure hook (C-002). The clear is the door's last step, after the report is printed.
- `state.clear_state` is the only owner of clearing a record (C-001). Do not unlink files.
- No new persisted field, no migration (NFR-001).
- `--abort` and `resolve._load_or_create_merge_state` are untouched (C-003, `--release-branch`
  recovery keeps its contract).

### Parallel Opportunities

- T001 and T002 are one change in two modules; T003/T004 verify afterwards.

### Dependencies

- WP01 (the failing regression must exist first).

### Risks & Mitigations

- Clearing too eagerly would drop a record that still holds un-restored content. Key the clear on
  the report's own verdict, never on "the target looks restored".
- A failed clear must not mask the operator's real error: mirror
  `phase_claim._clear_fresh_record_on_pre_mutation_exit`.

---

## Work Package WP03: Changelog and recovery docs (Priority: P2)

**Goal**: Tell the operator what a clean rollback now leaves: no record, a re-run based on the
target's current tip, and a plain `--abort` that is a clean no-op.
**Independent Test**: the new `[Unreleased]` entry renders with the `(#6770)` reference under
1,200 characters, and `docs/guides/how-to/recovery/troubleshoot-merge.md` states the new
behaviour with an `updated:` date bump; `uv run python -m scripts.docs.check_docs_freshness --ci`
reports errors=0.
**Prompt**: `tasks/WP03-changelog-and-recovery-docs.md`
**Requirement Refs**: SC-001, SC-002, SC-003

### Included Subtasks

T001 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold, impact-first lead with `(#6770)`, before/after, under 1,200 characters)
T002 Add the "a failed run that rolled back completely leaves no record" subsection to `docs/guides/how-to/recovery/troubleshoot-merge.md` and bump its `updated:` frontmatter date
T003 Run `uv run python -m scripts.docs.check_docs_freshness --ci` and record the result

### Implementation Notes

- `CHANGELOG.md` at the repo root is a symlink to `docs/changelog/CHANGELOG.md`; edit the real file.
- Keep the how-to in its existing voice (what you see / what it means / what to run).

### Parallel Opportunities

- T001 and T002 are different files.

### Dependencies

- WP02 (behaviour must be final).

### Risks & Mitigations

- Do not restate internal symbol names in the changelog; name the user-visible behaviour and the
  record path only.
