---
work_package_id: WP03
title: Work-package claim commits only the paths the claim wrote
dependencies: []
requirement_refs:
- FR-009
- SC-006
- C-005
- C-004
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T13:24:43.503808+00:00'
subtasks:
- T015
- T016
- T017
- T018
phase: Phase 2 - Same rule, other writers
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/implement_claim.py
create_intent:
- tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/implement_claim.py
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/cli/commands/implement.py
- tests/specify_cli/cli/commands/test_implement_claim.py
- tests/specify_cli/cli/commands/test_implement_phases.py
- tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py
- tests/specify_cli/cli/commands/test_implement_characterization.py
- tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5673'
---

# Work Package Prompt: WP03 – Work-package claim commits only the paths the claim wrote

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission upgrade-migration-commit-scope-01M4AKVE`). Address every feedback item before completing.

---

## Objectives & Success Criteria

- **FR-009** (#5673): the claim commit (`chore: WPxx claimed for implementation`) contains only what the claim wrote: the primary-surface status pair (`status.events.jsonl`, `status.json`) on flat/`single_branch`/`lanes` topologies, plus the mission's `meta.json` **only when the claim itself changed it** (the first claim's VCS lock) **and it was clean before the claim**. Plus the claimed WP prompt **only when workspace allocation stamped it in this claim** (`base_branch`/`base_commit`/`created_at`, `frontmatter.py:331-334`) **and it was clean before the claim**. Never `.kittify/config.yaml`, never another WP's prompt, never `tasks.md`. (Amended after review cycle 1: the earlier "never the WP prompt" rested on a wrong premise; the claim does write the claimed prompt on lanes and coord topologies.)
- If `meta.json` was already dirty before the claim, the claim leaves it uncommitted and prints a warning naming the file.
- US4 scenario 1: with a dirty `.kittify/config.yaml`, the claim commit does not contain it and the file still carries the operator's edit. Scenario 2 (positive control): with a clean config, the claim commit content is exactly the claim-written set.
- **SC-006** (claim part): measured on a real repository with unrelated staged, dirty and untracked operator work.
- C-004: a `regression` test is red before the fix commit through the pre-existing entry point (`spec-kitty implement`), green at the end. C-005: the commit still goes through `safe_commit` with an explicit path list.

## Context & Constraints

- Spec US4, FR-009; plan IC-03; lens B in `<operator-local squad notes>` ("#5673 PARTIAL ... Fix: explicit list — status pair (flat/single_branch), meta.json only when `_ensure_vcs_in_meta` changed it (return a flag), never WP/tasks/config; meta.json dirty before claim → leave uncommitted + warn. Gate cannot catch #5673 (list contents) → list-level regression test").
- **Out of scope (C-003)**: the separate planning-artifacts auto-commit `implement_planning_commit.py:228` (`_ensure_planning_artifacts_committed_git`, called from `implement_phases.py:321-341` `commit_planning_artifacts`) which also commits operator edits to the WP prompt / `tasks.md` / `meta.json`. Do not edit `implement_planning_commit.py`; record in the Activity Log that it is the follow-up issue's surface.
- Do not edit `src/specify_cli/git/commit_helpers.py` (WP07), `lanes/implement_support.py`, or any #5856 file.

### Seams on origin/main 5ee323802

- `src/specify_cli/cli/commands/implement_claim.py:167-192` `claim_commit_paths(*, repo_root, feature_dir, wp_file, status_artifacts, routes_through_coord, include_config=True)`: bundle = `[wp_file, *_primary_surface_status_paths(...), meta.json if exists, .kittify/config.yaml if exists and include_config]`. Its docstring already says "#5673 ... is a one-line change here" — it is more than one line: the WP file, `tasks.md` and the unconditional `meta.json` are also wrong.
- `implement_claim.py:145-164` `_primary_surface_status_paths`: on coord topology drops `.worktrees/`-nested artifacts; on flat keeps `status.events.jsonl`, `status.json` **and `tasks.md`** (from `_collect_status_artifacts`, `cli/commands/agent/tasks_materialization.py:109-128`, candidates events/snapshot/tasks.md).
- `implement_claim.py:195-215` `_stage_claim_writes` (`--no-auto-commit`): stages the same bundle with `include_config=False` via `git add --force`.
- `implement_claim.py:218-321` `_commit_wp_claim_status(*, repo_root, feature_dir, mission_slug, wp_id, wp_file, auto_commit, status_result)`: returns early when no lane change (`:237`); builds the bundle (`:269-275`); `safe_commit(..., target=placement_seam(...).write_target(MissionArtifactKind.WORK_PACKAGE_TASK), paths=tuple(files_to_commit))` (`:293-301`); re-raises `SafeCommitPathPolicyError`/`SafeCommitHeadMismatch`, softens anything else to `Warning: Could not auto-commit lane change` (`:320-321`).
- `src/specify_cli/cli/commands/implement_phases.py:134-147` `_ensure_vcs_in_meta(feature_dir) -> VCSBackend`: wraps `implement_support.ensure_vcs_locked(feature_dir)` (`lanes/implement_support.py:1012-1025`), which **already returns `True` only when it wrote the lock**; the flag is discarded today (`locked` only drives a console line).
- `implement_phases.py:391-430` `allocate(...)`: refusals, `_raise_if_claim_commit_head_mismatch`, then `vcs_backend = _ensure_vcs_in_meta(feature_dir)` (`:407`), then `create_lane_workspace`; returns `AllocationResult(result, effective_base)` (dataclass `:72-77`).
- `implement_phases.py:458-490` `commit_claim(ctx, wp_id, status_result)` → `implement_claim._commit_wp_claim_status(...)`.
- `src/specify_cli/cli/commands/implement.py:384-434`: order is `claim_preflight` → `commit_planning_artifacts` (`:387`) → … → `allocate` (`:416`) → `record_claim` (`:422`) → `commit_claim(ctx, wp_id, status_result)` (`:434`).
- The WP file: since the #2816 cutover `implement` writes 0 runtime bytes to the WP file (`implement_phases.py:394-398` comment), so it is never claim-written.
- `single_branch` dirty-checkout refusal (`lanes/implement_support.py:98-120, 236-243`) **excludes** `.kittify/` and the mission's `meta.json`/status pair from its scan — that is why a dirty `config.yaml` (and a dirty `meta.json`) reaches the claim commit on `single_branch` without a refusal. Any other dirty tracked file (e.g. the WP prompt) is refused there with `WRITE_CHECKOUT_DIRTY` on `single_branch`, so test those through the in-process path or a `lanes` mission.
- Existing tests pinning today's bundle (must be updated, not deleted): `tests/specify_cli/cli/commands/test_implement_claim.py:57-110` (`claim_commit_paths` units, `:75-85` explicitly pins `config.yaml` "#5673 is NOT fixed here") and `:225-262` (real-git `_commit_wp_claim_status`, asserts `meta.json` and the WP file in HEAD / in the staged set). `tests/specify_cli/cli/commands/test_implement_phases.py:666-700` calls `_ensure_vcs_in_meta(...).value`. `tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py:260-320` constructs `AllocationResult(...)` and calls `commit_claim(ctx, wp_id, status)`. `tests/specify_cli/cli/commands/test_implement_characterization.py:820,852` patches the `vcs_lock` collaborator (`tests/specify_cli/cli/commands/_implement_dispatch.py:47` → `implement_phases._ensure_vcs_in_meta`) with a spy — check what the spy returns once the return type changes.
- `tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py` builds its own bundle (`:231-238`, does not call `claim_commit_paths`) and must stay green unchanged.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP03 --agent claude`. This WP lands in PR 2.

