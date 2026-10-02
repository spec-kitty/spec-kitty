---
work_package_id: WP20
title: Extend the write-side rederivation gate; pin the commit-outcome consumer list
dependencies:
- WP06
- WP07
- WP08
- WP09
- WP10
- WP13
- WP14
- WP15
- WP16
- WP18
requirement_refs:
- FR-014
- FR-007
- SC-005
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-02T16:08:09.150210+00:00'
subtasks:
- T106
- T107
- T108
- T109
- T110
phase: Phase 7 - Gates and end-to-end
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_no_write_side_rederivation.py
create_intent:
- tests/coordination/test_commit_outcome_consumer_pin.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/_baselines.yaml
- tests/architectural/test_ratchet_baselines.py
- tests/coordination/test_commit_outcome_consumer_pin.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP20 – Extend the write-side rederivation gate; pin the commit-outcome consumer list

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

This WP closes the defect class "a COORD-partition writer derives its write location from a read resolver" **by construction** (FR-014, charter Standing Order 5, DIRECTIVE_043). It also pins the commit-outcome consumer list so that no consumer can drift back to hand-formatting or masking surface outcomes (FR-007, contracts/commit-outcome.md rule 6).

Done means all of the following hold:

- `tests/architectural/test_no_write_side_rederivation.py` gains a **third grammar**, `test_coord_writers_do_not_derive_write_location_from_read_resolver`. It is an extension of the existing gate family; no new gate file is added (spec FR-014, squad finding P10).
- The grammar scans a **concrete floor of at least 22 live writer functions** (the census in research D18). Every scanned `(rel_path, qualname)` resolves to a live definition, and a stale qualname turns the gate red.
- The gate is **proven red at base** (`ecb5dd914a`) on real offenders: at least `decisions/emit.py::_mission_dir` and `decisions/service.py::_mission_dir`. The output is pasted in the activity log for the PR.
- A **planted-mutation bite test** reds the scan when `read_dir(MissionArtifactKind.STATUS_STATE)` is planted in a synthetic writer.
- The allowlist is a **shrink-only** `ContentDescriptor` mechanism that starts **empty** (operator ruling Q4). Its cap is 0 under a new `test_no_write_side_rederivation:` key in `tests/architectural/_baselines.yaml`, registered in `test_ratchet_baselines.py`'s `_SIZE_RATCHETS` table, so adding any entry reds. A stale-entry twin guard is wired in.
- `tests/coordination/test_commit_outcome_consumer_pin.py` asserts with AST that every research D8 consumer renders through `render_commit_outcome` or `commit_outcome_payload`. It has a floor and a bite test.
- The new gate is **green on this WP's final commit**, because WP07-WP10, WP14-WP16, WP06 and WP18 migrated every census writer.

## Context & Constraints

- **Spec**: FR-014 (the gate), FR-007 (the consumer pin), SC-005 ("the extended gate is red at `ecb5dd914a` on real offenders and red on its planted mutation"). Constraint C-006 applies: no heavy suites.
- **Plan**: IC-15 (gate), IC-07 (consumer-list pin test). The shared-file map says this gate goes green only after IC-04 and IC-18.
- **Research**:
  - D18 has the grammar, the floor, the forbidden tokens, the allowlist, the red-at-base proof, the self-mutation and the twin.
  - D8 has the consumer table.
  - D21 explains why the consolidation and `materialize` sites migrate rather than being allowlisted.
  - R19 is the red-first id for this gate.
