---
work_package_id: WP07
title: safe-commit and spec-commit commit exactly the paths they were given
dependencies:
- WP01
requirement_refs:
- FR-016
- FR-017
- FR-018
- FR-022
- SC-006
- C-005
- C-004
- NFR-001
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T14:59:36.355157+00:00'
subtasks:
- T034
- T035
- T036
- T037
- T038
- T039
- T044
- T040
phase: Phase 2 - Commit-scope widening
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/resolution.py
create_intent:
- tests/kernel/test_resolve_commit_path.py
- tests/git_ops/test_safe_commit_link_and_stage_detail.py
- tests/specify_cli/cli/commands/test_safe_commit_paths_5401_5671_4722.py
- tests/specify_cli/cli/commands/test_spec_commit_symlink_5671.py
- tests/coordination/test_commit_router_symlink_paths.py
- tests/integration/upgrade/__init__.py
- tests/integration/upgrade/test_upgrade_carries_migration_untracks.py
execution_mode: code_change
model: sonnet
owned_files:
- src/kernel/resolution.py
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/cli/commands/safe_commit_cmd.py
- src/specify_cli/cli/commands/spec_commit_cmd.py
- src/specify_cli/coordination/commit_router.py
- src/mission_runtime/owned_checkout.py
- tests/kernel/test_resolution.py
- tests/specify_cli/cli/commands/test_safe_commit_cmd.py
- tests/specify_cli/cli/commands/test_safe_commit_cli.py
- tests/specify_cli/cli/commands/test_safe_commit_symlink_loop.py
- tests/kernel/test_resolve_commit_path.py
- tests/git_ops/test_safe_commit_link_and_stage_detail.py
- tests/specify_cli/cli/commands/test_safe_commit_paths_5401_5671_4722.py
- tests/specify_cli/cli/commands/test_spec_commit_symlink_5671.py
- tests/coordination/test_commit_router_symlink_paths.py
- tests/integration/upgrade/__init__.py
- tests/integration/upgrade/test_upgrade_carries_migration_untracks.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5401'
- '#5671'
- '#4722'
- '#5443'
---

# Work Package Prompt: WP07 – safe-commit and spec-commit commit exactly the paths they were given

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

