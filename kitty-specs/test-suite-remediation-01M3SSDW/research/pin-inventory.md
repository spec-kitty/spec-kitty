# Pin inventory: #5346 re-verification, the FR-007 exact-count class, and the FR-010 census gate

- **Mission:** `test-suite-remediation-01M3SSDW`. Addresses #5346, under parent #5353.
- **Lens:** researcher-robbie, the planning-research lens for pin honesty. This lens is read-only and makes no decisions; the planner owns the WP cut.
- **Tree:** branch `issue-5353-test-suite-remediation`, HEAD `732f445a1e`. That commit is based on `upstream/main` `74373ec95a`. PR #5407 (`0ca344c69e`) is an ancestor of HEAD.
- **Spec anchors:**
  - FR-006, FR-007, FR-008, FR-010 and FR-011;
  - NFR-002 and NFR-003;
  - C-002 and C-003;
  - Edge Cases 4 and 6.

## 0. Summary for the planner

1. **None of the #5346 pins is resolved yet.** All 7 rows still hold an exact pin or a copy pin at HEAD. PR #5407 touched 22 other `tests/consolidation` files and none of the four #5346 consolidation files, so it resolved nothing here. Three pins have drifted further since the issue was filed:
   - `_REQUIRED_TOP_LEVEL_KEYS` went 14→15 (`639aa2febc`, 2026-09-30);
   - `SYMBOL_TO_MODULE` went 186→190→196 (`b3084dacb4`, `75e678bb1e`);
   - git bootstrap parity went 2→4→3 on the same day.
2. **The compat-surface "cardinality-is-contract" marker is residue.** It is not a contract. The marker was the escape hatch of the retired golden-count gate:
   - #4315 (`a428532719`, 2026-09-14) swept all 381 markers, this one included;
   - `e455ce26c1` (2026-09-18) re-added it by hand four days later.
   - The counted map holds private `_mt_*`/`_ms_*` patch targets, so its size is no API. The file already enforces the real invariant three ways: superset, native-origin and disjointness.
   - The count has been re-pinned **18 times since 2026-08-01**. That is the single worst pin in the tree.
3. **The FR-007 class needs a split.** Some of the examples the spec names are designed ratchets, not pins:
   - The destructive-op baseline (`_baselines.yaml:387`, 55→56→61) and the inert-slot ceiling (`_baselines.yaml:231`, 37→38→36) moved **only with real allowlist or debt rows**. That is `frozen-baseline-shrink-only-ratchet` working as designed, so FR-008 is already met.
   - Converting either one to a floor would *loosen* a shrink-only ratchet, which C-003 forbids. The recommended disposition is **KEEP (RATCHET)**, recorded, with no conversion.
   - `ROUTED_LOAD_META_FLOOR` is **already resolved**: #4315 deleted it outright in `dd82bd340b` (2026-09-14), after 17 re-pins.
4. **The live-structure pins to convert number 13 across 11 files.** Each was re-pinned at least once since August (§2.3). Beyond the #5346 rows, the named examples are:
   - the gated-module count;
   - the bulk-edit census, 19→20 (its GOVERNANCE count moved 188→…→101);
   - git bootstrap parity, 2→4→3;
   - the glossary anchor count, 104→103.

   Found by the scan:
   - `materialize_calls == 29` (7 re-pins);
   - the convergence census counts (5+5);
   - `MissionReviewDiagnostic == 16` (3);
   - the agent-registry counts;
   - the timestamp-mixture denominator;
   - the remediation-effectiveness `== *_FLOOR` trio.
