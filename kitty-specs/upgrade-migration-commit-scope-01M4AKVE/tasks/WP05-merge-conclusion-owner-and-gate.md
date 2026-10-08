---
work_package_id: WP05
title: Merge-conclusion owner and an empty commit-scope gate
dependencies:
- WP01
- WP04
- WP06
- WP07
requirement_refs:
- FR-013
- SC-005
- NFR-002
- C-002
- C-004
- C-005
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T17:32:40.760896+00:00'
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
phase: Phase 3 - Close the class
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/merge_conclusion.py
create_intent:
- src/specify_cli/git/merge_conclusion.py
- tests/architectural/_commit_scope_census.py
- tests/architectural/test_commit_scope_owner.py
- tests/git_ops/test_merge_conclusion_owner.py
- tests/git_ops/test_merge_conclusion_owner_unit.py
- tests/lanes/test_merge_conclusion_routing.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/git/merge_conclusion.py
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/coordination/coherence.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/architectural/_commit_scope_census.py
- tests/architectural/test_commit_scope_owner.py
- tests/git_ops/test_merge_conclusion_owner.py
- tests/git_ops/test_merge_conclusion_owner_unit.py
- tests/lanes/test_merge_conclusion_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5443'
---

# Work Package Prompt: WP05 – Merge-conclusion owner and an empty commit-scope gate

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

