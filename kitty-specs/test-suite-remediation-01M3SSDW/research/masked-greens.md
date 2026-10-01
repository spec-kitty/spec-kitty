# Research: masked-green inventory, verified and disposition-ready

- **Lens:** debugger-debbie, the planning-research lens for masked greens (FR-001..FR-005, FR-011).
- **Mode:** read-only. This file is the only repository write.
- **Tree:** `issue-5353-test-suite-remediation` at `732f445a1e`, based on `upstream/main` `74373ec95a`. Checked on 2026-09-30.
- **Runs:** named files and node ids only (C-001). No directory sweeps, no `tests/architectural/` sweep, no stress/perf/e2e suites.
- **Scratch verification:** every "verified" prediction below came from a pytest plugin kept in the session scratchpad, outside the repo. It monkeypatches the one line under test at collection time. Nothing in the repo was edited.

## Headline

1. **FR-001, the doctrine probe.** All 9 tests skip today (confirmed with `-rs`). The canonical fix (below) was verified in scratch: **7 of 9 pass**. The other **2 go red** with `drg_root_graph_missing`. Their DRG-intent fixture writes `drg/intent.graph.yaml`, a shape the validator has flagged since #3387.
   - That shape is stale; the sibling tests already pass `check_drg_root=False`.
   - Tracing it turned up a real, small **product defect**: intent declared in `drg/fragment.yaml`, the shape the runtime reads, is ignored by the collision pass, which then emits a spurious `same_id_collision` advisory. Reproduced in scratch.
2. **FR-003, the quarantine.** All 5 quarantined accept-diagnose tests **pass**:
   - serially;
   - 3× under `-n 2 --dist loadfile`;
   - 2× under `-n 4 --dist load`;
   - after 23 accept-family neighbour files in one process.

   The original cross-file leak is not reproducible on this tree. The reason they "run nowhere" is structural, and it hits the whole file: `tests/cross_cutting/misc/test_acceptance_support.py` is **collected by no CI lane at all**, including its 18 unquarantined tests. De-quarantining alone does not satisfy FR-003.
3. **FR-002, closed-issue markers.**
   - The #3113 xfails still fail for their stated reason. Re-point them (file a new issue).
   - The #932 and #828 guards are dead: 0 of 61 and 0 of 2 fire. Retire them.
   - The sync gate module is a live guard with a stale premise. Keep it and re-cite.
   - `test_charter_sole_door_agent_profile_repository.py` is a **false positive**: its "828" is a line number in a docstring.
4. **FR-004, errors turned into skips.** 9 masking sites or clusters to convert. The grep found **two classes not in the handed list**:
   - **10 contract round-trip cases** skip forever because archived contract docs name relocated modules. With a relocation map they all pass (verified: 29 passed, 0 skipped).
   - `importorskip` / `ImportError`-skip of **declared** dependencies (`jsonschema`, `spec_kitty_events`).

   The `test_real_home_isolation_guard.py` "pre-WP04" skip is worse than dead: it fires precisely when isolation regresses, so the guard disarms at the moment it should bite.

---

## Disposition table

Legend:
- **est. size:** XS is 30 or fewer changed lines in one file; S is one file, or two small ones; M is several files or a product fix.
- **Predicted outcome:** the state after the disposition is applied.
- **"verified":** observed in a scratch run.

