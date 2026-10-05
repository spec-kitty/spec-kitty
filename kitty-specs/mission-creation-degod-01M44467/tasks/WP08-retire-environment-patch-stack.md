---
work_package_id: WP08
title: Retire the environment patch stack
dependencies:
- WP07
requirement_refs:
- FR-007
- NFR-004
- C-005
- SC-003
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 3 - Tests onto the seams
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/core/test_mission_creation_family.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/_factories/coord_mission.py
- tests/_factories/test_make_mission_parity.py
- tests/agent/test_agent_feature.py
- tests/agent/test_create_feature_branch_unit.py
- tests/contract/test_mission_id_creation_contract.py
- tests/core/test_mission_create_checkout_restore.py
- tests/core/test_mission_create_coord_seed_rollback.py
- tests/core/test_mission_create_coord_status_placement.py
- tests/core/test_mission_create_coord_status_seed.py
- tests/core/test_mission_create_protected_single_branch.py
- tests/core/test_mission_create_scaffold_rollback.py
- tests/core/test_mission_creation_decomposition.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/core/test_mission_creation_identity.py
- tests/core/test_mission_creation_topology.py
- tests/core/test_mission_creation_unborn_head.py
- tests/core/test_slug_validator_unit.py
- tests/integration/test_issue_4863_merge_abort_no_state.py
- tests/integration/test_placement_partition_golden_path.py
- tests/integration/test_specify_plan_commit_boundary.py
- tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
- tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py
- tests/specify_cli/cli/commands/agent/test_mission_create.py
- tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py
- tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
- tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/specify_cli/cli/commands/test_selector_resolution.py
- tests/specify_cli/core/test_feature_creation.py
- tests/specify_cli/core/test_mission_creation_fire_once.py
- tests/specify_cli/core/test_mission_creation_placement.py
- tests/specify_cli/core/test_mission_creation_specify_started.py
- tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
- tests/core/test_mission_creation_family.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Retire the environment patch stack

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them. Load the test-remediation doctrine: `spec-kitty charter context --include tactic:delete-the-assertion-not-the-test` and `--include tactic:test-scaffolding-as-design-smell`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback.

---

## Objectives & Success Criteria

Remove the four-name **environment patch stack** that tests wrap around `create_mission_core`: `is_worktree_context` (72 sites), `locate_project_root` (45), `is_git_repo` (44) and `get_current_branch` (42). That is about 203 of the 277 façade patch sites (spec FR-007, US3). Every removal must be one of:

- **(a) moved**: the test passes `allow_worktree_context=True`, or uses `monkeypatch.chdir(repo)` / an explicit `repo_root` instead of a patch;
- **(b) rewritten**: the test now runs on a real repository whose real state matches what the patch faked (for example `git init -b main`, or `clone_template`, instead of `git init` plus a patched `get_current_branch` returning `"main"`);
- **(c) retired**, with proof:
  - a **dead patch**: per-test coverage context shows the patched call site never ran under that test. Record the command and the result.
  - a **redundant guard test**: name the covering guard and show a planted break turning it red.

Done means:

- Static façade patch sites for these four names: **0**, except the three intentional refusal guards for the worktree context. Those become behaviour tests on a real `git worktree add` checkout with no patch.
- Each touched test keeps its assertions. Under C-005, an interaction assertion may be replaced only by an equal-or-stronger behavioural assertion, logged in the Activity Log as `file::test — old → new`.
- The routing check from WP06 stays green. When a name is no longer patched on the façade, Rule C ("stale") flags leaves still routing it. De-route those references (`_mc.is_git_repo(...)` back to `is_git_repo(...)`, with a direct import in the leaf), so routing only exists where a test needs it.
- The interim census (WP04 tool) is pasted in the Activity Log: static by name before and after, plus runtime applications.
- The golden files are untouched, and the covering set, golden matrix and WP03 tests are green.

## Context & Constraints

- Per-name verdicts and evidence: `research/test-remediation.md` §2, §3 and §5. The dead `locate_project_root` proof method is in §3: only 3 tests in `tests/agent/test_agent_feature.py` reach the two call sites.
- Covering guards to keep and re-prove:
  - worktree refusal:
    - `tests/core/test_mission_creation_decomposition.py::test_worktree_context_without_allow_flag_is_refused`
    - `tests/specify_cli/core/test_feature_creation.py::test_worktree_context_raises`
    - `tests/_factories/test_make_mission_parity.py::test_create_mission_core_worktree_guard_default_still_blocks`

    Convert them to a real worktree; no patch.
  - not a git repo: `tests/core/test_mission_creation_decomposition.py::test_not_a_git_repo_raises` (a real non-git dir).
  - detached HEAD: `tests/core/test_mission_creation_decomposition.py::test_detached_head_raises` (a real `git checkout --detach`).
