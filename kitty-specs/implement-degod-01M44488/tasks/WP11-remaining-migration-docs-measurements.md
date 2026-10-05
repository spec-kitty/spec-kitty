---
work_package_id: WP11
title: Remaining test migration, docs, changelog and closing measurements
dependencies:
- WP10
requirement_refs:
- FR-011
- FR-016
- SC-002
- SC-005
- NFR-003
- NFR-004
- NFR-006
planning_base_branch: issue-5635-implement-degod
merge_target_branch: issue-5635-implement-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5635-implement-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5635-implement-degod unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
phase: Phase 4 - Test migration and docs
history:
- at: '2026-10-04T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/_implement_dispatch.py
execution_mode: code_change
model: ''
owned_files:
- tests/integration/test_status_emit_on_alloc_failure.py
- tests/cli/test_implement_bulk_edit_planning.py
- tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py
- tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py
- tests/specify_cli/test_specify_topology_flag.py
- tests/specify_cli/lanes/test_lane_base_honoring.py
- tests/cli/commands/test_implement_base_flag.py
- tests/specify_cli/cli/commands/test_implement_*.py
- tests/specify_cli/cli/commands/_implement_dispatch.py
- tests/release/coverage_breadth_baseline.json
- pyproject.toml
- docs/architecture/wp-runtime-state-eviction.md
- docs/development/reference/read-side-seam-classification.md
- docs/architecture/04_implementation_mapping/README.md
- src/charter/offering/skills/spec-kitty-git-workflow/references/git-operations-matrix.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Remaining test migration, docs, changelog and closing measurements

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter through the canonical path, and work according to
its guidance before you read the rest of this prompt:

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --json
```

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State, in your first activity-log entry, which directives and tactics of the profile you applied.

---

## ⚠️ IMPORTANT: Review Feedback

Before you start, read the `review_ref` in the event log (`spec-kitty agent tasks status --mission implement-degod-01M44488`)
and the Activity Log below. Treat any review feedback as your TODO list.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Binding rules for this mission (read once, apply throughout)

- **Behaviour preserved (C-001).** Refusal texts, error codes, exit codes, console and `--json`
  output (including print order), commits and state files stay byte-identical.
- **Move, then adjust (C-002 / NFR-005).**
  - Commit 1 of each extraction is a verbatim move: `git diff --color-moved=zebra` must show only
    moved blocks plus the minimal import lines.
  - Commit 2 adjusts callers and imports, deletes the moved names' re-exports from `implement.py`
    (research R-3: keep a re-export only where *production* imports it from there), and applies
    typing-only fixes.
  - Never edit logic inside the move commit.
- **Existing packages only (C-004).** Lower packages (`lanes`, `workspace`, `coordination`,
  `status`, `core`) never import `specify_cli.cli`, `typer` or the console. They return typed
  results or raise typed errors; only the command package prints.
- **Gates follow the code (FR-012).**
  - Every census or scan list that names `implement.py` gains the module the code moved to; pins
    are re-pointed and never loosened.
  - Prove each widened scan by planting a violation in the new module, running the gate red, then
    removing the plant (never committed).
  - Record the commands and the red output in your activity log.
  - Record every local out-of-matrix test run (NFR-006) with its command and counts.
  - Checklist: research/code-grounding.md §1.5 and research/test-remediation.md §5 ("Gate/census edits").
- **Tests (charter SO 4, brief).**
  - Never edit an assertion to make a move pass.
  - Re-point imports and patches to the module that now *looks the name up*.
  - Add seam unit tests before trimming any end-to-end test, and keep at least one smoke test per
    behaviour family.
  - The characterization suite (`test_implement_characterization.py`) must stay green **unedited**.
    Only its dispatch-map fixture may change, when a collaborator's dispatch site moves.
- **Call style for moved collaborators (one rule, every WP).** Code in the command package calls a
  moved collaborator as an attribute of its owner module (`implement_claim.commit_wp_claim_status(...)`,
  `implement_support.resolve_base_ref(...)`), not through a `from … import name` binding.
  - One patch on the owner module then intercepts.
  - The widened liveness gate (WP01) treats `<alias-of-M>.<name>` reads as live.
  - Tests patch the owner module.
- **Ownership leeway for mechanical re-points.** A moving WP may edit any test or gate file only to
  re-point an import path, a patch target, a dispatch-map entry or a gate scan list for the names
  it moves (charter: ownership-map leeway; the no-overlap rule is the real guard, and this chain is
  sequential).
  - List every such out-of-map file in the activity log.
  - Assertion changes are never "mechanical".
- **Dispatch map scope.** `tests/specify_cli/cli/commands/_implement_dispatch.py` may only be used by
  the characterization suite and the F-50 alloc-failure test. Every `patch_collaborator(...)` call
  counts as a patch site in the SC-002 counter.
  - Never build an implement-family patch target dynamically (f-strings, concatenation) to evade
    the counter or the liveness gate.
- **Characterization suite immutability (SC-003).** At every review,
  `git diff <WP02 tip>..HEAD -- tests/specify_cli/cli/commands/test_implement_characterization.py`
  must be empty. Only `_implement_dispatch.py` may change.
- **Known red #5699.** Run `tests/specify_cli/cli/commands/test_commit_recipes.py` in every WP and
  compare its failing set with the base commit. It must be exactly
  `test_no_unallowed_git_commit_recipe_strings_in_src`, failing only on `_commit_message.py`.
  Any new entry is yours (for example the `silently demotes` allow-list row when that message moves).
- **No-CLI import guard for seams (C-004).** Every lower-package module that receives moved code
  (`coordination/planning_commit.py`, `lanes/implement_support.py`, `workspace/context.py`,
  `core/dependency_graph.py`) must be covered by an import gate forbidding `specify_cli.cli` /
  `typer` imports.
  - Extend `tests/coordination/test_commit_router_layering.py`, or the `test_layer_rules.py` rule,
    in the WP that first moves code into that module.
  - Prove it with a plant.
  - `lanes/implement_support.py`'s pre-existing lazy `cli.console` import (~L400) is the one
    recorded exception. Name it in the gate with the same carve-out `test_layer_rules.py` already
    grants consolidation for `cli.console`, plus a pointer to the follow-up issue the orchestrator
    files to drain it (charter SO 5).
- **NFR-003 per WP.** Time the regression subset (quickstart.md §2 plus the seam and phase unit
  tests) in every WP; the budget is ≤ 30 s. The characterization and reachability suites are timed
  separately (≤ 60 s each).
- **Quality (NFR-001/002/004).**
  - Complexity ≤ 15.
  - `mypy --strict` clean on new and receiving modules; nothing added to the mypy quarantine.
  - `ruff check` + `ruff format --check --force-exclude` clean on changed files.
  - No new `noqa` or `type: ignore` without an inline rationale.
- **Commits.** Every commit message ends with
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier anywhere
  (C-008).
- **Tracer files.** Append dated 1–3 sentence entries for friction, approach changes or design
  decisions to `kitty-specs/implement-degod-01M44488/traces/` (via the orchestrator, if your
  worktree cannot write the mission dir).
- **No heavy suites.** Never run `make test-full` or a whole `tests/architectural/` sweep. Run the
  targeted files and the specific gate files (quickstart.md §2–§3).


## Objectives & Success Criteria

- **SC-002**: the counter reports **≤ 45** family patch sites in total (string + object + dispatch;
  baseline 119). Reach it by rewriting coupling, not by re-pointing to a sibling.
- **FR-011**: migrate the remaining class-A/B files:
  - `test_status_emit_on_alloc_failure.py`, the F-50 contract (no `blocked` event on an allocation
    failure). It may use the dispatch map for `allocate`, and asserts by reading the real
    `status.events.jsonl`;
  - `test_implement_bulk_edit_planning.py`: assert the bulk-edit phase verdict and console output
    (WP09 phase tests) without its 6 patches;
  - `test_implement_vcs_lock_claim.py` / `test_implement_runtime_frontmatter_claim.py`: replace the
    shared 5-string-patch helper with a real fixture plus phase calls;
  - `test_specify_topology_flag.py` (2): re-point or rewrite;
  - the remaining patches in `test_lane_base_honoring.py` and `test_implement_base_flag.py`;
  - any other file the counter's `string_by_file` still lists.
- **Smokes kept, one per family** (test-remediation §5):
  - lane allocation e2e;
  - p0 repro and cross-partition scan;
  - crash recovery;
  - the single_branch CLI refusals;
  - the base-flag integration class;
  - #2993 ancestry;
  - the guard-capability regression;
  - the programmatic call and `--json` tests.
- **SC-005**: an activity-log table maps each phase (context; claim preflight + dependency gate;
  planning commit; bulk-edit + operational context; workspace/lane selection; allocate; record
  claim; present) to at least one test that calls the decision directly and patches nothing in
  the family.
- **NFR-003**: the regression subset plus all seam and phase test files run in ≤ 30 s
  (`-n auto --dist loadfile`). Record the time; the characterization and reachability suites are
  timed separately (≤ 60 s each).
- **FR-016 docs**:
  - re-point `docs/architecture/wp-runtime-state-eviction.md` (~L37, L80);
  - re-point `docs/development/reference/read-side-seam-classification.md` (~L603–606);
  - re-point the shipped git-operations-matrix
    `src/charter/offering/skills/spec-kitty-git-workflow/references/git-operations-matrix.md`
    `Source File` cells for moved code. That file ships in the charter pack, so also run
    `tests/charter` and `tests/doctrine` targeted files touching it, plus
    `test_git_matrix_paths_resolve.py`;
  - update `docs/architecture/04_implementation_mapping/README.md` (~L216) to list the new modules;
  - bump each touched page's `updated:` frontmatter date.
- **CHANGELOG**: add an `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (the root file is a
  symlink), following the file's style.
  - Bold impact-first lead: the maintainer-facing decomposition of `spec-kitty implement` (#5635),
    with no operator-visible behaviour change.
  - #5232: the meta-derived placement fallback is replaced by a seam-owned typed placement (use
    WP06's summary sentence).
  - #5673 is now a one-function change.
- **Checklist leftovers**:
  - `tests/release/coverage_breadth_baseline.json`: re-key or refresh any entry naming moved code,
    with the canonical regen command if one exists; check its header or the test that reads it;
  - `pyproject.toml` `[tool.ruff.format].exclude`: delete the entry of any excluded file this
    mission reformatted (the list may not grow; `test_ruff_format_exclude_ratchet.py`).

## Rules

- Never edit an assertion to make a migration pass.
- Add the replacement test before deleting the old one.
- Docs: run `scripts/docs/check_docs_freshness.py --ci` (errors=0) and
  `pytest tests/architectural/test_no_legacy_terminology.py`. Regenerate the docs retrieval index
  (`scripts/docs/docs_index.py --write`) if you add a page.

## Subtasks & Detailed Guidance

### Subtask T048 – Migrate the remaining class-A/B files
One file at a time, re-measuring the counter after each.

### Subtask T049 – Docs and CHANGELOG
As listed in the objectives.

### Subtask T050 – Checklist leftovers
The coverage-breadth baseline and the format-exclude entries.

### Subtask T051 – Closing measurements
Record the full targeted run:
- `make test-fast`;
- the regression subset;
- the owning dirs as targeted dirs: `tests/lanes/`, `tests/specify_cli/workspace/`,
  `tests/specify_cli/coordination/`, `tests/coordination/`, `tests/status/` and
  `tests/specify_cli/core/`;
- `tests/agent/` and `tests/specify_cli/cli/commands/` (out of matrix, NFR-006);
- the gate files (quickstart.md §3);
- `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`.

Also record the final counter, the SC-005 table, the NFR-003 timing and `wc -l` of every implement
family module.

## Definition of Done

- [ ] Counter ≤ 45; SC-005 table complete; NFR-003 met.
- [ ] Docs re-pointed and fresh; CHANGELOG entry; terminology guard green.
- [ ] No assertion edited; characterization unedited and green.

## Branch Strategy

- **Strategy**: lanes topology. Execution worktrees are allocated per computed lane from `lanes.json`.
  This mission's WPs form one dependency chain, so they run sequentially in one lane.
- **Planning base branch**: `issue-5635-implement-degod`
- **Merge target branch**: `issue-5635-implement-degod`. `spec-kitty consolidate` lands the lanes
  there, locally only. The branch then reaches `main` through a PR that the operator merges.
- Prepare the workspace only with `spec-kitty agent action implement WP11 --agent claude --mission implement-degod-01M44488`
  (or `spec-kitty implement WP11 --mission implement-degod-01M44488`), and work in the path it prints.

## Validation (run and record in the activity log: command + pass/fail counts)

1. `make test-fast`
2. The implement-direct regression subset (quickstart.md §2), plus every new or touched test file.
3. The owning subsystem directories of every source module you touched (CLAUDE.md blast radius),
   targeted files only.
4. The specific gate files you widened or re-pointed (quickstart.md §3).
5. `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`,
   `uv run --frozen mypy --strict <new/receiving src modules>`, and the C901 check.
6. The counter: `uv run --frozen python kitty-specs/implement-degod-01M44488/tools/count_patch_sites.py`
   (before/after numbers in the activity log).
7. Classify every red against the base commit (CLAUDE.md baseline-red gotcha). Charter rule:
   a pre-existing failure other than #5699 must get a GitHub issue. Record the command and the
   failure in the activity log and hand it to the orchestrator, who files it.
   `test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src` is a known
   pre-existing red (#5699); do not chase it.

## Activity Log

- 2026-10-04T20:45:00Z – system – Prompt created via /spec-kitty.tasks.


- 2026-10-05 — WP11 evidence (recorded by the orchestrator from the implementer's report).
  - **Counter:** 68 → **43** (string 6, object 19, dispatch 18; F-50 adds one `allocate` dispatch site). Console couplings 10 → 8; private imports stay at 30. **SC-002 met.**
  - **NFR-003:**
    - regression subset plus seam files: 23.8 s (budget ≤ 30 s);
    - characterization: 25.7 s (≤ 60 s);
    - reachability: 46.3 s (≤ 60 s).
  - **`wc -l` per module:**
    - `implement.py` 438, `implement_claim.py` 247, `implement_cores.py` 750;
    - `implement_phases.py` 477, `implement_planning_commit.py` 526, `implement_recover.py` 140;
    - `lanes/implement_support.py` 1017, `coordination/planning_commit.py` 524.
  - **SC-005, phase → direct test (no family patches):**
    - context: `TestDetectFeatureContext`, `test_the_declared_dependencies_reach_the_workspace_allocation`.
    - claim preflight + dependency gate: `test_claim_preflight_refuses_an_unready_dependency_before_anything_is_written`, `test_claim_preconditions.py`.
    - planning commit: `test_the_planning_commit_phase_follows_an_allowed_coordination_branch_preflight`, `test_planning_commit.py`, the vcs-lock claim tests.
    - bulk-edit + operational context: `test_bulk_edit_gate_*`, `test_implement_bulk_edit_planning.py`, `test_operational_context_carries_an_active_role_and_writes_nothing`.
    - workspace/lane selection: `test_select_workspace_reads_lanes_json_from_the_lanes_surface_not_the_status_surface`, `test_implement_support_lane_selection.py`.
    - allocate: `test_allocate_locks_the_vcs_and_creates_the_lane_worktree`.
    - record claim: `test_sequential_n_lane_claims_write_zero_wp_file_bytes`, `test_a_lane_claim_records_a_worktree_workspace_context`, `test_claim_policy_metadata.py`.
    - present: `test_json_payload_golden`, `test_banner_*`, `test_report_workspace_created`.
  - **Runs:**
    - `make test-fast`: 2276 passed.
    - Owning directories: 3811 passed. The 2 reload reds in `test_planning_commit.py` are fixed.
    - Out-of-matrix: 7035 passed, 4 failed. Three are `test_doctrine_asset` internal-pack path cases that depend on running from a worktree (to classify); one is #5699.
    - Gate files: 503 passed. e2e smoke: passed.
  - **Finding (follow-up candidate):** with `--no-auto-commit`, a second real claim is refused by the dirty-tree guard. The first claim leaves the allocator's frontmatter write and the status files uncommitted, and the old mocks hid this.
- 2026-10-05 — WP11 rework (cycle 1), recorded by the orchestrator.
  - `test_lane_base_honoring.py` now drives the real command on real missions: 5 string sites go to 0. The counter is 43 → **38** (string 1, object 19, dispatch 18).
  - The one string site left is `test_implement_cores.py:584` (`implement_cores.subprocess.run`), and it stays. It pins the #5576 positive `timeout` and the `TimeoutExpired` → changed behaviour. That is observable only at the subprocess boundary, and a real hung filter would wait out the 60 s production timeout. Follow-up: a GitPort-level timeout injection point.
  - The AC-4 error-path assertion was hollow on real missions: the second claim was refused before reaching the allocator. The test now commits `kitty-specs` between the claims. This is the same `--no-auto-commit` gap that is folded post-consolidation.
  - The bulk-edit "proceeds to allocation" claim now rests on the phase order in `implement()`, not on an observation.
