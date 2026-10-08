---
work_package_id: WP06
title: Remove the sweeping commit helpers and stop shipping sweeping staging text
dependencies: []
requirement_refs:
- FR-014
- FR-015
- NFR-002
- C-004
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T13:24:55.358838+00:00'
subtasks:
- T029
- T030
- T031
- T032
- T033
phase: Phase 2 - Close the class
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/architectural/test_shipped_text_path_scoped_commits.py
- tests/git_ops/test_sweeping_helpers_removed.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/core/vcs/git.py
- src/specify_cli/core/vcs/protocol.py
- src/specify_cli/core/git_ops.py
- src/specify_cli/core/__init__.py
- tests/git_ops/test_git.py
- tests/git_ops/test_vcs_integration.py
- tests/git_ops/test_git_ops.py
- tests/git_ops/test_sweeping_helpers_removed.py
- tests/architectural/test_shipped_text_path_scoped_commits.py
- src/charter/offering/skills/spec-kitty-implement-review/SKILL.md
- src/charter/offering/skills/spec-kitty-implement-review/references/rejection-loop-checklist.md
- src/charter/offering/skills/spec-kitty-git-workflow/SKILL.md
- src/charter/offering/skills/spec-kitty-git-workflow/references/git-operations-matrix.md
- src/charter/offering/skills/spec-kitty-charter-doctrine/SKILL.md
- packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md
- packs/built-in/toolguides/git-worktree-pr-workflow.toolguide.yaml
- packs/built-in/pack-manifest.yaml
- packs/built-in/toolguide.graph.yaml
- docs/api/upgrade-lifecycle.md
- docs/guides/how-to/installation/upgrade-project.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5443'
---

# Work Package Prompt: WP06 – Remove the sweeping commit helpers and stop shipping sweeping staging text

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

- **FR-014**: the unused sweeping helpers are gone. `GitVCS.commit(workspace_path, message, paths=None)` (stages `git add -A` when `paths` is falsy, then a pathspec-less `git commit`) and its `VCSProtocol.commit` declaration are deleted; `init_git_repo` (`git init` + `git add .` + pathspec-less commit) is deleted from `core/git_ops.py` and from the `specify_cli.core` re-export. Nothing in `src/` can route back into a sweeping commit through them.
- **FR-015**: shipped skills, the built-in git toolguide and the two upgrade docs stop recommending `git add -A`, `git add .`, `git add --all`, `git add -u` or a directory add. Replacement text teaches path-scoped commits (`spec-kitty safe-commit <paths>` or `git add -- <explicit files>`), consistent with Directive 033 (Targeted Staging Policy).
- **Enabler for WP05**: the gate `tests/architectural/test_commit_scope_owner.py` (WP05) starts empty — no allowlist, only the two canonical owners exempt by symbol; it can only pass on `src/` once `core/vcs/git.py:640` (`add -A`), `core/vcs/git.py:658` (pathspec-less commit), `core/git_ops.py:157` (`add .`) and `core/git_ops.py:158-162` (pathspec-less commit) are gone. Do not wait for WP05; WP05 depends on this WP.
- Red-first (C-004): the `regression` text check and the helper-removal tests land in a commit before the edits and are red there.

## Context & Constraints

