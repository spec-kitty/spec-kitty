---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-26T18:36:29Z'
reviewer_agent: claude-reviewer
wp_id: WP08
---

# WP08 review feedback (cycle 1) — reviewer-renata

**Verdict: changes requested.** One semantic regression; all other conversions are correct.

## 1. [HIGH] `test_bytecode_doctor.py::fake_pkg` now LEAKS the fake package into `sys.modules` (regression vs base)

`_purge_pkg_modules(monkeypatch)` runs twice, both times via `monkeypatch.delitem`. `monkeypatch.delitem` records the value it removes and **re-inserts it at undo**. The teardown purge (after `yield`) therefore records the module imported during setup, and monkeypatch undo (which runs after the fixture teardown) puts it back. The reversed undo stack ends by restoring whatever the *setup* purge removed. As a result, the first test's `skbcd_fake_pkg` (whose `__file__` points into a deleted tmp dir) stays in `sys.modules` for the rest of the worker session. On base, the teardown `del` left `sys.modules` clean.

Reproduced with a probe test run after the file, same process, `-p no:randomly`:
- lane: `LEAKED: ['skbcd_fake_pkg'] [.../test_valid_cache_yields_no_fin0/site/skbcd_fake_pkg/__init__.py]` (1 failed)
- base b4608ff731: `LEAKED: []` (21 passed)

This is the failure class the mission exists to remove, and here the conversion introduced it. The gate and junit comparison cannot detect it because the leak only shows up in a *later* file.

**Required fix:** the teardown removal must not be undone. For example, register the absent-key state before the import so that undo deletes the key: `monkeypatch.setitem(sys.modules, _PKG, None)` followed by `monkeypatch.delitem(sys.modules, _PKG)`, then import. Undo then restores `None` and next deletes it (notset), which leaves it absent. With that, drop the teardown purge. Any other approach that leaves `sys.modules` free of `skbcd_fake_pkg*` after the fixture also works, as long as it does not use `patch.dict(sys.modules)` and does not relocate a bare `del`. Prove it with a leak probe like the one above, and record the result in the Activity Log.

## Verified OK (no action)
- 16 cwd try/finally pairs (collisions ×3, selections ×4, doctrine_new ×9) and the `_invoke_upgrade` helper plus 6 whole-test sites converted to `contextlib.chdir`. These are exactly equivalent to the original try/finally. No assertion or indentation-scope changes.
- `CI` env in the golden test converted to `monkeypatch.setenv`. This is equivalent because the invoke is the last action before the asserts.
- `S3.yaml` is `rows: []`. Census, home-pin and sys.modules gates pass (58 passed). Owned files under `-n 4 --dist loadfile`: 2 failed / 145 passed, identical to base (the 2 golden-snapshot reds are pre-existing). ruff check and format are clean. The noqa/type-ignore counts are unchanged vs base. There are no `src/**` edits.
- The remaining churn is `ruff format` output only (line joins), with no semantic change.