- **Contracts**: `contracts/commit-outcome.md` (rule 6, the consumer list) and `contracts/write-location-accessor.md` ("`read_dir` is never a write location for a COORD kind; the FR-014 gate enforces that").
- **Charter**: load `.kittify/charter/charter.md` and `spec-kitty charter context --action implement --json`. The relevant rules are Standing Order 5 (non-vacuous gate: concrete floor, self-mutation test, shrink-only allowlist; "a gate-unmask cannot self-validate"), the `architectural-gate-non-vacuity` and `frozen-baseline-shrink-only-ratchet` tactics, and the Burn-down Policy (`_baselines.yaml` growth fails CI).
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: say Mission, never feature. Name the sense of "primary": PRIMARY partition, repository root checkout, or target branch.
- **The existing file's anatomy** (re-verified at this WP's base; cite symbols if lines drift):
  - `_SRC = _REPO_ROOT / "src" / "specify_cli"` (L77). The new grammar also scans `src/runtime/next/runtime_bridge.py` (outside `_SRC`), so resolve paths from `_REPO_ROOT`.
  - `_ALLOW_LIST_SEED: tuple[ContentDescriptor, ...]` (L175), keyed via `resolve_descriptor` into `_ALLOW_LIST_KEYS` / `_ALLOW_LIST` (L210-216), looked up with `_seed_and_key_for` (L219).
  - The planted bite test `test_ratchet_bites_on_planted_rederivation` (L307-336, parametrized from L307).
  - The staleness twins `test_checkout_head_selector_entry_is_still_a_live_finding` (L428) and `test_checkout_grammar_allow_list_entries_are_still_live` (L973), both through `descriptor_still_live`.
  - Helpers come from `tests/architectural/_ratchet_keys.py` (`ContentDescriptor`, `CompositeKey`, `composite_key`, `resolve_descriptor`, `descriptor_still_live`) and `tests/architectural/_ast_scan.py` (`parse_source`, `read_source`).