- Spec: `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md` (User Story 7, FR-014, FR-015, C-003); plan IC-06; squad evidence `<operator-local squad notes>` ("Dead helpers CONFIRMED zero product callers → delete (paths-required insufficient: still bare commit)"; "Shipped text … in scope; others follow-up").
- Decision `01M4AY23FFY71BJA2JRG39SMB6` (skill text in scope). C-003 keeps OTHER docs that show `git add .` for brand-new repositories out of scope: the docs part of this WP is exactly the two upgrade docs below, nothing else under `docs/`.
- Code reference = `origin/main` 5ee323802 (read with `git show origin/main:<path>`). Seams:
  - `src/specify_cli/core/vcs/git.py:612-673` `GitVCS.commit` — `:631-637` per-path `git add <path>` (no `--`), `:638-643` `git add -A` fallback, `:646-654` `diff --cached --quiet`, `:657-664` `git commit -m` without pathspec (commits every staged entry, including the operator's).
  - `src/specify_cli/core/vcs/protocol.py:202-224` `VCSProtocol.commit` declaration ("paths: Specific paths to commit (None = all)").
  - `src/specify_cli/core/git_ops.py:141-172` `init_git_repo` (`:153` `os.chdir`, `:156` `git init`, `:157` `git add .`, `:158-162` pathspec-less commit); `:524` its `__all__` entry.
  - `src/specify_cli/core/__init__.py:25` (import) and `:60` (`__all__` entry).
- Product callers: none. Verified on `origin/main`: `git grep -nw init_git_repo -- src packs scripts` hits only the definition, the two `__all__` entries and the core re-export, plus a prose mention in `src/charter/offering/skills/spec-kitty-mission-review/SKILL.md:277` (a `grep` pattern teaching reviewers to look for `init_git_repo` in diffs; leave it, it names the hazard and is not a call). `git grep -nE "(vcs|_vcs|git_vcs)\.commit\("` hits only tests. Re-run both greps on your lane before deleting; if a product caller appeared since 5ee323802, stop and report it in the Activity Log instead of deleting.
- Test callers (all yours to edit):
  - `tests/git_ops/test_git.py:342-349` `test_commit`, `:351-356` `test_commit_returns_none_when_nothing_to_commit`, `:358-385` `test_commit_specific_paths`, `:558-566` `test_commit_with_empty_message` — delete these four (they pin the deleted method). Keep every other test in the file.
  - `tests/git_ops/test_vcs_integration.py:196-206` `test_commit_changes` — delete; `:282-283` (a workflow test that commits in a workspace via `vcs.commit`) — replace that one call with explicit subprocess git: `git -C <ws> add -- feature_code.py` + `git -C <ws> -c commit.gpgsign=false commit -m "Implement feature" -- feature_code.py`, then keep the rest of the test unchanged.
  - `tests/git_ops/test_git_ops.py:11` (import) and `:70-80` `test_git_repo_lifecycle` — rewrite the setup with `subprocess.run(["git", "init", ...])` and assert `is_git_repo` / `get_current_branch` as today; drop `init_git_repo` from the import.
  - Many test modules define their OWN `init_git_repo` / `_init_git_repo` helper (`tests/specify_cli/charter_preflight/_fixtures.py:19`, `tests/runtime/_next_mission_scaffold.py:46`, …). They do not import the product function; do not touch them.
  - `tests/git_ops/test_detection.py:110` asserts `isinstance(vcs, VCSProtocol)` (runtime-checkable Protocol). Removing `commit` from BOTH the protocol and `GitVCS` keeps it green; removing it from only one side changes nothing for `isinstance` but leaves a lie in the protocol — remove both.
- Shipped text sites on `origin/main` (exact lines):
  - `src/charter/offering/skills/spec-kitty-implement-review/SKILL.md:301` — `9. Commit: git add -A && git commit -m "feat(WP##): <description>"` (inside a dispatched-agent prompt string).
  - `src/charter/offering/skills/spec-kitty-implement-review/SKILL.md:836` — `git add -A && git commit -m "merge: resolve lane-<X> conflicts"` (conflict resolution during a lane merge).
  - `src/charter/offering/skills/spec-kitty-git-workflow/references/git-operations-matrix.md:38` — `| \`git add . && git rebase --continue\` | During rebase conflict resolution | Complete rebase |`.
  - `packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md:32` — `git add -A && git commit -m "wip: checkpoint before rebase"` (contradicts Directive 033 in the same pack).
  - `docs/api/upgrade-lifecycle.md:130` and `docs/guides/how-to/installation/upgrade-project.md:105` — `git add .kittify/ .claude/ .agents/skills/` (directory adds; `.claude/` and `.agents/skills/` are gitignored since the 3.2.5 backfill, so the line is also wrong).
  - Directory adds found while grounding this prompt, also shipped skills and therefore in FR-015's literal scope: `src/charter/offering/skills/spec-kitty-implement-review/references/rejection-loop-checklist.md:9` (`git add kitty-specs/ && git commit …`), `src/charter/offering/skills/spec-kitty-git-workflow/SKILL.md:152` (`git add src/ tests/`), `src/charter/offering/skills/spec-kitty-charter-doctrine/SKILL.md:204` (`git add .kittify/doctrine/ .kittify/charter/provenance/ …`). The plan named only the first six; the text check below scans the whole shipped-skills tree, so these three must be fixed too (recorded as a planning ambiguity; if the reviewer rules them out, narrow the scan, never allowlist).
- Directive 033 (`packs/built-in/directives/033-targeted-staging-policy.directive.yaml`): "Use explicit file paths in staging commands rather than `git add -A`, `git add .`, or `git add --all`"; "Verify staged content with `git diff --staged --name-only` before committing". Replacement text must satisfy it.
- Generated/pinned files:
  - `packs/built-in/pack-manifest.yaml` is GENERATED (never hand-edit; `tests/architectural/test_pack_manifest_no_author_edit.py:174-226` regenerates and fails on a stale committed manifest: "run `spec-kitty doctrine regenerate-graph` and commit the result"). The manifest's `content_hash` for `git-worktree-pr-workflow` (`pack-manifest.yaml:1310-1314`) is computed over the toolguide YAML (`toolguides/git-worktree-pr-workflow.toolguide.yaml`), not over the `.md` it points at (`guide_path`). Bump that YAML's `last_updated` (`:19`, today `"2026-07-22"`) to the edit date so the toolguide records the change, then regenerate (`spec-kitty doctrine regenerate-graph`, `src/specify_cli/cli/commands/doctrine.py:251`); commit whatever it rewrites (expected: the manifest hash line; possibly `toolguide.graph.yaml`). If it rewrites any other file, stop and report.
  - `tests/architectural/test_git_matrix_paths_resolve.py` parses the matrix's "Python-Executed Git Commands" table; you edit only the "Agent-Expected Git Commands" table (`:31-39`), keep the table shape.
  - `tests/architectural/test_builtin_pack_provenance_ratchet.py`: shipped pack text must not gain `#1234`/`WP01`/`FR-001` tokens or repo-local paths — write the toolguide replacement without issue numbers or `src/` paths.
  - Terminology ratchet `tests/architectural/test_no_legacy_terminology.py`: no "feature" for missions; avoid the phrases "lane merge", "lane-merge", "merge the lanes", "merging lanes" in NEW prose outside baselined files (the existing SKILL.md text around `:826-836` may already be baselined — do not add new occurrences).
- PR #5856 adjacency (C-001, review NOTE 2): #5856 also edits `docs/api/upgrade-lifecycle.md` `:57-63` (the finalizer paragraph). Edit only the commit block at `:127-132` (the `git add .kittify/ .claude/ .agents/skills/` line at `:130`); leave `:57-63` byte-identical so the two PRs merge without conflict.
- Ownership: only `owned_files`. Do not touch `docs/changelog/CHANGELOG.md` (WP08), the commit gate (WP05), `git/commit_helpers.py` or the safe-commit CLI (WP07). Generated consumer copies of skills (a developer's `.claude/skills/…`, `.agents/skills/…`) are not tracked in this repository (verified: no `^\.(claude|agents)/skills/` paths in `origin/main`); they refresh from `src/charter/offering/skills/` through the managed-skill path on upgrade/startup — nothing to edit here.
- Charter: ATDD-first (C-011): red commit first; targeted test runs only (CI owns full suites); ruff-format touched Python files; complexity ≤ 15; behavioural assertions only (no shape pins).

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP06 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T029 – Red-first shipped-text check (`regression`)

- **Purpose**: pin FR-015 so the text cannot regress and the edit is proven (C-004).
- **Steps**:
  1. Create `tests/architectural/test_shipped_text_path_scoped_commits.py` with `pytestmark = [pytest.mark.architectural, pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]` (pure file reads, no subprocess). If `test_ci_corpus_trigger_completeness.py` requires a `corpus` marker for modules that read `packs/built-in/`, add `pytest.mark.corpus` and update nothing else (if that test needs a registry edit in a file you do not own, read `packs/built-in/` through a plain repo-relative path instead and note the choice).
  2. Scanned set (module constant, repo-relative):
     - every `*.md` under `src/charter/offering/skills/` (recursive);
     - `packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md`;
     - `docs/api/upgrade-lifecycle.md`, `docs/guides/how-to/installation/upgrade-project.md`.
     Assert a floor: at least 20 skill files and all four named files exist (kills the "glob matched nothing" mutant — an empty scan passes vacuously).
  3. Detector `find_sweeping_adds(text: str) -> list[tuple[int, str]]` (1-based line, offending command):
     - find each occurrence of `git add` (word boundary, also after `&&`, `;`, `|`, a backtick, `$ `, a table pipe);
     - its argument list = the tokens after `add` up to the first `&&`, `||`, `;`, `|`, backtick, `)` or end of line;
     - drop option tokens that are harmless (`--force`, `-f`, `--`, `-p`, `--patch`, `-N`, `--intent-to-add`, `-v`);
     - violation if any token is `-A`, `--all`, `-u`, `--update`, `.`, `./`, `:/`, `*`, or ends with `/` (a directory add), or a token is `-A`/`--all` combined with other flags (`-Av`, `-fA`).
     - Allowed: `git add <files>`, `git add -- <file> …`, `git add path/to/file.py`, placeholders in angle brackets.
     - Known blind spot (document it in the module docstring): a directory named without a trailing slash (`git add kitty-specs`) is indistinguishable from a file in text; reviewers own that case.
  4. Tests:
     - `test_detector_flags_each_sweeping_form` (non-vacuity, parametrised): `git add -A`, `git add --all`, `git add .`, `git add -u`, `git add kitty-specs/`, `git add src/ tests/`, `` `git add . && git rebase --continue` ``, `| \`git add -A\` |`, `cd x && git add -A && git commit -m y` → each yields exactly one hit naming the form. Mutant killed: a detector that only matches `-A` at line start, or drops the table-cell/backtick case.
     - `test_detector_allows_path_scoped_forms`: `git add <files>`, `git add -- src/app.py tests/test_app.py`, `git add --force -- .kittify/metadata.yaml`, `spec-kitty safe-commit src/app.py`, `git add -p src/app.py` → no hits. Mutant killed: a detector that flags every `git add` (would make the real-tree test unpassable for a correct text and push someone to allowlist).
     - `test_shipped_text_teaches_path_scoped_commits`: run the detector over the scanned set; assert the collected `{path: [(line, cmd), …]}` is `{}`; the failure message lists every hit as `path:line: cmd` plus the remedy ("stage explicit files: `spec-kitty safe-commit <paths>` or `git add -- <files>`; Directive 033").
  5. Run on the planning base: the real-tree test must be RED with exactly these hits (paste the list into the Activity Log): implement-review `SKILL.md:301`, `:836`; `rejection-loop-checklist.md:9`; git-workflow `SKILL.md:152`; `git-operations-matrix.md:38`; charter-doctrine `SKILL.md:204`; `GIT_WORKTREE_PR_WORKFLOW.md:32`; `upgrade-lifecycle.md:130`; `upgrade-project.md:105`. If the detector reports additional hits, fix them in T032/T033 (they are in scope by the same rule) and list them; if it misses one of these, the detector is wrong.
- **Files**: `tests/architectural/test_shipped_text_path_scoped_commits.py` (new, ~140 lines).
- **Validation**: the two detector tests green; the real-tree test red for the listed lines only. Commit T029 + T030 together as the red commit: `test(5443): red-first checks for sweeping staging text and helpers`.

### Subtask T030 – Red-first helper-removal tests (`regression`)

- **Purpose**: pin FR-014 behaviourally so the helpers cannot be reintroduced under the same names.
- **Steps**:
  1. Create `tests/git_ops/test_sweeping_helpers_removed.py`, `pytestmark = [pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]` (imports and attribute checks only).
  2. `test_git_vcs_has_no_sweeping_commit`: `from specify_cli.core.vcs.git import GitVCS`; assert `not hasattr(GitVCS, "commit")`. Mutant killed: keeping the method but making `paths` required (lens B: still a pathspec-less `git commit` that sweeps whatever the operator staged).
  3. `test_vcs_protocol_declares_no_commit`: `from specify_cli.core.vcs.protocol import VCSProtocol`; assert `"commit" not in VCSProtocol.__dict__`. Mutant killed: deleting only the implementation (protocol still advertises a commit capability a future backend would implement as a sweep).
  4. `test_core_exports_no_init_git_repo`: `import specify_cli.core as core`, `import specify_cli.core.git_ops as git_ops`; assert `not hasattr(core, "init_git_repo")`, `"init_git_repo" not in core.__all__`, `not hasattr(git_ops, "init_git_repo")`, `"init_git_repo" not in git_ops.__all__`. Mutant killed: removing the function but leaving a stale `__all__` entry (import-star breaks) or the reverse.
  5. Do not add a src-wide grep here — the cross-tree "no sweeping git form in src/" rule is WP05's gate; this module pins only the named symbols.
- **Files**: `tests/git_ops/test_sweeping_helpers_removed.py` (new, ~45 lines).
- **Validation**: all four RED on the planning base (`AssertionError`, not `ImportError` — the modules exist); paste the failing assertion lines into the Activity Log.

### Subtask T031 – Delete `GitVCS.commit`, `VCSProtocol.commit` and `init_git_repo`

- **Purpose**: FR-014; unblocks WP05's empty gate.
- **Steps**:
  1. Re-run the caller greps on your lane (Context bullet "Product callers"). Zero product callers → proceed.
  2. `core/vcs/git.py`: delete `:612-673` (`commit`). Check whether `ChangeInfo` (imported at `:25`) or `get_current_change` remain used elsewhere in the file; keep them if so (they are), remove only imports ruff reports as unused.
  3. `core/vcs/protocol.py`: delete `:202-224` (`commit` + docstring). If the module docstring or a class docstring lists the operations ("commit"), update the list.
  4. `core/git_ops.py`: delete `:141-172` (`init_git_repo`) and its `__all__` entry `:524`. `os` (used only by `os.chdir` at `:153`?) — check with ruff; `_resolve_console`, `escape`, `sanitize_terminal_text`, `ConsoleType` are still used by `run_command` (`:47`, `:79-84`), keep them.
  5. `core/__init__.py`: drop `init_git_repo` from the import at `:25` and the `__all__` entry at `:60`.
  6. Tests you own: delete the four `test_git.py` commit tests and `test_vcs_integration.py:196-206`; rewrite `test_vcs_integration.py:282-283` and `test_git_ops.py:70-80` as described in Context (explicit pathspec git in the test; tests may use plain git, the gate covers `src/` only).
  7. `grep -rn "init_git_repo\|\.commit(" docs/ src/charter/` for documentation of the deleted API (beyond the reviewer grep pattern at `spec-kitty-mission-review/SKILL.md:277`, which stays). If a doc outside your owned files documents `GitVCS.commit`, list it in the Activity Log as a follow-up (do not edit unowned files).
  8. `tests/architectural/dead_symbol_allowlist.yaml` has no entry for either symbol on `origin/main` (only `specify_cli.core.git_ops::BranchResolution`); if the dead-symbol test complains after the deletion, report it — do not edit the allowlist.
- **Files**: the four `src/specify_cli/core/` files; `tests/git_ops/test_git.py`, `test_vcs_integration.py`, `test_git_ops.py`.
- **Validation**: T030 module green; `pytest tests/git_ops/test_git.py tests/git_ops/test_vcs_integration.py tests/git_ops/test_git_ops.py tests/git_ops/test_detection.py -q` green; `ruff check` + `mypy` clean on the four source files. Note for WP05's reviewer: after this subtask `git grep -nE '"add", *"(-A|\.)"' -- src/specify_cli/core` is empty.

### Subtask T032 – Shipped skill and toolguide text; regenerate the pack manifest

- **Purpose**: FR-015 for shipped agent guidance; Directive 033 consistency.
- **Steps** (replacement wording is guidance; keep each file's voice and structure):
  1. `spec-kitty-implement-review/SKILL.md:301` (step 9 of the dispatched-agent prompt): `9. Commit only your deliverables: spec-kitty safe-commit <each file you changed> -m "feat(WP##): <description>"` — check the real `safe-commit` CLI flags first (`spec-kitty safe-commit --help`; `src/specify_cli/cli/commands/safe_commit_cmd.py`) and use the actual message option; if the prompt string context makes a CLI call awkward, use `git add -- <files you changed> && git diff --staged --name-only && git commit -m "…"`. Keep steps 10-11 unchanged.
  2. `SKILL.md:836` (conflict resolution during a merge): git refuses a pathspec while concluding a merge, so do NOT write `git commit -- <paths>`. Teach: `git add -- <each resolved file>` (list them from `git diff --name-only --diff-filter=U` before resolving), then `git commit --no-edit`. This is the merge-conclusion case WP05 routes in product code; in agent text it is a manual conclusion and is fine as long as the staging is explicit.
  3. `references/rejection-loop-checklist.md:9`: `git add kitty-specs/` → name the files the review feedback changed, e.g. `spec-kitty safe-commit kitty-specs/<mission>/tasks/WP##-<slug>.md -m "chore: …"` (verify the status-artifact files actually written in that step; prefer the files the checklist item refers to).
  4. `spec-kitty-git-workflow/SKILL.md:152`: `git add src/ tests/` → `git add -- src/auth/middleware.py tests/test_auth_middleware.py` (illustrative explicit files, matching the example's "auth middleware" commit message).
  5. `spec-kitty-git-workflow/references/git-operations-matrix.md:38`: `| \`git add -- <resolved files> && git rebase --continue\` | During rebase conflict resolution | Complete rebase with only the files you resolved |`. Keep the table's three columns.
  6. `spec-kitty-charter-doctrine/SKILL.md:204`: replace the directory adds with the files the step produced: tell the operator to list them (`git status --porcelain -- .kittify/doctrine .kittify/charter/provenance`) and stage them by name, or use `spec-kitty safe-commit <those paths>`. Do not invent file names the synthesis does not write; if the generated file set is variable, `spec-kitty safe-commit` with the explicit paths printed by `git status` is the teaching.
  7. `packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md:31-32` ("Prefer: a worktree-local commit"): `git add -- <files you changed>` then `git commit -m "wip: checkpoint before rebase"`; add one sentence: stage only named files — a blanket add sweeps unrelated work and secrets (Directive 033). No issue numbers, no `src/` paths (provenance ratchet).
  8. Bump `last_updated` in `packs/built-in/toolguides/git-worktree-pr-workflow.toolguide.yaml:19`; run `.venv/bin/spec-kitty doctrine regenerate-graph` from the lane worktree (make sure the `spec-kitty` you run imports the lane's `src`: `PYTHONPATH=<worktree>/src .venv/bin/python -m specify_cli doctrine regenerate-graph`); `git diff --stat packs/built-in/` must show only the toolguide YAML, `pack-manifest.yaml` and at most `toolguide.graph.yaml`.
  9. Re-run T029's module: the skill/toolguide hits are gone; only the two docs remain red until T033.
- **Files**: the five skill files, the toolguide `.md` + `.yaml`, `pack-manifest.yaml` (generated), possibly `toolguide.graph.yaml` (generated).
- **Validation**: `pytest tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_builtin_pack_provenance_ratchet.py tests/architectural/test_git_matrix_paths_resolve.py tests/architectural/test_no_legacy_terminology.py -q` green.

### Subtask T033 – The two upgrade docs; docs gates; verification

- **Purpose**: FR-015 for the upgrade docs; honest green for the WP.
- **Steps**:
  1. `docs/api/upgrade-lifecycle.md:126-132` and `docs/guides/how-to/installation/upgrade-project.md:102-106`: replace the "Commit the result" block. Content to convey (both docs, each in its own voice): `spec-kitty upgrade` commits the files it changed itself when `auto_commit` is enabled (default), and only those files — your own uncommitted work is left alone; if it reports that its changes were left uncommitted (auto-commit disabled, a hook rejected the commit, or files held for manual review), review with `git status` / `git diff` and stage the listed files by name: `git add -- .kittify/metadata.yaml <other files git status lists>` then `git commit -m "chore: upgrade Spec Kitty project to <version>"`, or `spec-kitty safe-commit <those files> …`. Drop `.claude/` and `.agents/skills/` from the example (gitignored machine-local projections since the 3.2.5 backfill). Describe the behaviour this mission ships (WP01) — do not promise anything WP01 does not do; if unsure about the exact warning wording, paraphrase rather than quote.
  2. Keep the `upgrade-project.md:109` note about `kitty-specs/` unchanged.
  3. Gates: `PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors=0; link WARNINGS acceptable); markdownlint on the two docs and every edited `.md` with the repo config (`.markdownlint-cli2.jsonc`; `npx markdownlint-cli2 <files>` if available, otherwise note it as CI-owned in the Activity Log) — do not exceed any per-file budget; terminology ratchet.
  4. Verification: T029 module fully green; T030 module green; the targeted runs listed in Test Strategy; `ruff check` / `ruff format --check --force-exclude` on touched Python; `mypy src/specify_cli/core/vcs/git.py src/specify_cli/core/vcs/protocol.py src/specify_cli/core/git_ops.py src/specify_cli/core/__init__.py`.
  5. Activity Log: RED output (T029 hit list, T030 failing assertions), GREEN output, the `regenerate-graph` diff stat, follow-ups found (other docs with `git add .` for brand-new repositories stay out of scope per C-003 — list them, do not edit). Then `spec-kitty agent tasks mark-status T029 T030 T031 T032 T033 --status done --mission upgrade-migration-commit-scope-01M4AKVE`.
- **Files**: the two docs.
- **Validation**: all targeted gates green; the lane holds the red commit before the fix commit(s).

## Test Strategy

```bash
# red on the planning base (T029+T030 commit), green at the end
.venv/bin/python -m pytest tests/architectural/test_shipped_text_path_scoped_commits.py tests/git_ops/test_sweeping_helpers_removed.py -q
# neighbours that must stay green
.venv/bin/python -m pytest tests/git_ops/test_git.py tests/git_ops/test_vcs_integration.py tests/git_ops/test_git_ops.py tests/git_ops/test_detection.py -q
.venv/bin/python -m pytest tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_builtin_pack_provenance_ratchet.py \
  tests/architectural/test_git_matrix_paths_resolve.py tests/architectural/test_no_legacy_terminology.py -q
PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/ruff check src/specify_cli/core/vcs/git.py src/specify_cli/core/vcs/protocol.py src/specify_cli/core/git_ops.py src/specify_cli/core/__init__.py \
  tests/architectural/test_shipped_text_path_scoped_commits.py tests/git_ops/test_sweeping_helpers_removed.py
.venv/bin/ruff format --check --force-exclude <same files>
.venv/bin/mypy src/specify_cli/core/vcs/git.py src/specify_cli/core/vcs/protocol.py src/specify_cli/core/git_ops.py src/specify_cli/core/__init__.py
```

No full or heavy suites locally (CI owns them). Markers: both new modules are pure (`unit` + `fast`, plus `regression`; the text module also `architectural`); no `git_repo`/`non_sandbox` needed in this WP.

## Risks & Mitigations

- **Stale pack manifest** → bump the toolguide YAML's `last_updated`, regenerate with `regenerate-graph` from the lane's `src`, never hand-edit `pack-manifest.yaml`; `test_pack_manifest_no_author_edit.py` is the check.
- **Docs freshness / markdownlint budgets** → small, in-place replacements; keep fenced blocks fenced with a language; run `check_docs_freshness.py --ci`; markdownlint on touched files.
- **Replacement text that is itself wrong** → a `git commit -- <paths>` example while concluding a merge (git refuses a pathspec there) — T032 step 2 uses `git add -- <resolved files>` + `git commit --no-edit`; every other example names files or uses `spec-kitty safe-commit <paths>` with the CLI's real flags (verify with `--help`).
- **Detector too broad / too narrow** → the two detector tests pin both directions; the real-tree run on the planning base must reproduce exactly the nine hits listed in T029.
- **Hidden product caller of a deleted helper** (added after 5ee323802) → re-grep before deleting; stop and report instead of rerouting.
- **Scope creep into other docs** (C-003) → only the two upgrade docs under `docs/`; list others as follow-ups.
- **Ownership collision with WP05** → WP05 may want to mention the merge-conclusion owner in the git-operations matrix; this WP owns the matrix file, so WP05 must not edit it (raise a follow-up instead).

## Review Guidance

- Verify the red commit (T029+T030) precedes the deletions and text edits, and that its RED output shows exactly the nine shipped-text hits and four `AssertionError`s (not `ImportError`).
- Verify `git grep -nE '"add", *"(-A|\.)"|"commit", *"-m"' -- src/specify_cli/core` is empty and `git grep -nw init_git_repo -- src` hits only the reviewer grep pattern in `spec-kitty-mission-review/SKILL.md:277`.
- Verify the detector's non-vacuity cases include a table cell, a backtick span and a `cd x && git add -A && …` chain, and that the scanned-set floor is asserted.
- Read every replacement snippet: explicit files or `spec-kitty safe-commit <paths>`; no `git commit -- <paths>` during a merge conclusion; no issue numbers or `src/` paths in the toolguide.
- Verify `git diff --stat` under `packs/built-in/` shows only the toolguide pair plus generated files, and `test_pack_manifest_no_author_edit.py` is green.
- Confirm no edits outside `owned_files` (in particular no `docs/changelog/CHANGELOG.md`, no `tests/architectural/test_commit_scope_owner.py`).

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Post-tasks review NOTE 2 folded: `docs/api/upgrade-lifecycle.md` `:57-63` is #5856's region (C-001 updated in spec); this WP edits only the commit block around `:130`.
- 2026-10-07 – planner-priti – Analysis fold AN-COV-002: C-004 (red-first) added to `requirement_refs`.
