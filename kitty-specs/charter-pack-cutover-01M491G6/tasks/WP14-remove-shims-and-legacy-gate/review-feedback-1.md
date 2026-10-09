# WP14 review, cycle 1 (architect-alphonso as reviewer)

**Verdict: changes requested.** Two blocking findings. Both fixes are small. The gate, the removal list, the tracker work and the fixture conversions are sound. Everything not listed under "Blocking" below is approved as it is.

Tests were run in a standalone clone of `kitty/mission-charter-pack-cutover-01M491G6-lane-n` at `2208665c`.

## Blocking

### B1. `ActiveCharterConfigError.__str__` turns the mission-create golden red

`tests/core/test_mission_creation_golden_refusals.py::test_malformed_config_invalid_yaml` fails on the lane:

```
-    "message": "ACTIVE_CHARTER_CONFIG_INVALID"
+    "message": "ACTIVE_CHARTER_CONFIG_INVALID: Invalid YAML in .kittify/config.yaml: ... Remediation: fix ..."
```

The cause is the new `__str__` in `src/charter/activation/pack_context.py` (dbc79355). The golden helper records `str(exc)` (`tests/core/_mission_create_golden.py:379`). I confirmed it is caused by WP14: with only that `__str__` removed in the clone, the test passes (1 passed).

`contracts/errors.md` says this error's shape is "unchanged". Pick one fix and say which in the Activity Log:

- **(a)** Drop the `__str__` override. Each renderer already reads `.body` (`upgrade.py:1057`, `charter/mission_type.py:139`, mission create, `charter activate`). Show the body where a generic renderer needs it. This one is preferred.
- **(b)** Keep the override, and update the golden cell on purpose with a recorded reason. Then check every other `str(exc)` and JSON `message` consumer of this class, and record the shape change for the WP24 changelog.

`tests/charter/test_governance_fail_closed.py::test_active_charter_config_error_str_keeps_the_body` follows whichever fix you choose.

### B2. The doctor selections diagnostic silently drops a retired `governance.doctrine` (T073 step 3)

`_doctrine_collect._read_project_selections` calls `require_canonical_governance`, but the error then lands in the existing `except Exception: pass`. The result is empty selections with no report.

The inline comment claims "the CLI-root LEGACY_CHARTER_STATE gate refuses such a project first". That is false for this key. `governance.doctrine` lives in `charter.yaml`, and the predicate never reads `charter.yaml` (`legacy_charter_layout.py` docstring: "``charter.yaml`` is never read here"). So the path is reachable from the CLI.

This is the silent loss of selections that T073 exists to prevent, on the surface an operator uses to diagnose. T073 step 3 says doctor-style diagnostics "must report, not crash".

Fix:
- Catch `ActiveCharterConfigError` separately and surface it in the doctor output: a finding/notice in the human and JSON output naming the file, the key and `spec-kitty upgrade`. Keep the best-effort degradation for malformed YAML.
- Correct the comment.
- Change `test_doctor_selection_diagnostic_degrades_instead_of_crashing` so it asserts that the retired key is reported, not only that it does not crash.

## Non-blocking (reviewer rulings on the flagged items)

1. **Usage probe before the refusal (`usage_errors_first`).** Accepted as sound and minimal for C-006.
   - Click cannot report a leaf's unknown option before the root callback runs, so a tokenizer-only probe on the refusal path is the least invasive option.
   - It runs only when the gate is about to refuse, so the common path costs nothing. It converts no parameter and fires no callback.
   - It behaves the same for every command: an unknown command still gets the refusal.
   - Keep it. Follow-up for the orchestrator, not you: rebase `test_fr011_shims_removed`'s exit-2 row onto a migrated fixture (or the contract on "usage errors exit 2 first"), so the contract and the test say the same thing. Then decide whether the probe stays.
2. **Gate.**
   - The exemptions match AR-S3. `session-stop` and `commit-guard-hook` are justified hook entry points; the merge remedy runs commit hooks.
   - The contract text matches. `NotADirectoryError` is now classified the same way in both places.
   - Wired into both startup gates and the deferred-bootstrap `migrate` path. Median 0.035 ms.
   - The only path that bypasses it is shell completion (`maybe_run_completion` in `main()`), which is acceptable.
   - Nit: `EXEMPT_COMMANDS` exempts the whole `live-work` group, not only `live-work hook`. Narrow it if that is cheap.
3. **Nested org layout `<pack>/doctrine/<plural>/<layer>` and the repo-root `doctrine/` candidate.** In scope.
   - Your prompt names the `pack_manager` nested layout, and `research/package-split-and-paths.md:194` leaves the decision to FR-018/FR-011. Retiring it is correct under C-001.
   - However, it does **not** fail loudly. A nested-layout org pack now resolves to an empty set in activation with no diagnostic. Runtime (`DoctrineService`) already ignored that layout before WP14, so this is not a new loss at runtime.
   - Recommended, may be a follow-up: a pack-validation/loader diagnostic, for example a retired-layout finding that names the flat `<pack>/<plural>/` layout. C-001 allows a validation diagnostic that names a replacement. Record the decision in the Activity Log either way.