5. **FR-010 is a re-introduction of a retired gate. Design it against that gate's recorded failure.**
   - `test_golden_count_ban.py` (#2076, advisory from #3458, deleted by #4315) had "0 real catches". Of its 15 baseline commits, 13 were whole-tree re-freezes forced by unrelated additions, and it charged a toll of 381 escape annotations.
   - The proposal in §3 differs on every one of those axes:
     - a narrow rule, 38 live hits instead of about 500;
     - per-site content-keyed entries instead of per-directory counts;
     - no inline escape marker.
   - A prototype measured **1.5 s** over the full `tests/` tree, against the NFR-002 budget of under 5 s.
6. **Ordering constraint.** Registering the census gate in `_baselines.yaml` adds a 16th `_SIZE_RATCHETS` section. If the `len(_REQUIRED_TOP_LEVEL_KEYS) == 15` pin is still live, the new gate forces its own re-pin. Convert that pin in the same WP as the gate, or before it.

---

## 1. Method (reproducible)

All commands ran from the repository root at HEAD `732f445a1e`. The scratch scripts live in the session scratchpad, which is ephemeral. Their logic is restated below, and the two load-bearing scripts are in Appendix A and Appendix B.

### 1.1 #5346 re-verification

- Each issue row was re-located with `grep -n`: the anchored symbol first, then the assertion line. A test's `def` line and its `assert` line are recorded separately, because the issue mixed the two.
- #5407's reach was checked with `gh pr view 5407 --json files,mergeCommit` and `git merge-base --is-ancestor 0ca344c69e HEAD`.
- Pin history came from:

  ```bash
  git log --since=2026-08-01 -G '<pinned line regex>' -p -- <file>
  ```

- Current values were confirmed by running the named files only:

  ```bash
  PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
    tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py \
    tests/architectural/test_ratchet_baselines.py tests/docs/test_glossary_linker.py \
    tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py \
    tests/git/test_guard_capability_regression.py tests/runtime/test_bridge_decision_builder.py \
    tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
  # 519 passed in 4.99s -- every pin below holds at HEAD
  ```

### 1.2 Static side: AST scan of `tests/**/*.py`

- **Script.** `scan_static.py` parses all 3,624 files.
- **Assertions matched:**
  - `assert <A> == <B>` with a single `Eq`, including a `Compare` nested inside `and`/`not` chains of the assert;
  - `self.assertEqual(A, B)`.
- **Hit kinds.** A hit is recorded when one of these holds:
  - `len(<expr>) == <int literal>`, in either order (`len==int`);
  - `len(<expr>) == NAME`, where `NAME` is a module-level int literal (`len==CONST`);
  - either side is a name ending in `_FLOOR`, `_CEILING`, `_COUNT` or `_BASELINE` (`x==COUNTCONST`).
- **Binding of the counted expression's root name.** The root is reached by unwrapping `list/set/frozenset/tuple/sorted(...)`, `.keys/.values/.items()`, attribute chains and subscripts. It is then classified:
  - `LOCAL`: bound in the enclosing function or its outer functions (parameter, assign, `for`, `with`, comprehension);
  - `MODULE`: bound by a module-level assign or `def`/`class` in the test file;
  - `IMPORTED`: bound by a module-level import, or by an import inside the function;
  - `CALL`: the counted expression is a call whose callee root is module-level or imported;
  - `UNRESOLVED`: anything else.
- **Result: 2,484 hits.**

  | kind / binding | hits |
  |---|---:|
  | `len==int` LOCAL | 2,333 |
  | `len==int` CALL | 43 |
  | `len==int` UNRESOLVED | 37 |
  | `len==int` IMPORTED | 24 |
  | `len==int` MODULE | 22 |
  | `len==CONST` (LOCAL 10, MODULE 2, CALL 1) | 13 |
  | `x==COUNTCONST` | 12 |

- **Refinement.** `refine_local.py` follows a local up to 3 assignment hops. If every free name resolves to module scope, imports or builtins, the hit becomes `LOCAL-LIVE`.
  - This produced 392 `LOCAL-LIVE` and 34 `CALL-LIVE` hits.
  - They are **dominated by behavioural counts**: events emitted, rows written, hash lengths.
  - The heuristic cannot tell "count of the live corpus" from "count of what the function under test returned", which is exactly the confusion that sank the retired golden-count gate.
  - Conclusion: a static rule is only trustworthy for the *direct* module-level or imported class (§3). Counts that reach live structure through a local must come from the history side.

### 1.3 Historical side: N→M integer re-pins since 2026-08-01

`scan_history.py` (Appendix A) runs two logs:

```bash
git log --since=2026-08-01 --no-merges -M -p -U0 --format='@@COMMIT %h %ad %s' --date=short \
  -G 'len\(.*\) *== *-?[0-9]|[0-9] *== *len\(|assertEqual\(len\(|(_FLOOR|_CEILING|_COUNT|_BASELINE|_CAP|_MAX|_MIN)\b.*[0-9]|(floor|ceiling|baseline|count|cap)[A-Za-z_]* *[:=] *[0-9]' \
  -- tests/
git log --since=2026-08-01 --no-merges -M -p -U0 ... -- ':(glob)tests/**/*baseline*.yaml' \
  ':(glob)tests/**/*baseline*.json' ':(glob)tests/**/*census*.yaml' ':(glob)tests/**/*census*.json'
```

- **Re-pin event.** Within one commit and one file, a removed line and an added line that are identical once every integer literal is replaced with `#`, but whose integers differ.
- **Result.** 197 raw events, deduplicated to 75 distinct sites.
- **Mapping to HEAD.** `intersect.py` looks up each site's normalized line in the same file at HEAD, or reports it as GONE.
- **Cross-checks:**
  - commit subjects: `git log --since=2026-08-01 -i --grep 're-pin\|bump.*count' -- tests/`, filtered to `N -> M`;
  - the direction of every move (up or down), used to separate ratchet burn-down from pin drift.
- **Known blind spots of the miner.** Each is covered by hand below.
  - **Parametrize-table counts** such as `("…/mission_finalize.py", "_bootstrap_canonical_state_via_mission", 3)`. The line holds no `len(`/`==`/`_FLOOR`. Git bootstrap parity was found through its commit subject (`ed943ebb1f`).
  - **Set-literal pins** such as the bulk-edit `gov_files == {...}` file sets. These are membership pins, not integer pins.
  - **Multi-line assertions** whose integer sits on a different physical line from `len(`.

### 1.4 Intersection

The FR-007 class is:

(re-pinned since 2026-08-01) ∩ (still present at HEAD) ∩ (counts live structure: a production collection, the shipped corpus, or a test-file collection whose membership another assertion forces to track production).

Each member is then classified:

- **LIVE-STRUCTURE PIN:** convert.
- **RATCHET BASELINE:** keep, because it moves only with debt.
- **GENUINE CONTRACT CARDINALITY:** keep, with the reason.
- **LOCAL TEST VALUE:** not a pin.

---

## 2. Tables

### 2.1 #5346 inventory, re-verified at HEAD `732f445a1e`

Status legend:

- **STILL-PIN:** unchanged in kind; the value may have drifted.
- **RESOLVED:** already converted, with its commit.

Nothing is RESOLVED.

| # | #5346 row (issue anchor) → HEAD file:line | Current value | Status | Proposed invariant form | Planted break (proves the new form reds) |
|---|---|---|---|---|---|
| 1 | `tests/architectural/test_ratchet_baselines.py:603` → **`:618`** (`test_size_ratchet_table_meets_floor`) | `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 15` (the issue says 14; `639aa2febc` moved it 14→15 on 09-30) | STILL-PIN: 3 re-pins since Aug (`f6c137cc1d` 12→13, `ed03553692` 13→14, `639aa2febc` 14→15) | **RETIRE the line and its comment.** `_REQUIRED_TOP_LEVEL_KEYS` is *derived* from `_SIZE_RATCHETS` (`:371`), so the count only restates the table. Covering guards already in the file: (a) `len(_SIZE_RATCHETS) >= 19` plus the duplicate `(section, leaf)` check (`:611-613`, the floor and duplicate halves); (b) `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` (the YAML↔rows bijection, i.e. the stale half both ways); (c) `test_baseline_file_exists_with_required_keys` (missing sections). A floor `>= 15` is an acceptable alternative but adds nothing to (a). | **Neutral:** add a new `_SIZE_RATCHETS` row plus its YAML leaf; the retired form stays green, while today `:618` reds. **Violation 1:** duplicate a row; (a)'s duplicate check reds. **Violation 2:** delete a row whose YAML leaf remains; (b) reds (unenforced leaf). **Violation 3:** delete a YAML section; (c) reds. |
| 2 | `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py:476` → def **`:492`** `test_guard_covers_full_167_symbol_surface`, assert **`:635`** | `assert len(SYMBOL_TO_MODULE) == 196` (the issue says 186) | STILL-PIN: **18 re-pins since Aug** (159→160→…→196; 17 up, 1 down). The name says 167, the docstring holds a ~140-line changelog, and the TODO at `:626-632` doubts its ROI. | **RETIRE the count test** and its changelog docstring. Coverage survives in the same file: `test_guard_keyset_is_superset_of_all_six_seams_native_defs` (`:465`, the *missing* check, with no symbol dropped from the map); `test_guard_symbol_is_genuinely_native_to_its_seam` (`:455`, the *stale* check, with no entry that is no longer native to its seam); `test_no_required_symbol_duplicated_in_survey` (`:484`, the *duplicate* check); and the `test_tasks_binding_is_seam_object` identity battery (`:432`). Optional non-vacuity floor, relational so never re-pinned: `assert all(_SEAM_GROUPS.values())`, one or more symbols per seam. On the "cardinality-is-contract" claim, see §2.1a. | **Neutral:** add `_mt_new_helper` to `tasks_move_task.py`, register it in `_TASKS_MOVE_TASK` and re-export it in `tasks.py`. The retired form stays green; today `:635` reds. **Violations:** (i) keep the def but drop the tuple entry, and `:465` reds; (ii) register a name the seam no longer defines, and `:455` reds; (iii) list one symbol in two seam tuples, and the `SYMBOL_TO_MODULE` construction raises or `:484` reds; (iv) drop the `tasks.py` re-export, and the `:432` identity test reds. |
| 3 | `tests/consolidation/test_mid8_embedded_preflight.py:372`, `:387` (issue anchors are the `def` lines) → asserts **`:383`** and **`:396-397`** | `teardown_path == tmp_path/".worktrees"/f"{slug}-{lane_id}"` (hand-built `allocator_path`); `:397` `teardown_path.name == "057-foo-bar-lane-a"` | STILL-PIN (not touched by #5407). The class docstring also misnames the seam: the real teardown resolves through `executor._created_lane_worktree` → `worktree_allocator.predict_lane_worktree`, not through a bare `branch_naming.worktree_path`. | **RETIRE both tests** (the class `TestWorktreeTeardownSeamRouting`). They re-derive the naming grammar by f-string. Covering guards: `tests/consolidation/test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output` (`:141`), which builds the mission with the **real** `allocate_lane_worktree` (via `tests/consolidation/_divergent_shapes.py`) and compares against the path the teardown uses; and `tests/lanes/test_branch_naming_seam.py`, the grammar table including legacy slugs. If the planner prefers FIX, rebuild the two cases with `shape_backfilled_legacy(...)`/`shape_mismatched_mid8(...)` and assert against `mission.lanes["lane-a"][0]`. | **Violation:** make `_created_lane_worktree` compose its own path (e.g. insert the mid8), so it diverges from the allocator. The covering guard `:141` reds, while the retired f-string tests stay green, which shows they guard nothing that the covering guard misses. **Neutral:** a coherent grammar change in `branch_naming.worktree_path` reds today's `:383` but not the covering guard. |
| 4 | `tests/consolidation/test_issue_4474_topology_aware_bake.py:188` (the `def` of `test_genuinely_unreachable_primary_surfaces_instead_of_silent_fail_open`) → assert **`:244`** | `assert result == 1, "the computed mission_number must reach the executor's target-tree write…"`, flipped from `result is None` in `2f8a558e6c` (09-28) | STILL-PIN (a name/contract mismatch) | **FIX (rename and re-scope).** Rename the test to the seam's actual contract, e.g. `test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it`: the seam returns the decided number, leaves `mission_number_baked` False, and prints a merge-summary line. Name the covering guard for the refusal half, which now lives in the executor: `tests/consolidation/test_mission_number_truthful_4900.py::test_absent_target_meta_refuses_instead_of_fabricating` (`:655`). No value change is needed. The fix is the name and the docstring, which now describe a contract this test no longer exercises. | **Violation A:** make the seam return `None` again on the unreachable path; the renamed test reds at `:244`. **Violation B:** make the executor write a `null` number silently when the target `meta.json` is absent; `test_absent_target_meta_refuses_instead_of_fabricating` reds. |
| 5 | `tests/ci/test_recapture_charter_shard_timings.py:479/:489/:493` (`def` lines) → asserts **`:481`**, **`:490`**, **`:494`** | `body == (<verbatim literal>)`; `COMMIT_MESSAGE == "chore(ci): automated charter shard-timings recapture"`; `MODULE == "charter"` | STILL-PIN (pure copy pins) | **`:481` FIX:** assert what the template *drives*. The rendered body must contain the substituted `before`/`after`/`run_url` values and name `.github/ci-shard-timings.json`, with no `{`/`}` left unformatted. **`:490` RETIRE:** covering guard `test_push_and_open_pr_runs_git_and_gh_with_expected_arguments` (`:336`, `:341`), where the one message is used for both the commit and the PR title. **`:494` FIX:** in a `run_capture_phase` test, record the `argv` passed to the (already stubbed) `capture_shard_timings.main` and assert `argv[:2] == ["--module", "charter"]`. That is the FR-009 scope lock through the real seam; today the stub `lambda argv: 0` ignores argv. `:199` (`_read_charter_length` reads the `charter` key) stays. | **`:481`:** drop `{after}` from `PR_BODY_TEMPLATE`, and the new form reds. **`:490`:** make `_push_and_open_pr` pass a different string to `git commit` than to `--title`, and `:336`/`:341` red. **`:494`:** make `run_capture_phase` pass `["--module", "specify_cli", "--write"]`, and the new argv assertion reds; renaming the constant alone stays green. |
| 6 | `tests/consolidation/test_behind_head_recovery_coverage.py:313`, `:366` → **`:309`**, **`:332`**, **`:362`**, plus the same pattern at **`:384`**, **`:416`**, **`:435`** | `mock_report.assert_called_once_with(exc, tmp_path, mission_branch="kitty/mission-m", base_sha=None)` (5 sites); `mock_recover.assert_called_once_with(exc, tmp_path, "01ID", mission_branch=…)` (`:309`) | STILL-PIN: pins the full signature of the private siblings `_report_pre_mutation_refusal`/`_recover_behind_head_primary_on_resume` | **FIX.** In the sibling tests (`:309`, `:332`, `:384`, `:416`, `:435`), assert only what each test is about: `assert_called_once()` plus `call_args.args[0] is exc`. Keep **one** explicit threading assertion in `test_preflight_with_recovery_threads_persisted_pre_mutation_target_sha_as_base_sha` (`:362`) as `mock_report.call_args.kwargs["base_sha"] == persisted_sha`; that is the #4933 contract. A stronger alternative: unmock `_report_pre_mutation_refusal` and assert through `capsys` on the printed remedy, since `base_sha` gates the reset-to-HEAD guidance. | **Neutral:** add a new keyword-only parameter with a default to `_report_pre_mutation_refusal`; the siblings stay green, while today all 5 red. **Violation:** at the call site, pass `base_sha=None` instead of the loaded `pre_mutation_target_sha`; `:362` reds. |
| 7 | `tests/specify_cli/coordination/test_teardown_single_seam_routing.py:97` → **`:107`** (`test_former_production_sites_route_through_the_seam`) | `"teardown_coordination_topology" in text` over `consolidate.py` and `mission_type.py` | STILL-PIN (Literal-Scan Trap) | **FIX to a behavioural seam test.** Both call sites import the seam lazily inside the function (`consolidate.py:365`, `mission_type.py:1140`), so `monkeypatch.setattr("specify_cli.coordination.teardown.teardown_coordination_topology", recorder)` intercepts them. Drive `consolidate._teardown_coordination_for_abort(...)` and `mission_type._teardown_coordination_worktree(...)` and assert that the recorder was called once with the mission identity. `tests/specify_cli/cli/commands/test_mission_close_teardown_message.py:24-32` already uses this exact pattern for `mission_type`. Drop the per-file absence assertion at `:111`: `test_zero_production_teardown_calls_outside_the_seam` (`:81`) already covers it globally. Do not RETIRE outright: I found no behavioural test that reds if `--abort` stops calling the seam, so C-002 blocks a plain delete. | **Violation:** replace the seam call in `_teardown_coordination_for_abort` with an inline `CoordinationWorkspace.teardown(...)`. The recorder test reds, and `:81` reds too. **Neutral:** rename `consolidate.py`, or move the function to another module; the behavioural test stays green, while today's literal scan reds. |

#### 2.1a Is `SYMBOL_TO_MODULE`'s cardinality a contract?

**No. It is a pin.** The evidence:

1. **What is counted.** The collection is the *test's own literal registry* of private seam helpers (`_mt_*`, `_ms_*`, `_st_*`, `_mr_*`, …) that `tasks.py` re-exports so that historical `@patch("…agent.tasks.<name>")` targets keep resolving. These are private patch targets, not a published API. No consumer depends on there being exactly 196 of them.
2. **Where the invariant lives.** The file already enforces the contract by *membership*:
   - identity re-export (`:432`);
   - native origin (`:455`);
   - superset over the live seam defs (`:465`);
   - disjointness (`:484`).

   Every legitimate addition is already forced by `:465`, so the count is a second entry for a fact the superset test just enforced. That is why it moved 18 times.
3. **Where the marker comes from.** The `# golden-count: cardinality-is-contract` marker is the escape hatch (`ESCAPE_HATCH_MARKER`) of the retired `test_golden_count_ban.py`. #4315 (`a428532719`) deleted that gate and tokenize-swept all 381 markers, including this one: the diff shows `-  == 179  # golden-count: …` becoming `+ == 179`. `e455ce26c1` (09-18) re-added it with the next re-pin.
4. **What the file's own authors say.** The TODO at `:626-632` flags the per-symbol "three-part edit … AND bump this hardcoded cardinality" as low-ROI.

**Recommendation.** Retire the count and the stale-numbered test name, and keep the four membership tests. The operator's wider doubt about the whole guard is out of scope. The identity and superset tests do guard live `@patch` targets.

### 2.2 The recurring exact-count class: evidence, both sides

- **Static side.** The rule-1 and rule-2 census hits of §3 (38 sites) are listed per file in §3.4. The wider `LOCAL`/`LOCAL-LIVE` population (§1.2) is not a trustworthy pin signal on its own.
- **Historical side.** 75 distinct re-pinned sites since 2026-08-01, compressed below to those still present at HEAD and relevant to FR-007. Sites that no longer exist are listed in §2.4.

### 2.3 FR-007 class table

Only sites re-pinned at least once since 2026-08-01 appear here. Commit lists are abbreviated; `intersect.json` held the full lists.

| # | HEAD file:line | Counts | Re-pins since Aug (commits) | Classification | Proposed form (surviving coverage) | Planted break |
|---|---|---|---|---|---|---|
| F1 | `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py:635` | test-literal map forced to track live seam defs | **18** (`0727ea0dd0` … `75e678bb1e`) | LIVE-STRUCTURE PIN (#5346-2) | see §2.1 row 2 | see §2.1 row 2 |
| F2 | `tests/architectural/test_ratchet_baselines.py:618` (**"gated-module count"**) | sections derived from `_SIZE_RATCHETS` | 3 (`f6c137cc1d`, `ed03553692`, `639aa2febc`) | LIVE-STRUCTURE PIN (#5346-1) | see §2.1 row 1 | see §2.1 row 1 |
| F3 | `tests/runtime/test_bridge_decision_builder.py:498` (`test_runtime_bridge_materializes_every_former_decision_site`) | `_materialize_decision(...)` call sites in the live `runtime_bridge` source (`inspect.getsource`) | **7** (`5773a637a9` 21→22, `6bc9f077ef` 22→25, `9d83d8bf4f`, `94fd1071a3`, `2864622117`, `e022462e74`, `8a64f60535` 28→29) | LIVE-STRUCTURE PIN | Floor `>= 1` for non-vacuity. The docstring's invariant ("zero open-coded `Decision`") is already `test_runtime_bridge_has_zero_raw_decision_constructions` (`:442`), an AST absence scan. Delete the per-site changelog docstring. Sibling `:510` `len(bare_decision_calls) == 3` in `cores`: not re-pinned in the window, so freeze it in the census or convert it as campsite work to "every `Decision(` call lies inside one of the three named helpers" (a qualname set). | **Neutral:** add a new `_materialize_decision` site; green, while today's form reds. **Violation:** add `Decision(...)` directly in `runtime_bridge.py`; `:442` reds. |
| F4 | `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py:520`, `:521` (**"bulk-edit census 19→20"**), plus the file-set pins `:525-575` | GOVERNANCE/RAW_MATERIAL entries of `inline_reference_inventory.collect()` over the **shipped doctrine corpus** | `len(gov)` 6 (224→92, …, 100→101); `len(raw)` 3 (`849477ebab` 14→21, `2b649bffcf` 21→19, `ab4013698d` 19→20); the file sets moved alongside (not integer re-pins) | LIVE-STRUCTURE PIN. The docstring calls SC-011 a "cardinality contract", but SC-011 is an archived mission's measurement of the corpus at authoring time, not a live contract (C-006: do not edit that spec; correct the claim here). | Replace the counts and file sets with *shape* invariants: `gov` and `raw` are non-empty (floor); every GOVERNANCE path is `agent_profiles/*.agent.yaml`; every RAW_MATERIAL path is under `styleguides/` or `toolguides/`; plus the per-triple contract already in `test_every_real_governance_field_is_expressible_as_field_path_exception`. | **Neutral:** add a profile with `directive-references`; green, while today's form reds. **Violation:** make the inventory classify a styleguide path reference as GOVERNANCE; the shape check reds. |
| F5 | `tests/docs/test_glossary_linker.py:69`, `:101` (**"glossary anchor count"**); the test name at `:62` still says `_104_` | terms in the shipped `GLOSSARY_SEED` | 1 commit, 2 sites (`b44992038e` 104→103) | LIVE-STRUCTURE PIN | Relational: `len(assign_anchor_ids(parse_glossary_seed(SEED))) == len(parse_glossary_seed(SEED))` (no term dropped) plus the existing uniqueness check (`:71`); for `load_link_terms`, one `LinkTerm` per seed term that has a surface. Rename the test to drop the `104`. Same pattern as `2e40057da1` ("de-hardcode DRG cardinality/inventory pins to filesystem-derived invariants", #3234). | **Neutral:** add a glossary term; green. **Violation:** make `assign_anchor_ids` skip a colliding term; the relational check reds. |
| F6 | `tests/git/test_guard_capability_regression.py:145` (parametrize row) plus the assertion at `:167` (**"git bootstrap parity 2→4"**) | `_bootstrap_canonical_state_via_mission` call sites in the live `mission_finalize.py` | 2 in one day (`ed943ebb1f` 2→4, then #5100 4→3); missed by the integer miner (table row) | LIVE-STRUCTURE PIN | `len(capabilities) >= 1` (non-vacuity per module/callee). The contract is the per-site loop "every site is REFUSED on a protected ref" (`:175-180`), which already covers every site. Drop `expected_sites` from all 5 parametrize rows. | **Neutral:** add a STANDARD call site; green, while today's form reds. **Violation:** add a call site passing `capability=GuardCapability.<protected-flow member>`; the loop reds. **Vacuity:** remove all sites; the floor reds. |
| F7 | `tests/unit/convergence/test_census_status.py:31`, `:32` | clusters and commits in the committed `.kittify/convergence-map.json` | 5 + 5 (`4b9f767d52` … `7bda4c4fa7`; 68→74 clusters, 596→800 commits; all up) | LIVE-STRUCTURE PIN (pins the size of a growing data artefact) | Retire the two absolute counts. Covering guards: `test_seed_map_census_counts_match_commit_lists` (`:36`, the per-cluster count equals the commit list, which is the real consistency contract) and the `PENDING` check at `:33`. Add a floor `len(clusters) >= 1`. | **Neutral:** append a cluster; green. **Violation:** a cluster whose `census_commit_count` disagrees with its list; `:36` reds. |
| F8 | `tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py:75` (`test_member_count`) | members of `MissionReviewDiagnostic` (a production `StrEnum`) | 3 (`ff25cc6f6a` 13→14, `43af053e38` 14→15, `895ce71670` 15→16) | LIVE-STRUCTURE PIN | RETIRE. Covering guards in the same class: `test_all_diagnostic_members_documented` (`:31`) and `test_section_count_matches_member_count` (`:48`). The contract is that every code is documented, not that there are 16. | **Violation:** add an enum member without an `ERROR_CODES.md` section; `:31` reds. **Neutral:** add a member with its section; green. |
| F9 | `tests/architectural/test_no_absolute_event_timestamp_mixture.py:419`, `:420` (`test_recorded_denominator_matches_docstring_claim`) | a module-level literal baseline `_MIXTURE_FUNCTION_PAIRS`/`_MIXTURE_FILES` | 1 (`0f63d3ae2e` 13→14) | LIVE-STRUCTURE PIN (it checks prose, not code) | RETIRE the test and remove the "2 files / 14 functions" numbers from the docstring. Covering guard: `test_derived_mixture_matches_recorded_baseline`, set equality against the live AST derivation. | **Violation:** add a mixture function in a scanned test file without recording it; the covering guard reds. |
| F10 | `tests/agent/test_agent_config_migration.py:238`; `tests/specify_cli/regression/test_twelve_agent_parity.py:233` | `AGENT_DIR_TO_KEY` (production), `NON_MIGRATED_AGENTS` | 1 each (`329e6fae11` 12→13, LLxprt) | LIVE-STRUCTURE PIN. The supported-agent **set** is a product contract; its **count** is derived. | Set equality across the registries: `set(AGENT_DIR_TO_KEY)` equals the slash-command dirs of the canonical `AGENT_DIRS` (`m_0_9_1_complete_lane_migration`), and `NON_MIGRATED_AGENTS` equals the `AGENT_COMMAND_CONFIG` keys. The existing special-mapping asserts (`:241-245`) stay. | **Violation:** add a dir to `AGENT_DIRS` without a key mapping; the set equality reds. **Neutral:** register a new agent consistently; green. |
| F11 | `tests/architectural/test_remediation_effectiveness.py:325`, `:335`, `:341`, `:403` | AST-discovered remediation-emitting states and producers in the live `charter` status computer; `_EXEMPT_STATES` | 1 (`7ede9ca13e`: `_REMEDIATION_STATE_FLOOR` 5→7, sum 7→9) | LIVE-STRUCTURE PIN (three `== *_FLOOR` plus an exact sum) | Partition invariant: `discovered_emitting == set(_CASES)` and `all_discovered_states == discovered_emitting ∪ _EXEMPT_STATES`, with `discovered_emitting ∩ _EXEMPT_STATES == ∅`. Floors become `>=` for non-vacuity. This closes the reviewer's exploit (`:348-360`) by construction rather than by a pinned sum. | **Violation:** the documented exploit (set `remediation=None` on a real state without declaring it exempt); the partition reds. **Neutral:** add a new emitting state together with its `_CASES` entry; green. |
| F12 | `tests/architectural/test_tracker_egress_guards_3108.py:947` `EXPECTED_ENCLOSING_COUNT` (asserted `:1158`); `:965` `EXPECTED_CALL_EXPRESSION_COUNT` (`:1159`) | enclosing functions and call expressions of the tracker egress verdict in live `src/` | 2 each (`81e95a8a93` up, `93dfab2e81` down; both on real egress-site changes) | Split. `EXPECTED_ENCLOSING_COUNT` is a **redundant pin**: `:1150` already asserts set equality with `EXPECTED_ENCLOSING_FUNCTIONS`, so retire it. `EXPECTED_CALL_EXPRESSION_COUNT` is a **GENUINE CONTRACT CARDINALITY**: an audited security census (#3108/#3030 egress consent) where each extra call expression is a new egress point that must be reviewed, and it moved only when egress sites changed. Keep it. Optionally re-key it as `{qualname: n}` so a failure names the function. | **`ENCLOSING`:** remove a function from the live set; `:1149` reds. **`CALL_EXPRESSION`:** keep the existing G4 mutation tests (`:1229`). |

The following re-pinned sites are **not converted**. Record their dispositions for SC-004.

| HEAD file:line | Re-pins since Aug | Classification | Reason |
|---|---|---|---|
| `tests/architectural/_baselines.yaml:387` `test_mutation_ownership_routing.destructive_op_allowlist: 61` (**"destructive-op baseline"**) | 2 (`c0bd1f4830` 55→56 #4907, `fb046369b0` 56→61 #4961/#4960/#4989) | RATCHET BASELINE, working as designed | Every growth landed with the matching allowlist row and a `# justification:` naming the new genuinely-safe raw op (`_baselines.yaml:373-386`). It moves only with the allowlist, so FR-008 holds. A floor would loosen it (C-003). |
| `tests/architectural/_baselines.yaml:231` `test_no_inert_schema_slots.baseline_entries: 36` (**"inert-slot ceiling"**, `_inert_slots.BASELINE_SLOTS` via the `_SIZE_RATCHETS` row `:236`; rows in `_inert_slots_baseline.yaml`) | 4 (`709a59534a` 48→47, `2f4659c2b5` 47→37, `e7dc1b344c` 37→38, `b4671d74ef` 38→36) | RATCHET BASELINE, working as designed | 3 of the 4 moves are burn-down. The one growth (+1 `path_conventions`, #3831/#4088) is a real new debt row with disposition `wire-the-producer`. `_inert_slots*.py` itself holds no count pin. |
| `tests/architectural/_baselines.yaml:158` `category_7_grandfathered_orphans: 5` | 13 (6 up, 7 down) | RATCHET BASELINE, working as a visibility device | Every move carries a justification. The growth is real new orphans, which is a burn-down concern (#925), not a pin. |
| `tests/architectural/_baselines.yaml:321` `egress_allowlist_files: 17`; `:50`, `:60`, `:72`, `:75`, `:356` (the other category and residual leaves) | 1-8 each | RATCHET BASELINE | Each growth coincides with a reviewed consent- or dead-module-class allowlist row. |
| `tests/architectural/test_charter_path_literal_authority.py:575` `CHARTER_PATH_LITERAL_FLOOR = 49` (a ceiling with `FLOOR_MARGIN`); `charter_path_literal_allowlist.yaml:65` | 6 / 8 | RATCHET BASELINE (misnamed: it is a ceiling) | The up-moves were detector blind-spot closures (`cbd3085aff`, `3bb93800ec`), which measured more existing debt. **One exception:** `583db03345` ("re-pin charter path-literal allow-list for S3776 extraction") moved it on a behaviour-neutral refactor. That is an FR-008 violation in history, not today. Recommend renaming it to `_CEILING` in whichever WP touches the file. |
| `tests/architectural/test_inline_meta_read_gate.py:75` `INLINE_META_READ_FLOOR = 2` (a ceiling; asserted `== len(allowlist)` at `:971`) | 1 (`81d8eaf8de` 7→2, down) | RATCHET BASELINE (lock-in-on-shrink) | Moved only on burn-down. Freeze `:971` in the census baseline as RATCHET. |
| `tests/architectural/test_ratchet_positional_anchor_ban.py:1055` `len(_FR014_DEFERRED_CENSUS_ALLOWLISTS) == 1` | 1 (`177e062694` 2→1, down) | RATCHET BASELINE (an enumerated shrink-only set) | Freeze as RATCHET. |
| `tests/architectural/test_home_pin_gate_verdict.py:87` `KEYS_CHECKED_FLOOR = 0`; `tests/next/test_internal_runtime_parity.py:36` `_RUNTIME_PACKAGE_FILE_FLOOR`; `tests/consolidation/test_single_rollback_authority.py:31` `_CALLER_FLOOR`; `tests/architectural/test_loop_aware_resolution.py:219`, `:381`; `tests/architectural/test_no_worktree_name_guess.py:216`; `tests/architectural/test_ruff_format_exclude_ratchet.py:33` | 1-2 each | RATCHET BASELINE / non-vacuity floor | Compared with `>=`/`<=`, not `==`, and moved with debt. Correct as they are. |
| `tests/post_merge/test_stale_assertions_message.py:223`, `:254`, `:259`, `:260`; `tests/zeitgeist_client/test_cli_zeitgeist_e2e.py:162`, `:416`; `tests/policy/test_hook_installer_rendering.py:43`; `tests/zeitgeist_client/test_transport.py:93` (and 3 more); `tests/migration/test_mission_state_repair.py:135` (and 3 more); `tests/review/test_pre_review_gate_integration.py:533`; `tests/agent/test_agent_config_migration.py:70`, `:85`, `:103` | 1 each | LOCAL TEST VALUE | Counts of what the unit under test emitted for a fixture: findings, lines, requests, rows, events. These are behavioural assertions and they moved with behaviour changes. Not pins. |

### 2.4 Named examples already resolved, or gone since August (Edge Case 6)

| Example | Resolution |
|---|---|
| `ROUTED_LOAD_META_FLOOR` (`tests/architectural/test_inline_meta_read_gate.py`) | **RESOLVED.** Deleted outright in `dd82bd340b` "delete the routed-meta count floor outright (#4315)" on 2026-09-14, after **17 re-pins** (117 to 157, e.g. `bcbf1c6e5e` 141→142, `06f8c85d9f` 128→130). |
| DRG `_EXPECTED_NODE_COUNT`/`_EXPECTED_EDGE_COUNT` (`tests/doctrine/drg/**`, `test_loader_fail_closed.py`, `test_pack_relocation_doctor_gate.py`) | **RESOLVED** by `2e40057da1` (#3234): the counts are now filesystem-derived (`pure_builtin_node_count()`, `builtin_profile_count()`). This is the in-repo precedent for F4 and F5. |
| `category_1_auto_discovered_migrations`, `category_a_slice_f_deferred`, `category_b_grandfathered_legacy`, `unassigned_entries` (`_baselines.yaml`) | **GONE.** Drained by `9aa6d6981a` ("frozen-baseline toll reduction", #2853) and `b4671d74ef`. |
| `tests/sync/**`, `tests/delivery/**`, `tests/contract/test_body_sync.py` counts | **GONE** with the sync transport (issue #5). |
| Destructive-op *line* re-pins (e.g. `24b2ae360e` "migrate.py rmdir census line 344->351", `925dfb6abb`) | **RESOLVED** by #5085 (`133755de03`, content-keyed census; the exemptions of `test_ratchet_positional_anchor_ban.py` are pinned empty). These were the line-anchor class, not counts. |

---

## 3. FR-010 census-gate proposal

### 3.1 Prior art: what must not be repeated

`tests/architectural/test_golden_count_ban.py` (mission 01KXDKBX, #2076) was demoted to advisory in #3458 and deleted by #4315 (`a428532719`). It flagged every `len(<expr>) == <int>`, about 2,000 sites, of which about 500 were classified `convert` by a word heuristic. It recorded failures as **per-directory counts**, which led to three problems:

- "13 of 15 baseline commits were whole-tree re-freezes forced by unrelated additions";
- 0 real catches;
- an escape-marker toll of 381 annotations.

It chose counts on purpose, believing that a per-site baseline "would need line-based keys". That belief is **false today**: #5085's `ContentDescriptor`/`partition_findings` substrate keys sites by content.

### 3.2 The rule

These are exact predicates, all AST-decidable, with no word heuristics.

**R1: exact count of a module-scope collection.** A node is flagged when all of the following hold:

1. **Where the comparison sits.** It is an `ast.Compare` with exactly one `Eq`, reachable from an `ast.Assert` test through `BoolOp`/`UnaryOp` only, or it is an `assertEqual(a, b)` call.
2. **The shape.** One operand is `len(E)` with one positional argument and no keywords. The other is either an `int` literal other than 0 (`bool` excluded), or a `Name` bound at module scope to an `int` literal (indirection).
3. **The root of `E`.** Unwrap `list/set/frozenset/tuple/sorted(x)` and `x.keys()/.values()/.items()`, then take the root `Name` of any attribute chain. That root is:
   - bound at the **module scope of the same file**, by assignment, `def`/`class`, or `import`/`from … import`;
   - **not** shadowed in the enclosing function, whether as a parameter or a `Store` name.
4. **The leaf name is constant-style.** It matches `^_?([A-Z][A-Z0-9_]*|[A-Z][a-zA-Z0-9]+)$`, i.e. UPPER_CASE or CapWords.
5. **The module-level binding is not a `str`/`bytes` literal.** That excludes `len(MISSION_ID) == 26`, which is a length, not a cardinality.

**R2: a floor or ceiling compared by equality.** A `Compare`/`assertEqual` as in R1.1, where either operand is a `Name` ending `_FLOOR` or `_CEILING`. An `==` against a floor is an exact pin under a floor's name.

**How R1 tells a live collection from a local literal.** It does not try to decide it semantically, which is where the old gate failed. It flags only names bound at module scope. The fixture-local counts are the 2,333 `LOCAL` hits of §1.2: `tmp_path` outputs, returned lists, emitted events. Those are behavioural and never flagged.

A module-scope collection counted exactly is a pin whether it is:

- imported from production (`ALLOWED_TRANSITIONS`);
- derived at import time (`_REQUIRED_TOP_LEVEL_KEYS`);
- a test-file literal whose membership another assertion forces to track production (`SYMBOL_TO_MODULE`, the worst offender).

All three need a second edit when a legitimate member is added.

**Deliberately out of scope.** These are known misses. The mission handles them directly, and review catches regressions.

- Counts that reach live structure through a local, such as `materialize_calls = [...]; len(materialize_calls) == 29`, or F4, F5, F7.
- Parametrize-table expected counts (F6).
- Module-level names imported *inside* the test function.

A third rule for any of these would reintroduce the heuristic class that sank the old gate.

### 3.3 Expected false-positive classes

Out of the 38 hits at HEAD:

| Class | Hits | Example | Handling |
|---|---:|---|---|
| Runtime-mutable module state observed after an act | 1 | `tests/specify_cli/invocation/test_propagator.py:227` `len(_PENDING_SEND_TASKS) == 1` | Freeze with disposition `behavioural`. The rule already drops lowercase runtime attributes (`_RecordingServer.instances`, `ManifestRegistry._cache`, `charter_cache`) through R1.4 or `n == 0`. |
| A test-file literal with a self-check count and no production link | 6 | `_DURABLE_CELLS` and `_INSULATED_CELLS` (module-level asserts), `_EXPECTED_TRIPLES`, `_DISTINCT_CONFIG_KEYS`, `KNOWN_DECISION_SITES` (dormant oracle), `BASELINE_FUNCTIONAL_ASSERTIONS` | Freeze with disposition `self-literal`. These can only change when the same file changes, so they cause little friction. |
| Frozen historical snapshots | 3 | `FROZEN_PRIOR_REDIRECT_KEYS` ×2 (the closed-mission 149-key census), `_RETIRED_BATTERY_UNION` | Freeze with disposition `contract: immutable snapshot`. |
| Published contract cardinality, where set equality would be stronger | 5 | `CANONICAL_LANES == 9` and `_STATUS_LANES_CANONICAL == 9` (the documented 9-lane FSM), `ALLOWED_TRANSITIONS == 29` ×2, `RETROSPECTIVE_EVENT_NAMES == 8` | Freeze with disposition `contract`, and follow up with a conversion to set equality. |
| Ratchet lock-ins (R2) | 2 | `INLINE_META_READ_FLOOR` `:971`, `_FR014_DEFERRED_CENSUS_ALLOWLISTS` | Freeze with disposition `ratchet`. |

These classes need no special-casing in the rule: a reviewed baseline entry with a disposition is the only exemption surface. **There is no inline escape marker.** The #4315 lesson is that a marker becomes a toll.

### 3.4 Frozen baseline if introduced today

Prototype run: `census_proto4.py`, Appendix B. There are **38 findings in 31 files**:

- 3 in `tests/architectural/test_remediation_effectiveness.py`;
- 3 in `tests/status/test_transitions.py`;
- 2 each in `test_no_absolute_event_timestamp_mixture.py`, `tests/docs/test_redirect_spine.py` and `tests/integration/test_review_durability_matrix.py`;
- 1 each in the other 26 files: `test_strictness.py`, `test_agent_config_migration.py`, `test_hosted_drain_gate.py`, `test_inline_meta_read_gate.py`, `test_os_detection_ban.py`, `test_ratchet_baselines.py`, `test_ratchet_positional_anchor_ban.py`, `test_timing_coverage_invariant.py`, `test_merge_compat_surface.py`, `test_merge_driver_goldens.py`, `test_merge_drivers.py`, `test_reconciliation.py`, `test_path_ref_resolver.py`, `test_instantiates_edges.py`, `test_events_shapes.py`, `test_gate_registry.py`, `tests/runtime/_bridge_oracle.py`, `test_tasks_compat_surface.py`, `test_diagnostic_codes_documented.py`, `test_propagator.py`, `test_twelve_agent_parity.py`, `shims/test_generator.py`, `shims/test_registry.py`, `test_command_installer.py`, `test_state_gitignore_migration.py`, `test_m_4_0_0rc5_retire_single_owner_doctrine_ids.py`.

The conversions in F1, F2, F8, F9 (×2), F10 (×2) and F11 (×3 R2 lines) remove 10 of them, leaving a **frozen baseline of 28 entries**. By disposition:

- 12 live-structure debt: `MERGE_DRIVER_BODIES`, `TERMINUS_ENTRY_POINTS`, `_PATH_KIND_PATTERNS`, `GATE_REGISTRY`, `CLI_DRIVEN_COMMANDS`, `PROMPT_DRIVEN_COMMANDS`, `CANONICAL_COMMANDS`, `_NEW_RUNTIME_ENTRIES`, `_PROVIDERS`, `RETIREMENTS`, `Strictness`, and `_NFR002_FLOOR`/`_OS_EXEMPTION_FLOOR` as R2;
- 5 contract;
- 3 immutable snapshot;
- 6 self-literal;
- 2 ratchet;
- 1 behavioural.

The exact per-bucket tally drifts by ±1, depending on whether the two R2 floors are counted under debt or ratchet. The planner fixes the final number when the baseline is generated. Generate it from the detector's output, never by hand, as `_exemptions/*.txt` already requires.

### 3.5 Content keys, never lines

- **Descriptor.** Each finding's key is `(rel_path, enclosing qualname, token_line)`, from `tests.architectural._ratchet_keys.composite_key` via `_content_identity`. Baseline entries are `ContentDescriptor` lines in the existing text form, rendered by `render_descriptor_line` and parsed by `parse_descriptor_line(line, rationale=<file or section>)`:

  ```text
  tests/status/test_transitions.py::TestConstants.test_allowed_transitions_count::len ( ALLOWED_TRANSITIONS ) ==
  ```

- **Leave the integer out of `token_substring`.** `code_tokens_by_line` keeps number tokens, but the descriptor matches on a *substring*. So re-pinning a frozen entry (196 → 197) neither stales the entry nor forces a baseline edit. The baseline identifies the *site*, not its value. Otherwise every re-pin of a frozen pin would cost a second edit, the double-entry toll this mission removes. The known cost: a frozen pin's re-pin is not visible to the gate. The remedy is conversion, not a tighter key.
- **Matching.** Use `resolve_allowlist` and `partition_findings`: multiset semantics, and the `rel_path` in the key stops cross-file blessing. Caller policy is **hand-curated**: a *stale* descriptor (`resolve_allowlist` errors, or unused keys) **fails**, which is US3 AC-2. An unexpected finding fails and names `file::qualname` plus the assertion text.
- **Existing guards.**
  - `test_ratchet_positional_anchor_ban.py`'s text arm scans `tests/architectural/**/*.txt` for `path:line` keys. Descriptor lines pass it, so the new file is automatically protected against line pins.
  - #5085 made the positional-anchor ban import-agnostic, so the gate module's own seeds must avoid `(path, int)` tuples.
- **Drift proof (NFR-001 pattern).** The self-test runs the scanner on `with_blank_line_at_top(src)` and `with_probe_above_statement(src, lineno)` and asserts an identical `(unexpected, suppressed)` identity.

### 3.6 Where it lives

| Artifact | Path | Precedent |
|---|---|---|
| Gate | `tests/architectural/test_exact_count_census.py` (`pytestmark = [pytest.mark.architectural]`) | `test_os_detection_ban.py` |
| Scanner, importable by the self-test | `tests/architectural/_exact_count_census.py`, exposing `scan_source(rel, src)` and `FROZEN_PINS: frozenset[ContentDescriptor]` | `_os_detection_exemptions.py`, `_inert_slots.py` (`BASELINE_SLOTS`) |
| Frozen baseline | `tests/architectural/_exemptions/exact-count-census.txt` (commented disposition blocks, one descriptor per line) | `_exemptions/os-detect-ban-deferred.txt` |
| Shrink-only ceiling | a new `_SIZE_RATCHETS` row `("test_exact_count_census", "frozen_pins", "tests.architectural._exact_count_census", "FROZEN_PINS")` plus the `_baselines.yaml` leaf `test_exact_count_census: frozen_pins: 28  # justification: …` | the `test_no_inert_schema_slots.baseline_entries` row |
| Classification | if it is registered in `shape_guard_membership.yaml`, class it `behavioral` or `enforcement-allowlist`, **never `shape-guard`** (its predecessor's demotion class) | `test_shape_guard_membership.py` |

On the `_SIZE_RATCHETS` row: the `.txt` alone can grow, because an author can add a line to silence the gate. The numeric leaf is the tactic's second visible approval diff (`frozen-baseline-shrink-only-ratchet` step 2; `testing-principles` "Shrink-only count ratchets are sanctioned … new entries require a visible human approval step"). It adds a 16th section, so **F2 must be converted in the same WP or earlier** (§0 item 6).

### 3.7 Self-mutation test (`architectural-gate-non-vacuity`)

1. **Planted positive (R1).** `scan_source("scratch/t.py", 'X = frozenset({"a","b"})\ndef test_x():\n    assert len(X) == 2\n')` returns exactly one finding keyed `("scratch/t.py", "test_x", …)`. Also:
   - the reversed order `assert 3 == len(REG) and True`, with `from m import REG`, is flagged;
   - the `assertEqual(len(X), 2)` form is flagged.
2. **Planted positive (R2).** `X_FLOOR = 3` with `assert len(found) == X_FLOOR` is flagged.
3. **Negative fixtures, one each:**
   - a local literal `x=[1,2]; len(x)==2`;
   - a `str` constant `ID="01ABC"; len(ID)==5`;
   - emptiness `len(REG)==0`;
   - a shadowing parameter `def test(REG): len(REG)==4`;
   - a lowercase runtime attribute;
   - a floor used correctly: `>=`.

   None is flagged. The prototype already behaves this way on all of them; see Appendix B, where the outputs match.
4. **Self-scan.** The scan universe includes `tests/architectural/` and so the gate's own module. A planted `assert len(_SOME_MODULE_SET) == 1` inside the gate file reds.
5. **Authority-parse non-vacuity.** Point the loader at a scratch copy of `exact-count-census.txt` with one descriptor removed. The real-tree run must turn red, naming that site; this proves the gate reads the baseline it claims. Also add a stale descriptor, and the gate must report it as stale.
6. **Real-tree floor.** While the baseline is non-empty, assert that at least one frozen descriptor resolves live. When the baseline reaches 0, this step becomes "the scanner found at least N scanned files", mirroring `_RUNTIME_PACKAGE_FILE_FLOOR`, so an empty glob cannot pass vacuously.
7. **Prefilter soundness.** The detector parses only files that pass a textual prefilter (§3.8). A test runs `scan_source` on every planted fixture with the prefilter bypassed and with it applied, and asserts identical findings.

### 3.8 Runtime (NFR-002: under 5 s)

Measured on this host, an AMD Ryzen 9 7950X3D, over the full `tests/` tree (3,624 `.py` files), 3 runs each:

| Variant | Files parsed | Findings | Wall time |
|---|---:|---:|---:|
| Naive: `ast.parse` of every file, GC on | 3,624 | n/a | 7.2–10.5 s (parse alone) |
| Stage-1 prefilter `len\(.*\)\s*==\|==\s*len\(\|assertEqual\(\s*len\(\|==\s*[\w.]*_(FLOOR\|CEILING)\b\|_(FLOOR\|CEILING)\s*==`, GC disabled around the loop | 950 | 38 | 2.9 s |
| Stage-1 plus stage-2 (a candidate `len(NAME` whose `NAME` appears at column 0, or in the module preamble before the first top-level `def`/`class`; or the file mentions `_FLOOR`/`_CEILING`), GC disabled | 305 | **38 (identical set)** | **1.5 s** |

**Estimate.** About 1.5 s here, and no more than about 3.5 s on a slower laptop at roughly 2× single-thread. That fits the budget.

**Requirements this puts on the implementation:**

- **GC off during parsing.** Wrap the parse loop in `gc.disable()`/`try…finally gc.enable()`. `ast.parse` allocation churn otherwise doubles the time.
- **Prefilter soundness.** Keep §3.7 step 7.
- **One pass.** Scan once per session, e.g. with `functools.lru_cache` on the scan function, the pattern `_home_pin_scan.py:1056` uses.

---

## 4. Conversion grouping (file-disjoint)

Each row owns its files exclusively. Sizes: **S** is at most about 1 hour with one file, **M** has two or three files or a new invariant, **L** is new gate machinery.

| Group | Files (exclusive) | Items | Size | Depends on |
|---|---|---|---|---|
| **G1 Compat-surface pin** | `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py` | #5346-2 / F1 | S | none |
| **G2 Consolidation trio** | `tests/consolidation/test_mid8_embedded_preflight.py`, `tests/consolidation/test_issue_4474_topology_aware_bake.py`, `tests/consolidation/test_behind_head_recovery_coverage.py` | #5346-3, -4, -6 | M | none. It only *names* `test_executor_lane_naming.py` and `test_mission_number_truthful_4900.py` as covering guards and does not edit them. |
| **G3 Copied-literal pins** | `tests/ci/test_recapture_charter_shard_timings.py`, `tests/specify_cli/coordination/test_teardown_single_seam_routing.py` | #5346-5, -7 | M | none |
| **G4 Architectural count pins** | `tests/architectural/test_no_absolute_event_timestamp_mixture.py`, `tests/architectural/test_remediation_effectiveness.py`, `tests/architectural/test_tracker_egress_guards_3108.py` | F9, F11, F12 (ENCLOSING retire, CALL keep) | M | none |
| **G5 Live-source call-site counts** | `tests/runtime/test_bridge_decision_builder.py`, `tests/git/test_guard_capability_regression.py`, `tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py` | F3 (+ `:510` campsite), F6, F8 | M | none |
| **G6 Corpus and data-artefact counts** | `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`, `tests/docs/test_glossary_linker.py`, `tests/unit/convergence/test_census_status.py` | F4, F5, F7 | M. F4's shape invariant needs care, since it is the largest docstring. | none |
| **G7 Agent-registry counts** | `tests/agent/test_agent_config_migration.py`, `tests/specify_cli/regression/test_twelve_agent_parity.py` | F10 | S | none. It could fold into G5 if the planner wants fewer WPs, since the files are disjoint. |
| **G8 Census gate plus the ratchet section count** | `tests/architectural/test_ratchet_baselines.py`, `tests/architectural/_baselines.yaml`, new `tests/architectural/test_exact_count_census.py`, new `tests/architectural/_exact_count_census.py`, new `tests/architectural/_exemptions/exact-count-census.txt`, and optionally `tests/architectural/shape_guard_membership.yaml` | #5346-1 / F2, FR-010 | L | **G1 and G4–G7.** Generate the baseline *after* the conversions land, so no conversion WP has to edit the baseline file; that keeps G8 file-disjoint. Put F2 in G8 because both edit `test_ratchet_baselines.py`. |

**Dispositions only, no WP.** The RATCHET, CONTRACT and LOCAL rows of §2.3 and the RESOLVED rows of §2.4 need no conversion, only a line each in the evidence record for SC-004. The planner may attach them to G8's evidence file.

**Not covered here.** FR-009, re-keying the dead-symbol allowlist off function-body hashes, is a separate pin class. It is outside this lens.

**Test runs.** Each group runs only its own files plus the named covering-guard files (C-001), e.g. G2 additionally runs `tests/consolidation/test_executor_lane_naming.py` and `tests/consolidation/test_mission_number_truthful_4900.py`. G8 runs only `test_ratchet_baselines.py`, `test_exact_count_census.py` and `test_ratchet_positional_anchor_ban.py`, never the `tests/architectural/` directory.

---

## Appendix A: history miner (`scan_history.py`, core)

```python
PY_PATTERN = r"len\(.*\) *== *-?[0-9]|[0-9] *== *len\(|assertEqual\(len\(|(_FLOOR|_CEILING|_COUNT|_BASELINE|_CAP|_MAX|_MIN)\b.*[0-9]|(floor|ceiling|baseline|count|cap)[A-Za-z_]* *[:=] *[0-9]"
INT = re.compile(r"(?<![\w.])-?\d+(?![\w.])")
def norm(line):  # integers -> '#', comments stripped, whitespace collapsed
    code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else line
    return re.sub(r"\s+", " ", INT.sub("#", code)).strip()
# For each commit/file hunk of the two `git log -p -U0` runs in §1.3: pair a '-' line and a '+' line
# with equal norm() and different INT.findall() -> one re-pin event (commit, file, old, new).
# YAML/JSON lines qualify via r'^\s*"?[A-Za-z_][\w.\-]*"?\s:\s*[0-9]+\s*,?\s*(#.*)?$'.
# Deduplicate on (commit, file, old, new); group by (file, norm) -> site; map to HEAD by norm() in same file.
```

## Appendix B: census detector prototype (`census_proto4.py`, core of R1 and R2)

```python
CONST_STYLE = re.compile(r"^_?([A-Z][A-Z0-9_]*|[A-Z][a-zA-Z0-9]+)$")
# module_scope(tree) -> (names bound at module scope incl. imports/defs, names bound to str/bytes literals,
#                        {name: int} for module-level int literals)
# visit(): per FunctionDef, shadow = params | Store-names in that function (inherited by nested defs)
# For each Assert (Compare with one Eq, anywhere under the assert's test) or assertEqual call:
#   R2: either operand is Name ending _FLOOR/_CEILING                         -> flag "R2 == NAME"
#   R1: operand a is len(E); b is int literal != 0, or module int-constant Name (not shadowed);
#       unwrap E through list/set/frozenset/tuple/sorted and .keys/.values/.items; leaf,root = attr chain;
#       root in module scope, not shadowed, not a str/bytes literal; leaf matches CONST_STYLE -> flag
# Prefilter stage 1 (regex, §3.8), stage 2: some len(NAME candidate is at column 0 or in the preamble
# before the first top-level def/class, or the file mentions _FLOOR/_CEILING. gc.disable() around the loop.
# Planted-source outputs (verified):
#   'X = frozenset({"a","b"})\ndef test_x():\n    assert len(X) == 2'   -> [('t.py','test_x',3,'R1 len(X) ==')]
#   local literal / str length / == 0 / shadowing param                   -> []
#   'from m import REG ... assert 3 == len(REG) and True'                  -> flagged (R1)
#   'X_FLOOR = 3 ... assert len(found) == X_FLOOR'                        -> flagged (R2)
```
