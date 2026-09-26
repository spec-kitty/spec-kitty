# Post-tasks squad — Python Pedro (implementer feasibility + code truth), WP08..WP13

Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z`, HEAD `dac86aa2`, planning base `3717c7ea` (verified an ancestor; `git cat-file -t` returns commit; the repo is shallow).

**Governance applied:**
- Profile `python-pedro` (implementer): TDD/red-first, ruff+mypy gate, no architectural decisions.
- Directives 010/024/025/030/034/041/043/044/045/051.
- Tactics tdd-red-green-refactor, delete-the-assertion-not-the-test, bug-fixing-checklist.
- `charter context --action tasks`: DIRECTIVE_041/043/044, USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY, RECONCILE_CHANGE_SCOPE_TENSIONS, and the SO #4/#5 non-vacuity rule. I applied these as the lens: every claimed mutation or red was probed through the real code path.

All probes were run read-only in the scratchpad (plugins under `squad/mut/`, the WP10 prototype under `squad/wp10/`, the seam probe under `squad/seam/`).

## Findings

### Cross-WP (blocks WP01–WP12 review flow)

- **[HIGH] WP13 T073 — the issue matrix gates every approval now, not only at closeout.**
  - The coord branch `kitty/mission-…-01M3EW3Z` already holds `issue-matrix.json` with 17 rows, all `verdict: "unknown"`.
  - `discover_issue_references` over spec/plan/research/tasks finds **23** gating refs. Six have no row at all: #1979, #2531, #3251, #4727, #5061, #5068.
  - `tasks_move_task._mt_issue_matrix_blocker` runs `_issue_matrix_approval_blocker` on every `move-task --to approved`. I probed it against the coord matrix, and it returns "has unresolved entries … verdict 'unknown' is not in the allowed set" for all 17 rows. `missing_issues` also blocks at `approved`.
  - So WP01..WP12 cannot be approved until rows exist, while T073 is the last WP.
  - **Fix:** add an early step. Either a new T000 in WP01, or an operator step before the first review. It seeds all 23 rows through `spec-kitty agent issue-verdict` as `in-mission`, which is accepted at approved, or as `not-applicable` for context refs. WP13 T073 then only terminalizes them. Also correct T073's "6 rows" framing to "23 gating refs, 17 already scaffolded".

### WP08

- **[MEDIUM] WP08 T045 step 2 — the mutation claim is false for the `delattr` variant.**
  - `engine._read_snapshot` has 3 internal callers: `engine.py:280`, `:541` and `:814`.
  - Probe: `del engine._read_snapshot` makes all 4 golden nodes ERROR, not only the pin.
  - **Fix:** drop the monkeypatch/delattr option. Specify a behaviour-preserving rename of the def and all 3 call sites in a scratch copy; then only `test_submodule_surface_matches_contract` reds. Note that `tests/runtime/test_bridge_parity.py:294` (WP11's `advance_to_step`) also imports it.
  - WP12 T066 row 1 repeats the claim, so fix it there too.
- **[MEDIUM] WP08 T048 step 1 — the `missing_seams` rationale and mutation expectation are wrong.**
  - Probe: rename both exempt seams (`_resolve_events_path` and `_canonical_events_dir`) with the arm removed. The kept ban **still reds**, via gate.py:218 and agent_retrospect.py:264. The seams contain the fallback reads, and the exemption is by name.
  - So "renaming reds only the removed arm" is false: the arm is redundant, not a lone name pin.
  - **Fix:** re-disposition it as "retire (redundant within test): the ban already reds on seam rename or deletion", citing this probe. Otherwise, keep the arm.
- **[LOW] WP08 Test Strategy — the collect-only delta is miscounted.** Base has 8 nodes. The plan retires 3 and adds 3 tests. "+4 new" only holds if `…fails_on_missing_or_empty_target` is parametrized (missing/empty). Say which.
- **[LOW] WP08 T046 vs Review Guidance item 6 — contradictory instructions.** The method being edited, `test_placeholder_is_absent_from_runtime_source`, lives inside `TestNoLegacyQueryPlaceholderInTemplates`, which the guidance says to leave "untouched". Clarify: only its sibling method stays untouched. Also say whether the new floor and planted tests go in that class or at module level.
- **[LOW] WP08 Test Strategy — mypy baseline is red.**
  - `mypy tests/next/test_internal_runtime_parity.py` has 6 pre-existing `type-arg` errors (L72-73 etc.).
  - The WP's "mypy clean" bar is unattainable without campsite fixes. State "0 new errors" or authorize the fix.
- **Verified OK:**
  - 16 files in `_internal_runtime` and 31 in `runtime/next`.
  - `src/specify_cli/next` is absent.
  - The only rich import is `runtime_bridge_retrospective.py:158`.
  - The survivor `test_production_never_imports_retired_runtime_package` exists with its planted self-test.
  - 0 placeholder hits in src/packs.
  - All pyproject exclude line numbers are exact.
  - The `_apply_xfail`/`_MATRIX` anchors are right and all 14 rows are `None`.
  - The T048 anchors are exact: L280, L205, L154, L181 and L2195-2200.

### WP09

- **[HIGH] WP09 T049 M1 — the mutation target does not exist in `src/`.**
  - Lane-state ordering is `spec_kitty_events.diary.reduce_parsed` (site-packages `diary.py:1579`, `sorted(unique_events, key=(at, event_id))`).
  - The `(at, event_id)` sorts in `src/specify_cli/status/reducer.py:105/156` only order the provenance projections. Mutating them leaves both expected reds green, and `git checkout -- src/` cannot revert a site-packages edit.
  - **Fix (probe-verified):** use a plugin that shadows the builtin in the module globals: `spec_kitty_events.diary.sorted = lambda it, key=None, reverse=False: list(it)`. With it, both `test_event_order_does_not_affect_final_state` and `TestReduceOutOfOrder::test_reduce_out_of_order_events` go red.
- **[MEDIUM] WP09 T049 M2–M4 — the plugin variant silently under-reports.** `ALLOWED_TRANSITIONS` is frozen at import (`transitions.py:53`). Monkeypatching `allowed_targets` alone leaves the parity tests and `test_allowed_transitions_count` green. Probe-verified: M2 gave 4 reds, not 6.
  - **Fix:** say "source edit (import-time)", or in a plugin also set `transitions.ALLOWED_TRANSITIONS = _derive_allowed_transitions()`.
  - With the recompute, the results match the table:
    - M2 reds the parity test plus the 5 named survivors, plus `test_collapsed_matrix_catches_planted_row`;
    - M3 reds the parity test plus `test_allowed_transitions_count`, `test_validate_transition_matches_baseline` and `test_collapsed_matrix_catches_planted_row` (these are the 3 survivors to name);
    - M4 reds the parity test plus `test_allowed_transitions_count`.
- **[LOW] WP09 T050 — the relocated tests drop out of the fast tier.** `test_parity.py` is `pytest.mark.fast`, while `test_reducer.py` is `[integration, git_repo]`. The relocated pure tests therefore leave `make test-fast` (`fast or unit`). Allow a class-level `pytest.mark.fast`, or accept and record it.
- **[LOW] WP09 Test Strategy — mypy baseline is red.** `tests/status/test_transitions.py:172`, plus a followed import in `tests/reliability/fixtures/review_prompt.py:127`. State "0 new errors".
- **Verified OK:**
  - Structure: 21 functions and 29 nodes, with every line number correct. The dispositions cover all 21.
  - Mutations: M7 reds only `test_sorted_keys_in_json_output`, so relocate is correct. M8 reds only the 2 parity tests, with no survivor in reducer/models, so the plan is correct.
  - Survivor anchors (:102/:177/:211/:280/:315/:425/:465, `_make_event` L45) and `_RETIRED_PATHS` L28 / test L390 are all correct.
  - The leftover grep matches the prompt (pyproject plus the historic docs path).

### WP10

- **[MEDIUM] WP10 T054 step 4 — the "8 offenders" count conflicts with the helper spec.** The spec emits one entry per ImportFrom of a `_` name and one per call of it. There are 2 imports and 2 calls, so the private offenders come to 4 and the total to **10 entries**, not 8.
  - **Fix:** either dedupe import and call per name, or expect 10: 6 patches + 2 imports + 2 calls. Otherwise the reviewer's "8" check rejects correct work.
- **[INFO / confirmed] WP10 mechanism works without private patches.**
  - I prototyped a copied mirror (`copytree` of each child, an empty real `directives/`, and the literal-YAML `parity-fixture-agent.agent.yaml`) plus `SPEC_KITTY_PACKS_ROOT`, inside a `git init` tmp dir, as the conftest autouse does.
  - Results for all three placements (repo at the tmp root, in a `repo/` subdir, and with caches pre-warmed against the real packs):
    - `first_load` True, state file written;
    - `directive:DIRECTIVE_998` and `Cause: missing_artifact` present;
    - needle gone, `section:terminology-canon` and `# Governance payload:` present;
    - pack root under tmp, no `PACKS_ROOT` warning.
  - Control (`empty_directives=False`): `missing_artifact` is absent and D998 still present, as the prompt predicts.
  - No `_reset_agent_profile_cache` is needed. There is no C-005 blocker, so the deferral clause should not trigger.
