---
work_package_id: WP04
title: Merge bookkeeping commits only the mission's meta.json
dependencies: []
requirement_refs:
- FR-010
- SC-006
- C-005
- C-004
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T13:24:49.398661+00:00'
subtasks:
- T019
- T020
- T021
- T022
phase: Phase 2 - Same rule for the other automatic commits
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/mission_number/
create_intent:
- tests/consolidation/test_bake_commit_scope_meta_only.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/mission_number/bake.py
- tests/consolidation/test_ordering_bake_seam.py
- tests/consolidation/test_bake_commit_scope_meta_only.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5443'
---

# Work Package Prompt: WP04 – Merge bookkeeping commits only the mission's meta.json

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

- **FR-010**: when consolidation assigns a `mission_number` on the operator's primary checkout, the bookkeeping commit contains **only** the mission's `meta.json`, lands on the merge target branch, and goes through the sanctioned bookkeeping seam (`safe_commit` underneath). When the primary checkout is on another branch, is detached, or `meta.json` already differs from HEAD (index or worktree), nothing is written or committed there and the number is reported as not yet baked. The temp-worktree commit on the mission branch names its path (`commit --only -- <rel_meta>`).
- **SC-006**: measured on a fixture with unrelated staged, unstaged and untracked operator work: the bookkeeping commit's file list is exactly `{kitty-specs/<slug>/meta.json}` and every operator path keeps its pre-bake state.
- **C-005**: every automatic commit this WP touches goes through `safe_commit` (here via `specify_cli.git.bookkeeping_commit.commit_merge_bookkeeping`) with an explicit path list, except the temp-worktree commit, which is one of C-005's two recorded exceptions: "the mission-number commit in a fresh detached temp worktree (`commit --only -- <rel_meta>`)" — `safe_commit` refuses a detached HEAD.
- **Gate dependency**: WP05's sweeping-commit gate starts empty and depends on this WP: both bare `git commit -m` calls in `bake.py` (`:388-392` primary, `:554-559` temp worktree) must be gone at the end of this WP. After it, `bake.py` contains no `commit` argv without a `--` pathspec.

## Context & Constraints

- Spec: `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md` User Story 5 (two acceptance scenarios), FR-010, SC-006, C-005. Plan IC-04. Evidence: `<operator-local squad notes>` ("bake.py:372-401 CONFIRMED worse"). Same defect class as the closed #5442 / #5479 (a bare commit sweeping the operator's index). This WP is not part of PR 1 (only WP01 is).
- Code reference = `origin/main` 5ee323802 (read with `git show origin/main:<path>`). Facts on `src/specify_cli/consolidation/mission_number/bake.py`:
  - `_surface_unbaked_mission_number(mission_slug, mission_branch, next_number, *, reason)` `:247-274` prints the red operator-visible warning + logger warning. It is THE "reported as not yet baked" surface; reuse it, add no new one.
  - `_bake_mission_number_on_primary_tree(main_repo, mission_slug, mission_branch, next_number)` `:277-408`. It has no `target_branch` parameter today. Path guards `:310-327`, `load_meta(..., on_malformed="none")` `:333`, idempotency `:343-354`, **write before any check of branch/dirtiness** `:356-357` (`write_meta(..., validate=False)`), `.worktrees/` guard `:359-368`, `git add <rel_meta>` `:372-385`, **bare commit** `git -c commit.gpgsign=false commit -m <msg>` `:388-401` with `cwd=main_repo`. The bare commit commits everything the operator staged, lands on whatever branch the primary checkout has checked out (or detached HEAD) and returns `True`; the read-modify-write also commits the operator's own unstaged in-file `meta.json` edit.
  - `_write_mission_number_to_branch(main_repo, mission_branch, mission_slug, next_number)` `:411-587`: detached temp worktree `git worktree add --detach <tmp> <mission_branch>` `:450-455`; falls through to the primary-tree fallback when the branch tree lacks `meta.json` `:478-497`; `git add <rel_meta>` `:547-552` (`check=True`); **bare commit** `:553-559` (`check=True`); `rev-parse HEAD` + `advance_branch_ref` `:561-580`; `worktree remove --force` in `finally` `:582-587`.
  - `_bake_mission_number_into_mission_branch(main_repo, mission_slug, mission_branch, target_branch, *, dry_run, merge_state)` `:608-738` is the only caller of `_write_mission_number_to_branch` (`:713`) and the only place the resolved merge target (`target_branch`) is known. Per #4900 it returns `next_number` whether or not the write landed — the executor writes and verifies the number on the target tree later, so an unbaked primary write is safe (it is reported, not lost).
