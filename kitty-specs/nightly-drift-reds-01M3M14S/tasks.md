# Work Packages: specify_cli out-of-matrix nightly drift reds

**Inputs**: `kitty-specs/nightly-drift-reds-01M3M14S/` (spec.md, plan.md)
**Prerequisites**: plan.md, spec.md (verdict table R1–R23)

**Tests**: Each WP carries its own targeted test surface (NFR-001). No full-directory or `make test-full` runs.

## Subtask Format: `[Txxx] [P?] Description`

---

## Work Package WP01: Colour-independent in-process CLI output (Priority: P1)

**Goal**: Typer's help and usage console is colourless under the autouse plain-console seam (R10–R14).
**Independent Test**: `GITHUB_ACTIONS=true .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_mission_close_guard.py -p no:randomly -q`: red before, green after.
**Prompt**: `/tasks/WP01-colour-independent-cli-output.md`
**Requirement Refs**: FR-001, SC-002

### Included Subtasks

T001 Reproduce R10–R14 red under `GITHUB_ACTIONS=true` (red-first evidence)
T002 Extend `tests/conftest.py::_plain_cli_console_seam` to pin and restore `typer.rich_utils.FORCE_TERMINAL` / `COLOR_SYSTEM`
T003 [P] Refresh the stale "seam does not reach Typer" notes in `test_complete.py` / `test_events_tail.py`

### Dependencies

- None.

---

## Work Package WP02: CLI-surface product fix and oracle re-pins (Priority: P1)

**Goal**: Fix the R4 `doctor coordination --fix` loop in the product. Re-pin R1–R4, R15, R17, R21 and R22; delete R16; remove the dead fallback-print branch.
**Independent Test**: The five owned test files pass.
**Prompt**: `/tasks/WP02-cli-surface-fix-and-repins.md`
**Requirement Refs**: FR-002

### Included Subtasks

T004 Red-first: add a regression test for the remote-only refusal without a `coord_branch` extra, asserting the ordered fetch/branch/fix steps (red on base)
T005 Fix `_apply_missing_worktree_fix` to reclassify on `exc.coordination_branch`; re-pin R4 and add the genuinely-generic local-head case
T006 [P] Re-pin the doctor golden (R1–R3: `decisions` subcommand, consolidate wording, provenance help)
T007 [P] Mission-type fallback: re-pin R15 (fail-closed + repeat), delete R16, re-pin R17; remove the dead branch in `mission_type.py`; refresh the module docstring
T008 [P] Re-pin R21 (audit-tail stderr envelope) and R22 (dispatch `json_error` envelope)

### Dependencies

- None.

---

## Work Package WP03: Dated report snapshots exempt from literal guards (Priority: P2)

**Goal**: R5 and R6 (decision command shape) plus #5187 (`--feature` literal) go green without rewriting historical findings.
**Independent Test**: `test_decision_command_shape_consistency.py` and `tests/contract/test_terminology_guards.py` pass.
**Prompt**: `/tasks/WP03-report-snapshot-exemption.md`
**Requirement Refs**: FR-002, FR-003

### Included Subtasks

T009 Re-pin R5 (`decision list` is canonical)
T010 Exempt `docs/reports/` in both guards, aligned with `ARCHIVE_PATH_PREFIXES`, and guard that `reports/` stays out of the docfx content globs
T011 Update the terminology narrowness pin and `terminology-exemptions.md`

### Dependencies

- None.

---

## Work Package WP04: DIRECTIVE_052 reachability and corpus-count ratchet (Priority: P2)

**Goal**: A curated `suggests` edge de-orphans DIRECTIVE_052 (R7); re-pin the SC-011 counts (R8).
**Independent Test**: `test_orphan.py`, `test_occurrence_map_field_paths.py` and `test_extractor_projection.py` pass.
**Prompt**: `/tasks/WP04-directive-052-reachability.md`
**Requirement Refs**: FR-004, FR-005

### Included Subtasks

T012 Add `procedure:disciplined-defect-diagnosis --suggests--> directive:DIRECTIVE_052` to `_CURATED_ARTIFACT_EDGES`; correct the extractor comment
T013 `spec-kitty doctrine regenerate-graph`; ledger entry (23) in `test_extractor_projection.py`
T014 Re-pin the R8 SC-011 counts (after T012/T013)

### Dependencies

- None.

---

## Work Package WP05: Installer and verdict-backfill oracles (Priority: P1)

**Goal**: Re-pin R18–R20 (with a rebuild spy) and R23, and add a positive pin for #4990.
**Independent Test**: `test_installer.py`, `test_installer_global_reassess_convergence.py` and `tests/migration/test_verdict_provenance_backfill.py` pass.
**Prompt**: `/tasks/WP05-installer-and-verdict-backfill.md`
**Requirement Refs**: FR-007

### Included Subtasks

T015 Re-pin R18/R19: tolerate only the lock file's mtime
T016 Bisect R20's cause; re-pin it to convergence and add a call-count spy on `rebuild_global_assets`
T017 Re-pin R23 with the causal rework hops; add a positive pin that a stale approval is dropped (#4990)

### Dependencies

- None.

---

## Work Package WP06: Archive sanction and template wording (Priority: P2)

**Goal**: Record the operator-sanctioned archive correction for the dogfood cutover, and fix "features" → "missions" in the src documentation template.
**Independent Test**: `grep -rn "large features" src packs` returns 0 hits; the archive gate passes once WP07 lands.
**Prompt**: `/tasks/WP06-archive-sanction-and-template-wording.md`
**Requirement Refs**: FR-006, FR-008

### Included Subtasks

T018 Add the dated sanctioned-correction entries (4 paths) to `test_archive_root_byte_identical.py`
T019 [P] Fix the template word

### Dependencies

- None.

---

## Work Package WP07: Dogfood corpus cutover (Priority: P2)

**Goal**: Cut over the two un-flipped dogfood missions with the canonical migration (R9).
**Independent Test**: `test_dogfood_corpus_backfilled.py` and `test_archive_root_byte_identical.py` pass.
**Prompt**: `/tasks/WP07-dogfood-corpus-cutover.md`
**Requirement Refs**: FR-006

### Included Subtasks

T020 Run `spec-kitty migrate backfill-runtime-state --mission <m>` for both missions from a standalone checkout; verify `verify_ok`

### Dependencies

- Depends on WP06 (the archive sanction must exist before the frozen bytes change).
