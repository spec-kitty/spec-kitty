---
work_package_id: WP06
title: '#5346 pins: consolidation trio'
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
base_commit: b95e9e6cb9b8a2669300bfd6a6709c684d5ab68c
created_at: '2026-09-30T21:23:57.592532+00:00'
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 2 - Pin honesty
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/consolidation/test_mid8_embedded_preflight.py
- tests/consolidation/test_issue_4474_topology_aware_bake.py
- tests/consolidation/test_behind_head_recovery_coverage.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – #5346 pins: consolidation trio

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

- **FR-006 (#5346 rows 3, 4, 6; pin-inventory group G2)**: Each pin is converted to an invariant form or retired behind a named covering guard:
  - **Row 3, RETIRE**: `TestWorktreeTeardownSeamRouting`, which re-derives the naming grammar with an f-string (`allocator_path = tmp_path/".worktrees"/f"{slug}-{lane_id}"` and `teardown_path.name == "057-foo-bar-lane-a"`).
  - **Row 4, FIX (rename + re-scope)**: `test_genuinely_unreachable_primary_surfaces_instead_of_silent_fail_open` asserts `result == 1` (flipped from `is None` by `2f8a558e6c`). Its name and docstring now describe a contract that the executor enforces, not this seam.
  - **Row 6, FIX**: five sibling tests pin the full private signature of `_report_pre_mutation_refusal` / `_recover_behind_head_primary_on_resume` with `assert_called_once_with(exc, tmp_path, mission_branch=…, base_sha=None)`.
- **NFR-003**: A behaviour-neutral plant needs **0** test edits to stay green. A violation plant goes red.
- **FR-011 / C-002**: Every RETIRE names a covering guard that goes red on the same plant.
- **FR-008**: No ratchet baseline is touched.

## Context & Constraints

- Read first: `spec.md` FR-006 and US2; `plan.md` IC-06 and the RK-1 ruling; `research.md` "Pin dispositions" rows #5346-3/-4/-6; `research/pin-inventory.md` §2.1 rows 3, 4 and 6, which give the exact neutral and violation plants.
- **RK-1**: Row 3 lowers the executed-test count. That is sanctioned by C-002 and FR-011, since the covering guard is proven red. NFR-001 applies to the masked-green files only.
- **Read-only covering guards (never edit)**:
  - `tests/consolidation/test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output` (`:141`) builds the mission with the **real** `allocate_lane_worktree`, via `tests/consolidation/_divergent_shapes.py`;
  - `tests/lanes/test_branch_naming_seam.py` (the grammar table, including legacy slugs);
  - `tests/consolidation/test_mission_number_truthful_4900.py::test_absent_target_meta_refuses_instead_of_fabricating` (`:655`).
- None of the three owned files is format-excluded, so `ruff format --check` applies.
- PR #5407 touched 22 other `tests/consolidation` files but none of these three. Nothing is already resolved (pin-inventory §0.1).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP06 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **Planted breaks never land (C-007).** Product plants go into `src/specify_cli/consolidation/*.py` as **scratch edits only**; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**:
   - For a **convert**: the neutral plant stays green with 0 test edits, and the violation plant goes red.
   - For a **retire**: the covering guard goes red on the violation plant, and the retired test stayed green on it (it guarded nothing extra).
   - If a covering guard stays green, stop: C-002 blocks the retirement, so switch to FIX and report.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP06 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" <owned files>`. Each hit carries a reason.
6. **Quality (NFR-005).** `uv run --frozen ruff check` and `ruff format --check` on the owned files. Delete imports that become unused (e.g. `worktree_path` once row 3 is gone). Add no new `noqa`.
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

### Subtask T024 – Row 3: retire `TestWorktreeTeardownSeamRouting`

- **Purpose**: The two tests re-derive the naming grammar by f-string (a copy pin), so a coherent grammar change reds them without any defect. They also misname the seam: the real teardown resolves through `executor._created_lane_worktree` (`src/specify_cli/consolidation/executor.py:722`) → `worktree_allocator.predict_lane_worktree`, not through a bare `branch_naming.worktree_path`. The covering guard already builds with the **real** allocator.
- **Files**: `tests/consolidation/test_mid8_embedded_preflight.py`.
- **Anchors**: the class at `:356-397`, with `test_embedded_mission_teardown_matches_allocator_path` at `:372` and `test_teardown_seam_matches_allocator_path_for_nnn_slug` at `:387` (the asserts at `:383` and `:396-397`).
- **Steps**:
  1. Baseline:
     ```bash
     uv run --frozen pytest tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_executor_lane_naming.py tests/lanes/test_branch_naming_seam.py -n0 -q
     ```
     Record the counts.
  2. **Violation plant FIRST** (C-002 proof; scratch edit). Make `_created_lane_worktree` compose its own path, e.g. insert a mid8 or a suffix, so it diverges from the allocator.
     - The covering guard `test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output` goes **RED**.
     - The two retired tests stay **GREEN**: they never call `_created_lane_worktree`, so they guard nothing the covering guard misses.

     Record both results, then revert with `git checkout -- src/specify_cli/consolidation/executor.py`.
  3. **Neutral plant** (required: data-model §3 `neutral_plant` for `delete-with-guard`): a coherent grammar change in `branch_naming.worktree_path` (scratch) reds today's `:383` but not the covering guard. That shows the retired form was a toll. Revert.
  4. Delete the class, and any import only it used (`worktree_path`?). Leave any class docstring references elsewhere in the file consistent.
  5. Re-run the baseline command. Everything is green, and the count drops by 2 (RK-1).
- **Edge cases**: If the covering guard does **not** go red under the plant, C-002 blocks the retirement. Rebuild the two cases instead with `shape_backfilled_legacy(...)` / `shape_mismatched_mid8(...)` from `tests/consolidation/_divergent_shapes.py`, asserting against `mission.lanes["lane-a"][0]` (the FIX alternative, pin-inventory §2.1 row 3), and report the switch.

### Subtask T025 – Row 4: rename and re-scope the unreachable-primary test

- **Purpose**: The test's name and docstring promise "surfaces instead of silent fail-open", but since `2f8a558e6c` (#4900) the seam **returns** the decided number and the **executor** refuses. The value is right; the name and contract text are stale.
- **Files**: `tests/consolidation/test_issue_4474_topology_aware_bake.py`.
- **Anchors**: `test_genuinely_unreachable_primary_surfaces_instead_of_silent_fail_open` at `:188-252`. `assert result == 1` is at `:244`, `assert state.mission_number_baked is False` follows it, and the merge-summary assertions come after.
- **Steps**:
  1. Rename it to the seam's actual contract, e.g. `test_unreachable_primary_returns_decided_number_unbaked_and_surfaces_it`.
  2. Rewrite the docstring. It should state the seam contract (it returns the decided number, leaves `mission_number_baked` False, and prints a merge-summary line) and **name the covering guard for the refusal half**: `tests/consolidation/test_mission_number_truthful_4900.py::test_absent_target_meta_refuses_instead_of_fabricating`.
  3. **Tighten the surfacing assertion, gated.** Today it accepts `"not" in joined.lower()`, which matches almost any sentence.
     - Tighten it **only** if the fragment is a named constant or an f-string field in `src/specify_cli/consolidation/ordering.py::_bake_mission_number_into_mission_branch`, and assert that (e.g. the mission slug field plus the constant).
     - **Never copy prose** into the test; that would create a new copy pin, the class this mission removes.
     - Otherwise leave it, and note why in the evidence.
  4. No value change: `result == 1` stays.
- **Planted breaks**:
  - **Violation A**: make the seam return `None` again on the unreachable path (scratch edit of `ordering.py`). The renamed test goes RED at the `result` assertion.
  - **Violation B**: make the executor write a `null` number silently when the target `meta.json` is absent (scratch edit in the executor's target-tree write). `test_absent_target_meta_refuses_instead_of_fabricating` goes RED.

  Revert both.
- **Parallel?**: Yes.

### Subtask T026 – Row 6: identity asserts instead of full-signature pins

- **Purpose**: `assert_called_once_with(exc, tmp_path, mission_branch="kitty/mission-m", base_sha=None)` pins the whole private signature of `_report_pre_mutation_refusal` (`executor.py:3897`) and `_recover_behind_head_primary_on_resume` (`:3971`). A new keyword **passed at the call sites** reds the sibling tests without any defect.
  - The mocks are `patch.object(ex, "…")` with **no autospec** (`:24`, `:291`, …). Adding a defaulted parameter to the *callee* alone therefore changes nothing in `call_args`, and cannot discriminate old from new.
- **Files**: `tests/consolidation/test_behind_head_recovery_coverage.py`.
- **Anchors**:
  - `:309`: `mock_recover.assert_called_once_with(exc, tmp_path, "01ID", mission_branch=...)`;
  - `:332`, `:384`, `:416`, `:435`: `mock_report.assert_called_once_with(exc|exc_after, tmp_path, mission_branch=..., base_sha=None)`. Note that `:384` and `:435` use **`exc_after`**.
  - `:362`: the threading test `test_preflight_with_recovery_threads_persisted_pre_mutation_target_sha_as_base_sha`, `…base_sha=persisted_sha)`.
- **Steps**:
  1. In each sibling (`:309`, `:332`, `:384`, `:416`, `:435`), replace the full-signature pin with what the test is about:
     ```python
     mock_report.assert_called_once()
     assert mock_report.call_args.args[0] is exc   # or exc_after where the original used it
     ```
     Keep any other assertion in the test unchanged.
  2. In `:362`, keep **one** explicit threading assertion, the #4933 contract:
     ```python
     mock_report.assert_called_once()
     assert mock_report.call_args.kwargs["base_sha"] == persisted_sha
     ```
     Check how the production call passes `base_sha` (keyword vs positional) before using `.kwargs`.
  3. Leave the `mock_pure_lag` / `mock_run_command` pins at `:227` and `:249` alone. They are not in the #5346 row; note them as outside scope if you judge them to be pins too.
- **Planted breaks**:
  - **Neutral (M2)**, scratch:
    - Add a defaulted keyword-only parameter `strategy: str | None = None` to `_report_pre_mutation_refusal` (`executor.py:3897`) **and pass it explicitly at both call sites**, `executor.py:4066` and `:4077`, e.g. `strategy=None`. `state` can be `None` on that path, so a literal is simplest; what the old pin trips on is the extra keyword in `call_args`.
    - For `:309`, do the same on `_recover_behind_head_primary_on_resume` (`:3971`, call site `:4060`).
    - **Old form** (stash your test change): `:332`, `:384`, `:416` and `:435` go RED under the `_report_pre_mutation_refusal` plant (4 failures), and `:309` goes RED under the `_recover_behind_head_primary_on_resume` plant (1 failure).
    - **New form**: GREEN with 0 test edits.
  - **Violation**: at the call site, pass `base_sha=None` instead of the loaded `pre_mutation_target_sha`. `:362` goes RED.

  Revert both.
- **Parallel?**: Yes.

### Subtask T027 – Plants, counts, hygiene, evidence

- **Purpose**: Assemble the FR-011 record for each row and run the verification.
- **Steps**:
  1. The full named-file run (see Test Strategy). All green.
  2. For each row, write one evidence record:
     - **#5346-3**: kind RETIRE. The covering guard `test_executor_lane_naming.py::test_created_lane_worktree_matches_real_allocator_output` is red under the plant, and the retired tests are green under it.
     - **#5346-4**: kind FIX. Violation A is red on the renamed test. Violation B is red on the 4900 guard.
     - **#5346-6**: kind FIX. The neutral plant (the new keyword passed at the call sites) stays green with 0 edits; the old form was red on it (4 `mock_report` failures plus 1 `mock_recover` failure). The violation plant is red at `:362`.
  3. Pin-inventory items get their `disposition`, `invariant_form` and `covering_guard` fields (data-model §3).
  4. `make test-fast` once.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_behind_head_recovery_coverage.py tests/consolidation/test_executor_lane_naming.py tests/consolidation/test_mission_number_truthful_4900.py tests/lanes/test_branch_naming_seam.py -n0 -q
uv run --frozen ruff check tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_behind_head_recovery_coverage.py
uv run --frozen ruff format --check tests/consolidation/test_mid8_embedded_preflight.py tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_behind_head_recovery_coverage.py
make test-fast
```

## Risks & Mitigations

- **Row 3's covering guard might not bite the planted divergence.** The C-002 fallback is described in T024; switch to FIX and report.
- **Over-tightening row 4's message assertion** turns it into a new copy pin. Assert one stable fragment only.
- **`exc_after` vs `exc`**: copy the right identity per test, or the identity assertion reds for the wrong reason.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- Re-run the row-3 violation plant: the covering guard is RED, and the retired class, checked out from the base, is GREEN.
- Re-run the row-6 neutral plant: 0 test edits, green.
- The renamed row-4 test's docstring names the executor refusal guard.
- There are no `src/` changes in any commit.

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
spec-kitty agent tasks mark-status T024 T025 T026 T027 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP06 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
