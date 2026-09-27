---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-27T02:51:11Z'
reviewer_agent: claude-reviewer
wp_id: WP13
---

# WP13 review, cycle 1: REJECT (one required fix, small)

Reviewer: claude-reviewer (reviewer-renata). Lane: lane-m. Implementation diff: d206f602b0..731d60f246.

## What passed (do not redo)

- Census, home-pin, sys.modules-patch.dict and home-owner gates on the lane: 72 passed.
- Shard files (31 files plus tests/terminus) under `-n 4 --dist loadfile`: 345 passed, 4 skipped, 2 failed. The per-test-id junit on lane and base is **identical** (351 testcases). The 2 reds (`test_reject_not_drop_cli.py::test_synthesize_{json,console}_*`) are red on base too.
- Full `tests/architectural/` (`-n 4`): 2916 passed, 1 failed. The failure is `test_ruff_format_exclude_ratchet`, which the orchestrator ruling accepts.
- Root `conftest.py::test_venv` was converted in place. No def was added, renamed or reordered, and `test_home_owner_behaviour.py` is green. A probe showed `SPEC_KITTY_TEST_VENV` present in 34 of 34 tests and removed after session teardown, so session semantics are preserved.
- sys.modules leak probe (lane vs base): the lane **removes** 2 pre-existing leaks (`contract_adapter_synthesizer`, `census_status_for_tests`). The action_sequence_dispatch, glossary and runtime/next import_paths files show the same result on lane and base.
- E1, E2 and E3 rows are genuinely unconvertible and their reasons are accurate. The S8.yaml justified rows are untouched.
- `ruff check` and `ruff format --check` pass on all 32 touched .py files, and the diff adds no new suppression (net -1 noqa).

## Required fix

1. **`tests/auth/secure_storage/test_from_environment_platform_split.py::_purge_modules` does not restore the parent-package attribute (WP contract T062 recipe plus the shard notes, which name this file).**
   The test relies on a fresh re-import. It purges `specify_cli.auth.secure_storage*` and then imports and reloads it, so the import machinery rebinds `specify_cli.auth.secure_storage` to the *fresh* package object. After the test, `sys.modules` gets the original package back, but `specify_cli.auth.secure_storage` (the attribute) still points at the stale fresh package.
   A probe measured this: `getattr(specify_cli.auth, "secure_storage") is sys.modules["specify_cli.auth.secure_storage"]` is True before the file and **False after** it. Base shows the same, so this is pre-existing, but the WP explicitly requires fixing it.
   It matters because later `mock.patch`/`monkeypatch.setattr` calls with dotted targets resolve through `getattr` and would patch the stale object.
   Verified fix (all 607 tests in tests/auth pass, and the probe then reports the attribute restored):
   ```python
   for name in [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]:
       parent_name, _, child = name.rpartition(".")
       parent = sys.modules.get(parent_name)
       if parent is not None and hasattr(parent, child):
           monkeypatch.delattr(parent, child)
       monkeypatch.delitem(sys.modules, name)
   ```
   Also correct the docstring. A bare `monkeypatch.delitem(sys.modules, name)` on a *present* key already records and restores the original module, so the `setitem(name, None)` step is redundant, and the claim that a bare delitem "would leak" is wrong. The two-step *is* meaningful in `tests/review/test_lock.py`, because `delenv(raising=False)` on an absent key records nothing. The redundant two-step in `tests/glossary/test_import_paths.py` and `tests/runtime/next/test_import_paths.py` is harmless and optional to simplify. Keep that pair consistent with whatever you choose.

## Informational, not a blocker: the escalated `_capture_nudge` row

Per the orchestrator ruling this is not a rejection reason. The measured facts:
- Regenerating the home-pin artefacts with `_home_pin_scan --root tests --frozen-at-sha <sha> ...` changes **nothing** in `spec_kitty_home_pin_baseline.yaml`. This holds both before and after a trial conversion, because `_capture_nudge` is not a census member (census rows: []). The only diff is the `frozen_at_sha` header scalar in `census/spec_kitty_home_pin_R1a.yaml`. The premise that `census_key_set_sha256` freezes these writes is therefore incorrect.
- The *real* constraint: converting to a `monkeypatch` parameter turns `tests/architectural/test_home_pin_scan_limbs.py::test_fr010_runtime_home_alias_is_measured_inert_and_refused_on_both_limbs` red. That test asserts `monkeypatch` is absent from `_capture_nudge`'s def chain (limb 1). The behaviour itself would be equivalent, since each caller invokes the helper once and no assertion reads env or argv.
- An in-map conversion exists that needs no re-baseline. Enter `mock.patch.dict(os.environ)` (no values) on the existing ExitStack, keep the owned raw `os.environ["SPEC_KITTY_HOME"] = str(runtime_home)` write inside it, and delete the old_env/try/finally restore. In a trial, the census gate (with the row removed), all `test_home_pin*.py` including the FR-010 limb, `test_home_owner_behaviour.py` and the file's own tests all passed (212 passed), and regeneration left the baseline unchanged. Apply it only if the orchestrator/operator agrees.
