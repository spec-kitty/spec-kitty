---
affected_files: []
cycle_number: 1
mission_slug: owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
reproduction_command:
reviewed_at: '2026-10-27T19:57:38Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review: changes requested (reviewer-renata)

The behaviour fix itself is correct and I verified it independently:
- Red first: I checked out 6efb39cc in a temporary detached worktree and ran
  `tests/integration/test_owned_issue_verdict_legacy_migration_6354.py`.
  Result: 3 failed. Every failure was exit 1 with `FileNotFoundError`, which matches research §1.1.
- Green now: on the lane tip, the blast-radius set gives 130 passed. The new module, 6320 authority,
  6320 p0 repro, coord legacy-md preservation and tests/specify_cli/tasks/ are all green.
- Issue-matrix terminality and gate tests (tests/policy/test_merge_gates_issue_matrix.py,
  tests/mission_runtime/test_issue_matrix_ref_read.py,
  tests/specify_cli/cli/commands/agent/test_move_task_done_issue_matrix{,_orchestrator}.py,
  test_tasks_parsing_validation.py): 143 passed.
- ruff check: clean. `ruff format --check --force-exclude`: clean.
- Forwarding is correct. Only `_migrate_if_needed` passes `owned`. The bulk `issue-matrix migrate`
  caller keeps `owned=None` implicitly. The `TYPE_CHECKING` import respects the cold-import boundary.

The work is rejected only because the mypy gate in NFR-002 is not met. NFR-002 says touched files
must pass mypy with zero findings and no new suppressions. CLAUDE.md and the charter also require
new code to pass mypy, and DIRECTIVE_025 (Boy Scout) applies to the touched area. Each fix below
is a typed local or an annotation. None needs a `cast`, `# type: ignore` or a config change, so
the fixes are in proportion to the work.

## Required changes

1. `src/specify_cli/tasks/issue_matrix_migration.py:255`: `no-any-return`. This error already
   existed on base 5223857c. It comes from `follow_imports = "skip"`, which makes
   `validate_issue_matrix` resolve as `Any`. Fix it with a typed local, for example:
   `rows: list[IssueMatrixRow] = validate_issue_matrix(...).rows` then `return rows`.
   Use the element type the function already declares.
2. `src/specify_cli/cli/commands/agent/issue_verdict.py:175`: `no-any-return`. This error also
   existed on base and has the same cause. Fix it the same way:
   `parsed: dict[str, Any] = parse_issue_matrix_document(data)` then `return parsed`.
3. `tests/integration/test_owned_issue_verdict_legacy_migration_6354.py`: 4 new `no-untyped-def`
   findings in this new file, at lines 43, 64, 72 and 80. Annotate `_verdict(*extra: str)` with
   its return type (`click.testing.Result`). Annotate the `checkouts` parameter in the three tests
   as `tuple[Path, Path, Path]`. Nothing else in the file should change.
4. Re-run and record in the history note:
   `uv run --frozen mypy src/specify_cli/tasks/issue_matrix_migration.py src/specify_cli/cli/commands/agent/issue_verdict.py tests/integration/test_owned_issue_verdict_legacy_migration_6354.py tests/specify_cli/tasks/test_issue_matrix_structured.py`.
   Ignore any errors this command reports for the imported module
   `tests/integration/test_explicit_checkout_commands.py`. That module is pre-existing and not
   touched. Also record the exact command behind your "202 passed" figure. I could not reproduce
   that set; my located set gives 143.

## Accepted deviations (no change needed)

- No non-owned integration control in the new module. The same-fixture positive control is
  covered by the unit pin `test_owned_defaults_to_none_for_existing_callers`, which asserts
  `owned is None` reaches the writer. The repository-root write is covered end to end by
  tests/integration/test_issue_verdict_coord_legacy_md_preservation.py, which still passes.
  Building a second ~170 s fixture is not in proportion, and the module docstring states this.
- No owned malformed-legacy assertion. The raise path does not depend on `owned`: it happens in
  `_legacy_md_rows` before the writer is called, and it is already pinned for the non-owned case.
  This is acceptable as the WP prompt allows ("only if it costs no extra fixture").

## Optional (campsite, not blocking)

- `tests/specify_cli/tasks/test_issue_matrix_structured.py`: there are two blank lines before the
  new `@staticmethod _record_writer_owned` inside the class. The file is on the formatter ratchet,
  so no gate flags this, but one blank line matches the rest of the class.
