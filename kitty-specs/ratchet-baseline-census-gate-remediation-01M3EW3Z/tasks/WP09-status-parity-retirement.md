---
work_package_id: WP09
title: Status parity retirement and relocation
dependencies: []
requirement_refs:
- FR-014
- NFR-005
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T049
- T050
- T051
- T052
- T053
phase: Phase 3 - Parity remediation
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-26T17:00:00Z'
  actor: planner-priti
  action: Folded post-tasks squad findings
agent_profile: python-pedro
authoritative_surface: tests/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/status/test_parity.py
- tests/status/test_reducer.py
- tests/status/test_transitions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Status parity retirement and relocation

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

Delete `tests/status/test_parity.py` (740 LOC, 0.1x cross-branch scaffold) without losing any live invariant (FR-014, NFR-006, US3-AS2).

Done means:

1. Every one of the file's 21 test functions (29 collected nodes incl. the 9 parametrized backport cases) has a recorded disposition. Each one is either **retire (duplicate)** with a named survivor and a mutation that reds both, **retire (scaffold)** with a cited reason and a mutation showing it could not fail, or **relocate** into `tests/status/test_reducer.py` or `tests/status/test_transitions.py`. Nothing is left without a disposition. This explicitly includes `test_reduce_then_serialize_roundtrip` (L407) and `test_realistic_log_identical_across_runs` (L660), which the plan's first draft missed.
2. Tests are relocated **only where no survivor enforces the same invariant**. The five `TestTransitionMatrixParity` tests are presumed duplicates, per the post-plan squad. They are retired as duplicates **after** the mutation matrix confirms a survivor reds. A test with no survivor is relocated, not retired.
3. `tests/status/test_parity.py` is gone, and its `pyproject.toml` format-exclude line is removed in the same commit.
4. `tests/status/` and `tests/architectural/` are green, and the evidence is recorded with `spec-kitty agent tracer-append` (D-OP-4).

## Context & Constraints

- Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Feature dir: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/`.
- Read before starting: `spec.md` (FR-014, NFR-006, US3-AS2), `plan.md` (the WP09 row, D-OP-4, and the pyproject coordination points), `research.md` §F2, `research/postplan-debbie.md` (the two MEDIUM WP09 findings), and `research/grounding-2631_2972.md` §N2.
- **C-001 as amended by D-OP-4.** This is a deletion WP. The tests being relocated are already GREEN on base, so there is **no honest RED-on-base** (Debbie, post-plan). Do **not** fake one, and do **not** add "module is gone" tombstone tests (the class #3285 removed). Red-first evidence is the mutation matrix in T049, recorded in the tracer, together with the surviving tests staying green.
- **C-005.** No `src/` changes. Mutations are applied only temporarily, in a scratch copy or via an uncommitted edit that you revert. Never commit them.
- **Format-exclude.** `tests/status/test_reducer.py` (pyproject L2555) and `tests/status/test_transitions.py` (L2562) are in `[tool.ruff.format].exclude`:
  - Do **not** run `ruff format` on them. WP13 formats files this mission rewrites and removes their lines.
  - Keep the relocated code in the files' existing style, so `test_every_exclude_entry_still_genuinely_reformats` stays green.
  - `tests/status/test_parity.py` (L2553) is deleted here, so you remove **its own** exclude line (a coordinated out-of-map edit of `pyproject.toml`). The hunk is ~1,600 lines away from WP07's hunk (L954-955), so there is no lane conflict. Line numbers may drift, so match on content (`"tests/status/test_parity.py",`).
- **#4506** (repo-wide reformat) may land mid-mission. If `pyproject.toml` no longer lists the line, skip that edit and note it in the tracer.
- Campsite (FR-020): clean Sonar S5778/S5779/S8997 findings only in the code you move or write in `test_reducer.py` and `test_transitions.py`. Do not sweep either file.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Commit in your lane worktree (`spec-kitty implement WP09` resolves it). Never push and never merge.

## Subtasks & Detailed Guidance

### Subtask T049 – Mutation matrix: prove each disposition before touching code (D-OP-4 red-first evidence)

- **Purpose**: NFR-006 forbids retiring a test without a named survivor or a mutation proof. The mutation matrix is this WP's red-first evidence: it shows which tests are genuine duplicates and which must be relocated.
- **Steps**:
  1. On the planning base (your lane head before any edit), run `.venv/bin/python -m pytest tests/status/test_parity.py tests/status/test_reducer.py tests/status/test_transitions.py tests/status/test_models.py tests/architectural/test_no_retired_subsystems.py -q`. All tests should pass. Record the counts.
  2. **Make the matrix reproducible** (Renata HIGH: the matrix is this WP's entire red-first evidence, so it must not be hand-applied prose). Write `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/wp09_mutation_matrix.py`, excluded from ruff by `ruff.toml` `extend-exclude = ["kitty-specs/*/research/**"]`. It works as follows:
     - It holds one mutation per row M1–M10. Each mutation is either a **pytest plugin** that monkeypatches at session start (Debbie's `mutplug.py` style, loaded with `-p`), or, where only a source edit works (M10's import scan, and any constant frozen at import that you cannot recompute), a temporary source edit applied in a throwaway `git worktree` of the current HEAD that is removed afterwards. It never edits your lane's `src/`.
     - For each mutation it runs the listed test files and prints a table `mutation → red node IDs` (from `-rf` / `--junitxml`).
     - `--base-root <path>` selects the checkout under test, so the reviewer can re-run it at the planning base.
     - **You** commit the script on the planning branch in the repository-root checkout (primary partition) before moving WP09 to `for_review`, and record the SHA in the Activity Log. Paste its output table **verbatim** into the tracer and the PR.

     Mutation notes (Pedro probes):
     - **M1**: lane-state ordering lives in `spec_kitty_events.diary.reduce_parsed` (site-packages `diary.py:1579`, `sorted(unique_events, key=(at, event_id))`). The `(at, event_id)` sorts in `src/specify_cli/status/reducer.py:105/156` order only the provenance projections: mutating them leaves both expected reds green, and `git checkout -- src/` cannot revert a site-packages edit. Use the plugin form `spec_kitty_events.diary.sorted = lambda it, key=None, reverse=False: list(it)` (shadowing the builtin in that module's globals). That reds both expected tests.
     - **M2–M4**: `ALLOWED_TRANSITIONS` is frozen at import (`transitions.py:53`). Monkeypatching `WPState.allowed_targets` alone under-reports (M2 gave 4 reds, not the expected set). In the plugin, also set `transitions.ALLOWED_TRANSITIONS = transitions._derive_allowed_transitions()` after patching, or use the source-edit form.

     | # | mutation (temporary) | target | expected RED |
     |---|---|---|---|
     | M1 | make the event sort a no-op (plugin: `spec_kitty_events.diary.sorted = lambda it, key=None, reverse=False: list(it)`) | `spec_kitty_events.diary.reduce_parsed` (site-packages; **not** `src/specify_cli/status/reducer.py`) | parity `test_event_order_does_not_affect_final_state` **and** survivor `test_reducer.py::TestReduceOutOfOrder::test_reduce_out_of_order_events` |
     | M2 | add a `done → planned` edge to `WPState.allowed_targets`, **and recompute `ALLOWED_TRANSITIONS`** | `src/specify_cli/status/wp_state.py` + `transitions.py:53` | parity `test_terminal_lanes_have_no_outbound_transitions` **and** survivors `test_transitions.py::TestConstants::test_allowed_transitions_count`, `TestIllegalTransitions::test_illegal_transition_rejected[done-planned]`, `TestBehaviorPreservationParity::test_validate_transition_matches_baseline`, `TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]`, plus `test_collapsed_matrix_catches_planted_row` |
     | M3 | add a `claimed → claimed` self-edge, and recompute `ALLOWED_TRANSITIONS` | `wp_state.py` + `transitions.py` | parity `test_no_self_transitions_in_matrix` **and** survivors `test_allowed_transitions_count`, `test_validate_transition_matches_baseline`, `test_collapsed_matrix_catches_planted_row` |
     | M4 | add an edge to a non-canonical lane, e.g. `planned → uninitialized`, and recompute `ALLOWED_TRANSITIONS` | `wp_state.py` + `transitions.py` | parity `test_transition_pairs_use_canonical_lanes` **and** survivor `test_allowed_transitions_count` (29 → 30) |
     | M5 | rename one entry of `CANONICAL_LANES` (e.g. `"in_review"` → `"reviewing"`) | `src/specify_cli/status_lanes.py` | parity `test_all_canonical_lanes_in_enum`; check `test_transitions.py`, `test_models.py` and `tests/status/test_validate.py::test_canonical_lanes_pass` for a survivor |
     | M6 | append a new display member to `Lane` without adding it to `CANONICAL_LANES` | `src/specify_cli/status/models.py` | parity `test_all_enum_values_in_canonical_lanes`; survivor candidate `test_models.py::TestLaneEnum::test_lane_member_names_exact` |
     | M7 | make `materialize_to_json` drop `sort_keys=True` | `reducer.py::materialize_to_json` | parity `test_sorted_keys_in_json_output`; expect **no** survivor in `test_reducer.py` (only `test_byte_identical_*` exist there) |
     | M8 | make `StatusSnapshot.from_dict` drop `last_event_id` | `src/specify_cli/status/models.py` | parity `test_reduce_then_serialize_roundtrip` (L407) and `test_realistic_log_json_roundtrip_stable` (L674) |
     | M9 | inject per-call nondeterminism into `materialize_to_json` (e.g. a random key) | `reducer.py` | parity `test_realistic_log_identical_across_runs` (L660) **and** survivor `test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls` |
     | M10 | plant `from specify_cli.sync import x` at module top of `status/emit.py` | `emit.py` | survivor `tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist` (covers `TestBackportReadiness`) |

  3. **Decision rule.** A parity test whose mutation reds a named survivor is retired as a duplicate. A parity test whose mutation reds **only** itself is relocated (T050/T051). Expect M5, M6 and M7 to need relocation, but let the results decide rather than this table.
  4. Record the full matrix (the script's verbatim output table) with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category design-decisions --actor <you> --entry "<WP09 mutation matrix: M1..M10 → red sets>"`. Use several entries if needed.
