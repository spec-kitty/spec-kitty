---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-26T18:54:19Z'
reviewer_agent: claude-reviewer
wp_id: WP09
---

# WP09 review feedback (cycle 1) — reviewer-renata

**Verdict: CHANGES REQUESTED.** There is one blocking regression. Every global-state conversion is correct. The problem is formatter churn in files outside the formatter gate.

## Blocking

1. **The `tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` test is RED on the lane and GREEN on the base (`beae3e337b`).**
   The WP ran `ruff format` directly on 10 owned files that appear in `pyproject.toml` `[tool.ruff.format].exclude` (the #473/#559 formatter-debt ratchet). Ruff formats a file passed by explicit path even when it is excluded. Those 10 files are now formatted, so the ratchet fails with "10 exclude entries are already formatted and no longer need the exclusion". The 10 files are `test_setup_plan_read_surface.py`, `test_init_hybrid.py`, `test_init_schema_stamp.py`, `test_issue_2876_plan_non_interactive_hang.py`, `test_issue_3033_post_consolidation_write.py`, `test_merge_cli_golden.py`, `test_research_read_surface.py`, `test_safe_commit_cli.py`, `test_safe_commit_cmd.py` and `test_session_start.py`.
   The churn is large: 599 lines are deleted, but only 451 of them remain with `-w`. Many assertion messages and signatures were reflowed. They are semantically identical, but the conversion diff is hard to review and it will conflict with sibling lanes.
   **Fix (in-map, preferred):** revert the format-only hunks in those 10 files and keep only the mutation-site conversions (plus the imports they need). One way is to reset each file to the base and re-apply the conversions by hand. Verify with `ruff format --check --force-exclude <files>` and with the ratchet test itself.
   (The alternative would be to shrink the `pyproject.toml` exclude list, which the ratchet invites. That edit falls outside the owned files, is cross-cutting and would collide with the other sweep lanes. Do it only if the orchestrator explicitly assigns it.)

## Verified OK (no action)

- Census gate, home-pin gate and sys.modules gate are green. `S4.yaml` is `rows: []`. All 21 rows were transitional, and none were justified.
- The 12 owned files give 92 passed and 1 skipped under `-n 4 --dist loadfile`, which matches the base exactly.
- **D1 deletions (3):** with no PYTHONPATH, both serially and under `-n 4`, `specify_cli.*` (session_start, init, migration.schema_version) and `tests._perf_helpers` resolve to the lane's `src/` and `tests/`. `pytest.ini` `pythonpath = src` and the rootdir cover them. The deletions are truly redundant.
- **The 10 whole-test `monkeypatch.chdir` conversions (7 in safe_commit_cli, 3 in safe_commit_cmd):** after the chdir, every step uses an explicit `cwd=`, `git -C` or an absolute path. No step needs the original cwd restored early. The 3033 `monkeypatch.chdir` is also sound.
- The `contextlib.chdir` in `_invoke_plan_non_interactive` preserves the enter and exit order.
- The `mock.patch.dict` / `patch.object(sys, "argv")` block scopes match the original try/finally scopes.
- The `monkeypatch.setenv` calls in the setup-plan helpers are fine, because each test calls its helper only once. They also fix the old leak, where the original code never restored an env var that was unset beforehand.
- The WP makes no `sys.modules` conversions, edits no `src/**` files and adds no new suppressions. Ruff check is clean.
