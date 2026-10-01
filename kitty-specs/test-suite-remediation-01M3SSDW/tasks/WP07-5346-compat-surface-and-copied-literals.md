---
work_package_id: WP07
title: '#5346 pins: compat surface and copied literals'
dependencies: []
requirement_refs:
- FR-006
- FR-008
- FR-011
- NFR-003
- NFR-005
- C-001
- C-002
- C-007
- SC-004
- SC-005
- NFR-004
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: eada9591d9f1962e65dfd519e0d1e386a3bb52ce
created_at: '2026-09-30T21:31:04.567357+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
phase: Phase 2 - Pin honesty
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py
- tests/ci/test_recapture_charter_shard_timings.py
- tests/specify_cli/coordination/test_teardown_single_seam_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – #5346 pins: compat surface and copied literals

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
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

- **FR-006 (#5346 rows 2, 5 and 7; pin-inventory groups G1 + G3)**:
  - **Row 2 / F1, RETIRE + floor**: `assert len(SYMBOL_TO_MODULE) == 196` is the single worst pin in the tree (18 re-pins since August). The test is named `…_167_…`, and its docstring is a ~140-line changelog.
  - **Row 5, split**:
    - `:481` is a verbatim PR-body copy; FIX it to assert the rendered substitutions;
    - `:490` (`COMMIT_MESSAGE == "…"`) is RETIRED behind the `:336/:341` guard;
    - `:494` (`MODULE == "charter"`) is FIXED to assert the argv the real seam passes.
  - **Row 7, FIX**: the literal-scan trap at `:107`, `"teardown_coordination_topology" in text`, becomes a behavioural seam recorder test.
- **NFR-003**: A behaviour-neutral plant needs 0 test edits. A violation plant goes red.
- **FR-011 / C-002**: Every RETIRE names a covering guard that goes red on the same plant.
- **R3**: The `# golden-count: cardinality-is-contract` marker is residue of the retired golden-count gate. #4315 (`a428532719`) swept it, and `e455ce26c1` re-added it by hand. Remove it, and do not re-add any escape marker.

## Context & Constraints

- Read first: `plan.md` IC-06; `research.md` "Pin dispositions" rows #5346-2/-5/-7; `research/pin-inventory.md` §2.1 rows 2, 5 and 7, plus §2.1a (why the count is not a contract).
- **Format-excluded**: `tests/specify_cli/coordination/test_teardown_single_seam_routing.py` (edit it without `ruff format`). The other two files are **not** excluded.
- **Read-only covering guards**:
  - `tests/specify_cli/cli/commands/test_mission_close_teardown_message.py`, whose `:24-32` already uses the recorder pattern for `mission_type`;
  - the in-file membership tests of the compat surface: `:432`, `:455`, `:465`, `:484`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP07 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **Planted breaks never land (C-007).** Product plants in `src/` or `scripts/` are **scratch edits only**; revert with `git checkout -- <file>`. Run `git diff --stat src/ scripts/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**:
   - For a convert: the neutral plant stays green with 0 test edits, and the violation plant goes red.
   - For a retire: the covering guard goes red on the same plant. If it stays green, stop (C-002) and report.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP07 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" <owned files>`. Each hit carries a reason.
6. **Quality (NFR-005).** `uv run --frozen ruff check` on all three files, and `ruff format --check` on the two non-excluded files. Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md).
9. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits. One commit per row is preferred.

### Additional mission-wide rules (analysis folds)

- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1).** If an unmasked or converted test exposes a **new** product defect, never re-mask it.
  - If the fix fits this WP: make it red-first, as a failing test commit followed by a **separate** `fix(...)` commit touching only the product file(s). It is a sanctioned out-of-map `src/` edit: record a one-line rationale in your WP notes, file an issue (`gh issue create`) and add its issue-matrix row (`spec-kitty agent issue-verdict ... --verdict fixed`). The "`git diff --stat src/` must be empty" rule is lifted for exactly that commit.
  - Otherwise: mark the test `xfail(strict=True, reason="<newly filed open issue>")` and tell the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T028 – Row 2: retire the compat-surface count; add a relational floor

- **Purpose**: `SYMBOL_TO_MODULE` is the test's **own** literal registry of private seam patch targets (`_mt_*`, `_ms_*`, `_st_*`, `_mr_*`, …) that `tasks.py` re-exports so historical `@patch("…agent.tasks.<name>")` targets resolve.
  - The file already enforces the real invariant by membership:
    - identity re-export, `test_tasks_binding_is_seam_object` (`:432`);
    - native origin, `test_guard_symbol_is_genuinely_native_to_its_seam` (`:455`);
    - superset over the live seam defs, `test_guard_keyset_is_superset_of_all_six_seams_native_defs` (`:465`);
    - disjointness, `test_no_required_symbol_duplicated_in_survey` (`:484`).
  - The count is a second entry for a fact that `:465` already enforces.