- **Files**: no lane file edited. The mission artefact `research/wp09_mutation_matrix.py` is committed on the planning branch (see step 2).
- **Parallel?**: No. It gates T050–T052.
- **Validation**: `git status` in the lane is clean after the matrix. The tracer entries exist, and the script's SHA is in the Activity Log.

### Subtask T050 – Relocate the determinism tests that have no survivor into `test_reducer.py`

- **Purpose**: Keep the realistic multi-WP event-log invariants and the unique sorted-keys check. Retire the rest as duplicates.
- **Disposition table**. Source line numbers are for `tests/status/test_parity.py` on the planning base. Confirm each against T049.

  | parity test (line) | disposition | survivor / destination |
  |---|---|---|
  | `test_same_events_produce_identical_snapshots` (217) | retire (duplicate) | `test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls` (:465) |
  | `test_event_order_does_not_affect_final_state` (258) | retire (duplicate) | `TestReduceOutOfOrder::test_reduce_out_of_order_events` (:177), per M1 |
  | `test_duplicate_events_deduplicated_deterministically` (299) | retire (duplicate) | `TestReduceDeduplication::test_reduce_deduplication` (:211) |
  | `test_json_serialization_byte_identical` (327) | retire (duplicate) | `TestByteIdenticalOutput::test_byte_identical_output` (:425) |
  | `test_sorted_keys_in_json_output` (373) | **relocate** (no survivor, per M7) | `test_reducer.py::TestByteIdenticalOutput` |
  | `test_reduce_then_serialize_roundtrip` (407) | retire (duplicate), per M8 | the relocated `test_realistic_log_json_roundtrip_stable`, which is a strict superset: a richer log plus full byte equality after `from_dict` |
  | `test_empty_events_produce_stable_snapshot` (447) | retire (duplicate) | `TestReduceEmpty::test_reduce_empty_events` (:102) |
  | `test_force_events_tracked_in_force_count` (469) | retire (duplicate) | `TestReduceForceCount::test_reduce_force_count_tracked` (:280) |
  | `test_concurrent_events_rollback_precedence` (511) | retire (duplicate) | `TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval` (:315) |
  | `TestFullEventLogParity._build_realistic_event_log` (556) | **relocate** (fixture) | new `test_reducer.py::TestRealisticEventLog` |
  | `test_realistic_log_produces_expected_summary` (635) | **relocate** | `TestRealisticEventLog` |
  | `test_realistic_log_identical_across_runs` (660) | retire (duplicate), per M9 | `test_byte_identical_across_reduce_calls` (:465) |
  | `test_realistic_log_json_roundtrip_stable` (674) | **relocate** | `TestRealisticEventLog` |

