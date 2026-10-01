# Quickstart: reviewer verification per requirement

This page is for reviewers and implementers checking the mission.

**Ground rules:**
- Every command runs from the repository root, on named files only (C-001, `NO_FULL_HEAVY_SUITES_IN_MISSION`).
- Never run `tests/architectural/` as a directory, `make test-full`, or a stress, timing, e2e or performance suite.
- Run `make test-fast` once as the shared baseline.
- **A planted break is always a scratch edit.** Apply it, observe the result, then run `git checkout -- <file>` (or `git stash drop`). It is never committed (C-007).
- Before approving, check the product-source diff:

  ```
  git diff <base>..HEAD -- src/
  ```

  It must show **only** the FR-005 fix in `src/specify_cli/doctrine/pack_validator.py`.

The shorthand used below:

```
PT="uv run --frozen pytest -n0 -q -rs"
```

SC-005 requires the independent reviewer to re-run **at least 6 FIX breaks and 2 RETIRE guards** personally, and to set `reviewer_rerun: true` on those evidence records. Suggested picks: #1, #3, #4, #9, #11 and #13 below (FIX), and #5 and #14 (RETIRE covering guards). #20 is the covering guard for retiring the refresh helper.

## FR-001 / SC-001: the doctrine probe (IC-01)

```
$PT tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py
```

- **Expect**: 0 SKIPPED for the 9 former probe tests. Compare with the "9 skipped" baseline in `evidence/IC-01-*.md`.
- **Break #1 (FIX)**: make `_load_built_in_ids_per_kind` in `pack_validator.py` return `{}`. The reworded-wording tests (`test_same_id_collision_uses_reworded_wording`, `test_step4a_…`) go RED.
- **Break #2**: delete the precondition assert's fixture tactic, or point the assert at a wrong id. The test fails loudly and does not pass vacuously.

## FR-005: the fragment-intent product fix (IC-01)

- **Red-first check**:
  1. `git checkout <red-commit> && $PT tests/specify_cli/doctrine/test_pack_validator.py` shows the fragment-intent regression test RED on `same_id_collision`.
  2. On the fix commit it is GREEN.
  3. The fix commit's diff touches only `src/specify_cli/doctrine/pack_validator.py`.
- **Break #3 (FIX)**: make `_collect_fragment_edge_intent` return `{}`. `test_enhances_suppresses_collision_advisory` and `test_overrides_suppresses_collision_advisory` go RED.
- **Tracker**: the regression test docstring cites the new issue (filed during implementation), and that issue has an issue-matrix row.
- **Unchanged path**: `$PT tests/doctrine/drg/test_org_fragment_validation.py` stays green, so the `*.graph.yaml` → `drg_root_graph_missing` error path is unchanged.

## FR-002 / SC-002: closed-issue markers (IC-02, IC-03)

```
$PT tests/architectural/test_egress_consent_boundary.py tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py tests/architectural/test_saas_sync_gate_selection_invariance.py tests/architectural/test_pyproject_shape.py
uv run --frozen pytest "tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape" --runxfail -rxX -n0 -q
```

**Expect:**
- Both limit-8 cases FAIL under `--runxfail` with "scanner went blind to transport-call", so the residual still holds.
- Their xfail reason cites the new open issue. Check it with `gh issue view <n> --json state`.
- The landmine guard passes, now asserting the new number.
- `rg -n "_has_events_5|clean_install_acceptance_deferred|shared_package_deferral" tests` returns nothing.

**Breaks:**
- **Break #4 (FIX)**: delete the `raise MissionStateDryRunError` at `src/specify_cli/migration/mission_state.py:1183-1184`. The new version-monkeypatch test in `test_mission_state_repair.py` goes RED.
- **Break #5 (RETIRE guard, #828)**: add `[tool.uv.sources] spec-kitty-events = { git = "https://…", rev = "…" }` to `pyproject.toml` in scratch. `test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies` goes RED.
- **Break #6 (KEEP, sync gate)**: put a module-scope `os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"` in a scratch `tests/unit/test_zz_scratch.py`. `test_no_test_module_sets_the_flag_at_import_time` goes RED.

**Grep:** `rg -n "EXPERIMENTAL#171|spec-kitty#171|#3113|#932" <touched files>` shows no reason text that still rests on a closed issue. Provenance docstrings are allowed.

## FR-003: the quarantine lane (IC-03)

```
uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -m "not stress and not timing" --collect-only -q | grep -c accept_diagnose   # expect >= 5 (the 5 formerly quarantined ids)
uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n 2 --dist loadfile -q                              # expect 23 passed, 0 skipped
uv run --frozen python -c "import yaml;r=yaml.safe_load(open('.github/ci-module-registry.yml'));print(any('tests/specify_cli/acceptance' in m.get('test_dirs',[]) for m in r['modules']))"   # expect False: still out-of-matrix, so the nightly specify-cli-out-of-matrix job collects it
$PT tests/architectural/test_quarantine_marker.py tests/architectural/test_out_of_matrix_evidence.py tests/architectural/test_module_shard_registry.py tests/architectural/test_ruff_pytest_style_baseline.py
```

