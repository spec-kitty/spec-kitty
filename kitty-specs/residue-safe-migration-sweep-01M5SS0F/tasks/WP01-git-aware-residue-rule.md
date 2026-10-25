---
work_package_id: WP01
title: Git-aware residue rule and shared notice
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- NFR-003
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/context/
create_intent:
- tests/context/test_is_kitty_specs_residue_git_aware.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/context/mission_resolver.py
- src/specify_cli/migration/normalize_mission_lifecycle.py
- src/specify_cli/migration/runtime_state_cutover.py
- tests/context/test_is_kitty_specs_residue_git_aware.py
- tests/specify_cli/migration/test_residue_dirs_left_untouched_6627.py
- tests/specify_cli/migration/test_normalize_mission_lifecycle.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Git-aware residue rule and shared notice

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `is_kitty_specs_residue` (in `src/specify_cli/context/mission_resolver.py`) decides residue in one of two modes:
  - **Git-aware mode**: git can run and git tracks at least one path under the project's `kitty-specs/`. A folder is residue when `is_mission_dir` rejects it and neither `spec.md` nor `meta.json` exists on disk, whatever else the folder holds.
  - **File-presence mode** (fallback): today's rule, i.e. none of `_MISSION_CONTENT` exists and `is_mission_dir` rejects it. It applies to non-git projects, unusable git, an ignored `kitty-specs/`, and an untracked project nested inside a parent repository.
- One shared `RESIDUE_NOTICE` text, used by every residue-aware step, names the folder and gives a remedy that works: add a `spec.md` or `meta.json` to make it a Mission, or remove the folder. The lifecycle normalization uses it.
- NFR-003, measured with a spy on `run_git`:
  - a folder whose `meta.json` carries a `mission_id` costs 0 git calls;
  - a walk that passes `tracked=` costs at most 2 calls for the mode check and tracked set, plus at most 2 per identity-less folder.
- Requirement refs: FR-001, FR-002, FR-003 (seam side), FR-008 (notice text), NFR-003.

## Context & Constraints

- Read `.kittify/charter/charter.md`, `kitty-specs/residue-safe-migration-sweep-01M5SS0F/spec.md` (Domain Language, FR-001/FR-002, Edge Cases), `plan.md` (IC-01), `research.md` (R-04) and `data-model.md` ("Residue decision").
- The operator rulings are binding:
  - git-aware rule;
  - git-aware mode only when `kitty-specs/` is tracked;
  - committed, pre-identity, tasks-only folders become residue (accepted cost).
