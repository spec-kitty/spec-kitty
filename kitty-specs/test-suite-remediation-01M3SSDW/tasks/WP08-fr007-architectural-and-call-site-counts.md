---
work_package_id: WP08
title: 'FR-007 class: architectural and live-source call-site counts'
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-011
- NFR-003
- NFR-005
- C-001
- C-002
- C-003
- C-007
- SC-004
- SC-005
- NFR-004
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: d92ef539b8a51c6efae84eaa6423675fbf98076a
created_at: '2026-09-30T21:33:09.675755+00:00'
subtasks:
- T033
- T034
- T035
- T036
- T037
- T038
- T039
phase: Phase 2 - Pin honesty
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_no_absolute_event_timestamp_mixture.py
- tests/architectural/test_remediation_effectiveness.py
- tests/architectural/test_tracker_egress_guards_3108.py
- tests/runtime/test_bridge_decision_builder.py
- tests/git/test_guard_capability_regression.py
- tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – FR-007 class: architectural and live-source call-site counts

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

- **FR-007 (pin-inventory groups G4 + G5)**: Exact counts of live structure are converted to invariant forms, or retired behind named covering guards:
  - **F9, RETIRE**: the prose-denominator test (`len(_MIXTURE_FILES) == 2`, `len(_MIXTURE_FUNCTION_PAIRS) == 14`), with the counts stripped from the docstring.
  - **F11, CONVERT (per-site partition)**: three `== *_FLOOR` pins plus an exact sum (`== 9`) become a **per-site** partition (`has_remediation or state in _PASS_STATES or (f, s) in _EXEMPT_STATES` for every construction site). The floors become `>=`, counted over sites.
  - **F12a, RETIRE**: `EXPECTED_ENCLOSING_COUNT` is redundant with the set equality at `:1150`.
  - **F12b, KEEP (contract)**: `EXPECTED_CALL_EXPRESSION_COUNT` is an audited egress census (#3108/#3030). Record the disposition; do not change the value.
  - **F3, CONVERT**: `len(materialize_calls) == 29` (7 re-pins) becomes a floor `>= 1`. The invariant lives in the AST absence scan at `:442`.
  - **F6, CONVERT**: drop `expected_sites` from the parametrize table and assert `>= 1` per row. The per-site REFUSED loop is the contract.
  - **F8, RETIRE**: `test_member_count` (`== 16`), behind `:31` and `:48`.
- **NFR-003**: A legitimate addition leaves every converted gate green with 0 test edits. A violation reds it.
- **FR-011 / C-002**: Each retirement is proven by its covering guard going red on the same plant.
- **C-003**: No ratchet is loosened. These are pins, not ratchets (research R3).

## Context & Constraints

- Read first: `plan.md` IC-07 and the RK-1 ruling; `research.md` "Pin dispositions" rows F3, F6, F8, F9, F11, F12a and F12b; `research/pin-inventory.md` §2.3, which gives each row's neutral and violation plant.
- **Format-excluded** (edit without `ruff format`):
  - `tests/architectural/test_no_absolute_event_timestamp_mixture.py`;
  - `tests/architectural/test_tracker_egress_guards_3108.py`;
  - `tests/git/test_guard_capability_regression.py`.
- **Not excluded** (run `ruff format --check`):
  - `tests/architectural/test_remediation_effectiveness.py`;
  - `tests/runtime/test_bridge_decision_builder.py`;
  - `tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py`.
- **RK-1**: F8, F9 and F12a reduce executed-test or assertion counts. C-002 and FR-011 sanction this.
- **Architectural gate files are run by name**, never as a directory.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP08 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **Planted breaks never land (C-007).** Product plants in `src/` are **scratch edits**; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**:
   - For a convert: the neutral plant stays green with 0 test edits (the old form reds on it), and the violation plant reds the new form.
   - For a retire: the covering guard reds on the plant. If it stays green, stop (C-002) and report.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP08 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" <owned files>`. Each hit carries a reason.
6. **Quality (NFR-005).** `uv run --frozen ruff check` on all six files, and `ruff format --check` on the three non-excluded files. Keep complexity ≤ 15; the F11 partition helper may need extraction. Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md).
9. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits. One commit per row (F-id) is preferred.

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

### Subtask T033 – F9: retire the prose-denominator test