- **The baselines table**: `tests/architectural/test_ratchet_baselines.py` holds the ONE size-ratchet table `_SIZE_RATCHETS` (≈L149). `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` (≈L478) reds any `_baselines.yaml` leaf without a row. A new yaml leaf therefore needs a matching `_SizeRatchet(...)` row, which is why that file is in this WP's `owned_files` (deviation from the plan's file list; it is required by the existing meta-gate).
- **Brownfield scout (binding read)**: before coding, read `## WP20` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`). Start with `spec-kitty agent action implement WP20 --agent claude`. Consume the resolved workspace path; never reconstruct it.
- Lane notes:
  - This WP shares no owned file with any other WP, so it gets its own lane.
  - It depends on ten writer and consumer WPs. Its lane base therefore stacks those lanes, and the gate scans the merged result. If a dependency is not approved yet, `implement` refuses (dependency gating). Do not work around that.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T106 – Third grammar: COORD writers must not derive a write location from a read resolver

- **Purpose**: Add the grammar that FR-014 requires and that research D18 specifies. It is an AST scan scoped to the census writer functions, flagging forbidden read-resolver calls inside them. R19 is `test_coord_writers_do_not_derive_write_location_from_read_resolver`.
- **Steps**:
  1. Add a module-level constant `_COORD_WRITER_CENSUS: tuple[tuple[str, str], ...]` of `(rel_path_from_repo_root, qualname)` pairs. Start from research D18's list and **re-derive every qualname from the merged code**. Several WPs renamed or extracted functions; for example, WP01 extracted a helper from `_ft_apply_writes`, and WP07 retired `_coord_feature_dir`. The gate must scan the function that NOW holds the write. Starting list:
     - `src/specify_cli/decisions/emit.py::_mission_dir`
     - `src/specify_cli/decisions/service.py::_mission_dir`
     - `src/specify_cli/agent_tasks_ports.py::RealCoordCommitRouter.feature_write_dir`
     - `src/specify_cli/cli/commands/agent/tasks_mark_status.py::_ms_resolve_read_dir`, or its write-side successor
     - `src/specify_cli/cli/commands/agent/tasks_finalize.py::_ft_apply_writes`, plus the WP01 helper if the write moved there
     - `src/specify_cli/cli/commands/agent/mission_finalize.py::_emit_local_canonical_events`
     - `src/specify_cli/review/cycle.py::_review_cycle_wp_dir`
     - `src/specify_cli/retrospective/tracer_writer.py::_local_staging_path`
     - `src/specify_cli/tasks/issue_matrix.py::scaffold_issue_matrix`
     - `src/specify_cli/cli/commands/agent/acceptance_verdict.py::_matrix_read_dir`
     - `src/specify_cli/coordination/status_transition.py::_coord_feature_dir`, or its successor
     - `src/specify_cli/coordination/transaction.py::BookkeepingTransaction._acquire_locked`
     - `src/runtime/next/runtime_bridge.py::_wrap_with_decision_git_log`
     - `src/specify_cli/cli/commands/accept.py::_coord_status_feature_dir`
     - `src/specify_cli/cli/commands/retrospect.py::_canonical_events_path`
     - `src/specify_cli/cli/commands/agent_retrospect.py::_canonical_events_dir`
     - `src/specify_cli/core/mission_creation.py::_emit_create_events`
     - `src/specify_cli/consolidation/executor.py::_phase_baseline_and_surface`
     - `src/specify_cli/consolidation/executor.py::_run_lane_based_consolidation`
     - `src/specify_cli/cli/commands/materialize.py::_resolve_selected_dir`
     - `src/specify_cli/cli/commands/materialize.py::materialize`
     - `src/specify_cli/lanes/recovery.py::reconcile_status`
  2. Implement `_scan_coord_writer(source, rel_path, qualname) -> list[_CoordWriterFinding]`. Parse with `parse_source`, locate the function node by dotted qualname (class then method), and walk only that function body, nested defs included. Flag any `ast.Call` whose callee name is one of:
     - `read_dir`, but only when its first positional argument (or the `kind=` keyword) names a COORD `MissionArtifactKind` attribute: `STATUS_STATE`, `DECISION_LOG`, `TRACER_FILE`, `REVIEW_CYCLE`, `ISSUE_MATRIX` or `ACCEPTANCE_MATRIX`. A `read_dir(PRIMARY_METADATA)` in a writer is NOT flagged; that is the ledger/planning PRIMARY read.
     - `read_dir_for`, `candidate_feature_dir_for_mission`, `resolve_feature_dir_for_mission`, `resolve_status_surface`, `resolve_status_surface_with_anchor`, `coord_read_dir_for`.
     - Composition of `KITTY_SPECS_DIR` onto a coordination worktree: a `BinOp(Div)` whose operand chain contains the `KITTY_SPECS_DIR` name and a name or attribute containing `worktree`. Keep this heuristic narrow and document it in the docstring.
  3. Callee-name extraction follows the existing `_checkout_grammar_callee_name` (≈L547): handle `Name` and `Attribute` (`seam.read_dir`, `placement_seam(...).read_dir`).
  4. The test iterates the census, collects findings, filters out composite keys in the new allowlist (T108), and asserts none remain. Its failure message lists `rel_path::qualname:line callee` per offender.
- **Files**: `tests/architectural/test_no_write_side_rederivation.py` only.
- **Validation**: green on this WP's base, which already contains all writer migrations. Red in T107 against `ecb5dd914a`.
- **Edge cases**:
  - A writer that reads its own log *before* appending (retrospect, `tasks_mark_status`) was split by WP14 and WP08 into a read helper and a write helper. The census names the write-side function. Do NOT add the read helper; reads legitimately keep the read resolver (C-002).
  - `materialize::materialize` contains the all-Missions loop. A `read_dir(PRIMARY_METADATA)` or `meta.json` read there is fine, and only the COORD-kind call matters.
  - If `_coord_feature_dir` was deleted outright (WP07), list the function that replaced its call sites. The census floor counts live functions, not names from the plan.
  - Use a `pytest.mark.architectural` marker (already module-level `pytestmark`).

### Subtask T107 – Non-vacuity: floor assertion and red-at-base proof

- **Purpose**: A gate whose scan list silently shrinks, or whose target functions vanished, would pass vacuously. Charter Standing Order 5: "a gate-unmask cannot self-validate". The red-at-base proof must come from running the gate against the pre-fix source, not from the gate itself.
- **Steps**:
  1. Add `test_coord_writer_census_floor_is_live`:
     - assert `len(_COORD_WRITER_CENSUS) >= 22`;
     - assert every pair resolves to exactly one live `FunctionDef`/`AsyncFunctionDef` (`qualname` lookup returns a node), so a stale qualname reds with a message naming the pair and the remedy ("re-point the census at the function that now holds the write; never delete it to green").
  2. Make the scanner root injectable for the proof: `_scan_census(repo_root: Path)`, where the test passes `_REPO_ROOT`. For the base run, an env var such as `SPEC_KITTY_GATE_SCAN_ROOT` lets you point the scan at another tree, used only manually.
  3. Produce the red-at-base proof:
     ```bash
     git -C <repo> worktree add /tmp/wp20-base ecb5dd914a
     SPEC_KITTY_GATE_SCAN_ROOT=/tmp/wp20-base \
       uv run --frozen pytest tests/architectural/test_no_write_side_rederivation.py \
       -k coord_writers_do_not_derive -q
     git -C <repo> worktree remove /tmp/wp20-base
     ```
     At base, census qualnames that did not exist yet must not abort the proof. The base run skips the floor and reports "absent at base" for missing qualnames. It must report findings at least for `src/specify_cli/decisions/emit.py::_mission_dir` (≈L88, `read_dir(STATUS_STATE)`) and `src/specify_cli/decisions/service.py::_mission_dir` (≈L246).
  4. Paste the full red output (offender lines and exit code) into the activity log and the PR body's *Tests run* section.
- **Files**: the gate file.
- **Validation**: the floor test is green on the WP's final commit, and the base-proof run shows ≥ 2 real offenders.
- **Edge cases**:
  - Do not commit the env-var override as a test default.
  - Prefer the override over `PYTHONPATH`, because the scan reads source files and imports nothing.
  - If you add the override, test its parsing with a narrow unit test (NFR-003).

### Subtask T108 – Shrink-only allowlist starting empty, with a baseline cap of 0

- **Purpose**: Operator ruling Q4. The consolidation executor and `materialize` sites were migrated (WP18), so the allowlist starts empty. Any future entry must be a visible, reviewed diff that also grows a baseline, and that growth fails CI.
- **Steps**:
  1. Add `_COORD_WRITER_ALLOW_LIST_SEED: tuple[ContentDescriptor, ...] = ()`, with a comment block in the style of L163-174 explaining that a new entry is a deliberate scope decision with a per-descriptor rationale. Also add `_COORD_WRITER_ALLOW_LIST_KEYS` / `_COORD_WRITER_ALLOW_LIST` mirroring L210-216 (empty tuples and frozensets type-check fine under mypy).
  2. Add a stale-entry twin `test_coord_writer_allow_list_entries_are_still_live`, modelled on `test_checkout_grammar_allow_list_entries_are_still_live` (L973): for each seed entry, `descriptor_still_live(...)` must hold. With an empty seed it iterates zero times, so also add the T109 bite test for the twin itself: construct an in-test `ContentDescriptor` targeting a non-existent token and assert `descriptor_still_live` returns `False`. The twin must not be vacuous.
  3. In `tests/architectural/_baselines.yaml`, add:
     ```yaml
     test_no_write_side_rederivation:
       coord_writer_allowlist: 0  # justification: FR-014 / ruling Q4 -- consolidation + materialize writers migrated, allowlist starts empty; any entry must grow this visibly.
     ```
     Follow the file's header policy (L12-16).
  4. In `tests/architectural/test_ratchet_baselines.py` `_SIZE_RATCHETS` (≈L149), add a row:
     `_SizeRatchet("test_no_write_side_rederivation", "coord_writer_allowlist", "tests.architectural.test_no_write_side_rederivation", "_COORD_WRITER_ALLOW_LIST_SEED")`,
     with a one-line comment citing this Mission.
- **Files**: the gate file, `_baselines.yaml`, `test_ratchet_baselines.py`.
- **Validation**: run `tests/architectural/test_ratchet_baselines.py` green. Planting one dummy seed entry locally must make the ratchet red; do that once, then revert and note it in the activity log.
- **Edge cases**:
  - `test_baseline_file_exists_with_required_keys` (≈L445) may require a section list. Read it and keep it consistent.
  - Do not widen any other existing baseline.

### Subtask T109 – Planted-mutation bite test for the new grammar

- **Purpose**: Prove the new grammar is not inert (R19's "red on its planted mutation"). This follows the L307-336 pattern.
- **Steps**:
  1. Add `test_coord_writer_grammar_bites_on_planted_read_resolver`, parametrized over at least these plants:
     - `seam.read_dir(MissionArtifactKind.STATUS_STATE)`
     - `placement_seam(repo_root, slug).read_dir(MissionArtifactKind.TRACER_FILE)`
     - `resolve_feature_dir_for_mission(repo_root, slug)`
     - `candidate_feature_dir_for_mission(repo_root, slug)`
     - `resolve_status_surface(repo_root, slug)`
     - `coord_read_dir_for(...)`
     - `worktree / KITTY_SPECS_DIR / slug`
  2. Embed each plant in a synthetic `def _synthetic_writer(...)` source string. Run `_scan_coord_writer(source, "src/specify_cli/synthetic.py", "_synthetic_writer")` and assert at least one finding with the expected callee.
  3. Add negative controls in the same style as `test_ratchet_ignores_prose_quoting_a_prior_walk` (L339):
     - a docstring or comment quoting `read_dir(MissionArtifactKind.STATUS_STATE)` → no finding;
     - `read_dir(MissionArtifactKind.PRIMARY_METADATA)` → no finding;
     - `write_dir(MissionArtifactKind.STATUS_STATE)` → no finding. This is the sanctioned accessor, and the control proves the gate does not ban the fix.
- **Files**: the gate file.
- **Validation**: all plants red, all controls green. Mutation check: temporarily empty the forbidden-callee set and confirm the bite test fails, then restore it.
- **Edge cases**: AST only, so prose is never a `Call` node. Keep the synthetic sources valid Python.

### Subtask T110 – Consumer-list pin for the commit-outcome contract

- **Purpose**: contracts/commit-outcome.md rule 6 says "Every consumer renders through `render_commit_outcome` (text) or `commit_outcome_payload` (JSON). No consumer formats surface outcomes by hand. A test pins the consumer list from research D8." Masking lived in the shared contract (#5513, #5501), so the pin keeps it from coming back.
- **Steps**:
  1. Create `tests/coordination/test_commit_outcome_consumer_pin.py` with `_CONSUMERS: tuple[tuple[str, str], ...]` of `(rel_path, qualname)` for each D8 site, re-derived from the merged code. The D8 sites are:
     - setup-plan: `mission_setup_plan.py`, the functions around L237 / L892 / L951;
     - record-analysis: `mission_record_analysis.py::record_analysis` or the private helper WP14 extracts from it (see Binding corrections);
     - the report transaction helper in `git/report_transaction.py` (WP01 extracted it);
     - the orchestrator API site (`orchestrator_api/commands.py`, ≈L3018);
     - acceptance: `acceptance/__init__.py` ≈L1791 and ≈L1822, and `acceptance/matrix.py` ≈L524;
     - `coordination/write_seam.py`, plus `tasks/issue_matrix.py` and `retrospective/tracer_writer.py`;
     - finalize: `mission_finalize.py::_apply_finalize_commit_router_result` and the pin-refresh consumer;
     - retrospect: `retrospect.py`, ≈L315;
     - spec-commit: the `spec_commit_cmd.py` render helper;
     - the tasks ports: `agent_tasks_ports.py`, `review/cycle.py` ≈L712, ~~`tasks_mark_status.py` ≈L279~~ (struck: dead shim, mark-status commits nothing), `tasks_map_requirements.py` ≈L668;
     - accept: the residual committer in `accept.py`.
     Discarded-result sites render only a warning, but they still call the shared renderer, so they are in scope.
  2. AST assertion, per consumer function: it calls `render_commit_outcome`, `commit_outcome_payload`, or a thin wrapper defined in `commit_outcome.py` (allow `commit_outcome_exit_code` as a companion, not a substitute). Also:
     - assert no consumer function references the attribute names of `SurfaceOutcome`'s rendered fields (`.committed`, `.skipped`, `.refused`) inside an f-string or `str.format` call. That would be hand formatting.
     - add a floor `len(_CONSUMERS) >= 14` (D8 counts 14 sites) plus a liveness check that each pair resolves.
  3. Bite test: a synthetic consumer that formats `f"{outcome.refused}"` and never calls the renderer must be flagged.
- **Files**: `tests/coordination/test_commit_outcome_consumer_pin.py` (new).
- **Validation**: green on the final commit; the bite test reds its plant.
- **Edge cases**:
  - Wrappers such as `WriteSeamResult` / `CommitArtifactResult` only pass `surfaces` through. Their *callers* render, so the pin names the callers.
  - If a consumer legitimately renders via a module-local helper, pin the helper and assert the consumer calls it. Document this in a comment.
- **Additional consumer (post-tasks squad R-M2)**: add `cli/commands/agent/tracer_append.py` (migrated in WP10) to the pinned `_CONSUMERS` floor.
- **Legacy root-staging copy note (P-M2)**: the router's legacy `shutil.copy2` root-staging copy is a recorded **post-consolidation fold** (tasks.md). Add a comment in the gate module pointing at it, so the follow-up is visible where the class is guarded. Do not allowlist it.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Gate fix (operator decision; scout X3)**: `test_no_worktree_name_guess.py` explicitly excludes `.parent.parent` (L474-476, #2007). This WP therefore extends **`test_no_write_side_rederivation.py`'s scanned-module list** (`_ADOPTED_MODULES`, L87-111) to every `write_dir` consumer module, with a **`.parent.parent`-from-`WriteLocation` ban**: any `.parent.parent` on an expression derived from `write_dir(...)` / `WriteLocation.path` reds; use `checkout_root`.
  - **Modules to add**: `decisions/emit.py`, `decisions/service.py`, `decisions/fork.py`, `events/decision_log.py`, `runtime/next/runtime_bridge.py` (outside `_SRC`, so resolve from the repo root), `review/cycle.py`, `cli/commands/accept.py`, `cli/commands/_decisions_doctor.py`, `consolidation/executor.py`, `cli/commands/materialize.py`, `coordination/commit_router.py`, `coordination/coord_seed.py`, `coordination/transaction.py`, `lanes/recovery.py`, `retrospective/tracer_writer.py`, `tasks/issue_matrix.py`, `acceptance/matrix.py`, `acceptance/gates_core.py`, `cli/commands/agent/issue_verdict.py`, `cli/commands/agent/tasks_mark_status.py`, `agent_tasks_ports.py`, `cli/commands/retrospect.py`, `cli/commands/agent_retrospect.py`.
  - **Pre-existing `.parent.parent` occurrences** the extension surfaces: fix them if they sit in Mission-touched code; otherwise record them in a shrink-only sanctioned list with rationale (cap in `_baselines.yaml`). Add a bite test and a twin.
- **T110 consumer-list corrections**:
  - there is no `mission_record_analysis.py::_maybe_auto_commit`; the record-analysis consumer is `record_analysis` or the private helper WP14 extracted;
  - the retrospect consumer is `retrospect.py::_maybe_auto_commit` (L294);
  - `acceptance/matrix.py` ≈L524 is a `write_seam.write_artifact` consumer, so pin its caller;
  - the `report_transaction` and `spec_commit` helpers are WP14's and WP13's own extractions (not WP01's);
  - the accept consumer is WP16's private router-result helper;
  - `tracer_append.py` is WP10's;
  - mark-status has no live commit consumer, because WP08 dropped the dead L279 shim; remove it from the list.
- **Ratchet tests**: run `tests/architectural/test_ratchet_baselines.py` as a whole file. Its parametrized tests treat a cap-0 leaf with an empty live list as an edge case. Respect lazy module resolution (`test_fast_collection_does_not_import_round_trip_corpus`, L780).
- **Red evidence (analyze C2)**: red at `ecb5dd914a` on the real offenders (`decisions/emit.py::_mission_dir`, `decisions/service.py::_mission_dir`), plus the planted mutation. The proof is feasible now because both still hold `read_dir(STATUS_STATE)` at HEAD.
- **Legacy root-staging copy**: its retirement is an **in-mission closeout fold** (tasks.md "Closeout items"), not deferred. The gate-module comment points to it.

## Targeted test surface

Run only these, recording commands and pass/fail counts in the activity log for the PR's *Tests run* section:

```bash
uv run --frozen pytest tests/architectural/test_no_write_side_rederivation.py -q
uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -q
uv run --frozen pytest tests/coordination/test_commit_outcome_consumer_pin.py -q
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_write_surface_placement_guard.py \
  tests/architectural/test_status_events_writes_gate.py tests/architectural/test_status_state_read_dir_single_authority.py -q
