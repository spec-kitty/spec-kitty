---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-26T19:53:47Z'
reviewer_agent: claude-reviewer
wp_id: WP10
---

# WP10 review feedback (cycle 1) — REJECT

Reviewer: claude-reviewer (reviewer-renata). Base: `277d4fdede` (lane-a merge). Head: lane-j HEAD.

## Blocking

1. **`test_bytecode_heal.py` leak-sentinel reclassification is wrong; the 2 sites can be converted, so convert them.**
   The row reason says monkeypatch "cannot" express a purge/reimport cycle that repeats. That holds only for the naive form tried
   (`monkeypatch.delitem(sys.modules, name, raising=False)` inside the prefix loop). When the key is absent, `delitem`
   records nothing (pytest `MonkeyPatch.delitem`: the `if name not in dic` branch skips `_setitem.append`). So nothing
   captures the true pre-state ("absent"). The next purge then records the stale module, and teardown restores it.
   The fix is to anchor the pre-state first:
   - `_purge_pkg_modules(monkeypatch)` should loop over a fixed tuple of the synthetic names
     (`_PKG`, `.runner`, `.base`, `.boom`, `.broken`). For each name it does
     `monkeypatch.setitem(sys.modules, name, None)` and then `monkeypatch.delitem(sys.modules, name)`.
     `setitem` records `notset` even when the key is absent.
   - The `fake_pkg` fixture calls `_purge_pkg_modules(monkeypatch)` once at setup, before `yield`. This records
     "absent" as the earliest undo entry. Delete the teardown purge after `yield`.
   - Thread `monkeypatch` into `_import_pkg` / `_purge_pkg_modules` and into the tests that call them.
   Monkeypatch undoes in LIFO order, so the setup anchor is undone last and every synthetic key ends up absent.

   **Proof** (standalone probe: file under test + a trailing probe test in the same process, asserting that no
   `skbh_fake_pkg*` key remains in `sys.modules`):
   - lane as submitted (manual `del`): no leak, 12 passed.
   - naive `delitem(raising=False)`, no teardown purge: **leaks** `skbh_fake_pkg`, `.runner`, `.base`, `.boom`
     (1 failed). This reproduces what you observed.
   - anchored pattern above: **no leak**, 12 passed. I also ran each of the 11 tests alone followed by the probe:
     all clean.
   - Non-vacuity: dropping only the fixture-setup anchor brings the leak back (1 failed). The anchor is load-bearing.
     `test_laundered_genuine_import_bug_is_not_healed` imports the package without purging first.

   **Why this blocks:** the frozen seal cap for `leak-sentinel` is **2** (contracts/global-state-allowlist.md
   §7, research E3). S8's `tests/conftest.py::_isolated_worker_home` (count 2) already uses that whole budget.
   S5's 2 rows would make it 4 and break the Seal WP's invariant. Required end state: remove both
   `test_bytecode_heal.py` rows from `S5.yaml`, so S5 has no rows left.
   Maintainability note: put the fixed name tuple next to the fixture as a module constant, with a comment that any
   new synthetic submodule a test writes must be added to it.

## Verified OK (no action)

- **`sys.modules` leak probe, lane vs base, same process:**
  - `test_context_lifecycle.py`: the single `monkeypatch.setitem(..., None)` is equivalent to the 4-site
    pop/store/restore. No leak.
  - `test_runtime_bridge_dispatch.py`: deleting `_restore_modules` in favour of `monkeypatch.setitem` is safe.
    No leak. This is stricter than before, because a pre-existing `None` value is now restored rather than popped.
  - `test_runtime_bridge_documentation_composition.py`: no leak.
  - `test_occurrence_map_field_paths.py`: base **leaked** `inline_reference_inventory`; the lane fixes that.
- **cwd:**
  - `contextlib.chdir` in the helpers that are called repeatedly: correct.
  - `monkeypatch.chdir` in the 3 whole-test sites: the rest of each test uses absolute repo paths, so this is
    equivalent.
- **D1:** deleting the 5 `sys.path.insert` sites is redundant-safe (`pytest.ini` has `pythonpath = src`).
- **Assertions and scope:** no assertion changed, no test deleted or skipped, no `src/**` edits. Only owned files
  and `S5.yaml` were touched.
- **Evidence:**
  - Gates (census + home-pin + patch.dict): 58 passed. Format-exclude ratchet: 6 passed.
  - Shard files at `-n 4 --dist loadfile`: 290 passed / 2 skipped on both lane and base.
  - `ruff check`: clean.
  - `ruff format`: the 9 non-excluded files are clean. 10 files are on `[tool.ruff.format].exclude` and were not
    reformatted. Operator ruling: formatting them by explicit path is acceptable, but it is not required here.