- **Purpose**: `test_recorded_denominator_matches_docstring_claim` (`:416-421`) checks that the docstring's "2 files / 14 functions" matches `len()` of two module constants. It checks prose, not code (1 re-pin, `0f63d3ae2e` 13→14). The real contract is `test_derived_mixture_matches_recorded_baseline` (`:423`): set equality between the live AST derivation and the recorded baseline, in both directions.
- **Files**: `tests/architectural/test_no_absolute_event_timestamp_mixture.py` (format-excluded).
- **Steps**:
  1. Delete the test.
  2. In the module docstring (`:95-105`), replace "* **2 files**: … * **14 test functions**: …" with prose that names the constants (`_MIXTURE_FILES`, `_MIXTURE_FUNCTION_PAIRS`) **without numbers**, e.g. "recorded as literal, checked-in constants below…".
- **C-002 proof**: add a new mixture function to a scanned test file without recording it (scratch). Pick a file `_derive_mixtures` scans: an `at=`-keyword `StatusEvent` call mixing absolute timestamps. `test_derived_mixture_matches_recorded_baseline` goes RED on growth. The retired test stayed GREEN on it, because it counts the constants, not the tree.
- **Parallel?**: Yes.

### Subtask T034 – F11: partition invariant for remediation effectiveness

- **Purpose**: Three pins (`len(discovered) == _REMEDIATION_STATE_FLOOR` at `:325`, `len(producers) == _PRODUCER_FLOOR` at `:335`, `len(_EXEMPT_STATES) == _EXEMPTION_FLOOR` at `:341`) plus an exact sum `_REMEDIATION_STATE_FLOOR + _EXEMPTION_FLOOR == 9` at `:403`. The sum was added to close the reviewer's exploit (`:348-360`): turn a real state's `remediation=` into `None` without declaring it exempt, drop the floor and delete its `_CASES` entry. A **partition** closes that exploit by construction, with no pinned sum.
- **Files**: `tests/architectural/test_remediation_effectiveness.py`.
- **Anchors**:
  - `_discover_producers` at `:133`;
  - `_discover_remediation_emitting_states_full` at `:150`, returning `(lineno, function, state)` for states that emit a non-`None` remediation;
  - `_discover_remediation_emitting_states` at `:220`;
  - `_EXEMPT_STATES` at `:280`;
  - the floors at `:304`, `:308` and `:320`;
  - `_CASES` at `:615`;
  - `test_case_table_matches_ast_derived_states` at `:626`.
- **Why per-site (B2, verified by AST enumeration on HEAD)**:
  - `computer.py` constructs 5 non-emitting **pass-state** pairs that are not in `_EXEMPT_STATES`: `(_compute_charter_source, fresh)`, `(_compute_synced_bundle, fresh)`, `(_synthesized_drg_built_in_only_state, built_in_only)`, `(_synthesized_drg_missing_graph_state, built_in_only)` and `(_synthesized_drg_graph_state, fresh)`. A pair-level `all_states == emitting | _EXEMPT_STATES` is RED on day one.
  - `emitting` pairs number 4, while `_REMEDIATION_STATE_FLOOR` (7) counts **sites**.
  - A pair-level partition also lets the documented exploit survive on a **split** site. The two `missing` sites of `_compute_charter_source` share one pair, so neutering one of them keeps the pair "emitting".
- **Steps**:
  1. **One walker, per site.** Factor the AST walk in `_discover_remediation_emitting_states_full` into one walker that visits **every** `FreshnessSubState(...)` construction site in the scanned producers. It yields `(lineno, function, state, has_remediation)`, one tuple per site. Derive the existing emitting views from it. Keep each function at complexity ≤ 15.
     - Fail closed: if the walker meets a construction whose `state` it cannot read as a literal, it raises rather than skipping the site.
  2. **Per-site partition**, replacing the three `==` floor tests and the `== 9` sum. For **every** site:
     ```python
     assert has_remediation or state in _PASS_STATES or (function, state) in _EXEMPT_STATES, (lineno, function, state)
     ```
     `_PASS_STATES` is already imported from `specify_cli.charter_runtime.preflight.runner` at `:109`.
     - **Disjointness**: no **emitting** site's `(function, state)` is in `_EXEMPT_STATES`.
     - The existing `test_case_table_matches_ast_derived_states` (`:626`) already asserts that `_CASES` covers the emitting sites minus the exemptions. Keep it; it is the `emitting == set(_CASES)` half.
     - **Non-vacuity floors counted over SITES**, `>=`: `len(emitting_sites) >= _REMEDIATION_STATE_FLOOR`, `len(producers) >= _PRODUCER_FLOOR` and `len(_EXEMPT_STATES) >= 1`. Keep the constants as floors, and update their comments to say "floor over sites (non-vacuity), not a pin".
  3. **Keep** the `expected_exempt == _EXEMPT_STATES` identity check (`:389-394`). It is a reviewed membership decision, not a count, and it is out of FR-007 scope. Delete only the `== 9` sum and its long comment, replaced by one comment pointing to the per-site partition.
