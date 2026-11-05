# Contract: `.gitattributes` merge-driver rows after an upgrade

Applies to every project `spec-kitty upgrade` touches (a consumer repository, this repository, or
a fresh clone). It is the observable contract the retirement is judged against.

## Guarantees

1. **No orphan rows.** After an upgrade, every `kitty-specs/**` row whose driver key starts with
   `spec-kitty-` matches a pattern declared in `_MERGE_DRIVERS`
   (`tests/architectural/test_merge_reconciliation_class_guard.py`). The retired
   `kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix` row violates this and must be
   absent.
2. **No silent tracked writes.** If `.gitattributes` already satisfies this contract, an upgrade
   leaves its bytes unchanged (`git status --porcelain` is empty).
3. **Healing is line-exact.** If the retired row is present, an upgrade removes that line and
   changes nothing else in the file: no re-ordering, no blank-line collapse.
4. **Idempotence.** A second upgrade performs no change and reports no repeated change line.
5. **No driver loss.** The `acceptance-matrix.json` and `issue-matrix.json` rows exist, and
   `merge.spec-kitty-acceptance-matrix.{name,driver}` / `merge.spec-kitty-issue-matrix.{name,driver}`
   carry the canonical values from `_MERGE_DRIVERS` (#2804's filled-side merge survives the
   retirement).

## Non-goals

- The driver command is unchanged: `spec-kitty merge-driver-issue-matrix` keeps merging the JSON
  `rows` array. Nothing in this mission introduces a Markdown merge driver.
- Legacy `issue-matrix.md` files already committed in old missions are not deleted or rewritten;
  only the attribute row is retired (legacy readers keep working).
- The historical changelog entry that described seeding the inert line stays as history.

## Enforcement

| Guarantee | Test |
|---|---|
| 1 | `tests/architectural/test_merge_reconciliation_class_guard.py::test_declared_merge_drivers_are_registered_in_gitattributes` (on this repository) and `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` (on an upgraded project) |
| 2, 3, 4 | `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` |
| 5 | `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py::test_the_live_gate_artifact_rows_and_drivers_survive_the_retirement` |
