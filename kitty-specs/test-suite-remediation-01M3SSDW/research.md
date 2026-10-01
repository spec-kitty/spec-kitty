# Research: Test-suite remediation (Phase 0 consolidation)

**Mission**: `test-suite-remediation-01M3SSDW`. Parent: #5353. Addresses: #5346.

**Base**: `issue-5353-test-suite-remediation` at `732f445a1e`, based on `upstream/main` `74373ec95a`.

This file consolidates three lens reports. It does not repeat their evidence tables; it cites them. The evidence lives in:

- [`research/masked-greens.md`](research/masked-greens.md) (debugger-debbie): masked-green rows 1–18, the quarantine root cause and the platform/tool-guard list;
- [`research/pin-inventory.md`](research/pin-inventory.md) (researcher-robbie): #5346 rows 1–7, the FR-007 table F1–F12, and the kept-ratchet table. Its §3 census proposal and its G8 group are **withdrawn** (see D-2);
- [`research/dead-symbol-rekey.md`](research/dead-symbol-rekey.md) (architect lens): the FR-009 options, staleness semantics, migration parity and the brownfield map.

## Binding rulings (not re-opened)

These rulings come from the orchestrator (`traces/design-decisions.md`) and the operator decision moments.

- **R1 Scope.** Masked greens (FR-001..FR-005) plus pin honesty (FR-006..FR-009, FR-011). There is no census gate (C-008, DM-01M3SVDP).
- **R2 Dead-symbol allowlist:**
  - re-key to `(module, name)` in `tests/architectural/dead_symbol_allowlist.yaml`, loaded by `tests/architectural/_dead_symbol_allowlist.py`;
  - category ids are the existing `_CATEGORY_*` names, lower-cased;
  - retire the refresh helper and `SymbolKey.source_module`;
  - add a size-ratchet row, and convert the `test_ratchet_baselines.py:618` `== 15` pin to a floor in the same concern;
  - fold the #470 widened list into the same YAML;
  - write one ADR in `docs/adr/4.x/`, partially superseding D-1 of the relocation-hardened mission;
  - keep `tests/unit/test_symbol_key.py` `len(index) == 400`;
  - the converter keys on `module_path`;
  - do not rename `test_no_dead_symbols.py`.
- **R3 Ratchets that move only with debt stay**, each with a recorded disposition. The FR-007 class is the live-structure pins plus the #5346 rows. "cardinality-is-contract" is treated as a pin.
- **R4 FR-005 product fix is in scope**, red-first and in its own commit, with a new issue. The #3113 xfails are re-pointed to a new open issue, and the landmine guard changes in the same edit. The #932 and #828 guards are retired. A version-monkeypatch test replaces the dead branch. The sync gate is kept and re-cited.
- **R5 Quarantine.** Remove the marker, parse `result.stdout`, and relocate the file to `tests/specify_cli/acceptance/`. Verify with the shard registry.
- **R6 FR-004.** Convert the listed sites, delete `_build_wheel_fallback`, split the stress budget into a `timing` test, and add the relocation map. The platform/tool-guard list is the exemption list.

---

## Decisions

### D-1 — Doctrine probe: delete it, assert the precondition (FR-001)

- **Decision**: Delete both `_has_built_in_doctrine()` probes and their skips. Replace them with a precondition **assert** through `charter.offering.pack_paths.built_in_dir(ArtifactKind.TACTIC)`, on the fixture tactic id.
- **Rationale**:
  - The probe reads `resolve_doctrine_root()/"tactics"/"built-in"`. That is the doctrine *package* root, which does not exist, so all 9 tests skip on every run.
  - Packs always ship, and `built_in_dir` fails closed with `PackRootNotFound`. A "skip if absent" probe is therefore always either dead or masking.
  - The assert keeps the two `collision_advisories == []` tests from passing vacuously if the fixture id is ever renamed.
  - Verified in scratch: 7 of 9 pass (masked-greens, headline 1 and note 1).
- **Alternatives**:
  - Fix the probe path and keep a skip. Rejected: it is still a masking probe for a condition that cannot legitimately occur.
  - Use `SPEC_KITTY_PACKS_ROOT`-aware skips. Rejected for the same reason.

### D-2 — Withdrawn census gate: adversarial-evidence disposition (FR-010, NFR-002, SC-006)