| # | FR | file::test | marker/guard + reason | issue state | observed today | disposition | planted break or covering guard | predicted outcome | est. size |
|---|---|---|---|---|---|---|---|---|---|
| 1 | FR-001 | `tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::{test_same_id_collision_uses_reworded_wording, test_enhances_unknown_target_errors, test_overrides_unknown_target_errors}` | `if not self._has_built_in_doctrine(): pytest.skip("shipped doctrine not on disk in this environment")`; probe `resolve_doctrine_root()/"tactics"/"built-in"` (→ `src/charter/offering/tactics/built-in`, absent) | n/a (uncited) | SKIP ×3 (lines 482, 527, 551) | **RUN**: delete the probe and skip; add a precondition *assert* on the fixture id (see note 1) | reworded wording: `_load_built_in_ids_per_kind` → `{}` makes it red (verified). unknown-target: drop the `unknown_target` issue append at `pack_validator.py:1180`/`:1198` | PASS (verified) | XS |
| 2 | FR-001 / FR-005 | `…::TestIntentAwareCollision::{test_enhances_suppresses_collision_advisory, test_overrides_suppresses_collision_advisory}` | same probe | n/a | SKIP ×2 (lines 428, 453) | **RUN + FIX** (see note 2): re-author the intent fixture in `drg/fragment.yaml` and fix the product red-first. Fallback: `validate_pack(tmp_path, check_drg_root=False)`, matching `tests/doctrine/drg/test_org_fragment_validation.py` | `_collect_fragment_edge_intent` → `{}` makes both red (verified with the fallback applied) | RED once unmasked (verified: `drg_root_graph_missing`). With the fallback: PASS (verified 7/7 in class). With fragment.yaml: RED until the product fix, then PASS (predicted) | S (fallback XS; product fix S) |
| 3 | FR-001 | `tests/integration/test_quickstart_end_to_end.py::TestStep4_PackValidatorVocabulary::{test_step4a_same_id_advisory_uses_reworded_message, test_step4b_inline_enhances_is_rejected_after_hard_cutover, test_step4b_unknown_enhances_target_errors}` + `::test_step5_pack_validate_json_has_no_shipped_layer_label` | module `_has_built_in_doctrine()` (line 394), same stale probe | n/a | SKIP ×4 (lines 412, 440, 464, 559) | **RUN**: delete the probe and skip; same precondition assert | 4a: built-in ids → `{}`. 4b-unknown: drop the `unknown_target` append. 4b-inline: stop rejecting the inline `enhances` field (FR-028 cutover). 5: add a `"shipped"` layer label to the JSON render | PASS (verified 4/4) | XS |
| 4 | FR-002 | `tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape[injected-transport-positional-url-name]` and `[…-non-url-name]` | `pytest.mark.xfail(strict=True, reason="#3113 case (A)/(B) … limit 8 … FR-015 … matcher left alone")` (lines ~963–1001) | #3113 **CLOSED 2026-08-02, COMPLETED**: its done-when was "document the limit; tighten only if cheap". Tightening was measured and rejected. No open tracker. | `--runxfail`: **both FAIL** with `AssertionError: scanner went blind to transport-call` (the stated reason holds) | **RE-POINT** to a **newly filed** open issue: "egress guard limit 8: all-positional injected transport call (accepted residual)". The same WP must update the landmine guard `test_positional_transport_strict_xfail_landmines_disposition_still_pending`, which asserts `"#3113" in reason` (line ~1040), plus the limit-8 docstring cross-reference | strict=True already reds on XPASS if the matcher is fixed. The docstring pin `TestCompletenessLimitsDocstring::test_limit_8_positional_transport_call_is_documented` keeps the limit named | XFAIL (strict), citing an open issue | XS |
| 5 | FR-002 / FR-003 | `tests/cross_cutting/misc/test_acceptance_support.py::{test_accept_diagnose_json_reports_missing_events_bootstrap_issue, test_accept_diagnose_json_reports_skipped_checks_without_mutation, test_accept_diagnose_json_blocks_corrupt_lanes_json, test_accept_diagnose_does_not_mutate_matrix_metadata_or_events, test_accept_diagnose_does_not_execute_custom_negative_invariants}` | `_ACCEPT_COMMAND_XDIST_QUARANTINE = pytest.mark.quarantine(reason="spec-kitty#171: in-process accept CLI family fails under xdist -n auto; passes alone")` (line 22), gated by `tests/conftest.py:320-338` → `tests/_support/quarantine.py` (`SPEC_KITTY_RUN_QUARANTINE == "1"`) | EXPERIMENTAL#171 **CLOSED 2026-08-26**. Its "fix" was the quarantine plus a `quarantine-visibility` CI job. `e8cc2f444f` deleted that job **the next day**. | With the flag set: **23/23 pass** serially, `-n 2 --dist loadfile` ×3, `-n 4 --dist load` ×2, and after 23 accept-family files in one `-n0` process (392 passed). `.github/workflows/*` sets the flag nowhere. | **DE-QUARANTINE + PLACE IN A LANE** (see the quarantine root cause). Also switch `json.loads(result.output)` to `result.stdout` (hardening) | Lane: prove it with the lane's `--collect-only` listing the 5 node ids. Per-test proof: make `accept --diagnose` write `meta.json` (e.g. drop the diagnose short-circuit before the matrix/meta stamp) and the `…_without_mutation` / `…_does_not_mutate…` tests go red | PASS in the normal parallel lane (verified locally) | S (+ lane edit) |
| 6 | FR-002 | `tests/migration/test_teamspace_migration_rehearsal.py::test_teamspace_mission_state_rehearsal_is_deterministic_across_clones` (skipif, line 169); `tests/migration/test_mission_state_repair.py` (skip at 632, 691, 750; unreachable `if not _has_events_5()` branch at 161); `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py::{test_dry_run_report_json_carries_per_mission_records_e2e, test_dry_run_still_refuses_audit_blocking_mission_e2e}` (skipif 189, 270) | `_has_events_5()`: `reason="… requires spec-kitty-events >= 5.0.0"`. #932 is the tests' **provenance**, not the skip reason. | #932 CLOSED 2026-05-10. The guard is unreachable: `pyproject.toml` floor is `spec-kitty-events>=10.4.0,<11`, lock is 10.4.0 | 61 passed, **0 skipped** across the 3 files | **RETIRE the guards** (delete `_has_events_5` ×3 and the 6 guard sites). **Replace** the unreachable branch at line 161 with an explicit test: monkeypatch `spec_kitty_events.__version__ = "4.9.0"` and assert `MissionStateDryRunError` | Covering guard for "the floor never regresses": `tests/architectural/test_pyproject_shape.py::test_events_dependency_floor_rejects_pre_v10_contract`. The new negative test's planted break: delete the `raise` at `src/specify_cli/migration/mission_state.py:1183-1184` | PASS. The product refusal branch becomes tested; today it is untested because the test branch is unreachable | S |
| 7 | FR-002 | `tests/doctrine/test_packaging_parity.py::test_clean_venv_install_imports_and_resolves_built_in` (skipif 186); `tests/integration/test_clean_install_next.py::test_clean_install_next_runs_without_runtime` (skipif 59); helper `tests/_support/shared_package_deferral.py` | `skipif(clean_install_acceptance_deferred(), reason="clean-venv wheel installation is deferred until #828's shared packages are published")`. The helper is true iff `uv.lock` has a **git** source for events/tracker. | The cited #828 is **EXPERIMENTAL#828** ("de-factory dependency pins → PyPI ranges"), **CLOSED 2026-09-01**. `spec-kitty/spec-kitty#828` is an unrelated docs issue, the same ambiguity class as #171. | Predicate evaluates `False`, so the guard never fires. The lock sources both packages from PyPI. | **RETIRE** both skipifs and delete `shared_package_deferral.py` (its only importers are these 2 files) | Covering guard: `tests/architectural/test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies` + `::test_shared_dependencies_use_public_pypi_ranges`. Planted break: add `[tool.uv.sources] spec-kitty-events = { git = "…", rev = "…" }`, the route by which a git pin re-enters the lock, and it reds "committed local source for spec-kitty-events" | Tests unchanged (already executing). Silent re-disarm removed | XS |
| 8 | FR-002 | `tests/architectural/test_charter_sole_door_agent_profile_repository.py` | none: "828" is a **line number** (`_doctrine_collect.py` sites 193/283/420/828) in a docstring. No skip or xfail in the file. | n/a | n/a | **NO-OP**: record as a false positive in the inventory | n/a | unchanged | — |
| 9 | FR-002 | `tests/architectural/test_saas_sync_gate_selection_invariance.py` (module: `test_flag_is_set_at_collection_time`, `test_no_test_module_sets_the_flag_at_import_time`, `test_scan_is_not_vacuous`) | No skip or xfail. The guard's premise, per its docstring, is that import-time `skipif(not os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC"))` gates are selection-dependent (#3213). | #3213 CLOSED 2026-08-10. #3980 CLOSED (flag now opt-out-only) | 3 passed. **Zero** import-time skipif gates on the flag remain in `tests/`. The flag is still read by product (`core/saas_sync_config.py:28`, `tracker/saas_readiness.py`) as an opt-out kill switch. | **KEEP, correct the citation.** Its live contract is still true: a module-scope write of the flag, e.g. `"0"`, pollutes every later test in the worker because product reads it at runtime. Rewrite the docstring from "import-time skipif gates" to "process-global opt-out kill-switch pollution (post-#3980)". Retiring it would violate C-002: no other gate bans module-scope env writes in `tests/`. | Existing bite test `test_scan_is_not_vacuous`. Planted break: add `os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"` at module scope of any test file; `test_no_test_module_sets_the_flag_at_import_time` goes red | PASS | XS (docstring) |
| 10 | FR-004 | `tests/conftest.py::build_artifacts` (lines 1233-1242) | `if not _build_tool_available(): pytest.skip("python -m build not available")`; `except SharedBuildError as error: pytest.skip(str(error))` | n/a | not run (it builds a wheel) | **CONVERT → fail.** `build>=1.0.0` is a declared `test` extra, so its absence is a stale venv (CLAUDE.md category 4), not a platform. `SharedBuildError` is the packaging failure FR-004 names. Also update the `SharedBuildError` docstring in `tests/_support/shared_build_artifacts.py:82` ("callers turn this into a skip"). Optionally make `default_wheel_sdist_builder` use `--no-isolation`: `hatchling` is pinned in the `test` extra for exactly this, which removes the only non-product failure mode (network). | Plant a packaging-metadata break (e.g. an invalid `[tool.hatch.build.targets.wheel].packages` entry). Today every `build_artifacts` consumer reads SKIP; after, ERROR naming the build stderr | PASS on a healthy tree (predicted, **unverified**: not run because it is a wheel build) | S |
| 11 | FR-004 | `tests/conftest.py::installed_wheel_venv` (1259-1276) | `pytest.skip(f"Failed to create venv: …")`, `pytest.skip("pip not found in venv")`, `pytest.skip(f"Failed to install wheel: …")` | n/a | not run | **CONVERT → fail** (all three). A wheel that will not install is a packaging defect. | Same planted break as #10, or a wheel with an unsatisfiable `Requires-Dist`. Today SKIP; after, ERROR | PASS on a healthy tree (predicted, unverified) | XS |
| 12 | FR-004 | `tests/doctrine/test_wheel_packaging.py::_build_wheel_fallback` (lines 33-48) | `pytest.skip(f"Wheel build failed: …")`, `pytest.skip("No wheel generated")` | n/a | **Dead code**: repo-wide grep finds no caller. The module uses the `build_artifacts` fixture. | **DELETE** the function and the stale "fallback fixtures below" comment block (lines 12-18) | Not applicable (no behaviour). Covered by #10's conversion | unchanged | XS |
| 13 | FR-004 | `tests/cross_cutting/versioning/test_version_detection.py`: 11 skip sites at lines 40, 75, 88, 106, 151, 177, 239, 242, 301, 321, 367 (incl. the 3 named `test_version_matches_package_metadata`, `test_cli_version_matches_package_metadata`, `test_no_hardcoded_version_in_init`) | `except Exception as exc: pytest.skip(f"Could not read package metadata: {exc}")` and variants; `returncode != 0 → skip` at 40 | n/a | 18 passed, 0 skipped. **Planted (scratch):** `get_installed_version → None` gives **7 SKIPPED** + 2 FAILED. The same file's `test_package_metadata_accessible` already treats that condition as `pytest.fail`. | **CONVERT → fail** at all 11 sites: let exceptions propagate or `pytest.fail`, matching lines ~340-348. The `test_venv` session fixture (conftest 1185-1200) already fails loudly when the venv cannot be built, so "metadata unreadable" is always a defect. | Planted: `get_installed_version` → `None` (scratch plugin). Today 7 SKIP; after, 9 FAIL. Product planted break: hardcode `__version__ = "0.4.13"` in `specify_cli/__init__.py` → `test_version_matches_package_metadata` red | PASS (verified: all 18 pass today with no skip firing) | S |
| 14 | FR-004 | `tests/stress/test_concurrent_emits.py::test_concurrent_emits_produce_valid_event_log` (lines 257-262) | `if duration > 60.0: pytest.skip("stress completed but exceeded 60s budget …")` (`# pragma: no cover`) | n/a | not run (stress suite, C-001) | **CONVERT, operator choice:** (a) remove the skip and move the SC-12 budget into a separate `@pytest.mark.timing` assertion (serial `-n0` pass), so correctness reports PASS and the budget reports FAIL; or (b) remove the skip and record `duration` via `record_property` if SC-12 has no owner. A bare `pytest.fail` in the stress test would be a wall-clock flake on shared runners, against the flakiness policy (tune budgets, never retry to green). | Monkeypatch the 60.0 budget to 0.0 (hoist it to a module constant first, per S1192). Today SKIP; after (a), the timing test FAILs and the stress test PASSes | PASS (predicted; unverified by C-001) | XS–S |
| 15 | FR-004 | `tests/architectural/test_real_home_isolation_guard.py::test_no_real_home_mutation_under_xdist` (lines 253-265) | `if not _isolation_active_from_homes(...): pytest.skip(_SKIP_PRE_WP04)` | n/a (WP04 shipped) | 8 passed: isolation active, gated body executes. The skip is reachable **only on a regression**, so it masks the exact failure the guard exists for. | **CONVERT → assert** that isolation is active, with the diagnostic message. Delete `_SKIP_PRE_WP04`, the stale `# pragma: no cover` on lines 265/268, and the "pre-WP04" docstrings. | Plant: make `tests/conftest.py`'s per-worker HOME redirect a no-op (the `_HOME_ENV_VARS` setenv loop in `_isolated_worker_home` / `pytest_configure`). Today SKIP; after, FAIL | PASS (verified 8/8 today) | XS |
| 16 | FR-004 (new) | `tests/contract/test_example_round_trip.py` (skip at line 650), 10 parametrized cases over archived contracts in `kitty-specs/{charter-ux-and-org-pack-vocabulary-01KSAF14, consolidate-charter-bundle-01KXSYB9, org-pack-subdir-and-doctrine-qol-01KVSRJ6, slice-f-multi-context-extensibility-01KRX5C8}/contracts/*.md` | `except ImportError: pytest.skip("… module ``X`` not yet importable … owning WP turns this GREEN")` | n/a (those WPs landed long ago) | **10 SKIPPED** today, forever: the modules were relocated (`doctrine.drg.*` → `charter.offering.drg.*`; `specify_cli.next._internal_runtime.*` → `runtime.next._internal_runtime.*`; `charter.scope` → `charter.activation.scope`; `charter.schemas` → `charter.activation.schemas`) | **CONVERT.** Archived contracts are immutable (C-006), so add a test-side historical→canonical module relocation map. Then **fail** on `ImportError` for a module absent from both. | Plant: remove one map row → FAIL naming the module. Product: rename a field on `charter.offering.drg.models` used by a contract example → round-trip FAIL | PASS (verified in scratch: 29 passed, 0 skipped) | S |
| 17 | FR-004 (new) | `tests/retrospective/test_events_shapes.py::…::test_matches_upstream_registry_when_available` (line 311) | `except ImportError: pytest.skip("spec_kitty_events is not importable")` | n/a | passes (no skip) | **CONVERT → plain import.** `spec-kitty-events` is a declared runtime dependency, so this skip hides a stale venv (CLAUDE.md category 4). | Plant: `sys.modules["spec_kitty_events.retrospective"] = None` → today SKIP, after ERROR | PASS | XS |
| 18 | FR-004 (new) | `tests/upgrade/test_unified_bundle_migration.py` (lines 345, 357), `tests/specify_cli/core/test_wps_manifest.py` (line 393) | `jsonschema = pytest.importorskip("jsonschema")` | n/a | passes (no skip) | **CONVERT → plain import.** `jsonschema>=4.0` is a declared **runtime** dependency. | Plant: hide `jsonschema` from `sys.modules` → today SKIP, after ERROR | PASS (verified: 48 passed; the 1 skip is the performance chokepoint, not this) | XS |

