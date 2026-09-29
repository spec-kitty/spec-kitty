# Bundle M red-proofs — Op 01M3QJAVJCFZSPSPR11J4K6N08

Implementer M (Sonnet), spec-kitty #5353 slice 2, `tests/charter` test-quality.
Base: `5c8d24d02b`. Branch `bundle-m-charter`.

For every item: verdict (and any change), planted break (path :: function ::
mutation), old-test / fixed-test-or-guard / post-revert pytest one-line
summaries.

---

## B#2–5 — FIX (`tests/charter/synthesizer/test_evidence.py`)

Verdict unchanged: narrow `pytest.raises(Exception)` to
`dataclasses.FrozenInstanceError` with a `match=` on the field name, for
`test_code_signals_is_frozen`, `test_corpus_entry_is_frozen`,
`test_corpus_snapshot_is_frozen`, `test_evidence_bundle_is_frozen`.

- **Planted break** (`src/charter/activation/synthesizer/evidence.py`): for
  each of `CodeSignals`, `CorpusEntry`, `CorpusSnapshot`, `EvidenceBundle`,
  changed `@dataclass(frozen=True)` to `@dataclass(unsafe_hash=True)` and
  added a custom `__setattr__` that raises `AttributeError` only on a
  *second* assignment to the asserted field name (first assignment, from
  `__init__`, still succeeds). This reproduces "every other field is now
  mutable; the asserted field raises something that isn't
  `FrozenInstanceError`" without needing a full property/InitVar rewrite.
- Old test (`pytest.raises(Exception)`): `27 passed in 0.53s` (break active) — GREEN.
- Fixed test (`pytest.raises(dataclasses.FrozenInstanceError, match=...)`): `4 failed, 23 passed in 31.72s` (break active) — all four narrowed tests RED with `AttributeError: property '<field>' ... has no setter`.
- After `git checkout -- src/`: `27 passed in 0.53s` — GREEN.
- `ruff.toml`: cleared `B017`/`PT011` for this file, kept `C408`. Verified: `ruff check` clean with only `["C408"]`.

## B#18 — FIX (`tests/charter/test_merged_graph_on_live_path.py`)

Verdict unchanged: narrow `pytest.raises(Exception)` (`test_load_validated_graph_rejects_invalid_merge`) to `pytest.raises(DRGValidationError, match=r"Dangling target: .*directive:missing")`.

