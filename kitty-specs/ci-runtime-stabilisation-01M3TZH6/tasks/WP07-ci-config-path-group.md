---
work_package_id: WP07
title: ci_config path group selects the battery
dependencies: []
requirement_refs:
- FR-007
- C-003
- C-008
- SC-006
- C-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
phase: Phase 4 - CI path routing and duplicate removal
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_ci_config_battery_routing.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- tests/architectural/_ci_integrity_oracle.py
- tests/ci/test_ci_module_wiring.py
- tests/ci/test_ci_config_battery_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – ci_config path group selects the battery

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Close the CI-configuration blind spot (FR-007 / SC-006): a PR that edits only CI configuration (a workflow, a composite action, a `scripts/ci/` helper, `pytest.ini`, `pyproject.toml`, the `Makefile`, the module registry or the shard timings) must run the architectural battery on its own PR. Today gate selection for such a diff selects no battery, so the gates that guard CI configuration first run after merge.

Done means:

1. A new **non-src** dorny filter group `ci_config` exists in the `changes` job of `.github/workflows/ci-router.yml`, with the eight globs listed in D-09 (no more, no fewer).
2. The group is folded into the `changes` outputs exactly like its non-src siblings, and is **not** in the `unmatched` loop.
3. The `architectural-heavy` job's `if:` ORs in `needs.changes.outputs.ci_config == 'true'`; the `&& needs.prose-scan.outputs.prose_only != 'true'` conjunct stays the single outer AND (C-002).
4. `_ci_integrity_oracle.HEAVY_BATTERY_NON_SRC_GROUPS == frozenset({"architectural", "ci_config"})`.
5. The existing `ci` group, its registry row and its scrub mirror are byte-identical; `scripts/ci/gate_selection.py` is not edited (C-003).
6. Red-first tests prove: every `ci_config` glob selects `architectural-heavy`; a docs-only, `uv.lock`-only or `tests/conftest.py`-only diff still selects no battery; a proven prose-only `scripts/ci/*.py` diff is still subtracted from the battery.

This is the **first router edit of the Mission** (D-30): every later Mission commit that touches CI configuration then runs the battery on the PR's own CI, which is the C-011 evidence the later WPs rely on.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (ATDD-First Discipline, single canonical authority, `NO_FULL_HEAVY_SUITES_IN_MISSION`).
- Mission docs: `kitty-specs/ci-runtime-stabilisation-01M3TZH6/spec.md` (FR-007, C-002, C-003, C-008, SC-006), `plan.md` (IC-05), `research.md` decision log **D-09, D-10, D-20, D-25, D-30** (these govern) and delegate section R2 "FR-007" for detail, `contracts/router-two-authority-amendment.md` (amendment A1 — already written; this WP implements it).
- The archived contract `kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/router-two-authority.md` is byte-frozen by `tests/architectural/test_archive_root_byte_identical.py` — never edit it. The amendment lives in this Mission's `contracts/` (D-10).
- Terminology: say "CI path routing" or "gate selection", never bare "routing" in new prose.
- **Anchor by job/constant name, not line number** — `ci-router.yml` lines drift.
- Workflow file count is at 17/20 — add no workflow file.
- Lane discipline: inside the lane worktree always use `uv run --frozen …`; never `git stash`.

### Current-state anchors (verified 2026-10-01 against `issue-5510-ci-runtime-stabilisation`)