- **One authority.** Do not add a second predicate. `is_mission_dir` stays the canonical Mission predicate, and `is_kitty_specs_residue` is the single write-seam rule layered on it.
- Current callers: `upgrade/feature_meta.build_baseline_feature_meta`, `migration/normalize_mission_lifecycle.normalize_repo`, `migration/runtime_state_cutover.cutover_mission`. Their call shape must keep working; `tracked=` and `repo_root=` stay optional keywords.
- `_git_prefix` already treats `GitCommandError.not_run` as "not a work tree" (#6662). Keep that.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

Implementation command:

```bash
spec-kitty agent action implement WP01 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T001 – Git-aware mode probe

- **Purpose**: decide which mode applies, once per walk where possible.
- **Steps**:
  1. Add a small pure helper, for example `_git_aware_mode(tracked: frozenset[str] | None) -> bool`, which is True iff `tracked` is not `None` and not empty. `tracked_mission_paths(repo_root)` already returns `None` outside a work tree or when git cannot run, and an empty set when nothing under `kitty-specs/` is tracked: the ignored and nested-untracked cases.
  2. In `is_kitty_specs_residue`, compute `tracked` lazily via `tracked_mission_paths(repo_root)` only when the caller did not pass one, and only after the cheap no-git checks: markers on disk, identity in `meta.json`.
- **Files**: `src/specify_cli/context/mission_resolver.py`.
- **Notes**: never call git for a folder whose `spec.md` or `meta.json` exists on disk; it is not residue in either mode.

### Subtask T002 – Git-aware branch of `is_kitty_specs_residue`

- **Purpose**: implement FR-001 and FR-002 exactly.
- **Steps** (order matters for cost):
  1. `path.parent.name != KITTY_SPECS_DIR` → return False (unchanged).
  2. `(path / "spec.md").exists() or (path / "meta.json").exists()` → return False (both modes, 0 git calls).
  3. Resolve `tracked` (passed in, or computed once).
  4. Git-aware mode → `return not is_mission_dir(path, repo_root=..., tracked=tracked)`.
  5. File-presence mode → `if any((path / n).exists() for n in _MISSION_CONTENT): return False`, then `return not is_mission_dir(path, repo_root=..., tracked=tracked)`. Pass `tracked=None` when the probe returned `None`, so `is_mission_dir` keeps its own non-git existence fallback.
  6. Update the docstring: both modes, the accepted cost, the deleted-tracked-marker case (still a Mission, because `is_mission_dir` rule 2 sees the tracked path).
- **Files**: `src/specify_cli/context/mission_resolver.py`.
- **Notes**: `normalize_repo` already computes `tracked` once and passes it. Keep `runtime_state_cutover.cutover_mission` calling `is_kitty_specs_residue(feature_dir)`; no signature change is needed there. Keep every function at complexity ≤ 15 (extract `_file_presence_residue` if needed).

### Subtask T003 – Shared `RESIDUE_NOTICE`

- **Purpose**: one text for every step's residue warning (FR-008). The runner collapse in WP04 keys on it.
- **Steps**:
  1. In `mission_resolver.py`, add `RESIDUE_NOTICE = "{slug}: not a Mission (residue directory: no mission_id and no spec.md or meta.json); left untouched. Add a spec.md or meta.json to make it a Mission, or remove the folder."`, plus a tiny `residue_notice(slug: str) -> str` formatter. Adjust the wording if the review asks, but keep it a single constant.
  2. `migration/normalize_mission_lifecycle.py`: replace `RESIDUE_SKIP_WARNING` with the shared text. The slug is prefixed by the 3.2.0a4 migration (`f"{result.slug}: {warning}"`), so expose a slug-less form, or make the constant slug-less and let callers prefix. Pick one convention and document it in the constant's comment. Keep `RESIDUE_SKIP_WARNING` as an alias only if a test imports it; prefer updating the test.
- **Files**: `mission_resolver.py`, `normalize_mission_lifecycle.py`.

### Subtask T004 – Unit tests for every mode and shape

- **Purpose**: pin FR-001, FR-002 and NFR-003.
- **Steps**:
  - Create `tests/context/test_is_kitty_specs_residue_git_aware.py`, marked `git_repo`. Build fixtures with real `git init`.
  - Tracked project (one committed Mission): residue for an untracked-only `tasks/WP01.md`, `status.events.jsonl`, `status.json`, `tasks/doing/WP01.md` and `decisions/`. Not residue for an uncommitted `spec.md`, an untracked identity-less `meta.json`, a tracked `spec.md` deleted on disk, a folder outside `kitty-specs/`, or a committed `tasks.md` + `tasks/` folder. The last one **is** residue: assert the accepted cost explicitly, with a comment citing the ruling.
  - The same tasks-only fixture is **not** residue in each fallback setting:
    - non-git;
    - `PATH` without git (`monkeypatch.setenv("PATH", ...)`);
    - `kitty-specs/` gitignored;
    - an untracked project nested inside a parent repo.
  - A git-call spy: monkeypatch `specify_cli.context.mission_resolver.run_git` with a counting wrapper. Assert 0 calls for an identity-bearing folder. For a 50-folder identity-less walk that passes a precomputed `tracked=` (`tracked_mission_paths`), assert at most `2 + 2*50` calls; record the measured number in the test docstring.
- **Files**: `tests/context/test_is_kitty_specs_residue_git_aware.py`.

### Subtask T005 – Re-pin the #6627 seam tests

- **Purpose**: `tests/specify_cli/migration/test_residue_dirs_left_untouched_6627.py` and `test_normalize_mission_lifecycle.py` encode #6662's file-presence semantics. Re-pin the cases whose verdict changes under the ruling. Every changed assertion gets a one-line comment naming the ruling; never delete a case.
- **Steps**: run both files; for each failure decide stale-pin (re-pin) vs. product bug (fix the code). The meta-only and spec-only cases stay "not residue".
- **Files**: the two test files.

## Test Strategy

```bash
uv run --frozen pytest tests/context tests/specify_cli/migration/test_residue_dirs_left_untouched_6627.py tests/specify_cli/migration/test_normalize_mission_lifecycle.py tests/integration/migration/test_upgrade_residue_identity_6627.py -q
uv run --frozen ruff check src/specify_cli/context/mission_resolver.py src/specify_cli/migration/normalize_mission_lifecycle.py tests/context/test_is_kitty_specs_residue_git_aware.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy --strict src/specify_cli/context/mission_resolver.py src/specify_cli/migration/normalize_mission_lifecycle.py src/specify_cli/migration/runtime_state_cutover.py
```

## Risks & Mitigations

- **Over-widening**: a real Mission becomes residue. Mitigation: the deleted-marker and uncommitted-marker tests, plus every fallback setting.
- **Git cost regressions**: the spy test.
- **Import cycles**: `mission_resolver` must not import from `upgrade/` or `migration/`.

## Review Guidance

- Verify the order of checks (cheap first), both modes, and that the accepted-cost case is asserted explicitly.
- Confirm that `RESIDUE_NOTICE` is the only residue text in `src/` (`git grep -n "not a Mission (residue"`).
- Confirm that mypy strict and ruff ran clean on the changed modules.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`). Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