- **FR-013 / SC-005 / US7**: an architectural gate over `src/**/*.py` reports every sweeping, pathspec-less or hook-bypassing commit route — `add -A`/`add .`/`add --all`/`add -u`/`add :/`, a pathspec-less `commit` (including `--amend`), `commit -a`, `--no-verify`/`commit -n`/`-c core.hooksPath=`, and a `merge`/`revert`/`cherry-pick` that creates a commit — and passes on the real tree with **no allowlist**. Its only exemptions are the **two canonical owners, by symbol** (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`, do not reopen): `safe_commit` in `src/specify_cli/git/commit_helpers.py` (including WP07's index-deletion commit, which is pathspec-less under a temporary index) and the merge-conclusion owner in `src/specify_cli/git/merge_conclusion.py`, through which every merge/revert/squash conclusion in `src/` is routed. No allowlist, no path-level exemption.
- **C-005**: every automatic commit this WP touches goes through `safe_commit` (none here) or the owner, except the `consolidation.py:843-849` amend, which is C-005's second recorded exception: "the restored-bookkeeping amend in a consolidation worktree (`commit --amend --only -- <restored>`)"; the owner never adds a pathspec-less sweep the git state does not already force (git refuses a pathspec while a merge is being concluded — verified below).
- **ADR 2026-09-30-1** (`docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md`) and Decision `01M4B2XJQ0JAHVXGVDNQBMF6XF` (`decisions/DM-01M4B2XJQ0JAHVXGVDNQBMF6XF.md`): no allowlist, no `_baselines.yaml` entry, no count ratchet. Non-vacuity: scanned-file floor, one planted hit per form, a positive control that disabling the owner exemption makes the owner itself fail, and negative controls for the non-committing forms.
- **Behaviour preservation**: the routed merge paths (auto-rebase, consolidation, lane allocation, coordination repair, lifecycle rollback) produce the same commits, messages, parents, env, signing behaviour and conflict handling as on the planning base. Existing merge/consolidation suites pass unchanged.

## Context & Constraints

- Spec: `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md` (US7, FR-013, SC-005, C-005); plan IC-05; squad evidence `<operator-local squad notes>` (site table, git behaviour, owner recommendation).
- **Why this WP depends on WP07** (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`): WP07 T044 adds `safe_commit(index_deletions=...)`, whose commit runs a plain `git commit` with `GIT_INDEX_FILE=<temp index>` — pathspec-less by construction, so the census reports it unless it sits inside `safe_commit`'s exempt scope (T023 step 2). The gate must be written against the final `commit_helpers.py`, and its real-tree test must be green with WP07's commit present; hence base on WP07 too. Do not edit `commit_helpers.py` (WP07's); if WP07's commit argv is outside the exempt scope defined below, stop and report to WP07 — never add an exemption.
- **Why this WP depends on WP01, WP04, WP06**: on `origin/main` (5ee323802) the census also hits `migration/runner.py:330` (`add -A`), `:360`, `:376` (`commit --no-verify`) — removed by WP01; `consolidation/mission_number/bake.py:389`, `:555` (pathspec-less `commit -m`) — rewritten by WP04; `core/vcs/git.py:640` (`add -A`), `:658`, `core/git_ops.py:157` (`add .`), `:159` — deleted by WP06. The gate can only start empty once those land; base this lane on the merge of WP01+WP04+WP06+WP07. If any of those sites is still present on your base, STOP and report — do not allowlist it, do not edit those files (not owned).
- **Census on `origin/main` (rerun it at your base and paste the result in the Activity Log)** — the merge-conclusion sites this WP routes:

  | Site (origin/main) | Call | Shape |
  |---|---|---|
  | `lanes/auto_rebase.py:917-920` | `_run(["git","-c","commit.gpgsign=false","commit","-m",message])` | concludes the `merge --no-commit` of `:985` after classifier resolution |
  | `lanes/auto_rebase.py:1006-1009` | `_run([... "commit","--no-edit"])` behind `_merge_head_exists` (`:488`) | concludes a clean `merge --no-commit` |
  | `lanes/consolidation.py:843-849` | `commit --amend --no-edit --allow-empty` in `_preserve_target_newer_planning_artifacts` (`:772`) | amend of the squash commit in the temp worktree → `--amend --only -- <restored>` |
  | `lanes/consolidation.py:1013` | `_git_in(worktree, ["-c","commit.gpgsign=false","commit","--no-edit"], env)` in `_complete_merge_after_target_owned_resolution` (`:992`) | concludes a conflicted merge (callers: consolidation `:1420`, worktree_allocator `:1544`) |
  | `lanes/consolidation.py:1333-1346` | `commit -m "feat(<src>): squash merge of mission"` in `_merge_branch_into` (`:1209`) | concludes `merge --squash` (`:1106`, `_run_squash_merge` `:1081`) in the fresh `kitty-merge-` temp worktree (`:1243`, `worktree add --detach` `:1266-1274`) |
  | `lanes/consolidation.py:1410-1416` | `git merge <src> --no-edit -m "Merge <src> into <tgt>"` | committing merge, MERGE strategy |
  | `lanes/worktree_allocator.py:1426-1440` | `git merge --no-edit -m "Merge recorded planning-artifact commit into <lane> (FR-009)" <sha>` | committing merge |
  | `lanes/worktree_allocator.py:1549-1556` | `git commit --no-edit` (NO `-c commit.gpgsign=false`) | concludes the dependency/planning merge after target-owned resolution |
  | `lanes/worktree_allocator.py:1645-1658` | `git merge --no-edit -m "Merge dependency lane …" <dep_branch>` in `_merge_dependency_lane_tips` | committing merge |
  | `coordination/coherence.py:735-741` | `git -C <coord> revert --no-edit <sha>` in `_revert_recorded_sha` (`:726`) | committing revert |
  | **`cli/commands/agent/workflow.py:661-672`** | `git -c commit.gpgsign=false revert --no-edit <sha>` in `_revert_coordination_commit` (`:634`) | committing revert — **not in lens B's table; found by this WP's census; owned here**. Post-tasks site rescan (review NOTE 5) re-confirmed it: the `"revert"` token is at `:666` inside the `:661-674` call; no other uncovered site |

  Not hits (negative controls for the census): `merge --squash` (`consolidation.py:1106`), `merge --no-ff --no-commit` (`auto_rebase.py:985`), `merge --abort` / `revert --abort`, `merge --ff-only` (`cli/commands/_coordination_doctor.py:1900`, `_workspace_husk_doctor.py:201`, `agent/mission_repair.py:181`), `commit --only … -- <paths>` (`git/commit_helpers.py:869`), `commit -m … -- meta_rel` (`acceptance/__init__.py:1760`, `:1780`), `add <path>` without the sweeping flags (`auto_rebase.py:269/274/714/852`, `conflict_resolver.py:185`, `acceptance:1751/1777`), `worktree add`. `git rebase` (`consolidation.py:1363`) replays existing commits and is out of FR-013's forms — document it as out of scope in the gate docstring, do not flag it.
- **git behaviour verified on 2026-10-07 (scratch repo, git 2.x)** — the owner design rests on these; re-verify in T024's real-git tests:
  1. `git merge --no-commit --no-edit -m "msg" <b>` then `git commit --no-edit` → commit subject `msg` (MERGE_MSG carries `-m`).
  2. With MERGE_HEAD present, `git commit -m x -- <path>` → `fatal: cannot do a partial commit during a merge.` (a conclusion cannot take a pathspec — hence an owner, not a pathspec rule).
  3. `git merge --no-commit` on a fast-forwardable branch fast-forwards and leaves no MERGE_HEAD.
  4. `git merge` (diverged or `--no-ff`) with an unrelated staged file → refuses ("Your local changes … would be overwritten by merge").
  5. `git merge --squash` on a fast-forwardable branch with an unrelated staged file → **succeeds and keeps the unrelated file staged** (`A b`, `A u`), SQUASH_MSG written. A squash conclusion is therefore safe only in a fresh worktree.
  6. `git revert --no-edit <sha>` (committing) with an unrelated staged file → refuses. **`git revert --no-commit <sha>` and `git cherry-pick --no-commit` with an unrelated staged file → accepted, unrelated file stays staged.** Do NOT convert committing reverts into `--no-commit` + conclude: that would weaken git's own guard.
  7. `git commit --amend --only --no-edit --allow-empty -- r` with another file `q` staged → amends only `r`; `q` stays staged.
  8. Concluding via `git commit` runs `pre-commit`/`commit-msg`/`post-commit`; a committing `git merge` runs `pre-merge-commit`/`commit-msg`/`post-merge`. spec-kitty's lane-tip recorder installs `post-commit` and `post-rewrite` (`policy/lane_tip_recorder.py:75`). Converting a committing merge into `--no-commit` + `git commit` would change which operator hooks run on lane merges — so committing merges/reverts keep their exact argv and are *run by* the owner, not rewritten.
- **Owner placement**: `src/specify_cli/git/merge_conclusion.py` (the `specify_cli.git` package already hosts commit authority — `commit_helpers.py`, `ref_advance.py`; `lanes/consolidation.py:28` and `lanes/lane_tip.py:24-25` already import from it; `cli/commands/agent/workflow.py:89` too). Not `kernel/git`: its module docstring (`src/kernel/git/__init__.py:1-16`) scopes it to *reading* paths. Do not edit `specify_cli/git/__init__.py` (import the module directly), `git/commit_helpers.py` (WP07) or any file outside `owned_files`.
- **Env authority**: `tests/architectural/test_merge_pipeline_ratchets.py:168-215` requires every `subprocess.run` in `lanes/consolidation.py` to pass `env=` and forbids `os.environ` there outside `_make_merge_env` (`consolidation.py:650`). The owner takes `env` explicitly and never reads `os.environ`; `env=None` means "inherit" and is used only by the workflow rollback, which inherits today.
- Charter: ATDD-first — T023's gate is its own red commit; complexity ≤ 15 per function; ruff-format touched files; terminology ratchet (`tests/architectural/test_no_legacy_terminology.py`) — say "consolidation pipeline", never "lane merge"/"lane-merge"/"feature" in new prose.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP05 --agent claude`. Base on the integration of WP01, WP04, WP06 and WP07.

## Subtasks & Detailed Guidance

### Subtask T023 – Red-first: the commit-scope census and gate

- **Purpose**: pin the class before routing anything; the red must list exactly the merge-conclusion sites above (proving the census sees them for the right reason).
- **Steps**:
  1. Read `tests/architectural/_destructive_op_census.py` (helpers `iter_py_files` :70, `parse` :75, `module_string_constants` :85, `import_alias_map` :113, `resolve_token` :151, `argv_tokens` :160, `ordered_subsequence` :165, `scan_planted_source` :255) and the precedent gate `tests/architectural/test_git_path_listing_owner.py` (docstring shape :1-28, `_SCANNED_FILE_FLOOR` :42, positive control :74, planted-hit parametrisation :133, owner-skip test :179). Reuse those helpers; do not copy them.
  2. Create `tests/architectural/_commit_scope_census.py` — the single authority for the rule:
     - `CANONICAL_OWNERS` — exactly two entries, keyed by symbol, never by path alone (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`): `OwnerSymbol(rel="src/specify_cli/git/commit_helpers.py", symbols=("safe_commit",))` and `OwnerSymbol(rel="src/specify_cli/git/merge_conclusion.py", symbols=("run_committing_op", "conclude_in_progress_op"))`. A hit is exempt only when its enclosing **top-level** function (AST, nested defs count as their enclosing top-level function) is one of the owner's `symbols`, or is a module-private (`_`-prefixed) top-level function of the same module that one of those symbols calls **directly by name** (one level of `ast.Call` with an `ast.Name` func inside the owner body — computed by the census, never listed by hand). Everything else in those two files is scanned like any other file. Assert at import time that `len(CANONICAL_OWNERS) == 2` and that each named symbol exists in its file (a rename must fail the gate loudly, not silently drop the exemption). `src_files()` = every `src/**/*.py`.
     - `Hit(path, lineno, kind, argv_repr)` NamedTuple; `kind` ∈ {`add-sweep`, `commit-no-pathspec`, `amend-no-pathspec`, `commit-all`, `hook-bypass`, `committing-merge`, `committing-revert`, `committing-cherry-pick`}.
     - Candidate argv = every `ast.List`/`ast.Tuple` whose resolved tokens start with `"git"`, plus, for a call to a known git runner name (`_git_in`, `run_git`, `_run_git`, `_git`, `_run_git_for_commit`; keep the set in one constant and document it), its first list/tuple argument **or**, for a varargs runner (`run_git(cwd, *args)` — `kernel/git/runner.py:65-67`), the positional arguments after `cwd` taken as the argv (string constants resolved, a `Starred` argument kept as an unresolved token). Example on `origin/main`: `implement_claim.py:210` `run_git(repo_root, "add", "--force", "--", *rel_paths)` → `["add","--force","--",<starred>]` — path-scoped, not a hit; a `run_git(cwd, "add", "-A")` would be (review minor 14). Resolve module-level string constants (`module_string_constants`) so `_GIT_WORKTREE`-style indirection does not hide a hit.
     - `classify_argv(tokens) -> list[str]`: strip a leading `"git"`; walk global options (`-C <x>`, `-c <k=v>`, `--literal-pathspecs`, `--no-pager`, `--git-dir=…`, `--work-tree=…`) — a `-c` value starting with `core.hooksPath=` is `hook-bypass`; then by subcommand:
       - `add`: `add-sweep` if any of `-A`, `--all`, `.`, `-u`, `--update`, `:/`, `:/*` appears.
       - `commit`: `hook-bypass` for `--no-verify`/`-n`; `commit-all` for `-a`/`--all`; `amend-no-pathspec` when `--amend` and no `"--"` token followed by ≥1 token (a `Starred` after `--` counts as a path); otherwise `commit-no-pathspec` when there is no such `"--" <path…>`.
       - `merge`: `committing-merge` unless one of `--no-commit`, `--squash`, `--ff-only`, `--abort`, `--quit` is present (`--continue` IS committing).
       - `revert` / `cherry-pick`: committing unless `--no-commit`/`-n`, `--abort`, `--quit`, `--skip`.
       - any subcommand: `--no-verify` → `hook-bypass`.
       - Unresolved tokens (`None`) never satisfy a flag test and never count as `"--"`.
     - `census(paths) -> list[Hit]` drops a hit only through the `CANONICAL_OWNERS` symbol rule above (resolved-path equality for the file, then the enclosing-symbol test); `census_source(text, rel)` never applies the exemption (used by planted cases and the positive control).
     - Module docstring: the rule, the forms, the owner exemption, and the **AST blind spots** (argv grown by `+=`/`.append`/`.extend` across statements, `shlex.split(var)`, `shell=True`/`os.system` strings, argv held in a variable assigned in another function, `git rebase`/`pull`/`am` out of FR-013's forms, and plumbing commits — `git commit-tree` + `git update-ref` — which create commits without the porcelain `commit` subcommand; `safe_commit`'s expected-parent path uses them (`commit_helpers.py:1074` `_create_expected_parent_commit`, `:1103` `_compare_and_swap_commit_ref`). Plumbing commits are outside this gate: say so in the docstring and record a follow-up issue (title: "commit-scope gate: cover commit-tree/update-ref plumbing commits") in the Activity Log with its number once filed. State that none of the blind-spot shapes other than the documented plumbing exists in `src/` today (verify with `git grep -n "shell=True" -- src` — only comments at `cli/commands/_git_remedies.py:81`, `configured_command.py:1/172`).
  3. Create `tests/architectural/test_commit_scope_owner.py`, `pytestmark = pytest.mark.architectural`, docstring in the precedent's shape (record the planning-base numbers: scanned files, hits per file). Tests:
     - `test_no_sweeping_or_hook_bypassing_commit_outside_the_owner`: `census(src_files()) == []`; on failure print each hit as `path:line kind argv` plus the fix hint ("route merge/revert/squash conclusions through specify_cli.git.merge_conclusion; commit written paths through safe_commit").
     - `test_gate_scans_a_non_trivial_number_of_files`: floor = 90% of the count at your base (origin/main has 1397 `src/**/*.py`; set the constant from your measured number and write the measurement in the docstring).
     - `test_planted_hit_is_reported` parametrised, one case per form: `["git","add","-A"]`, `["git","add","."]`, `["git","add","--all"]`, `["git","add","-u"]`, `["git","add",":/"]`, `["git","commit","-m",msg]`, `["git","commit","--amend","--no-edit"]`, `["git","commit","-a","-m","x"]`, `["git","commit","--no-verify","-m","x","--","p"]`, `["git","commit","-n","-m","x","--","p"]`, `["git","-c","core.hooksPath=/dev/null","commit","-m","x","--","p"]`, `["git","merge","--no-edit",b]`, `["git","revert","--no-edit",sha]`, `["git","cherry-pick",sha]`, `["git","merge","--continue"]`, `_git_in(wt, ["commit","--no-edit"], env)`, and a module-constant indirection case (`_ADD = "add"; ["git", _ADD, "-A"]`). Plus the varargs runner form `run_git(cwd, "add", "-A")` and `run_git(cwd, "commit", "-m", msg)` (review minor 14). Assert the exact `kind` per case (a mutant that maps every hit to one kind, or drops a form, fails).
     - `test_non_committing_forms_are_not_reported` parametrised: every negative control listed in Context (`--squash`, `--no-commit`, `--ff-only`, `--abort`, `commit --only -m x -- p`, `commit -m x -- p`, `add -- p`, `add p`, `worktree add`, `revert -n sha`, `rebase main`, `run_git(cwd, "add", "--force", "--", *paths)`, `["git","commit-tree",tree,"-p",parent,"-m",m]` (plumbing, documented out of scope)). Kills a mutant that flags every `merge`.
     - `test_canonical_owners_are_the_only_exemptions`: (a) `merge_conclusion.py` and `commit_helpers.py`, scanned with the exemption bypassed (`census_source`), each report ≥1 hit (positive control: both owners really are what the gate would otherwise catch — for `commit_helpers.py` that is WP07's temp-index `git commit`; if it reports none, WP07's commit argv is not statically visible: stop and report); (b) `census([merge_conclusion.py, commit_helpers.py]) == []`; (c) a planted copy of either owner's source written to `tmp_path/other.py` IS reported (exemption needs the owner file); (d) planted into a copy of `commit_helpers.py` at its real relative path (`census_source(text, rel="src/specify_cli/git/commit_helpers.py")` with the exemption applied): a pathspec-less `git commit` in a new top-level function **not** called by `safe_commit` IS reported, and the same argv in a private helper called directly from `safe_commit` is not (the exemption is by symbol, not by file); (e) `CANONICAL_OWNERS` has exactly two entries (kills a mutant that adds a third).
     - `test_classify_argv_ignores_unresolved_tokens`: `["git", None, "-A"]` (no subcommand resolved) → `[]`; `["git","commit","-m",None,"--",None]` → `[]` (a `--` followed by an unresolved path still counts as a pathspec).
  4. Run on your base: `.venv/bin/python -m pytest tests/architectural/test_commit_scope_owner.py -q`. Expected: everything green except the real-tree test, which fails listing exactly the 11 sites in the Context table (auto_rebase ×2, consolidation ×4, worktree_allocator ×3, coherence ×1, workflow ×1) — WP07's temp-index commit inside `safe_commit`'s scope is exempt and does not appear; the merge-conclusion owner does not exist yet, so its positive control (a) is written against T024's module and goes green with T024. Paste that output in the Activity Log. If anything else appears, it belongs to a WP that has not landed or to an unowned site — stop and report; do not widen ownership silently.
  5. Commit T023 alone: `test(5443): red-first commit-scope gate (merge conclusions still unrouted)`.
- **Files**: the two new test-support/gate files.
- **Validation**: red for the right reason (the listed sites, nothing else); planted/negative tests green.

### Subtask T024 – The canonical owner `specify_cli.git.merge_conclusion`

- **Purpose**: one module that may run a committing merge/revert and conclude an in-progress merge/revert/cherry-pick/squash (FR-013, C-005).
- **API** (keep it this small; module docstring explains the git facts 1-8 it relies on):
  - `class MergeConclusionRefused(RuntimeError)` — message always names the worktree and the reason.
  - `@dataclass(frozen=True) class FreshWorktree: worktree: Path; head: str` — minted only by `mint_fresh_worktree(worktree, env) -> FreshWorktree`, which asserts: (i) `git rev-parse --git-dir` ≠ `--git-common-dir` (a linked worktree, never the operator's primary checkout); (ii) HEAD is detached (`git symbolic-ref -q HEAD` fails); (iii) `status_entries(worktree, untracked="all")` (from `kernel.git`) is empty — nothing staged, modified or untracked. Any failure raises `MergeConclusionRefused` naming the offending paths.
  - `run_committing_op(worktree, op, args, *, env, disable_gpgsign) -> subprocess.CompletedProcess[str]` — `op ∈ {"merge","revert"}` (add `"cherry-pick"` only if a site needs it; none does today). Refuses (raises, before any subprocess) when `args` contains `--no-verify`, `--no-commit`, `-n`, `--squash`, `--continue`, or any `-c core.hooksPath=`; runs `["git", *(["-c","commit.gpgsign=false"] if disable_gpgsign else []), op, *args]` with `cwd=worktree`, `capture_output=True`, `text=True`, `check=False`, `env=env`. No index precheck: git itself refuses a committing merge/revert over a staged unrelated file (facts 4, 6); T024's tests pin that reliance.
  - `conclude_in_progress_op(worktree, *, env, message=None, fresh=None, disable_gpgsign=True) -> subprocess.CompletedProcess[str]` — detects the op: `git rev-parse -q --verify MERGE_HEAD` / `REVERT_HEAD` / `CHERRY_PICK_HEAD`; else SQUASH_MSG via `git rev-parse --git-path SQUASH_MSG` (resolve relative to `worktree`) existing. Rules: no op → raise; squash requires `fresh` with `fresh.worktree.resolve() == worktree.resolve()` and `fresh.head ==` current HEAD, else raise; then run `git [-c commit.gpgsign=false] commit --no-edit` (or `-m message` when given). Never `-a`, `--no-verify`, pathspec, `--allow-empty`. Return the completed process; callers keep their own returncode handling.
  - `__all__` per the charter convention.
- **Steps**: write the module; keep each function ≤ 15 complexity (`_detect_op`, `_git_path`, `_gpg_prefix`).
- **Tests** — `tests/git_ops/test_merge_conclusion_owner_unit.py` (`unit`, `fast`, no subprocess): argv validation of `run_committing_op` for each refused flag (assert raised before `subprocess.run` is called — monkeypatch `subprocess.run` to fail the test if invoked); `_gpg_prefix(True/False)`; `FreshWorktree` is frozen.
  `tests/git_ops/test_merge_conclusion_owner.py` (`git_repo`, `non_sandbox`; module-level fixture: `monkeypatch` deletes every `GIT_*` and `SPEC_KITTY_*` env var, sets `SPEC_KITTY_NO_UPGRADE_CHECK=1`, `HOME`/`XDG_CONFIG_HOME` under `tmp_path`, `GIT_CONFIG_NOSYSTEM=1`, local `user.name/email`, `git init -b work` — never `main`, so no protected-branch policy interferes). Each test asserts behaviour, not shape:
  1. `conclude` with no op in progress → `MergeConclusionRefused`; `git rev-list --count HEAD` unchanged. (Kills a mutant that commits when nothing is in progress.)
  2. Conflicted merge resolved and staged → `conclude(message=None)` → exit 0, HEAD has 2 parents, subject equals the `-m` given to the merge (fact 1). With `message="X"` → subject `X`. (Kills message-dropping and parent-losing mutants.)
  3. Squash in a fresh worktree (`git worktree add --detach <tmp> work`, `mint`, `merge --squash side`) → `conclude(fresh=proof, message="feat(side): squash merge of mission")` → one parent, tree contains the squashed file.
  4. Squash without `fresh` → refused; SQUASH_MSG still present, HEAD unchanged.
  5. Proof minted, then HEAD moved (an extra commit) → refused (kills a mutant that skips the HEAD check). Proof from worktree A used in worktree B → refused.
  6. `mint_fresh_worktree` on the primary checkout → refused (not linked); on a linked worktree with an unrelated staged file → refused naming that file (fact 5: this is what keeps a squash from sweeping it).
  7. Committing merge via `run_committing_op` with an unrelated staged file → non-zero returncode, the file is still staged (`git diff --cached --name-only` contains it), no new commit (fact 4). Same for `revert` (fact 6). These pin the reliance on git's guard; if a git upgrade ever changes it, these go red.
  8. A rejecting `pre-commit` hook that appends to `tmp_path/hook.calls` and exits 1: `conclude` → non-zero returncode, `hook.calls` has exactly one line, MERGE_HEAD still present (caller's abort path still works), no commit. (Kills a mutant that adds `--no-verify` or retries.)
  9. Signing: set local `commit.gpgsign=true` and `gpg.program=/bin/false`; `conclude(disable_gpgsign=True)` succeeds, `conclude(disable_gpgsign=False)` fails. Same pair for `run_committing_op`. (Pins that the allocator's unsigned-vs-signed difference is plumbed, not hard-coded.)
- **Files**: owner module + two test modules.
- **Validation**: both modules green; `ruff`/`mypy` clean on the owner.

### Subtask T025 – Route `lanes/auto_rebase.py` and `lanes/consolidation.py`

- **Purpose**: the hot consolidation paths go through the owner with byte-identical outcomes.
- **Steps**:
  1. `auto_rebase.py:917-920`: replace with `conclude_in_progress_op(worktree_path, env=_make_merge_env(), message=message)` inside `try/except MergeConclusionRefused as exc:` → `return _abort_with_failure(worktree_path, lane_id, classifications, f"merge commit failed: {exc}")`. The returncode branch `:921-926` stays (same text). `record_tip` (`:931-933`) unchanged.
  2. `auto_rebase.py:1005-1015`: keep the `_merge_head_exists` guard (`:1005`); replace the `_run` commit with `conclude_in_progress_op(worktree_path, env=_make_merge_env())`; same failure text. `_run` (`:156-167`) builds env with `_make_merge_env()` — pass the same.
  3. `consolidation.py:843-849` (`_preserve_target_newer_planning_artifacts`): argv becomes `["git","-c","commit.gpgsign=false","commit","--amend","--only","--no-edit","--allow-empty","--",*restored]` (fact 7). This is path-scoped, so the gate accepts it without the owner; cite C-005's exception wording ("the restored-bookkeeping amend in a consolidation worktree (`commit --amend --only -- <restored>`)") in a one-line comment. The restored paths were already staged at `:826-836`; `--only` takes their worktree content, which equals what was staged.
  4. `consolidation.py:1013`: `return _conclude_ok(worktree, env)` where a small local helper calls `conclude_in_progress_op(worktree, env=env)` and returns `result.returncode == 0`, returning `False` on `MergeConclusionRefused` (the docstring `:993-1006` promises "otherwise the merge is left in progress for the caller's existing abort path" — keep that contract; update the docstring's `git commit --no-edit` wording to name the owner).
  5. `consolidation.py:1266-1274` + `:1333-1346`: in `_merge_branch_into`, right after the `worktree add --detach` succeeds and only for `MergeStrategy.SQUASH`, `fresh = mint_fresh_worktree(tmp_path, _env)`; at the squash commit, `result = conclude_in_progress_op(tmp_path, env=_env, message=f"feat({source_branch}): squash merge of mission", fresh=fresh)`. The `returncode != 0` raise `:1345-1346` stays verbatim. A `MergeConclusionRefused` propagates as the `RuntimeError` it is (callers already treat `RuntimeError` as merge failure; the ExitStack still removes the worktree).
  6. `consolidation.py:1410-1416`: `result = run_committing_op(tmp_path, "merge", [source_branch, "--no-edit", "-m", f"Merge {source_branch} into {target_branch}"], env=_with_meta_two_way(_env) if meta_two_way else _env, disable_gpgsign=False)` — `disable_gpgsign=False` because the original argv has no `-c commit.gpgsign=false`. Everything after (`:1420` target-owned resolution, `:1422` abort) unchanged.
  7. `test_merge_pipeline_ratchets.py` checks only `subprocess.run` calls that remain in `consolidation.py`; the owner calls are not `subprocess.run` there and carry `env=` explicitly — confirm the ratchet stays green and that no `os.environ` read was added.
- **Files**: `lanes/auto_rebase.py`, `lanes/consolidation.py`.
- **Validation**: `pytest tests/lanes/test_auto_rebase_additive.py tests/lanes/test_auto_rebase_target_owned.py tests/lanes/test_auto_rebase_managed_artifact_recognition.py tests/lanes/test_target_owned_merge_sites.py tests/lanes/test_squash_seam_reconciliation.py tests/lanes/test_merge.py tests/consolidation/test_squash_target_newer_planning_3942.py tests/consolidation/test_squash_reconcilers_2709.py tests/consolidation/test_issue_2709_squash_provenance.py tests/architectural/test_merge_pipeline_ratchets.py -q` green and unchanged.

### Subtask T026 – Route `worktree_allocator.py`, `coherence.py`, `agent/workflow.py`

- **Purpose**: drain the remaining census hits.
- **Steps**:
  1. `worktree_allocator.py:1426-1440`: `merge = run_committing_op(worktree_path, "merge", ["--no-edit", "-m", f"Merge recorded planning-artifact commit into {lane_id} (FR-009)", planning_commit_sha], env=env, disable_gpgsign=False)` inside the same `with _ephemeral_merge_driver_activation(repo_root):` block (`:1425`). The `returncode` branch and `merge --abort` (`:1455`) unchanged.
  2. `worktree_allocator.py:1549-1556`: replace with the owner's conclude, `disable_gpgsign=False` (the original never disabled signing — preserve it), returning `result.returncode == 0`, `False` on `MergeConclusionRefused`. Keep the try/except structure `:1541-1548` around the resolvers.
  3. `worktree_allocator.py:1645-1658` (`_merge_dependency_lane_tips`): `run_committing_op(worktree_path, "merge", ["--no-edit", "-m", f"Merge dependency lane {dep_lane.lane_id} into {lane.lane_id}", dep_branch], env=env, disable_gpgsign=False)`; the `_auto_resolve_dependency_merge` / abort path (`:1660-1670`) unchanged.
  4. `coherence.py:735-741` (`_revert_recorded_sha`): git's `-C <coord_worktree>` becomes `cwd=coord_worktree` in the owner — equivalent for a non-bare worktree; `run_committing_op(coord_worktree, "revert", ["--no-edit", sha], env=env, disable_gpgsign=False)`. `revert --abort` (`:744-750`) is not a hit and stays. Respect the module's function-local import rule documented at `coherence.py:18` (import the owner inside the function if the module-top import would create a cycle — check `python -c "import specify_cli.coordination.coherence"` both ways).
  5. `agent/workflow.py:661-672` (`_revert_coordination_commit`): `run_committing_op(Path(receipt.worktree_root), "revert", ["--no-edit", receipt.commit_sha], env=None, disable_gpgsign=True)`; the `RuntimeError` text at `:673-677` unchanged. `env=None` preserves today's inherited environment.
  6. Rerun the gate: `test_no_sweeping_or_hook_bypassing_commit_outside_the_owner` is now GREEN with no allowlist (only the two canonical owners exempt by symbol). Commit: `fix(5443): route merge conclusions through one owner; commit-scope gate starts empty`.
- **Files**: the three source files.
- **Validation**: `pytest tests/lanes/test_worktree_allocator.py tests/lanes/test_worktree_allocator_merge_env.py tests/lanes/test_worktree_allocator_target_owned.py tests/lanes/test_worktree_allocator_merge_driver_selfheal.py tests/lanes/test_worktree_allocator_atomicity.py tests/coordination/test_coherence.py tests/coordination/test_coherence_integrity.py tests/architectural/test_coord_rollback_coherence_guard.py tests/architectural/test_workflow_coherence.py -q` green and unchanged; grep the tests for any monkeypatch of `subprocess.run` that asserted the old argv (e.g. `rg -n '"revert", "--no-edit"|"merge", "--no-edit"' tests/`) and confirm none broke (if one did, it pinned shape, not behaviour — report it before touching it; it is not in `owned_files`).

### Subtask T027 – Behaviour-preservation tests for the routed sites

- **Purpose**: the gate proves routing; these prove the routed paths still produce the same commits (a mutant that routes correctly but drops the message, the second parent or the signing flag must fail).
- **Steps**: create `tests/lanes/test_merge_conclusion_routing.py` (`git_repo`, `non_sandbox` — no `regression` marker: these are behaviour-preservation tests, green on the base and after, not issue reproductions (review minor 15); same env-scrub fixture as T024 — import it from a local helper in the module, do not add a conftest). Drive each through its existing entry function, not the owner:
  1. `consolidation._merge_branch_into(..., strategy=MergeStrategy.SQUASH)` on a two-branch fixture: target advances by exactly one commit whose subject is `feat(<src>): squash merge of mission`, one parent, tree = target tree + source changes; an unrelated file staged in the operator's primary checkout before the call is still staged and absent from the commit.
  2. `_merge_branch_into(..., strategy=MergeStrategy.MERGE)`: subject `Merge <src> into <tgt>`, two parents.
  3. `consolidation._complete_merge_after_target_owned_resolution` on a merge whose only conflict is a target-owned path (reuse the fixture shape of `tests/lanes/test_target_owned_merge_sites.py:203`): returns `True`, HEAD has two parents, MERGE_HEAD gone; with a genuine conflict left: returns `False`, MERGE_HEAD still present (`:216` shape).
  4. `_preserve_target_newer_planning_artifacts` with one restored path and an extra unrelated staged path in the temp worktree: the amended commit contains the restored path, not the unrelated one, which stays staged (fact 7).
  5. `coherence._revert_recorded_sha`: returns `None`, HEAD subject starts with `Revert "`; with an unrelated staged file → returns a diagnostic, no new commit, file still staged.
  6. `workflow._revert_coordination_commit` on a receipt pointing at HEAD: HEAD subject `Revert "…"`; `commit.gpgsign=true` + `gpg.program=/bin/false` still succeeds (signing disabled as before).
  7. `worktree_allocator._merge_dependency_lane_tips` (or the narrowest public path that reaches `:1645`): merge commit subject `Merge dependency lane <dep> into <lane>`; with `commit.gpgsign=true` and a failing `gpg.program` the merge FAILS exactly as it did on the planning base (signing honoured — proves `disable_gpgsign=False` was kept). If reaching it needs heavy lane scaffolding, test `run_committing_op` with the same argv instead and say so in the Activity Log.
- **Files**: the new test module.
- **Validation**: green on the fix commit; run it once on the T023 red commit too — it must be green there as well (it pins unchanged behaviour), record both runs.

### Subtask T028 – Verification and closeout

- **Steps**:
  1. Targeted runs only (no full suites): the gate, both owner modules, the routing module, the suites listed in T025/T026, plus `tests/architectural/test_no_legacy_terminology.py`, `tests/architectural/test_git_path_listing_owner.py` (the owner calls `kernel.git` for status; it must not build a path-listing argv itself), `tests/architectural/test_safe_commit_import_boundary.py`.
  2. `ruff check` + `ruff format --check --force-exclude` on every touched file; `mypy src/specify_cli/git/merge_conclusion.py src/specify_cli/lanes/consolidation.py src/specify_cli/lanes/auto_rebase.py src/specify_cli/lanes/worktree_allocator.py src/specify_cli/coordination/coherence.py`.
  3. Self-mutation spot checks (do not commit): (a) delete the `CANONICAL_OWNERS` exemption in `census()` → the real-tree test fails on both owners (merge-conclusion functions and `safe_commit`'s temp-index commit); (a2) widen the exemption to the whole `commit_helpers.py` file → case (d) of `test_canonical_owners_are_the_only_exemptions` fails; (b) re-add `"--no-verify"` to any routed call → fails; (c) remove the HEAD check in `conclude` → T024 case 5 fails. Record each in the Activity Log.
  4. `git diff --stat <base> -- tests/architectural/_baselines.yaml` is empty (no allowlist anywhere).
  5. Tracer entries (`spec-kitty agent tracer-append --mission upgrade-migration-commit-scope-01M4AKVE --category approach|design-decisions|tooling-friction --actor <agent>`) for the owner design and the hook/signing facts; `spec-kitty agent tasks mark-status T023 … T028 --status done --mission upgrade-migration-commit-scope-01M4AKVE`.
- **Validation**: the lane holds the red gate commit before the routing commit(s).

## Test Strategy

```bash
# red on the base (only the real-tree test fails, listing the 11 sites), green at the end
.venv/bin/python -m pytest tests/architectural/test_commit_scope_owner.py -q
.venv/bin/python -m pytest tests/git_ops/test_merge_conclusion_owner_unit.py tests/git_ops/test_merge_conclusion_owner.py tests/lanes/test_merge_conclusion_routing.py -q
# neighbours that must not move
.venv/bin/python -m pytest tests/lanes/test_auto_rebase_additive.py tests/lanes/test_auto_rebase_target_owned.py \
  tests/lanes/test_auto_rebase_managed_artifact_recognition.py tests/lanes/test_target_owned_merge_sites.py \
  tests/lanes/test_squash_seam_reconciliation.py tests/lanes/test_merge.py tests/lanes/test_worktree_allocator.py \
  tests/lanes/test_worktree_allocator_merge_env.py tests/lanes/test_worktree_allocator_target_owned.py \
  tests/consolidation/test_squash_target_newer_planning_3942.py tests/consolidation/test_squash_reconcilers_2709.py \
  tests/coordination/test_coherence.py tests/architectural/test_coord_rollback_coherence_guard.py -q
.venv/bin/python -m pytest tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_git_path_listing_owner.py \
  tests/architectural/test_no_legacy_terminology.py tests/architectural/test_workflow_coherence.py -q
.venv/bin/ruff check <touched files>; .venv/bin/ruff format --check --force-exclude <touched files>
.venv/bin/mypy src/specify_cli/git/merge_conclusion.py src/specify_cli/lanes/consolidation.py src/specify_cli/lanes/auto_rebase.py
```

Markers: `unit`+`fast` only for the no-subprocess module; `git_repo`+`non_sandbox` for real git (including the routing module — no `regression`, it pins unchanged behaviour, not a fixed defect); `architectural` on the gate. No `p0_repro` in this WP (that marker is reserved for #5443's reproduction in WP01).

## Risks & Mitigations

- **Hook semantics drift** (fact 8): converting a committing merge into `--no-commit` + `git commit` would run operator `pre-commit` hooks on lane merges and fire the lane-tip `post-commit` hook where `post-merge` ran before. Mitigation: committing merges/reverts keep their exact argv and are only *run by* the owner; `conclude` is used only where the code already concluded with `git commit`.
- **Weakening git's own guard** (fact 6): never route a committing revert/cherry-pick through `--no-commit`; T024 case 7 pins git's refusal.
- **Squash sweep** (fact 5): only a minted `FreshWorktree` can conclude a squash; T024 cases 4-6.
- **Signing behaviour**: two sites never disabled signing (`consolidation.py:1411`, `worktree_allocator.py:1429/1550/1647`, `coherence.py:736`); `disable_gpgsign` is explicit at every call; T024 case 9 / T027 case 7.
- **Env authority ratchet**: owner takes `env` explicitly; no `os.environ` in `consolidation.py`.
- **Census blind spots**: documented; planted cases cover constant indirection, the `_git_in` runner form and the varargs `run_git(cwd, *args)` form; plumbing `commit-tree`/`update-ref` documented as outside the gate; the follow-up issue is filed at closeout (C-003).
- **Exemption creep**: exactly two owners by symbol (Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ`); a third owner, a file-wide exemption or an allowlist entry is a decision change, not an implementation choice — stop and report.
- **Unowned extra sites**: `agent/workflow.py:661` was outside lens B's list and is owned here; if your base census shows anything else (e.g. a site added on `main` after 5ee323802), stop and report rather than editing an unowned file.
- **Import cycles** (`coherence.py:18` function-local import rule; `specify_cli.git` importing `kernel.git` only): verify with a bare `import` of each touched module.

## Review Guidance

- Verify the red gate commit precedes the routing commit and its recorded red output lists exactly the 11 sites (and nothing from WP01/WP04/WP06 files).
- Verify the gate has no allowlist, no `_baselines.yaml` change, a scanned-file floor, one planted case per form (including the varargs runner form) with an exact `kind` assertion, negative controls, and positive controls for BOTH canonical owners; the exemption is keyed by symbol (`safe_commit`; `run_committing_op`/`conclude_in_progress_op`) and a non-owner function in `commit_helpers.py` is still scanned.
- Read each routed call next to its origin/main line: same message, same `-m`/`--no-edit`, same env object, same signing behaviour, same failure text and abort path.
- Verify the owner never emits `--no-verify`, `-a`, a pathspec during a conclusion, or `--no-commit` for a revert; that `conclude` refuses with no op in progress and refuses a squash without a matching `FreshWorktree`.
- Confirm T027 is green on both the red commit and the fix commit (behaviour unchanged).

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Decision `01M4B6FZNNSTP6DPN2AAEDEQHZ` (not reopened; review M8): the gate exempts exactly two canonical owners by symbol — `safe_commit` (`git/commit_helpers.py`, including WP07's index-deletion commit under a temporary index) and the merge-conclusion owner (`run_committing_op`, `conclude_in_progress_op`) — no allowlist; WP05 now depends on WP07 as well as WP01/WP04/WP06. Post-tasks review folded: minor 14 (varargs `run_git(cwd, *args)` extraction, planted case, `implement_claim.py:210` negative control, `commit-tree`/`update-ref` documented outside the gate with a follow-up), minor 15 (`regression` dropped from T027), NOTE 5 (site rescan: `workflow.py:666` revert routed here; no uncovered site). Cited lines re-verified on `origin/main` 5ee323802.
- 2026-10-07 – planner-priti – Analysis fold: AN-INC-004 (gate wording: every sweeping, pathspec-less or hook-bypassing commit route; no allowlist); AN-INC-002 (C-005 exception wording cited for the `consolidation.py` amend); AN-UND-004 (plumbing follow-up filed at closeout); AN-COV-002 (C-004 added; C-005 added since the WP cites it).
- 2026-10-07 – orchestrator (recording implementer evidence) – Lane-e on 7a022c203 (deps WP01, WP04, WP06, WP07 merged). Commits:
  - 22b10e333: red gate. 4 failed / 47 passed; the gate lists exactly the 11 sites (workflow.py:662 and coherence.py:736 committing-revert; auto_rebase.py:918 and :1007; consolidation.py:844 amend, :1013, :1333, :1411 merge; worktree_allocator.py:1427 merge, :1550, :1645 merge). The other 3 failures are owner positive controls (owner absent).
  - ce1a7ec1d: owner.
  - cc6604627: routing tests (the amend red on base).
  - 34bce06b4: routing; the gate starts empty.
  - fce8b2148: bare `--` case.
  - 333254acb: clock, dead-symbol and tmp-path gates.
  - be570f797: recorded out-of-map edit stubbing the fresh-worktree proof in the #5460 squash opt-out unit test, which fakes all git output (orchestrator decision).
- GREEN: lanes/consolidation/coordination/git_ops + review-lane gate 4163 passed / 0 failed (base 4098 / 0); `tests/architectural` 4268 passed before the 5 own-gate fixes, which re-ran green (138 passed). 28/28 mutants killed. No existing test edited besides the recorded stub. Follow-up issue (plumbing `commit-tree`/`update-ref` outside the gate) is to be filed at closeout.