---

## Per-item notes

### Note 1: the canonical resolver for the shipped pack root (FR-001)

- **Canonical seam:** `charter.offering.pack_paths.built_in_dir(ArtifactKind.TACTIC)` resolves to `…/packs/built-in/tactics` (verified). It is the same seam the product uses in `pack_validator._load_built_in_ids_per_kind`. For the bare root there is `built_in_root()`. Both delegate to `kernel.paths.get_built_in_pack_root()`, which honours `SPEC_KITTY_PACKS_ROOT` and fails closed with `PackRootNotFound`.
- **Why the old probe is wrong:** `resolve_doctrine_root()` is the doctrine **package** root (`src/charter/offering`), not the pack root.
- **The probe should go entirely.**
  - Packs always ship: `packs/` is force-included in the wheel, and `built_in_dir` fails closed rather than returning a missing path.
  - A "skip if absent" probe is therefore always either dead or masking.
- **Replace it with a precondition *assert*,** not a skip:

  ```python
  from charter.offering.artifact_kinds import ArtifactKind
  from charter.offering.pack_paths import built_in_dir
  assert (built_in_dir(ArtifactKind.TACTIC) / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml").is_file()
  ```

  This matters because the two "suppresses advisory" tests assert `collision_advisories == []`. If `adversarial-qa-handoff` were ever renamed out of the built-ins, those assertions would pass vacuously. The assert turns that into a loud fixture failure.
