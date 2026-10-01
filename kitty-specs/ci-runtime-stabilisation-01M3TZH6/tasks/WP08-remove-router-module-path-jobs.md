---
work_package_id: WP08
title: Remove the duplicate router module-path jobs
dependencies:
- WP07
requirement_refs:
- FR-008
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T034
- T035
- T036
- T037
phase: Phase 4 - CI path routing and duplicate removal
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/architectural/test_dual_mode_contract.py
- tests/architectural/test_local_gate_parity.py
- tests/architectural/test_ci_collection_completeness.py
- scripts/verify_shard_3115.sh
- tests/architectural/test_gate_selection_authority.py
- tests/ci/test_ci_module_wiring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Remove the duplicate router module-path jobs

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

FR-008: the legacy router jobs `tests (consolidation)`, `tests (status)` and `tests (cli)` (job keys `tests-consolidation`, `tests-status`, `tests-cli`) re-run, on every PR touching those `src/` groups, test trees that the `consolidation`, `status` and `cli` module rows in `ci-modules.yml` already run. Measured per-PR overlap (research R2 F6): 1,460, 1,311 and 889 node-ids. Delete them so those tests run once, in their module rows.

Done means:

1. The three jobs, their `router-gate.needs` entries and their `AUTHORIZED_PER_CHANGE_SUITE_JOBS` ledger rows are gone, in one commit (the needs-invariant and the stale-ledger-row check make a partial edit red).
2. A new structural guard fails if any `ci-router.yml` job runs a positional test **directory** that a module-registry row already owns — red today, green after the deletion, and it would catch the same duplicate re-added under a new name.
3. Every test that asserted `tests-consolidation` is repointed to the battery/group facts that still hold.
4. The two stress tests only these jobs ran are verified to be collected by the nightly `stress` lane; the seven performance tests are verified to be homed by the nightly `performance` lane (they were skipped in the router anyway). The verification is recorded.
5. `router gate` (the required check) keeps its name and its classify-all invariant.

## Context & Constraints

- Charter: `.kittify/charter/charter.md`; `NO_FULL_HEAVY_SUITES_IN_MISSION` (C-009).
- Mission docs: `spec.md` (FR-008, C-001, C-005), `plan.md` (IC-06), `research.md` decision log **D-11, D-20, D-25, D-30, D-33** (govern) and R2 "FR-008" for detail; `contracts/router-two-authority-amendment.md` A3.
- **Depends on WP07** (same file; `ci_config` already present, which shifts every line below the filter block by ~12 — anchor by job name).
- Required checks are `router gate`, `CI Modules gate`, `Clean install verification` (ADR `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md`); the three jobs are not required checks themselves.
- `pytest.ini`'s `stress` marker doc declares the stress home as the dedicated nightly lane; the router running stress tests per-PR (no `-m`) was incidental (R2 rationale). Do **not** add `stress` to the module rows (C-005).
- Lane discipline: `uv run --frozen …`; never `git stash`.

### Current-state anchors (verified 2026-10-01; WP07 adds ~12 lines above these)