- **Planted breaks** (scratch edits of the charter status computer that the walker scans; find the path from the module constants):
  - **Violation, the split-site exploit (B2; the case the old `== 9` caught)**: set `remediation=None` on **one** of the two `missing` sites of `_compute_charter_source` (e.g. the `_REMEDIATE_UPGRADE_YES` site), lower `_REMEDIATION_STATE_FLOOR` to 6 and delete its `_CASES` row. The **per-site partition** goes RED: that site has no remediation, `missing` is not a pass state, and the pair is not exempt.
  - **Violation, the documented exploit on a single-site state**: the same neutering on a single-site emitting state. The partition reds.
  - **Swap exploit** (`:376-388`): swap one exempt member for a real emitting pair. The disjointness assertion reds, and the identity check reds too.
  - **Neutral**: add a new emitting site together with its `_CASES` entry. Everything stays green with 0 test edits. The old `== _REMEDIATION_STATE_FLOOR` and `== 9` would have red.
- **Edge cases**: A new **pass-state** site (e.g. a new `fresh` branch) is legitimate and stays green through `_PASS_STATES`. A new non-pass, non-emitting site must be declared in `_EXEMPT_STATES` (a reviewed act).

### Subtask T035 – F12: retire `EXPECTED_ENCLOSING_COUNT`; keep `EXPECTED_CALL_EXPRESSION_COUNT`