- **Gate check:** `tests/architectural/test_built_in_location_authority.py` scans `src/` only, so calling `built_in_dir` from tests is fine.
- **Scope:** only these 2 sites use the stale probe pattern (grep verified).

### Note 2: the two red-on-unmask tests (FR-005 pre-assessment)

- **Stale test.** `_write_drg_intent` writes `drg/intent.graph.yaml`, a document that #3387 (`de0468eff2`) made `validate_pack` flag as `drg_root_graph_missing`: "the runtime never reads `drg/*.graph.yaml`". The sibling suite `tests/doctrine/drg/test_org_fragment_validation.py` already opts out with `check_drg_root=False`. These two missed the update only because they were masked.
- **Adjacent real defect (reproduced in scratch).** `_collect_fragment_edge_intent` (`src/specify_cli/doctrine/pack_validator.py:1260-1300`) globs **only** `drg/*.graph.yaml`. It never reads `drg/fragment.yaml`, the org-pack shape the runtime *does* read. The reproduction:
  - Input: a pack with tactic `adversarial-qa-handoff` and `drg/fragment.yaml` carrying `tactic:adversarial-qa-handoff —enhances→ tactic:adversarial-qa-handoff`.
  - Output: `ok=True` plus `same_id_collision` advisory: "… will field-merge into the built-in tactic — declare 'enhances: …'".
  - The advisory tells the author to declare the intent they already declared.
  - Net effect: an org-pack author has **no** DRG shape that validates clean with declared intent. `fragment.yaml` gets a spurious advisory, and `*.graph.yaml` gets a hard error.