- **Planted break** (`src/charter/activation/_drg_helpers.py` :: `load_validated_graph`): `assert_valid(merged)` → `assert_valid(merged, strict=True)` (a `TypeError`, since `assert_valid` has no `strict` kwarg).
- Old test (target only): `1 passed in 0.55s` (break active) — GREEN. (Note: an unrelated sibling test `test_load_validated_graph_overlays_project_graph`, which does not mock `assert_valid`, also breaks under this src mutation — expected collateral, not part of this item's oracle.)
- Fixed test (`pytest.raises(DRGValidationError, match=...)`): `1 failed in 32.04s` (break active) — RED with `TypeError: assert_valid() got an unexpected keyword argument 'strict'`.
- After revert: `4 passed in 0.80s` — GREEN.
- `ruff.toml`: cleared `PT011`, kept `F401`/`SIM117` (still fire). Verified via targeted `ruff check` with only those two active.

## B#20–22 — FIX (`tests/charter/test_pack_manager.py`)

Verdict unchanged: narrow all three `pytest.raises(Exception)` in
`TestMissionTypeMalformedOrgLayerLoudFails` to `pytest.raises(ValueError, match=re.escape(...))`.

- **Planted break #20/#22** (`src/charter/offering/missions/mission_type_repository.py` :: `_load_layered_mission_type_file`): raise a new `MalformedMissionTypeError(Exception)` (not `ValueError`-derived) instead of `ValueError` for the YAML-parse-failure branch.
  - Old tests (`test_malformed_org_layer_yaml_is_not_silently_skipped`, `test_activate_on_malformed_org_layer_type_raises_real_cause_not_generic_unknown_id`): `3 passed in 0.55s` (whole class, break active) — GREEN.
  - Fixed tests: `2 failed, 1 passed in 30.90s` (break active) — both narrowed tests RED (`MalformedMissionTypeError` is not `ValueError`); `#21`'s fixed test correctly stayed green (unrelated mutation).
  - After revert: clean.
- **Planted break #21** (`src/charter/offering/missions/mission_type_repository.py` :: `scan_mission_types_dir`): dropped the `try/except OSError` translation around `directory.iterdir()`, letting the raw `PermissionError` propagate.
  - Old test (temporarily restored to its pre-fix form for this one check): `1 passed in 31.41s` (break active) — GREEN.
  - Fixed test (restored): `1 failed in 0.64s` (break active) — RED (`PermissionError` propagates uncaught, `pytest.raises(ValueError, match=...)` does not match).
  - After revert: `62 passed in 2.68s` (whole file) — GREEN.
- `ruff.toml`: no entry existed for this file; none needed.

## B#14/15 — FIX (`tests/charter/test_generator.py`)

Verdict unchanged: the "nothing leaked" assertions checked `charter.md` /
`references.yaml`, files `write_compiled_charter` never writes. Replaced with
`assert not (outside_dir / "charter.yaml").exists()` and
`assert list(outside_dir.iterdir()) == []`.

- **Planted break** (two src files, both reverted together — the verdict's single-guard-removal break alone is now caught by an independent defense-in-depth check added since the verdict was written, see note below):
  - `src/charter/activation/compiler.py` :: `write_compiled_charter`: deleted the first `_assert_safe_charter_output_dir(...)` call and moved the second to after `_bootstrap_charter_yaml(...)`.
  - `src/charter/activation/charter_yaml_io.py` :: `observe_yaml_input`: made it follow a symlinked ancestor (`path.stat()`) instead of rejecting it, so the compiler-level break can actually reach a real write (otherwise `charter_yaml_io`'s own symlink guard raises `ValueError` before any bytes land, which would flip the *old* test red on the wrong exception type instead of proving the leak).
  - Verified by ad-hoc script that `outside_dir/charter.yaml` is genuinely created while `FileExistsError("Charter output path ...")` still raises.
- Old tests (both): `4 passed in 0.58s` (break active) — GREEN.
- Fixed tests: `2 failed, 2 passed in 33.50s` (break active) — both go RED (`assert not (outside_dir / "charter.yaml").exists()` fails: the file really is there).
- After `git checkout -- src/` (both files): `4 passed in 0.59s` — GREEN.
- `ruff.toml`: no entry existed for this file; none needed.

## B#19 — RETIRE (`tests/charter/test_mission_type_profiles.py`)

Verdict unchanged. Retired `TestMissionTypeProfileOpenStr::test_pydantic_validation_error_not_raised_for_unknown`.

- **Planted break** (`src/charter/activation/mission_type_profiles.py` :: `MissionTypeProfile.mission_type`): re-annotated as `Literal["software-dev","documentation","research","plan"]` (re-introducing the pre-T029 constraint).
- Covering guard `test_custom_type_accepted_without_validation_error` (and sibling `test_arbitrary_string_accepted`): `3 failed, 1 passed in 0.68s` (whole class) — guard RED with `pydantic.ValidationError`.
- After revert: `30 passed, 1 warning in 33.38s` (whole file, post-deletion) — GREEN (was 31 before deletion).
- `ruff.toml`: no entry for this file.

## B#26 — RETIRE (`tests/charter/test_schemas_additive_fields.py`)

Verdict unchanged. Retired `TestExistingDirectivesFixturesStillLoad::test_existing_directives_yaml_fixture_still_loads` (confirmed it SKIPs in this worktree, matching the verdict's "masked in CI" characterization — no stray `.worktrees/*/directives.yaml` pollution here).

- **Planted break** (`src/charter/activation/schemas.py` :: `Directive.references`): removed `Field(default_factory=list)`, making the field required.
- Covering guard `TestDirectiveReferencesField::test_round_trip_without_references` (+ siblings): `3 failed, 6 passed, 1 skipped in 0.77s` — guard RED with `pydantic.ValidationError: references / Field required`.
- After revert: `9 passed in 32.77s` (whole file, post-deletion, imports cleaned: dropped now-unused `Path` and `DirectivesConfig`) — GREEN (was 10 before deletion).
- `ruff.toml`: no entry for this file.

## B#27 — RETIRE (`tests/charter/test_sonar_complexity_a_helpers.py`)

Verdict unchanged. Retired `TestResolveIncludeKind::test_resolve_include_kind_unknown_token_fails_closed`.

- **Planted break** (`src/charter/activation/context_renderers/template_include.py` :: `_resolve_include_kind`): for non-`mission-type` tokens, resolve via `ArtifactKind[kind.upper().replace("-", "_")]` instead of `ArtifactKind.from_operator_token(kind)` (raises `KeyError` for an unknown token instead of `ValueError`).
- Covering guard `tests/charter/test_context_include.py::TestUnknownSelectors::test_unknown_kind_fails_closed`: `1 failed, 41 passed in 0.88s` (both files together) — guard RED with `KeyError: 'BOGUS_KIND'`. Retiring test itself stayed GREEN (bare `pytest.raises(Exception)` matches `KeyError` too), confirming it added nothing over the guard.
- After revert: `38 passed in 34.08s` (whole file, post-deletion) — GREEN (was 39 before deletion).
- `ruff.toml`: cleared the `PT011` entry entirely (file had no other PT011-suppressed line left). Verified with `ruff check` (no per-file-ignore) — clean.

## A#4 — RETIRE, A#6 — FIX (`tests/charter/synthesizer/test_interview_mapping.py`)

Verdicts unchanged.

- **A#4 planted break** (`src/charter/activation/synthesizer/interview_mapping.py` :: `INTERVIEW_MAPPINGS`): appended a bare tuple `("stray", ("directive",))`.
  - Result: the whole module fails to **collect** (`AttributeError: 'tuple' object has no attribute 'requires_nonempty'`, raised at import time by an unrelated class's module-level `pytest.mark.parametrize` list comprehension over `INTERVIEW_MAPPINGS`) — a strictly stronger failure than the named guard `test_section_labels_are_nonempty_strings` alone would show, since collection failure takes down every test in the file including that guard. Confirms the retiring test added nothing a real consumer of the table wouldn't catch first.
  - After `git checkout -- src/`: `65 passed in 0.66s` (whole file, pre-deletion) — GREEN.
  - Deleted `test_all_entries_are_interview_section_mapping`. `InterviewSectionMapping` import still used elsewhere — kept.
- **A#6 planted break** (same file :: `_append_table_driven_results`): `"kinds": list(mapping.kinds)` → `"kinds": []`.
  - Old test (`test_context_is_dict`, `isinstance(ctx, dict)`): `1 passed in 0.45s` (break active) — GREEN.
  - Fixed test (literal-dict equality oracle from the verdict, `contexts["testing_philosophy"] == {...}`): `1 failed in 32.18s` (break active) — RED (`{'kinds': []} != {'kinds': ['tactic', 'styleguide']}`).
  - After revert: `64 passed in 0.65s` (whole file, post A#4-deletion) — GREEN.
- `ruff.toml`: file's `PT011` entry retained (an unrelated `pytest.raises(ValueError) as exc_info:` at line 132, KEEP-verdict item A#5, still needs it).

## A#25 — FIX, A#26 — RETIRE (`tests/charter/test_invocation_context.py`)

Verdicts unchanged.

- **A#25 planted break** (`src/charter/activation/invocation_context.py` :: `ProjectContext.require_pack_context`): `return self.pack_context` → re-read via `PackContext.from_config(self.require_repo_root())`.
  - Old test (`pc is not None`): `1 passed in 0.57s` (break active) — GREEN.
  - Fixed test (`ctx.require_pack_context() is ctx.pack_context` + assumption check on `activated_mission_types`): `1 failed in 34.00s` (break active) — RED (`assert ... is ...` fails; re-read object is equal but not identical).
  - After revert: `1 passed in 0.57s` — GREEN.
- **A#26 planted break** (same file :: `build_operational_context`): body replaced with `return OperationalContext()`, ignoring all arguments.
  - Retiring test (`isinstance(ctx, OperationalContext)`) + covering guard `tests/charter/test_operational_context.py::test_explicit_operational_context_round_trip`: `1 failed, 3 passed in 0.65s` — guard RED (`assert None == 'opus'`); retiring test stayed GREEN (still an instance).
  - After revert: clean.
  - Deleted `test_returns_operational_context_instance`. `OperationalContext` import still used elsewhere — kept.
- Final: `23 passed in 33.05s` (whole file, post both deletions) — GREEN (was 24).
- `ruff.toml`: no entry for this file.

## A#8, A#9 — RETIRE (`tests/charter/synthesizer/test_orchestrator_synthesize.py`)

Verdicts unchanged.

- **A#8 planted break** (`src/charter/activation/synthesizer/synthesize_pipeline.py` :: `run_all`): `return results` → `return results[:-1]`.
  - Covering guard `TestRunAllTupleCount::test_run_all_expected_count` (`len == 7`): `1 failed, 4 passed in 0.66s` (whole class) — guard RED (`6 != 7`). Retiring test `test_run_all_returns_list` (`isinstance(results, list)`) stayed GREEN.
  - After revert: clean.
- **A#9 planted break** (`src/charter/activation/synthesizer/orchestrator.py` :: `synthesize`): both `return _reconstruct_synthesis_result(...)` sites (dry-run branch and the tail) replaced with `return outcome.delta`.
  - Covering guards `test_synthesize_result_has_target_kind` / `test_synthesize_result_has_inputs_hash`: `3 failed, 1 passed in 0.86s` (whole class) — both guards RED with `AttributeError: 'ReconciliationDelta' object has no attribute ...`. Retiring test `test_synthesize_returns_synthesis_result` also failed here (an `isinstance` check on the wrong type fails immediately too) — expected and fine; RETIRE only requires the named guard to go red, not the old test to stay green.
  - After revert: clean.
- Deleted both retiring tests. Final: `25 passed, 1 warning in 32.71s` (whole file) — GREEN (was 27).
- `ruff.toml`: no entry for this file.

## A#31–33 — RETIRE (`tests/charter/test_pack_context.py`)

Verdicts unchanged.

- **#31 planted break** (`src/charter/activation/pack_context.py` :: `PackContext.from_config`): `pack_roots: tuple[Path, ...] = (builtin_root, *org_pack_roots)` → a list.
  - Guard `test_pack_context_is_hashable`: `2 failed in 0.68s` (both retiring test and guard fail together) — guard RED (`TypeError: unhashable type: 'list'`).
- **#32 planted break** (same file :: `_read_activated_kinds`): default-fallback branch returns `set(_BUILTIN_ARTIFACT_KINDS)` instead of the frozenset.
  - Guard: `2 failed in 0.63s` — RED (`TypeError: unhashable type: 'set'`).
- **#33 planted break** (same file :: `_read_list_key`): returns `set(...)` instead of `frozenset(...)`.
  - Guard: `2 failed in 0.62s` — RED (`TypeError: unhashable type: 'set'`).
- After each revert: `git diff --stat src/` empty; final whole-file run after all three deletions: `27 passed, 1 warning in 0.72s` — GREEN (was 30).
- `ruff.toml`: no entry for this file.

## A#34 — RETIRE, A#38 — RETIRE (`tests/charter/test_path_conventions_slot.py`)

Verdicts unchanged.

- **A#34 planted break** (`src/charter/offering/missions/models.py` :: `VALID_PATH_KEYS`): dropped `"data"` from the frozenset literal.
  - Guard `test_valid_path_keys_matches_historical_specify_cli_value`: `1 failed, 1 passed in 0.60s` (class) — RED (`Extra items in the left set: 'data'`). Retiring test `test_valid_path_keys_is_a_frozenset` stayed GREEN (still a frozenset, just missing a member).
  - After revert + deletion: `20 passed in 31.82s` (whole file) — GREEN (was 21).
- **A#38 planted break** (same file :: `validate_path_conventions`): `unknown = sorted(set(pc) - VALID_PATH_KEYS)` → subtract a stale local set lacking `"data"` (`VALID_PATH_KEYS - {"data"}`).
  - Guards `test_each_valid_key_accepted_individually[data]` and `TestMissionTypePathConventionsField::test_all_valid_keys_accepted_together`: `3 failed, 17 passed in 0.67s` (whole file) — both guards RED (`ValueError: Unknown path-convention keys: ['data']`), alongside the retiring test itself (also fine — not required to stay green).
  - After revert + deletion: `19 passed in 32.00s` (whole file) — GREEN (was 20 after A#34's deletion).
- `ruff.toml`: no entry for this file.

## A#17 — RETIRE (`tests/charter/test_action_sequence_dispatch.py`)

Verdict unchanged. Retired `TestResolveActionSequence::test_result_is_a_list`.

- **Planted break** (`src/charter/activation/mission_type_profiles.py` :: `_resolve_action_slot`): final `return action_sequence` → `return tuple(action_sequence)`.
- Covering guard `test_software_dev_returns_builtin_sequence` (+ 2 other siblings that also assert list equality): `4 failed, 3 passed in 0.66s` (whole class) — guard RED (`('specify', ...) == ['specify', ...]` fails; Python `tuple != list`). Retiring test also failed here (expected, not required to stay green).
- After revert + deletion: `13 passed in 32.33s` (whole file) — GREEN (was 14).
- `ruff.toml`: no entry for this file.

## A#20 — RETIRE, carefully verified (`tests/charter/test_builtin_missions_root.py`)

Verdict unchanged after careful verification (per the brief's explicit caution
about a possible vacuous zero-iteration pass).

- **Planted break** (`src/charter/activation/mission_type_profile_repository.py` :: `MissionTypeProfileRepository._default_built_in_dir`): `return builtin_missions_root()` → `return builtin_missions_root() / "nope"`.
- Covering guard `tests/charter/test_mission_type_profile_override.py::TestShippedProfilesHonourInvariant::test_all_shipped_profiles_have_id_equal_to_mission_type` iterates `builtin_mission_type_ids()` (sourced from the *separate* `MissionTypeRepository.default()`, which is unaffected by this break) and calls `repo.get(mission_type)` on the broken `MissionTypeProfileRepository`.
- Verified with `-v` output: the loop iterated real mission types (confirmed non-vacuous — `5 items collected`, `4 passed`) and the guard failed with a genuine assertion: `AssertionError: shipped profile for 'documentation' did not load — the governance-profile.yaml is missing or mis-keyed. assert None is not None` — **not** a vacuous "0 iterations, trivially pass." This confirms the guard is a real, non-degenerate cover for the retiring test's contract.
- After revert + deletion: `2 passed in 31.95s` (whole file, `MissionTypeProfileRepository` import dropped as now-unused) — GREEN (was 3).
- `ruff.toml`: no entry for this file.

## A#22 — RETIRE (`tests/charter/test_context.py`)

Verdict unchanged. Retired `TestBuildContextV2::test_returns_charter_context_result`.

- **Planted break** (`src/charter/activation/context.py` :: `build_charter_context`): the final `return _bootstrap_context_result(...)` wrapped to `result = _bootstrap_context_result(...); return result.text` (returns the rendered string instead of the `CharterContextResult`).
- Covering guards `test_action_normalized` (`result.action`) and `test_mode_is_bootstrap_on_first_load` (`result.mode`, `result.first_load`): `21 failed, 9 passed in 38.09s` (whole class) — both named guards RED with `AttributeError` (a `str` has no `.action`/`.mode`), along with many other bootstrap-path tests in the same class (expected collateral — the break affects every call that reaches the bootstrap branch, not just the two named guards).
- After revert: `30 passed, 3 warnings in 37.75s` (whole class, pre-deletion) — GREEN.
- After deletion: `36 passed, 3 warnings in 68.70s` (whole file) — GREEN (was 37). `CharterContextResult` import still used (return-type annotation) — kept.
- `ruff.toml`: file's `SIM102` entry retained (unrelated).

---

## Aggregate final state

All 15 owned test files green together:

```
383 passed, 4 warnings in 43.23s
```

`git diff --stat src/` is empty at every commit boundary (planted breaks were
never committed). `ruff check` and `ruff format --check --force-exclude`
clean on every touched file plus `ruff.toml`.

`tests/architectural/test_ruff_pytest_style_baseline.py` (4 of 7 tests) is
**pre-existing red on the base commit** (`5c8d24d02b`), independent of this
work: its subprocess probes shell out to `python -m ruff`, and this
worktree's `.venv` has no importable `ruff` module (the `ruff` CLI on `PATH`
resolves to a separate pyenv shim, not this project's venv) — a stale-venv/
environment gap (CLAUDE.md category 4), confirmed identical before and after
this bundle's changes via `git stash`.


> **Integration note (orchestrator):** the SHAs above were rewritten to the integrated `issue-5353-charter-test-quality` commits. The worktree evidence commits (`31026abcef`, `9691c0a89f`) were not ported: evidence lives in `.kittify/evidence/<op>/`, not in `work-evidence/`.
