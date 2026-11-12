---
work_package_id: WP04
title: 'Baseline commit and target banner read through the seam (#7551 baseline, #7595)'
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-009
- SC-004
planning_base_branch: fix/7546-settled-placement-surface
merge_target_branch: fix/7546-settled-placement-surface
branch_strategy: Planning artifacts for this mission were generated on fix/7546-settled-placement-surface. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7546-settled-placement-surface unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/cli/commands/agent/test_baseline_and_banner_settled.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/core/git_ops.py
- src/specify_cli/core/paths.py
- tests/architectural/test_no_read_side_bypass.py
- tests/specify_cli/cli/commands/agent/test_baseline_and_banner_settled.py
role: implementer
tags: []
tracker_refs: []
---

# WP04 — Baseline commit and target banner read through the seam (#7551 baseline, #7595)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

After settlement, the `for_review` baseline capture commits `tasks/<WP>/baseline-tests.json` on the
topic branch in the checkout that holds it (FR-005), and the target-branch helpers behind the
`implement` / `move-task` banner read the Mission's `meta.json` where the seam finds it instead of
falling back to the primary branch (FR-009, #7595).

## Context

- Baseline: `cli/commands/agent/workflow_executor.py` ≈ lines 1400–1565.
  `_baseline_artifact_needs_commit(authority_root=main_repo_root, artifact)` runs `git status` in the
  repository root checkout with a pathspec under the ignored `.worktrees/` → empty → no commit, no
  warning. `move-task --to for_review` exits 0 and leaves the file untracked in the coordination
  worktree. The commit itself uses `worktree_root=authority_root` (the root when not owned) and target
  `_resolve_workflow_placement(WORK_PACKAGE_TASK)` (the topic branch).
- #7595: `core/git_ops.py::resolve_target_branch` (≈ 440–475) and
  `core/paths.py::get_feature_target_branch` (≈ 870–900) compose the literal root Mission dir with the
  module-private `_compose_primary_feature_dir` (deliberately "unrouted foundation sites", sanctioned by
  tokens in `tests/architectural/test_no_read_side_bypass.py::_FOUNDATION_SANCTION_SEED`), then fall
  back to `resolve_primary_branch` when `meta.json` is absent there — which it is after settlement.
- Operator ruling: fold #7595 by collapsing onto the one placement-seam reader;
  `placement_seam(root, slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)` is that reader (it is what
  `coordination/planning_commit.primary_partition_checkout` already uses, and it routes through
  `default_mission_topic_dir`). If that collapse needs any other design choice, STOP and report.
- WP01 made `write_dir(kind).surface_root` the containing checkout.
- **Blast radius (not banner-only)**: `get_feature_target_branch` also feeds the write-side composition
  root — `resolve_placement_only` (`mission_runtime/resolution.py:≈2047`, the `write_target` of every
  kind), `mission_context_for` (≈1474), `_assemble_core_fragments` (≈3272), `lifecycle_phase.py:≈271`,
  `lanes/implement_support.py:≈300` (expected HEAD), `tracer_append.py:≈166`, `workflow.py:≈1160`. For a
  settled Mission whose declared target is not the primary branch, every one of these flips from the
  primary-branch fallback to the declared target — the correct value (operator informed). Test it.
- `core/paths.py::resolve_merge_target_branch` (foundation sanction 2/4) reads the same root-only
  `meta.json`; it is OUT of scope (C-006): keep its sanction row untouched and list it as a follow-up in
  the PR notes.

Implement with: `spec-kitty agent action implement WP04 --agent claude --mission settled-placement-surface-01M78GR4`

### Subtask T014: Red

**Steps**:
1. Create `tests/specify_cli/cli/commands/agent/test_baseline_and_banner_settled.py` on the real fixture.
   - Baseline: settle, record analysis (see WP03's recipe), configure a real `review.test_command` that
     writes a tiny junit XML (check how `tests/review/` or `tests/specify_cli/cli/commands/agent/`
     baseline tests configure it: `grep -rln "baseline-tests.json" tests | head`), run implement WP01 from
     an unprotected root (`standing_on="dev"`, so WP03's fix is not needed), then `move-task WP01 --to
     for_review` → assert `git show <topic>:kitty-specs/<slug>/tasks/<WP01 dir>/baseline-tests.json`
     succeeds and the coordination worktree has no untracked baseline file.
     If driving the whole flow is too costly, call the baseline commit helper in-process with the
     settled fixture's paths — but the CLI path is preferred (C-007).
   - Banner: settle, then `resolve_target_branch(slug, root, current_branch=…)` (slug FIRST — check the
     signature) and `get_feature_target_branch(root, slug)`
     return the Mission's `target_branch` (the fixture's `return_branch`, e.g. `dev` with
     `standing_on="dev"` — pick a non-primary value so a `main` fallback is distinguishable).
   - Write side on the same `standing_on="dev"` settled fixture: assert
     `placement_seam(root, slug).write_target(TRACER_FILE).ref` and `…(WORK_PACKAGE_TASK).ref` are the
     topic branch, and that the lifecycle phase / landed-target reads report `dev`, not `main`.
   - `monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)` in every red test
     so a leaked variable cannot make it pass vacuously.
2. Commit red: `test(workflow): pin baseline commit and target banner on a settled Mission (#7551, #7595)`.

### Subtask T015: Baseline in the holder checkout

**Steps**: compute `holder = placement_seam(main_repo_root, slug).write_dir(WORK_PACKAGE_TASK).surface_root`
(owned: keep `authority_root`) and use it ONLY for `_baseline_artifact_needs_commit` and as the
`safe_commit` `worktree_root`. Keep `authority_root` for `resolve_scope_source` and
`resolve_review_test_timeout` (≈ lines 1487-1488). If the artifact lies outside the checkout used,
warn naming the file and the checkout instead of returning silently; because `quiet=st.json_output`
suppresses console output in `--json` mode, also put the warning into the JSON envelope (or the
module's logger) so FR-005 holds in both modes. Add a test for the new warning arm. Keep the function ≤ 15 complexity (extract a
helper with a unit test).

### Subtask T016: Target helpers through the seam

**Steps**:
1. In both helpers, replace `_compose_primary_feature_dir(...)` with
   `placement_seam(<root>, slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)` inside the existing
   deferred import (keep the import-layering comment accurate: `core/paths.py` is imported early).
   Keep the `read_target_branch_from_meta` + primary-branch fallback for a genuinely absent `meta.json`.
   If `read_dir` can raise for a malformed handle where the old code did not, catch only that typed
   error and keep today's fallback (document why).
2. Update `tests/architectural/test_no_read_side_bypass.py`: remove (shrink) the two
   `_FOUNDATION_SANCTION_SEED` entries for `resolve_target_branch` / `get_feature_target_branch` now that
   they no longer call `_compose_primary_feature_dir`. Do not add entries.
3. Rewrite the two "RECORDED FOUNDATION SITE … deliberately UNROUTED" comments to say they now read
   through the seam (#7595).

## Definition of Done

- Red first, green after. `pytest tests/mission_runtime -q`,
  `pytest tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py -q`, the
  lifecycle_phase tests (`grep -rl lifecycle_phase tests | head`), `pytest tests/specify_cli/lanes -q -k implement_support`
  (or `tests/lanes`), `pytest tests/specify_cli/core -q -k "target_branch"`,
  `pytest tests/specify_cli/cli/commands/agent -q -k "baseline or workflow"`,
  `pytest tests/architectural/test_no_read_side_bypass.py tests/architectural/test_read_surface_placement_guard.py tests/architectural/test_single_mission_surface_resolver.py -q` green.
- Run the direct test modules of `core/git_ops.py` and `core/paths.py`
  (`grep -rl "resolve_target_branch\|get_feature_target_branch" tests | head -20`).
- ruff/format/mypy clean; mark-status T014–T016 done.

## Risks

24 callers; an import cycle if the deferred import moves to module level; a Mission with no
`meta.json` anywhere must still fall back to the primary branch.

## Reviewer Guidance

Check the sanction entries were removed (not re-pointed to a new bypass), the fallback still exists for
an absent `meta.json`, and the baseline warning is no longer silent.
