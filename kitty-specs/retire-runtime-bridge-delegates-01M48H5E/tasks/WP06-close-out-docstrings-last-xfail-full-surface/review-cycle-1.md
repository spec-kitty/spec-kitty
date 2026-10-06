---
affected_files: []
cycle_number: 1
mission_slug: retire-runtime-bridge-delegates-01M48H5E
reproduction_command:
reviewed_at: '2026-10-06T14:36:14Z'
reviewer_agent: claude-reviewer
wp_id: WP06
---

# WP06 review feedback (cycle 1) - reviewer: claude-reviewer (reviewer-renata)

Verdict: changes requested. Docstring-only fixes; everything else checks out.

## Blocking (T024 / FR-010: stale mechanism prose in files this WP owns)

The T024 sweep regex did not catch three function docstrings in
`src/runtime/next/runtime_bridge_composition.py` (a WP06-owned file) that still
describe the retired compat mechanism. Two are now factually false:

1. `runtime_bridge_composition.py:182-184` (`_resolve_step_binding`):
   "Not part of the WP02 compat guard's tracked symbol inventory (nothing
   imports/patches it) ... no residual delegate needed." This WP's own change to
   `tests/next/test_composition_gate_widening.py` now patches it, and the
   gate file's composition tests patch normalize through it.
   Fix: replace with an ownership statement, e.g. "Owned by this seam; a test
   that replaces it patches it here (`_should_dispatch_via_composition` looks it
   up on this module)."
2. `runtime_bridge_composition.py:301-304` (`_composition_dispatch_inputs`):
   "re-exported into the residual (`decide_next_via_runtime` still calls it
   bare)". False: there is no re-export, and the bridge calls
   `_composition._composition_dispatch_inputs(...)` (`runtime_bridge.py:1856`).
   Fix: say the bridge calls it on this seam.
3. `runtime_bridge_composition.py:422-424` (`_has_generated_docs`): drop the
   "WP02 compat guard's tracked symbol inventory" sentence; keep the
   `gather_artifact_presence` reaches it directly from this seam fact.

Recommended in the same pass (in-package, campsite; `runtime_bridge_io.py` is
not in WP06's owned_files, so record the out-of-map rationale like the other
docstring edits): `runtime_bridge_io.py:1177-1184` says `wp_advance_ready` is
filled "by the residual guard delegates in `runtime_bridge.py`" and cites
"its own WP02 compat reach". Reword to: `_check_cli_guards` (and
`_check_composed_action_guard`) set it from the bridge-owned
`_should_advance_wp_step`.

Suggested check after fixing: `git grep -nE "compat guard|compat reach|residual delegate|native delegate" src/runtime/next`
returns only historical prose you deliberately keep (e.g. the identity module
header's history line), not claims about current behaviour.

## Non-blocking (nit)

- `tests/runtime/test_bridge_no_compat_delegates.py:98-131,362-366`: with
  `_PENDING_SEAMS` empty, the `_MIGRATING_WP` table, `_GREEN_TODAY` and the
  xfail branches in `_row`/`_named_row` are dead scaffolding. Optional: remove
  them so the "no xfail left" state is literal, not conditional.

## Verified OK

- `_check_cli_guards` docstring matches its body (io snapshot ->
  `wp_advance_ready` from bridge-owned `_should_advance_wp_step` for
  implement/review -> `_cores.evaluate_guards_strict`, which raises for an
  unregistered family with no manifest).
- Gate has no active xfail: gate + characterisation 70 passed, 0 xfailed.
- `test_builtin_software_dev_short_circuits_without_run_dir` now guards the
  real call: mutating `_should_dispatch_via_composition` to call
  `_resolve_step_binding` before the charter lookup makes it FAIL; reverted.
- Characterisation file change is docstring-only, as the WP prompt requested.
- C-001: `git diff 1458e92e..HEAD --name-only -- src` touches only
  `src/runtime/next/`. `git grep "compat delegate" src/runtime/next`: 0 hits.
- Reconciliation consistent: 58 + 12 = 70 collected; 4 deleted test functions
  (`test_advance_run_state_after_composition_delegate_still_forwards_to_engine_adapter`,
  `test_bridge_parse_requirement_refs_delegate_reaches_cores_wp_sections`,
  `test_runtime_bridge_keeps_native_thin_delegates_for_public_relocated_names`,
  `test_thin_delegates_forward_to_the_seam`); the other 16 removed defs are renames.
- Spec Deferred section accurate (command.py:204 and retrospective_terminus.py:216-221 verified).
