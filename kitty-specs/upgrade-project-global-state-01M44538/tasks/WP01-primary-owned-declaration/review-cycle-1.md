---
affected_files: []
cycle_number: 1
mission_slug: upgrade-project-global-state-01M44538
reproduction_command:
reviewed_at: '2026-10-04T20:13:22Z'
reviewer_agent: claude
wp_id: WP01
---

# WP01 review feedback (cycle 1) - reviewer-renata

Verdict: changes requested. Two blocking items, three minor ones. The predicate, the C-008
negatives, the `to_dict` pin and the fixture builders are good; keep them.

## Issue 1 (HIGH): import-time `_validate_primary_owned_surfaces()` masks the dead-symbol gate

`src/specify_cli/state/contract.py:1183-1200` adds a private validator and calls it at module
import. The commit body states that one purpose is to give `is_primary_owned_path` an
intra-module reference so `tests/architectural/test_no_dead_symbols.py` passes before WP03-WP05
land callers. The gate's #470 widening scans every public non-`__all__` name and rescues one
only if it is referenced in its own module (`_used_within_own_module`). This call therefore
makes `is_primary_owned_path` permanently exempt. If WP03-WP05 never land a caller, or a later
refactor removes it, the gate stays green. That is a vacuous gate (charter SO-5), not an
invariant check:

- The invariants (TRACKED, PROJECT, literal path) are already pinned by
  `test_primary_owned_surfaces_are_tracked_project_literals` and `test_primary_owned_set_is_pinned`.
- Raising `ValueError` at import of a contract module turns a declaration typo into an
  ImportError on every command that imports it. A failing unit test diagnoses that better.

Required change:
1. Delete `_validate_primary_owned_surfaces` and the module-level `_validate_primary_owned_surfaces()`
   call. Delete the three `test_validator_*` tests. If you want the "declared path is accepted
   unchanged by the predicate" check, add it as a unit test:
   `for p in primary_owned_paths(): assert is_primary_owned_path(p)`.
2. Do not swap in any other intra-module or test-only reference to rescue the symbol. Do not
   touch `dead_symbol_allowlist.yaml`; the binding fold forbids it.
3. As a result, `test_no_dead_symbols` will report `specify_cli.state.contract.is_primary_owned_path`
   until WP03 adds the first production caller. Record that in the move-task note as an
   expected, attributed transient red that WP03 closes. WP03's acceptance must include
   `test_no_dead_symbols` going green.

The fold's premise ("not scanned as dead `__all__` members") is wrong, because #470 widened the
gate. If the operator wants lane-a green in isolation, the only honest route is an operator
ruling on a temporary allowlist entry. Escalate it; do not work around it.

## Issue 2 (HIGH): the selftest asserts "bug present" in a file WP02 cannot edit

`tests/integration/test_primary_owned_fixtures_selftest.py::test_todays_upgrade_leaves_divergent_lane_metadata`
asserts `observed.branches_with_divergent_metadata` and `observed.branches_with_upgrade_commit`
are non-empty. That is the pre-fix defect, so the test goes red when WP02 lands. WP02 owns
`tests/upgrade/` and `tests/integration/test_upgrade_live_lanes_cli.py`, but not this file, so WP02
cannot flip it. The binding fold says: "Do not assert 'bug present' in a test that must stay green
after WP02."

Required change: keep `observe_upgrade_divergence()` and `UpgradeObservation` as they are. Rewrite
the selftest to assert only facts that hold both before and after the fix:
- `returncode == 0`;
- the root metadata is upgraded past `OLDER_VERSION`;
- `set(metadata_by_branch) == set(project.branches())` and every blob is not `None`;
- `set(upgrade_commits_by_branch) == set(project.branches())`.

The "defect is observable" positive control moves to WP02's own red test, which asserts
`branches_with_divergent_metadata == []` and `branches_with_upgrade_commit == []` and is shown red
before the fix. Rename the test to match; for example,
`test_observe_upgrade_divergence_reports_every_branch`. Add a coordination note for WP02 to the
move-task note.

## Issue 3 (LOW): the `depends_on_lanes` knob assertion is loose

`test_primary_owned_fixtures_selftest.py`, in `test_depends_on_lanes_knob_is_recorded_in_the_manifest`:
the string `or` match can pass on unrelated text. Parse `lanes.json` and assert
`lane-b.depends_on_lanes == ["lane-a"]` exactly, or use `read_lanes_json`.

## Issue 4 (LOW): the acceptance knob is not provided or documented

The fold lists "approved WPs plus a recorded acceptance and analysis report". Approved events and
`with_analysis_report` exist. A recorded acceptance does not. Either add it, or state in the
builder docstring that `consolidate` does not need it, with the evidence.

## Issue 5 (LOW): the manifest timestamp is not deterministic

`_build_manifest` uses `_now_iso()` for `computed_at`. It is harmless today because nothing asserts
it, but use a fixed timestamp to keep the "deterministic fixture" promise.

## Checks run (reviewer)
- `PYTHONPATH=src pytest` on the owned tests, `test_state_doctor`, `test_gitignore_contract`,
  `test_exemption_registry_ratchet`, `test_no_dead_symbols` and `test_lifted_root_gitignore_contract`:
  158 passed.
- `ruff check`: clean. `ruff format --check --force-exclude`: clean.
- `mypy` on the changed files: no findings in them. The 12 pre-existing errors are in
  `runtime/next/_internal_runtime/engine.py` and are unrelated.
