# Post-tasks squad review: coverage, non-vacuity and anchor accuracy

- **Reviewer:** reviewer-renata, running the `adversarial-squad-deployment` procedure at the post-tasks point-cut. It was read-only; this file is the only write.
- **Tree:** `issue-5353-test-suite-remediation` at `b9030a0102`. The 15 WP prompts are untracked working files.
- **Read:** `spec.md`, `plan.md` (including the Risk rulings), `research.md`, `research/{masked-greens,pin-inventory}.md`, `data-model.md`, `contracts/dead-symbol-allowlist.md`, `quickstart.md`, `tasks.md`, `tasks/WP01..WP15`, and the tactic `acceptance-criteria-non-vacuity` (loaded via `spec-kitty charter context`).
- **Anchor spot-check:** 94 file:line anchors and symbol names were checked against the tree with `sed -n`/`grep -n`. 90 are exact and 4 are off by 1–5 lines (listed in §4). No anchor points at the wrong symbol.
- **Runs:** no tests were run. One ruff probe was run on a throw-away file, created and deleted in the same command, to confirm B018 (finding m1). One read-only Python AST enumeration of `computer.py` was run for B2.

## Verdict: **FOLD-REQUIRED**

Two blockers and seven majors need folding into the prompts before implementation:

- **The two blockers.** In each, an implementer who follows the prompt exactly either records a vacuous proof (B1) or cannot satisfy the prompt on HEAD. In B2, the obvious improvisation also loses coverage against the pin it replaces.
- **The seven majors.** Each is a wrong covering guard, a neutral or violation plant that cannot discriminate, or a contradiction inside or between prompts that a reviewer would bounce.

Coverage is otherwise complete:
- every active FR, NFR, C and SC maps to concrete subtasks;
- every masked-green row, #5346 row, F-row, kept-ratchet row, M-case, L-rule, G-rule and RK ruling has an owner (§3).

## 1. Findings

