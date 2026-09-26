# Tasks: Terminus Reconciliation Attribution Integrity

**Mission**: terminus-reconciliation-attribution-integrity-01M3D4RW
**Branch**: `fix/terminus-reconciliation-attribution-integrity`
**Issues**: #5022, #5018, #5021 (r1 + r2), #5038 (all Epic #5001)

Two work packages, sliced by file cluster so ownership never overlaps (four issue-level WPs would collide on `reconciliation.py`/`executor.py`). Each WP is internally severity-ordered and red-first (ADR 2026-07-17-1 / charter C-011).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first repro `test_repro_5022.py`: canceled-WP deletion of a pre-existing file ships under default squash (RED via real `spec-kitty merge`) | WP01 | |
| T002 | Add `authored_deletions` field + `_final_authored_deletions` collector; thread `_collect_authored` → `build_approved_wp_set` | WP01 | |
| T003 | Attribute deletions in `_unattributable_content_squash` (+ `_window_has_non_bookkeeping_change`); GREEN T001 + adversarial (rename, cross-lane re-author, bookkeeping-deletion) | WP01 | |
| T004 | Red-first repro `test_repro_5018.py`: mixed approved+canceled write-scope lane false-FAILs under `--strategy merge` (RED) | WP01 | |
| T005 | Commit-level exclusion: subtract approved first-parent SHAs/patch-ids in `_collect_excluded` (threaded); GREEN T004 + adversarial (2nd-parent smuggle still excluded, cherry-pick patch-id, fully-canceled lane) | WP01 | |
| T006 | Run `tests/terminus/` + `tests/merge/`; confirm 4 axis tests green, 3-way `xfail(strict)` STILL xfailing (not un-stricted) | WP01 | |
| T007 | Red-first repro `test_repro_5021.py`: squash interrupted after PASS during coord teardown, `--resume` false-FAILs (RED) | WP02 | |
| T008 | Resume tolerates completed-but-mid-teardown squash; GREEN T007 + guard (genuinely-incomplete merge still runs full gate) | WP02 | |
| T009 | Red-first repro `test_repro_5038.py`: clean single-approved-lane squash false-REFUSEd on bookkeeping projection; `--resume` dead-ends (RED) | WP02 | |
| T010 | Projection-proof precision in `_assert_squash_projected_content_landed`/`projected_content_matches_target`; GREEN T009 + guard (genuine failed projection still REFUSEs) | WP02 | |
| T011 | Run `tests/terminus/` + `tests/merge/`; confirm all repros green, no regressions, 3-way still xfail | WP02 | |

## Work Packages

### WP01 — reconciliation.py attribution (#5022 + #5018)

- **Goal**: The squash content axis attributes deletions (#5022, data-loss — done first), and the excluded axis attributes at commit granularity so a mixed approved+canceled write-scope lane merges legitimately (#5018).
- **Priority**: P1 (contains the data-loss fix). MVP of the mission.
- **Independent test**: `test_repro_5022.py` (squash deletion FAILs) and `test_repro_5018.py` (mixed lane PASSes under merge) both green; adversarial siblings hold; 3-way still xfail.
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Dependencies**: none
- **Owned files**: `src/specify_cli/merge/reconciliation.py`, `tests/terminus/test_repro_5022.py`, `tests/terminus/test_repro_5018.py`, `tests/merge/test_reconciliation.py`
- **Risks**: C-001 — must fix attribution granularity, not gate strictness (a naive "approved wins" reopens #4977). C-003 — must not un-strict the 3-way xfail.
- **Est. prompt size**: ~380 lines.

### WP02 — executor resume + squash projection proof (#5021-r1 + #5038)

- **Goal**: `merge --resume` tolerates a completed-but-mid-teardown squash (#5021 r1), and the squash bookkeeping-projection proof does not false-REFUSE a clean single-lane merge (#5038).
- **Priority**: P2 (both fail-closed availability regressions).
- **Independent test**: `test_repro_5021.py` (resume completes) and `test_repro_5038.py` (clean squash PASSes, resume completes) green; genuine-failure guards still REFUSE.
- **Subtasks**: T007, T008, T009, T010, T011
- **Dependencies**: WP01 (sequential integration; shares no files but lands after the attribution axis to keep the gate's behavior integrated cleanly)
- **Owned files**: `src/specify_cli/merge/executor.py`, `src/specify_cli/merge/bookkeeping_projection.py`, `tests/terminus/test_repro_5021.py`, `tests/terminus/test_repro_5038.py`
- **Risks**: C-001 — resume tolerance must not skip verification of genuinely-unfinished work; projection precision must still REFUSE a genuine failed projection.
- **Est. prompt size**: ~340 lines.

## Out of scope (kept honest)

- #5021 residual 2 (3-way merge-resolution content): remains `xfail(strict=True)` in `tests/merge/test_reconciliation.py`. Documented tracked Epic #5001 follow-up; NOT green-washed (charter Standing Order #9).

## MVP

WP01 (delivers the data-loss fix #5022 + the availability fix #5018).