4. **The single-pack `charter_packs.org.local_path` form is deleted.** Accepted. No writer, doc or fixture used it. In lenient mode it warns ("Invalid org-pack config; ignoring org layer"); in strict mode it raises. `ensure_pack_identity` now keys on `built-in` (matches `packs/built-in/pack.yaml`) and is tested. Note for WP24: list the canonical single-pack form as removed in the changelog Before/After.
5. **rc5 `_retired_activation` reads the retired org keys.** Acceptable: a migration may read legacy state. The docstring claim "runs before the rc6 rewrite" is inaccurate in general: rc6 is `runs_first`. It holds only for selection, because `get_applicable` evaluates `detect()` for a same-version migration before rc6 applies. Reword it.
6. **Removal list.** No production occurrence remains of any of these names: `LEGACY_PROJECT_PACK_DIRNAME`, `resolve_project_pack_read_root`, `LegacyDoctrineRootWarning`, `_warn_legacy_project_pack_root_once`, `_is_legacy_artifact_prefix`, `legacy_root_read_fallback`, `save_pack_registry`, `doctrine_mode`, `--doctrine-mode`, `LegacyGovernanceKeyWarning`, `LegacyOrgPackDoctrineKeyWarning`, `LegacyTrackerOwnershipKeyWarning`, `apply_legacy_governance_selection_key_compat`.
   - The remaining hits are docstrings, the migration and predicate modules, the test helper and the negative tests.
   - Stale docstring: `org_pack_config.py:231` still names the deleted `save_pack_registry`. Fix it.
   - Both allowlists only shrink. The 7 remaining path-allowlist entries are all `repository.py` origin labels owned by WP25.
7. **Step-0 fixes.** Fine. In `_charter_pack_cutover_skills.py`, an unresolvable catalog (`None`) now yields an empty shipped set, which means no removed skill is protected. Consider failing closed (raise, or skip retirement) rather than an empty set. WP18 is approved and merged into the lane, so the conflict risk is gone.
8. **Fixture conversions.** Spot-checked about 25 files. The deleted assertions only tested the shims (the legacy registry, warnings, `save_pack_registry` round-trips, the legacy-root fallback). The converted fixtures keep their subjects. No weakened assertion found.
9. **mypy.** `pack_manager.py:361` reports `no-any-return`. The line predates this WP (blame `9a1ebd56`), so it is not yours. Ruff check and ruff format are clean.

## Tests run (standalone clone, lane tip 2208665c)

| Command | Result |
|---|---|
| `uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -n 4 --dist loadfile` | 269 passed, 1 skipped, 84 xfailed, **0 failed, 0 xpassed** |
| `uv run --frozen pytest tests/specify_cli/migration tests/charter/test_governance_fail_closed.py tests/tracker tests/agent/cli/commands/test_tracker.py tests/core/test_mission_creation_golden_refusals.py tests/specify_cli/upgrade/migrations/test_retired_activation.py -n 4` | 1160 passed, **2 failed**: B1's golden cell (caused by WP14); `test_dogfood_corpus_backfilled::test_all_eligible_missions_snapshot_non_empty_and_verify_ok` ("not cut over: charter-pack-cutover-01M491G6", in-flight repository data, no WP14 commit touches its inputs, not yours) |
| `uv run --frozen pytest tests/charter/activation tests/kernel tests/specify_cli/upgrade/migrations -n 4` | 1506 passed, 5 skipped |
| `uv run --frozen pytest tests/specify_cli/upgrade/migrations -k "rc5 or charter_pack_cutover" -n 4` | 229 passed |
| `uv run --frozen pytest tests/charter tests/doctrine tests/runtime -n 4` | 8850 passed, 34 skipped |
| `make test-fast` | 2281 passed, 8 skipped |
| Gate files: `test_no_dead_symbols`, `test_dead_symbol_allowlist_contract`, `test_compat_shims`, `test_unregistered_shim_scanner`, `test_layer_rules`, `test_kernel_no_doctrine_import`, `test_no_legacy_terminology`, `test_charter_pack_path_authority`, `test_doctrine_census`, `test_charter_kind_vocabulary_single_authority`, `test_skill_catalog_seam` | 331 passed, 2 skipped |
| `uv run --frozen ruff check .` / `ruff format --check .` | clean / 3424 files formatted |
| `mypy` on 8 touched modules | 1 error, which predates this WP (item 9) |

## For cycle 2

Fix B1 and B2. Run the golden refusals test, `tests/charter/test_governance_fail_closed.py`, the doctor selections tests (`tests/specify_cli/cli/commands/test_doctrine_collect.py`, `test_doctor_doctrine_selections.py`) and the acceptance suite again. Also apply the docstring nits in items 5 and 6.