| Surface | Anchor | What is there today |
|---|---|---|
| `ci-router.yml` `changes.outputs` | `architectural:` output (≈ line 98), then `unmatched:` (≈ line 100) | Non-src outputs `docs`, `corpus`, `e2e`, `ci`, `architectural` all use the fold `(inputs.mode == 'full' \|\| steps.unmatched.outputs.unmatched == 'true') && 'true' \|\| steps.filter.outputs.<group>` |
| `ci-router.yml` dorny filter block | `ci:` group (`scripts/ci/**`, `.github/workflows/**`), then `architectural:` (`tests/architectural/**`, ≈ line 209), then `any_src:` (≈ line 214) | No `ci_config` group |
| `ci-router.yml` `unmatched` step | `Compute fail-closed catch-all unmatched signal` | Loops over exactly the 20 src-backed groups; must stay so (`test_unmatched_union_covers_every_src_backed_group`) |
| `ci-router.yml` job `architectural-heavy` | `if: >-` (≈ lines 560-582) | OR of 20 src groups + `needs.changes.outputs.architectural == 'true'`, then `&& needs.prose-scan.outputs.prose_only != 'true'` |
| `_ci_integrity_oracle.py` | `HEAVY_BATTERY_NON_SRC_GROUPS` (≈ line 96) and its comment (≈ lines 90-95, says "`ci` deliberately gates no router job, #4386") | `frozenset({"architectural"})` |
| `tests/ci/test_ci_module_wiring.py` | module docstring last paragraph (≈ lines 26-29) | Claims "The architectural battery's heavy job is gated on src-backed groups, so it would skip such a PR" — becomes false |
| same | `test_ci_infra_only_diffs_route_to_the_named_group` | asserts `matched_groups == frozenset({"ci"})` |
| same | `test_ci_infra_diff_alongside_src_change_keeps_the_src_routing` | asserts `matched_groups == frozenset({"ci", "consolidation"})` |
| same | `_BASE_CONTEXT_ALL_FALSE` (≈ lines 336-359) | no `"changes.ci_config"` key; `_GhIfEvaluator._eval_condition` asserts every referenced key is modelled, so the three golden tests go red the moment the battery `if:` references `ci_config` unless the key is added |
| `scripts/ci/gate_selection.py` | `Router.src_backed_groups`, `routing_groups`, `select_modules` | Derives everything from the YAML; a non-src group joins `routing_groups` (run-all fold) automatically and is dropped from `select_modules` by the registry intersection — **no edit needed** (R2 F1, simulated) |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T030 – Red-first: CI-config-only diffs select the battery; prose/docs-only do not

- **Purpose**: Pin FR-007's observable behaviour through the single gate-selection authority before touching the router, so the change is proven by a test that is red today (charter ATDD-First Discipline).
- **Steps**:
  1. Create `tests/ci/test_ci_config_battery_routing.py` with `pytestmark = pytest.mark.fast` (the `tests/ci` convention; see `tests/ci/test_ci_module_wiring.py`). Import `load_router`, `select_gates`, `select_modules` from `scripts.ci.gate_selection`, and `tests.architectural._ci_integrity_oracle as oracle` (cross-tree import precedent: `tests/ci/test_interpreter_matrix_env_pinning.py`).
  2. A module-scoped `router` fixture (`load_router()`).
  3. `test_ci_config_only_diff_selects_the_heavy_battery` — parametrize one representative path per `ci_config` glob, with ids:
     - `.github/workflows/ci-aggregate.yml`
     - `.github/actions/warmup/action.yml`
     - `scripts/ci/gate_selection.py`
     - `pytest.ini`
     - `pyproject.toml`
     - `Makefile`
     - `.github/ci-module-registry.yml`
     - `.github/ci-shard-timings.json`

     Assert `"architectural-heavy" in sel.selected_jobs`, `"architectural-heavy" in sel.selected_code_shards`, `"ci_config" in sel.matched_groups`, and `not sel.unmatched_src`.
  4. `test_ci_config_leaves_the_module_selection_unchanged` — same parametrization; assert `select_modules([path], router=router)` equals `{"ci"}` for the workflow and `scripts/ci` paths, and `frozenset()` for the other six (the module matrix is not widened — `ci_config` is not a registry row).
  5. `test_out_of_scope_paths_still_skip_the_battery` — parametrize `docs/x.md`, `uv.lock`, `tests/conftest.py`, `packs/built-in/missions/foo.md`; assert `"architectural-heavy" not in sel.selected_jobs`. (`uv.lock` and `tests/conftest.py` are deliberately excluded by D-09.)
  6. `test_ci_config_is_non_src_and_outside_the_catch_all` — assert `"ci_config" in router.routing_groups`, `"ci_config" not in router.src_backed_groups`.
  7. `test_dropping_ci_config_from_the_battery_reds_the_oracle` — positive control modelled on `test_heavy_battery_losing_a_non_src_group_reds_the_oracle` in `tests/architectural/test_ci_integrity_oracle_nonvacuous.py`: build a drifted `Router(filters=live.filters, job_gates={..., HEAVY: live_gates - {"ci_config"}})` and assert `oracle.assert_must_run_gates_wired` raises `MustRunGateUnwiredError` matching `ci_config`.
  8. Run it and confirm it is **red today**: steps 3, 4 (for `ci_config` in `matched_groups`), 6 and 7 fail because the group does not exist. Record the red output (counts) in the Activity Log.