## Subtasks & Detailed Guidance

### Subtask T015 – Red-first `regression` tests through `spec-kitty implement` and the claim seam

- **Purpose**: pin #5673 at the list level (the architectural gate cannot see list contents — lens B).
- **Commit boundary**: T015 alone first (`test(5673): red-first claim commit carries only claim-written paths`); record RED in the Activity Log; fix commits follow.
- **Module** `tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py`, `pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]`.
- **Fixture hygiene**: build the child env allowlist-style (copy the shape of `tests/upgrade/preview_support/process.py::child_environment`, `:17-58`, or import it): isolated `HOME`, all `XDG_*`, `SPEC_KITTY_HOME`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<home>/.gitconfig`; no inherited `GIT_*`/`SPEC_KITTY_*` except `SPEC_KITTY_NO_UPGRADE_CHECK=1`; `PYTHONPATH=<checkout>/src` with `<checkout> = Path(__file__).resolve().parents[4]` (verify the depth); `PATH` containing `git`. Pin the agent config in `.kittify/config.yaml` (`agents: {available: [claude]}`) and the project metadata at the current schema so no upgrade gate fires. Initialise the repo on a **non-protected** branch (e.g. `git init -b work`; set `target_branch: work` in `meta.json`) so the claim commit is allowed and no `--commit-to-target` is needed. Local `user.name`/`user.email`, `commit.gpgsign=false`.
- **Mission fixture**: a minimal finalized `single_branch` mission ready to implement. Reuse the shape that `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py` and `test_implement_characterization.py:200-240` already build (meta.json with `mission_id`/`mid8`/`mission_slug`/`topology`/`target_branch`, `tasks.md`, one WP file with frontmatter, `lanes.json` with the `lane-planning` repo-root lane, a bootstrapped `status.events.jsonl` with the WP `planned`), committed. Do not hand-roll a different topology vocabulary — read `resolve_topology` for the stored value. If no reusable builder exists, put a small private builder in this module; keep it under ~80 lines.
- **Run**: `subprocess.run([sys.executable, "-m", "specify_cli", "implement", "WP01", "--mission", <slug>], cwd=repo, env=env, capture_output=True, text=True, timeout=180)` (check the exact selector flag with `--help` on the base).
- **Case 1 — dirty config (US4-1, red today)**: before implement, append `operator_edit: true\n` to the committed `.kittify/config.yaml` (unstaged), stage an unrelated new file `notes/staged.md`, and leave an untracked `scratch.txt`. Assertions, in order:
  1. `returncode == 0` and HEAD's subject is `chore: WP01 claimed for implementation` (proves the claim commit ran; if the planning-artifacts commit lands instead, assert on the commit with that subject via `git log --format=%H%x00%s`).
  2. `set(git show --name-only --format= <claim sha>) == {f"kitty-specs/{slug}/status.events.jsonl", f"kitty-specs/{slug}/status.json" if it exists in the tree, f"kitty-specs/{slug}/meta.json"}` — first claim writes the VCS lock, meta was clean → included. Exact equality (not `in`): kills a mutant that only drops `config.yaml` but keeps the WP file/`tasks.md`.
  3. `.kittify/config.yaml` not in that set; `git diff -- .kittify/config.yaml` still shows `operator_edit: true` (content intact, still unstaged).
  4. `notes/staged.md` still staged (`git diff --cached --name-only`) and not in the claim commit; `scratch.txt` still untracked.
  - RED on base: assertion 2 fails with `.kittify/config.yaml` and the WP file present in the commit.
- **Case 2 — clean config positive control (US4-2)**: same fixture without the config edit; assert the claim commit's file set equals case 1's expected set exactly. Kills a "commit nothing" mutant (empty set) and a "drop meta even when the claim wrote it" mutant (meta missing). Green on base? No — the WP file is in today's bundle, so it is red too; say so in the docstring.
- **Case 3 — meta.json dirty before the claim (in-process, red today)**: the CLI cannot reach it on `single_branch` because `commit_planning_artifacts` (`implement.py:387`) runs before the claim and may commit `meta.json` itself (out of scope). Drive the claim seam directly on a real repo, reusing the `claim_repo` fixture shape of `test_implement_claim.py:165-190`: commit `meta.json` WITHOUT `vcs`, then add an operator key to it (`"operator_note": "x"`, unstaged), then call the post-fix entry with the flags the phases compute (`meta_written=True`, `meta_dirty_before=True`) — for the RED commit, call today's `_commit_wp_claim_status(...)` signature and assert on outcome only, so the test is red on content, not on a `TypeError`: wrap the call in a small adapter `_claim(env, *, meta_dirty_before)` that passes the new kwargs only when `inspect.signature(...)` has them (remove the adapter in the fix commit). Assertions: `meta.json` not in the claim commit; `git diff -- kitty-specs/<slug>/meta.json` still shows `operator_note`; stdout contains `meta.json` and the word `uncommitted` (the warning). Kills a mutant that commits meta whenever it exists.
- **Case 4 — operator edits to the WP prompt and `tasks.md` (in-process)**: same seam, WP file and `tasks.md` modified and unstaged before the call; assert neither is in the claim commit and both keep their edits. Kills "WP file still bundled" and "`tasks.md` still bundled via `_collect_status_artifacts`".
- **Case 5 — `--no-auto-commit` staging**: through the seam with `auto_commit=False`: staged set equals the claim-written set (status pair [+ meta when written and clean]); `config.yaml`, the WP file and `tasks.md` unstaged. Extends `test_implement_claim.py:225-249`.
- **Validation**: record the RED lines (assertion messages) in the Activity Log; a red that is a fixture error (non-zero exit, refusal code) is not acceptable.

### Subtask T016 – Thread "the claim wrote meta.json" and "meta.json was dirty before" from `allocate` to the commit

- **Purpose**: the commit decides from facts the claim observed, not from `exists()` probes.
- **Steps**:
  1. `implement_phases.py:134-147`: change `_ensure_vcs_in_meta(feature_dir)` to return `tuple[VCSBackend, bool]` — `(VCSBackend.GIT, locked)` where `locked` is `implement_support.ensure_vcs_locked`'s return. Keep the printed line. Update the docstring ("returns the backend and whether this call wrote the lock").
  2. In `allocate` (`:391-430`), immediately BEFORE `_ensure_vcs_in_meta` (`:407`), probe whether the mission's `meta.json` differs from HEAD (index or worktree): use `kernel.git.status_entries(repo_root, pathspecs=(rel_meta,), untracked="no")` (`src/kernel/git/listing.py:269`) — non-empty ⇒ dirty. Never build a `git status` argv by hand (`tests/architectural/test_git_path_listing_owner.py` enforces the listing owner). On `GitCommandError`, treat as dirty (fail toward not committing it).
  3. Extend `AllocationResult` (`:72-77`) with two fields with defaults so existing constructors keep working: `meta_written: bool = False`, `meta_dirty_before: bool = False`.
  4. `commit_claim(ctx, wp_id, status_result, allocation: AllocationResult | None = None)` (`:458`) passes `meta_written=allocation.meta_written and not allocation.meta_dirty_before` and `meta_dirty_before=allocation.meta_dirty_before` into `_commit_wp_claim_status`. With `allocation=None` (legacy callers) pass `meta_written=False` — never infer from `exists()`.
  5. `implement.py:434`: `implement_phases.commit_claim(ctx, wp_id, status_result, allocation)` (`allocation` is bound at `:416`; every path that reaches `:434` went through it).
  6. Update `test_implement_phases.py:693` (`_ensure_vcs_in_meta(feature_dir)[0].value == "git"`) and add two `unit`/`fast` cases: first call returns `(GIT, True)`, second `(GIT, False)` (kills a mutant hard-coding `True`, which would commit a dirty-by-operator meta on every claim). Check the `vcs_lock` spy in `test_implement_characterization.py:820` still returns a value `allocate` can unpack; if it returns `None`, make the spy return `(VCSBackend.GIT, False)` and note it.
- **Files**: `implement_phases.py`, `implement.py`, `test_implement_phases.py`, possibly `test_implement_characterization.py`, `test_implement_runtime_frontmatter_claim.py` (its `AllocationResult(...)` at `:267` keeps working through the defaults; its `commit_claim(ctx, wp_id, status)` at `:319` keeps working through `allocation=None` — confirm and leave it unless a test asserts on meta in the commit).
- **Complexity**: `allocate` must stay ≤ 15; extract `_meta_dirty_before_claim(repo_root, feature_dir) -> bool` (pure apart from one listing call) and unit-test it on a real tmp repo (`git_repo` marker, not `fast`).

### Subtask T017 – `claim_commit_paths` becomes the explicit written-path list; warn on a pre-dirty `meta.json`

- **Purpose**: the product fix (FR-009).
- **Steps**:
  1. `implement_claim.py:167-192`: new signature `claim_commit_paths(*, feature_dir, status_artifacts, routes_through_coord, meta_written: bool) -> list[Path]`. Body: `[*_claim_status_paths(status_artifacts, routes_through_coord=routes_through_coord)]` + `[feature_dir / "meta.json"]` iff `meta_written`. Drop `repo_root`, `wp_file`, `include_config` (no claim path writes `config.yaml` — lens B: added in 421dda8cc, no writer on any implement path; the WP file gets 0 runtime bytes since #2816). Keep the order stable: status events, status snapshot, meta.
  2. Exclude `tasks.md`: `_primary_surface_status_paths` (`:145-164`) keeps it on flat topology; add a filter to `is_status_state_path(path)` only (the two STATUS_STATE files) for every topology, still dropping `.worktrees/`-nested paths on coord. Update its docstring (the #3784 note stays true: coord `tasks.md` was already dropped; now the primary one is too, because the claim never writes it). Before relying on that, verify on a real flat claim that `tasks.md` bytes are unchanged by the claim (`start_implementation_status` does not rewrite it); if it does change, stop and report — the spec says never `tasks.md`.
  3. `_commit_wp_claim_status` (`:218-321`): replace `wp_file` param use with the new flags `meta_written: bool = False, meta_dirty_before: bool = False` (keep `wp_file` as an accepted-but-unused keyword only if a caller outside this WP's files passes it — grep; otherwise remove it). When `meta_dirty_before` print once: `[yellow]Warning:[/yellow] kitty-specs/<slug>/meta.json had uncommitted changes before the claim; the claim's VCS lock was left uncommitted with them — commit meta.json yourself.` (hoist the text to a module constant). When the bundle is empty (coord topology with no meta write — the status pair was already committed to the coordination branch by the transactional emitter), skip `safe_commit` entirely and print today's success line; do not let `SafeCommitEmptyChangeset` fall into the soft-warning branch (kills a mutant that prints a spurious "Could not auto-commit" on every coord claim).
  4. `_stage_claim_writes` callers (`:241-254`) use the same list (no separate `include_config` variant any more).
  5. Rewrite the pinning tests in `test_implement_claim.py`: `:57-110` → assert the new exact lists (flat: status pair; flat + `meta_written=True`: status pair + meta; coord: `[]` / `[meta]`; `tasks.md` never present — a parametrised case per topology). `:225-262` → exact HEAD / staged sets without the WP file and without `config.yaml`. Keep `test_claim_commit_reraises_*` and `test_claim_commit_softens_any_other_failure` (`:265-300`) green.
  6. Update the module docstring (`:1-5`) and the `claim_commit_paths` docstring: "the claim commit carries exactly the paths the claim wrote (#5673)".
