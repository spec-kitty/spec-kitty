---
work_package_id: WP03
title: Uncovered decision branches and create invariants
dependencies: []
requirement_refs:
- FR-008
- FR-011
- SC-004
- C-008
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-creation-degod-01M44467
base_commit: 861c8b74dd9c159c4feaf31f2c70e825e8562f32
created_at: '2026-10-04T20:24:40.761393+00:00'
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 1 - Behaviour freeze
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/core/
create_intent:
- tests/core/test_mission_creation_branch_coverage.py
- tests/core/test_mission_creation_invariants.py
execution_mode: code_change
model: ''
owned_files:
- tests/core/test_mission_creation_branch_coverage.py
- tests/core/test_mission_creation_invariants.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Uncovered decision branches and create invariants

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission mission-creation-degod-01M44467` and the Activity Log for returned feedback. Address every item.

---

## Objectives & Success Criteria

Before any code moves (spec C-008), cover the decision branches that **no test exercises today**, and pin the create invariants that the WP01 snapshot cannot observe (spec FR-008, FR-011, SC-004).

Done means:

- Each branch in the table below has a test that passes on the unchanged base **and** fails on a planted break of that branch. The planted break is recorded in the Activity Log.
- Prefer a real reproduction with no patch. Use fault injection (monkeypatching a name on `specify_cli.core.mission_creation`) **only** where no real route exists, and list each injected name in the module docstring. WP06's routing check and WP09's migration will pick these up, so keep them few and explicit.
- No assertion in any existing test file is edited. This WP only adds two files.

| # | Branch (current location) | Preferred route |
|---|---|---|
| 1 | protected-mint dirty-checkout refusal (`_mint_protected_single_branch_mission_branch`, ~:571-581) | **Already a WP01 golden refusal cell.** Here, add one focused assert on the message text and the "outside this mission's own scaffold" overlap rule: an untracked file *inside* the new scaffold path must not count as dirty (real repo, no patch). |
| 2 | `git checkout -b` failure (~:605-607) | Real: create a branch named exactly `kitty` so the ref `refs/heads/kitty/...` cannot be created (a directory/file ref conflict). The existence probe says "absent", and `checkout -b` then fails. Assert the `MissionCreationError` text prefix "Failed to create and check out mission branch". |
| 3 | topology corroboration failure (`_build_create_meta`, ~:1487-1497) | Probably needs injection: patch `classify_topology` *as imported into* `mission_creation` (check the import form first) to return a mismatching topology. Assert the refusal text. |
| 4 | MissionCreated persisted-payload mismatch (`_emit_create_events`, ~:1690) | Read the code. Inject the narrowest seam that makes the persisted payload differ, and assert the raised error. |
| 5 | coordination commit failure (`_commit_coord_create_events`, ~:1956-1957) | Real if possible, for example make the coordination worktree's index locked by creating `index.lock` in its git dir after the seed. Otherwise inject the committer it calls. Assert that the failed-create rollback ran: no coordination branch or worktree is left (FR-011). |
| 6 | bootstrap meta-commit skip (`_commit_create_scaffold`, ~:1821-1822, `_BOOTSTRAP_META_COMMIT_SKIPS`) | Read `_BOOTSTRAP_META_COMMIT_SKIPS` (~:76) and reproduce one skip reason for real, for example the protected-target skip on `main` with `LANES`. Assert the result's uncommitted-artifacts field and that no commit was created. |
| 7 | duplicate scan fail-closed on missing `meta.json` (`_find_live_duplicate_mission`, ~:425-426) | Real: an existing `kitty-specs/<slug>-ABCDEFGH/` with no meta, then create the same slug, and `MissionAlreadyExistsError` names that dir. |
| 8 | abandonment read failure (`_prior_mission_is_abandoned`, ~:378-379) | Real: a prior same-key mission with a corrupt `status.events.jsonl` (a non-JSON line) means the guard treats it as LIVE and refuses. |
| 9 | same-prefix neighbour guard (`_plan_orphan_scaffold_removal`, ~:668) | Call it directly on a real repo with untracked scaffolds `task-list-<mid8>` and `task-list-api-<mid8>` and `mission_slug="task-list"`. Only the former is planned. |
| 10 | coordination rollback early return (`_rollback_coordination_surface`, ~:765, `pre_seed_coord_tip is None` with `coordination_branch_created=False`) | Call it directly with a real repo and a pre-existing coordination branch. The branch survives and its tip is unchanged. |

## Context & Constraints

- The lines above are approximate (`origin/main` 9adc6880). Read the current function before writing each test.
- Grounding: `research/test-remediation.md` §3 ("Missing seam coverage") and `research/code-grounding.md` (invariants in the synthesis).
- Fixture builders: `tests._factories.coord_mission._init_repo_with_target`, `_write_protected_branches`, `tests._factories.provision_test_charter`, `tests/_support/git_template.clone_template`. Call `create_mission_core(..., allow_worktree_context=True)`.
- These tests will run against the **moved** code from WP06 onward. Assert on public behaviour (exceptions, files, refs), not on private call order, except where FR-011 pins an order.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T010 – Protected-mint branch coverage (rows 1–2)

- File: `tests/core/test_mission_creation_branch_coverage.py`, under a `class TestProtectedMintBranches`.
- Row 2 trick: on protected `main`, run `git branch kitty`. Then `kitty/mission-…` cannot be created as a ref. Confirm the probe returns non-zero for the full name. If git's behaviour differs from this plan, record it and fall back to injecting `subprocess.run` *only for the checkout call*, scoped with a wrapper that delegates other calls.

### Subtask T011 – Meta and events branch coverage (rows 3–6)

- Same file, `class TestMetaAndEventBranches`. For rows 3–5, keep the injection surface to one name per test, and pass `raising=True` to `monkeypatch.setattr` so a renamed target fails loudly.

### Subtask T012 – Duplicates and rollback branch coverage (rows 7–10)

- Same file, `class TestDuplicateAndRollbackBranches`. Rows 9–10 call private functions directly. That is acceptable here; it is the seam the pure cores in WP05 will take over, and WP09 re-points these to the cores.

### Subtask T013 – FR-011 invariant pins not visible in the snapshot

- File: `tests/core/test_mission_creation_invariants.py`. One test per invariant:
  1. **Failed-create restore order**: on protected `main` with `SINGLE_BRANCH`, force a failure *after* the mint (reuse the row-5 or row-6 mechanism, or inject a failure in `_commit_create_scaffold`). Assert that, afterwards:
     - HEAD is back on `main`;
     - the minted mission branch is deleted;
     - the disposable scaffold is removed;
     - no stray worktree remains.

     The ordering itself is pinned by the fact that a branch checked out cannot be deleted. The test goes red if the restore order is swapped; confirm that with a planted swap in `_restore_git_state_after_failed_create`.
  2. **Coordination rollback order**: on a coordination-routed create (`COORD`), force a failure after the coordination seed (row 5's mechanism). Assert that afterwards:
     - the coordination worktree and branch are gone;
     - the repository root checkout HEAD is restored;
     - no untracked coordination Mission dir is left behind.

     `_rollback_coordination_surface` clears the coordination Mission dir *before* the teardown (a dirty worktree refuses teardown) and tears the worktree down *before* the branch delete. Confirm with a planted swap (delete the branch first) that the test goes red. Note: no "status-log salvage" helper exists; an earlier grounding claim about one was wrong.
  3. **MISSION_ALREADY_EXISTS precedes the mint refusal**: on protected `main`, a re-create of an existing scaffold while the checkout is also dirty must raise `MissionAlreadyExistsError`, not the dirty-mint error.
  4. **Scaffold commit lands on the minted branch**: after a protected `SINGLE_BRANCH` create, the scaffold commit is reachable from `kitty/mission-…` and not from `main`.
  5. **#846 commit boundary at create**: `spec.md` is left untracked and `tasks/README.md` is committed (probe-confirmed). Assert the observed state of both.
  6. **Meta commit after origin binding**: register a pending-origin consumer through the public `core.adapters` registration (read `specify_cli.core.adapters`) that records whether `meta.json` is already committed when it is called. Assert it is called before the meta commit, and unregister it in teardown. If registration needs a patch, use the documented registration API, not a patch.
  7. **mid8 derived once**: `meta["mid8"] == meta["mission_id"][:8]`, and the directory name ends with it.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/core/test_mission_creation_decomposition.py tests/core/test_mission_create_checkout_restore.py tests/core/test_mission_create_coord_seed_rollback.py -q
uv run --frozen ruff check <new files> && uv run --frozen ruff format --check --force-exclude <new files>
.venv/bin/mypy <new files>
make test-fast
```

## Risks & Mitigations

- **Fault injection that silently stops intercepting after the WP06 move**: WP06's routing check must include every name you patch here. List the names in the module docstring under the exact heading `Patched façade names:`, so WP06 finds them.
- **Over-pinning private order**: pin only the orders named in FR-011.

## Review Guidance

- Each row and each invariant needs a planted break recorded in the Activity Log. Re-run at least two.
- The `Patched façade names:` docstring list is complete: grep the files for `monkeypatch.setattr` and `patch(`.
- No existing test file is changed.

## Post-tasks squad folds (binding)

1. Each row and invariant names its **concrete planted break**, recorded as a `git diff` patch block in the Activity Log, so a reviewer can `git apply` it.
2. A duplicate-refusal setup must commit the first mission's `spec.md`; a genesis-only prior is abandoned.
3. Confirmed by probe: row 2's `kitty` branch trick works (`rev-parse` exits 128; `checkout -b` fails with "cannot lock ref").

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
