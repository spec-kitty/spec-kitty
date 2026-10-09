---
affected_files: []
cycle_number: 1
mission_slug: charter-pack-cutover-01M491G6
reproduction_command:
reviewed_at: '2026-10-07T21:21:46Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 1: changes requested

Reviewer: architect-alphonso (claude). Lane head reviewed: e4fde1e8 (lane-m, merged as a4b0df6c).

## Blocking

1. **A live test now fails because of the `dispatch.py` text change.** Commit c89e4d2a changed the
   empty-charter panel in `src/specify_cli/cli/commands/dispatch.py` from
   `spec-kitty charter pack apply minimal` to `spec-kitty charter activate --preset minimal`. One test
   still asserts the old text:

   ```
   tests/specify_cli/invocation/cli/test_dispatch.py:343
       assert "charter pack apply minimal" in result.output
   FAILED tests/specify_cli/invocation/cli/test_dispatch.py::test_dispatch_empty_charter_rich_output_shows_warning_panel
   ```

   The test passes at c970fd90 (the red-first commit, where `dispatch.py` was unchanged) and fails at
   the lane head, so this WP caused it. Change the assertion to the new remedy
   (`"charter activate --preset minimal" in result.output`). Also add a negative check that
   `"charter pack apply"` is not in the output, so the retired spelling cannot come back. In the same
   test, update the docstring and comment wording ("applying a pack" -> "applying a preset"). Then run
   `uv run --frozen pytest tests/specify_cli/invocation -q` and record the count.

   Process note: `tests/specify_cli/invocation/` is the owning test tree of `dispatch.py` and
   `invocation/empty_charter.py`, which this WP edited. Its blast radius had to be run. After this
   fix, re-grep `tests/` for each user-facing string you changed in `src/`.

## Non-blocking (fix while you are there)

2. `tests/specify_cli/invocation/test_is_charter_empty_bundle_predicate.py` lines 8 and 27: the module
   docstring still describes the journey as `charter pack apply minimal`. The helper at line 145 was
   updated, so make these two match it.
3. The WP's Activity Log (`tasks/WP13-retire-preset-registry.md`) has no entries. The WP asks for the
   T066 inventory, the red output, one line per out-of-ownership follow-up, and the test-deletion
   decisions. The commit messages and your hand-off report contain most of this. Add a short summary to
   the Activity Log, or to the status note, so WP14 and WP15 can read it.

## Verified (no action)

- **C-001: complete removal.** `git grep` over src/, tests/, pyproject.toml, .github/, scripts/ and
  packs/ for `charter_pack_registry`, `BUILTIN_PACKS`, `pack apply`, `accompanies_doctrine_pack`,
  `activation/packs`, `resolve_accompanying` and `UnresolvedDoctrinePackError` finds no live code hit.
  The only `src/` mentions are the explanatory docstrings in `pack_descriptor.py` and
  `pack_lineage.py` and the table row in `retired_fields.py`. The two
  `spec-kitty-charter-doctrine` skill docs that still cite `activation/packs/default.yaml` belong to
  WP18, which deletes that skill. The docs/ hits belong to WP22. `pack.py` has no hidden `apply`
  command and the registry imports are gone.
- **Red-first.** c970fd90 removes only the WP13 markers (3 red). Using `.get(r.pending, ())` is the
  minimal mechanical change once the WP13 key is gone.
- **WP01 fixture change (e089e5bb/e4fde1e8)** is legitimate. The old-spelling assertion still runs on
  the doctrine-command fixture with the same expected exit 2 and the same `UNKNOWN_COMMAND` check. Only
  the replacement control moves to a plain project, because the fixture declares an unfetched org pack
  and preset id resolution reads the whole offering (`PRESET_ID_UNRESOLVED`). The control's expected
  exit is unchanged.
- **Retired field.** The `model_validator(mode="before")` runs before the `extra="forbid"` check
  (`test_model_without_loader_wraps_the_typed_error` asserts that no `extra_forbidden` error appears).
  `load_pack_descriptor` moves the error to the file it read through `raise_retired_field_at`. The
  validator reuses the same exception message. The tests include positive controls: an unrelated
  unknown field still gives `extra_forbidden`, a clean descriptor loads, and a planted table row is
  rejected the same way.
- **Out-of-ownership edits** (activate/generate/compiler/schemas docstrings, dispatch, empty_charter,
  org_pack_config, migration docstrings, rosters, nightly yml, coverage-guard lists) are mechanical.
  The `org_pack_config` remedy `spec-kitty upgrade` is accurate: rc6 `_rewrite_legacy_org` migrates
  `doctrine.org.packs`. The `ci-nightly.yml` edit removes only the deleted test path from shard 5. The
  foreign-coverage baseline change is a shrink and carries a provenance note.
  `tests/release/coverage_breadth_baseline.json` is a point-in-time evidence snapshot, so leaving it
  alone is acceptable (the `test_coverage_breadth` baseline tests pass).
- **Deleted tests** (`test_charter_pack_registry.py`, `test_apply_compile_bridge.py`, the apply tests in
  `test_charter_pack_builtin.py`, the two `pack apply --compile` tests in
  `test_whole_kind_unresolved_handling_5257.py`, the `accompanies` lineage tests) all exercised deleted
  code. The retargeted doctrine checks now read `packs/built-in/presets/`.
- **Pre-existing reds, confirmed at c970fd90:** `test_doctrine_census.py` x3,
  `test_charter_kind_vocabulary_single_authority.py::test_no_hand_authored_kind_vocabulary_literal_under_src`,
  and `tests/charter/test_context_noop_stability.py` (3 errors, "fixture is vacuous"). These are
  routed to WP14 step 0 and not WP13's to fix.
- mypy on the touched src files: the same 10 findings at base and head (environment-related, none
  new). `ruff check` and `ruff format --check --force-exclude` are clean on all touched files.
