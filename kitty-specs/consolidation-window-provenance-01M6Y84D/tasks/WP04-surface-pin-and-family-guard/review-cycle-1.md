---
affected_files: []
cycle_number: 1
mission_slug: consolidation-window-provenance-01M6Y84D
reproduction_command:
reviewed_at: '2026-11-09T01:07:48Z'
reviewer_agent: claude:claude-sonnet-5-5:reviewer-renata
wp_id: WP04
---

# WP04 review feedback (cycle 1) - reviewer-renata

Verdict: **changes requested**. Two scanner/guard holes that the WP prompt names as MUSTs, both small to fix. Everything else checked out.

## Required fixes

1. **[MEDIUM] `test_reconciliation_surface_pin.py:94` (`_names_from_imports`) misses relative imports.**
   `src/specify_cli/consolidation/approved_attestation.py:52` does `from .reconciliation import (_APPROVED_MEMBERSHIP_LANES, _bound_approved_wp_ids, _bound_lanes, _closed_world_anchors, _is_bookkeeping, _lane_branch_for, _planning_prefix, approval_stamp_anchors)`.
   The scanner only matches `node.module == "specify_cli.consolidation.reconciliation"` and ignores `node.level`.
   Result: `_APPROVED_MEMBERSHIP_LANES`, `_bound_approved_wp_ids`, `_bound_lanes`, `_planning_prefix` are reached by `src/` but absent from `reconciliation_surface.json` (66 names). The pin cannot catch the split dropping them, which is the pin's whole purpose (FR-018, "every name that src/ and tests/ reach").
   Fix: resolve `ImportFrom` with `level > 0` against the file's package (`specify_cli.consolidation`) before comparing, in `_names_from_imports` and the alias detection (`_facade_aliases` should also handle `from . import reconciliation`). `_iter_python_files` needs to pass the path or package in. Then regenerate the JSON with `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE=1`. Add a control: a synthetic source with `from .reconciliation import X` (path under `src/specify_cli/consolidation/`) yields `X`.

2. **[MEDIUM] `patch.object` via `from unittest.mock import patch` is not recognized by either the scanner or the guard.**
   `test_reconciliation_surface_pin.py:148-151` and `test_reconciliation_family_guard.py:75-78` (`_patch_callee_name`) return `"patch.object"` only when `func.value` is an `ast.Attribute` (`mock.patch.object`). For `patch.object(rec, "Y")`, `func.value` is an `ast.Name`, so the callee name is `"object"`, which is not in `_PATCH_CALLEES`.
   Proved on synthetic sources: `from unittest.mock import patch` + `patch.object(rec, "Y")` gives `guard_msgs=0` and `scanner_names=[]`, while `mock.patch.object`, `unittest.mock.patch.object`, `mock.patch("...")` and `patch("...")` are all caught. The WP says "your scanner and guard MUST handle all of them" including `mock.patch.object(module, "name")`; `patch.object` is the most common spelling, and a vacuous patch of this shape would go green after the split.
   Fix: in `_patch_callee_name`, treat `Attribute(attr="object", value=Name("patch") | Attribute(attr="patch"))` as `patch.object`. Share one implementation between the two files if that is simple (the helper is duplicated verbatim today).

3. **[MEDIUM] No control exercises the `mock.patch` / `patch.object` forms.**
   `test_stale_patch_fails_the_guard` covers only plain string, f-string and module-object `monkeypatch.setattr`. Add cases to it (or a sibling test) for `mock.patch("...reconciliation.Y")`, `patch.object(rec, "Y")` and `mock.patch.object(rec, "Y")`, each expecting exactly one message. Item 2 would have been caught by this.

## Non-blocking (fix if cheap)

