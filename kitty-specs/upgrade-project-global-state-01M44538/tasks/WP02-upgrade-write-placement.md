---
work_package_id: WP02
title: Upgrade write placement (source fix)
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-011
- NFR-001
- C-001
- C-006
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-5457-upgrade-project-global-state
merge_target_branch: issue-5457-upgrade-project-global-state
branch_strategy: Planning artifacts for this mission were generated on issue-5457-upgrade-project-global-state. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5457-upgrade-project-global-state unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-project-global-state-01M44538
base_commit: b33766f3b95528e03a4c0a1df73d9fcd159bcc60
created_at: '2026-10-04T20:30:28.587959+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Source fix
history:
- at: '2026-10-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_upgrade_integrating_worktrees.py
- tests/integration/test_upgrade_live_lanes_cli.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/runner.py
- tests/upgrade/test_upgrade_worktree_commit.py
- tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py
- tests/upgrade/test_upgrade_integrating_worktrees.py
- tests/integration/test_upgrade_live_lanes_cli.py
- tests/upgrade/test_worktree_stamp_guard.py
- tests/upgrade/test_symlinked_ignore_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Upgrade write placement (source fix)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`):
`spec-kitty agent profile show python-pedro` and `spec-kitty charter context --action implement --json`. Apply the profile before reading on.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Every feedback item is a TODO.

---

## Objectives & Success Criteria

`spec-kitty upgrade` must write, stamp and commit **nothing** in an *integrating worktree*: a linked worktree under `.worktrees/` whose checked-out branch is a `kitty/mission-…` branch (mission, lane or coordination branch), or whose branch cannot be read (detached HEAD, which fails safe). Project-global state is then written and committed only in the repository root checkout. Worktrees on any other branch keep today's behaviour exactly, including #2385 commit-on-own-branch and the #4972 version-only alignment.

With this WP alone, every **future** upgrade with live lanes consolidates (Path A, Path B) and coordination missions keep moving (Path C).

Spec refs: FR-001, FR-002, FR-003, FR-011, NFR-001, C-001, C-006; Stories 1, 2 and 3. Read `spec.md`, `plan.md` (IC-02), `research.md` D1, and `research/code-grounding.md` §1–§2 and Appendix A (the per-branch touched-file list).

## Context & Constraints

- **C-001 (hard)**: change only *worktree selection and write placement*. Do **not** touch how upgrade computes or reports its result (`UpgradeResult`, `worktree_failures`, `effective_success`, exit codes). A separate mission (C6, #4925/#4893) is editing that area of `upgrade/runner.py` and `cli/commands/upgrade.py` in parallel. Keep the diff to the skip seam so the second PR to land rebases cleanly.
- There is **one seam**: `MigrationRunner._upgrade_worktrees` (`src/specify_cli/upgrade/runner.py:374ff`). `upgrade_worktrees_only` (`:237-260`) delegates to it, so a single skip covers both the migrations pass and the no-migrations stamp pass.
- Branch lookup: `specify_cli.core.git_ops.get_current_branch(path)` returns `None` on a detached HEAD or error, which is treated as integrating. Recognition: `specify_cli.lanes.branch_naming.parse_mission_slug_from_branch(branch) is not None` (it accepts `kitty/mission-…` in new and `NNN-` legacy forms, and lane suffixes; the coordination branch uses the mission grammar). Do **not** add a local regex.
- `.kittify` resolution inside a worktree already goes to the repository root checkout (`core/paths.py:197 locate_project_root`), so leaving a lane's pre-upgrade copy is harmless (grounding §4).
- Charter SO-4 / C-006: **the red test is committed before the fix**. Any tidy-first extraction comes before the red test.

## Branch Strategy

- **Strategy**: lanes · **Planning base branch**: `issue-5457-upgrade-project-global-state` · **Merge target branch**: `issue-5457-upgrade-project-global-state`.

## Subtasks & Detailed Guidance

### Subtask T005 – Red test: integrating worktrees are untouched by `upgrade`

- **Purpose**: pin FR-001, FR-002 and FR-003 through the pre-existing entry point, the `spec-kitty upgrade --yes` CLI.
- **Steps**:
  1. In `tests/upgrade/test_upgrade_integrating_worktrees.py`, use WP01's `build_older_version_lanes_project` (from `tests/integration/primary_owned_fixtures.py`) to get a project at an older recorded version with:
     - two lane worktrees on real lane branches;
     - for `lanes_with_coord`, a coordination worktree on the coordination branch;
     - **plus** one non-integrating worktree under `.worktrees/` on an unrelated branch (e.g. `feature/unrelated`), which is the FR-003 positive control on the same fixture.
  2. Record each branch tip and each worktree's `.kittify/metadata.yaml` bytes. Run `spec-kitty upgrade --yes` via `run_cli` (subprocess, isolated env).
  3. Assert:
     - every lane branch tip and the coordination branch tip are **unchanged**;
     - each integrating worktree's `metadata.yaml` bytes and `git status --porcelain` are unchanged (no write, no dirt);
     - the repository root checkout's branch gained the upgrade commit;
     - the non-integrating worktree's branch **did** gain its own upgrade commit, and its `metadata.yaml` advanced to the target version (positive control: proves the probe can see a worktree upgrade).
  4. Parametrise over `lanes` and `lanes_with_coord`. Add a detached-HEAD worktree case, which must be skipped.
  5. Run it. It must be **RED** on the current code. Commit it alone: `test(upgrade): red — upgrade writes and commits in integrating worktrees (#5457)`.

### Subtask T006 – Implement the skip seam

- **Steps**:
  1. Add `def _is_integrating_worktree(worktree: Path) -> bool` (module-level private, or a `@staticmethod`, matching the file's idiom), with a docstring citing #5457 and the glossary terms (repository root checkout; integrating worktree = a branch that integrates back into the mission's target branch).
  2. In `_upgrade_worktrees`, right after the `if not worktree.is_dir(): continue` check, add `if _is_integrating_worktree(worktree): continue`. Emit nothing into `result["warnings"]` / `["errors"]` / `["worktree_failures"]` (C-001: the result shape is unchanged). If an informational console line is wanted, use the existing console the runner already holds, and keep it to one line per run, not per worktree.
  3. Do not delete `_reconcile_worktree_bookkeeping` / `_aligned_worktree_timestamp`. They still serve non-integrating worktrees (#4972).
  4. Make T005 green. Commit: `fix(upgrade): write project-global state once; skip integrating worktrees (#5457)`.

### Subtask T007 – Re-pin the defect-pinning tests (FR-011, boy-scout)

- **Steps**:
  1. `tests/upgrade/test_upgrade_worktree_commit.py`:
     - `test_genuine_worktree_migration_still_mints_fresh_stamp_not_main_aligned` (~:157-219, assertion ~:211) asserts a divergent per-worktree stamp. Inspect which branch its fixture worktree is on.
       - If it is a `kitty/mission-…` branch, re-pin the test to the new invariant: the integrating worktree is untouched.
       - If it is a non-integrating branch, the assertion still describes intended behaviour for non-integrating worktrees. Keep it, rename it if needed for clarity, and add a sibling assertion for the integrating case.
     - The #2385 per-worktree commit assertions (~:91 and others) get the same treatment: keep them for non-integrating fixtures, and re-pin them for integrating fixtures.
  2. `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py`:
     - ensure the alignment tests run on **non-integrating** worktrees, so the #4972 regression arm stays meaningful;
     - where a fixture models a lane or coordination branch, re-pin it to "untouched".
  3. Never delete a test to get green (charter SO-4: judge the test; stale → re-pin). Note each re-pin in the commit message body.

### Subtask T008 – Real-CLI fresh-upgrade paths A / B / C

- **Purpose**: Stories 1, 2 and 3 end to end through the pre-existing entry points.
- **Steps** (in `tests/integration/test_upgrade_live_lanes_cli.py`, real CLI via `run_cli`):
  - **Path A**:
    - Older-version `lanes` project with 2 lanes, each with committed work. Drive both WPs to `approved` the way the issue reproducer does (`agent tasks mark-status`, `agent status emit … --to approved`), or via the fixture if it already does that.
    - Run `upgrade --yes`, then `consolidate --mission <slug>`.
    - Assert exit 0, both lane files present on the target, and 0 upgrade commits on lane branches.
  - **Path B**:
    - One lane, target branch `work` (the repository root checkout on `work`).
    - Run `upgrade --yes`, record the acceptance verdict, `accept`, then `consolidate`. Mirror the issue's Path B script steps (grounding Appendix A and the issue body).
    - Assert exit 0, with no `TARGET_BRANCH_CONTENT_CONFLICT` in the output.
  - **Path C**:
    - A `lanes_with_coord` project with WP02 `for_review` at upgrade time.
    - Run `upgrade --yes`, then `agent action review WP02 --mission <slug>`.
    - Assert exit 0, WP02 `in_review`, and no `LANE_AUTO_REBASE_FAILED`.
    - If an unrelated gate blocks it (e.g. `analysis_report_required`), satisfy that gate in the fixture (record an analysis report through the CLI, as the issue's Path B script does). Do not skip it.
  - These go green with T006 alone. Write them **before** T006 and confirm them red, alongside T005, if practical. Otherwise commit them right after T005 as part of the red set and record the red output in the Activity Log.
  - If a real-CLI path is genuinely too slow for the default tier, mark it with the repo's existing slow/integration marker (check `pytest.ini`) rather than dropping it, and say so.

## Post-tasks squad folds (binding)

- **The defect-observable positive control moved here from WP01** (WP01 review cycle 1). In T005, before the fix, assert via `observe_upgrade_divergence(project)` that `branches_with_divergent_metadata` and `branches_with_upgrade_commit` are **non-empty** (red-phase evidence, recorded in the Activity Log). After the fix, assert both are `[]`. The WP01 fixture self-test asserts only fix-invariant facts.
- **The exact integrating rule** (refines T006):
  - a worktree with **no `.git` entry** (a plain directory, not a git worktree) is **not** integrating, so today's behaviour is kept;
  - a real git worktree whose branch `get_current_branch` cannot read (detached HEAD) **is** integrating (fail safe);
  - otherwise it is integrating iff `parse_mission_slug_from_branch(branch) is not None`.

  Test all three on the same fixture. Update the spec edge case wording only if WP06 or the reviewer asks; the plan already records this.
- **Re-pin the collateral test files you now own** (they would go red):
  - `tests/upgrade/test_worktree_stamp_guard.py` builds its worktrees on `kitty/mission-lane-*`, so they all become integrating. Move those fixtures to non-integrating branch names so the #3376 / FR-012 `worktree_failures` coverage stays meaningful. Add one test showing that a `kitty/mission-…` worktree is skipped there.
  - `tests/upgrade/test_symlinked_ignore_guard.py::TestWorktreeMigrationGuard`: plain directories without git are not integrating under the rule above. Confirm it stays green; re-pin only if needed.
  - Also run `tests/upgrade/test_m_3_2_5_agents_skills_gitignore.py` (it passes today only because its plain directory reads the parent repo's branch) and fix fragility only inside owned files.
- **NFR-001 and the edge cases**:
  - a spy migration (`runs_on_worktrees=True`, counting `detect()` calls) registered as `tests/upgrade/test_upgrade_worktree_commit.py:185` does, asserting 0 calls for integrating worktrees and >0 for the non-integrating control;
  - a no-migrations run (`upgrade_worktrees_only`) over an integrating worktree, which must stay untouched;
  - `--dry-run` and `--no-worktrees` are unchanged.
- **The lane runtime still works.** In T008, after `upgrade`, run `spec-kitty agent tasks status --mission <slug>` with `cwd` set to a skipped lane worktree, which must exit 0. This pins the "a stale lane `.kittify` copy is inert" assumption.
- **Path C fallback** (aligned with WP05): keep `upgrade --yes` as real CLI. Try `agent action review` through the CLI first. If an unrelated gate makes it impractical, fall back to `sync_lane_after_coordination_commit`, the production function `review` calls, and assert the coordination branch tip and the lane branch tip carry no upgrade commit. Record the CLI attempt and the reason in the Activity Log.
- **Red assertions name the defect**: no lane commit with subject `chore: apply spec-kitty upgrade changes`, and so on. The Path A and B CLI tests assert the specific refusal text is absent and the WP files are present.
- **Gate-file rights**: if a named architectural gate goes red because of a *legitimate* change, you may edit **only** that gate's own pin or allowlist entry. Name the file in the commit body with a one-line justification, and the reviewer re-checks it. Never touch `dead_symbol_allowlist.yaml` or `_git_path_listing_census.py`, and never add a new allowlist (C-007). Expected gates: `test_no_dead_symbols.py`, `test_migration_chain_integrity.py`, `test_no_op_stable_writes.py`, `test_layer_rules.py`.

## Test Strategy

- Targeted: `uv run --frozen pytest tests/upgrade/ tests/integration/test_upgrade_live_lanes_cli.py tests/e2e/test_upgrade_post_state.py -q` (record the counts).
- Gates: `uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_migration_chain_integrity.py tests/architectural/test_no_op_stable_writes.py tests/architectural/test_layer_rules.py -q`.
- `make test-fast`. Run `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed files. Complexity ≤ 15 in `_upgrade_worktrees` (it is long; if the new line pushes it over, extract the per-worktree body into a helper as a tidy-first commit **before** the red test).

## Risks & Mitigations

- **A C6 collision on `runner.py`**: keep the diff minimal and line-local.
- **Existing fixtures on ad-hoc branch names**: these become "non-integrating" and keep the old behaviour. This is intended, and it keeps #4972/#2385 coverage alive.
- **A slow real-CLI path**: reuse the WP01 builders, and run upgrade once per scenario.

## Review Guidance

- Is the red test committed before the fix, and was it red for the right reason (a lane commit exists or the lane metadata changed)?
- Does the positive control (the non-integrating worktree) prove the probe works?
- The result and exit computation are untouched (diff review against C-001).
- Re-pins are justified one by one; no test is deleted.

## Activity Log

- 2026-10-04T19:40:00Z – system – Prompt generated via /spec-kitty.tasks
