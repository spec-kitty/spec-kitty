---
affected_files: []
cycle_number: 1
mission_slug: orientation-content-authority-01M7X5W6
reproduction_command:
reviewed_at: '2026-11-20T20:48:38Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback (cycle 1): changes requested

Reviewer: claude::reviewer-renata (independent; implementer was claude::python-pedro).
Reviewed commit: 85b5b531. (Re-recorded after a container reset lost the first record. The findings are unchanged. The fix commit 6a11491e was NOT reviewed here; a fresh reviewer takes it.)

Scope, design and the slug/health rulings are correct. Red-first is confirmed: the new test file fails at collection on base 2c2b4395. No migration module was edited (C-001). One blocking regression.

## Blocking

### B1: 7 rc39 migration tests go red

`tests/specify_cli/upgrade/migrations/test_m_3_2_0rc39_refresh_orientation_block.py`: 24/24 pass on the base, 7 fail at 85b5b531 (TestDetect::test_false_when_block_already_current; TestApply::test_apply_refreshes_stale_agents_md_block, test_apply_refreshes_stale_non_agents_writer_block, test_apply_skips_current_block, test_apply_idempotent, test_apply_returns_change_entry_per_stale_key, test_refresh_assertions_reject_output_regressions).

Cause: the tests patch `importlib.metadata.version`. `projection.py` binds `version` at module import, so the patch no longer applies and the real installed version leaks into the content that the rc39 migration writes through `manager._build_content()`. The directory runs only in the nightly build (out-of-matrix).

Fix: read the version lazily inside `expected_orientation`.

Verify: run pytest on the four session-presence migration test files under `tests/specify_cli/upgrade/migrations/`. At 85b5b531 the result is 7 failed, 54 passed.

## Non-blocking

- N1: in `install` / `update`, `orientation_writer()` (and with it `can_write`) runs outside the per-agent `try`, which breaks the swallowed-exceptions contract.
- N2: `slug_from_git_remote` ends in `or None`, so `derive_project_slug` falls back to the directory name when the remote URL's last segment is empty (it used to return `""`). Document it or test it.
- N3: `test_dry_run_preview_and_write_use_the_same_content` never calls `update(dry_run=True)`.

## Verified OK

- The slug is never the directory name. NFR-003 (no git spawn when a slug is recorded) is tested.
- Committed health is deterministic. The hook uses `live_content`.
- The removed `update(dry_run)` variant had test-only callers.
- Filtering to `MarkdownRulesWriter` excludes only `NullWriter`.
- ruff, `ruff format --check --force-exclude`, C901 and mypy are clean.
- Test runs: session_presence + identity + test_session_start gave 462 passed, 2 skipped; tool_surface gave 1255 passed.