- **Verified OK:** the leftover-reference list is exact (context_contract.py:68, the procedures_json_array docstring L49, render_seams:7, leaf_seams:6). Baseline mypy on the file is clean.

### WP11

- **[MEDIUM] WP11 T060/T061/T062 — the import closure for the moved tests is incomplete.**
  - P0 test bodies use the golden-path aliases **directly**: `_golden_create_mission`, `_golden_init_git_repo`, and `_MissionTopology` (in `@parametrize` and annotations).
  - T061 step 2's import list omits all three. T062 step 2 says to keep them "module-private if unused outside the scaffold", but they *are* used outside it.
  - **Fix:** the new module imports `MissionTopology as _MissionTopology` from `mission_runtime`, and the two golden-path helpers from `tests.integration.test_placement_partition_golden_path`, either directly or via re-exported scaffold names.
  - The `[MissionTopology.COORD]` node IDs are repr-derived, so they stay stable.
- **[LOW] WP11 T060 step 4 — ruff will red on unused imports in the residual oracle module.** Once the helpers leave, `re`, `shlex`, `subprocess`, `write_single_lane_manifest` and `_MissionTopology` are all unused there. Only `_MissionTopology` is mentioned. List them all (import-only edits, C-002-safe).
- **[LOW] WP11 Test Strategy — mypy on the new modules reds on a pre-existing error.** `tests/lane_test_utils.py:82` (`no-any-return`) is a followed import. State "0 errors in owned files".
- **[LOW] WP11 T062 step 4 — the straggler grep also matches `_golden_init_git_repo` call sites.** Say so, or anchor the grep with `\b_init_git_repo`.
- **Verified OK:**
  - 24 base nodes, split into 8 oracle and 16 moved (13 P0 functions → 14 nodes, plus 2 fail-closed).
  - All helper line anchors are exact, and the P0 block uses no oracle symbol.
  - The residual file stays format-dirty (probe: "Would reformat"), so the ratchet is safe.