- **Files**: `tests/ci/test_ci_config_battery_routing.py` (new).
- **Parallel?**: No — first commit of the WP.
- **Notes**: Do not hand-encode any glob in the test as a path-group map; the paths are probes, the answer always comes from `select_gates` parsing the live YAML (the #2476 hazard). Keep each test function ≤ 15 complexity; no `# noqa`.

### Subtask T031 – Add `ci_config` to the filter block, output fold and battery `if:`

- **Purpose**: Implement amendment A1 in the two CI path routing authorities, in lockstep (C-003).
- **Steps**:
  1. In the `changes` job dorny `filters:` block, insert after the `architectural:` group and before `any_src:` (keep the probe last):

     ```yaml
            # CI-configuration group (Mission ci-runtime-stabilisation, FR-007; contract
            # amendment kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/
            # router-two-authority-amendment.md A1). NON-src (not in the unmatched loop);
            # gates ONLY the architectural battery, whose gates guard exactly these files.
            # Overlaps the `ci` group by design: `ci` keeps gating no router job (#4386).
            ci_config:
              - '.github/workflows/**'
              - '.github/actions/**'
              - 'scripts/ci/**'
              - 'pytest.ini'
              - 'pyproject.toml'
              - 'Makefile'
              - '.github/ci-module-registry.yml'
              - '.github/ci-shard-timings.json'
     ```
  2. In `changes.outputs`, add next to `architectural:` (same fold shape, with a one-line comment):
     `ci_config: ${{ (inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || steps.filter.outputs.ci_config }}`
     (`test_changes_outputs_cover_every_routing_group` requires the outputs to equal the parsed path-group set; `test_changes_outputs_never_force_run_all_on_push` forbids any `github.event_name == 'push'` term.)
  3. Do **not** add `steps.filter.outputs.ci_config` to the `unmatched` loop (contract Invariant 2; `test_unmatched_union_covers_every_src_backed_group`).
  4. In `architectural-heavy.if`, add `needs.changes.outputs.ci_config == 'true' ||` inside the parenthesised OR (put it right before `needs.changes.outputs.architectural == 'true'`). The outer `&& needs.prose-scan.outputs.prose_only != 'true'` stays exactly as it is.
  5. Update the job's banner comment ("HEAVY architectural battery …") to name the `ci_config` group, and add one line to the file header comment pointing at `kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md`.
  6. Re-run T030's file: steps 3–7 now pass.
- **Files**: `.github/workflows/ci-router.yml`.
- **Parallel?**: No (same file as T032's golden evaluation).
- **Notes**: Every glob must match a tracked file (`test_every_restored_filter_glob_is_live` in `tests/architectural/test_workflow_coherence.py`) — verified tracked today: `.github/actions/warmup/action.yml`, `pytest.ini`, `pyproject.toml`, `Makefile`, the registry and the timings. `ci_config` is consumed by a job `if:`, so `_DELIBERATELY_UNGATED_FILTER_GROUPS` does **not** change. C-002: workflow YAML, `pytest.ini`, `pyproject.toml` and `Makefile` are never prose-only; a docstring-only `scripts/ci/*.py` edit is down-routed exactly like a `src/**` one, which is safe because the raw-prose gates live in always-on lanes.

### Subtask T032 – Oracle constant, `test_ci_module_wiring.py` pins and golden context

- **Purpose**: Move every same-commit companion with the router edit so the oracle stays an exact-equality assertion and the golden `if:` evaluator models the new key.
- **Steps**:
  1. `tests/architectural/_ci_integrity_oracle.py`: `HEAVY_BATTERY_NON_SRC_GROUPS: frozenset[str] = frozenset({"architectural", "ci_config"})`. Rewrite the comment above it: `architectural` — tests/architectural has no module row; `ci_config` — the CI configuration the battery's gates guard (FR-007, contract amendment A1); `ci` still deliberately gates no router job (#4386). Keep `HEAVY_BATTERY_GATE` unchanged (WP12 owns the battery family).
  2. `tests/ci/test_ci_module_wiring.py`:
     - Docstring: replace the false sentence "The architectural battery's heavy job is gated on src-backed groups, so it would skip such a PR." with one stating that a CI-infrastructure-only PR now also runs the heavy battery through the sibling `ci_config` group, while `ci` itself still gates no router job.
     - `test_ci_infra_only_diffs_route_to_the_named_group`: expected `matched_groups == frozenset({_MODULE, "ci_config"})` (the `ci` group still routes; `ci_config` co-matches). Keep the "never trip the src catch-all" assertion. Update the docstring by one sentence.
     - `test_ci_infra_diff_alongside_src_change_keeps_the_src_routing`: expected `frozenset({"ci", "ci_config", "consolidation"})`. Leave the `tests-consolidation` assertion untouched — WP08 removes that job and repoints it.
     - `_BASE_CONTEXT_ALL_FALSE`: add `"changes.ci_config": False` (mandatory — without it all three golden tests fail with "golden test context does not model 'changes.ci_config'").
     - Add `test_golden_ci_config_only_pr_runs_the_heavy_battery_and_no_code_shard(router_workflow)`: context all-false, `changes.ci_config=True`, `prose-scan.prose_only=False` → `architectural-heavy.if` is `True`; `tests-consolidation`, `tests-status`, `tests-cli`, `tests-docs` evaluate `False`.
     - Add `test_golden_prose_only_ci_script_still_down_routes_the_battery(router_workflow)`: `changes.ci_config=True`, `prose-scan.prose_only=True` → `architectural-heavy.if` is `False` (C-002 subtraction holds for the new group). Do not add a `changes.ci` key: no job `if:` references it.
     - `test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all` stays **unchanged** (it is the #4386 pin; optionally add one docstring sentence naming `ci_config` as the battery-gating sibling).
  3. Run `tests/ci/test_ci_module_wiring.py` and `tests/ci/test_ci_config_battery_routing.py` green.
- **Files**: `tests/architectural/_ci_integrity_oracle.py`, `tests/ci/test_ci_module_wiring.py`.
- **Parallel?**: No.
- **Notes**: **Pinning inventory (tasks.md Global rules):** `_ci_integrity_oracle.py` carries no inventory rule today, so this WP runs `uv run --frozen python scripts/ci/derive_pinning_inventory.py --check` (and `--stdout` vs the base) **only** and does not regenerate `tests/release/pinning_rule_inventory.json`. The base inventory is green (#5523 closed by main's `e3794ded2d`, D-37), so `--check` must stay green. If `--check` shows a delta your diff caused, record the rule names in the Activity Log and raise it with the orchestrator rather than regenerating. Neither edited file is in `[tool.ruff.format].exclude`; run `uv run --frozen ruff format` on them freely.

### Subtask T033 – Confirm the unchanged pins stay green without a `gate_selection.py` edit

- **Purpose**: Prove C-003 (no parallel encoding, no authority edit) and C-008 (unmatched src still runs everything) hold after the change.
- **Steps**:
  1. Confirm `git diff --stat` shows no change to `scripts/ci/gate_selection.py`, `.github/ci-module-registry.yml`, `tests/release/ci_retirement_scrub.json`.
  2. Run the specific architectural gate files (never the whole directory):
     `tests/architectural/test_gate_selection_authority.py`, `test_ci_quality_path_filters.py`, `test_ci_router_transcription_guards.py`, `test_ci_integrity_oracle_nonvacuous.py`, `test_workflow_coherence.py`, `test_local_gate_parity.py`, `test_dual_mode_contract.py`, `test_no_duplicate_suite_execution.py`.
  3. Confirm specifically: `test_unmapped_src_change_forces_run_all_fail_closed` (C-008), `test_ci_router_docs_only_selects_zero_code_shards`, `test_select_modules_selects_the_ci_module_on_ci_infra_change`, `test_enumerated_must_run_gates_are_all_wired` (it asserts `job_gates[HEAVY] == src_backed | HEAVY_BATTERY_NON_SRC_GROUPS` and `routing_groups - src_backed >= HEAVY_BATTERY_NON_SRC_GROUPS`).
  4. Optional: `test_non_vacuity_floor` may gain `"ci_config"` in the non-src floor — **not** required, and that file is owned by WP12; leave it.
  5. Record the commands and pass counts in the Activity Log.
- **Files**: none edited.
- **Parallel?**: Yes, once T031/T032 are committed.
- **Notes**: If `test_workflow_coherence.py::test_every_restored_filter_glob_is_live` fails, a glob is mistyped — fix the glob, never the guard.

## Test Strategy

Red-first (commit 1): `tests/ci/test_ci_config_battery_routing.py` — red today on every `ci_config` assertion.

Local validation (all via `uv run --frozen`):

```bash
uv run --frozen pytest tests/ci/test_ci_config_battery_routing.py tests/ci/test_ci_module_wiring.py tests/ci/test_fork_guard.py tests/ci/test_prose_only.py -q
uv run --frozen pytest tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_ci_integrity_oracle_nonvacuous.py tests/architectural/test_workflow_coherence.py tests/architectural/test_local_gate_parity.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_no_duplicate_suite_execution.py -q
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check
uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/ci/test_ci_config_battery_routing.py tests/ci/test_ci_module_wiring.py tests/architectural/_ci_integrity_oracle.py
uv run --frozen ruff format --check tests/ci/test_ci_config_battery_routing.py tests/ci/test_ci_module_wiring.py tests/architectural/_ci_integrity_oracle.py
uv run --frozen mypy --strict tests/ci/test_ci_config_battery_routing.py
```

Never run `pytest tests/architectural` as a whole or `make test-full` (C-009). The PR's own CI is the real evidence: after this WP lands, the Mission PR runs `architectural-heavy` on every CI-config commit — note the first such run ID in the Activity Log (SC-006).

## Risks & Mitigations

- **Golden evaluator red on an unmodelled key** — add `"changes.ci_config": False` in the same commit as the `if:` change.
- **Battery now fires on every workflow/pyproject PR (runner minutes)** — intended (US-4). `uv.lock`, `tests/conftest.py` and `.github/ci-foreign-coverage-baseline.json` are deliberately excluded (D-09); do not add them.
- **Accidentally widening `ci`** — breaks `test_scrub_carries_the_ci_group_verbatim` and the #4386 pin; touch only the new group.
- **Lane conflict on `ci-router.yml`** — WP08, WP09, WP10, WP12 and WP18 edit the same file in sequence after this WP; keep your diff confined to the filter block, the one output line, the battery `if:` and comments.
- **Pinning inventory drift** — `--check` only here (no rule lives in your edited files); never hand-merge (D-25).

## Review Guidance

- `ci_config` globs equal D-09 / contract A1 exactly; group absent from the `unmatched` loop; output fold identical in shape to `architectural`.
- `architectural-heavy.if` gained exactly one OR term; prose-only AND unchanged.
- `HEAVY_BATTERY_NON_SRC_GROUPS == {"architectural", "ci_config"}`; comment updated.
- `scripts/ci/gate_selection.py`, the registry, the scrub file and the `ci` group are untouched.
- The red-first file was committed before the router edit and its red was recorded.
- `test_ci_group_gates_no_router_job_and_stays_out_of_the_catch_all` is unchanged and green.
- Pinning inventory not regenerated; `--check` stays green (base inventory fresh since #5523 closed, D-37); mypy/ruff clean on the new test file.
- Definition of Done: FR-007 (battery selected for CI-config diffs), C-003 (no authority edit, contract amendment referenced), C-008 (unmatched src still run-all), SC-006 (first PR run ID recorded).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
