---
work_package_id: WP12
title: Decision ledger reclassified to the PRIMARY partition
dependencies:
- WP05
- WP11
requirement_refs:
- FR-009
- FR-009a
- FR-009b
- FR-017
- C-008
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:51:28.185771+00:00'
subtasks:
- T064
- T065
- T066
- T067
- T068
phase: Phase 4 - Decision ledger
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/artifacts.py
create_intent:
- tests/mission_runtime/test_decision_ledger_reader_flips.py
- tests/specify_cli/decisions/test_ledger_primary_ratchet.py
- tests/coordination/test_ledger_topology_less_callers.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/mission_runtime/artifacts.py
- tests/mission_runtime/test_artifact_partition.py
- tests/mission_runtime/test_decision_ledger_reader_flips.py
- tests/specify_cli/decisions/test_ledger_primary_ratchet.py
- tests/architectural/test_write_surface_placement_guard.py
- tests/architectural/test_merge_reconciliation_class_guard.py
- tests/mission_runtime/test_artifact_partition_mapping.py
- tests/coordination/test_coherence_integrity.py
- src/specify_cli/consolidation/planning_recency.py
- tests/consolidation/test_planning_recency_helper.py
- src/specify_cli/coordination/coherence.py
- tests/coordination/test_ledger_topology_less_callers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Decision ledger reclassified to the PRIMARY partition

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

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