| # | severity | WP | finding | concrete fix (exact text/anchor) |
|---|---|---|---|---|
| B1 | **blocker** | WP10, WP12 (also plan IC-09, quickstart Break #19, tasks.md WP10 Independent Test) | **The SC-003 real-tree plant is vacuous.**<ul><li>The plant is "add a docstring line to `append_lifecycle_event`", and WP10 T049 step 4 expects the base gate to go **RED** "because its body hash changed".</li><li>But the content-tier hash is `body_hash()` → `specify_cli.contracts.anchoring.code_tokens_by_line` (`src/specify_cli/contracts/anchoring.py:87-117`). It **drops `STRING` and `COMMENT` tokens**; the gate itself notes this at `test_no_dead_symbols.py:3818` ("body-hash (which drops string-literal content…)").</li><li>So a docstring edit leaves the hash, and the base gate, **GREEN**.</li><li>Consequences: the SC-003 "today ≥ 1 edit" red-first observation cannot be recorded; WP12 T060 step 2 ("stays GREEN") then proves nothing; and SC-003 ships without its before/after contrast.</li></ul> | Replace the plant everywhere: WP10 Objectives + T049 step 4, WP12 T060 step 2, quickstart Break #19 and plan IC-09 Proof. New text: *"Behaviour-neutral **code-token** body edit: in `src/specify_cli/status/lifecycle_events.py::append_lifecycle_event` (`:608-645`), rename the local `envelope` to `persisted_envelope` (all 4 occurrences). A docstring or comment edit does NOT change the content-tier hash (`code_tokens_by_line` drops STRING/COMMENT tokens) and must not be used."* Keep WP10's M1 synthetic `Baz = 1` → `Baz = 2` / `x + 1` → `x + 2` (those are code tokens, so they are fine). |
| B2 | **blocker** | WP08 (T034, F11) | **The F11 partition as written is false on HEAD, and it also loses coverage.**<ul><li>**(a)** `computer.py` constructs 5 non-emitting **pass-state** pairs that are not in `_EXEMPT_STATES`: `(_compute_charter_source, fresh)`, `(_compute_synced_bundle, fresh)`, `(_synthesized_drg_built_in_only_state, built_in_only)`, `(_synthesized_drg_missing_graph_state, built_in_only)` and `(_synthesized_drg_graph_state, fresh)`. So `all_states == emitting \| _EXEMPT_STATES` is RED day one (verified by AST enumeration).</li><li>**(b)** `emitting` is keyed on `(function, state)` pairs, and there are 4 of them. The floor `len(emitting) >= _REMEDIATION_STATE_FLOOR` (7, a **site** count) is also RED day one.</li><li>**(c)** If the implementer "fixes" this at pair granularity, the documented exploit on a **split** site survives green: neuter one of the two `missing` sites of `_compute_charter_source`, lower the floor to 6, and delete its `_CASES` entry. The pair is still emitting through the sibling site. The old `== 9` sum caught this, so FR-011 and C-002 regress silently.</li></ul> | Rewrite T034 step 2 as a **per-site** partition. Walk every `FreshnessSubState(...)` site once (one walker yielding `(lineno, function, state, has_remediation)`) and assert, for every site: `has_remediation or state in _PASS_STATES or (function, state) in _EXEMPT_STATES`. `_PASS_STATES` is already imported from `specify_cli.charter_runtime.preflight.runner` at `:109`. Also assert that no emitting site's `(function, state)` is in `_EXEMPT_STATES` (disjointness), and keep `expected_exempt == _EXEMPT_STATES` (`:389-394`). The floors become `>=` over **sites** (`len(emitting_sites) >= _REMEDIATION_STATE_FLOOR`). Add the violation plant *"set `remediation=None` on ONE of the two `missing` sites of `_compute_charter_source` (e.g. the `_REMEDIATE_UPGRADE_YES` site), lower `_REMEDIATION_STATE_FLOOR` to 6 and delete its `_CASES` row → the per-site partition goes RED"*. |
| M1 | major | WP02 (T007; also masked-greens row 6) | **The #932 covering guard is misnamed.** `test_pyproject_shape.py::test_events_dependency_floor_rejects_pre_v10_contract` (`:128`) **overwrites** the events dependency with `>=9,<10` itself, then checks the detector. It never reads the live floor, so the prescribed plant (`spec-kitty-events>=4.0` in a scratch `pyproject.toml`) leaves it **GREEN**. Following rule 3 ("if the guard stays green, stop") blocks the WP, or the implementer records a false RETIRE proof. | T007 "Covering guard (C-002)": replace it with `tests/architectural/test_pyproject_shape.py::test_shared_dependencies_use_public_pypi_ranges` (`:113`), which asserts the exact `_EXPECTED_SHARED_RANGES` (`:27-30`, `spec-kitty-events>=10.4.0,<11`) against the live `pyproject.toml`. The plant `spec-kitty-events>=4.0` reds it at `:118`. Correct masked-greens row 6 the same way. |
| M2 | major | WP06 (T026, #5346-6) | **The neutral plant cannot discriminate.** The tests use `patch.object(ex, "_report_pre_mutation_refusal")` with **no autospec** (`test_behind_head_recovery_coverage.py:24`, `:291`…). Adding a defaulted keyword parameter to the *callee* leaves `call_args` unchanged, so the **old** `assert_called_once_with(...)` form stays green too. The prompt's claim "Before the change, all 5 went red" is false, and the NFR-003 evidence would be vacuous. Also `:309` pins `mock_recover`, not `mock_report`. | T026 neutral plant: *"Add a defaulted keyword-only parameter `strategy: str \| None = None` to `_report_pre_mutation_refusal` (`executor.py:3897`) **and pass `strategy=state.strategy` at both call sites `executor.py:4066` and `:4077`**; for `:309`, do the same on `_recover_behind_head_primary_on_resume` (`:3971`, call site `:4060`). Old form: `:332/:384/:416/:435` (and `:309` for its plant) go RED. New form: GREEN with 0 edits."* Replace "all 5" with the per-mock counts. |
| M3 | major | WP04 (T019; also quickstart Break #9) | **The home-isolation planted break is incomplete.** HOME is redirected **twice**: process-wide by `_apply_home_env` (`tests/conftest.py:126-137`, called from `pytest_configure`) and per test by the autouse `_isolated_worker_home` loop (`:418`). T019 neuters only the fixture loop (`:373-420`), so `Path.home()` in the probe worker is still the isolated home from `pytest_configure`. The guard stays GREEN, so the plant is vacuous. | T019 planted break: *"Make BOTH redirects no-ops in scratch: the `for var in _HOME_ENV_VARS:` loop in `_apply_home_env` (`:134`) AND the one in `_isolated_worker_home` (`:418`). Before (stash): SKIP. After: FAIL."* Update quickstart Break #9 to match. |
| M4 | major | WP10, WP12 (tasks.md WP10 Independent Test) | **The prompts contradict each other on the ATDD red.**<ul><li>WP10 rule 7 commits M1/M7/M8/M11 as `xfail(strict=True)`.</li><li>But WP10 Objectives, T049 step 5, Test Strategy ("expect: all FAIL") and Review Guidance ("every test fails on the missing seam") still expect plain FAILs, and so does tasks.md WP10 "every test is RED".</li><li>WP12 Review Guidance says "WP10's contract tests are green, **without being edited**", while WP12's out-of-map section removes the markers.</li><li>A bare strict xfail also accepts *any* exception (e.g. a typo `NameError`), so "fails for the stated reason" is unenforced.</li><li>`test_dead_symbol_allowlist_contract.py` is not in WP12's `owned_files`.</li></ul> | WP10: add `raises=(ImportError, AttributeError)` to the xfail marker. Reword T049 step 5, Test Strategy and Review Guidance to *"expect every test XFAIL (strict); `--runxfail` shows each failing on `ModuleNotFoundError` / `AttributeError: _evaluate_allowlist`"*. tasks.md WP10 Independent Test: "every test is strict-XFAIL, red under `--runxfail`". WP12 Review Guidance: *"WP10's contract tests PASS after removing only their xfail markers (no other edit)"*. Record the out-of-map file in WP12 frontmatter, or note it in the WP12 `history`. |
| M5 | major | WP10 (T048, M11a) | **M11(a) can trip the loader's own L9.** Popping "the first entry by sorted `(module, name)`" empties its category whenever that category has one entry. `load_allowlist` then raises `AllowlistSchemaError [L9]` (no tombstones), and M11 errors for the wrong reason. WP12 would then have to edit WP10's test. | T048 (a): *"pop the first entry, sorted by `(module, name)`, **whose category has ≥ 2 entries** (or, if you pick a singleton, also delete its now-empty category from `raw['categories']`)."* |
| M6 | major | WP10 (T046, M1) | **M1 is an absence assertion with no same-fixture positive control** (tactic `acceptance-criteria-non-vacuity`, step 3). `offenders == [] and stale == []` also passes if `_evaluate_allowlist` ignores the corpus or the allowlist entirely. M7 and M8 catch a fully inert seam, but not one that ignores bodies. | T046: add a control arm on the **same** `_synthetic_corpus` output: evaluate against an allowlist of `[("pkg.m", "Other")]` and assert `result.offenders == ["pkg.m::Baz"]`. This proves the probe sees the dead symbol when it is not exempted. |
| M7 | major | tasks.md, quickstart, data-model §4, plan (Project Structure) | **The evidence has no durable home.** tasks.md forbids any WP from writing evidence under `kitty-specs/`, and hand-off goes to `move-task --note` ("or a one-line summary if the CLI rejects the length") plus the final report. But:<ul><li>data-model §4 fixes the location as `kitty-specs/.../evidence/IC-NN-*.md`;</li><li>quickstart FR-009 diffs `kitty-specs/.../evidence/dead-symbol-parity/{before,after}.json`, which will never exist (WP10 keeps the file in the scratchpad);</li><li>SC-005's `reviewer_rerun: true` has no file to be set on.</li></ul>FR-011 ("checked item by item at review") therefore depends on ephemeral notes. | Add to tasks.md an explicit **orchestrator closeout step**: *"Materialize every WP's evidence records into `kitty-specs/test-suite-remediation-01M3SSDW/evidence/IC-NN-<slug>.md` and the parity JSONs into `evidence/dead-symbol-parity/` on the planning branch; the independent reviewer sets `reviewer_rerun: true` there (SC-005)."* Update the quickstart FR-009 diff to use the WP10/WP12 recorded digests if the JSONs are not committed. |
| m1 | minor | WP10 (T045) | The `_seam()` snippet line `gate._evaluate_allowlist  # attribute probe` is a bare expression. Ruff **B018** flags it (verified), and NFR-005 forbids `noqa`. | Replace it with `evaluate = gate._evaluate_allowlist` and return `(allowlist_mod, gate, evaluate)`, or use `if not callable(gate._evaluate_allowlist): raise AttributeError("_evaluate_allowlist")`. |
| m2 | minor | WP13 (T061), WP11, WP12 | The WP13 grep gate `rg -n "source_module" src tests scripts` must show hits **only** in `_symbol_key.py` and `test_symbol_key.py`, or WP13 stops. But WP11's loader (T050 step 5 says the loader "refuses `line`, `body_hash` and `source_module`") and WP12's gate docstring are likely to mention the token. WP13 does not own those files. | Add to WP11 rule 5 and WP12 rule 4: *"Do not write the literal token `source_module` in owned files; say 'the retired provenance field'."* Alternatively, scope WP13's grep to code with `rg -n "\bsource_module\s*[=:]"`. |
| m3 | minor | quickstart (Break #20), plan IC-10/IC-11 Proof | The claim "`test_p1_planted_regression.py` goes RED too" on a real-tree plant is wrong: that test drives a **synthetic** corpus (`:180-213`). WP12 T059 already states this correctly. | Quickstart Break #20: *"…the gate goes RED and names `module::name`; `test_p1_planted_regression.py::test_planted_dead_symbol_still_red_by_dead_symbol_gate` stays green on its own synthetic plant (it proves the `_compute_offenders` path is live)."* |
| m4 | minor | WP06 (T024) | The row-3 neutral plant is marked "optional, recommended". data-model §3 makes `neutral_plant` **required** for `delete-with-guard`. | Change "(optional, recommended)" to "(required: data-model §3 `neutral_plant`)". |
| m5 | minor | WP12 (T057) | "`bite_j_gate_annassign_whitespace_zero_false_red` (`:4770`), which you must judge" is an open judgement in an opus WP, with no decision rule. | Decide it in the prompt: *"RETIRE it (its subject, whitespace sensitivity of a persisted hash key, no longer exists; M1 covers body-edit tolerance) unless it asserts AnnAssign **keyability** (`_resolve_final_key(...) is not None`), in which case keep only that assertion."* |
| m6 | minor | WP01 (T005 plant 2) | "Drop the `unknown_target` append at `:1180` **or** `:1198`": `:1180` is the `overrides` branch and `:1198` the `enhances` branch. Dropping one reds only half the named tests. | "Drop **both** appends (`:1180` overrides, `:1198` enhances), each in its own scratch run; the matching `*_unknown_target_errors` test and `test_step4b_unknown_enhances_target_errors` go RED." |
| m7 | minor | WP01 (T003) | The FR-005 regression test asserts an absence (no `same_id_collision`). Its positive control, `test_same_id_collision_uses_reworded_wording`, is a sibling test on the same tactic fixture and not the same fixture. Planted break 3 covers this at proof time only. | Parametrize the regression test with a control arm: the same `_write_tactic(...)` with **no** `drg/fragment.yaml` asserts the advisory **is** present. |
| m8 | minor | WP05 (T021 step 4) | "raise an `ImportError` whose message names **both** names" cannot hold when no map row matches, because there is no canonical name. | "…names both when a rewrite exists; otherwise names the historical module and says 'no relocation row matches'." |
| m9 | minor | WP04 (T020) | Converting `test_events_shapes.py:318-319` (the "older than retrospective 4.1" guard) is outside masked-greens row 17, which lists only `:311`. It is the same class and in an owned file, so it is acceptable, but it is an inventory addition. | Record it in MG-17 evidence as "inventory addition (same class, campsite)". |
| m10 | minor | WP04 (T018) | The budget test re-implements a timing assert. The repo has a house helper, `tests._perf_helpers.assert_timing_budget`, whose call sites the performance-marker guard already vets (`test_timing_coverage_invariant.py:517`). | "Assert through `tests._perf_helpers.assert_timing_budget(run.duration, _SC12_BUDGET_SECONDS, ...)` if its signature fits; otherwise a plain `assert` using only `duration`/`budget` tokens." |
| m11 | minor | WP06 (T025 step 3) | "Tighten the surfacing assertion" is optional scope that can create a new copy pin, the class the mission removes (DIRECTIVE_024). | Keep it, but gate it: "only if the fragment is a named constant or an f-string field in `ordering.py`; never copy prose." |
| m12 | minor | WP09 (T043) | Violation 2's path `specify_cli/core/config.py` is missing `src/`. | `src/specify_cli/core/config.py` (`AGENT_COMMAND_CONFIG` at `:55`). |
| m13 | minor | tasks.md (closeout) | The follow-ups have no owning subtask. The D-14 and RK-5 follow-ups (quarantine-visibility residue; the three open-issue quarantines; tracker `importorskip`; the `inline_meta_read` three-authority count; auto-exempt condition (1); optional F12 re-key), the RK-2 "collected by some lane" gate, and the #5346 claim/assignment (Standing Order 8) are each assigned only to "the orchestrator at closeout". | Add a "Closeout (orchestrator)" checklist to tasks.md that lists each follow-up issue to file plus its issue-matrix row (`issue-verdict --verdict deferred-with-followup`). Also confirm that `issue-verdict` creates a row for a newly filed issue: the mission has no issue matrix yet, and WP01 T005 and WP02 T010 rely on it. |
| m14 | minor | plan IC-10, contract G8 | `test_p1_planted_regression.py:257` should be `:252` (`isinstance(dead_symbols_gate._SYMBOL_ALLOWLIST, frozenset)`). WP12 already has `:252`. | Leave the archived plan text alone; WP12 is correct. |

## 2. Per-check summary

1. **Coverage.** Complete, apart from the proof defects above. No inventory row is silently dropped (§3).
   - FR-010, NFR-002 and SC-006 are correctly withdrawn. FR-010 is parked on WP14 only as a disposition record.
   - C-004 is honoured by exclusion.
2. **Non-vacuity.**
   - Every FIX names a plant. The vacuous or incorrect ones are B1, B2, M2, M3 and M6, plus m4, m6 and m7.
   - Every RETIRE covering guard **exists at HEAD**. All of them were grepped: `test_executor_lane_naming.py:141`, `test_mission_number_truthful_4900.py:655`, `test_tasks_compat_surface.py:432/455/465/484`, `test_recapture_charter_shard_timings.py:311/336/341`, `test_teardown_single_seam_routing.py:81`, `test_diagnostic_codes_documented.py:31/48`, `test_no_absolute_event_timestamp_mixture.py:423`, `test_tracker_egress_guards_3108.py:1150`, `test_census_status.py:36`, `test_pyproject_shape.py:96/113`, and `test_saas_sync_gate_selection_invariance.py::test_no_test_module_sets_the_flag_at_import_time`.
   - The one guard that does not bite its plant is M1 (`:128`).
3. **Anchor accuracy.** 94 anchors were checked, and 90 are exact. The approximate ones:
   - WP08 T037 test def is `:154`, not `:152`;
   - WP04 T018 `_emitter_count` is `:167`, not `~:165`;
   - WP04 T017 `test_venv` is `:1187`, not `:1185`;
   - plan/contract p1 is `:252`, not `:257`.

   All the other WP01–WP15 anchors resolve to the named symbol, including every `test_no_dead_symbols.py` line cited by WP11 and WP12 (`:153`, `:1329-1334`, `:2296`, `:2408`, `:2425`, `:2468`, `:2489`, `:2506`, `:2537`, `:3102`, `:3149`, `:3287`, `:3471`, `:3517`, `:3555`, `:3617-3632`, `:3799`, and the bite tests `:4391`–`:4799`).
4. **Verification commands.**
   - All commands use named files or nodes. No `tests/architectural/` directory run and no `make test-full` appear.
   - The stress file gets `--collect-only` only (the RK-3 ruling).
   - The wheel and venv tests run by node.
   - Every edited test file appears in its WP's run command. WP02's two wheel files appear by node only, which is acceptable because the edit is a decorator and import removal. WP12's out-of-map contract file is included.
5. **Prompt quality.**
   - `## ⚡ Do This First: Load Agent Profile` is the first `##` section in all 15 prompts.
   - There is no "TBD", "as appropriate" or "verify somehow".
   - Open judgements remain: m5, the optional plant in m4, and the optional tightening in m11.
   - Each Definition of Done is objective, apart from the internal contradictions in M4.
6. **Scope and locality.**
   - The only product-source edit is `pack_validator.py` (WP01, C-005).
   - The out-of-map edits are sanctioned: WP03's `ruff.toml` and the `test_issue_4891` docstring, which the relocation forces, and WP12's edit to WP10's file, which is dependency-ordered (see M4).
   - The small campsites are in m9 and m11. No edit reaches outside the spec's FRs.

## 3. Coverage matrix (inventory row → WP / T-id)

### 3.1 Masked greens (`research/masked-greens.md`)

| Row | Disposition | WP / T |
|---|---|---|
| 1 (3 pack-validator probe tests) | RUN | WP01 T001, T005 |
| 2 (2 intent-suppression tests + product defect) | RUN + FIX | WP01 T003, T004, T005 |
| 3 (4 quickstart steps) | RUN | WP01 T002, T005 |
| 4 (#3113 strict xfails + landmine guard) | RE-POINT | WP02 T006 |
| 5 (5 quarantined + 18 unlaned tests) | DE-QUARANTINE + RELOCATE | WP03 T011–T014 |
| 6 (#932 `_has_events_5` ×3 files, 6 sites + unreachable branch) | RETIRE + new FIX test | WP02 T007, T008 (guard: see M1) |
| 7 (EXP#828 skipifs + helper) | RETIRE | WP02 T009 |
| 8 (`test_charter_sole_door…` "828") | NO-OP | WP02 T010 step 4 |
| 9 (sync gate premise #3213) | KEEP + re-cite | WP02 T010 |
| 10 (`build_artifacts` skips) | CONVERT | WP04 T015 |
| 11 (`installed_wheel_venv` skips) | CONVERT | WP04 T015 |
| 12 (`_build_wheel_fallback`) | DELETE | WP04 T016 |
| 13 (11 version-detection sites) | CONVERT | WP04 T017 |
| 14 (stress SC-12 budget skip) | SPLIT → `timing`+`stress` (RK-3 b) | WP04 T018 |
| 15 (home-isolation skip) | CONVERT → assert | WP04 T019 (plant: see M3) |
| 16 (10 contract round-trips) | CONVERT (relocation map) | WP05 T021–T023 |
| 17 (`spec_kitty_events` ImportError skip) | CONVERT | WP04 T020 (+ `:318` campsite, m9) |
| 18 (`jsonschema` importorskip ×3) | CONVERT | WP04 T020 |
| Platform/tool-guard list | KEEP (exemptions) | WP04 T020 step 4 (exemption diff check) |
| #3595 stale citation (chokepoint) | NFR-004 campsite | WP04 T015 step 5 |
| Tracker `importorskip` ×2; 3 open-issue quarantines; quarantine-visibility residue | out of scope (C-004 / RK-5) | orchestrator closeout (m13) |

### 3.2 Pins (`research/pin-inventory.md` §2.1, §2.3, §2.4)

| Row | Disposition | WP / T |
|---|---|---|
| #5346-1 / F2 `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` (`:618`) | convert (floor) | WP14 T065 |
| #5346-2 / F1 `len(SYMBOL_TO_MODULE) == 196` (`:635`) | delete-with-guard + relational floor | WP07 T028 |
| #5346-3 allocator f-string (`:383`, `:396-397`) | delete-with-guard | WP06 T024 |
| #5346-4 unreachable-primary name (`:244`) | convert (rename + re-scope) | WP06 T025 |
| #5346-5 `:481` / `:490` / `:494` | convert / delete-with-guard / convert | WP07 T029, T030 |
| #5346-6 private-signature pins (`:309`…`:435`) | convert | WP06 T026 (plant: see M2) |
| #5346-7 literal-scan trap (`:107`) | convert (behavioural) | WP07 T031 |
| F3 `materialize_calls == 29` (+ `:510` campsite) | convert (floor) | WP08 T036 |
| F4 bulk-edit counts + file sets | convert (shape) | WP09 T040 |
| F5 glossary `== 103` ×2 | convert (relational) + rename | WP09 T041 |
| F6 `expected_sites` parametrize | convert (floor) | WP08 T037 |
| F7 census `== 74` / `== 800` | delete-with-guard + floor | WP09 T042 |
| F8 `test_member_count == 16` | delete-with-guard | WP08 T038 |
| F9 prose denominator | delete-with-guard | WP08 T033 |
| F10 agent registries `== 13` ×2 | convert (cross-registry set equality) | WP09 T043 |
| F11 `== *_FLOOR` ×3 + `== 9` | convert (partition) | WP08 T034 (**see B2**) |
| F12a `EXPECTED_ENCLOSING_COUNT` | delete-with-guard | WP08 T035 |
| F12b `EXPECTED_CALL_EXPRESSION_COUNT` | keep-contract (recorded) | WP08 T035 |
| Kept ratchets: destructive-op `:387`, inert-slot `:231`, `category_7…:158`, `:321/:50/:60/:72/:75/:356` | keep-ratchet + FR-008 history check | WP14 T069 step 2 |
| `CHARTER_PATH_LITERAL_FLOOR`, `INLINE_META_READ_FLOOR`/`:971`, `_FR014_DEFERRED_CENSUS_ALLOWLISTS`, the `>=`/`<=` floors | keep-ratchet (recorded) | WP14 T069 step 3 |
| LOCAL TEST VALUE rows | not-a-pin (recorded) | WP14 T069 step 3 |
| `test_timing_coverage_invariant.py:386 == 62` | keep-contract (recorded) | WP14 T069 step 3 |
| `test_symbol_key.py:644 len(index) == 400` | keep (untouched) | WP13 T063 |
| Resolved: `ROUTED_LOAD_META_FLOOR`, DRG counts, destructive-op line re-pins | resolved (commit recorded) | WP14 T069 step 3 |

### 3.3 Dead-symbol contract (`contracts/dead-symbol-allowlist.md`)

| Item | WP / T |
|---|---|
| M1, M7, M8, M11 (ATDD) | WP10 T046, T047, T048 (see B1, M4–M6); turned green by WP12 (marker removal) |
| M2, M3, M4, M5, M6, M9, M10, M13 | WP12 T057 |
| M12 (schema battery) | WP11 T052 (moved to the loader test file; the rationale is recorded) |
| L1–L10 + category-id pattern | WP11 T050 |
| G1, G5, G7, G8 | WP12 T055 |
| G2, G3 (INVALID→GONE→REVIVED→SUPERSEDED→MOOT + move hint) | WP12 T055, T056 |
| G4 (widened unchanged) | WP12 T055 step 6 |
| G6 (deletions) | WP12 T056 step 3 |
| §2.1 corpus floor | WP12 T056 step 4 + M13 |
| §2.2 growth cap (+ RK-6 widened leaf) | WP14 T066, T067 |
| §4 parity before → converter → after | WP10 T049, WP11 T051/T053, WP12 T054/T060 |
| Retire the refresh helper + 17 tests | WP12 T059 |
| Retire `SymbolKey.source_module` + G1–G6 tests; docstrings; README | WP13 T061–T064 |
| ADR + ci-gate-mechanics + indexes | WP15 T070–T073 |

### 3.4 Requirements, constraints, success criteria and RK rulings

| Item | WP / T |
|---|---|
| FR-001 / SC-001 | WP01 T001, T002, T005 |
| FR-002 / SC-002 | WP02 T006–T010; WP03 T012, T014 (EXP#171); WP04 T015 (#3595) |
| FR-003 | WP03 T011–T014 |
| FR-004 | WP04 T015–T020; WP05 T021–T023 |
| FR-005 | WP01 T003, T004 (fix); WP02 T006 (honest red); WP05 T022 (contingency) |
| FR-006 / FR-007 / SC-004 | WP06, WP07, WP08, WP09, WP14 (§3.2) |
| FR-008 | WP14 T069 (history check); every conversion WP ("no ratchet touched") |
| FR-009 / SC-003 | WP10–WP15 (§3.3; **see B1**) |
| FR-011 / SC-005 | every WP's plant subtask (T005, T010, T014, T020, T023, T027, T032, T039, T044, T049, T053, T060, T064, T069, T073); durability, **see M7** |
| NFR-001 (masked-green files, RK-1) | WP01 T005, WP02 T007, WP03 T014, WP04 T020, WP05 T023 |
| NFR-003 | neutral plants in WP06–WP09, WP10 M1, WP12 T060, WP14 T065 |
| NFR-004 | rule 5 in WP01–WP09; WP10's xfail markers cite open #5346 |
| NFR-005 | rule 6 (or equivalent) in every WP |
| C-001 | every WP's rule 1 + Test Strategy |
| C-002 | WP02, WP06, WP07, WP08, WP09, WP12 T059, WP13 T061 |
| C-003 | WP08, WP11, WP12, WP14 |
| C-005 | WP01 T004 (product-only commit) |
| C-006 | WP05, WP09 T040, WP03 (ADR left), WP15 |
| C-007 | every WP's rule 2 |
| C-008 | WP14, WP15 |
| RK-1 | WP06 T024, WP07, WP08, WP13 T064 notes |
| RK-2 | WP03 T013 |
| RK-3 (b) | WP04 T018 |
| RK-4 | WP11 T051 step 2 |
| RK-5 | WP03 "Out of scope" + orchestrator closeout (m13) |
| RK-6 | WP14 T067 |