- **Files**: `implement_claim.py`, `test_implement_claim.py`.
- **Validation**: T015 cases 1-5 green; `pytest tests/specify_cli/cli/commands/test_implement_claim.py tests/specify_cli/cli/commands/test_implement_claim_commit_head_mismatch.py tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py -q` green.

### Subtask T018 – Verification and closeout

- **Steps**:
  1. Remove the T015 signature adapter in the fix commit (call the new signature directly).
  2. Targeted runs (no full suites):
     ```bash
     .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py tests/specify_cli/cli/commands/test_implement_claim.py \
       tests/specify_cli/cli/commands/test_implement_phases.py tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py \
       tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/test_implement_claim_commit_head_mismatch.py \
       tests/specify_cli/cli/commands/test_issue_610_head_mismatch_not_swallowed.py tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py \
       tests/integration/test_issue_3784_coord_tasks_md_primary_bundle_guard.py tests/integration/test_implement_review_flow.py -q
     .venv/bin/python -m pytest tests/architectural/test_git_path_listing_owner.py -q
     ```
  3. `ruff check` + `ruff format --check --force-exclude` on touched files; `mypy src/specify_cli/cli/commands/implement_claim.py src/specify_cli/cli/commands/implement_phases.py src/specify_cli/cli/commands/implement.py`.
  4. `git diff --stat <planning base> -- src/specify_cli/cli/commands/implement_planning_commit.py src/specify_cli/git/commit_helpers.py` must be empty.
  5. Activity Log: RED and GREEN lines; draft WP08 changelog text ("`spec-kitty implement` no longer commits your `.kittify/config.yaml` edit, the WP prompt or `tasks.md` into the claim commit; an already-modified `meta.json` is left uncommitted with a warning (#5673)"); note the out-of-scope planning-artifacts commit as the follow-up issue's surface.
  6. `spec-kitty agent tasks mark-status T015 T016 T017 T018 --status done --mission upgrade-migration-commit-scope-01M4AKVE`.