The decision ledger (`decisions/DM-*.md` and `decisions/index.json`) is classified as a COORD-partition record (the #3928 intent), but it is written to and read from the PRIMARY partition (`decisions/service.py::_ledger_dir`, #4966). That split makes `spec-commit` re-route ledger files onto the coordination branch and triggers the fork (#5023). This WP makes the classification match the behaviour: the ledger becomes a **PRIMARY-partition** record. Decision **events** (in `status.events.jsonl` and `decisions.events.jsonl`) stay COORD.

Done means:
- R13 is green: `artifact_home_for(DECISION_LEDGER)` is PRIMARY.
- The commit router groups a ledger path to the target branch.
- `DECISION_LEDGER` lives in `_PRIMARY_ARTIFACT_KINDS`. `_COORD_RESIDUE_DIRS["decisions"]` keeps mapping the dir to the kind, so `kind_is_coordination_residue` is now false for it. The stale #3928 comments are rewritten.
- Every reader in research D12 has a focused test of its post-flip answer. Any pre-existing test that pinned the old COORD answer is re-pinned in this WP, never left red for a later WP.
- An FR-009a ratchet proves that ledger writes and reads stay on the PRIMARY partition.
- Both architectural guards are updated and remain non-vacuous:
  - `test_write_surface_placement_guard.py`;
  - `test_merge_reconciliation_class_guard.py`, amending the single-writer ruling with a reference to WP11's `spec-kitty-decision-index` driver.

## Context & Constraints

- **Spec**: FR-009 (reclassification), FR-009a (ledger writes and reads stay PRIMARY; a ratchet), FR-009b (lane merge; with WP11's driver), US4.7, US4.9.
- **Plan**: IC-11, the reclassification half.
- **Research**: D12 (reader blast radius; the authoritative list of reader sites), D13 (driver), R13.
- **Data model**: §1, partition table.
- **Behaviour change** to state in the PR. After this WP:
  - the accept dirty gate and the consolidation dirty gate treat uncommitted ledger files as **real work**: refused or committed, never reset as residue;
  - the accept side is finished in WP16 (accept commits the ledger on the target branch);
  - the consolidation side is finished in WP17 (the refusal message names `accept` / `spec-commit`).

  Between this WP and those, an uncommitted ledger blocks accept or consolidate on the Mission branch. That is acceptable mid-mission; note it in the activity log.
- **Pre-fix coordination-only ledgers**: the bookkeeping projection excludes PRIMARY kinds (`bookkeeping_projection.py` ≈L481), so a ledger that exists only on the coordination branch is not projected. WP17 adds the teardown refusal plus the doctor repair. Do not add a read fallback (spec Out of Scope).
- **Charter**: load `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`. Architectural gate discipline: gates stay non-vacuous, keeping their floor and self-mutation checks green.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`), review = opus.
- **Terminology**: say Mission, never feature. Always name the sense of "primary": the PRIMARY partition, the target branch, or the repository root checkout.
- **C-006**: named architectural files only.
- **Brownfield scout (binding read)**: before coding, read `## WP12` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`).
- Start with `spec-kitty agent action implement WP12 --agent claude`. Use the workspace path it resolves.
- **Lane-relevant sharing**: ownership is disjoint, so this WP runs in its own lane once WP05 (the router contract) and WP11 (the driver) are approved. WP13, WP16 and WP17 depend on it.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T064 – Red-first R13 and the router grouping reader

- **Purpose**: Make the misclassification visible through two pre-existing entry points before changing it.
- **Steps**:
  1. In `tests/mission_runtime/test_artifact_partition.py`, add `test_decision_ledger_is_primary`: `artifact_home_for(MissionArtifactKind.DECISION_LEDGER)` (artifacts.py ≈L302) reports the PRIMARY home. Follow the existing style (`test_artifact_home_for_spec_is_primary`, ≈L95). It is red at the base, where the answer is COORD.
  2. Add a router-level reader test, in `tests/mission_runtime/test_decision_ledger_reader_flips.py` (new):
     - build a coordination-routed Mission with WP02's factory (`tests._factories.coord_mission`);
     - make `decisions/index.json` dirty in the repository root checkout;
     - call `commit_for_mission(files=(<root path of index.json>,), kind=MissionArtifactKind.SPEC, …)`;
     - assert the ledger is committed on the **target branch** and that `surfaces` (WP05's contract) shows a primary-surface `committed` entry.

     At the base the router groups it as COORD and stages it to the coordination branch, which is red.
  2b. In the same new file, add the spec-commit leg (#5501, US3.4): `test_spec_commit_commits_ledger_on_target_branch`. Run the CLI `spec-kitty spec-commit --mission <M> -m "ledger" kitty-specs/<dir>/decisions/index.json kitty-specs/<dir>/decisions/DM-<ulid>.md --json` on a coordination-routed Mission (create the ledger by opening a decision through the production service). Assert with `git log -1 --name-only <target>` that the target branch tip holds both ledger files, and that the coordination branch gained no commit touching `decisions/`. It is red at the base, where spec-commit re-routes the ledger to the coordination branch. WP13 (spec-commit's per-argument output) is deliberately not a dependency of this WP, and this WP is not one of WP13's: the edge would create a lane cycle. So this assertion lives here, and WP13 only asserts that the ledger's fate is *named* on the taxonomy-assigned surface.
  3. Commit the three red tests alone, before T065.
- **Files**: `tests/mission_runtime/test_artifact_partition.py`, `tests/mission_runtime/test_decision_ledger_reader_flips.py`.
- **Validation**: both tests are red on the WP base. Paste the output into the activity log.
- **Edge cases**:
  - The partition test file may stub resolvers. Keep the new assertion on the real `artifact_home_for`.
  - Use the factory's `coord` topology. A `lanes` Mission routes everything to the PRIMARY partition and would make the test vacuous.

### Subtask T065 – Move `DECISION_LEDGER` to the PRIMARY kinds and rewrite the #3928 comments

- **Purpose**: One classification change in the single taxonomy authority (C-001: no second classifier).
- **Steps**:
  1. In `src/mission_runtime/artifacts.py`:
     - remove `MissionArtifactKind.DECISION_LEDGER` from `_PLACEMENT_ARTIFACT_KINDS` (≈L194-213; the entry is at ≈L209-211 with its #3928 comment);
     - add it to `_PRIMARY_ARTIFACT_KINDS` (≈L158-186).
  2. Keep `_COORD_RESIDUE_DIRS["decisions"] = MissionArtifactKind.DECISION_LEDGER` (≈L287). The dir still maps to the kind, and the kind's partition now makes `kind_is_coordination_residue` (≈L131-149) false. Check that function's logic: if it consults the dict without checking partition, adjust it so the answer derives from the partition, not from dict membership.
  3. Rewrite the stale comments. They must say that the ledger is PRIMARY (FR-009, Mission coord-artifact-single-home-01M3V4BE), that #3928's COORD intent is reversed because writes and reads were already PRIMARY (#4966), and that decision events stay COORD. The locations:
     - the `DECISION_LEDGER` enum docstring and comment (≈L108-117);
     - the placement-kinds comment (≈L209-211);
     - the residue-dir comment (≈L280-287);
     - the `artifact_home_for` comment (≈L356-357).

     This is FR-017's code-comment half for this file.
  4. Run R13 and the router reader test: both green.
- **Files**: `src/mission_runtime/artifacts.py`.
- **Validation**:
  - `tests/mission_runtime/` is green;
  - `tests/architectural/test_layer_rules.py` is green (no new imports);
  - every partition-invariant assertion is green (`placement_seam` asserts the partition invariant at construction, `resolution.py` ≈L2835).
- **Edge cases**:
  - A frozenset-disjointness assertion between the two kind sets may exist. Keep the sets disjoint.
  - `MissionArtifactKind` order or `__all__` must not change.

### Subtask T066 – Reader-flip focused tests and re-pins (research D12)

- **Purpose**: Every reader that flips gets a focused test of its new answer, so the behaviour change is deliberate and pinned, not incidental.
- **Steps**:
  1. In `tests/mission_runtime/test_decision_ledger_reader_flips.py`, add one test per D12 reader, each driven through the reader's public predicate or its narrowest real entry point. Re-derive each site by symbol with grep, because line numbers are approximate at `ecb5dd914a`. Each test needs a short docstring naming the reader and the D12 row.

     | Reader (site at `ecb5dd914a`) | Expected answer after the flip |
     |------|------|
     | commit router grouping (`commit_router.py` ≈L768) | ledger to the target branch (done in T064) |
     | retrospect residue filter (`retrospect.py` ≈L281, `is_coord_residue_churn`) | ledger dirt is real work |
     | record-analysis preflight (`mission_record_analysis.py` ≈L198) | real work |
     | implement partition (`implement.py` ≈L905/947, `implement_cores.py` ≈L355) | PRIMARY |
     | move-task / tasks shared (`tasks_move_task.py` ≈L824, `tasks_shared.py` ≈L750) | not dropped as residue |
     | git probes (`consolidation/git_probes.py` ≈L183 `_classify_porcelain_lines`, injected predicate) | real work |
     | auto-rebase (`lanes/auto_rebase.py` ≈L225) | not coordination-owned |
     | review dirty classifier (`review/dirty_classifier.py` ≈L129) | not benign |
     | workspace teardown (`coordination/workspace.py` ≈L379) | ledger dirt in the coordination worktree blocks removal |
     | orchestrator lane cleanup (`orchestrator_api/commands.py` ≈L958) | real work |
     | rollback (`consolidation/rollback.py` ≈L362) | real work |
     | ordering (`consolidation/ordering.py` ≈L659) | real work |
     | bulk-edit diff check (`bulk_edit/diff_check.py` ≈L361) | not exempt |
     | lane consolidation (`lanes/consolidation.py` ≈L1234/L1316) | real work |
     | bookkeeping projection (`consolidation/bookkeeping_projection.py` ≈L481) | ledger excluded from projection (PRIMARY) |

     Many of these readers share one predicate (`kind_is_coordination_residue` or `is_coord_residue_churn` in `coordination/coherence.py` ≈L159). Where several readers call the same predicate, a parametrized test over the predicate plus one smoke test per distinct call shape is enough. Avoid tautological tests (DIRECTIVE_041): assert the reader's observable decision.
  2. Excluded here: the accept dirty gate (WP16) and the consolidation executor gates and message (`executor.py` ≈L2036/3273/3500, WP17). Do not test or edit them here.
  3. Run each reader's existing test files. Find them with `grep -rl "<module>" tests --include="test_*.py"`.
     - A pre-existing test that pins the OLD COORD classification of `decisions/` (for example, asserting that ledger dirt is reset as residue) is now stale. Re-pin it in this WP; that is an out-of-map test edit under ownership-map leeway. Add a one-line rationale comment citing FR-009.
     - List every re-pinned test in the activity log.
     - Never leave a red test for a later WP, and never `xfail`.
- **Files**: `tests/mission_runtime/test_decision_ledger_reader_flips.py` (new), plus re-pins as needed, recorded.
- **Validation**: all reader tests are green, and each owning test file is green after the re-pins.
- **Edge cases**:
  - Readers in the consolidation executor are in WP17's files. If an executor test pins the old reset behaviour, coordinate: re-pin only the assertion that the flip broke, with a rationale, because WP17 runs after you in another lane. Do not change `executor.py`.
  - If a reader turns out to have no observable decision (dead code), note it rather than writing a vacuous test.
- **Declared re-pins (post-tasks squad P-m3)**, both now in owned_files:
  - `tests/mission_runtime/test_artifact_partition_mapping.py`: `test_decisions_ledger_classifies_to_coord` and `test_decisions_ledger_is_coord_residue_churn` flip to the PRIMARY expectation;
  - `tests/coordination/test_coherence_integrity.py`: the `decisions/DM-…` parametrization.
  Each re-pin carries a one-line rationale (FR-009 reclassification). Any other stale pin you find outside owned files is re-pinned with an out-of-map rationale and listed in the activity log.

### Subtask T067 – FR-009a ratchet: ledger writes and reads stay on the PRIMARY partition

- **Purpose**: FR-009a is a `[ratchet]` that pins existing behaviour, so the reclassification stays behaviour-aligned.
- **Steps**:
  1. Create `tests/specify_cli/decisions/test_ledger_primary_ratchet.py`.
  2. On a coordination-routed Mission (WP02 factory) and on a `lanes` Mission (C-008 control):
     - open a decision through the production service or CLI (`spec-kitty agent decision open …`), and assert that `DM-*.md` and `index.json` are written under the repository root checkout's Mission dir (the PRIMARY partition), never under `.worktrees/`;
     - read through the service's list or verify path and assert it reads the same PRIMARY dir. The code paths are `decisions/service.py::_ledger_dir` (≈L255-279, resolving `PRIMARY_METADATA`) and `cli/commands/_decisions_doctor.py` ≈L146-156.
  3. This is a test only. No product edit.
- **Files**: `tests/specify_cli/decisions/test_ledger_primary_ratchet.py` (new).
- **Validation**: green before and after T065, by design (a ratchet). State that in its docstring, together with the FR-009 `[build]` rows it is paired with.
- **Edge cases**: decision event writes move to the coordination surface in WP09. This test asserts only the ledger files' location, not the events'.

### Subtask T068 – Architectural guard updates

- **Purpose**: Keep both guards truthful and non-vacuous after the flip.
- **Steps**:
  1. `tests/architectural/test_write_surface_placement_guard.py`:
     - update the module docstring's kind bifurcation (≈L5-12) to list `DECISION_LEDGER` among the PRIMARY kinds;
     - in the live sets (≈L330-360), move `MissionArtifactKind.DECISION_LEDGER` from `coord_kinds` to the primary set and replace its #3928 comment.

     The guard drives the real resolver: confirm it now asserts that the ledger resolves to the target branch for every topology.
  2. `tests/architectural/test_merge_reconciliation_class_guard.py`, `_NON_DIVERGENT_COORD_RESIDUE_DIRS` (≈L316-334):
     - amend the #3928 single-writer ruling for `"decisions"`. The ledger is now PRIMARY, travels with lane branches, can be written concurrently on two lanes, and `index.json` carries WP11's `spec-kitty-decision-index` driver;
     - ~~decide whether `decisions` leaves this frozenset~~ **Decided (`plan.design.merge-class-guard-set`)**: `decisions` **stays** in `_NON_DIVERGENT_COORD_RESIDUE_DIRS`. Amend only the ruling text, and add the assertion that the `decisions/index.json` driver pattern is registered in root `.gitattributes`, discovered via the `_MERGE_DRIVERS` `config_key`;
     - keep `test_both_sides_divergent_canonical_artifacts_carry_merge_driver` and the guard's self-mutation tests green and non-vacuous: the driver must be found through the real `_MERGE_DRIVERS` registry.
  3. Record the amended ruling text in the activity log for the PR.
- **Files**: the two architectural test files.
- **Validation**: run both files by name. Also run `tests/architectural/test_status_state_read_dir_single_authority.py` and `tests/architectural/test_layer_rules.py`.
- **Edge cases**: if WP11's driver is not yet visible in your lane, rebase onto the lane base that includes WP11, which is a declared dependency. Never hard-code the driver name in the guard; resolve it through the registry.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **`planning_recency` hazard (operator decision; now owned)**: `src/specify_cli/consolidation/planning_recency.py` must skip paths covered by a registered merge driver (`_MERGE_DRIVERS` pattern match; driver-covered wins) in `_is_primary_planning_path` (L47) / `target_newer_primary_artifacts` (L84).
  - Otherwise `lanes/consolidation.py:748-750` (`_restore_target_newer_planning`) and `:892-901` (`_resolve_planning_conflicts`) overwrite the driver's `decisions/index.json` with `git merge-file --ours`.
  - Test in `tests/consolidation/test_planning_recency_helper.py` (owned). It is a **forward guard**: green at the base, because the ledger is COORD there. Show it red on the commit after T065 and before the recency fix, and record that output.
- **Merge class guard (operator decision)**: keep `"decisions"` in the guard's existing `_NON_DIVERGENT_COORD_RESIDUE_DIRS` set. Do not move it into the divergent set: the guard hard-asserts `divergent_dirs == {"traces"}` and requires a `decisions/*.md` driver that does not exist, because `DM-*.md` files are ULID-unique.
  - Amend the ruling text: the dir is PRIMARY, `DM-*.md` are ULID one-shot writes, and `index.json` is covered by the `spec-kitty-decision-index` driver.
  - **Require** that the `.gitattributes` pattern for `decisions/index.json` is registered, discovered via the `_MERGE_DRIVERS` `config_key`, never a literal. Note that the guard reads root `.gitattributes` (`_gitattributes_merge_drivers()`, L161), not `_MERGE_DRIVERS`.
  - Interpretation note: the operator wrote "divergent set"; the guard's set that holds `decisions` today is the non-divergent one, and it stays there.
- **Topology-less callers (operator decision; C-008)**: `is_coord_residue_churn` / `is_toolchain_generated_churn` (`coordination/coherence.py`, now owned) project COORD when `topology=None`. After the flip, the ledger verdict changes for **every** topology at these callers: `consolidation/executor.py` ~L2036, `tasks_move_task.py:824`, `tasks_shared.py:750`, `implement.py:905/947`, `lanes/auto_rebase.py:225`, `commit_router.py:768`.
  - **Red-first**: `tests/coordination/test_ledger_topology_less_callers.py` (new) is a parametrized characterization on a **`lanes`** Mission and a `single_branch` Mission. It pins each caller's base verdict for `decisions/*` paths, and it goes red after T065 without the fix.
  - **Fix at the single predicate point** in `coherence.py`. When `topology is None` and `mission_slug` is known, resolve the stored topology and keep the base verdict for non-coordination topologies. Coordination-routed Missions get the new PRIMARY rule. No per-caller patches.
  - A caller that passes neither topology nor slug: list it and keep the base behaviour.
  - Record the rule in `design-decisions` (tracer).
- **Extended reader list for T066 (scout)**: `commit_router.py` L697-698, L839-841, L915, L1193, L1337; `coordination/surface_authority.py:232`; `missions/_read_path_resolver.py:1446`; `resolution.py` L1289/1316/1419/2487/2704; `git/ref_advance.py` (injected predicate); `cli/commands/agent/workflow.py:393`; `acceptance/__init__.py:1219/1269`; `consolidation/planning_recency.py:47`.
- **T065 step 2**: `kind_is_coordination_residue` is already partition-derived (`return kind in _PLACEMENT_ARTIFACT_KINDS`), so it needs no code change. Say so in the activity log.
- **R13** needs a `placement_ref`: `artifact_home_for(DECISION_LEDGER, CommitTarget(ref=...)).read_surface`.
- **Router reader test**: never use an `owned=` fixture, because owned bypasses grouping (`commit_for_mission` L281). Assert `git log` per branch, not only `surfaces`.
- **Placement guard**: apply the move to **both** `primary_kinds` and `coord_kinds` (`test_write_surface_placement_guard.py:356-359`). `test_artifact_partition_mapping.py::test_decisions_ledger_kind_is_distinct_from_neighbor_kinds` (L197) should stay green.
- **G2**: FR-017 is now in requirement_refs (T065 rewrites the residue comments). C-008 is added for the topology-less fix.
- Quick-run includes `tests/lanes/test_squash_seam_reconciliation.py`.
- **Round 4 (`plan.design.topology-less-callers`)**: the fix point and its semantics are confirmed, and the design docs now match (plan IC-11, research D12, data-model). There is **no** compatibility set.
  - **Add coordination-Mission tests** at move-task (`tasks_move_task.py:824`), implement (`implement.py:905/947`) and auto-rebase (`lanes/auto_rebase.py:225`), in `tests/coordination/test_ledger_topology_less_callers.py`. For the now-PRIMARY ledger, an uncommitted `decisions/` file on a coordination Mission is **real work, not residue**. This is a deliberate widening for coordination Missions.
  - The `lanes`/`single_branch` characterization stays byte-identical to the base.
- **Round 4 (`plan.design.merge-class-guard-set`)**: confirmed, and plan IC-11 / research D13 now match. `decisions` stays in `_NON_DIVERGENT_COORD_RESIDUE_DIRS`, the ruling text is amended, and the `decisions/index.json` driver pattern is asserted as registered.

## Targeted test surface

```bash
uv run --frozen pytest tests/mission_runtime/test_artifact_partition.py tests/mission_runtime/test_decision_ledger_reader_flips.py -q
uv run --frozen pytest tests/specify_cli/decisions/test_ledger_primary_ratchet.py tests/specify_cli/decisions/ tests/decisions/ -q
uv run --frozen pytest tests/mission_runtime/ -q
uv run --frozen pytest tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_layer_rules.py tests/architectural/test_status_state_read_dir_single_authority.py -q
# each flipped reader's own test files (grep per module, run by name), e.g.:
uv run --frozen pytest tests/coordination/test_coherence_integrity.py tests/coordination/test_commit_router.py -q
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record the commands and pass/fail counts in the activity log.
- **Baseline-red gotcha**: classify reds you did not cause as one of: known P0, CI environment, stale install, or stale venv. Only branch-red plus base-green failures are yours.

## Quality gates

- C901 ≤ 15 for any touched function (NFR-004). `kind_is_coordination_residue` must not grow complex.
- `ruff check` and `ruff format --check` on the changed files; `mypy --strict` on the changed files. No new suppressions (NFR-005).
- ≥ 90% coverage on changed lines, with a focused test per new branch (NFR-003).
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5023

## Definition of Done

- R13 and the router-grouping reader test were red on the WP base and are green on the final commit.
- `DECISION_LEDGER` is in `_PRIMARY_ARTIFACT_KINDS`, the residue mapping is kept, and the comments are rewritten.
- There is a D12 reader-flip test per reader (excluding accept and executor). All re-pins are listed with a rationale.
- The FR-009a ratchet is green.
- Both guards are updated and green, and remain non-vacuous.
- The behaviour-change note (accept and consolidate gates mid-mission) is in the activity log.

## Risks & Mitigations

- **The broadest behaviour flip** in the Mission (about 20 reader sites). Mitigation: a focused test per reader, and running each reader's owning test files.
- **Stale tests in other WPs' files go red.** Mitigation: re-pin them here with a rationale; never defer red.
- **The class guard's completeness check could go vacuous** if the amended ruling weakened it (`decisions` stays in the frozenset; `plan.design.merge-class-guard-set`). Mitigation: the new `index.json`-driver-registered assertion, plus the guard's self-mutation tests, which must still bite.
- **Pre-fix coordination-only ledger loss at teardown.** Mitigation: WP17's refusal ships in the same mission. Mention it in the PR.

## Review Guidance

- The reviewer (opus, a different agent from the implementer) verifies red→green: R13 and the router-grouping reader test were RED on the WP base and are GREEN on the final commit.
- Diff `artifacts.py`: one kind moved, comments rewritten, no new classifier.
- Check the re-pin list. Each one must be a stale classification pin, not a masked regression.
- Check that both architectural guards still bite: run their self-mutation tests.
- Confirm no edits to `executor.py`, `accept.py` or `acceptance/__init__.py`. Those belong to WP16 and WP17.

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
- 2026-10-01T19:42:10Z – unknown – Review cycle 1 (B1-B4) addressed: B1 reverted formatting-only hunks in the 5 ruff-format-excluded files (ratchet green, diff coverage restored ~90%); B3 renamed the two re-pinned tests (classifies_to_primary / is_not_coord_residue_churn); B4 added a real mixed-batch commit_for_mission test (decisions.events.jsonl COORD + ledger PRIMARY split across both branches); B2 part 1 replaced the vacuous topology-less-callers test with 5 real caller-level tests (move-task, implement x2, auto-rebase, commit_router) on a WP02 coordination Mission, all red-at-base/green-after-T065, plus a coherence.py docstring-only listing of the six topology-less callers. B2 part 2 (lanes/single_branch characterization + any coherence.py logic change) is on hold pending the operator's C-008 ruling (design-decisions tracer entry filed). Commit 6e2fac3d10. make test-fast: 2173 passed, 5 skipped. Not moving to for_review until the B2 ruling arrives, per the coordinator's instruction.