- **Commit seam (important deviation from lens B's wording)**: lens B says "`safe_commit(target=…, capability=MERGE_BOOKKEEPING, paths=(meta,))`". Do NOT call `safe_commit` with `GuardCapability.MERGE_BOOKKEEPING` from `bake.py`: `tests/architectural/test_guard_capability_call_sites.py:42-53` allowlists `MERGE_BOOKKEEPING` only in `core/commit_guard.py` and `src/specify_cli/git/bookkeeping_commit.py` (the #1850 guard-bypass ratchet). Use the existing seam `specify_cli.git.bookkeeping_commit.commit_merge_bookkeeping(*, repo_root, worktree_root, mission_slug, message, paths, branch=None, destination_ref_override=None)` (`bookkeeping_commit.py:58-125`), passing `destination_ref_override=target_branch` (the authoritative resolved merge target — the same mechanism the merge executor uses, #4985/#4991). It builds `CommitTarget(ref=…)` (`mission_runtime/context.py:119`) and calls `safe_commit(..., capability=GuardCapability.MERGE_BOOKKEEPING)` (`bookkeeping_commit.py:186-198`). `consolidation/phase_bookkeeping.py` and `phase_teardown.py` already import that module, so the layer rules allow it; import it lazily inside the function (`tests/consolidation/test_ordering_bake_seam.py::test_lazy_imports_stay_lazy` pins lazy imports — read it first).
- `safe_commit` facts (`src/specify_cli/git/commit_helpers.py`, owned by WP07 — do not edit): `safe_commit` `:1362`; `preflight_commit` `:1246-1330` raises `SafeCommitHeadMismatch` (`:171`) when the worktree HEAD is not `destination_ref`, including detached (`observed_head="<detached>"`); it stages with `git add --force -- <path>` and commits `git commit --only -- <paths>`, hooks honoured; on a rejected commit it restores the requested paths' staged state and raises `RuntimeError("safe_commit: git commit failed …")`. Protected branches (`main`) are authorised by the `MERGE_BOOKKEEPING` capability; the existing primary-tree tests (`tests/consolidation/test_issue_4474_topology_aware_bake.py`, `test_issue_4764_bake_rollback_on_done_failure.py`, `test_merge_rollback_resume_coherence.py`) commit on `main` and must stay green.
- Censuses that pin this file (do not move their counts): `tests/architectural/_load_meta_census.py:208` pins exactly **one** `load_meta` call in `_bake_mission_number_on_primary_tree` — read the original bytes with `primary_meta_path.read_bytes()` for the restore, never a second `load_meta`/`json.loads` (`test_inline_meta_read_gate.py`). `tests/architectural/test_destructive_op_routing.py:263-275` exempts the two ephemeral `worktree remove --force` sites — leave them. `test_layer_rules.py:593` lists `bake.py` as a CLI-console importer (unchanged). `test_exemption_registry_ratchet.py:109` scans the file (do not add exemptions).
- Out of scope: `acceptance/__init__.py:1760/1780` (already path-scoped), `implement_planning_commit.py` (follow-up), the merge-conclusion sites (WP05), `commit_helpers.py` (WP07). Terminology: "mission", "consolidation"; never "feature"; no "lane merge" phrasing.
- Charter: ATDD-first — the red `regression` tests land in their own commit before the fix; targeted runs only (CI owns full suites); complexity ≤ 15 per function (split `_bake_mission_number_on_primary_tree` if the prechecks push it over); ruff-format touched files.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP04 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T019 – Red-first `regression` real-git tests for both bake commits

- **Purpose**: pin User Story 5's two scenarios plus the temp-worktree commit on real git, red on the planning base for the right reason (a wrong commit content or a wrong branch, not a crash).
- **Steps**:
  1. Create `tests/consolidation/test_bake_commit_scope_meta_only.py` with `pytestmark = [pytest.mark.regression, pytest.mark.git_repo, pytest.mark.non_sandbox]`. Drive the real seam `_bake_mission_number_into_mission_branch(main_repo=…, mission_slug=…, mission_branch=…, target_branch="main", dry_run=False, merge_state=ConsolidationState(..., mission_number_baked=False))` exactly as `tests/consolidation/test_issue_4474_topology_aware_bake.py:104-121` does (copy its `_git`, `_init_repo`, `_write_meta_file` helpers; do not import private helpers across test modules). No CLI subprocess is needed: the defect is in the in-process seam, and the seam is the entry point consolidation calls.
  2. **Fixture hygiene**: an autouse fixture that `monkeypatch.delenv`s every `GIT_*` and `SPEC_KITTY_*` variable except `SPEC_KITTY_NO_UPGRADE_CHECK` (set it to `"1"`), sets `HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` under `tmp_path / "home"`, sets `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=<tmp_path>/home/.gitconfig` (empty file), and `GIT_TERMINAL_PROMPT=0`. Repo-local `user.email`/`user.name`, `commit.gpgsign false`. The primary checkout is on `main` (the merge target; `MERGE_BOOKKEEPING` is the authorised protected flow — this is the real topology, not a protected-guard test). Build the #4474 coord shape: `kitty-specs/<slug>/meta.json` (`mission_number: null`, `target_branch: "main"`) committed on `main`; the coordination branch `kitty/mission-<slug>` cut from the root commit (before `meta.json` existed) so the bake falls through to the primary-tree path.
  3. `test_primary_bake_commits_only_meta_and_keeps_operator_staging` (US5 scenario 1): before the bake, on `main`: stage a new `src/staged.py` (`git add`), leave an unstaged edit in a tracked `README.md`, and create an untracked `notes.txt`. Run the bake. Assert, in this order: (a) the return value is `1` (the number is still returned); (b) `git rev-list --count main` grew by exactly one; (c) `git show --name-only --format= HEAD` equals exactly `["kitty-specs/<slug>/meta.json"]`; (d) `git diff --cached --name-only` still lists `src/staged.py`; (e) `git diff --name-only` still lists `README.md` with the original unstaged content on disk; (f) `notes.txt` is untracked (`git status --porcelain` shows `?? notes.txt`); (g) the committed `meta.json` blob (`git show HEAD:kitty-specs/<slug>/meta.json`, parsed with `json.loads` — tests are outside the inline-meta gate's scope; check `test_inline_meta_read_gate.py` and use `load_meta` on a temp copy if it scans tests) has `mission_number == 1`. **Pre-fix red**: (c) fails — the bare `git commit -m` sweeps `src/staged.py` into the bookkeeping commit. Mutant killed: re-introducing a pathspec-less commit (or `git add -A`) fails (c) and (d).
  4. `test_primary_bake_refuses_when_checkout_is_on_another_branch` (US5 scenario 2a): after the fixture, `git switch -c operator-topic` on the primary checkout. Record `main`'s and `operator-topic`'s tips and the `meta.json` bytes on disk. Run the bake. Assert: both tips unchanged; on-disk `meta.json` bytes identical to before (nothing written); captured stdout (use `capsys` — `console` is Rich; if Rich writes to its own file object, patch `bake.console` with a `Console(file=io.StringIO(), width=240)` and read it) contains `could NOT be baked` and the slug; return value still `1`. **Pre-fix red**: the commit lands on `operator-topic` (its tip moves). Mutant killed: a version that drops the HEAD/branch check but keeps `safe_commit` would still be refused by `SafeCommitHeadMismatch` **after** writing — the on-disk-bytes assertion kills that "write then refuse" mutant (the file must not be left modified).
  5. `test_primary_bake_refuses_on_detached_head` (2b): `git checkout --detach`; same assertions (HEAD sha unchanged, `meta.json` bytes unchanged, unbaked warning). Pre-fix red: a detached commit is created (HEAD moves).
  6. `test_primary_bake_refuses_when_meta_has_operator_edit` (2c), two parametrised cases: (i) unstaged in-file edit to `meta.json` (add an operator key `"note": "mine"`), (ii) the same edit staged. Assert: no new commit on `main`; the operator's edit is still on disk (and still staged in case ii); `mission_number` on disk is still `null`; unbaked warning printed. Pre-fix red: the commit contains `"note": "mine"`. Mutant killed: a check that inspects only the worktree (or only the index) fails one of the two parametrised cases.
  7. `test_mission_branch_bake_commit_names_only_meta` (temp worktree, `:553-559`): the non-coord shape — the mission branch `kitty/mission-<slug>` carries `meta.json`. The temp worktree is fresh (nothing else can be staged there), so the bare commit's content is identical to a scoped one; the observable difference is the argv. Assert behaviourally: the new mission-branch tip's commit touches exactly `kitty-specs/<slug>/meta.json` and `mission_number == 1`; and assert structurally with a `subprocess.run` spy wrapping the real function (`monkeypatch.setattr(bake_module_subprocess, …)` is awkward because `bake.py` imports `subprocess as _subprocess` locally — wrap `subprocess.run` globally with a pass-through recorder) that every recorded argv containing `"commit"` also contains `"--only"` and ends with `["--", "kitty-specs/<slug>/meta.json"]`. Pre-fix red on the argv assertion only (document that the content assertion is a positive control, green before and after).
  8. Run the module on the planning base and paste the failing assertion lines into the Activity Log. Commit T019 alone: `test(5443): red-first scope tests for the mission-number bake commits`.
- **Files**: `tests/consolidation/test_bake_commit_scope_meta_only.py` (new, ~260 lines).
- **Validation**: on the planning base, scenarios 3–6 fail on a content/branch/bytes assertion (not on an exception from the fixture); scenario 7 fails only on the argv assertion; nothing passes vacuously (each test first asserts the fixture precondition, e.g. `git diff --cached --name-only == ["src/staged.py"]` before the bake).

### Subtask T020 – Primary-checkout bake through the bookkeeping seam, refusing before writing

- **Purpose**: the product fix for US5 (FR-010, C-005).
- **Steps**:
  1. Thread the target: `_write_mission_number_to_branch(main_repo, mission_branch, mission_slug, next_number, *, target_branch: str)` and `_bake_mission_number_on_primary_tree(main_repo, mission_slug, mission_branch, next_number, *, target_branch: str)`; pass `target_branch=target_branch` from `_bake_mission_number_into_mission_branch` (`:713`) and from the fallback call (`:492-497`). Keyword-only and required — no default, so a forgotten call site fails loudly (update the seam tests in T021).
  2. In `_bake_mission_number_on_primary_tree`, after the existing path guards (`:310-327`) and **before** `load_meta`/`write_meta`, add one precheck helper `_primary_checkout_refusal(main_repo: Path, rel_meta: Path, target_branch: str) -> str | None` returning a human reason or `None`:
     - current branch: read with `git symbolic-ref --quiet --short HEAD` (via `kernel.git.run_git` if it fits the path-listing owner rule; this is not a path listing, so a plain `subprocess.run` is acceptable — check `tests/architectural/test_git_path_listing_owner.py` before choosing). Detached → `"primary checkout is on a detached HEAD"`; a branch other than `target_branch` → `f"primary checkout is on {branch!r}, not the merge target {target_branch!r}"`.
     - dirtiness: `kernel.git.status_entries(main_repo, pathspecs=(rel_meta.as_posix(),), untracked="no")` non-empty → `f"{rel_meta} has uncommitted changes on the primary checkout"` (covers index and worktree in one call; never build a `git status` argv yourself — the path-listing owner gate forbids it).
     Compute `rel_meta` before the precheck (move the `relative_to` up; keep the `.worktrees/` guard before it). On a reason: `_surface_unbaked_mission_number(..., reason=reason)` and `return False` — nothing written.
  3. Keep the single `load_meta` call and the idempotency branch as they are. Capture `original = primary_meta_path.read_bytes()` immediately before `write_meta`.
  4. Replace `git add` + bare commit (`:372-401`) with one lazily imported call:
     ```python
     from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping
     commit_merge_bookkeeping(repo_root=main_repo, worktree_root=main_repo, mission_slug=mission_slug,
                              message=commit_msg, paths=(rel_meta,), destination_ref_override=target_branch)
     ```
     Catch `SafeCommitError` (import from `specify_cli.git.commit_helpers`; `SafeCommitHeadMismatch` is a subclass — a race between precheck and commit) and `RuntimeError` (a rejecting hook): restore `primary_meta_path.write_bytes(original)` (the operator's tree must look untouched), then `_surface_unbaked_mission_number(..., reason=f"bookkeeping commit refused: {exc}")`, `return False`. Do not catch `SafeCommitRecoveryFailed` separately — it is a `SafeCommitError`; include `exc` in the reason so its recovery state is visible. Never retry without hooks.
  5. Update the function docstring: "commits exactly `meta.json` on `target_branch` via the merge-bookkeeping seam; refuses (unbaked, nothing written) when the primary checkout is off-target, detached, or `meta.json` is dirty".
- **Files**: `src/specify_cli/consolidation/mission_number/bake.py`.
- **Validation**: T019 scenarios 3–6 green; `tests/consolidation/test_issue_4474_topology_aware_bake.py`, `test_issue_4764_bake_rollback_on_done_failure.py`, `test_merge_rollback_resume_coherence.py` green unchanged; `tests/architectural/test_guard_capability_call_sites.py` green (no new `MERGE_BOOKKEEPING` site); `_load_meta_census` green (still one `load_meta`).
- **Mutant notes for the reviewer**: dropping the precheck → scenario 4's on-disk-bytes assertion fails (write then `SafeCommitHeadMismatch`); dropping the restore in the `except` → a hook-rejection unit (add one: a repo-local `pre-commit` hook `exit 1` on `main`, assert `meta.json` bytes unchanged and no commit) fails; passing `paths=(primary_meta_path.parent,)` (directory) → scenario 3's exact file-list assertion still passes only if nothing else is in the dir — add `kitty-specs/<slug>/spec.md` with an unstaged edit to the scenario-3 fixture so a directory pathspec mutant fails.

### Subtask T021 – Temp-worktree commit names its path; seam fakes updated

- **Purpose**: the second bare commit (`:553-559`) becomes path-scoped so the WP05 gate can start empty; the fake-subprocess seam tests follow the new signature.
- **Steps**:
  1. In `_write_mission_number_to_branch`, replace the `git add <rel_meta>` (`:547-552`) + `git -c commit.gpgsign=false commit -m <msg>` (`:553-559`) pair with a single
     `["git", "-c", "commit.gpgsign=false", "commit", "--only", "-m", commit_msg, "--", rel_meta.as_posix()]` run with `cwd=mission_tmp_path`, `capture_output=True`, `check=True` (same failure behaviour as today: a `CalledProcessError` propagates as before — do not change the error policy here). `meta.json` is tracked on that branch (the code only reaches this point when `meta_path.exists()` on the checked-out branch tree), so `--only` needs no prior `git add`. Verified on git (2026-10-07, scratch repo): `commit --only -m … -- <path>` on a detached HEAD commits exactly that path and leaves other staged entries staged. Hooks still run (no `--no-verify`, ever).
  2. `safe_commit` is deliberately not used here: it refuses a detached HEAD (`preflight_commit` HEAD assertion), and this worktree is a fresh spec-kitty-owned detached checkout. Say so in a two-line comment citing C-005's exception wording: "the mission-number commit in a fresh detached temp worktree (`commit --only -- <rel_meta>`)".
  3. `tests/consolidation/test_ordering_bake_seam.py`: every direct call `bake._write_mission_number_to_branch(tmp_path, "kitty/mission-m", "m", N)` (e.g. `:202`, and the `test_write_*` tests around `:375-495`) gains `target_branch="main"`. Fakes that match `args[:3] == ["git", "worktree", "add"]` keep working; if any fake asserts on `["git", "add", …]` or the old commit argv, change it to the new argv and assert `"--only" in args and args[-2:] == ["--", "kitty-specs/m/meta.json"]`. Add one `fast` test: `test_write_commit_argv_names_only_meta` — fake `worktree add` creates `kitty-specs/m/meta.json` with `{"mission_number": null}`, record every argv, patch `advance_branch_ref` to a no-op and `rev-parse` to return a sha; assert exactly one recorded argv contains `"commit"`, it contains `"--only"`, ends with `["--", "kitty-specs/m/meta.json"]`, and no recorded argv equals `["git", "add", …]` without `--`. Mutant killed: restoring the bare commit fails the `--only`/pathspec assertion.
  4. Add a `fast` test for the precheck helper only if it is pure — it is not (it runs git), so cover it via T019's real-git cases instead; do not mock git to unit-test it (shape pin).
- **Files**: `bake.py`, `tests/consolidation/test_ordering_bake_seam.py`.
- **Validation**: T019 scenario 7 green; `pytest tests/consolidation/test_ordering_bake_seam.py -q` green; `git grep -n '"commit"' -- src/specify_cli/consolidation/mission_number/bake.py` shows only argvs with `--only` and `--`.

### Subtask T022 – Verification and closeout

- **Purpose**: honest green, red→green evidence, gate-readiness for WP05.
- **Steps**:
  1. Targeted runs (no full suites):
     ```bash
     .venv/bin/python -m pytest tests/consolidation/test_bake_commit_scope_meta_only.py tests/consolidation/test_ordering_bake_seam.py \
       tests/consolidation/test_issue_4474_topology_aware_bake.py tests/consolidation/test_issue_4764_bake_rollback_on_done_failure.py \
       tests/consolidation/test_merge_rollback_resume_coherence.py tests/consolidation/test_merge_time_number_assignment.py \
       tests/consolidation/test_mission_number_package.py -q
     .venv/bin/python -m pytest tests/architectural/test_guard_capability_call_sites.py tests/architectural/test_destructive_op_routing.py \
       tests/architectural/test_layer_rules.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_inline_meta_read_gate.py \
       tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_no_legacy_terminology.py -q
     .venv/bin/python -m pytest tests/architectural -q -k "load_meta"
     ```
  2. `ruff check` + `ruff format --check --force-exclude` on the touched files; `mypy src/specify_cli/consolidation/mission_number/bake.py`.
  3. Gate-readiness note for WP05: `git grep -nE '"commit"' -- src/specify_cli/consolidation/mission_number/bake.py` — paste the output into the Activity Log; it must show no pathspec-less commit and no `git add` without `--`.
  4. Changelog: do not edit `docs/changelog/CHANGELOG.md` (WP08 owns it). Put a one-paragraph draft bullet in the Activity Log for WP08: "Consolidation's mission-number assignment no longer commits files you had staged on your checkout, no longer commits onto another branch or a detached HEAD, and leaves your own `meta.json` edit alone; it reports the number as not yet baked instead."
  5. Record RED (T019 commit) and GREEN outputs in the Activity Log; `spec-kitty agent tasks mark-status T019 T020 T021 T022 --status done --mission upgrade-migration-commit-scope-01M4AKVE`; tracer entries for anything surprising (`spec-kitty agent tracer-append --mission upgrade-migration-commit-scope-01M4AKVE --category approach|design-decisions|tooling-friction --actor <agent>`).
- **Validation**: all green; the lane holds the red test commit before the fix commit(s).

## Test Strategy

```bash
# red on the planning base (commit T019 alone), green at the end
.venv/bin/python -m pytest tests/consolidation/test_bake_commit_scope_meta_only.py -q
# neighbours that must not move
.venv/bin/python -m pytest tests/consolidation/test_ordering_bake_seam.py tests/consolidation/test_issue_4474_topology_aware_bake.py \
  tests/consolidation/test_issue_4764_bake_rollback_on_done_failure.py tests/consolidation/test_merge_rollback_resume_coherence.py -q
# ratchets this file is pinned by
.venv/bin/python -m pytest tests/architectural/test_guard_capability_call_sites.py tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_layer_rules.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_inline_meta_read_gate.py -q
.venv/bin/ruff check src/specify_cli/consolidation/mission_number/bake.py tests/consolidation/test_bake_commit_scope_meta_only.py tests/consolidation/test_ordering_bake_seam.py
.venv/bin/mypy src/specify_cli/consolidation/mission_number/bake.py
```

Markers: the new module is `regression` + `git_repo` + `non_sandbox` (real git, fixed bug); the seam-test additions are `fast` (fake subprocess only, as the module already is). Never `p0_repro` (reserved for #5443's upgrade reproduction in WP01).

## Risks & Mitigations

- **Guard-capability ratchet**: calling `safe_commit(capability=MERGE_BOOKKEEPING)` from `bake.py` fails `test_guard_capability_call_sites.py` → use `commit_merge_bookkeeping(destination_ref_override=target_branch)`.
- **Write-then-refuse leaves a dirty `meta.json`** → precheck branch + dirtiness before writing; restore the original bytes if the commit is still refused (race, hook).
- **Placement resolution with stale meta** → `destination_ref_override` bypasses it; the HEAD-match guard still runs.
- **Unbaked becomes "lost"** → it does not: `_bake_mission_number_into_mission_branch` returns `next_number` regardless (#4900) and the executor writes/verifies it on the target tree; T019 asserts the return value.
- **Census drift** (`_load_meta_census.py:208`, destructive-op exemptions) → no new `load_meta`, no new `worktree remove`.
- **Fake-subprocess tests silently passing on the old argv** → T021's argv assertions.
- **Coupling with WP05** → WP05's gate expects zero bare commits here; T022 step 3 records the evidence.

## Review Guidance

- Confirm the T019 commit precedes the fix and its RED output in the Activity Log is a content/branch/bytes assertion (scenario 3 lists `src/staged.py` in the commit; scenario 4 shows `operator-topic` tip moved).
- Confirm no `safe_commit(... MERGE_BOOKKEEPING ...)` call in `bake.py`; the seam is `commit_merge_bookkeeping` with `destination_ref_override=target_branch`, imported lazily.
- Confirm the precheck runs before `write_meta`, the restore runs on every refused commit, and no path retries without hooks.
- Confirm `bake.py` has no pathspec-less `commit` and no `git add` left; the temp-worktree commit is `commit --only -m … -- <rel_meta>`.
- Confirm `target_branch` is keyword-only and required on both private functions and all callers pass it.
- Run scenario 3 by hand once and read `git show --stat HEAD`: exactly one file.

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Analysis fold: AN-INC-002 (C-005 now names this WP's temp-worktree commit as a recorded exception; Context and T021 cite its wording); AN-COV-002 (C-004 added to `requirement_refs`).
- 2026-10-07 – orchestrator (recording implementer evidence) – Cycle 0: RED at f649c95fd, all 7 new tests fail on assertions (scenario 3 commit lists `src/staged.py`; off-target/detached HEAD moves and bakes `mission_number: 1`; operator edit carried; hook snapshot differs; temp-worktree argv lacks `--only`); GREEN at 828dece16, 7/7.
- 2026-10-07 – orchestrator (recording implementer evidence) – Review cycle 1 rework: RED at bbabe9db6, 3 failed / 7 passed (untracked and gitignored-untracked `meta.json`: `main` moved; probe failure: `RuntimeError: git probe exploded` escapes the bake). GREEN at 0442b5a16: consolidation suites 78 passed; architectural suites 303 passed, 1 skipped; `-k load_meta` 5 passed; ruff, format, C901 ≤ 15, mypy clean. Fix: refuse unless `meta.json` is tracked in HEAD (`tree_entry`) and clean; probe failures report the number unbaked; refusal reasons asserted in the branch/detached tests.
- 2026-10-07 – orchestrator – Gate-readiness grep for WP05 (`git grep -nE '"commit"|"add"' -- src/specify_cli/consolidation/mission_number/bake.py`): only `worktree add --detach` (two) and `commit --only -m <msg> -- <rel_meta>` (C-005 exception). No pathspec-less commit, no bare `git add`.
- 2026-10-07 – orchestrator – Changelog draft for WP08: "Assigning a mission number during merge or consolidation no longer commits anything beyond the mission's own metadata file. It commits only to the merge target branch and leaves your staged and unstaged work alone. If the metadata file is untracked, ignored or has your own pending edits, it skips the write and reports the number as unbaked."
