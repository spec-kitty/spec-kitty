# WP03 review feedback (cycle 1) — reviewer-renata

## Blocking

**Issue 1 — the #4962 retirement drops the only guard on the `.bak` payload.**
The retired `test_cp1252_sentinel_becomes_byte_exact_utf8_with_backup` (case 1) asserted
`backup_file.read_bytes() == original_bytes`. Nothing left in the suite pins that. Planted break,
re-run by the reviewer:

| id | product edit | guard files | result | reverted |
|----|--------------|-------------|--------|----------|
| R-1 | `_write_normalized_with_backup`: `backup_path.write_bytes(original_bytes)` -> `backup_path.write_bytes(b"x")` (`src/specify_cli/cli/commands/migrate/charter_encoding.py`) | `tests/migrate/` + `tests/charter/test_io_edge_paths.py` + `tests/charter/test_read_path_encoding.py` + `tests/migration/test_backfill_provenance.py` | 48 passed / 2 skipped: GREEN | yes |
| R-1 control | same edit | the retired `tests/regressions/test_issue_4962_charter_encoding.py`, restored temporarily | case 1 FAILED: RED | yes |

The ledger counts cases 1 and 2 as redundant because the tie-break break reds the lower tests. That
holds for the decode axis only. Case 1 also pinned the backup-recoverability contract, and the
writer docstring says operators can "recover the exact original bytes". Under the planted-break
protocol, a green guard flips this part of the removal to KEEP.

**Fix (cheap, in-process).** In `tests/migrate/test_charter_encoding_migration.py`, add an assertion
on the writer seam. It can go in a new happy-path test of `_write_normalized_with_backup`, or in
`test_yes_flag_normalizes_without_prompt`. Assert three things:
- `.bak` == the original bytes;
- the target file == `content.encode("utf-8")`, byte-exact;
- no temp file is left behind.

Re-plant R-1 and record it RED in the activity log and the evidence file. Then the retirement stands.
Land the new test in a commit before the retirement commit, or in a fixup that says why.

## Nits (fix while you are in there)

1. **Stale red-first wording is still in three touched files** (checklist item: "rewrite stale
   docstrings that call a green test red-first"):
   - `tests/specify_cli/migration/test_mission_state_identity.py:3`: the module docstring says
     "Red-first (T012): ... the base behavior is ...".
   - `tests/unit/migration/test_mission_state_lanes_rebuild.py:18` and `:131`: "T011 is the
     pinned RED-first regression" and "# T011: RED-first regression".
   - `tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py:70`: the comment
     "(RED-FIRST — commit this test alone)".

   Reword each to say the defect is fixed and the test is a permanent guard, and keep the issue number.
2. **Commit 5085f2a4 mixes two changes**: the marker scoping and the `git rm` of the #4962 subprocess
   file. The prompt asks for one logical change per commit. When you rework Issue 1, put the
   retirement in its own commit.

## Verified OK (no action)
- `git diff <base>..HEAD -- src/` is empty, and the WP commits touch only owned test files.
- P-5621-1 (`cp1252_in_tied = False`): 4 failed in `tests/migrate/test_charter_encoding_migration.py`. RED.
- P-5621-2a (command collision pre-check forced False): the ported CLI-seam test is RED.
- P-5621-2b (writer `raise _BackupCollisionError` -> `pass`): the writer-seam test is RED.
- P-5621-3 (`review_result` removed from the `status_event_row` registry): T032 is RED.
- The touched files run 77 passed, 1 skipped.
- `-m regression` collects 22 of 78 tests, and each one is a ledger pin.
- The marker gates pass (8 passed).
- `ruff check`, `ruff format --check --force-exclude` and `mypy` are clean.
- The new seam tests take under 1 s and are deterministic.
- The commit messages follow the Conventional `test(...)` form and carry the co-author trailer.