- **Expect**: `rg -n "quarantine|result\.output" tests/specify_cli/acceptance/test_acceptance_support.py` returns no quarantine marker, and no `json.loads(result.output)`.
- **Break #7 (per-test proof)**: make `accept --diagnose` write `meta.json` by dropping the diagnose short-circuit before the matrix or meta stamp. `test_accept_diagnose_json_reports_skipped_checks_without_mutation` and `test_accept_diagnose_does_not_mutate_matrix_metadata_or_events` go RED.

## FR-004: errors fail instead of skipping (IC-04, IC-05)

```
$PT tests/cross_cutting/versioning/test_version_detection.py tests/architectural/test_real_home_isolation_guard.py tests/retrospective/test_events_shapes.py tests/upgrade/test_unified_bundle_migration.py tests/specify_cli/core/test_wps_manifest.py tests/doctrine/test_wheel_packaging.py tests/contract/test_example_round_trip.py tests/architectural/test_home_owner_behaviour.py tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_performance_marker_guard.py
uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m timing    # the new budget test is collected
uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m stress    # the correctness test is collected
```

**Expect:**
- `test_example_round_trip.py` shows 32 passed (29 round-trip cases plus 3 map self-tests) and 0 skipped. The baseline was 19 passed, 10 skipped.
- `rg -n "_build_wheel_fallback|_SKIP_PRE_WP04|importorskip\(\"jsonschema\"\)" tests` returns nothing.

**Breaks:**
- **Break #8 (FIX, row 13)**: make `get_installed_version` return `None`, using a scratch conftest monkeypatch. Before: 7 SKIPPED. After: FAIL.
- **Break #9 (FIX, row 15)**: make **both** HOME redirects no-ops in `tests/conftest.py`: the `_HOME_ENV_VARS` loop in `_apply_home_env` (`:134`, process-wide, from `pytest_configure`) **and** the loop in the autouse `_isolated_worker_home` fixture (`:418`). Neutering only one leaves the probe on an isolated home. `test_no_real_home_mutation_under_xdist` FAILs; it no longer skips.
- **Break #10 (RETIRE, row 12)**: `_build_wheel_fallback` had no caller, so there is nothing to break. The covering guard is the `build_artifacts` conversion: plant an invalid `[tool.hatch.build.targets.wheel].packages` entry. A `build_artifacts` consumer, run by node, ERRORs and names the build stderr, where before it SKIPPED.
- **Break #11 (FIX, row 16)**: delete one row of `tests/contract/_module_relocations.py`. The round-trip FAILs and names the module.
- **Break #12 (rows 17–18)**: `sys.modules["jsonschema"] = None` in a scratch conftest gives ERROR, not SKIP.
- **Row 14 (stress budget)**: see plan RK-3. The default proof is the `--collect-only` marker split, plus `test_timing_coverage_invariant.py` staying green. The red run of the timing node (budget monkeypatched to `0.0`) needs an operator exception.

**Exemptions:** no platform or tool guard from the masked-greens "Declared platform / tool-guard list" was converted. Check with `git diff <base>..HEAD` over those files; it should be empty.

## FR-006 / FR-007 / FR-008 / NFR-003: pin conversions (IC-06, IC-07, IC-08, IC-12)

```
$PT tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_behind_head_recovery_coverage.py tests/ci/test_recapture_charter_shard_timings.py tests/specify_cli/coordination/test_teardown_single_seam_routing.py tests/consolidation/test_executor_lane_naming.py tests/consolidation/test_mission_number_truthful_4900.py tests/lanes/test_branch_naming_seam.py tests/specify_cli/cli/commands/test_mission_close_teardown_message.py
$PT tests/architectural/test_no_absolute_event_timestamp_mixture.py tests/architectural/test_remediation_effectiveness.py tests/architectural/test_tracker_egress_guards_3108.py tests/runtime/test_bridge_decision_builder.py tests/git/test_guard_capability_regression.py tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
$PT tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/docs/test_glossary_linker.py tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py tests/specify_cli/regression/test_twelve_agent_parity.py
$PT tests/architectural/test_ratchet_baselines.py tests/architectural/test_ratchet_positional_anchor_ban.py
```

Every pin row in `research.md` ("Pin dispositions") has an evidence record. A **convert** row needs a neutral plant that stays green with 0 test or baseline edits, and a violation plant that goes red. A **delete-with-guard** row needs its covering guard red under the same break.

Spot checks:

