---
work_package_id: WP11
title: 'Bridge parity split: P0 board-authority tests out of the oracle module'
dependencies: []
requirement_refs:
- C-002
- FR-017
- NFR-004
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T059
- T060
- T061
- T062
- T063
- T064
phase: Phase 3 - Parity remediation
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/runtime/test_next_board_authority.py
create_intent:
- tests/runtime/_next_mission_scaffold.py
- tests/runtime/test_next_board_authority.py
execution_mode: code_change
model: ''
owned_files:
- tests/runtime/test_bridge_parity.py
- tests/runtime/_next_mission_scaffold.py
- tests/runtime/test_next_board_authority.py
- tests/next/test_finalized_task_routing.py
- tests/runtime/fixtures/bridge/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Bridge parity split: P0 board-authority tests out of the oracle module

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`tests/runtime/test_bridge_parity.py` (1862 LOC) holds two unrelated things:

- the #2531 two-run parity oracle, whose module-scoped `ledger_results` fixture costs about 391 s;
- since 2026-09-25, the P0 board-authority acceptance tests for #4980/#4975.

Move the P0 tests, plus the two fail-closed direct-call tests, into a behaviour-named module that never touches the oracle. That leaves the oracle retirable in isolation later (#5116, after #2633). The oracle itself is **not** retired, relaxed or edited (C-002).

Done means:

1. `tests/runtime/test_next_board_authority.py` holds **15 functions / 16 collected nodes**:
   - the 13 P0 functions from L1409-1851 (`test_review_reject_redispatches_implement_coord_family` is parametrized ×2, giving 14 nodes);
   - `test_research_fail_closed_default_direct_call` (L1383) and `test_documentation_fail_closed_default_direct_call` (L1392).
   Its node-ID set, compared as `func[param]`, equals the planning-base set exactly (FR-017).
2. `test_board_authority_module_does_not_import_the_oracle` is GREEN. It was RED on base because the module holds fewer than 15 tests.
3. `tests/runtime/test_bridge_parity.py` keeps exactly **8** nodes: the 6 `ledger_results` consumers, `test_hollow_ledger_fails_coverage_floor` and `test_reason_normalizer_meta_test`. Their assertions, the fixture and the `_build_*` functions are unchanged. `tests/runtime/_bridge_oracle.py` is **not modified** (C-002).
4. The new module runs in under 60 s standalone. Debbie measured 48.49 s for the 16 nodes. **Record** the `--durations=0` figure (NFR-004); never assert it.
5. History is reviewable as **three separate commits**: verbatim move, `ruff format` of the new modules, then the rename to public names. There is also a red-first commit before them.

## Context & Constraints

- Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Read these first:
  - `spec.md` (FR-017, C-002, NFR-004, US3-AS3);
  - `plan.md` (the WP11 row: "separate move/format/rename commits");
  - `research.md` §F5;
  - `research/postplan-debbie.md` (LOW: "oracle keeps 8"; compare node IDs by `func[param]`; the private `_read_snapshot` import);
  - `research/postplan-priti.md` (MEDIUM, WP11: 3-commit mandate, ~1.6k diff lines);
  - `research/grounding-2631_2972.md` §N6.
- **Verified closure (planning base).**
  - No P0 or fail-closed test uses the `ledger_results` fixture (L1120-1144) or any `_bridge_oracle` symbol. `--setup-plan` confirms `ledger_results` is set up only for the 6 oracle nodes.
  - The P0 block's helper closure is:
    - `_init_git_repo` (L70), `_commit_all` (L80), `_seed_wp_lane` (L85), `_write_wp_task_files` (L105), `_add_wp_files` (L132), `_write_spec_md` (L140), `_provision_mission_type_activations` (L148);
    - `scaffold_software_dev` (L182), `advance_to_step` (L284);
    - the late golden-path imports (L321-326: `MissionTopology as _MissionTopology`, `_create_mission`, `_init_git_repo`, `_materialize_coord_worktree` from `tests.integration.test_placement_partition_golden_path`);
    - `scaffold_coord_software_dev` (L329), `_reject_wp_on_status_surface` (L370);
    - `_assert_reason_has_runnable_recovery_command` (L1853, used only by P0).
  - Stdlib or first-party names the P0 block uses: `re`, `shlex`, `subprocess`, `DecisionKind`, and `write_single_lane_manifest` (via `_write_wp_task_files`).
- **Stays in the oracle module**: `scaffold_research`, `scaffold_documentation`, `_write_block_retrospective_config`, all `_build_*`, `FixtureSpec`, `FixtureRun`, `drive_*`, `copytree_snapshot`, `_drive`, `ledger_results` and the 8 oracle tests. The oracle re-imports the moved helpers from the scaffold, so there are no duplicates.
- **Format-exclude.** `tests/runtime/test_bridge_parity.py` (pyproject L1909) and `tests/runtime/_bridge_oracle.py` (L1902) are excluded.
  - Do **not** `ruff format` `test_bridge_parity.py`. WP13 formats files this mission rewrote and removes their lines.
  - Keep the residual module format-dirty, which it will stay after a pure deletion plus an import change.
  - The two **new** modules are not excluded and **must** be formatted.
- `advance_to_step` imports the private `runtime.next._internal_runtime.engine._read_snapshot` (L294). Move it verbatim. It is not in scope to change (C-005 forbids a `src/` seam), so record it in the tracer as known residual coupling.
- **Oracle untouched (C-002).** Do not edit `_bridge_oracle.py`, including its stale `bridge:NNNN` comment anchors (:448, :465, :518). Those belong to the oracle retirement follow-up #5116; note them there via the tracer.
- **#2560** (the runtime_bridge degod) touches `src/runtime/next/runtime_bridge.py`, not these tests. If it moves the P0 import surface mid-mission, rebase and re-run.
- Campsite (FR-020): clean S5778/S5779/S8997 findings only in the two new modules.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Commit in your lane worktree. Never push and never merge.

## Subtasks & Detailed Guidance

### Subtask T059 – Capture the base node-ID set; RED-first guard module (commit alone)

- **Purpose**: Pin the exact set to move, and land a behavioural RED: the P0 tests are not yet independent of the oracle.
- **Steps**:
  1. On the planning base, run `.venv/bin/python -m pytest tests/runtime/test_bridge_parity.py --collect-only -q > <scratch>/bridge_base_nodes.txt`. This is cheap: collection does not run the fixture. Expect 24 nodes.
  2. From that list, extract the 16 target IDs as `func[param]`:
     - the 13 P0 functions (14 nodes);
     - the 2 fail-closed functions.
     Save them to `<scratch>/p0_expected.txt`. Also extract the 8 oracle IDs into `<scratch>/oracle_expected.txt`.
  3. Create `tests/runtime/test_next_board_authority.py` with a module docstring, `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`, and:
     - a pure helper `_oracle_coupling_offenders(source: str) -> list[str]`. It flags:
       - any `import` or `from` of `tests.runtime._bridge_oracle` or `tests.runtime.test_bridge_parity`;
       - any function decorated `@pytest.fixture(scope="module")`, `"package"` or `"session"`.
     - `test_board_authority_module_does_not_import_the_oracle`. It reads this module's source **and** `tests/runtime/_next_mission_scaffold.py`. If the scaffold is absent it contributes no source, and the floor below still fails. The test asserts:
       - `_oracle_coupling_offenders(...) == []` for both files;
       - non-vacuity: this module defines ≥ 15 top-level `test_` functions.
     - `test_oracle_coupling_scan_flags_planted_imports`: a self-mutation test that feeds the same helper planted sources (`from tests.runtime._bridge_oracle import canonical`, `import tests.runtime.test_bridge_parity`, and a module-scoped fixture) and asserts each one is flagged. A clean source yields `[]`.
  4. Run the module. The guard test is RED ("found 2 test functions, need ≥ 15"), and the planted test is green. Paste the failure text into the Activity Log (#5068).
  5. Format the new file (it is new, so format it from the start). Commit: `test(WP11): red-first oracle-independence guard for board-authority tests`.
- **Files**: `tests/runtime/test_next_board_authority.py`.
- **Validation**: the RED is for the intended reason; there is no ImportError.

### Subtask T060 – Commit 1a: verbatim move of the helper closure into `_next_mission_scaffold.py`

- **Purpose**: Create one scaffold authority for real-engine mission fixtures, so the oracle and the P0 tests share it without duplication.
- **Steps**:
  1. Create `tests/runtime/_next_mission_scaffold.py` with a module docstring explaining its purpose: the real on-disk mission scaffolds shared by the board-authority tests and the parity oracle. Carry over the rationale paragraphs from the source blocks (L63-67 and L308-319) as comments, in their original words.
  2. Move these **verbatim**, keeping their names:
     - `_init_git_repo`, `_commit_all`, `_seed_wp_lane`, `_write_wp_task_files`, `_add_wp_files`, `_write_spec_md`, `_provision_mission_type_activations`;
     - `scaffold_software_dev`, `advance_to_step`;
     - `scaffold_coord_software_dev`, `_reject_wp_on_status_surface`;
     - the golden-path imports.
     Hoist the golden-path imports to the top of the new module. This drops the two `# noqa: E402` suppressions (zero new suppressions; this removes two).
  3. Declare `__all__` (charter C-007) listing the moved names. The rename happens in T062.
  4. In `test_bridge_parity.py`, delete the moved definitions and the L321-326 late imports, and import the moved names from `tests.runtime._next_mission_scaffold`. `_MissionTopology` is still needed there only if an oracle `_build_*` uses it. Check with grep, and drop the import if nothing does.
  5. Do **not** reformat `test_bridge_parity.py`.
- **Files**: new `tests/runtime/_next_mission_scaffold.py`; `tests/runtime/test_bridge_parity.py`.
- **Parallel?**: Same commit as T061 (the "move" commit).

### Subtask T061 – Commit 1b: verbatim move of the 15 test functions (same "move" commit as T060)

- **Purpose**: Make the P0 tests independent of the oracle module.
- **Steps**:
  1. Cut these from `test_bridge_parity.py` and paste them verbatim into `test_next_board_authority.py`, after the guard tests:
     - L1372-1400: the fail-closed banner comment and both direct-call tests;
     - L1402-1862: the board-authority banner, the 13 P0 functions and `_assert_reason_has_runnable_recovery_command`.
  2. Imports in the new module:
     - `re`, `shlex`, `subprocess`, `Path`, `pytest`;
     - `DecisionKind` from `runtime.next.decision`;
     - the scaffold names from `tests.runtime._next_mission_scaffold`.
     Keep the function-local `from runtime.next.runtime_bridge import ...` lines exactly as they are.
  3. Commit the T060 and T061 changes together: `refactor(WP11): move board-authority P0 tests + scaffold out of the oracle module (verbatim)`. Verify with `git diff --color-moved=dimmed-zebra HEAD~1` that the move is pure. Save the stat in the PR notes.
  4. Run `.venv/bin/python -m pytest tests/runtime/test_next_board_authority.py -q`. The guard test should now be GREEN: 15 functions, no oracle import.
- **Validation**:
  - `pytest --collect-only -q tests/runtime/test_next_board_authority.py`: the normalized `func[param]` set equals `<scratch>/p0_expected.txt`.
  - The oracle module's collection equals `<scratch>/oracle_expected.txt`, with 8 nodes.

### Subtask T062 – Commit 2: `ruff format` the new modules; Commit 3: rename to public names

- **Purpose**: Keep the formatting and renaming churn out of the move diff, so review can trust `--color-moved`.
- **Steps**:
  1. **Commit 2 (format):** run `uv run --frozen ruff format tests/runtime/_next_mission_scaffold.py tests/runtime/test_next_board_authority.py`. Commit only the formatter output.
  2. **Commit 3 (rename):** give the scaffold public names and list them in `__all__`:
     - `init_git_repo`, `commit_all`, `seed_wp_lane`, `write_wp_task_files`, `add_wp_files`, `write_spec_md`, `provision_mission_type_activations`, `reject_wp_on_status_surface`;
     - `scaffold_software_dev`, `advance_to_step` and `scaffold_coord_software_dev` are already public.
     Rename the golden-path import aliases to something non-underscored where they are re-exported, or keep them module-private if unused outside the scaffold.
  3. Update every call site in `test_next_board_authority.py` and in the oracle module's `_build_*`, `scaffold_research` and `scaffold_documentation`. These call-site renames are mechanical; do **not** reformat the oracle module.
  4. Search for stragglers: `grep -n "_init_git_repo\|_commit_all\|_seed_wp_lane\|_write_wp_task_files\|_add_wp_files\|_write_spec_md\|_provision_mission_type_activations\|_reject_wp_on_status_surface" tests/runtime/`. It must return only the golden-path `_init_git_repo` alias source, if you kept it.
  5. Run `uv run --frozen ruff check` and `ruff format --check` on the two new modules, and `uv run --frozen mypy` on them.
- **Files**: the two new modules; `tests/runtime/test_bridge_parity.py` (call sites only).

### Subtask T063 – Update references outside the modules

- **Purpose**: SC-003. No pointer should name the old location of a moved test.
- **Steps**:
  1. In `tests/next/test_finalized_task_routing.py:268-269`, change the comment `tests/runtime/test_bridge_parity.py::test_no_advancing_path_emits_unauthorized_step` to `tests/runtime/test_next_board_authority.py::test_no_advancing_path_emits_unauthorized_step`. This file is not format-excluded, so keep it `ruff format`-clean.
  2. In `tests/runtime/fixtures/bridge/README.md` (L11-17), change the sentence naming the `scaffold_software_dev` helpers "in `test_bridge_parity.py`" so it says the scaffolds live in `tests/runtime/_next_mission_scaffold.py`, and the `_build_*` functions stay in the oracle module. Add one line noting that the board-authority P0 tests live in `test_next_board_authority.py` and do not use the oracle fixture.
  3. Check that the remaining `test_bridge_parity` references (`src/runtime/next/runtime_bridge_io.py:1005`, `tests/runtime/test_bridge_engine.py:32`, `tests/runtime/test_bridge_decide_next.py:12`, `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py:132`, `tests/specify_cli/next/test_next_output_preservation.py:12`) all cite **oracle** parts, which stay. Leave them unchanged, and record that in the tracer.
- **Files**: `tests/next/test_finalized_task_routing.py`, `tests/runtime/fixtures/bridge/README.md`.

### Subtask T064 – Evidence: node-ID diff, oracle unchanged, durations, tracer

- **Purpose**: Make the split non-fakeable (Renata HIGH, FR-017 AS).
- **Steps**:
  1. Node-ID set equality:
     - collect the new module on head;
     - normalize to `func[param]`;
     - `diff` against `<scratch>/p0_expected.txt`. The output must be empty; 16 = 16.
     - repeat for the oracle module against `<scratch>/oracle_expected.txt`; 8 = 8.
     Paste both diffs (empty) and the counts into the PR notes.
  2. Oracle unchanged (C-002):
     - `git diff <base> -- tests/runtime/_bridge_oracle.py` is empty;
     - for `test_bridge_parity.py`, the 8 oracle test functions and `ledger_results` are byte-identical to base. Extract them with `ast.get_source_segment` on both SHAs and compare.
  3. `--setup-plan`: `pytest tests/runtime/test_next_board_authority.py --setup-plan -q | grep -c ledger_results` returns 0.
  4. Durations: `pytest tests/runtime/test_next_board_authority.py --durations=0 -q`. Record the total (target < 60 s; no assertion).
  5. Append tracer entries with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category design-decisions --actor <you>`. They cover:
     - 16/8 node sets;
     - the duration;
     - the residual `_read_snapshot` private import;
     - the `bridge:NNNN` anchors deferred to #5116;
     - "oracle untouched (C-002)".
- **Validation**: everything in Test Strategy is green.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/runtime/test_next_board_authority.py --durations=0 -q
# Oracle run (~390-440 s) — required once at WP end, not per commit
.venv/bin/python -m pytest tests/runtime/test_bridge_parity.py tests/runtime/test_bridge_decide_next.py tests/next/ -q
make test-fast
uv run --frozen ruff check tests/runtime/_next_mission_scaffold.py tests/runtime/test_next_board_authority.py tests/next/test_finalized_task_routing.py
uv run --frozen ruff format --check tests/runtime/_next_mission_scaffold.py tests/runtime/test_next_board_authority.py tests/next/test_finalized_task_routing.py
uv run --frozen mypy tests/runtime/_next_mission_scaffold.py tests/runtime/test_next_board_authority.py
```

- Do not run `ruff format` on `tests/runtime/test_bridge_parity.py` (format-excluded; WP13 owns it). `uv run --frozen ruff check` on it must stay clean. Removing the E402 late imports helps.
- Complexity ≤ 15, and no new suppressions.
- **Pre-existing failure rule**: classify any base-red failure (for example the #4874-class integration reds). If it is pre-existing, file or locate a GitHub issue before continuing.

## Risks & Mitigations

- **The review diff (~1.6k lines) is unreadable.** Use the 3-commit mandate plus `--color-moved`. Do not split the WP, because each half would need its own ~440 s oracle run.
- **A hidden fixture dependency.** A P0 test could pick up a `conftest.py` fixture by name. `--setup-plan` in T064 and the collection diff catch this.
- **Renames ripple into the oracle.** Mechanical call-site renames are allowed. Any change to oracle **assertions** or the fixture is a C-002 breach, so revert it.
- **The golden-path import from another test module (`tests/integration/...`) is fragile.** It is unchanged from base, so it is not this WP's concern. Keep it.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md` HIGH on FR-017, and Debbie's post-plan LOW):

- The PR carries the node-ID set diffs: new module = 16 base IDs (`func[param]`) and oracle = 8. A "split" that re-imports the oracle fixture is caught by `test_board_authority_module_does_not_import_the_oracle` and by `--setup-plan`.
- The self-mutation test calls the same `_oracle_coupling_offenders` function the guard uses.
- `_bridge_oracle.py` is unchanged, and the oracle's 8 test bodies plus `ledger_results` are byte-identical (C-002).
- The history has red-first, move, format and rename as distinct commits, and `--color-moved` shows the move is pure.
- The durations figure is recorded, not asserted.
- The new modules have `__all__`, pass format/lint/mypy, and add no suppressions.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>` (append at the END; UTC timestamps via `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP11 --to <status>` to change WP status.