- **Files**: `tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py`.
- **Anchors**: `_SEAM_GROUPS` at `:379`; `SYMBOL_TO_MODULE` at `:392-393`; `test_guard_covers_full_167_symbol_surface` at `:492-635`, with the changelog docstring, the TODO at `:626-632` (which doubts its own ROI) and the assert at `:635`.
- **Steps**:
  1. Delete the whole test function, including its docstring and TODO.
  2. Add a small relational non-vacuity test (never re-pinned):
     ```python
     def test_every_seam_group_declares_at_least_one_symbol() -> None:
         """Non-vacuity: an emptied seam tuple cannot silently pass the membership battery."""
         assert _SEAM_GROUPS, "no seam groups declared"
         empty = [name for name, symbols in _SEAM_GROUPS.items() if not symbols]
         assert not empty, f"seam groups with no symbols: {empty}"
     ```
  3. Check for per-tuple comments that carry counts (e.g. `# WP06 … — 20 symbols` at `:82`). They are prose, not assertions; leave them, or trim them only if it costs nothing.
  4. Run the file. All green.
- **Planted breaks**:
  - **Neutral**: add a `_mt_new_helper` function to `src/specify_cli/cli/commands/agent/tasks_move_task.py`, register it in `_TASKS_MOVE_TASK` (test file, scratch) and re-export it in `tasks.py` (scratch). The new form stays green. **Before** (the base): `:635` reds.
  - **Violations**, one at a time, each reverted:
    1. keep the def but drop the tuple entry: `:465` reds;
    2. register a name the seam no longer defines: `:455` reds;
    3. list one symbol in two seam tuples: the `SYMBOL_TO_MODULE` construction raises, or `:484` reds;
    4. drop the `tasks.py` re-export: `:432` reds.
  - **Floor**: empty one seam tuple (scratch). The new floor test reds.

### Subtask T029 – Row 5a: rendered-substitution assert (`:481`); retire `:490`

- **Purpose**: `test_pr_body_template_matches_fr010_verbatim_text` (`:479-487`) asserts the template body **verbatim**, so any wording tweak reds it. `test_commit_message_matches_fr010_verbatim_text` (`:489-490`) copies a constant.
- **Files**: `tests/ci/test_recapture_charter_shard_timings.py`.
- **Steps**:
  1. **`:481`, FIX**: assert what the template *drives*.
     - Render `recapture.PR_BODY_TEMPLATE.format(before=100, after=105, run_url="https://example.invalid/run/1")`, then assert:
       - `"100" in body`;
       - `"105" in body`;
       - `"https://example.invalid/run/1" in body`;
       - `".github/ci-shard-timings.json" in body`;
       - no unformatted placeholder remains: `"{" not in body and "}" not in body`.
     - Rename the test to e.g. `test_pr_body_template_renders_substitutions_and_names_timings_file`.
  2. **`:490`, RETIRE**: delete `test_commit_message_matches_fr010_verbatim_text`. The covering guard is `test_push_and_open_pr_runs_git_and_gh_with_expected_arguments` (`:311`, asserts at `:336/:341`), which proves that the one message is used for both the commit and the PR title. Read `:311-345` to confirm that before deleting.
- **Planted breaks**:
  - `:481`: drop `{after}` from `PR_BODY_TEMPLATE` in `scripts/ci/recapture_charter_shard_timings.py` (scratch). The new form reds.
  - `:490`: make `_push_and_open_pr` pass a different string to `git commit` than to `--title` (scratch). `:336/:341` red.
  - **Neutral for `:490`**: change `COMMIT_MESSAGE`'s wording (scratch). The covering guard stays green, since it compares the two uses, and the retired test would have red.
- **Parallel?**: Yes.

### Subtask T030 – Row 5b: argv through the real seam (`:494`)

- **Purpose**: `test_module_is_hardcoded_to_charter` (`:493-494`) asserts `recapture.MODULE == "charter"`, a constant copy. The real FR-009 scope lock is that `run_capture_phase` passes `--module charter` to `capture_shard_timings.main`. Today every `run_capture_phase` test stubs `main` with `lambda argv: 0` (`:553`, `:570`, `:583`) and ignores argv.
- **Files**: `tests/ci/test_recapture_charter_shard_timings.py`.
- **Anchors**: `scripts/ci/recapture_charter_shard_timings.py:514` `run_capture_phase`, whose `:526` calls `run_capture_or_die(capture_shard_timings.main, ["--module", MODULE, "--write"])`.
- **Steps**:
  1. Replace `test_module_is_hardcoded_to_charter` with a test that stubs `capture_shard_timings.main` with a **recorder**:
     ```python
     seen: list[list[str]] = []
     monkeypatch.setattr(capture_shard_timings, "main", lambda argv: seen.append(list(argv)) or 0)
     ```
     Mirror the setup of `test_run_capture_phase_writes_drift_false_outputs_on_agreement` (`:580`) so `run_capture_phase()` completes: the same `GITHUB_OUTPUT` / timing-file preparation.
  2. Assert `seen == [[...]]` has exactly one call, and `seen[0][:2] == ["--module", "charter"]`.
  3. Keep `:199` (`_read_charter_length` reads the `charter` key) unchanged.
