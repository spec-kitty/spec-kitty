---
work_package_id: WP10
title: Blocking home for the orphaned corpus tests
dependencies:
- WP09
requirement_refs:
- FR-009
- C-001
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
phase: Phase 4 - CI path routing and duplicate removal
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_corpus_blocking_home.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/packs.yml
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/ci/test_corpus_blocking_home.py
- tests/architectural/test_workflow_coherence.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Blocking home for the orphaned corpus tests

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

WP09 made the corpus lane advisory. The "35" (the D-13 label used in the plan and this WP's title) is now **40** corpus-marked node-ids with **no other blocking per-PR home** (R2 F12; operator DM 01M3V1F4H388T9Q01Y4PMA77BS, D-13). D-22 gives them one: a small required router job `tests (corpus-blocking)`, gated on the router `corpus` path group, and the Packs advisory corpus run deselects them so they run exactly once.

**Exact selection — corrected against live code (read this):** D-22 says "run `-m "corpus and not windows_ci"` over exactly the three files". Verified by collect-only on 2026-10-01 post-rebase (base `bc826fcbcb`, D-37), that selects **403** node-ids (398 at planning), not 40:

| File | `-m "corpus and not windows_ci"` | of which have no other blocking per-PR home |
|---|---|---|
| `tests/contract/test_example_round_trip.py` | 34 (29 before PR #5503 added five `_module_relocations` tests) | 34 (`tests/contract` is out-of-matrix) |
| `tests/integration/test_mission_review_contract_gate.py` | 5 | 5 (`tests/integration` is out-of-matrix) |
| `tests/doctrine/test_shipped_profiles.py` (path verified: `tests/doctrine/`, not `tests/charter/**`) | 364 | **1** — `TestShippedProfilesPerformance::test_shipped_profile_load_time` (`performance`-marked); the other 363 are already run by the `charter` module row (`test_dirs: [tests/charter, tests/doctrine]`, marker `not performance and not stress`) |

So the job must select the two whole files plus the single class node-id `tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance` — **40 node-ids** on `bc826fcbcb` (verified 2026-10-01 post-rebase: `39 passed, 1 skipped in 1.74s` locally). At planning it was 35 / `24 passed, 11 skipped`: PR #5503 added `tests/contract/_module_relocations.py` plus five tests to the round-trip file, so the ten contract blocks that skipped on not-yet-importable modules now run (D-37). Running the whole third file would re-create a 363-node duplicate with module `charter` that WP15's live uniqueness check (FR-010) would flag. Honest caveat to record: the `TestShippedProfilesPerformance` node-id is a `performance` test that `tests/conftest.py` skips unless `SPEC_KITTY_RUN_PERFORMANCE=1`; its executing home is the nightly `performance` job. Keeping it in the blocking job's selection preserves the D-13 "selected by exactly one required job, no advisory job" invariant at no cost.

Done means:

1. Router job `tests-corpus-blocking` (`name: tests (corpus-blocking)`) runs exactly the 40, gated on `needs.changes.outputs.corpus == 'true'`, is in `router-gate.needs` and has a ledger row.
2. The Packs advisory corpus run deselects exactly those three selections (40 node-ids).
3. `corpus` is a gated group again: the transitional entry WP09 put in `_DELIBERATELY_UNGATED_FILTER_GROUPS` is removed.
4. A red-first test proves the 40 are selected by exactly one required job and by no advisory job.

## Context & Constraints

- Mission docs: `spec.md` (FR-009, C-001 — the corpus downgrade is the single scoped exception), `plan.md` (IC-07), `research.md` **D-13, D-22 (amends D-12), D-20, D-25**, R2 F12 and FR-009; `contracts/router-two-authority-amendment.md` A3.
- **Depends on WP09** (Packs owns corpus, router `tests-corpus` deleted, `corpus` transitionally ungated).
- Required check is `router gate`; adding a job to its `needs` makes the job effectively blocking.
- The gate model (`tests/architectural/_gate_coverage.py`) already understands node-id positionals: `_extract_paths` keeps any `tests/…` token (quotes stripped), and `path_matches` treats an entry containing `::` as a node-id prefix; `--deselect` values land in `Gate.ignores`. No model change needed.
- Lane discipline: `uv run --frozen …`; never `git stash`.

### Current-state anchors (as left by WP09; anchor by name)

| Surface | Anchor | Expected state at WP start |
|---|---|---|
| `ci-router.yml` | `changes.outputs.corpus` + filter group `corpus:` | present, unchanged |
| `ci-router.yml` | "Non-code shards" banner; jobs `tests-docs`, `tests-e2e`; `router-gate.needs` | `tests-corpus` already gone |
| `packs.yml` `built-in-corpus-suite` | command `uv run --frozen pytest -m "corpus and not windows_ci" -n 4 --dist loadfile --deselect tests/architectural/test_pack_manifest_no_author_edit.py --cov=charter.offering --cov-report=term-missing` | advisory |
| `tests/architectural/test_workflow_coherence.py` | `_DELIBERATELY_UNGATED_FILTER_GROUPS` | contains transitional `"corpus"` |
| `test_no_duplicate_suite_execution.py` | `AUTHORIZED_PER_CHANGE_SUITE_JOBS` | no corpus row for the router |

**Companions:** `tests/architectural/test_workflow_coherence.py` (owned by this WP; remove the transitional `corpus` entry and its bullet) and the out-of-map `tests/release/pinning_rule_inventory.json` (regenerate after editing `test_no_duplicate_suite_execution.py` / `test_workflow_coherence.py`).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T043 – Red-first: the 40 are selected by exactly one required job and no advisory job

- **Purpose**: Pin D-13 from real collection, not a hand count, before any workflow edit.
- **Steps**:
  1. Create `tests/ci/test_corpus_blocking_home.py` (`pytestmark = pytest.mark.fast` for the pure checks; the subprocess collect test may be marked like other collect-based tests in `tests/ci` — follow sibling conventions). Import `tests.architectural._gate_coverage as gc` (cross-tree precedent: `tests/ci/test_interpreter_matrix_env_pinning.py`).
  2. Module constants: `_BLOCKING_SELECTION = ("tests/contract/test_example_round_trip.py", "tests/integration/test_mission_review_contract_gate.py", "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance")`, `_MARKER = "corpus and not windows_ci"`, `_EXPECTED_COUNT = 40`.
  3. A module-scoped fixture `expected_nodeids` = `gc.collect_job_nodeids(gc.Gate(workflow="probe", job="probe", shard=None, paths=list(_BLOCKING_SELECTION), marker_expr=_MARKER))` (real scoped `--collect-only`, ~2 s). Assert `len == _EXPECTED_COUNT` (non-vacuity and drift alarm: a new corpus test in these files must be a conscious change here).
  4. `test_exactly_one_required_router_job_selects_the_orphans`: from `gc.parse_workflow(gc.WORKFLOWS_DIR / "ci-router.yml")`, the gates whose real scoped collection (`gc.collect_job_nodeids(gate)` restricted to `_BLOCKING_SELECTION` — build a probe `Gate` with the job's `ignores`/`marker_expr` and positional paths intersected with the selection) contains any expected node-id must be exactly `{"tests-corpus-blocking"}`, and that job's selection ⊇ the 40. The job must be in `router-gate.needs`.
  5. `test_no_advisory_job_selects_the_orphans`: for `packs.yml::built-in-corpus-suite`, a probe `Gate(paths=list(_BLOCKING_SELECTION), ignores=corpus_gate.ignores, marker_expr=corpus_gate.marker_expr)` collected for real must be **empty** (the deselects cover all three).
  6. `test_no_module_row_selects_the_orphans`: from `.github/ci-module-registry.yml`, no module row's resolved test dirs (explicit `test_dirs`, else `tests/<module>`) contain `tests/contract` or `tests/integration`; for the one `tests/doctrine` row (`charter`), the row marker `not performance and not stress` deselects `TestShippedProfilesPerformance` (assert the class carries `performance` via `-m performance` collect-only of that node).
  7. `test_corpus_group_is_gated_again`: `"corpus" not in test_workflow_coherence._DELIBERATELY_UNGATED_FILTER_GROUPS` and `load_router().job_gates["tests-corpus-blocking"] == frozenset({"corpus"})`.
  8. Run: red today (no router job selects them; Packs still selects them; transitional exemption present). Record the output.
- **Files**: `tests/ci/test_corpus_blocking_home.py` (new).
- **Parallel?**: No — first commit.
- **Notes**: Reuse `gc.collect_job_nodeids` (the established real-collection authority) — no second collector. Keep helpers ≤ 15 complexity, mypy-strict clean.

### Subtask T044 – Add the router job, `needs` entry, ledger row; re-gate `corpus`

- **Purpose**: Give the 40 a blocking per-PR home (D-13/D-22) on the corpus path family.
- **Steps**:
  1. In `ci-router.yml`, in the non-code shards section, add:
     ```yaml
       tests-corpus-blocking:
         name: tests (corpus-blocking)
         runs-on: ubuntu-24.04
         timeout-minutes: 10
         needs: [changes]
         if: ${{ needs.changes.outputs.corpus == 'true' }}
         steps:
           - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
             with:
               fetch-depth: 0
           - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
             with:
               python-version: '3.12'
           - run: |
               uv sync --frozen --all-extras
               # The 40 corpus-marked tests with no other blocking per-PR home (D-13/D-22):
               # Packs owns the corpus suite as ADVISORY (FR-009) and deselects exactly
               # these selections. The third entry is a single performance-marked class,
               # skipped per-PR by tests/conftest.py and executed by ci-nightly `performance`.
               uv run --frozen pytest -m "corpus and not windows_ci" \
                 tests/contract/test_example_round_trip.py \
                 tests/integration/test_mission_review_contract_gate.py \
                 "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance"
     ```
     Copy the checkout/setup-uv SHA pins from the neighbouring jobs (never type them fresh). Keep `fetch-depth: 0` as the retired corpus job had (conservative; the files read `kitty-specs/` contracts). No `-n` (40 tests, ~2 s); not on WP12's worker-policy list. Mirror the retired job: `needs: [changes]`, no `prose-scan` term.
  2. `router-gate.needs`: add `tests-corpus-blocking` (`test_router_gate_step_wiring_and_needs_invariant_are_pinned` requires needs == all non-gate jobs).
  3. `test_no_duplicate_suite_execution.py` ledger: `("ci-router.yml", "tests-corpus-blocking"): "Path-routed lane: the 40 corpus tests with no other blocking per-PR home (D-13/D-22); the advisory Packs corpus run deselects exactly these."`
  4. Out-of-map `tests/architectural/test_workflow_coherence.py`: remove `"corpus"` from `_DELIBERATELY_UNGATED_FILTER_GROUPS` and its TRANSITIONAL bullet (back to `{"any_src", "ci"}`).
  5. Regenerate the pinning inventory (`uv run --frozen python scripts/ci/derive_pinning_inventory.py`; `--check`; `tests/release/test_pinning_inventory_fresh.py`).
- **Files**: `.github/workflows/ci-router.yml`, `tests/architectural/test_no_duplicate_suite_execution.py`; out-of-map `tests/architectural/test_workflow_coherence.py`, `tests/release/pinning_rule_inventory.json`.
- **Parallel?**: No.
- **Notes**: WP08's `test_router_runs_no_module_owned_test_tree` only considers directory positionals, so the node-level `tests/doctrine/…::TestShippedProfilesPerformance` entry does not trip it (by design; it is disjoint from the `charter` row by marker). `gate_selection`: the job's gate is `{"corpus"}` (non-src) so it is not a code shard; `test_gate_selection_authority.py::test_corpus_only_diff_selects_zero_code_shards` stays green, and run-all (`unmatched`/`full`) selects it through the `corpus` output fold.

### Subtask T045 – Packs deselects the 40; verify the count by collect-only

- **Purpose**: No double execution (D-13) and an independently recorded count.
- **Steps**:
  1. `packs.yml` `built-in-corpus-suite` command: append
     `--deselect tests/contract/test_example_round_trip.py --deselect tests/integration/test_mission_review_contract_gate.py --deselect tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance`
     (file paths are valid node-id prefixes for `--deselect`; precedent: the router battery's `--deselect tests/architectural/…py`). Keep everything else in the command unchanged.
  2. Update the job comment: the 40 run blocking in router `tests (corpus-blocking)`.
  3. Verify and record (Activity Log + PR body):
     ```bash
     uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_example_round_trip.py tests/integration/test_mission_review_contract_gate.py "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance" | tail -1   # expect 40
     uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_example_round_trip.py tests/integration/test_mission_review_contract_gate.py tests/doctrine/test_shipped_profiles.py | tail -1   # 403 — why the class node-id is used
     uv run --frozen pytest --collect-only -q -p no:cacheprovider -m performance "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance" | tail -1   # 1 — nightly performance home
     uv run --frozen pytest -q -m "corpus and not windows_ci" tests/contract/test_example_round_trip.py tests/integration/test_mission_review_contract_gate.py "tests/doctrine/test_shipped_profiles.py::TestShippedProfilesPerformance"   # 39 passed, 1 skipped (the performance skip; since #5503 every contract block imports)
     ```
  4. `tests/ci/test_corpus_blocking_home.py` green.
- **Files**: `.github/workflows/packs.yml`.
- **Parallel?**: No.
- **Notes**: If the count is no longer 40 (a corpus test was added to these files), update `_EXPECTED_COUNT` consciously and say why in the Activity Log — never loosen the equality.

## Test Strategy

```bash
uv run --frozen pytest tests/ci/test_corpus_blocking_home.py tests/ci/test_corpus_select.py tests/ci/test_ci_module_wiring.py tests/ci/test_fork_guard.py -q
uv run --frozen pytest tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_workflow_coherence.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_ci_quality_path_filters.py -q
uv run --frozen python scripts/ci/derive_pinning_inventory.py --check && uv run --frozen pytest tests/release/test_pinning_inventory_fresh.py -q
make test-fast
uv run --frozen ruff check tests/ci/test_corpus_blocking_home.py tests/architectural/test_no_duplicate_suite_execution.py
uv run --frozen ruff format --check tests/ci/test_corpus_blocking_home.py tests/architectural/test_no_duplicate_suite_execution.py
uv run --frozen mypy --strict tests/ci/test_corpus_blocking_home.py
```

`test_workflow_coherence.py` is format-excluded: hand-edit only. Never run `tests/architectural` whole or `make test-full`.

## Risks & Mitigations

- **Whole-file selection of `test_shipped_profiles.py`** would duplicate 363 node-ids with module `charter` — use the class node-id; T043 step 6 pins disjointness.
- **Transitional exemption left behind** — T043 step 7 is red until it is removed.
- **New corpus test in one of the three files** silently changes the blocking set — `_EXPECTED_COUNT` equality alarms.
- **Job added outside `router-gate.needs`** — the dual-mode needs invariant catches it.
- **Pinning inventory drift** — regenerate, never hand-merge.

## Review Guidance

- Job selection is the two files + the `TestShippedProfilesPerformance` class node-id, marker `corpus and not windows_ci`, gated only on `corpus`, in `router-gate.needs`, with a ledger row.
- Packs deselects exactly the same three selections; nothing else in the Packs command changed.
- `corpus` removed from `_DELIBERATELY_UNGATED_FILTER_GROUPS`.
- Red-first test committed first; counts (40 / 403 / 1 / 39 passed + 1 skipped) recorded.
- Definition of Done: FR-009 (no double execution of the 40; corpus lane otherwise advisory), C-001 (the 40 keep a blocking per-PR home).

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