- **The faked-branch trap** (HIGH finding T3): `tests/specify_cli/core/test_feature_creation.py::_init_git_repo` runs `git init` with no `-b`, leaving HEAD on `master` while tests patch `get_current_branch` to return `"main"`. About 33 creates across four files assert on a branch that does not exist. Fix the fixture (`git init -b main`, or `clone_template`) and drop the patch. Expect some assertions on `target_branch` to start reflecting the **real** branch. If an assertion's expected value was `main` and the fixed fixture is on `main`, it stays; never change an expected value to make a test pass (C-005). If a rewrite would require changing an expected value, stop and report it in the Activity Log.
- `tests/_factories/coord_mission.py` is a shared factory used by about 44 incidental consumer files. Changing its helpers changes many tests' setup. Prefer adding an explicit `allow_worktree_context=True` / `chdir` path over removing a parameter, and run the full covering set after each change.
- Golden files are frozen (NFR-001): never edit `tests/core/golden/**`, `tests/core/_mission_create_golden.py`, `tests/core/test_mission_creation_golden_*.py` or the CLI golden files.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T038 – `is_worktree_context` (72)

- Most sites exist because developers run pytest from inside `.worktrees/*-lane-*`. Replace them with `allow_worktree_context=True` on direct `create_mission_core` calls, or `monkeypatch.chdir(repo)` for CLI paths. The CLI derives its root from cwd; confirm that `chdir` makes the guard read the temp repo.
- Convert the three refusal guards to a real `git worktree add` with cwd inside it.
- Run the covering set **from inside this lane worktree**. That is exactly the environment the patch was hiding.

### Subtask T039 – `locate_project_root` (45)

- Retire every site that coverage proves dead. Command template:

  ```bash
  PWHEADLESS=1 .venv/bin/python -m pytest <file> --cov=specify_cli.core --cov-context=test --cov-report= -q
  ```

  then check that the `locate_project_root` call lines have no context for that test (use `coverage json --show-contexts` or `coverage report --contexts`). Record per file: sites retired, plus the command.
- The 3 live sites in `tests/agent/test_agent_feature.py` become `monkeypatch.chdir(repo)`.

### Subtask T040 – `is_git_repo` (44)

- Always patched to `True` on a real repository, so the patch is redundant. Retire it.
- Re-prove the guard: in your worktree, temporarily delete the `is_git_repo` check in `_resolve_create_roots` (now in `mission_creation_roots.py`). `test_not_a_git_repo_raises` must go red. Revert, and record the result.

### Subtask T041 – `get_current_branch` (42)

- Fix the fixtures that fake the branch (see the trap above). Delete the patch, and assert against the real branch.
- The detached-HEAD guard becomes a real `git checkout --detach`.
- Run the four affected files plus the covering set, and record any expected-value tension (should be none).

### Subtask T042 – De-route leaves and the interim census

- Run the WP06 routing check. For every Rule C (stale) finding, de-route the leaf reference and replace the lazy `_mc` import with a direct import if no other routed name remains in that function.
- Re-run `tests/core/test_mission_creation_family.py` (including its behavioural intercept tests). If an intercept test used one of these four names, switch it to a name that is still routed (for example `_commit_feature_file`); this is an edit to WP06's file within this WP's sequential ownership.
- Paste the census report into the Activity Log:

  ```bash
  python -m tests._support.patch_census --report
  ```

  plus the runtime counter over the covering set.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest $(grep '^tests/' <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md)) tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/core/test_mission_creation_family.py tests/_support/ -q
git diff <lane-base> -- tests/core/golden tests/core/test_mission_creation_golden_* tests/core/_mission_create_golden.py tests/specify_cli/cli/commands/agent/golden   # must be empty
uv run --frozen ruff check <changed files> && uv run --frozen ruff format --check --force-exclude <changed files>
.venv/bin/mypy <changed src files>
make test-fast
```

Baseline reds to classify, not chase: baseline-red #5705, #5706.

## Risks & Mitigations

- **The factory blast radius** (`tests/_factories/coord_mission.py`): run the covering set plus `grep -rl "coord_mission" tests` consumers you touched.
- **A retired patch that was load-bearing**: only coverage-proven dead sites are retired; everything else is moved or rewritten.
- **Expected-value drift** from the faked-branch fix: stop and report, never adjust.

## Review Guidance

- Sample 5 retired sites and re-run the coverage-context proof for one.
- Re-plant the `is_git_repo` guard break.
- Count static sites before and after with the census tool yourself.
- Check the Activity Log for any C-005 replacement entry.

## Post-tasks squad folds (binding)

1. **Freeze set is read-only for this WP** (NFR-001): the golden modules, the snapshots, `tests/core/_mission_create_golden.py`, `tests/_support/git_template/**` and `tests/_factories/__init__.py`. Check `git diff <WP01-commit> -- <freeze set>` is empty.
2. **Removing a name from the façade attribute list** (WP06 fold 3) happens only when de-routing, in the same commit, with a reason.
3. **Census**: report family-namespace **and** source-namespace counts, runtime applications and collected test counts (WP04 folds 2–4). NFR-004's budget is scope (a), family-module patches anywhere, plus scope (b), source-module patches of family-read names within the fixed file set (WP09 fold 6). Stdlib process-global names are reported separately.
4. Record planted breaks and retirement proofs as `git diff` patch blocks or exact commands in the Activity Log.
5. **Failing-first evidence (charter C-011) for a test-migration WP**: before rewriting a test, record a planted break of the behaviour it guards, which turns it red. Then show that the rewritten test turns red on the **same** break. That pair, one per migrated test or one per file for mechanical allow-flag swaps, is this WP's red→green record. The census baseline from WP04 is the measured "before".

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