- **Planted breaks**:
  - **Violation**: make `run_capture_phase` pass `["--module", "specify_cli", "--write"]` (scratch). The argv assertion reds.
  - **Neutral**: rename the constant `MODULE` → `TARGET_MODULE`, keeping the value (scratch, all references). The new test stays green; the old test would have errored.

### Subtask T031 – Row 7: a behavioural seam recorder replaces the literal scan

- **Purpose**: `test_former_production_sites_route_through_the_seam` (`:97-114`) greps `consolidate.py` and `mission_type.py` for the string `teardown_coordination_topology`. That is the Literal-Scan Trap: moving the function reds it, and a caller that imports the name but stops calling it passes. Both call sites import the seam **lazily inside the function**, so `monkeypatch.setattr("specify_cli.coordination.teardown.teardown_coordination_topology", recorder)` intercepts them:
  - `consolidate.py:365` imports it and `:408` calls it;
  - `mission_type.py:1140` imports it and `:1144` calls it.
- **Files**: `tests/specify_cli/coordination/test_teardown_single_seam_routing.py` (format-excluded).
- **Steps**:
  1. Replace the literal-scan test with **two** behavioural tests, or one parametrized test:
     - **mission_type**: follow `tests/specify_cli/cli/commands/test_mission_close_teardown_message.py:24-32`. Monkeypatch the seam with a recorder and `CoordinationWorkspace.is_present` as needed. Call `mission_type._teardown_coordination_worktree(tmp_path, slug, MID8)`, and assert the recorder was called **once** with `(tmp_path, slug, MID8, …)`, i.e. the mission identity.
     - **consolidate**: call `consolidate._teardown_coordination_for_abort(repo_root, resolved, state_entry)` (`:335`). Build the smallest `state_entry` that reaches the teardown: read `:335-410` for the resolution path (slug and meta resolution is best-effort, so you may need a minimal `ConsolidationState` plus meta). Assert the recorder was called once with the resolved mission identity and `persist=False`.
  2. Drop the per-file absence assertion (`not _TEARDOWN_CALL.search(text)`). `test_zero_production_teardown_calls_outside_the_seam` (`:81`) already covers it globally, and it stays unchanged.
- **Planted breaks**:
  - **Violation**: replace the seam call in `_teardown_coordination_for_abort` with an inline `CoordinationWorkspace.teardown(...)` (scratch). The recorder test reds, and `:81` reds too.
  - **Neutral**: move `_teardown_coordination_worktree`'s body into a same-module helper it calls (scratch). The behavioural test stays green; the old literal scan still passed too, so also record that a *rename of the importing module* would red the old scan but not the new test.
- **Parallel?**: Yes.
- **Edge cases**: Do not RETIRE outright. The research found no other behavioural test that reds if `--abort` stops calling the seam, so C-002 blocks a plain delete.

### Subtask T032 – Plants, counts, evidence

- **Steps**:
  1. The full named-file run (Test Strategy). All green.
  2. Evidence records:
     - **#5346-2**: RETIRE + floor. Covering guards `:465`, `:455`, `:484` and `:432`, each red under its violation. The neutral plant is green with 0 edits, and the old form was red on it.
     - **#5346-5**: `:481` FIX, `:490` RETIRE (covering guard `:336/:341`), `:494` FIX.
     - **#5346-7**: FIX (recorder red under the inline-teardown plant).
  3. `rg -n "golden-count" tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py` returns nothing.
  4. `make test-fast` once.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/ci/test_recapture_charter_shard_timings.py tests/specify_cli/coordination/test_teardown_single_seam_routing.py tests/specify_cli/cli/commands/test_mission_close_teardown_message.py -n0 -q
uv run --frozen ruff check tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/ci/test_recapture_charter_shard_timings.py tests/specify_cli/coordination/test_teardown_single_seam_routing.py
uv run --frozen ruff format --check tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/ci/test_recapture_charter_shard_timings.py
make test-fast
```

## Risks & Mitigations

- **The consolidate abort path needs state to reach the seam.** Build the minimal state. If it is truly unreachable without a git repo, use the existing git fixtures (`tests/conftest.py`) rather than weakening the assertion.
- **Over-asserting the PR body** re-creates a copy pin. Assert substitutions and the file name only.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- Re-run the row-2 neutral plant: 0 test edits, green.
- Re-run violation (i): `:465` red. This is SC-005 pick #14.
- Re-run the row-7 violation: the recorder test is red (quickstart #15).
- There are no escape markers and no `src/` or `scripts/` changes.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T028 T029 T030 T031 T032 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP07 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