- **Purpose**: `EXPECTED_ENCLOSING_COUNT = 5` (`:947`) duplicates `len(EXPECTED_ENCLOSING_FUNCTIONS)`, which the set equality at `:1150` already enforces. `EXPECTED_CALL_EXPRESSION_COUNT = 5` (`:965`) is a **genuine contract cardinality**: each extra call expression is a new egress point that must be reviewed (#3108/#3030), and it moved only when egress sites changed.
- **Files**: `tests/architectural/test_tracker_egress_guards_3108.py` (format-excluded).
- **Steps**:
  1. Delete `EXPECTED_ENCLOSING_COUNT` and its comment block, and the `assert len(real.enclosing) == EXPECTED_ENCLOSING_COUNT` at `:1158`.
  2. Replace its remaining uses in messages (`:1152`, `:1235`) with `len(EXPECTED_ENCLOSING_FUNCTIONS)`.
  3. **Do not change** `EXPECTED_CALL_EXPRESSION_COUNT`, its assertion (`:1159`) or the G4 mutation tests (`:1228-1235`). Record the KEEP disposition with its reason.
  4. Run the file. All green.
- **C-002 proof**: remove one function from the live enclosing set (scratch: drop an egress verdict call inside one enclosing function in `src/`, keeping the rest). The set equality at `:1149-1150` reds. The mutation tests stay meaningful.
- **Evidence**: F12a RETIRE (covering guard `:1150`); F12b KEEP-contract (reason: audited egress census; each extra call expression is a new egress point, #3108/#3030; moved only with real egress changes). Optional follow-up (research D-14): re-key as `{qualname: n}`. **Do not do it here.**

### Subtask T036 – F3: `materialize_calls` floor `>= 1`

- **Purpose**: `assert len(materialize_calls) == 29` (`:498`) counts `_materialize_decision(...)` call sites in the live `runtime_bridge` source: 7 re-pins (`5773a637a9` 21→22 … `8a64f60535` 28→29). The docstring's real invariant, "zero open-coded `Decision`", is `test_runtime_bridge_has_zero_raw_decision_constructions` (`:442`), an AST absence scan.
- **Files**: `tests/runtime/test_bridge_decision_builder.py`.
- **Steps**:
  1. Change the assert to `assert len(materialize_calls) >= 1`, with a message saying this is non-vacuity and the invariant is `:442`.
  2. Replace the per-site changelog docstring (the long history `:460-497`) with 2–3 lines: what the test checks (the builder is actually used) and where the real invariant lives.
  3. **`:510`** (`len(bare_decision_calls) == 3` in the cores module) was not re-pinned in the window. Leave it untouched and record "not in the recurring class; left by locality". Convert it only if you can do so in ≤ 10 lines as a qualname set ("every `Decision(` call lies inside one of the three named helpers") with its own planted break.
- **Planted breaks**:
  - **Neutral**: add a new `_materialize_decision(...)` site in `runtime_bridge.py` (scratch). Green; the old `== 29` reds.
  - **Violation**: add `Decision(...)` directly in `runtime_bridge.py` (scratch). `:442` reds.
  - **Vacuity**: rename every `_materialize_decision` call (scratch, e.g. through an alias). The floor reds.

### Subtask T037 – F6: drop `expected_sites`; per-row floor `>= 1`

- **Purpose**: `test_status_bookkeeping_call_sites_are_refused_on_protected_destination` (def at `:154`) parametrizes `(module_rel, callee, expected_sites)` over 5 rows (`:115-150`) and asserts `len(capabilities) == expected_sites` (`:165-170`). It was re-pinned 2→4→3 in one day. The contract is the per-site loop "every site is REFUSED on a protected ref" (`:172-180`), which already covers every site.
- **Files**: `tests/git/test_guard_capability_regression.py` (format-excluded).
- **Steps**:
  1. Change the parametrize signature to `("module_rel", "callee")` and drop the third element from all 5 rows. Keep the explanatory comments that describe **why** each site exists; delete comments that only narrate count re-pins ("Re-pinned 2 -> 4 …", "Re-pinned 4 -> 3 …").
  2. Replace the count assert with `assert capabilities, f"no {callee} call site found in {module_rel} — the parity test would pass vacuously"`.
  3. Keep the REFUSED loop unchanged.
- **Planted breaks**:
  - **Neutral**: add a STANDARD call site of `_bootstrap_canonical_state_via_mission` in `mission_finalize.py` (scratch). Green; the old count reds.
  - **Violation**: add a call site passing `capability=GuardCapability.<a protected-flow member>` (scratch). The loop reds.
  - **Vacuity**: remove all sites for one row (scratch). The floor reds.

### Subtask T038 – F8: retire `test_member_count`

- **Purpose**: `test_member_count` (`:73-77`) pins `len(list(MissionReviewDiagnostic)) == 16` (3 re-pins). The contract is "every code is documented":
  - `test_all_diagnostic_members_documented` (`:31`);
  - `test_section_count_matches_member_count` (`:48`), which is relational: sections equal members.
- **Files**: `tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py`.
- **Steps**: Delete `test_member_count`, then run the file.
- **C-002 proof**:
  - **Violation**: add an enum member to `MissionReviewDiagnostic` without an `ERROR_CODES.md` section (scratch). `:31` reds, and so does `:48`.
  - **Neutral**: add a member **with** its section (scratch, both files). Green; the old test reds.

### Subtask T039 – Plants, counts, evidence

- **Steps**:
  1. The full named-file run (Test Strategy). All green.
  2. One evidence record per row: F3 FIX, F6 FIX, F8 RETIRE, F9 RETIRE, F11 FIX, F12a RETIRE, F12b KEEP-contract. Each gets its plants, results and covering guard. Also fill the pin-inventory item fields (data-model §3): `disposition`, `invariant_form`, `neutral_plant`, `violation_plant` and `keep_reason`.
  3. `make test-fast` once.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_no_absolute_event_timestamp_mixture.py tests/architectural/test_remediation_effectiveness.py tests/architectural/test_tracker_egress_guards_3108.py tests/runtime/test_bridge_decision_builder.py tests/git/test_guard_capability_regression.py tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py -n0 -q
uv run --frozen ruff check tests/architectural/test_no_absolute_event_timestamp_mixture.py tests/architectural/test_remediation_effectiveness.py tests/architectural/test_tracker_egress_guards_3108.py tests/runtime/test_bridge_decision_builder.py tests/git/test_guard_capability_regression.py tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
uv run --frozen ruff format --check tests/architectural/test_remediation_effectiveness.py tests/runtime/test_bridge_decision_builder.py tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py
make test-fast
```

## Risks & Mitigations

- **F11's per-site walker misses a construction shape** and silently shrinks the partition. Make it fail closed. The split-site exploit (B2) and the documented exploit must both stay red.
- **Deleting F6's history comments** loses useful "why this site exists" context. Keep the why, drop only the count narration.
- **F12b is a KEEP.** Do not "fix" it; record it.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- Re-run the F11 split-site exploit yourself (neuter one of the two `_compute_charter_source` `missing` sites, floor 6, `_CASES` row deleted): RED (quickstart #16).
- Re-run the F8 violation: `:31` RED.
- `EXPECTED_CALL_EXPRESSION_COUNT` is unchanged, and its KEEP reason is recorded.
- Every converted form stays green under its neutral plant with 0 test edits.

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
spec-kitty agent tasks mark-status T033 T034 T035 T036 T037 T038 T039 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP08 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
