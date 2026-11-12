---
work_package_id: WP03
title: Protected-branch preflights judge the write surface (#7601)
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-012
- SC-002
- C-002
- C-003
planning_base_branch: fix/7546-settled-placement-surface
merge_target_branch: fix/7546-settled-placement-surface
branch_strategy: Planning artifacts for this mission were generated on fix/7546-settled-placement-surface. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7546-settled-placement-surface unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_implement_settled_protected_root.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement_claim.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_shared.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/specify_cli/cli/commands/test_implement_settled_protected_root.py
- tests/specify_cli/cli/commands/test_implement_claim.py
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/cli/commands/test_implement_characterization.py
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Protected-branch preflights judge the write surface (#7601)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

For a settled default Mission, `agent action implement WP01` and `agent tasks move-task …` (with or
without `--note`) succeed from a repository root checkout on protected `main`, and the WP frontmatter
is committed instead of silently skipped. Every protected-branch check judges **the branch of the
checkout the commit actually runs in**. Every non-settled Mission behaves byte-identically to today.
Protected targets are never written (FR-006, FR-007, FR-008, FR-012; #7601).

**Binding ruling** (escalation 2, option B — supersedes the earlier write_target ruling; see
`decisions/`):
- implement: the protected-branch preflight judges the HEAD of `_claim_commit_checkout(...)` — the
  same checkout the #5738 check (`_raise_if_claim_commit_head_mismatch`) already judges.
- move-task: the WP file's holder, `placement_seam(main_repo_root, slug).write_dir(WORK_PACKAGE_TASK).surface_root`,
  and its branch are fed to BOTH `_skip_target_branch_commit` and `_mt_refuse_protected_status_commit`.
- #2453 is NOT drained: its single allow-list entry in `tests/architectural/test_no_write_side_rederivation.py`
  is re-pointed to ONE shared holder-HEAD helper (count unchanged, never grown); #2453 stays open.

## Context

- Live failure: `implement WP01` on the settled fixture with the root on protected `main` →
  "Refusing to start implementation status on protected branch 'main' … rerun with --no-auto-commit"
  (`cli/commands/implement_claim.py:≈108-113`). `agent action implement` has no `--no-auto-commit`
  (exit 2). With the check patched out, implement succeeds and the claim lands on the topic branch.
- The check: `_raise_if_status_commit_protected` → `_status_commit_destination_branch(repo_root,
  fallback)` = `get_current_branch(repo_root) or fallback_branch` (the #2453 allow-listed line,
  `_ALLOW_LIST_SEED` ≈ 285-297, twin-guard `test_checkout_head_selector_entry_is_still_a_live_finding` ≈ 501).
- `_claim_commit_checkout(repo_root, feature_dir, slug)` (≈ 144) = `planning_checkout_root(...)`:
  the repository root checkout, or the topic holder for an unlanded default Mission (WP01 made the seam
  the authority behind it). For every non-settled Mission it is the repository root checkout, so
  "HEAD of the claim checkout" == today's `get_current_branch(repo_root)`: byte-identical.
- move-task (`tasks_move_task.py:≈697-709`): `st.skip_target_branch_commit =
  _skip_target_branch_commit(st.main_repo_root, slug, st.target_branch)`. That flag is more than the
  `--note` guard: when True it bypasses `_mt_refuse_protected_status_commit` (≈ 633, judges
  `st.target_branch`), feeds `_guard_protected_branch` (`tasks_transition_core.py:≈478`),
  `Emit.skip_primary` (≈ 1068) and verdict persistence (`tasks_verdict_persistence.py:≈508/525`).
  Today on a settled Mission the coordination worktree exists → skip=True → the protected check is
  bypassed AND the WP-file frontmatter commit is skipped (`wp_file_update: skipped` in JSON): silent
  data loss; with `--note` it refuses `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH`.
  Template for judging the commit ref: `tasks_map_requirements.py:≈258-262` (`st.commit_target.ref`).

Implement with: `spec-kitty agent action implement WP03 --agent claude --mission settled-placement-surface-01M78GR4`

## Branch Strategy

Base and merge target: `fix/7546-settled-placement-surface`; `single_branch`, sequential.

### Subtask T010: Red — protected root on a settled Mission, the silent skip, and positive controls

**Steps**:
1. Create `tests/specify_cli/cli/commands/test_implement_settled_protected_root.py` on the real fixture
   (`make_default_mission(tmp_path, THREE_LANES)` — root on protected `main`; write + commit `plan.md`
   before `run_finalize`; then `spec-kitty agent mission record-analysis --mission <slug> --input-file -`
   with a minimal valid report carrier — see `kitty-specs/settled-placement-surface-01M78GR4/analysis-report.md`
   for the shape, or reuse how existing implement tests seed the analysis gate). In every test
   `monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)` (vacuity guard).
   Cases (subprocess CLI from the root, matching how `test_implement_placement_reachability.py` invokes):
   - (a) `agent action implement WP01` → exit 0; `main` tip unchanged; a claim commit on the topic branch.
   - (b) `agent tasks move-task WP01 --to <lane> --note "…"` → exit 0; note + frontmatter committed on
     the topic; `main` unchanged.
   - (c) **silent-skip regression**: `move-task … --json` without `--note` → JSON does NOT report
     `wp_file_update: skipped`; the WP file change is committed on the topic branch.
   - (d) followable remedy (SC-003): any refusal printed in these flows names only options the invoked
     command accepts (assert `--no-auto-commit` is absent from `agent action implement` output).
2. Positive controls (FR-008 / byte-identical):
   - (e) explicit `--topology lanes_with_coord` Mission targeting protected `main` (coordination branch
     ≠ `main`), root on `main` → `implement` still refuses with the same code/exit as today, and
     move-task keeps skip=True semantics as today.
   - (f) existing tests that pin today's behaviour stay green UNCHANGED:
     `test_implement_phases.py::test_claim_preflight_allows_auto_commit_from_a_coordination_branch_when_the_target_is_protected`
     (≈ 489), `test_implement_claim.py` HEAD/fallback tests (≈ 104-118),
     `test_implement_characterization.py` (≈ 391). If one must change, STOP and report (the ruling is
     byte-identical behaviour for non-settled Missions).
3. Verify (a)–(c) red now, (e)/(f) green. Commit the test alone:
   `test(implement): pin implement and move-task from a protected root on a settled Mission (#7601)`.

### Subtask T011: implement preflight judges the claim checkout's HEAD

**Steps**:
1. Introduce ONE shared helper (in `implement_claim.py`), e.g.
   `_claim_checkout_branch(repo_root, feature_dir, mission_slug, fallback_branch) -> str`, returning the
   current branch of `_claim_commit_checkout(...)` (fallback when detached/unknown, exactly as today's
   `or fallback_branch`). Use it in `_raise_if_status_commit_protected` (thread `feature_dir`; check
   `implement_phases.claim_preflight` ≈ 365 for what it has) and, if natural, in
   `_raise_if_claim_commit_head_mismatch` so both checks read one helper.
2. Error handling: if resolving the claim checkout raises `(ActionContextError, StatusReadPathNotFound)`
   (the same typed set `_raise_if_claim_commit_head_mismatch` catches at ≈ 200-206), fall back to the
   repository root checkout's HEAD — today's behaviour — never skip the check.
3. Re-point the #2453 `_ALLOW_LIST_SEED` entry (and its twin-guard token) to the helper's single
   `get_current_branch(...) or fallback` line. Count unchanged; do not add entries. Update the WS#3
   comments (≈ 254-262, 351-353) to say the read moved into the shared helper and #2453 stays open.

### Subtask T012: move-task judges the WP file's holder

**Steps**:
1. In `tasks_move_task.py` (≈ 697-709), compute once:
   `holder = placement_seam(st.main_repo_root, st.mission_slug).write_dir(MissionArtifactKind.WORK_PACKAGE_TASK).surface_root`
   (owned Missions: unchanged path — `st.owned` short-circuits today) and the branch that holder has
   checked out (reuse T011's helper shape or the existing branch reader; ONE helper, no second
   current-checkout read site beyond the re-pointed #2453 entry — if a second read site is unavoidable,
   STOP and report).
2. Feed that branch to BOTH `_skip_target_branch_commit` (rename its parameter to `commit_branch` and
   update its docstring: "the branch the WP-file commit runs on") and `_mt_refuse_protected_status_commit`.
   For non-settled Missions the holder is the repository root checkout, which `_ensure_target_branch_checked_out`
   already puts on `st.target_branch` → byte-identical.
3. Keep `st.target_branch` for banners and status display.

### Subtask T013: Remedy text

1. `_protected_branch_status_commit_error` and `_protected_destination_hint`: thread a caller flag
   (e.g. `accepts_no_auto_commit: bool`) so only the top-level `spec-kitty implement` (which has the flag,
   `implement.py:≈388`) suggests `--no-auto-commit`; `agent action implement` (reaches it via
   `top_level_implement`, `workflow.py:≈1740`) gets a remedy it can follow. Name the branch judged and
   the checkout. One test per entry point.
2. `_guard_unsupported_skip_metadata`: name the branch judged; suggest only options `move-task` accepts
   (verify with `--help`).
3. No refusal code or exit code changes.

## Definition of Done

- Red commit first; green after. `main` never moves in any test.
- `pytest tests/specify_cli/cli/commands/test_implement_settled_protected_root.py tests/specify_cli/cli/commands/test_implement_claim.py tests/specify_cli/cli/commands/test_implement_phases.py tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/test_implement_placement_reachability.py -q`
  and `pytest tests/specify_cli/cli/commands/agent -q -k "move_task or skip_target or protected or verdict"` green.
- `pytest tests/architectural/test_no_write_side_rederivation.py -q` green with the entry re-pointed (same count).
- `test_protection_config_honoring.py` is a known local red (#5602): classify, do not chase.
- ruff/format/mypy clean; complexity ≤ 15; mark-status T010–T013 done.

## Risks

- Byte-identical for non-settled Missions is the contract: any existing test that must change is a STOP.
- Explicit-topology protected targets must still refuse (e).

## Reviewer Guidance

Confirm the single helper, the unchanged allow-list count, the silent-skip regression test, the
unchanged pinned tests, and that every printed remedy names an option the invoked command accepts.