- **Recommended path (FR-005, fits one WP):**
  1. Re-author the two tests' intent fixture in `drg/fragment.yaml`. They go RED on the spurious advisory: the red-first proof.
  2. Fix `_collect_fragment_edge_intent` to also fold `drg/fragment.yaml` edges, through the same org fragment loader `_validate_org_fragment` already uses (`pack_validator.py:543-570`), in its own fix commit (C-005).
  3. Keep a third, `drg/*.graph.yaml`-shaped case with `check_drg_root=False` if the operator wants that shape pinned too.
- **Size:** product fix S (one function plus the tests). Nothing in the tracker covers it: searched `fragment.yaml enhances same_id_collision`, no hits.
- **Fallback:** if the planner wants zero product change in this mission, add `check_drg_root=False` to the two calls (verified 7/7 green). File the fragment-intent gap as a new issue, with no xfail needed because nothing then asserts it.

### Note 3: #3113 is an accepted limitation, not a pending fix

#3113 closed as COMPLETED once limit 8 was documented. FR-015 then measured a structural matcher tightening and rejected it for false positives (`resolve_workspace_for_wp`, `get_wp_lane`, …).

The two strict xfails are therefore honest pins of an accepted blind spot, and the spec's edge-case rule applies: re-point, do not remove.

- **Alternative, if the operator wants no "won't-fix" tracker:** turn both into passing characterization assertions (`assert _find_sinks(...) == []` with a "limit 8" message), backed by the existing docstring pin.
- **Cost of either route:** the landmine guard (`…_landmines_disposition_still_pending`) must change in the same edit. It asserts the xfail set and `"#3113" in reason`.

### Note 4: the #932 guards cite a version, not the issue

- **What the skip says:** "requires spec-kitty-events >= 5.0.0". #932 appears only in the test docstring as provenance.
- **Why it is dead:** the dependency floor is 10.4.0, so the skip is unreachable.
- **What the dead branch hides:** the unreachable branch at `test_mission_state_repair.py:161-164` is the *only* test of the product refusal at `mission_state.py:1182-1184`, so that product branch is effectively untested. Retiring the dead guards should come with the explicit version-monkeypatch negative test in row 6.

### Note 5: open-question register for the planner

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | FR-001 two red tests: fragment.yaml + product fix, or `check_drg_root=False` fallback? | Product fix (fits one WP; C-005 permits it, being surfaced by an unmasked test) |
| Q2 | #3113: file a new "accepted residual" issue, or convert to characterization asserts? | File a new issue (the spec's edge-case rule) |
| Q3 | Stress SLA: split into a `timing` test, or record-only? | Split into a `timing` test |
| Q4 | FR-003 lane: relocate the file, or add a registry/nightly lane? | See the quarantine section; relocation |

---

## Quarantine root cause (FR-003)

**What was measured on this tree (`74373ec95a` base):**

