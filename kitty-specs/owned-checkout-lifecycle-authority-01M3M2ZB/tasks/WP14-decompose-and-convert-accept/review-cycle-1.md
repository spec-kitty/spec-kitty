---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T09:35:43Z'
reviewer_agent: claude
wp_id: WP14
---

# WP14 review, cycle 1: REJECT (one small, mechanical finding; everything else verified)

## Finding

[MEDIUM] tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py, tests/specify_cli/cli/commands/test_accept_clean_tree.py
(commit 03ef94e98 and the earlier test-double edits) - incidental whole-file `ruff format` reflow of two out-of-map test files.
Both files are listed in `[tool.ruff.format].exclude` in pyproject.toml (the #473 formatter-debt ratchet). Once reformatted they
are no longer "genuinely reformattable", so
`tests/architectural/test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` reports them as
already-clean stale entries. The base versions of both files fail `ruff format --check`, so WP14 introduced these two entries.
(The same test also lists 14 other stale entries. They come from other WPs' files, not this one, and are not for WP14 to fix.)
The reflow hunks also break the out-of-map rule: each out-of-map hunk must be minimal and declared, and the commit body declares
only the signature widenings.

Required fix (either one):
1. Preferred: restore both files to their base formatting and apply only the declared `owned: object | None = None` /
   `**_kwargs` signature widenings. Then the ratchet no longer counts these two files.
2. Otherwise: remove exactly those two paths from `[tool.ruff.format].exclude` in pyproject.toml and declare the pyproject.toml
   edit and the reflow in the commit body.

Re-verify with `pytest tests/architectural/test_ruff_format_exclude_ratchet.py` (single named gate file). WP14's two files
must not appear in the "already formatted" list.

## Verified OK (no action)
- T075 characterisation: 49 green on f8d822fd1 (undecomposed accept). Mutations on exit code, residual-after-error, and stamp/PR-merge order/precedence all go red.
- Complexity: max function complexity in accept.py is 13. C901 removed from ruff.toml, ruff check is clean, and no new suppressions.
- FR-003: count is 1 on the base; the red is the signature pin (fails on 975bfd101, green on 7f7d407a8). A second validation gives a count != 1 and a bypass gives 0; both are caught.
- Owned arms: pins that raise on get_main_repo_root / handle walk / subprocess are non-vacuous (mutations red).
- Bridges: 5 marked (WP15 x3, WP17 x2); the callees are still `effective_root` and are listed in the WP15/WP17 task files. G5 = 0. TRANSITIONAL(WP18) added = 0.
- Enum members: value == name; test_mission_runtime_surface is green; test_owned_checkout_helper parametrisation is extended, not weakened.
- mypy --strict: 4 errors on base, 2 at head, 0 new.