make test-fast
```

Also run the base-revision proof from T107 against `ecb5dd914a` and paste its red output.

**Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).** CI's cross-cutting lane owns the full architectural sweep.

Baseline-red gotcha (CLAUDE.md): before treating a red as yours, check whether it is a pre-existing known P0, a CI-environment failure, a stale install or a stale venv (`uv sync --frozen --all-extras`). A red caused by a writer that still uses a read resolver is a real finding. Report it to the owning WP's lane; do not allowlist it (the cap is 0).
- **Integrated re-run of every new test file the Mission adds (post-tasks squad R-M5)**, on this WP's lane base (the merged tree after WP06 and every other writer WP). Run by name, never by directory:
  ```bash
  uv run --frozen pytest \
    tests/coordination/test_surface_resolver_anchor_helpers.py \
    tests/coordination/test_coord_mission_factory.py \
    tests/coordination/test_coord_seed.py \
    tests/mission_runtime/test_write_location.py \
    tests/coordination/test_event_prefix.py \
    tests/mission_runtime/test_placement_seam_write_dir.py \
    tests/coordination/test_surface_resolver_post_fix_empty_loud.py \
    tests/coordination/test_commit_outcome.py \
    tests/core/test_mission_create_coord_seed_rollback.py \
    tests/missions/test_expected_coordination_divergence.py \
    tests/coordination/test_status_transition_write_dir.py \
    tests/lanes/test_recovery_write_dir.py \
    tests/specify_cli/test_agent_tasks_ports_write_dir.py \
    tests/review/test_cycle_write_dir.py \
    tests/specify_cli/cli/commands/agent/test_tasks_port_commit_outcome.py \
    tests/specify_cli/cli/commands/agent/test_review_reject_fix_mode_coord.py \
    tests/specify_cli/decisions/test_service_coord_single_home.py \
    tests/runtime/test_decision_git_log_write_dir.py \
    tests/coordination/test_write_seam_surfaces.py \
    tests/retrospective/test_tracer_writer_write_dir.py \
    tests/tasks/test_issue_matrix_write_dir.py \
    tests/acceptance/test_acceptance_matrix_write_dir.py \
    tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py \
    tests/consolidation/test_decision_index_merge_driver.py \
    tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py \
    tests/mission_runtime/test_decision_ledger_reader_flips.py \
    tests/specify_cli/decisions/test_ledger_primary_ratchet.py \
    tests/specify_cli/cli/commands/agent/test_planning_commit_outcome_consumers.py \
    tests/orchestrator_api/test_commit_outcome_rendering.py \
    tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py \
    tests/decisions/test_decision_fork_detector.py \
    tests/consolidation/test_executor_ledger_preflight.py \
    tests/coordination/test_commit_outcome_consumer_pin.py \
    -q
  ```
  Plus the folded relocations (R-M8): `tests/coordination/test_commit_router.py` (holds R2/R2b) and `tests/core/test_mission_creation_decomposition.py` (holds R1/R1b). The e2e file `tests/integration/test_coord_single_home_workflow.py` belongs to WP21 and is not run here. Record pass/fail counts per file in the activity log. A red here that belongs to an earlier WP is reported to the orchestrator, not patched in this WP.

## Quality gates

- C901 ≤ 15 for every new helper (NFR-004). Split the scanner into find-function, extract-callee and classify steps.
- `ruff check` and `ruff format --check` on changed files; `mypy --strict` on changed test files (NFR-005, no new suppressions).
- Every new helper and branch has a focused test (NFR-003): the scan-root override, the qualname lookup, and the `KITTY_SPECS_DIR` heuristic.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #2533 #5513 #5501

## Definition of Done

- T106-T110 committed. The third grammar, floor, empty allowlist with a cap-0 baseline row, twin, bite tests and consumer pin are all green on the final commit.
- The red-at-base proof output (≥ 2 real offenders) is recorded in the activity log.
- `_baselines.yaml` has the new leaf, enforced by a `_SizeRatchet` row.
- No product code edited. If the gate finds a live offender, stop and report it to the orchestrator.
- **R-M5**: the integrated by-name re-run of every new Mission test file (see Targeted test surface) is green on this WP's lane base, with counts recorded.
- `tracer_append.py` is in the consumer-pin floor (R-M2), and the legacy root-staging fold is noted in the gate module (P-M2).

## Risks & Mitigations

- **Vacuous scan after renames.** Mitigated by the live-qualname floor, and by re-deriving the census from merged code, not the plan.
- **Over-broad heuristic** (`KITTY_SPECS_DIR` composition) flags legitimate PRIMARY composition. Mitigated by scoping to the census functions only and requiring a worktree-named operand, with controls.
- **Base proof crash** on qualnames absent at base. Mitigated by the "absent at base" reporting mode.
- **Ratchet meta-gate red** from an unregistered yaml leaf. Mitigated by T108 step 4.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies **red → green**:
  - the new grammar is RED against `ecb5dd914a` source on `decisions/emit.py::_mission_dir` and `decisions/service.py::_mission_dir` (re-run the T107 command);
  - it is GREEN on this WP's final commit;
  - the bite tests red on their plants.
- Check that the census floor is ≥ 22 live functions, each pointing at the function that actually performs the write today. Spot-check 3 by opening the source.
- Check that the allowlist is empty, `_baselines.yaml` caps it at 0, and the cap is enforced by `test_ratchet_baselines.py`.
- Check that no forbidden-token control bans `write_dir`.
- Check that the consumer pin covers every D8 row and bites.

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T16:39:58Z – cursor – shell_pid=1302175 – T106-T110 implemented, commit f65075ce59 on lane-p, NOT moved to for_review. Gate test_coord_writers_do_not_derive_write_location_from_read_resolver is RED at HEAD on 2 live offenders (cap 0, not allowlisted): coordination/transaction.py BookkeepingTransaction._acquire_locked:666 and runtime/next/runtime_bridge.py _wrap_with_decision_git_log:427 (both worktree_root / KITTY_SPECS_DIR / <mission dir>). Red-at-base proof (SPEC_KITTY_GATE_SCAN_ROOT=git archive ecb5dd914a src): exit 1, 18 offenders. Tests: gate+ratchet+pin+layer/placement/status gates+commit_router+mission_creation_decomposition = 391 passed, 1 failed (the live-offender gate); consumer pin 17 passed; make test-fast equivalent 2187 passed 5 skipped. ruff check/format and mypy --strict clean on the 3 changed test files. WP18 isolation confirmed (resolve_status_surface only in _completed_mission_projected_events_path).
- 2026-10-02T16:55:35Z – cursor – shell_pid=1376486 – Orchestrator ruling: cap stays 0. Migrated the two live offenders onto WriteLocation.path. Commit 10ac99df77. transaction._acquire_locked: coordination arm carries write_dir's WriteLocation.path (_CoordWriteTarget); legacy lane/primary checkouts use legacy_resolution._checkout_mission_dir. runtime_bridge._wrap_with_decision_git_log: owned arm now placement_seam(owned=owned).write_dir(DECISION_LOG) (write_dir derives the undeclared coord branch itself; no fixture change needed). Gate 81 passed; blast radius 5133 passed, 15 failed all identical on the lane base without my edits (mission_runtime coord-read seam / remote-probe / teardown-seam / next_board_authority).
