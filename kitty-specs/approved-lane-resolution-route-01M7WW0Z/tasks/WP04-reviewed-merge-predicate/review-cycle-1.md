---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:02:25Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP04
---

# WP04 review feedback (cycle 1) — reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commit 62704eed

## What passed
- Red-first holds: the tests at 62704eed, run against the 62704eed^ consolidation sources, give 13 failed and 5 passed (the 4 goldens and the arity check).
- The golden is non-circular and bites: mutating `_drop_unreviewed_merges` to `return spine` turns 5 tests red, including the 3 byte-identity goldens.
- `_drop_unreviewed_merges` behaviour is unchanged. A git error fails closed. The three-lane precondition is asserted. The field is advisory only. The import-cycle note is correct.
- Results: 18/18 post-fix; `tests/consolidation` 3511 passed / 1 skipped / 11 xfailed; `make test-fast` 3144 passed / 7 skipped; ruff, format and mypy clean; the layer, guard and format arch gates pass.

## Must fix
1. CI red: `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` fails on three new symbols.
   - `reconciliation_authorship::_dropped_merges` is a private helper in `__all__` with no outside caller. Remove it from `__all__`.
   - `merge_reviewed_by_own_stamps` and `own_approval_stamps` have no src caller outside the module yet. Remove them from `__all__` until WP05 imports them; WP05 re-adds them. Do not allowlist them.
   - Add `test_no_dead_symbols.py` to the gate list.
2. (LOW, fold) Two of the new branches are untested:
   - `_dropped_merges`, the `except GitProbeError: continue` branch (:358-359);
   - `_unreviewed_merge`, the `except GitProbeError` branch that logs and returns None (:372-374).

   Add a real-git test with an octopus merge on an approved lane after its stamp (`merge_own_changed_paths` raises on octopus merges). Assert:
   - the claim builds with no refusal;
   - no `unreviewed_merges` entry names that SHA;
   - the SHA is absent from `authored_shas`.

   Also add a monkeypatched `is_merge_commit` that raises for one SHA in `_dropped_merges`, and assert that SHA is not listed.

## Not blocking (for WP05)
An absent entry never means "no own content". `RESOLUTION_MERGE_UNREVIEWED` must re-probe or refuse when there is no entry.