## Test Strategy

```bash
# red on the planning base (T015 commit), green at the end
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_implement_claim_scope_5673.py -q
# neighbours
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_implement_claim.py tests/specify_cli/cli/commands/test_implement_phases.py -q
```

Markers: the new module is `git_repo`+`non_sandbox`+`regression` (subprocess + real git); pure list cases added to `test_implement_claim.py` keep its `_FAST` (`unit`+`fast`) marker and use no subprocess. Never `p0_repro`.

## Risks & Mitigations

- **Topology variants**: coord topology routes the status pair to the coordination branch through the transactional emitter, so the primary claim bundle can be empty — skip the commit instead of warning. `lanes` claims run from the repository root checkout too (`_raise_if_claim_commit_head_mismatch`, `implement_claim.py:102-142`); the list rule is identical.
- **Claim that rewrites `tasks.md`** (unexpected): verify before excluding; escalate rather than silently drop a claim-written path.
- **Pre-dirty detection race**: the probe runs after `commit_planning_artifacts` and before the lock write in the same process; a concurrent agent writing `meta.json` in between is indistinguishable from the claim — accepted (single write checkout per WP).
- **Spy/mocks returning the old shape**: characterization dispatch spy (`_implement_dispatch.py:47`) — adapt the spy, never the production signature back.
- **`--no-auto-commit` regression (#3471)**: the staged set must still be exactly the claim's writes; T015 case 5.

## Review Guidance

- Verify the T015 commit precedes the fix and its RED is a content assertion on the claim commit's file set (exit 0 first).
- Verify the claim commit's file set is asserted with exact equality, and that a positive control proves the commit still happens.
- Verify `meta.json` inclusion is driven by the `ensure_vcs_locked` return value AND the pre-claim dirty probe, never by `exists()`.
- Verify no `git status` argv is hand-built (listing owner gate) and `implement_planning_commit.py` is untouched.
- Run case 1 yourself and inspect `git show --stat HEAD`.

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Analysis fold AN-COV-002: C-004 (red-first) added to `requirement_refs`.
- 2026-10-07 – orchestrator (recording implementer evidence) – Cycle 0: c3b85ede5 (red: 4 failed / 1 passed on base; extra config.yaml, meta.json, WP prompt, tasks.md) and eb20dc7d1 (fix). Review cycle 1 rework: c97058eff red at eb20dc7d1, 4 failed / 5 passed ((a) lanes claim commit lacks the stamped WP prompt; (b) `--no-auto-commit` leaves it unstaged; (c) stamped-but-dirty prompt gives no warning; (d) coord claim exits 1, `safe_commit: refusing to stage path under .worktrees/`). 7473f01be green: scope module 9 passed; the six cycle-1 regressions pass unmodified; the `destroy_lane` fixture change is reverted (file byte-identical to base); the gate set gives 240 passed; ruff, format, C901 and mypy are clean. FR-009 amended in fc14ace. NOTE: with auto-commit, an ordinary operator prompt edit is committed by the out-of-scope planning-artifacts step (C-003 follow-up), so case (c) uses a tolerated frontmatter edit under `--no-auto-commit`.
- 2026-10-07 – orchestrator – Changelog draft for WP08 (#5673): "`spec-kitty implement` no longer commits your `.kittify/config.yaml` edit, other WPs' prompts or `tasks.md` into the claim commit. The claim commit now carries only what the claim wrote: the status files, `meta.json` on the first claim, and the claimed WP prompt's workspace stamp on lanes and coordination missions. A `meta.json` or WP prompt you had already modified is left uncommitted, with a warning naming it (#5673)."