### WP12

- **[MEDIUM] WP12 T065/T066 — the checker's verdict enum rejects the WP's own rows.** T066 prescribes `keep (retire 1 test)` for 2 rows, which is not in T065's allowed set. The checker can never print `45/45 OK`. **Fix:** add `keep (retire 1 test)`, or use `fix + retire parts`.
- **[LOW] WP12 Branch Strategy — "commit in your lane worktree" is wrong for a `planning_artifact`.** WP12 is in `lane-planning`. `resolve_workspace_for_wp` resolves it to the **repository-root checkout** (branch `None`, target `claude/spec-kitty-remediation-wfje22`). There is no worktree. Say to commit on the primary checkout.
- **Verified OK:** 49 find hits − 4 `_support/coverage_safety` = 45, and `ls-tree 3717c7ea` also gives 45. The #2620 table header sits at L20 of `test-suite-friction-remediation-01KXDKBX/tracer-design-decisions.md`, and `ruff.toml` extend-excludes `kitty-specs/*/research/**`.

### WP13

- **[MEDIUM] WP13 T071 — the drain table misses WP03, and the permission list forbids formatting it.**
  - WP03 rewrites the code of the format-excluded files `tests/architectural/_exemptions/__init__.py` (pyproject L938) and `test_clock_call_ban.py` (L964), and explicitly defers their exclude lines to WP13.
  - The WP13 Context "sequenced out-of-map edits" list names only WP01/05/06/08/09/11 for formatter rewrites, and the table omits both files.
  - **Fix:** add WP03 and the two rows ("format + remove").
- **[MEDIUM] WP13 T071 step 2 — the AST-equality rule misclassifies docstring edits.** `ast.dump` includes docstrings and string constants, so "AST equal ⇔ comment/docstring-only" is false. These are predicted "stay excluded" but will compare AST-different:
  - WP07 `_ratchet_keys.py` (the module docstring L47-59);
  - WP10 `test_context_leaf_seams.py:6` and `test_context_render_seams.py:7` (module docstrings);
  - WP13's own `test_no_read_side_bypass.py` `rationale=` string (L906).

  **Fix:** compare an AST with docstrings stripped (drop the leading `Expr(Constant(str))` of module, class and function bodies). Or accept "format + remove" for these and update the table. Decide one way; the current rule contradicts the current table.
- **[LOW] WP13 T073 step 2 — the doctor command is vaguely named.** "`status doctor`" is actually `spec-kitty agent status doctor --mission <handle>`. The blocker message comes from `move-task`.
- **Verified OK:**
  - `spec-kitty agent issue-verdict` flags and verdict vocabulary match, including the evidence-token rule for `deferred-with-followup`.
  - `tracer-append` flags match.
  - The issue matrix is canonical `issue-matrix.json` on the coord branch, written via `write_target(ISSUE_MATRIX)`, so the CLI is correct and hand-editing is wrong, as the prompt says.
  - Lane-l merges all 12 dependency lanes (`worktree_allocator` #1684), so the `git diff 3717c7ea...HEAD` drain derivation is valid.
  - The aggregate.py:543 edit is a `#` comment, so its AST is equal. All drain-table pyproject line numbers are exact.

## C-005 check

No step in WP08–WP13 requires a `src/` behaviour change. The WP10 mechanism is prototyped green without patches. The only `src/` edits are comments (context_contract.py:68, aggregate.py:543), and both are AST-equal.

## Verdict

**CONDITIONAL GO.**
- Fix before implementation starts: the HIGH issue-matrix seeding (otherwise no WP can reach `approved`) and the HIGH WP09 M1 target.
- Fix before those WPs start (text-only prompt edits): the MEDIUMs, meaning the WP08 mutation claims, the WP10 offender count, the WP11 import closure, the WP12 verdict enum, and the WP13 drain rule/table.