- **FR-016 (#5401)**: `spec-kitty safe-commit docs/` after a staged `git mv docs/old.md docs/new.md` commits the rename completely: HEAD has `docs/new.md`, HEAD no longer has `docs/old.md`, nothing is left staged.
- **FR-022 (#5443, second PR)**: `safe_commit(..., index_deletions=...)` commits an index deletion while the file stays on disk (no move-aside), and `spec-kitty upgrade` uses it to carry the 3.2.5 migration's own `git rm --cached` untracks; an operator-staged deletion is never committed.
- **FR-017 (#5671)**: a symlink argument (tracked or untracked, relative or absolute, or reached through a directory argument) commits the **link** path (`git ls-tree HEAD link.md` mode `120000`), never the target; the target's WIP stays uncommitted. Same for `spec-commit` and for the in-process `safe_commit(paths=(abs_link,))` route. A symlinked directory argument is committed as one link, never expanded. A looping link is refused on every interpreter (#5251 / PR #5252).
- **FR-018 (#4722)**: a batch with one bad path fails and names that path and git's reason; a lone path unknown both on disk and to git is an error (exit 1), while a deleted tracked file stays a valid argument.
- **US8 scenario 4**: a staged rename whose other side lies outside the directory argument is refused, the outside path is named, nothing is committed.
- **SC-006**: each `safe-commit` call commits exactly the paths it was responsible for, measured on fixtures that also carry unrelated staged / dirty / untracked operator work (which must be byte-identical before and after).
- C-004: every defect gets a `regression` test committed red **before** its fix commit.

## Context & Constraints

- Spec: `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md` (US8, FR-016..FR-018, SC-006); plan IC-07; data-model "Commit path (safe-commit)": *a path whose parents are resolved and whose final component is kept as given; a looping final component is refused; a symlinked directory is a single path.* Evidence: `<operator-local squad notes>` (reviewer-renata; its T1–T7 are this WP's T034–T040).
- Code reference is `origin/main` 5ee323802. Read seams with `git show origin/main:<path>`; line numbers below are from that commit.
- **Root cause, one sentence**: every path normaliser in the commit chain calls `Path.resolve()` (or `resolve_rejecting_loops`, which wraps it) on the **whole** path, so the final symlink component is followed and the target's path replaces the link's.
- Sites (all `origin/main`):
  - `src/kernel/resolution.py:50-84` `resolve_rejecting_loops` (keep; add the new helper beside it; `__all__` :32).
  - `src/specify_cli/git/commit_helpers.py:1246` `preflight_commit`; the normalisation loop :1300-1308 (`candidate.resolve().relative_to(resolved_worktree_root)` at :1307 follows the leaf for absolute paths).
  - `commit_helpers.py:1046-1071` `_normalize_expected_parent_path_bytes` (:1060 same leaf-follow).
  - `commit_helpers.py:653-667` `_stage_requested_files` returns `bool`, discarding git's stderr; caller :1542-1543 raises `RuntimeError(f"safe_commit: failed to stage requested files in {worktree_root}: {normalized_files!r}")` naming **every** path.
  - `commit_helpers.py:136` `SafeCommitError(RuntimeError)` — base for a new loop-refusal subclass.
  - `src/specify_cli/cli/commands/safe_commit_cmd.py:141-153` `_changed_paths_under` returns `entry.path` only — drops `entry.orig_path` (#5401); :175-188 `_expand_arguments` (`path.is_dir()` follows a symlinked dir; :179 `(repo_root / rel).resolve()` follows each leaf); :191-199 `_has_candidate_changes` (lone unknown path → empty status → "No requested changes", exit 0); :228 and :250 `path.resolve().relative_to(...)` in `_mission_slug_from_paths` / `_mission_file_kind` (leaf followed → a link under `kitty-specs/` pointing elsewhere mis-routes); :404-422 `_resolve_file_argument` (:420 `resolve_rejecting_loops(candidate)` — leaf followed); command body :448-513; exit contract :501-513 (catches `SafeCommitError, ProtectedBranchCommitError, SafeCommitBackstopError, TaskCliError, ValueError, RuntimeError` → exit 1).
  - `src/specify_cli/cli/commands/spec_commit_cmd.py:143` `abs_files = [(repo_root / path).resolve() ... else path.resolve()]`; :157-176 `_reject_directory_args` (`f.is_dir()` follows a symlinked dir); :215 `_relpath` (cosmetic).
  - `src/mission_runtime/owned_checkout.py:209-229` `OwnedCheckout.files` (:223 `resolve_rejecting_loops(candidate)`, then `_is_within(resolved, mission_dir)` :226).
  - `src/specify_cli/coordination/commit_router.py:1313-1321` `_is_directly_in_worktree` (:1318), :1954-1981 `_dirty_paths_in_checkout` (:1976); :1948-1951 `_relpath`-style renderer (:1949, cosmetic only — leave the fallback, but normalise through the helper for consistency if trivial).
- Contracts that must not break (grep them before changing any exception text):
  - `tests/consolidation/test_bare_slug_alias_consumers.py:426` — `pytest.raises(RuntimeError, match="failed to stage")` for a never-tracked missing path.
  - `tests/cli/commands/test_retrospect.py:1015` — returns the literal `"failed to stage requested files"` as the expected substring.
  - `commit_router.py:878-881` — maps any `RuntimeError` to `_safe_commit_error_result`, except `_is_empty_changeset_error`.
  - `src/specify_cli/upgrade/autocommit.py:429` — flattens any non-recovery exception into the skip warning. **`autocommit.py` is WP01's file**: the only edit allowed here is T044's one recorded out-of-map call site in `commit_touched_checkout`, sequenced after WP01 (this WP depends on WP01). Your new exception types must remain `RuntimeError` subclasses so that flattening is unchanged.
  - `events/decision_log.py:273` area — another `safe_commit` caller that relies on `RuntimeError`; read it, do not edit it.
  - `tests/specify_cli/cli/commands/test_safe_commit_symlink_loop.py:71` — loop refused with exit 1 and a JSON error payload, nothing committed (#5251 / PR #5252 — cite these, not #3189, in new prose).
  - `tests/architectural/test_loop_aware_resolution.py` — bans hand-rolled `RuntimeError`/`ELOOP` translation outside `src/kernel/resolution.py`. Put all loop detection in the kernel helper; callers only catch `OSError` from it (the existing `_resolve_file_argument` shape is allowlisted/compliant — keep that shape).
  - `tests/architectural/test_safe_commit_import_boundary.py` — read it before adding imports to `commit_helpers.py`.
- Decisions already taken (do not reopen): loop policy **refuse** (#5671 opening comment, #5251 group 1); symlinked directory = the link (git never traverses a symlink; precedent `upgrade/autocommit.py:298`); cross-boundary rename **refused**, never auto-included; a lone nonexistent path (not `lexists` and unknown to git) is an error; `RuntimeError` + the `safe_commit: failed to stage requested files` prefix are kept and git's detail is appended (precedent `commit_helpers.py:982`/`:995` which already append `stderr.strip()`).
- **Owned-checkout decision (T038)**: `OwnedCheckout.files` keeps its containment rule on the **link's own location** (parents resolved, leaf kept) — a link that lives inside `mission_dir` is accepted and committed as a link even if it points outside the mission, because what is committed is the link blob (its target string), not the outside file. A link that *lives* outside the mission (its parent resolves outside) is refused as today. Rationale: the owned rule protects which tree paths an owned write touches; committing a 120000 blob at an in-mission path touches only that path. Record this in the Activity Log; if a reviewer prefers refusing out-pointing links, it is a one-line `_is_within(resolved_target, ...)` addition — do not add it unasked.
- PR #5856 files are untouched by this WP. Do not edit any file outside `owned_files`.
- Charter: ATDD-first (red commit before each fix), complexity ≤ 15 per function, `__all__` updated, ruff-format touched files, targeted test runs only (CI owns full suites), no "feature" wording (Mission / work package).

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP07 --agent claude`. This WP depends on WP01 (T044 builds on WP01's baseline seams and edits one call site in WP01's `upgrade/autocommit.py`) and ships in PR 2. WP05 depends on this WP (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`): its commit-scope gate exempts `safe_commit` by symbol, including T044's temp-index commit.

## Fixture hygiene (applies to every real-git test in this WP)

- Build `env` from scratch: copy `os.environ`, drop every key starting with `GIT_` or `SPEC_KITTY_`, then set `SPEC_KITTY_NO_UPGRADE_CHECK=1`, `HOME`/`USERPROFILE`=`tmp_path/"home"`, `XDG_CONFIG_HOME`/`XDG_CACHE_HOME`/`XDG_DATA_HOME`/`XDG_STATE_HOME` under that home, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<home>/.gitconfig`, `PYTHONPATH=<checkout>/src` where `<checkout> = Path(__file__).resolve().parents[N]` (count N for your module depth; assert `(<checkout>/"src"/"specify_cli").is_dir()`).
- In-process `CliRunner` tests: `monkeypatch.delenv` the same prefixes (pattern in `test_safe_commit_symlink_loop.py`), `monkeypatch.setenv("HOME", ...)`, `monkeypatch.chdir(repo)`.
- Subprocess tests run `[sys.executable, "-m", "specify_cli", "safe-commit", ...]` — never a global `spec-kitty` binary.
- Repos: `git init -b work`, local `user.email`/`user.name`, `commit.gpgsign=false`; check out a **non-protected** branch (`kitty/mission-test-01ABCDEF` like the existing CLI tests, or `work`), and always pass `--to-branch <that branch>`.
- Every fixture plants unrelated operator work: an untracked `secret.env`, a staged `staged.txt`, an unstaged edit to tracked `tracked.txt`. Snapshot `git diff --cached --name-status`, `git status --porcelain=v1 -z` and the three files' bytes before the call; assert them unchanged after (except for the paths the call was responsible for). This is SC-006 and kills any "sweep the index" mutant.
- Symlink tests: `pytest.mark.skipif(not hasattr(os, "symlink"))` plus a probe that `os.symlink` works in `tmp_path` (Windows without developer mode); skip with a named reason.
- Markers: pure helper tests `pytest.mark.unit` + `pytest.mark.fast` (no subprocess, no git); real-git tests `pytest.mark.git_repo` + `pytest.mark.non_sandbox`; issue-pinned reproductions add `pytest.mark.regression`. No `p0_repro` in this WP (only #5443 uses it).

## Subtasks & Detailed Guidance

### Subtask T034 – `resolve_commit_path`: parents resolved, the final component never followed

- **Purpose**: one normalisation rule for every commit path (lens C T1), so no call site re-derives "link vs target".
- **Steps**:
  1. Red first: create `tests/kernel/test_resolve_commit_path.py` (`unit`, `fast`; symlink skip guard). Cases, each with the mutant it kills:
     - `root/link.md -> real.md`: `resolve_commit_path(root, root/"link.md") == root.resolve()/"link.md"` — kills a mutant that calls `.resolve()` on the whole path (it returns `.../real.md`).
     - relative input `Path("link.md")` resolved against `root` → same result — kills a mutant that ignores `root` for relative paths.
     - parent symlink: `root/alias -> root/real_dir`, input `root/alias/f.md` → `root.resolve()/"real_dir"/"f.md"` — kills a mutant that resolves nothing (returns `alias/...`), which would break `relative_to(worktree)` for worktrees reached through a symlinked parent (e.g. macOS `/tmp` → `/private/tmp`).
     - symlinked directory `root/linkdir -> real_dir`: result ends in `linkdir` — kills an "expand directories" mutant.
     - dangling link `root/dangling -> nowhere`: returned unchanged, no raise — kills a strict-resolve mutant.
     - looping leaf `a -> b`, `b -> a`: `pytest.raises(OSError)` with `errno.ELOOP` (use `is_symlink_loop_error`) — kills a "never follow so never detect" mutant; detect with `os.stat(path)` on the leaf after resolving the parent, mapping a loop-shaped `OSError` exactly like `resolve_rejecting_loops` does (:74-82).
     - loop in a **parent** component: raises via `resolve_rejecting_loops(parent)`.
     - `..` in the input after the root join, and a path outside `root`: the helper does **not** decide containment (callers do); assert it returns the normalised absolute path so callers can `relative_to` and fail. State that contract in the docstring.
     - 3.13 shape: monkeypatch `Path.resolve` to return its input unchanged for a looping parent (simulating 3.13's silent return) and assert the loop is still refused — kills a mutant that relies on `RuntimeError` from 3.11/3.12 only.
  2. Run it: red (`ImportError` is acceptable as the red reason **only** for this helper's own module; record it). Commit: `test(5671): red-first pin for leaf-preserving commit path resolution`.
  3. Implement in `src/kernel/resolution.py`:
     ```python
     def resolve_commit_path(root: Path, path: Path) -> Path:
         candidate = path if path.is_absolute() else root / path
         parent = resolve_rejecting_loops(candidate.parent)
         leaf = parent / candidate.name
         _refuse_loop_leaf(leaf)   # os.lstat ok + os.stat ELOOP → _loop_error
         return leaf
     ```
     Handle `candidate.name in ("", ".", "..")` by falling back to `resolve_rejecting_loops(candidate)` (a directory argument like `docs/` or `.` has no link leaf to keep). Add `"resolve_commit_path"` to `__all__` (:32). Docstring: the rule, the four outcomes (link kept, dangling kept, loop refused, containment left to the caller), and why (`git` stores links as blobs; following the leaf commits a different path — #5671).
  4. Extend `tests/kernel/test_resolution.py` only if a shared fixture is useful; do not change its existing assertions.
- **Files**: `src/kernel/resolution.py`, `tests/kernel/test_resolve_commit_path.py` (new, ~150 lines).
- **Validation**: new module green; `tests/kernel/test_resolution.py`, `tests/architectural/test_loop_aware_resolution.py` green (the kernel module is the excluded primitive, so ELOOP mapping belongs here).

### Subtask T035 – Core normalisation in `safe_commit` + typed loop refusal

- **Purpose**: the in-process `safe_commit(paths=(abs_link,))` route commits the link, and a looping path fails with a typed, still-`RuntimeError` error (lens C T2).
- **Steps**:
  1. Red first in `tests/git_ops/test_safe_commit_link_and_stage_detail.py` (`git_repo`, `non_sandbox`, `regression`), calling `safe_commit` directly with `target=CommitTarget(ref="work")`:
     - `test_absolute_symlink_path_commits_the_link_not_the_target`: tracked `real.md` (committed), `link.md -> real.md` untracked; then append WIP to `real.md`. Call with `paths=(repo/"link.md",)` (absolute). Assert: `git ls-tree HEAD link.md` prints mode `120000`; `git show HEAD:link.md` == `"real.md"`; `git diff HEAD -- real.md` still shows the WIP; `git show HEAD --name-only` lists exactly `link.md`. **Mutant killed**: pre-fix `:1307` resolve → commits `real.md` with the WIP; the mode/name-only assertions fail.
     - same with a **tracked** link whose target changed (link already in HEAD, re-pointed): HEAD records the new link target string, `real.md` untouched.
     - relative `Path("link.md")`: positive control, green before and after.
     - looping absolute path `repo/"a"` (`a -> b`, `b -> a`): `pytest.raises(SafeCommitPathLoopRefused)`, and `isinstance(exc, RuntimeError)`; HEAD unchanged; index unchanged. **Mutant killed**: a normaliser that keeps the leaf but never probes would stage two link blobs and commit them.
     - `expected_path_bytes={repo/"link.md": b"real.md"}` with `expected_parent_sha=HEAD`: commit succeeds and records the link (exercises `_normalize_expected_parent_path_bytes` :1060). Pre-fix: "expected raw-bytes path was not requested for staging: 'real.md'" — red.
  2. Commit the red tests alone.
  3. Fix `preflight_commit` :1300-1308: for an absolute `candidate`, `rel = resolve_commit_path(resolved_worktree_root, candidate).relative_to(resolved_worktree_root)` inside `contextlib.suppress(ValueError)` exactly like today (a path outside the worktree still passes as-is and fails later — unchanged behaviour). Relative paths stay as given (git interprets them relative to the worktree; do not resolve them — that would change today's relative-path contract).
  4. Catch the helper's `OSError` where `is_symlink_loop_error(exc)` and raise a new `SafeCommitPathLoopRefused(SafeCommitError)` (`error_code = "SAFE_COMMIT_PATH_LOOP"`, message `safe_commit: refusing symlink loop at {path}`; carry `worktree_root`). Any other `OSError` propagates unchanged. Add to the module's `__all__` if it declares one; place the class next to `SafeCommitPathPolicyError` (:356).
  5. Same normalisation in `_normalize_expected_parent_path_bytes` :1059-1063 (keep the two existing `RuntimeError` messages verbatim).
- **Files**: `src/specify_cli/git/commit_helpers.py`, the new test module (~200 lines incl. T036's cases).
- **Validation**: new tests green; `tests/git_ops/test_safe_commit_helper_integration.py`, `tests/integration/git/test_safe_commit_backstop.py`, `tests/git_ops/test_safe_commit_commit_failure_classification.py` green.

### Subtask T036 – `_stage_requested_files` names the failing path and git's reason (#4722)

- **Purpose**: a batch failure names the offending path and git's own reason, keeping the exception type and prefix every caller matches (lens C T3).
- **Steps**:
  1. Red first (same module as T035): `test_batch_stage_failure_names_the_path_and_gits_reason` — request `(repo/"ok.md", Path("missing.md"))` where `missing.md` never existed and is unknown to git. Assert `pytest.raises(RuntimeError) as ei`; `str(ei.value).startswith("safe_commit: failed to stage requested files in ")`; `"missing.md" in msg`; `"did not match any files" in msg` (git's stderr); and `"ok.md" not in msg.split(":", 2)[-1]` after the prefix's path list is replaced (see step 3). Also assert `ok.md` is **not** staged afterwards (`git diff --cached --name-only` excludes it — the restore path :1542 must still run). **Mutants killed**: (a) a message that still lists every path (fails the "names only the bad one" check); (b) a change that drops the prefix (fails the `startswith`; `test_bare_slug_alias_consumers.py:426` and `test_retrospect.py:1015` would also fail); (c) a change that skips `_restore_staged_patch` (fails the not-staged assertion).
  2. Commit red.
  3. Change `_stage_requested_files` (:653) to return `tuple[str, str] | None` — `None` on success, `(file_path, add_result.stderr.strip())` for the first failure (keep the loop order; stop at the first failure as today). Update the single caller (:1542-1543):
     ```python
     failure = _stage_requested_files(worktree_root, normalized_files)
     if failure is not None:
         _restore_staged_patch(...)
         bad_path, git_reason = failure
         raise RuntimeError(f"safe_commit: failed to stage requested files in {worktree_root}: {bad_path!r}: {git_reason}")
     ```
     The prefix `safe_commit: failed to stage requested files` is preserved byte-for-byte (FR-018 and the two contract tests). Grep for other callers of `_stage_requested_files` across `src/` and update each (only within owned files; if one exists elsewhere, stop and report).
  4. Check `commit_router._is_empty_changeset_error` and `autocommit.py:429` behaviour is unchanged (both see a `RuntimeError`).
- **Files**: `src/specify_cli/git/commit_helpers.py`, the T035 test module.
- **Validation**: `pytest tests/consolidation/test_bare_slug_alias_consumers.py -k "never_tracked" tests/cli/commands/test_retrospect.py -q` green.

### Subtask T037 – `safe-commit` CLI: link leaf, rename sources, cross-boundary refusal, lone unknown path

- **Purpose**: the CLI front end stops losing or redirecting paths (#5401, #5671, #4722, US8 scenarios 1–4; lens C T4).
- **Steps**:
  1. Red first: `tests/specify_cli/cli/commands/test_safe_commit_paths_5401_5671_4722.py` (`git_repo`, `non_sandbox`, `regression`). Drive the real CLI through `sys.executable -m specify_cli safe-commit --to-branch <branch> -m msg --json ...` with the hygienic env (one subprocess per case keeps it honest; reuse the in-process `CliRunner` only for the loop case already covered). Every case plants the unrelated operator work and asserts it unchanged.
     - **#5401 rename** `test_directory_argument_commits_a_staged_rename_completely`: commit `docs/old.md`; `git mv docs/old.md docs/new.md`; run `safe-commit docs/`. Assert exit 0; `git ls-tree HEAD docs/old.md` is empty; `git ls-tree HEAD docs/new.md` non-empty; `git diff --cached --name-only` is empty (nothing left staged); `git show --stat HEAD` shows the rename (`git show -M --name-status HEAD` line `R100\tdocs/old.md\tdocs/new.md`). **Mutant killed**: dropping `orig_path` (today :153) leaves `old.md` in HEAD and a staged deletion behind.
     - **#5671 link, four shapes** (parametrize): untracked link relative `link.md`; untracked link absolute; tracked link re-pointed; directory argument `links/` containing `links/link.md -> ../real.md`. Each: `real.md` carries WIP; assert `git ls-tree HEAD <link>` mode `120000`, `git show HEAD --name-only --format=` equals exactly the link path(s), `git diff HEAD -- real.md` still non-empty. **Mutant killed**: any leaf-following site (:420, :179) commits `real.md`.
     - **symlinked directory argument** `linkdir -> realdir` (untracked) with WIP files in `realdir`: run `safe-commit linkdir`; assert HEAD has `linkdir` mode `120000` and **no** `linkdir/*` or `realdir/*` entries. **Mutant killed**: `path.is_dir()` (:176) expanding through the link.
     - **cross-boundary rename** (both directions): `git mv docs/a.md other/a.md` then `safe-commit docs/` → exit 1, error names `other/a.md`, HEAD unchanged, the staged rename still staged (index identical to the pre-call snapshot). And `git mv other/b.md docs/b.md` then `safe-commit docs/` → exit 1 naming `other/b.md`. **Mutants killed**: auto-including the outside side (HEAD changes) or silently dropping it (exit 0).
     - **#4722 lone unknown path** `safe-commit typo.md` (not on disk, unknown to git) → exit 1, JSON `error` contains `typo.md`; HEAD unchanged. Positive control: a **deleted tracked** file `gone.md` (`rm gone.md`, unstaged) → exit 0 and HEAD no longer has `gone.md`. **Mutant killed**: an "every missing path is an error" rule fails the control; today's exit 0 fails the first.
     - **#4722 batch** `safe-commit ok.md typo.md` → exit 1, error contains `typo.md` and git's reason; `ok.md` not committed and not left staged.
  2. Commit red.
  3. Fix `safe_commit_cmd.py`:
     - `_resolve_file_argument` (:404-422): call `resolve_commit_path(repo_root, candidate)` (pass `repo_root` in; keep the `OSError → ValueError("Symlink loop while resolving file argument ...")` translation so `test_safe_commit_symlink_loop.py:71` stays green).
     - `_expand_arguments` (:175-188): treat `path.is_dir() and not path.is_symlink()` as a directory; a symlinked dir passes through as one file. For contained entries use `repo_root / rel` **without** `.resolve()` (git already reports repo-relative, leaf-literal paths).
     - `_changed_paths_under` (:141-153): return entries carrying `orig_path`; for an entry with `orig_path`, if both sides are under `rel_dir` add both paths; if exactly one side is outside, raise `ValueError(f"Rename crosses the directory argument {rel_dir}/: {outside} is outside it; commit both paths explicitly")` (exit 1 via the :501 handler; nothing staged yet). Use `GitPath` component-wise containment (kernel.git) rather than string prefixes (`docs2/` must not count as under `docs/`).
     - `_mission_slug_from_paths` (:226-234) / `_mission_file_kind` (:248-256): replace `path.resolve()` with `resolve_commit_path(repo_root, path)` so a link inside `kitty-specs/<slug>/` is classified by where it lives.
     - Lone unknown path: before `_has_candidate_changes` (:469), for each **non-expanded** argument check `os.path.lexists(path)` or known to git (`kernel.git.is_tracked` / `index_entries` for that pathspec; HEAD-tracked deleted files count as known). Unknown → `ValueError(f"Unknown path (not on disk and not known to git): {rel}")`. Directory-expanded paths are exempt (they come from git).
  4. Keep the exit contract (:501-513) unchanged — every new refusal is a `ValueError`, `RuntimeError` or `SafeCommitError` subclass.
- **Files**: `src/specify_cli/cli/commands/safe_commit_cmd.py`, the new CLI test module (~300 lines); adjust `tests/specify_cli/cli/commands/test_safe_commit_cmd.py` / `test_safe_commit_cli.py` only where they pinned the old leaf-following or "unknown path → exit 0" behaviour (list every changed assertion in the Activity Log with the FR that flips it).
- **Validation**: new module green; `pytest tests/specify_cli/cli/commands/test_safe_commit_cmd.py tests/specify_cli/cli/commands/test_safe_commit_cli.py tests/specify_cli/cli/commands/test_safe_commit_symlink_loop.py -q` green.

### Subtask T038 – `spec-commit` and the owned checkout keep the link

- **Purpose**: `spec-commit link.md` commits the link (FR-017 names it explicitly); owned writes follow the same rule (lens C T5).
- **Steps**:
  1. Red first: `tests/specify_cli/cli/commands/test_spec_commit_symlink_5671.py` (`git_repo`, `non_sandbox`, `regression`). Build a minimal mission checkout the way `tests/integration/test_protected_primary_spec_commit.py` does (read it for the fixture shape; copy, do not import across test packages unless it is already a shared helper). Under `kitty-specs/<slug>/` create `notes.md` (committed) and `notes-link.md -> notes.md` (untracked); add WIP to `notes.md`; run `sys.executable -m specify_cli spec-commit kitty-specs/<slug>/notes-link.md -m msg --json` (check the real argv in `spec_commit_cmd.py` first). Assert: HEAD has `notes-link.md` mode `120000`; `notes.md` WIP uncommitted. **Mutant killed**: :143 `.resolve()` commits `notes.md`.
  2. Symlinked dir: `kitty-specs/<slug>/assets-link -> assets` must be accepted as a file (not rejected by `_reject_directory_args` :157-176 — use `f.is_dir() and not f.is_symlink()` there) and committed as `120000`.
  3. Owned mode (`OwnedCheckout.files`, `owned_checkout.py:209-229`): replace :223 with `resolve_commit_path(self.owned_root, candidate)`; keep `..` refusal (:220) and loop → `OwnedCheckoutPathRefused` (:224-225) unchanged; containment (:226) is checked on the link's own location (decision in Context). Unit-test it in the same module or in `tests/core/test_adopt_owned_checkout.py`'s style **inside your new module** (do not edit non-owned tests): in-mission link → accepted path ends in the link name; link whose parent resolves outside the mission → refused; looping leaf → refused.
  4. Commit red first, then fix `spec_commit_cmd.py:143` to `resolve_commit_path(repo_root, path)` for both branches and `_relpath` (:215) the same way.
- **Files**: `src/specify_cli/cli/commands/spec_commit_cmd.py`, `src/mission_runtime/owned_checkout.py`, the new test module (~180 lines).
- **Validation**: new module green; `pytest tests/integration/test_protected_primary_spec_commit.py tests/integration/test_owned_checkout_mark_status.py tests/cli/commands/test_owned_checkout_git_calls.py tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_owned_checkout_gate_selftest.py -q` green.

### Subtask T039 – Commit router path classification keeps the link

- **Purpose**: the router's surface and dirtiness checks see the same path `safe_commit` will commit (lens C T6).
- **Steps**:
  1. Red first: `tests/coordination/test_commit_router_symlink_paths.py`. Unit (`unit`, `fast`, no git): `_is_directly_in_worktree(worktree/"link.md", worktree)` where `link.md -> /outside/real.md` must be `True` (pre-fix :1318 resolves to `/outside/...` → `False` — **mutant killed**: leaf-following misclassifies an in-worktree link as foreign and mis-routes the commit). Real git (`git_repo`, `non_sandbox`, `regression`): `_dirty_paths_in_checkout(root, (root/"link.md",))` returns the link when only the link is new and `real.md` is clean, and returns nothing when only `real.md` has WIP but the link is committed and unchanged (pre-fix :1976 asks git about `real.md` → wrong answer both ways).
  2. Commit red; then replace `path.resolve()` at :1318 and :1976 with `resolve_commit_path(worktree_or_root, path)` (keep `worktree.resolve()` / `surface_root.resolve()` for the root itself). :1949 is cosmetic: switch it too for consistency, keep its `ValueError` fallback.
  3. Read `commit_router.py:840-881` (the `safe_commit` call and exception mapping) and confirm `SafeCommitPathLoopRefused` lands in the `RuntimeError` arm (`_STATUS_ERROR`), not the "unchanged" arm.
- **Files**: `src/specify_cli/coordination/commit_router.py`, the new test module (~120 lines).
- **Validation**: new module green; `pytest tests/coordination/test_commit_router.py tests/coordination/test_commit_router_fail_loud.py tests/coordination/test_commit_router_layering.py -q` green.

### Subtask T044 – Commit index deletions without re-adding the file; upgrade carries the migration's own untracks (FR-022)

- **Purpose**: FR-022 — a file the schema-3 upgrade's 3.2.5 backfill stops tracking (`git rm --cached`, file kept on disk and ignored) must leave HEAD in the upgrade commit, instead of staying tracked and ignored at once. The orchestrator rejected the "move the file aside around `safe_commit`" workaround (2026-10-07): a crash between the move and the restore loses the file. This subtask adds first-class deletion support to `safe_commit`, then wires the upgrade call site. Pre-existing behaviour on main; not part of the P0 secret exposure; ships with PR 2.
- **Root cause (verified by the planner in a scratch repo)**: `safe_commit` stages with `git add --force -- <paths>` (`commit_helpers.py` ~`:653-667`) and commits with `git commit --only -- <paths>` (~`:869`). `--only` re-reads the working tree, so a file that is still on disk is re-added and the index deletion made by `git rm --cached` is lost. With the file absent the deletion would commit, which is why the rejected workaround existed.
- **Steps**:
  1. Red first, committed as `test(5443): upgrade does not carry the migration's untracks`: the red commit holds ONLY the real-git upgrade integration tests (step 4, first four bullets) plus `tests/integration/upgrade/__init__.py` — they go through `spec-kitty upgrade`, so they are red on the base for a behavioural reason (the file is still in HEAD). The `safe_commit(index_deletions=...)` unit test is NOT part of the red commit: on the base it would fail with `TypeError: unexpected keyword argument` — a signature reason, not a behaviour (review minor 16). It lands with the fix commit.
  2. Add an explicit keyword parameter `index_deletions: Sequence[Path] = ()` to `safe_commit`: paths whose INDEX deletion is committed while the file stays on disk. Requirements:
     - never touch the working tree and never create a window in which the file is missing (no move, rename, delete or restore);
     - mechanism (review M7 — use this; deviate only with a recorded reason): (1) create a temporary index file under `$GIT_DIR` (`git rev-parse --git-path` → e.g. `<git-dir>/spec-kitty-index-deletions.<pid>.tmp`, never in the work tree); (2) seed it from HEAD, not from the real index: `GIT_INDEX_FILE=<tmp> git read-tree HEAD` — so no operator-staged entry can enter the commit; (3) in that index, `git add --force -- <requested paths>` and `git rm --cached --quiet --ignore-unmatch -- <index_deletions>`; (4) run a plain `git commit -m <message>` (no pathspec, no `--only`, no `-a`) with `GIT_INDEX_FILE=<tmp>` in the env, so hooks run and see exactly the intended diff (HEAD vs the temp index); (5) after a successful commit, `git reset -q HEAD -- <requested ∪ index_deletions>` on the REAL index, so those entries match the new HEAD while every other real-index entry stays as the operator left it; (6) assert afterwards that `git diff --cached --name-only -z -- <requested ∪ index_deletions>` is empty on the real index (no staged entry remains for the committed paths) and raise a `SafeCommitError` subclass naming the paths if not. Note `index.lock` contention: step (5) takes the real `index.lock`; a concurrent git process holding it makes `reset` fail — surface that as a `SafeCommitError` with git's stderr (the commit already landed; say so in the message, like `SafeCommitRecoveryFailed` does) rather than retrying silently. The temp index has its own lock (`<tmp>.lock`), so steps (2)–(4) never contend with the operator's index;
     - WP05's commit-scope gate (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`) exempts `safe_commit` **by symbol**: the step-(4) `git commit` argv must sit lexically inside `safe_commit` or inside a module-private (`_`-prefixed) top-level helper that `safe_commit` calls directly by name (e.g. `_commit_with_index_deletions`, called from `safe_commit`'s body). A deeper call chain, a public helper or an argv assembled in another module is reported by the gate. Build the argv as a literal list (`["git", "commit", "-m", message]`) so the census can see it — WP05's positive control expects to find it;
     - any other staged operator entry (including an operator-staged deletion) stays staged and uncommitted, byte for byte, in the real index;
     - hooks still run (no `--no-verify`); a rejecting hook leaves HEAD and the real index unchanged and the file on disk;
     - the temporary index is removed in a `finally`, also on hook rejection and on `SafeCommitRecoveryFailed`, which still propagates;
     - an entry in `index_deletions` that is not tracked is a no-op, not an error; a path listed both as a normal path and as an index deletion is refused with a clear `SafeCommitError` subclass message.
     Update `__all__` / docstring; keep complexity at or below 15 per function (extract a helper such as `_commit_with_index_deletions`).
  3. Call site, `src/specify_cli/upgrade/autocommit.py` (owned by WP01 — a **recorded out-of-map edit**, one call site in `commit_touched_checkout`; record a one-line rationale in the Activity Log, e.g. "FR-022 needs `safe_commit(index_deletions=...)`; the only caller is the upgrade commit, WP01 owns the file, edit limited to one call site"). Pass the migration-made untracks: candidates whose porcelain entry is an index deletion (`xy[0] == "D"`) that were NOT in the pre-run baseline, whose file still exists (`os.path.lexists`) and is now ignored (one batched `git check-ignore --stdin -z`). Never pass an operator-staged deletion (it is in the baseline). Because WP07 depends on WP01, the baseline and `prepare_upgrade_commit_files` seams are already in place; do not re-derive them: WP01 T008 already records `_GitStatusPaths.index_deletions` and **excludes** exactly these paths from `prepare_upgrade_commit_files` (otherwise `git add --force` would re-add them) — this call site moves them from "excluded" to `index_deletions=`; it does not change `prepare_upgrade_commit_files`. Protected-test compatibility (WP01 Context): `tests/upgrade/test_upgrade_auto_commit_unit.py:390-498` call `commit_touched_checkout` on a NON-git `tmp_path` with `prepare_upgrade_commit_files` monkeypatched (`lambda _project, baseline_paths:`) and `safe_commit` faked with `**kwargs` — the deletion collection must read from the `_GitStatusPaths` it already has or tolerate a failing probe (→ no deletions), must not add arguments to the `prepare_upgrade_commit_files(checkout, baseline_paths)` call, and should pass `index_deletions=` only when non-empty. Those four protected files stay green unchanged.
  4. Tests (new file `tests/integration/upgrade/test_upgrade_carries_migration_untracks.py`, real git, `git_repo` + `non_sandbox`, `regression` — not `p0_repro`; reuse WP01's `tests/upgrade/_legacy_upgrade_fixture.py` helpers):
     - `test_upgrade_commits_migration_untrack`: legacy project with tracked, clean `.agents/skills/demo/SKILL.md` so `m_3_2_5_agents_skills_gitignore_backfill._untrack_tracked_paths` runs `git rm --cached`. After `spec-kitty upgrade --yes`: `git ls-tree -r --name-only HEAD` lacks the file, it is still on disk with identical bytes, `git check-ignore` matches it, `git status --porcelain` shows nothing for it. Confirm 3.2.5 applies from the fixture's starting version; if not, start at one where it does.
     - control `test_operator_staged_deletion_stays_staged`: an operator-staged `D` of another tracked file (`git rm --cached docs/old.md`) is still staged and absent from the upgrade commit.
     - `test_rejecting_hook_commits_nothing_and_file_stays`: a rejecting pre-commit hook leaves HEAD unchanged and the file on disk (no move-aside).
     - `test_file_present_at_every_step`: a pre-commit hook that appends `test -f <file>` results to a counter file outside the work tree; assert every recorded result is "present".
     - `safe_commit` test (`tests/git_ops/`, temp repo, `git_repo`/`non_sandbox`; lands with the fix commit, not the red one — step 1): `safe_commit(repo, ..., index_deletions=[Path("a.md")])` with a concurrently staged unrelated `b.md` and an unrelated staged deletion `c.md` — HEAD loses `a.md` only, `a.md` is on disk, `b.md` and `c.md` remain staged exactly as before, no `D a.md` remains staged in the real index (step (6)), and no temp index file is left under `$GIT_DIR`. Plus: a pre-commit hook that writes `git diff --cached --name-status` (it sees `GIT_INDEX_FILE`) to a file outside the work tree records exactly `D a.md` — kills a mutant that commits from a copy of the real index (it would show `b.md`/`c.md`).
  5. Mutant notes: a mutant that re-adds the file (today's behaviour) fails the "absent from HEAD" assertion; a mutant that moves the file aside fails the `test -f` at-every-step check; a mutant that resets the whole index fails the staged-`b.md`/`c.md` assertions; a mutant that drops `index_deletions` for operator-staged entries fails the control test.
- **Files**: `src/specify_cli/git/commit_helpers.py`, `src/specify_cli/upgrade/autocommit.py` (one call site, out of map, after WP01), `tests/integration/upgrade/__init__.py` (new, empty — `tests/integration/upgrade/` does not exist on `origin/main` and every `tests/integration/*/` subpackage has an `__init__.py`; WP01 creates nothing there), `tests/integration/upgrade/test_upgrade_carries_migration_untracks.py` (new, ~150 lines), the `safe_commit` unit test module (append to `tests/git_ops/test_safe_commit_link_and_stage_detail.py` or a sibling in `owned_files`).
- **Validation**: new tests red on the base, green after; `tests/upgrade/` protected files and `tests/git_ops/test_safe_commit_*.py` green unchanged; the upgrade test marked `regression`.

### Subtask T040 – Verification, loop policy on every interpreter, closeout

- **Purpose**: honest green across interpreters and contracts (lens C T7).
- **Steps**:
  1. Loop refusal on every surface: one parametrized case per surface (core `safe_commit`, `safe-commit` CLI, `spec-commit` CLI, `OwnedCheckout.files`, `resolve_commit_path`) with a real `a -> b`, `b -> a` loop; each refuses with its surface's existing error shape and leaves HEAD/index unchanged. The 3.12 CI gate runs them natively; the nightly 3.13 matrix covers the silent-resolve path; T034's monkeypatched case covers 3.13 locally on 3.12. If your local interpreter is 3.13, run once on 3.12 too (`uv run --python 3.12 pytest ...`) or note in the Activity Log that only CI covered it.
  2. Targeted runs (no full suites):
     ```bash
     .venv/bin/python -m pytest tests/kernel/test_resolve_commit_path.py tests/kernel/test_resolution.py \
       tests/git_ops/test_safe_commit_link_and_stage_detail.py tests/git_ops/test_safe_commit_helper_integration.py \
       tests/git_ops/test_safe_commit_commit_failure_classification.py tests/integration/git/test_safe_commit_backstop.py \
       tests/specify_cli/cli/commands/test_safe_commit_paths_5401_5671_4722.py tests/specify_cli/cli/commands/test_safe_commit_cmd.py \
       tests/specify_cli/cli/commands/test_safe_commit_cli.py tests/specify_cli/cli/commands/test_safe_commit_symlink_loop.py \
       tests/specify_cli/cli/commands/test_spec_commit_symlink_5671.py tests/coordination/test_commit_router_symlink_paths.py \
       tests/coordination/test_commit_router.py tests/integration/upgrade/test_upgrade_carries_migration_untracks.py tests/consolidation/test_bare_slug_alias_consumers.py tests/cli/commands/test_retrospect.py -q
     .venv/bin/python -m pytest tests/architectural/test_loop_aware_resolution.py tests/architectural/test_safe_commit_import_boundary.py \
       tests/architectural/test_owned_checkout_single_authority.py tests/architectural/test_no_legacy_terminology.py -q
     .venv/bin/ruff check <touched files>; .venv/bin/ruff format --check --force-exclude <touched files>
     .venv/bin/mypy src/kernel/resolution.py src/specify_cli/git/commit_helpers.py src/specify_cli/cli/commands/safe_commit_cmd.py \
       src/specify_cli/cli/commands/spec_commit_cmd.py src/specify_cli/coordination/commit_router.py src/mission_runtime/owned_checkout.py
     ```
  3. `git grep -n "\.resolve()" -- src/specify_cli/cli/commands/safe_commit_cmd.py src/specify_cli/cli/commands/spec_commit_cmd.py` — every remaining hit resolves a **root**, never a commit path; list them in the Activity Log.
  4. Record red outputs (one line per red test, the assertion that failed) and green counts in the Activity Log; append tracer entries (`spec-kitty agent tracer-append --mission upgrade-migration-commit-scope-01M4AKVE --category approach|design-decisions|tooling-friction --actor <agent>`); hand WP08 a one-line user-visible summary per issue (#5401, #5671, #4722) in the Activity Log; `spec-kitty agent tasks mark-status T034 T035 T036 T037 T038 T039 T044 T040 --status done --mission upgrade-migration-commit-scope-01M4AKVE`.
- **Validation**: all of the above green; each fix commit is preceded on the lane by its red `test(...)` commit.

## Test Strategy

- Red-first per defect (C-004): T034 (helper), T035/T036 (core), T037 (CLI), T038 (spec-commit/owned), T039 (router) each land a `test(<issue>): ...` commit that is red on the planning base for the stated reason before its fix commit.
- Behavioural assertions only: tree modes and names in HEAD (`git ls-tree`, `git show --name-only/--name-status`), index snapshots, exit codes and named paths in errors. No assertions on internal call counts or private return shapes except `_stage_requested_files`' new tuple where a unit test is cheaper.
- SC-006 discipline: every real-git case carries unrelated staged / unstaged / untracked work and asserts it is untouched.
- Commands: see T040 step 2 (targeted only; CI owns full suites).

## Risks & Mitigations

- **Exception-type contracts** (`test_bare_slug_alias_consumers.py:426`, `test_retrospect.py:1015`, `commit_router.py:878`, `autocommit.py:429`, `decision_log.py:273`): every new error is a `RuntimeError` (or `SafeCommitError`) subclass; the staging message prefix is byte-identical; run those tests explicitly.
- **3.12 vs 3.13 `Path.resolve` loop behaviour**: all loop detection goes through `kernel.resolution` (stat probe), never through `resolve()` raising; monkeypatched 3.13 case in T034; nightly matrix.
- **Relative-path contract**: core `preflight_commit` keeps relative paths verbatim; only absolute paths are normalised (internal callers such as upgrade pass relative paths — lens C confirmed the P0 path is unaffected).
- **Symlinked worktree roots** (macOS `/tmp`): the helper resolves parents, so `relative_to(resolved_root)` still works; covered by the parent-symlink unit case.
- **Windows symlinks**: skip with a named reason when `os.symlink` is unavailable; never let a skipped symlink case hide a non-symlink assertion (keep rename / unknown-path cases in separate, unskipped tests).
- **Cross-boundary refusal false positives**: use component-wise containment (`GitPath`), test `docs2/` vs `docs/`.
- **Loop-aware gate**: no `try/except` that inspects `ELOOP` outside `src/kernel/resolution.py`; callers catch `OSError` generically or use `is_symlink_loop_error` the way `_resolve_file_argument` already does.

## Review Guidance

- Confirm each red commit precedes its fix and the recorded red reason is a behavioural assertion (wrong tree entry, exit 0, missing name), not an import or collection error — except T034's helper module, where the missing symbol is the expected red.
- Check `git ls-tree HEAD <link>` mode `120000` assertions exist for safe-commit (relative, absolute, tracked, via directory), spec-commit, and in-process `safe_commit`; and that the target's WIP is asserted uncommitted in each.
- Check the #5401 test asserts both `ls-tree HEAD docs/old.md` empty **and** an empty `git diff --cached` afterwards.
- Check the staging-failure message keeps the prefix and names only the bad path plus git's reason.
- Check no file outside `owned_files` changed (`git diff --stat <planning base>`), except the one recorded out-of-map call site in `src/specify_cli/upgrade/autocommit.py` (T044, rationale in the Activity Log).
- Check the owned-checkout decision is recorded in the Activity Log and implemented as stated.
- mypy / ruff clean, complexity ≤ 15, `__all__` updated in `kernel/resolution.py` and `commit_helpers.py`.

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Orchestrator decision: FR-022 moved here from WP01 (move-aside rejected: file lost if the process dies mid-commit); WP07 now depends on WP01 and records one out-of-map edit in `upgrade/autocommit.py` (T044).
- 2026-10-07 – planner-priti – Post-tasks review folded: M7 (T044 mechanism: temp index under `$GIT_DIR` seeded by `git read-tree HEAD`; `add --force` requested + `rm --cached` deletions in it; plain `git commit` with `GIT_INDEX_FILE` so hooks see the right diff; `git reset -q HEAD -- <requested ∪ deletions>` on the real index; no staged entry may remain for committed paths; `index.lock` contention surfaced, not retried), minor 16 (the red is the upgrade integration test; the `index_deletions` unit test lands with the fix), minor 17 (`owned_files` += `src/specify_cli/upgrade/autocommit.py` — out-of-map, sequenced after WP01 — and `tests/integration/upgrade/__init__.py`; WP01 does not create `tests/integration/upgrade/`). Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ` (not reopened): WP05's gate exempts `safe_commit` by symbol, so T044's temp-index `git commit` must live in `safe_commit` or a private helper it calls directly; WP05 now depends on this WP. Stale "no dependencies" / "do not edit autocommit.py" wording corrected. WP01 T008 now excludes index-deletion candidates whose file still exists; T044 routes them into `index_deletions=`.
- 2026-10-07 – planner-priti – Analysis fold AN-COV-002: C-004 and NFR-001 added to `requirement_refs` (NFR-001: any changed pin listed old→new in this Activity Log).
- 2026-10-07 – orchestrator (recording implementer evidence) – Lane-g 9a148e333..69254b1d5. Red→fix pairs: T034 96e513f1f/194ade3ca; T035–T036 93a18b744/2ee3636c6; T037 21fd0fee9/b60f25a71; T038 649d9bb93/a3898c00a; T039 fd3125d12/2b102b43a; T044 959e7ccba/973b77f62 (+ db5561baa, d404cff22, d205ff813, 5149a7aac); registry row 69254b1d5. Every red was a content assertion except T034 (ImportError on the helper's own module). Targeted run: 5501 passed (2 new-gate failures fixed, 56 passed on re-run); tests/upgrade: 1112 passed, 46 preview failures (`.venv`, pre-existing). 14/15 mutants killed (L equivalent). Out-of-map edits: upgrade/autocommit.py (T044 call site), test_cli_git_paths.py (rename-sides pin, FR-016 — accepted by the orchestrator), .github/ci-module-registry.yml (nightly row for the new tests/integration/upgrade — orchestrator prefers the test under tests/upgrade so it runs per PR; for review).
- 2026-10-07 – orchestrator (recording implementer evidence) – Review cycle 1 rework: the claim merged lane-a into lane-g (a5c54bd94). de383fff2 moves the FR-022 e2e from `tests/integration/upgrade/` to `tests/upgrade/test_upgrade_carries_migration_untracks_5443.py` so it runs per PR. It drops `tests/integration/upgrade/__init__.py` and reverts `.github/ci-module-registry.yml` to the base (30 passed with the shard registry). Wherever this prompt names `tests/integration/upgrade/…`, read the new path. ca31d852a (red) and 00f62b24d (fix):
  - m1: the temp index is now under `--absolute-git-dir`; RED showed it inside the work tree.
  - m4: the router's `_relpath` and `_is_directly_in_worktree` catch OSError on a symlink loop.
  - m2: the guard is pinned.
  - m3: the message carries git's "did not match any files".
  - Gates: 1863 passed / 5 skipped; `tests/architectural` 4188 passed; ruff, format and C901 clean; mypy only the pre-existing commit_router.py:936.
- 2026-10-07 – orchestrator – Correction: an earlier commit (1c10078) bulk-rewrote this prompt's `tests/integration/upgrade` paths, including past Activity Log entries. This commit restores the original planning text; the path change is recorded only in the entry above. Review cycle 2 (reviewer-renata) approved; non-blocking notes n1, n2 and n4 are in review-cycle-2.md.