- **Steps**:
  1. Add `class TestRealisticEventLog` to `tests/status/test_reducer.py`, next to `TestByteIdenticalOutput`. Move the fixture builder plus the two relocated tests verbatim, apart from the helper adaptation in step 2.
  2. `test_reducer.py::_make_event` (L45) has no `evidence` parameter, but the realistic log's `WP01 → done` event needs `DoneEvidence`. Pick one of these:
     - add an optional `evidence: DoneEvidence | None = None` kwarg to `test_reducer.py::_make_event` (the preferred, smallest change); or
     - construct that one `StatusEvent` directly.
     Import `DoneEvidence` and `ReviewApproval` from `specify_cli.status.models`.
  3. Move `test_sorted_keys_in_json_output` into `TestByteIdenticalOutput`. Its snapshot `summary` literal omits `in_review` and `approved`; keep it as is, because the test asserts key order, not the summary schema.
  4. The relocated tests keep `patch("kernel.clock.now_utc_iso", ...)`. It is already the file's idiom and patches a public kernel function (C-005 safe).
  5. `test_reducer.py` has `pytestmark = [integration, git_repo]`. The relocated tests are pure. Leave the module mark as is and do not add per-test markers. **Consequence (accepted; record it in the tracer)**: `test_parity.py` was `pytest.mark.fast`, so the relocated tests leave `make test-fast`, whose marker expression is `(fast or unit) and ... not integration ...`. A class-level `pytest.mark.fast` would not bring them back, because the module-level `integration` mark still deselects them.
- **Files**: `tests/status/test_reducer.py`.
- **Parallel?**: Yes, alongside T051. Both depend on T049.
- **Validation**: `.venv/bin/python -m pytest tests/status/test_reducer.py -q` passes. Re-apply M7 and M8 temporarily and confirm the relocated tests go RED, then revert.

### Subtask T051 – Transition-matrix dispositions (`TestTransitionMatrixParity`)

- **Purpose**: `ALLOWED_TRANSITIONS` is a non-authoritative derived projection (`src/specify_cli/status/transitions.py:9-13`) that is already pinned by the golden baseline and the count test. The matrix tests are duplicates unless T049 shows otherwise.
- **Steps**:
  1. `test_no_self_transitions_in_matrix` (730): retire as a duplicate, per M3. Name the survivors T049 observed.
  2. `test_terminal_lanes_have_no_outbound_transitions` (735): retire as a duplicate, per M2. There are five survivors (listed in the T049 table, with `ALLOWED_TRANSITIONS` recomputed).
  3. `test_transition_pairs_use_canonical_lanes` (719): retire as a duplicate if M4 reds `test_allowed_transitions_count`. It does unless the mutation also removes an edge. Record whether the golden baseline catches a count-preserving swap as well.
  4. `test_all_canonical_lanes_in_enum` (698) and `test_all_enum_values_in_canonical_lanes` (703): retire each **only if** M5 or M6 reds a named survivor. If not, relocate them into `tests/status/test_transitions.py::TestConstants`, next to `test_canonical_lanes_count`. Keep the `NON_DISPLAY_LANES` carve-out and its docstring, and import `Lane` and `NON_DISPLAY_LANES` from `specify_cli.status.models`.
  5. Do not add a new `TestTransitionMatrixInvariants` class unless at least three tests are relocated. `TestConstants` is the owning home for lane-constant invariants.
- **Files**: `tests/status/test_transitions.py` (only if something is relocated).
- **Parallel?**: Yes, alongside T050.
- **Validation**: `.venv/bin/python -m pytest tests/status/test_transitions.py -q` passes. For each relocated test, its T049 mutation reds it.

### Subtask T052 – Delete `tests/status/test_parity.py` and its format-exclude line (one commit)