| # | Kind | Plant | Expect |
|---|---|---|---|
| 13 | FIX, #5346-1 / F2 | In scratch, add a `_SIZE_RATCHETS` row plus its leaf | `test_size_ratchet_table_meets_floor` stays green; before the change, `:618` went red |
| | | Duplicate a row | the duplicate check goes red |
| 14 | RETIRE, #5346-2 | Add `_mt_new_helper` to `tasks_move_task.py`, register it and re-export it | stays green with no count edit (neutral) |
| | | Drop the tuple entry but keep the def | `test_guard_keyset_is_superset_of_all_six_seams_native_defs` goes red |
| 15 | FIX, #5346-7 | Replace the seam call in `_teardown_coordination_for_abort` with an inline teardown | the behavioural recorder test goes red |
| 16 | FIX, F11 | Set `remediation=None` on a real state without exempting it | the partition assert goes red |
| 17 | FIX, F10 | Add a dir to `AGENT_DIRS` with no key mapping | set equality goes red |
| 18 | KEEP, the ratchets | `git log --since=2026-08-01 -p -- tests/architectural/_baselines.yaml` | every destructive-op or inert-slot move coincides with a justified allowlist or debt row (FR-008) |

## FR-009 / SC-003: the dead-symbol re-key (IC-09 .. IC-12)

The parity `diff` below needs the JSONs that the orchestrator commits at closeout (tasks.md "Closeout (orchestrator)" step 1). If they are not committed, compare the parity digests recorded in the WP10 and WP12 evidence instead.

```
$PT tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_p1_planted_regression.py tests/architectural/test_shape_guard_membership.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_timing_coverage_invariant.py tests/unit/test_symbol_key.py
$PT tests/docs/test_freshen_adr_inventory.py tests/docs/test_inventory_lockfile.py tests/docs/test_adr_content_invariance.py tests/architectural/test_no_legacy_terminology.py
diff <(python -m json.tool --sort-keys kitty-specs/test-suite-remediation-01M3SSDW/evidence/dead-symbol-parity/before.json | grep -v base_sha) \
     <(python -m json.tool --sort-keys kitty-specs/test-suite-remediation-01M3SSDW/evidence/dead-symbol-parity/after.json | grep -v base_sha)   # expect: no output
```

`test_no_dead_symbols.py` takes about 4 minutes. It is a named gate file, not a sweep.

**Expect:**
- `rg -n "body_hash|source_module|_refresh_dead_symbol_hashes|_CATEGORY_" tests/architectural/test_no_dead_symbols.py tests/architectural/_symbol_key.py tests/unit/test_symbol_key.py` returns no allowlist data and no `source_module`. `_symbol_key.py` may keep its runtime `body_hash` computation.
- `tests/unit/test_symbol_key.py` still contains `len(index) == 400`.

**Breaks:**
- **Break #19 (SC-003, real tree)**: a behaviour-neutral **code-token** body edit. In `src/specify_cli/status/lifecycle_events.py::append_lifecycle_event` (`:608-645`), rename the local `envelope` to `persisted_envelope` (all 4 occurrences). `test_no_dead_symbols.py` stays GREEN with 0 edits. `evidence/IC-09-*.md` records the same plant going RED on the base. A docstring or comment edit does **not** change the content-tier hash (`code_tokens_by_line` drops STRING/COMMENT tokens), so it must not be used.
- **Break #20 (US2 AC-2)**: add a new dead name to some `__all__` in `src/`. The gate goes RED and names `module::name`. `test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate` stays green on its own synthetic plant, which proves the `_compute_offenders` path is live. This is also the C-002 covering guard for retiring the refresh helper.
- **Break #21 (US2 AC-3)**: import an allowlisted symbol from another `src/` module. The gate reports `module::name [REVIVED]`.
- **Break #22 (L8)**: duplicate one YAML entry. Collection fails with `AllowlistSchemaError` naming both locations.
- **Break #23 (cap)**: append one valid entry for a genuinely dead symbol without raising the leaf. `test_growing_an_allowlist_above_baseline_fails` goes RED.
- **ADR**: the new file under `docs/adr/4.x/` is listed in `docs/adr/4.x/index.md`, states that it partially supersedes D-1 of `relocation-hardened-dead-code-scanners-01KX958P`, and relates to ADR 2026-09-14-1.

## FR-011 / SC-004 / SC-005 / NFR-001 / NFR-004 / NFR-005: evidence and hygiene

- **Evidence.** Each `evidence/IC-NN-*.md` parses: one `yaml` block per record, following the rules in data-model §4. Every row in research.md's pin table and every masked-green row has a record.
- **NFR-001.** For each masked-green file, `executed_after ≥ executed_before` (`pytest -rA` counts). For the 9 probe tests, that means `+9`. For pin-retire files, see plan RK-1.
- **NFR-004.** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" <every touched file>`. Each hit has a reason, and each defect citation resolves to an **open** issue (`gh issue view <n> --json state`).
- **NFR-005.** Run the following over the touched files:

  ```
  uv run --frozen ruff check <touched files>
  uv run --frozen mypy <touched src files>
  uv run --frozen ruff format --check <touched files NOT in the format exclude list>
  ```

  All must report 0 findings, with no new `noqa` or `type: ignore`.
- **C-008.** `git diff <base>..HEAD --stat -- tests/architectural` adds no census or golden-count gate module.