| Run | Result |
|---|---|
| `SPEC_KITTY_RUN_QUARANTINE=1 pytest <file> -n0` | 23 passed |
| same, `-n 2 --dist loadfile` × 3 | 23 passed each |
| same, `-n 4 --dist load` × 2 | 23 passed each (tests of the file scattered across workers) |
| the 6 `tests/cross_cutting/misc/*` files, `-n0` | 51 passed, 3 skipped (unrelated) |
| 23 accept-family neighbours (`tests/specify_cli/acceptance/test_*.py`, `tests/specify_cli/cli/commands/test_accept*.py`, `test_issue_4891_accept_missing_lanes.py`), then this file, `-n0` | 392 passed |

**Original failure (EXPERIMENTAL#171 body).**
- All 8 family nodes failed in two full-suite `-n auto` runs on two SHAs, including bare main, and passed alone.
- The same runs also flagged the `agent_context_resolve` quartet (#160).
- That signature is **deterministic cross-file state leakage within a worker**, not an intra-file race.
- The VM evidence paths are gone. The quarantine commit `24190343d6` also added `repo_root=tmp_path` to an `emit_inner_state_changed` call in `tests/architectural/test_2093_authority_invariant.py`. Without that argument, the call resolved the repo root from ambient state and wrote through it. That test is a plausible polluter the #171 implementer spotted.

**Named shared-state root cause.**
- The leak class is **process-global state inherited across files in a worker**: ambient `SPEC_KITTY_*` environment and the cwd-derived repo root. The in-process `accept` (`resolve_owned_or_adopt(cwd=Path.cwd())`, mission/repo resolution) reads both.
- Two structural fixes landed after the quarantine, which explains why the leak no longer reproduces:
  1. **`SPEC_KITTY_*` env-namespace snapshot/restore** in the autouse `_isolated_worker_home` fixture (`tests/conftest.py` ~395-420, WP06 FR-015). In this line's history it arrives with `9370ec2c23`, 2026-09-07.
  2. The **#5030 real-fixture seeding** (`549f59f477`, `1409dc827f`). It de-quarantined the 3 sibling tests of the identical shape after "repeated broad `-n auto --dist loadfile` runs".
- The exact leaking variable is **unconfirmed**: the evidence is lost and the failure does not reproduce.

**Residual fragility (confirmed, fix it regardless).**
- All 5 tests do `json.loads(result.output)`. Under Click 8.3.3 / Typer 0.24.2, `CliRunner().invoke(...).output` **interleaves stderr**. Verified: stdout `{"a": 1}` plus stderr `noise` gives `output == '{"a": 1}\nnoise\n'` and `stdout == '{"a": 1}\n'`.
- Any stray stderr line from leaked logging or warning state in a worker breaks the JSON parse. That is exactly the "fails under -n auto, passes alone" signature.
- **Fix:** parse `result.stdout` in the 5 tests. The 3 de-quarantined siblings have the same pattern.

**Why they "run nowhere" (the real FR-003 blocker).**
1. **Quarantine wiring.**
   - The marker is registered in `pytest.ini:51`.
   - `tests/conftest.py:320-338` adds a skip unless `quarantine_opted_in(os.environ)` (`tests/_support/quarantine.py`: exactly `"1"`).
   - `.github/workflows/*.yml` sets `SPEC_KITTY_RUN_QUARANTINE` **nowhere** (grep: 0 hits).
   - The `quarantine-visibility` job (then in `ci-quality.yml`, listing this very file) was deleted by `e8cc2f444f` on 2026-08-27, the day after the quarantine.
   - Leftover references to that job: `scripts/ci/quality_gate_decision.py:47,60,186-222`, and docstrings in `tests/architectural/test_marker_job_completeness.py:31`, `test_workflow_coherence.py:18` and `test_suite_jobs_gate_blocking.py`.
2. **Lane topology (the larger problem).**
   - `tests/cross_cutting/misc` is listed in `.github/ci-module-registry.yml` `out_of_matrix_test_dirs` (line 732) under a "performance marker home … no per-PR lane selects this directory" reason.
   - The file is `pytestmark = [pytest.mark.integration]`, so the nightly interpreter shard (`-m "fast or unit"` over `tests/cross_cutting`) deselects all 23 tests (verified: `-m "fast or unit"` collects 0 of 23).
   - The per-PR `e2e` router job runs only `tests/e2e`.
   - **The whole file, 18 non-quarantined tests included, is executed by no CI lane.**

**Recommendation: fix the parallel-unsafety and put the file in a lane.** No serial lane is needed.
- (a) Remove `_ACCEPT_COMMAND_XDIST_QUARANTINE` and its 5 uses.
- (b) Parse `result.stdout` in the accept-CLI JSON assertions.
- (c) Give the file a lane. The cheapest honest choice is to **relocate** it to `tests/specify_cli/acceptance/test_acceptance_support.py`:
  - It tests `specify_cli.acceptance` and the `accept` CLI.
  - The nightly `specify_cli out-of-matrix` job then runs it under `-n auto --dist loadfile` (`ci-nightly.yml:1037-1053`), the exact condition that originally failed, which makes it the right regression surface.
  - Relocation touches `ruff.toml` (the file's per-file-ignore key) and the `tests.lane_test_utils` imports stay valid.
  - Alternative: add `tests/cross_cutting/misc` to an existing registry module's `test_dirs` for per-PR execution. That is a census-gated registry edit plus removing it from the ledger at line 732, which is heavier.
- **Verification for FR-003:** run the chosen lane's exact pytest command with `--collect-only -q` and grep for the 5 node ids.

**Adjacent, same structural cause, not in FR-003's five.** These three open-issue quarantines also run nowhere. Flag them to the planner; decide at plan time.
- `tests/characterization/test_trio_transitions.py::test_corrupted_events_file_raises_acceptance_error` (EXP#1021 OPEN)
- `tests/specify_cli/acceptance/test_accept_gate_read_surface.py::test_planning_read_dir_raises_when_kind_leaves_primary` (EXP#1021 OPEN)
- `tests/review/test_verdict_save_performance.py::test_uncontended_real_verdict_save_median_is_below_two_seconds` (EXP#901 OPEN)

---

## Declared platform / tool-guard list (FR-004 exemptions: KEEP)

These convert a genuine platform or tool absence into a skip. They are the only error→skip sites FR-004 exempts. They were found by an AST scan of `pytest.skip`/`xfail` inside `except` handlers across `tests/`, plus a grep of `skipif`/`importorskip`/`returncode`-gated skips.

| Class | Sites (file:line) |
|---|---|
| **Symlink unsupported** (`OSError` / `NotImplementedError`) | `tests/charter/test_generator.py:31,58,85`; `tests/charter/test_governance_references.py:85`; `tests/cross_cutting/encoding/test_encoding_validation_functional.py:325`; `tests/integration/test_explicit_checkout_commands.py:624,906`; `tests/mission_runtime/test_owned_checkout.py:216,231,261`; `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py:299`; `tests/specify_cli/invocation/test_writer.py:125,141,183`; `tests/specify_cli/session_presence/test_claude_code_hook.py:141,159`; `tests/specify_cli/test_analysis_report.py:486,506,561`; `tests/test_test_venv_bootstrap.py:404,434`; `tests/unit/intake/test_traversal_symlink_block.py:74,93`; `tests/upgrade/migrations/test_m_0_12_1_remove_kitty_specs_from_gitignore.py:219,236,328`; `tests/upgrade/migrations/test_m_0_16_2_remove_wp_status_gitignore_rule.py:168,185,253` |
| **Docker absent** | `tests/docs/test_plantuml_render.py:37`, `tests/docs/test_plantuml_sandbox_negative.py:50`, `tests/docs/test_plantuml_no_egress_corpus.py:73` |
| **Playwright / browser absent** | `tests/ui/test_dashboard_wp_modal.py:44`, `tests/ui/test_glossary_page_render.py:28` |
| **git capability / checkout shape** | `tests/architectural/test_dead_builtin_doc_paths.py:76` (`git grep` returncode not in {0,1}: not a git checkout, e.g. an sdist); `tests/charter/test_canonical_root_resolution.py:226` (`git submodule add` refused by the host's file-protocol policy) |
| **By-design topology refusal** | `tests/charter/evidence/test_orchestrator.py:206`: charter synthesize refuses linked worktrees by design (#4785, closed as the design decision). The charter slice is done; keep. |
| **CI auth environment** | `tests/adversarial/test_distribution.py:255` (`logged_out_on_connected_teamspace`; CLAUDE.md baseline-red category 2) |
| **Env-gated chokepoints** (policy, not errors) | quarantine (`tests/conftest.py:337`, see above); performance (`tests/conftest.py` ~322, `SPEC_KITTY_RUN_PERFORMANCE`, run by `ci-nightly.yml`). The performance reason cites #3595 (CLOSED), a stale citation only; correct it if the file is touched (NFR-004). |

**Out of this mission's scope (C-004, tracker slice), same masking class:**
- `tests/tracker/test_gateway.py:567` and `tests/contract/spec_kitty_tracker_consumer/test_consumer_contract.py:136` both call `pytest.importorskip("spec_kitty_tracker.context", reason="… needs spec-kitty-tracker>=0.5")`.
- The declared floor is `>=0.5.2`, so both are dead guards that mask a stale venv.
- Hand them to the tracker slice.

---

## FR-005 pre-assessment: predicted reds when unmasked

| Item | Predicted red? | Class | Path |
|---|---|---|---|
| Rows 1, 3 (7 doctrine-probe tests) | no (verified pass) | — | keep |
| Row 2 (2 intent-suppression tests) | **yes** (verified: `drg_root_graph_missing`) | **stale fixture**. Investigating it surfaced an adjacent **real defect** (fragment.yaml intent ignored) | Fix the fixture; the product fix fits **one WP** (small): red-first via fragment.yaml fixture → `_collect_fragment_edge_intent` fix |
| Row 4 (#3113 xfails) | yes (by design) | accepted limitation | stays a strict xfail on a new open issue |
| Row 5 (5 quarantined) | no (verified pass ×6 configurations) | — | keep; lane + stdout hardening |
| Rows 6–7, 9 | no (already executing) | — | cleanup |
| Rows 10–11 (wheel build/install) | no on a healthy tree (unverified: not run) | — | convert |
| Row 13 (version detection) | no (verified) | — | convert |
| Row 14 (stress SLA) | unknown (not run, C-001) | environment budget | split the budget into `timing`; a slow runner then reports an honest `timing` red, never a skip |
| Row 15 (home isolation) | no (verified) | — | convert |
| Row 16 (10 contract round-trips) | no (verified: 29/29 with the relocation map) | — | convert |
| Rows 17–18 | no | — | convert |

**Net:** one real product defect, the fragment-intent gap. It fits in one WP, so no new strict xfail is needed for FR-005. The only other xfails that stay are the two #3113 accepted-residual pins.

---

## Files touched (for WP grouping without overlap)

`fmt-excl` marks a file in `pyproject.toml [tool.ruff.format].exclude`. `pfi` marks one in `ruff.toml` per-file-ignores.

**Advice:** edit excluded files *without* running `ruff format` on them. Reformatting forces a `pyproject.toml` exclude-list removal (`test_ruff_format_exclude_ratchet.py`), and `pyproject.toml` would then become a shared conflict file across WPs.

**WP-A: doctrine probe + fragment-intent fix (FR-001, FR-005)**
- `tests/specify_cli/doctrine/test_pack_validator.py` (fmt-excl)
- `tests/integration/test_quickstart_end_to_end.py` (fmt-excl)
- `src/specify_cli/doctrine/pack_validator.py` (fmt-excl; only with the product-fix option, in its own commit)

**WP-B: closed-issue markers (FR-002)**
- `tests/architectural/test_egress_consent_boundary.py` (xfail reasons + landmine guard + docstring cross-ref)
- `tests/migration/test_teamspace_migration_rehearsal.py`
- `tests/migration/test_mission_state_repair.py` (+ new negative version test)
- `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py`
- `tests/doctrine/test_packaging_parity.py` (fmt-excl)
- `tests/integration/test_clean_install_next.py` (fmt-excl)
- `tests/_support/shared_package_deferral.py` (delete)
- `tests/architectural/test_saas_sync_gate_selection_invariance.py` (fmt-excl; docstring only)
- Tracker action outside the diff: file the new "egress limit 8" issue.

**WP-C: quarantine (FR-003)**
- `tests/cross_cutting/misc/test_acceptance_support.py` (pfi): remove the marker, use `result.stdout`. Relocate it to `tests/specify_cli/acceptance/`, or edit `.github/ci-module-registry.yml` instead.
- `ruff.toml` (pfi key rename, only if relocated)
- Optional residue cleanup of the deleted `quarantine-visibility` lane: `pytest.ini` (marker text), `scripts/ci/quality_gate_decision.py`, the docstrings of `tests/architectural/test_marker_job_completeness.py` / `test_workflow_coherence.py` / `test_suite_jobs_gate_blocking.py`, and `docs/development/testing/testing-flakiness.md`. It could be split into its own WP to keep the arch-file blast radius out of WP-C.

**WP-D: error→skip conversions (FR-004)**
- `tests/conftest.py` (pfi; cross-cutting: run `tests/architectural/test_home_owner_behaviour.py`, which pins conftest definition names, plus `test_real_home_isolation_guard.py`)
- `tests/_support/shared_build_artifacts.py` (docstring; optional `--no-isolation`)
- `tests/doctrine/test_wheel_packaging.py` (delete dead fallback)
- `tests/cross_cutting/versioning/test_version_detection.py` (fmt-excl)
- `tests/stress/test_concurrent_emits.py` (fmt-excl)
- `tests/architectural/test_real_home_isolation_guard.py` (fmt-excl)
- `tests/contract/test_example_round_trip.py` (fmt-excl)
- `tests/retrospective/test_events_shapes.py`
- `tests/upgrade/test_unified_bundle_migration.py` (fmt-excl)
- `tests/specify_cli/core/test_wps_manifest.py` (fmt-excl)

There are no file overlaps between WP-A..D. `tests/conftest.py` is touched only by WP-D; WP-C reads the quarantine gate but does not need to edit it.

## Verification commands used (reproducible)

```bash
# FR-001 baseline (9 skipped)
uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py -n0 -rs -q
# FR-002 #3113 strict xfails (2 failed: "scanner went blind to transport-call")
uv run --frozen pytest "tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape" -rxX --runxfail -q -n0
# FR-002 #932 (61 passed, 0 skipped)
uv run --frozen pytest tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py -n0 -rs -q
# FR-003 (23 passed in every configuration)
SPEC_KITTY_RUN_QUARANTINE=1 uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -n 2 --dist loadfile -q
SPEC_KITTY_RUN_QUARANTINE=1 uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -n 4 --dist load -q
uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -m "fast or unit" --collect-only -q   # 0/23 collected
# FR-004
uv run --frozen pytest tests/cross_cutting/versioning/test_version_detection.py -n0 -rs -q        # 18 passed
uv run --frozen pytest tests/architectural/test_real_home_isolation_guard.py -n0 -rs -q           # 8 passed
uv run --frozen pytest tests/contract/test_example_round_trip.py -n0 -rs -q                       # 19 passed, 10 skipped
```

Issue states were read with `gh issue view <n> -R spec-kitty/spec-kitty` or `-R spec-kitty/EXPERIMENTAL-spec-kitty --json state,closedAt,stateReason`:
- #3113 CLOSED 08-02, COMPLETED
- #932 CLOSED 05-10
- #3213 CLOSED 08-10
- #3980 CLOSED 09-09
- #5030 CLOSED 09-25
- EXP#171 CLOSED 08-26, COMPLETED
- EXP#828 CLOSED 09-01
- EXP#1021 OPEN
- EXP#901 OPEN
- spec-kitty#828 CLOSED (unrelated docs epic)