- **Purpose**: Remove the retired-subsystem scaffold and the residue together (spec edge case "Retiring files listed in `pyproject.toml` format exclusions").
- **Steps**:
  1. Retire `TestBackportReadiness` (L75-190). Reason: `src/specify_cli/sync` does not exist, and `tests/architectural/test_no_retired_subsystems.py` is the canonical guard. Its `_RETIRED_PATHS` includes `"src/specify_cli/sync"` (L28), and `test_no_retired_import_targets_exist` (L390) has a planted self-test (L394). M10 is the mutation proof.
  2. Retire `TestPhaseCap::test_phase_module_deleted` (L200). Reason: it is a tombstone that pins the absence of `specify_cli.status.phase`. It can only fail if someone re-creates a module with that name, so it pins no behaviour (the #3285 class). Do **not** add `status/phase.py` to `_RETIRED_PATHS`; that is out of scope.
  3. `git rm tests/status/test_parity.py`. In the **same commit**, delete the `"tests/status/test_parity.py",` line from `[tool.ruff.format].exclude` in `pyproject.toml`. Otherwise `test_ruff_format_enforcement.py::test_formatter_debt_exclude_only_names_live_files` goes red.
  4. Search for live references: `grep -rn "status/test_parity" --include=*.py --include=*.md --include=*.toml --include=*.yml . | grep -v '^./kitty-specs\|^./.worktrees'`.
     - `docs/plans/testing/mutation-testing-findings.md:176` cites `tests/specify_cli/status/test_parity.py`, a different, historical path. Leave it.
     - Any other live hit is fixed in this commit.
- **Files**: `tests/status/test_parity.py` (deleted); `pyproject.toml` (one line, coordinated out-of-map edit).
- **Parallel?**: No. Do this after T050 and T051 are committed.
- **Validation**: `.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q` passes.

### Subtask T053 – NFR-006 record and blast-radius validation

- **Purpose**: Make the retirement auditable. WP12's catalog row and WP13's closeout both cite this record.
- **Steps**:
  1. Append one tracer entry per disposition group, via `spec-kitty agent tracer-append --category design-decisions`:
     - retired duplicates, with their survivors;
     - retired scaffold, with its reasons and M10;
     - relocated tests, with their destinations.
     Include the pre and post test counts for `tests/status/`. The net should drop by the retired count only.
  2. Run the blast radius (see Test Strategy).
  3. Report any base-red failure per the pre-existing-failure rule below.
- **Files**: none (tracer via CLI).
- **Validation**: all commands in Test Strategy are green, and the counts are recorded in the Activity Log.

## Test Strategy

Tests are required. Run these from the lane worktree:

```bash
.venv/bin/python -m pytest tests/status/ tests/architectural/test_no_retired_subsystems.py -q
.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q
# pyproject.toml touched ⇒ cross-cutting ⇒ full architectural sweep
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
uv run --frozen ruff check tests/status/test_reducer.py tests/status/test_transitions.py
uv run --frozen mypy tests/status/test_reducer.py tests/status/test_transitions.py
```

- **mypy bar**: the base is not clean (`tests/status/test_transitions.py:172`, plus a followed import in `tests/reliability/fixtures/review_prompt.py:127`). Record base and head counts and require **0 new errors**.

- Do **not** run `ruff format --check` on `test_reducer.py` or `test_transitions.py`. They are format-excluded, and WP13 owns them.
- Complexity stays ≤ 15. Add no new `# noqa` or `# type: ignore`.
- **Pre-existing failure rule**: any failure that is also red on the planning base must be classified using CLAUDE.md's baseline-red gotcha. If it is pre-existing, file or locate a GitHub issue before continuing and note it in the Activity Log.

## Risks & Mitigations

- **A mutation leaks into a commit.** Run `git diff --stat src/` before every commit; it must be empty.
- **Lane-enum tests are wrongly treated as duplicates.** T049's M5 and M6 decide; relocate by default if in doubt.
- **The relocated code becomes format-clean.** That flips `test_every_exclude_entry_still_genuinely_reformats`. Keep the moved code verbatim (long lines, existing quoting).
- **#4506 lands mid-mission.** Rebase, skip the pyproject edit if the line is gone, and note it in the tracer.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`, NFR-006 and FR-013-AS):

- Every one of the 21 original test functions appears in the tracer with a disposition. **Diff the function list** from `git show <base>:tests/status/test_parity.py`.
- Each "retire (duplicate)" names a survivor node ID, and the recorded mutation reds **both** tests. A "survivor" that the mutation leaves green is a rejection.
- The "retire (scaffold)" entries cite the concrete reason (the deleted package/module and its guard) and give a mutation showing the test could not fail.
- The relocated tests are not weakened. Compare the assertions line by line with the base.
- There are no tombstone tests ("test_parity.py is gone"), and no `src/` diff.
- `research/wp09_mutation_matrix.py` is committed on the planning branch; the tracer and PR carry its verbatim output. M1 targets `spec_kitty_events.diary` (not `status/reducer.py`), and M2–M4 recompute `ALLOWED_TRANSITIONS`.

**Reviewer RED reproduction** (deletion/relocation WP, D-OP-4: the RED is the mutation matrix). Re-run it yourself against a clean planning-base checkout and compare the table with the tracer:

```bash
git worktree add /tmp/wp09-base 3717c7ea
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/wp09_mutation_matrix.py --base-root /tmp/wp09-base
git worktree remove /tmp/wp09-base
```

Each "retire (duplicate)" row must show both the parity test and its survivor red. A row whose survivor stays green is a rejection. A mutation that errors at collection instead of failing an assertion is not valid evidence.

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-014, NFR-005, NFR-006, C-001 (as amended by D-OP-4), C-005; contributes to SC-003 and SC-005.
- The `pyproject.toml` exclude line is removed in the same commit as the deletion. No other exclude lines change.
- `tests/status/` and the full `tests/architectural/` are green, and the counts are recorded.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>` (append at the END; UTC timestamps via `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP09 --to <status>` to change WP status.