- **Decision**: Add no census gate (C-008). Pin-inventory §3 and its G8 grouping are **not** implemented. The one element of G8 that survives is the conversion of `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` to a floor (#5346-1 / F2). It moves to IC-12, because the size-ratchet row trips it.
- **Rationale**. The adversarial evidence was weighed on both sides:
  - **For a gate** (pin-inventory §3): a narrow R1/R2 AST rule would have 38 live hits instead of about 2,000. It would use per-site content keys through the #5085 `ContentDescriptor` substrate, have no inline escape marker, and run in about 1.5 s.
  - **Against a gate** (dead-symbol-rekey §8.5.1; ADR `docs/adr/3.x/2026-09-14-1-census-floor-ratchet-adjudication.md`):
    - The predecessor `test_golden_count_ban.py` made **0 real catches**.
    - It forced **13 whole-tree re-freezes** and levied **387 annotation tolls**.
    - Its classifier bug taxed honest dynamic-result cardinality asserts.
    - The ADR's accepted consequence is that a future `len(X) == N` regrowth "is caught by review rather than CI".
    - A gate would also have to coexist with `test_timing_coverage_invariant.py`, which pins exact-count texts verbatim. That needs a shared definition of "live collection pin" that nobody owns.
  - **Adjudication** (DM-01M3SVDP, operator): honour the ADR.
    - The narrowness argument reduces the toll but does not produce a catch record. The rule's own known misses cover most of the recurring class: locals, parametrize tables and function-scope imports (F3–F7). So the gate would guard the minority of pins while re-opening a retired decision.
    - Converting the existing pins removes the friction directly. Regrowth stays a review concern.
- **Alternatives**:
  - A narrow blocking gate with a superseding ADR. Rejected by DM-01M3SVDP.
  - An advisory report only. Rejected: an advisory that nobody gates rots, like the predecessor's advisory phase from #3458 to #4315.

### D-3 — Unmasked defect: fix red-first in-mission (FR-005)

- **Decision**:
  - Fix `pack_validator._collect_fragment_edge_intent` so that it also folds `drg/fragment.yaml` edges, through the existing org-fragment loader.
  - The fix commit is separate from the red commit.
  - The regression test runs through `validate_pack(pack_dir)`, the pre-existing entry point the `doctrine` CLI calls.
  - A new issue (filed during implementation) records the defect.
- **Rationale**:
  - The intent the runtime *reads* (`fragment.yaml`) is ignored, so authors are told to declare intent they have already declared. `*.graph.yaml` is a hard error since #3387.
  - Net effect: no DRG shape validates clean with declared intent (masked-greens, note 2).
  - The fix fits one work package, so DM-01M3SSV4 requires fixing it.
- **Alternatives**:
  - The `check_drg_root=False` fallback. Rejected: it re-masks a known defect.
  - A strict xfail on a new issue. Rejected: that is only for defects too large for one work package.

### D-4 — #3113: re-point to a new open issue, keep strict (FR-002)

- **Decision**:
  - Re-point both strict xfails to a newly filed open issue, "egress guard limit 8: all-positional injected transport call (accepted residual)".
  - In the same edit, update the landmine guard `test_positional_transport_strict_xfail_landmines_disposition_still_pending`, which asserts `"#3113" in reason`, and the limit-8 docstring cross-reference.
- **Rationale**:
  - #3113 closed COMPLETED once limit 8 was documented. FR-015 measured a matcher tightening and rejected it.
  - Under `--runxfail` the xfails still fail for the stated reason, so these are honest pins of an accepted blind spot.
  - The spec's edge case: a strict xfail citing a closed issue that still fails is re-pointed, not removed (masked-greens, note 3).
- **Alternatives**: Characterization asserts (`_find_sinks(...) == []`) with no tracker. Rejected by R4; it hides the residual from the tracker.

### D-5 — #932 and EXPERIMENTAL#828 guards: retire; add the missing negative test (FR-002)

- **Decision**:
  - Delete `_has_events_5` in 3 files, its 6 guard sites, both `clean_install_acceptance_deferred()` skipifs, and `tests/_support/shared_package_deferral.py`.
  - Replace the unreachable branch at `test_mission_state_repair.py:161` with a version-monkeypatch test of the product refusal at `src/specify_cli/migration/mission_state.py:1183-1184`.
- **Rationale**:
  - Both guards are unreachable: the dependency floor is `spec-kitty-events>=10.4.0`, and the lock takes both shared packages from PyPI. 0 of 61 and 0 of 2 fire.
  - The unreachable branch was the **only** test of the product refusal. Retiring the guard without replacing it would leave that product branch untested.
  - Covering guards for "no git pin re-enters": `test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies` and `::test_shared_dependencies_use_public_pypi_ranges` (masked-greens rows 6–7).
  - The spec-kitty#828 and EXPERIMENTAL#828 ambiguity is recorded in the evidence.
- **Alternatives**: Re-cite the guards to a current version. Rejected: the guard can never fire, so re-citing it keeps dead code.

### D-6 — Sync gate: keep and re-cite (FR-002)

- **Decision**: Keep `test_saas_sync_gate_selection_invariance.py`. Rewrite its docstring premise from "import-time skipif gates" (#3213, closed) to "process-global opt-out kill-switch pollution (post-#3980)".
- **Rationale**:
  - The flag is still read at runtime by `core/saas_sync_config.py` and `tracker/saas_readiness.py`, so a module-scope write still pollutes the worker.
  - No other gate bans module-scope env writes, so retiring this one would violate C-002.
- **Alternatives**: Retire the module. Rejected: there is no covering guard.

### D-7 — Quarantine: fix the fragility and relocate into a collected tree (FR-003)

- **Decision**:
  - Remove the quarantine marker.
  - Parse `result.stdout`, because Click 8.3's `.output` interleaves stderr.
  - `git mv` the file to `tests/specify_cli/acceptance/test_acceptance_support.py`, and rename the `ruff.toml` per-file key.
- **Rationale**. Two problems, one structural:
  - The 23 tests pass under every configuration measured (serial, `-n 2 --dist loadfile` ×3, `-n 4 --dist load` ×2, and after 23 neighbours). The original leak was ambient `SPEC_KITTY_*` / cwd state, and the `SPEC_KITTY_*` snapshot/restore in `_isolated_worker_home` and the #5030 seeding have since fixed it.
  - The real blocker is structural:
    - `tests/cross_cutting/misc` is out-of-matrix;
    - the nightly interpreter shard's `-m "fast or unit"` deselects this `integration`-marked file;
    - the `quarantine-visibility` job was deleted by `e8cc2f444f`.

    So the **whole file** runs in no lane.
  - **Registry verification (this plan).**
    - `tests/specify_cli/acceptance` sits in `out_of_matrix_test_dirs` (`.github/ci-module-registry.yml:640`) and is claimed by no `modules[]` row.
    - The nightly `specify-cli-out-of-matrix` job ignores only the registry-claimed `tests/specify_cli/*` dirs and runs the rest with `-m "not stress and not timing" -n auto --dist loadfile` (`ci-nightly.yml:1015-1056`).
    - So the destination is collected, under the exact xdist condition of the original failure.
    - There is no fixture shadowing at the destination: `feature_repo` is defined only in `tests/conftest.py`, and there is no `tests/specify_cli/acceptance/conftest.py`. The basename is unique.
- **Alternatives**:
  - Add `tests/cross_cutting/misc` to a registry module's `test_dirs`. Heavier: a census-gated registry edit plus a ledger removal.
  - A serial lane. Unnecessary: the tests are parallel-safe.
  - De-quarantine only. Insufficient: the file still runs nowhere.

### D-8 — Error-to-skip conversions and the exemption list (FR-004)

- **Decision**:
  - Convert masked-greens rows 10, 11, 13, 15, 17 and 18 to fail.
  - Delete the dead row-12 `_build_wheel_fallback`.
  - Split row 14's SC-12 budget into a separate `@pytest.mark.timing` test, with the budget hoisted to `_SC12_BUDGET_SECONDS`.
  - Correct the stale #3595 citation on the performance chokepoint in `tests/conftest.py` (NFR-004 campsite).
  - **Exempt** exactly the masked-greens "Declared platform / tool-guard list": symlinks unsupported, Docker absent, Playwright absent, git capability or checkout shape, by-design topology refusal, CI auth environment, and the env-gated chokepoints.
- **Rationale**:
  - `build`, `hatchling`, `jsonschema` and `spec-kitty-events` are declared dependencies, so their absence is a stale venv (CLAUDE.md baseline-red category 4), not a platform.
  - A packaging or metadata failure is exactly the defect FR-004 names.
  - The home-isolation skip fires *only* on the regression it guards.
  - The stress split keeps correctness PASS and budget FAIL separate. That avoids a wall-clock flake on shared runners, and the flakiness policy forbids retry-to-green.
  - **Brownfield check.** `test_timing_coverage_invariant.py:327-337` pins the stress file's functional assertion texts. They must stay in a non-`performance` test, and the timing-only test carries only vocabulary tokens (`duration`, `budget`).
- **Alternatives**:
  - Stress budget as `record_property` only. Rejected by R6.
  - A bare `pytest.fail` in the stress test. Rejected: a wall-clock flake.
- **Residual**: The `timing` marker has no live CI job (`pytest.ini:57`). See plan RK-3.

### D-9 — Contract round-trips: a test-side relocation map (FR-004)

- **Decision**: Add a new `tests/contract/_module_relocations.py` with a longest-prefix-first `HISTORICAL_TO_CANONICAL` map:
  - `doctrine.drg` → `charter.offering.drg`;
  - `specify_cli.next._internal_runtime` → `runtime.next._internal_runtime`;
  - `charter.scope` → `charter.activation.scope`;
  - `charter.schemas` → `charter.activation.schemas`.

  `test_example_round_trip.py` imports through the map and fails when a module is absent from both names. A self-test checks that the map has no dead rows.
- **Rationale**:
  - The archived contracts are immutable (C-006), and their modules were relocated long ago.
  - Today there are 10 permanent skips. With the map: 29 passed, 0 skipped (verified in scratch; masked-greens row 16).
- **Alternatives**:
  - Edit the archived contracts. Forbidden by C-006.
  - Delete the round-trip cases. Rejected: that loses executed coverage of live model shapes.

### D-10 — Dead-symbol identity is `(module, name)` (FR-009)

- **Decision**:
  - Key every entry on `(module, name)`, where `module` is the `__all__`-declaring module the gate evaluates.
  - Never persist a body hash.
  - Keep runtime hashing only for (a) the keyability precondition (INVALID) and (b) auto-exempt condition (1), `final_key.module_path is None`.
- **Rationale**:
  - Since 2026-08-18, 41 of 78 allowlist commits were body-edit re-pins (57 entries). 25 of them did nothing else, and 0 sampled re-pins changed a rationale. One re-pin was formatter-induced (`2641f6b181`).
  - The hash's claimed relocation-proofness is already defeated by the `source_module` guard (`:2425`): a move costs one edit per entry today.
  - `(module, name)` is unique per location by construction, so the 18 collision-escalated module_path-tier entries and the T016 suppression disappear (dead-symbol-rekey §1–§3).
- **Alternatives** (dead-symbol-rekey §3):
  - B, `(module_path, qualname)`: the same shape, but it over-promises nested-symbol coverage.
  - C, a stored advisory hash: it rots silently.
  - E, advisory hash plus an automatic refresh: it still edits test source, so it fails NFR-003. `01M0A42D` already tried this.

### D-11 — The allowlist is externalised to YAML with a schema-enforcing loader (FR-009, DIRECTIVE_044)

- **Decision**:
  - Data lives in `tests/architectural/dead_symbol_allowlist.yaml`, loaded by `tests/architectural/_dead_symbol_allowlist.py`. The schema is in data-model.md §1 and the contract in contracts/dead-symbol-allowlist.md.
  - `_SYMBOL_ALLOWLIST` and `_WIDENED_SCOPE_GRANDFATHERED_470` stay module attributes of the gate, loaded at import.
  - Category ids are the lower-cased constant names without the leading underscore (R2; plan RK-4).
- **Rationale**:
  - Data edits and logic edits currently share a 4,824-line file that co-changes with 516 src files.
  - The loader turns free comments into enforced fields: rationale is required, an issue is required where the category demands one, and uniqueness covers the whole file. That closes the intra-category duplicate blind spot (`check_push_safety` ×2).
  - There is precedent: `inline_meta_read_allowlist.yaml`, `charter_path_literal_allowlist.yaml`, `mission_type_reader_allowlist.yaml` and `requirement_id_pattern_allowlist.yaml`.
- **Alternatives**: Keep the frozensets in Python with the new key. Rejected: the co-change coupling stays, and rationale stays unenforced.

### D-12 — Fold the #470 widened grandfather list into the same YAML (FR-009, DIRECTIVE_044)

- **Decision**:
  - Move the 91 `"module::Name"` strings into a `widened_grandfathered_470` section of the same file, under the same loader.
  - Parity: the set of strings is identical before and after.
  - The widened stale semantics (`_compute_widened_stale`: "no longer a widened offender" / "already rescued") are **unchanged**. A change to the #470 scope is a non-goal.
- **Rationale**:
  - Two exemption authorities in one gate, with different key types and different stale logic, is a parallel authority.
  - The only stated reason to keep them apart was that content keys can collide with widened names (`:3815-3829`). `(module, name)` keys cannot.
- **Alternatives**: Leave the list in Python. Rejected: R2.

### D-13 — Size ratchet and the top-level-keys floor (Burn-down (a); #5346-1 / F2)

- **Decision**:
  - Add `_SizeRatchet("test_no_dead_symbols", "allowlist_entries", "tests.architectural._dead_symbol_allowlist", "SYMBOL_ALLOWLIST")`, with the `_baselines.yaml` leaf set to the live count at landing (293 today).
  - In the same concern, replace `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 15` with a `>= 15` floor.
  - Re-plant the planted-leaf test at `:564-570`, which currently plants `test_no_dead_symbols` as an unenforced section.
- **Rationale**:
  - Charter Burn-down (a) caps every mutable architectural allowlist. The dead-symbol list has had **no** cap since `01M0A42D` deleted the inert key.
  - The YAML makes growth cheaper, so the cap must land with it.
  - `_REQUIRED_TOP_LEVEL_KEYS` is derived from `_SIZE_RATCHETS`, so its exact count only restates the table: 3 re-pins since August.
  - The duplicate `(section, leaf)` check and the YAML-to-row bijection already carry the invariant (pin-inventory §2.1 row 1).
- **Alternatives**:
  - Bump the pin to `== 16`. Rejected: that repeats the pin class.
  - Put the count inside the YAML data. Rejected: that makes a second authority (the `inline_meta_read` three-copies anti-pattern).

### D-14 — Deferred, tracked follow-ups (DIRECTIVE_046: defer only with a rationale)

Each item below gets one new issue (filed during implementation) and an issue-matrix row. Locality keeps them out of this mission's file set (DIRECTIVE_024; plan RK-5).

- The `quarantine-visibility` lane residue (`scripts/ci/quality_gate_decision.py`, arch-test docstrings, `pytest.ini` marker text, `testing-flakiness.md`), plus a gate for "a marker that no lane collects".
- The three OPEN-issue quarantines that run in no lane (EXP#1021 ×2, EXP#901).
- The tracker-slice `importorskip("spec_kitty_tracker.context")` dead guards (C-004: the tracker slice is out of scope).
- The `inline_meta_read` three-authority count (dead-symbol-rekey §8.2).
- Simplifying auto-exempt condition (1) (dead-symbol-rekey §9).
- Optional: re-key F12's `EXPECTED_CALL_EXPRESSION_COUNT` as `{qualname: n}`.

---

## Pin dispositions (SC-004)

The legend:

- **convert**: replaced by an invariant form;
- **delete-with-guard**: retired, with a named covering guard (C-002);
- **keep-ratchet**: a baseline that moves only with debt (FR-008, C-003);
- **keep-contract**: a genuine contract cardinality, kept with its reason;
- **resolved**: already fixed upstream (Edge Case 6).

"Pin-inv" means `research/pin-inventory.md`.

| # | Site (HEAD file:line) | Class | Disposition | Invariant form / covering guard | Concern | Source |
|---|---|---|---|---|---|---|
| #5346-1 / F2 | `tests/architectural/test_ratchet_baselines.py:618` `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` | live-structure pin | **convert** (floor) | `>= 15`, plus the duplicate check `:611-613` and the leaf↔row bijection | IC-12 | pin-inv §2.1 r1 |
| #5346-2 / F1 | `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py:635` `len(SYMBOL_TO_MODULE) == 196` | pin ("cardinality-is-contract" is residue) | **delete-with-guard** | superset `:465`, native `:455`, disjoint `:484`, identity `:432`; floor `all(_SEAM_GROUPS.values())` | IC-06 | pin-inv §2.1 r2, §2.1a |
| #5346-3 | `tests/consolidation/test_mid8_embedded_preflight.py:383`, `:396-397` | copied grammar | **delete-with-guard** | `tests/consolidation/test_executor_lane_naming.py:141`; `tests/lanes/test_branch_naming_seam.py` | IC-06 | pin-inv §2.1 r3 |
| #5346-4 | `tests/consolidation/test_issue_4474_topology_aware_bake.py:244` | name/contract mismatch | **convert** (rename + re-scope) | the executor refusal guard `test_mission_number_truthful_4900.py:655` | IC-06 | pin-inv §2.1 r4 |
| #5346-5 | `tests/ci/test_recapture_charter_shard_timings.py:481`, `:490`, `:494` | copy pins | **convert** `:481`, `:494`; **delete-with-guard** `:490` | rendered-substitution assert; argv assert; `:336/:341` | IC-06 | pin-inv §2.1 r5 |
| #5346-6 | `tests/consolidation/test_behind_head_recovery_coverage.py:309`, `:332`, `:362`, `:384`, `:416`, `:435` | full private-signature pins | **convert** | `assert_called_once()` + `args[0] is exc`; one `base_sha` threading assert `:362` | IC-06 | pin-inv §2.1 r6 |
| #5346-7 | `tests/specify_cli/coordination/test_teardown_single_seam_routing.py:107` | literal-scan trap | **convert** (behavioural) | monkeypatched seam recorder; global absence `:81` | IC-06 | pin-inv §2.1 r7 |
| F3 | `tests/runtime/test_bridge_decision_builder.py:498` `materialize_calls == 29` | live-structure pin | **convert** (floor ≥ 1) | AST absence scan `:442` | IC-07 | pin-inv §2.3 |
| F4 | `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py:520`, `:521`, file sets `:525-575` | live-structure pin | **convert** (shape) | non-empty + path-shape invariants; per-triple contract test | IC-08 | pin-inv §2.3 |
| F5 | `tests/docs/test_glossary_linker.py:69`, `:101` | live-structure pin | **convert** (relational) | anchors == parsed terms + uniqueness `:71` | IC-08 | pin-inv §2.3 |
| F6 | `tests/git/test_guard_capability_regression.py:145`, `:167` | live-structure pin | **convert** (floor ≥ 1) | the per-site REFUSED loop `:175-180` | IC-07 | pin-inv §2.3 |
| F7 | `tests/unit/convergence/test_census_status.py:31`, `:32` | data-artefact size pin | **delete-with-guard** + floor | per-cluster consistency `:36`; PENDING `:33` | IC-08 | pin-inv §2.3 |
| F8 | `tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py:75` | live-structure pin | **delete-with-guard** | `:31`, `:48` | IC-07 | pin-inv §2.3 |
| F9 | `tests/architectural/test_no_absolute_event_timestamp_mixture.py:419`, `:420` | prose pin | **delete-with-guard** | `test_derived_mixture_matches_recorded_baseline` | IC-07 | pin-inv §2.3 |
| F10 | `tests/agent/test_agent_config_migration.py:238`; `tests/specify_cli/regression/test_twelve_agent_parity.py:233` | derived count of a contract set | **convert** (set equality) | `AGENT_DIR_TO_KEY` ↔ `AGENT_DIRS`; `NON_MIGRATED_AGENTS` ↔ `AGENT_COMMAND_CONFIG` | IC-08 | pin-inv §2.3 |
| F11 | `tests/architectural/test_remediation_effectiveness.py:325`, `:335`, `:341`, `:403` | `== *_FLOOR` + exact sum | **convert** (partition) | `emitting == set(_CASES)`, `all == emitting ∪ exempt`, disjoint; floors `>=` | IC-07 | pin-inv §2.3 |
| F12a | `tests/architectural/test_tracker_egress_guards_3108.py:947` `EXPECTED_ENCLOSING_COUNT` | redundant pin | **delete-with-guard** | set equality `:1150` | IC-07 | pin-inv §2.3 |
| F12b | `tests/architectural/test_tracker_egress_guards_3108.py:965` `EXPECTED_CALL_EXPRESSION_COUNT` | audited egress census | **keep-contract** | reason: each extra call expression is a new egress point needing review (#3108/#3030). The G4 mutation tests `:1229` stay. | IC-07 (record only) | pin-inv §2.3 |
| — | `tests/architectural/_baselines.yaml:387` destructive-op allowlist | ratchet | **keep-ratchet** | moved only with justified allowlist rows | — (record) | pin-inv §2.3 kept |
| — | `tests/architectural/_baselines.yaml:231` inert-slot ceiling | ratchet | **keep-ratchet** | 3 of 4 moves were burn-down; the growth was a real debt row | — (record) | pin-inv §2.3 kept |
| — | `_baselines.yaml:158` `category_7_grandfathered_orphans`; `:321`, `:50`, `:60`, `:72`, `:75`, `:356` | ratchets | **keep-ratchet** | justified moves | — (record) | pin-inv §2.3 kept |
| — | `tests/architectural/test_charter_path_literal_authority.py:575` `CHARTER_PATH_LITERAL_FLOOR` | ratchet (misnamed ceiling) | **keep-ratchet** | one historical FR-008 lapse (`583db03345`) is noted; the file is not touched, so no rename | — (record) | pin-inv §2.3 kept |
| — | `test_inline_meta_read_gate.py:75`/`:971`; `test_ratchet_positional_anchor_ban.py:1055`; the `>=`/`<=` floors listed in pin-inv §2.3 | ratchets / non-vacuity floors | **keep-ratchet** | shrink-only; correct as they are | — (record) | pin-inv §2.3 kept |
| — | the LOCAL TEST VALUE rows (pin-inv §2.3 last row) | behavioural counts | **not a pin** | behaviour of the unit under test | — (record) | pin-inv §2.3 |
| — | `tests/architectural/test_inline_meta_read_gate.py` `ROUTED_LOAD_META_FLOOR` | pin | **resolved** | deleted by `dd82bd340b` (#4315) | — | pin-inv §2.4 |
| — | the DRG `_EXPECTED_NODE_COUNT`/`_EXPECTED_EDGE_COUNT` | pin | **resolved** | `2e40057da1` (#3234), filesystem-derived | — | pin-inv §2.4 |
| — | destructive-op *line* re-pins | line anchors | **resolved** | #5085 (`133755de03`) | — | pin-inv §2.4 |
| — | `tests/unit/test_symbol_key.py:644` `len(index) == 400` | fixture-size assert | **keep** (not a live-structure pin) | pinned verbatim by `test_timing_coverage_invariant.py:338` | IC-11 (untouched line) | rekey §8.5.2 |
| — | `tests/architectural/test_timing_coverage_invariant.py:386` `== 62` | frozen evidence table | **keep-contract** | a canonical-commit snapshot | — (record) | rekey §8.2 |

**Count note.** The spec quotes "13 live-structure pins in 11 files" from the lens summary. The site-level table above is the authoritative inventory: F1–F12 cover 13 test files, and F12 splits into a delete and a keep. SC-004 is judged row by row, not against the summary count.

## Masked-green dispositions (FR-001..FR-004), for reference

The masked-greens.md rows map to the concerns as follows. Row 8 is a **false positive** and is recorded, not edited.

| Rows | Disposition | Concern |
|---|---|---|
| 1, 3 | RUN (probe deleted, precondition assert) | IC-01 |
| 2 | RUN + FIX (fragment.yaml fixture, product fix) | IC-01 |
| 4 | RE-POINT (new open issue; strict) | IC-02 |
| 5 | DE-QUARANTINE + RELOCATE into a collected lane | IC-03 |
| 6, 7 | RETIRE guards (+ negative version test for row 6) | IC-02 |
| 8 | NO-OP (false positive: "828" is a line number) | IC-02 evidence |
| 9 | KEEP + re-cite | IC-02 |
| 10, 11, 13, 15, 17, 18 | CONVERT → fail | IC-04 |
| 12 | DELETE dead code | IC-04 |
| 14 | CONVERT: split the budget into `timing` | IC-04 |
| 16 | CONVERT: relocation map | IC-05 |
| Platform/tool-guard list | KEEP (the FR-004 exemptions) | — |