4. **[LOW] Rule 4 of the T022 precedence rules is implemented but untested.** `_resolve_load` ignores a function-local import from a module outside `specify_cli.consolidation.reconciliation*`. `test_forward_reference_precedence_and_alias` covers rules 1-3 only. Add one case (kernel `def g(): from os.path import Y; return Y`, facade-only patch of `Y` is a lookup in the kernel, so one narrowed message).
5. **[LOW] `reconciliation_family.py:77` `patch_reconciliation_family` has no test.** Add a short test using the real modules (patch `build_approved_wp_set`, assert facade and the three consumers see the same mock, and that the patch is restored on exit).
6. **[LOW] `RECONCILIATION_CONSUMERS` omits `approved_attestation`, `resolve` (`write_post_fix_marker`) and `run_state` (`ApprovedWpCommitSet`, `VerifyResult`)**, which also bind reconciliation names by name. No name patched in the corpus is bound by them today (checked: nothing outside the facade binds any of the 9 patched names), so nothing is vacuous now. Add a comment in the module saying so, or list them; WP08/WP09 retargets will need the answer.
7. **[LOW] `test_pinned_names_keep_object_identity`** (`test_reconciliation_surface_pin.py:217`): the non-function/class branch compares the facade attribute with itself while `RECONCILIATION_FAMILY == (reconciliation,)`, and the function/class branch is true for any ordinary def/class. It cannot fail on today's code and has no control. This matches the WP text, so it is not blocking; consider a control with a fake family module that binds a different object (the `types.ModuleType` trick used in the helper tests).
8. **[LOW] `test_reconciliation_family_guard.py:40`**: `import types` sits between third-party imports; move it to the stdlib block.

## What was verified (commands and outcomes)

- No production code changed: commit `824d3682bf` touches exactly the 4 owned files; `git diff --name-only 824d3682bf^ 824d3682bf` lists only those.
- The 12 named tests exist with the exact names; `12 passed in 31.16s`.
- Blast radius: `test_reconciliation.py` + `test_canceled_dependency_attribution.py` + `test_presence_lane_base.py` = `241 passed, 1 xfailed`; `test_single_rollback_authority.py` = `23 passed`; `make test-fast` = `2921 passed, 6 skipped`.
- `ruff check`, `ruff format --check --force-exclude`, `mypy` on the 3 test modules: all clean; no `noqa` / `type: ignore`.
- Regeneration: `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE=1 ... test_scanned_surface_is_pinned` passes and `git diff --exit-code reconciliation_surface.json` is clean (the JSON is generator output). All eight WP-listed patched names are in it.
- Pin fails on an added name: appended `zz_bogus_name` to the JSON, so `test_every_pinned_name_is_importable` and `test_pinned_names_keep_object_identity` failed (`names missing from ...reconciliation: ['zz_bogus_name']`). Reverted with `git checkout --`.
- Pin fails on a removed name: removed `resolve_canceled_wp` from the JSON, so `test_scanned_surface_is_pinned` failed (`names reached on the facade but not pinned: ['resolve_canceled_wp']`). Reverted with `git checkout --`; `git status` clean afterwards.
- Guard detects a stale string patch: scratch test `tests/consolidation/test_zz_scratch_stale.py` patching `specify_cli.consolidation.reconciliation.zz_never_looked_up` made `test_patched_reconciliation_names_are_looked_up` fail with the expected message (`... reconciliation never looks zz_never_looked_up up; patch it where it is looked up`). Scratch file deleted; tree clean.
- Controls `test_stale_patch_fails_the_guard`, `test_narrowed_patch_fails_the_guard`, `test_facade_forward_reference_counts_as_a_facade_lookup`, `test_forward_reference_precedence_and_alias` assert exact message counts and module names, not mere truthiness. Not vacuous.
- `RECONCILIATION_CONSUMERS` check: `phase_claim`, `phase_gate`, `forecast` bind `build_approved_wp_set` to the facade's object and `test_family_helper_patches_consumer_bindings` verifies all four see the sentinel and that a different-object consumer is left alone (real behavior, not a mock-only test).

## Re-review scope

After fixes 1-3: rerun the DoD commands, regenerate the JSON (expect the four missing names to appear, ~70 names), and I will re-prove items 1 and 2 on synthetic sources.