| Surface | Anchor | Today |
|---|---|---|
| `ci-router.yml` | banner comment `# Code shards (group -> job, authority #2). Representative per-group shards; …` (≈ 608-611) | introduces the three jobs |
| `ci-router.yml` | jobs `tests-consolidation` (≈ 612), `tests-status` (≈ 627), `tests-cli` (≈ 642) | each `needs: [changes, prose-scan]`, `if: ${{ needs.changes.outputs.<group> == 'true' && needs.prose-scan.outputs.prose_only != 'true' }}`, `uv run --frozen pytest tests/<dir> -q` (no `-m`, so stress tests run; performance tests are skipped by `tests/conftest.py` without `SPEC_KITTY_RUN_PERFORMANCE=1`) |
| `ci-router.yml` | `router-gate.needs` list entries `tests-consolidation`, `tests-status`, `tests-cli` | 3 of 19 entries |
| `test_dual_mode_contract.py` | `test_router_gate_step_wiring_and_needs_invariant_are_pinned` (≈ 269) | asserts `needs == every non-gate top-level job` — deleting a job without its needs entry (or vice versa) reds it |
| `test_no_duplicate_suite_execution.py` | `AUTHORIZED_PER_CHANGE_SUITE_JOBS` rows `("ci-router.yml", "tests-consolidation"|"tests-status"|"tests-cli")` (≈ 258-260) | `test_every_authorized_ledger_row_still_names_a_live_suite_job` (≈ 939) reds on a stale row |
| `test_local_gate_parity.py` | `test_single_module_src_diff_local_parity_matches_ci` (≈ 135) | `assert "tests-consolidation" in local_selection.selected_code_shards` |
| `test_gate_selection_authority.py` (owned; WP12 edits it later on the same lane) | `test_src_group_diff_selects_its_shard_and_heavy_arch` (≈ 82); `test_authority_parses_the_yaml_not_a_hardcoded_map` (≈ 135) | both assert `tests-consolidation` in `selected_code_shards` |
| `tests/ci/test_ci_module_wiring.py` (owned; WP07 before you and WP12 after you edit it on the same lane) | `test_ci_infra_diff_alongside_src_change_keeps_the_src_routing` (≈ 172); `_CODE_SHARD_JOB_NAMES` (≈ 334); golden tests (`jobs["tests-…"]` at ≈ 391-393, 424-426, 442-444, plus WP07's new `ci_config` golden) | hard-coded job names |
| `test_ci_collection_completeness.py` | parametrize case `("needs.fast-tests-cli.result == 'success'", True)` (≈ 365) | retired job name in a synthetic expression (file is in `[tool.ruff.format].exclude` — edit, do not reformat) |
| `scripts/verify_shard_3115.sh` | `run_shard "cli (fast-tests-cli)"` (≈ 450) | historical evidence script quoting retired `ci-quality.yml` jobs |

**Same-commit companions:** `tests/architectural/test_gate_selection_authority.py` and `tests/ci/test_ci_module_wiring.py` are in this WP's `owned_files` (WP07 and WP12 also edit them, sequenced on the same router lane WP07 → WP08 → … → WP12, so there is no parallel-lane conflict). They must change in the same commit as the deletion, or they go red. The only out-of-map companion is `tests/release/pinning_rule_inventory.json` — regenerate it (D-20/D-25; one-line rationale in the commit body).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T034 – Red-first: no router job may re-run a module-owned test directory

- **Purpose**: A generic structural guard that is red on today's router and stays a guard against re-adding the duplicate under a different job name until WP15's node-level FR-010 live check subsumes it (FR-008 "no-op passable: no"; WP15 T062 removes this guard — see Notes).
- **Steps**:
  1. In `tests/architectural/test_no_duplicate_suite_execution.py` add a helper and a test (near the ledger tests):
     ```python
     def module_owned_test_dirs(registry_path: Path) -> dict[str, tuple[str, ...]]:
         """module -> its test dirs: registry ``test_dirs`` when declared, else ``tests/<module>``."""
     def router_dirs_owned_by_a_module(router_path: Path, registry_path: Path) -> dict[str, list[tuple[str, str]]]:
         """ci-router.yml job -> [(positional dir, owning module)] for directory positionals only."""
     def test_router_runs_no_module_owned_test_tree() -> None: ...
     ```
  2. Resolution rule for a row: explicit `test_dirs` when present, else `tests/<module>` — the rule the `module-tests.yml` "resolve the test selection" step documents. If `scripts/ci/shard_select.py` (WP01) already exists in your base and exposes this resolution publicly, import it instead (C-010: one resolver); otherwise read the registry with `yaml.safe_load` and do not invent a third rule (in particular, not `gate_selection._canonical_test_mirror`, which differs for `next`).
  3. Gates come from `gc.parse_workflow(gc.WORKFLOWS_DIR / "ci-router.yml")`. Consider only **directory** positionals: skip entries ending in `.py` or containing `::` (file/node selections are FR-010's domain — WP10 adds a node-level corpus job that this guard must not flag), and skip gates with no positional paths (marker-only gates).
  4. Overlap: positional `P` and row dir `D` overlap when `P == D`, `P` is under `D`, or `D` is under `P` (a router job running `tests/specify_cli` would swallow the `specify_cli_runtime` row).
  5. Assertion message lists `job -> (dir, module)` and says: "the module row is the per-PR executor; delete the router job (FR-008)".
  6. Positive control in the same file: `test_router_module_tree_guard_flags_a_planted_job(tmp_path)` — copy `ci-router.yml` into `tmp_path`, append a job `tests-planted` running `uv run --frozen pytest tests/kernel -q`, and assert the helper reports it (use a small fixture workflow string if splicing is simpler; follow the existing `write_triggered_duplicate` pattern).
  7. Run: red today with exactly `tests-consolidation -> tests/consolidation (consolidation)`, `tests-status -> tests/status (status)`, `tests-cli -> tests/cli (cli)`. Record the output in the Activity Log.
- **Files**: `tests/architectural/test_no_duplicate_suite_execution.py`.
- **Parallel?**: No — first commit.
- **Notes**: Keep helpers pure and ≤ 15 complexity. This file is pinned (D-20): regenerate the pinning inventory after editing (T036 step 5).
- **Lifetime — a deliberate structural pre-check, subsumed by WP15.** This directory-level guard exists so FR-008 is red-first and guarded *now*, before the node-level FR-010 live check lands. WP15 owns the same file after you (dependency-ordered: WP15 depends on WP12, which depends on WP08) and its T062 removes this guard, its helpers and its positive control (or folds them into `_live_uniqueness.py`). Keep it self-contained (the three helpers + two tests, one block, a comment naming "WP15 T062 subsumes this") so that removal is a clean diff, and do not build other tests on its helpers.

### Subtask T035 – Delete the jobs, `needs` entries, ledger rows; fix stale prose

- **Purpose**: Remove the duplicates and every same-commit companion in one atomic commit.
- **Steps**:
  1. `ci-router.yml`: delete the `# Code shards (group -> job, authority #2) …` banner and the three jobs `tests-consolidation`, `tests-status`, `tests-cli` in full.
  2. `ci-router.yml` `router-gate.needs`: remove `tests-consolidation`, `tests-status`, `tests-cli`. Leave every other entry in its order.
  3. Optionally add a two-line comment above the remaining non-code shards noting that per-group code shards were removed by FR-008 because the `ci-modules.yml` module rows are their sole per-PR executor.
  4. `test_no_duplicate_suite_execution.py`: delete the three `AUTHORIZED_PER_CHANGE_SUITE_JOBS` rows. Do **not** touch `("ci-router.yml", "tests-corpus")` (WP09) or `architectural-heavy` (WP12).
  5. `test_ci_collection_completeness.py` (format-excluded — hand-edit only): change the synthetic case `"needs.fast-tests-cli.result == 'success'"` to a live job name, e.g. `"needs.tests-e2e.result == 'success'"`; the semantics (needs-result conjunct is permissive under push) are unchanged.
  6. `scripts/verify_shard_3115.sh`: the `run_shard "cli (fast-tests-cli)"` label quotes a retired `ci-quality.yml` job and the companion `verify_shard_3115.recorded-output.md` records it verbatim. Do **not** rename the label (the recorded output would no longer match); add a one-line comment above the call: `# fast-tests-cli (ci-quality.yml) and the later router tests-cli job are both retired; the cli module row is the live executor (FR-008).`
  7. Run T034's test → green.
- **Files**: `.github/workflows/ci-router.yml`, `tests/architectural/test_no_duplicate_suite_execution.py`, `tests/architectural/test_ci_collection_completeness.py`, `scripts/verify_shard_3115.sh`.
- **Parallel?**: No.
- **Notes**: `test_dual_mode_contract.py::test_router_gate_step_wiring_and_needs_invariant_are_pinned` must stay green with no edit (its synthetic `classify({"tests-cli": …})` inputs at ≈ 333-368 are classifier fixtures, not live job references — leave them). Recommended campsite (comment-only, out-of-map, one-line rationale): `tests/cli/test_lazy_command_module_imports.py:36`, `tests/cli/test_register_commands_lazy_import_shape.py:9-24`, `tests/performance/test_cli_startup_agent_commands_freshness.py:28` say "ci-router.yml's hardcoded tests-cli job"; reword to "the `cli` module row". If you skip it, record it in the Activity Log for WP19.

### Subtask T036 – Repoint tests that asserted `tests-consolidation`; local-gate parity

- **Purpose**: Keep every remaining assertion true and non-vacuous now that `router.code_shard_jobs == {"architectural-heavy"}`.
- **Steps**:
  1. `tests/architectural/test_local_gate_parity.py::test_single_module_src_diff_local_parity_matches_ci`: replace `"tests-consolidation" in local_selection.selected_code_shards` with `"architectural-heavy" in local_selection.selected_code_shards` **and** `local_selection.matched_groups == frozenset({"consolidation"})` (the group fact is what still distinguishes a scoped diff).
  2. Out-of-map `tests/architectural/test_gate_selection_authority.py`:
     - `test_src_group_diff_selects_its_shard_and_heavy_arch`: drop the `tests-consolidation` line, keep `matched_groups` and `architectural-heavy`; rename to `test_src_group_diff_selects_its_group_and_heavy_arch`.
     - `test_authority_parses_the_yaml_not_a_hardcoded_map`: baseline becomes `assert "consolidation" in baseline.matched_groups and not baseline.unmatched_src` (run-all re-selects the battery, so `selected_code_shards` can no longer tell the two states apart; the post-mutation asserts already carry the proof).
  3. Out-of-map `tests/ci/test_ci_module_wiring.py`:
     - `test_ci_infra_diff_alongside_src_change_keeps_the_src_routing`: replace the `tests-consolidation` assertion with `"architectural-heavy" in selection.selected_code_shards`.
     - Replace `_CODE_SHARD_JOB_NAMES = (...)` with iteration over `sorted(router.code_shard_jobs)` inside the prose-only golden (add the `router` fixture to its signature if missing) plus `assert router.code_shard_jobs, "non-vacuity: at least the battery is a code shard"`.
     - Delete the `jobs["tests-consolidation"|"tests-status"|"tests-cli"]` evaluations in the architectural-only golden, the non-prose golden and WP07's `ci_config` golden. Do not touch the `tests-corpus` line (WP09).
  4. Run the touched files green.
  5. Pinning inventory: `uv run --frozen python scripts/ci/derive_pinning_inventory.py --check`; if stale, regenerate (`… derive_pinning_inventory.py`) and commit `tests/release/pinning_rule_inventory.json` with "out-of-map companion: regenerated, never hand-merged". Then `uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q`.
- **Files**: `tests/architectural/test_local_gate_parity.py`, `tests/architectural/test_gate_selection_authority.py`, `tests/ci/test_ci_module_wiring.py`; out-of-map `tests/release/pinning_rule_inventory.json`.
- **Parallel?**: No (same commit as T035 or the immediately following one; the branch must never be red between commits on the lane tip you hand to review).
- **Notes**: `test_unmapped_src_change_forces_run_all_fail_closed` and `test_full_mode_runs_everything` assert `selected_code_shards == router.code_shard_jobs` — they stay true and non-empty (the battery). `test_ci_integrity_oracle_nonvacuous.py`'s synthetic `"tests-cli"` routers need no change.

### Subtask T037 – Verify the stress and performance homes; record it

- **Purpose**: Prove FR-008's "stress-marked tests they alone ran are kept in a lane that executes them" with collect-only evidence (no heavy run).
- **Steps**:
  1. `uv run --frozen pytest --collect-only -q -p no:cacheprovider -m stress tests/cli tests/status tests/consolidation` → expected exactly 2: `tests/status/test_emit_durability.py::test_two_concurrent_distinct_verdicts_are_both_durable` and `tests/status/test_journal_lock_unification.py::test_co1_locked_and_rehomed_writers_never_lose_a_row` (verified at prompt time: `2/3698 tests collected`).
  2. `… -m performance tests/cli tests/status tests/consolidation` → 7 (1 cli, 1 consolidation, 5 status); `-m timing` → 0; `-m windows_ci` → 3 in `tests/cli`, which the `cli` module row already selects (it excludes only performance and stress), so they lose nothing.
  3. The nightly `stress` job in `.github/workflows/ci-nightly.yml` runs `uv run --frozen pytest -m "stress and not windows_ci" -q …`; confirm both node-ids appear in `uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "stress and not windows_ci" | grep -E 'test_two_concurrent_distinct_verdicts|test_co1_locked_and_rehomed'` (verified: both present, 33 stress tests total). The nightly `performance` job (`pytest -m performance` with `SPEC_KITTY_RUN_PERFORMANCE=1`) collects all 7 performance tests; in the router they were skipped by `tests/conftest.py` (`apply_performance_skip`).
  4. Record the four counts and the two nightly job names in the Activity Log and in the PR body ("2 stress tests move from per-PR on status-path PRs to nightly; 7 performance tests were never executed per-PR"). The Mission evidence file is assembled at Mission level — do not write under `kitty-specs/` from this code_change WP.
- **Files**: none edited.
- **Parallel?**: Yes (independent of T034–T036).
- **Notes**: If either stress node-id is missing from the nightly collect, stop: FR-008 then needs an explicit home before deletion.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_no_duplicate_suite_execution.py -q          # red first (T034), then green
uv run --frozen pytest tests/architectural/test_dual_mode_contract.py tests/architectural/test_local_gate_parity.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_collection_completeness.py tests/architectural/test_ci_integrity_oracle_nonvacuous.py tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_workflow_coherence.py -q
uv run --frozen pytest tests/ci/test_ci_module_wiring.py tests/ci/test_ci_config_battery_routing.py tests/ci/test_fork_guard.py -q
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check && uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_local_gate_parity.py tests/architectural/test_gate_selection_authority.py tests/ci/test_ci_module_wiring.py
uv run --frozen ruff format --check tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_local_gate_parity.py tests/architectural/test_gate_selection_authority.py tests/ci/test_ci_module_wiring.py
bash -n scripts/verify_shard_3115.sh
```

`test_ci_collection_completeness.py` is in `[tool.ruff.format].exclude`: do not run `ruff format` on it (if you ever do, you must drop it from the exclude in the same commit, and `pyproject.toml` is not yours). Never run `pytest tests/architectural` whole or `make test-full`.

## Risks & Mitigations

- **Partial edit reds the needs invariant / stale-ledger check** — delete job, needs entry and ledger row in one commit.
- **Shared companion files** — `test_gate_selection_authority.py` and `test_ci_module_wiring.py` are owned by this WP and also by WP07/WP12 on the same sequenced router lane; edit them in the same commit as the deletion and rebase on WP07's merged state first.
- **Lost stress coverage** — T037 proves the nightly home before deletion.
- **Guard false positives on WP10's node-level corpus job** — directory positionals only.
- **Pinning inventory line drift** — regenerate, never hand-merge.

## Review Guidance

- The three jobs, three needs entries and three ledger rows are gone; no other router job changed.
- `test_router_runs_no_module_owned_test_tree` was committed red first (recorded output names exactly the three jobs) and has a planted-job positive control.
- No assertion was weakened to "pass": each repointed assertion still distinguishes a scoped consolidation diff (`matched_groups`) from run-all.
- `router gate` name and `test_router_gate_step_wiring_and_needs_invariant_are_pinned` unchanged and green.
- T037 counts recorded (2 stress / 7 performance / 0 timing / 3 windows_ci) with the nightly job names.
- Pinning inventory fresh; out-of-map edits carry rationale lines.
- The T034 guard is one self-contained block marked "WP15 T062 subsumes this"; no other test depends on its helpers.
- Definition of Done: FR-008 satisfied; C-001 holds (no test lost a per-change home except the 2 stress tests, which move to their documented nightly home).

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
