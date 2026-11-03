---
work_package_id: WP02
title: One authority for tasks/README.md
dependencies: []
requirement_refs:
- FR-006
- C-001
- C-004
planning_base_branch: issue-6877-ascii-mission-scaffold
merge_target_branch: issue-6877-ascii-mission-scaffold
branch_strategy: Planning artifacts for this mission were generated on issue-6877-ascii-mission-scaffold. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6877-ascii-mission-scaffold unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Remove the second source of truth
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/worktree.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/worktree.py
- tests/git_ops/test_worktree.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 - One authority for `tasks/README.md`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: (the harness running this work package)

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

`src/specify_cli/core/worktree.py` contains a second producer of the same scaffold file: a
~55-line string literal inside `setup_feature_directory()` that is written to
`kitty-specs/<mission>/tasks/README.md`. It is reached through `create_feature_worktree()`
(no production caller today, tests only). It happens to be ASCII — it spells the title
`WP01 -- Work Package Title` — but it has drifted from the canonical text in every other
respect, and it sits outside the pin WP01 installs.

This WP is complete when:

1. `setup_feature_directory()` writes `render_tasks_readme_content(feature_dir.name)` — the
   inline literal is deleted, not kept as a fallback.
2. Its signature, symlink/memory handling, `.gitkeep` creation and spec-template copy are
   unchanged (C-004).
3. A test proves the convergence: the bytes on disk equal the renderer's output for the same
   directory name.
4. No second inline copy of the scaffold text remains in `src/`.

## Context & Constraints

- Mission spec: [`../spec.md`](../spec.md) — FR-006, C-003, C-004, SC-006.
- Mission plan: [`../plan.md`](../plan.md) — IC-02 (including the lazy-import note), and the
  "Complexity Tracking" entry that records why convergence beats pinning two texts.
- Discovery: [`../research.md`](../research.md) — D-6 (the two emitters, and how they differ).
- **Ordering**: WP01 lands the ASCII canonical text first. This WP inherits it; do not edit
  `mission_creation_scaffold.py` (that file belongs to WP01's `owned_files`) — if the
  canonical text still needs a change, record the finding and raise it, do not reach across
  the ownership boundary.
- **Single canonical authority** (DIRECTIVE_044): the point of this WP is that one literal owns
  the text. Do not solve it by adding a third copy, a `try/except ImportError` fallback, or a
  duplicated constant in `worktree.py`.
- **Import shape**: `mission_creation_scaffold` lazily imports
  `specify_cli.core.mission_creation` inside functions to avoid a module-scope cycle, and
  `mission_creation` re-exports the scaffold names. Use a **lazy in-function import** of
  `render_tasks_readme_content` from `specify_cli.core.mission_creation_scaffold` and record
  in a comment why the import is lazy (mirrors the module's own convention). Verify no cycle
  appears by importing the module fresh (`uv run python -c "import specify_cli.core.worktree"`).

## Branch Strategy

- **Strategy**: Planning artifacts and code both land on `issue-6877-ascii-mission-scaffold`; completed changes merge back into `issue-6877-ascii-mission-scaffold`.
- **Planning base branch**: `issue-6877-ascii-mission-scaffold`
- **Merge target branch**: `issue-6877-ascii-mission-scaffold`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T006 - Red-first: the emitter matches the renderer

- **Purpose**: State the convergence as a failing test before changing production code.
- **Files**: `tests/git_ops/test_worktree.py` (beside the existing
  `TestSetupFeatureDirectory.test_creates_tasks_readme`).
- **Steps**:
  1. Add `test_tasks_readme_comes_from_the_canonical_renderer`: build a `feature_dir` under
     `tmp_path`, call `setup_feature_directory(feature_dir, worktree_path, repo_root,
     create_symlinks=False)`, and assert the written content equals
     `render_tasks_readme_content(feature_dir.name)`.
  2. Run it and record the RED: the inline literal differs (it lacks the `branch_strategy` /
     `merge_target_branch` lines, has a different section set, and spells the frontmatter
     example `at:`/`actor:`).
- **Notes**: keep the pre-existing `test_creates_tasks_readme` assertions intact and passing
  (`# Tasks Directory`, `YAML frontmatter`, `status.events.jsonl`, `"lane:" not in content`)
  — they are the behavioural floor this WP must not break.

### Subtask T007 - Delete the literal, render through the renderer

- **Purpose**: The fix.
- **Files**: `src/specify_cli/core/worktree.py` (`setup_feature_directory`).
- **Steps**:
  1. Replace the `tasks_readme_content = """..."""` block and its `write_text` with:
     ```python
     (tasks_dir / "README.md").write_text(
         render_tasks_readme_content(feature_dir.name),
         encoding="utf-8",
     )
     ```
     with a lazy in-function import and a one-line comment naming the single-authority
     reason (#6877, DIRECTIVE_044).
  2. Delete the literal entirely — no dead constant, no `if False` copy
     (`tests/architectural/test_no_dead_modules.py` and the campsite rule both object to
     leaving it behind).
  3. Do not touch anything else in the function. `git diff` for this file must be the import,
     the replaced block, and the comment.
- **Notes**: `feature_dir.name` is the mission directory name, which for this entry point *is*
  the branch name — `create_feature_worktree` composes both from `mission_dir_name(...)`.
  Record that reasoning in the comment so a reader does not have to rediscover it.

### Subtask T008 - Census: no second copy of the text

- **Purpose**: Make the "one authority" claim checkable rather than aspirational.
- **Steps**:
  1. Add an assertion (in the same test module is fine) that the scaffold text is produced
     from exactly one core module: the string `# Work Package Prompt:` appears in exactly one
     file under `src/` outside the pack tree. Implement it as a concrete scan with a small
     allowlist-free predicate, and make the failure message name the offending path.
  2. Run it against the current tree to confirm it passes after T007 (it must fail if you
     revert T007 — say so in the WP history if you check that).
- **Notes**: keep it cheap — a bounded glob over `src/**/*.py` reading only files that
  mention the marker; no full-tree byte scan on every run. If a scan proves noisy,
  prefer asserting the specific pair (the constant exists in
  `mission_creation_scaffold`, and `worktree.py` no longer contains the marker) over a
  fragile global rule; record which form you chose and why.

### Subtask T009 - Re-run the touched suites and record counts

- **Purpose**: Close-out evidence.
- **Steps**:
  1. `uv run pytest tests/git_ops/test_worktree.py -q`.
  2. `uv run pytest tests/specify_cli/git/test_guarded_site_routing_misc.py -q -k setup_feature_directory`.
  3. `uv run pytest tests/core/test_tasks_readme_scaffold_ascii.py tests/core/test_mission_creation_family.py -q`.
  4. Record every command with its pass/fail counts in the WP history note, and flag any red
     that also fails on the merge base (report it, do not work around it).
- **Notes**: no full heavy suite; CI owns the sweep.

## Test Strategy

- **New**: the convergence test (T006) and the census (T008).
- **Regression**: `tests/git_ops/test_worktree.py` in full — it is the tightest existing
  coverage of this function (subdirectories, `.gitkeep`, symlink and copy modes, the
  `#228` no-stray-`spec.md` rule, guarded-site routing).
- **Typecheck**: `uv run mypy src/specify_cli/core/worktree.py`.
- **Lint/format**: `uv run ruff check` and `uv run ruff format --check` on both touched files.
- **Import sanity**: `uv run python -c "import specify_cli.core.worktree"`.

## Risks & Mitigations

- **Import cycle.** Mitigation: lazy in-function import, mirroring the module's existing
  convention; verify with a fresh interpreter import and record the command.
- **Content change to a legacy path surprises a consumer.** Mitigation: the path has no
  production caller (verified in `research.md` D-6 — `create_feature_worktree` is referenced
  only by tests). The new text is the canonical one, which is the intended behaviour; state
  this in the PR body.
- **Losing the pre-existing behavioural assertions.** Mitigation: T009 runs the whole module;
  the `"lane:" not in content` and `status.events.jsonl` assertions must still pass on the
  converged text.
- **Reaching into WP01's file.** Mitigation: ownership boundary is explicit; report instead of
  editing `mission_creation_scaffold.py`.
- **Census noise.** Mitigation: prefer the two-file predicate over a global rule if the scan
  turns out fragile, and record the choice.

## Review Guidance

- Confirm the inline literal is gone (no dead constant left behind) and that the `git diff`
  for `worktree.py` is only the import, the replaced write, and the comment.
- Confirm the function's signature, symlink/memory handling, `.gitkeep` and spec-template copy
  are unchanged (C-004).
- Confirm the convergence test would fail if the literal were restored — ask for the recorded
  red output.
- Confirm the full `tests/git_ops/test_worktree.py` module is green, including the
  pre-existing `test_creates_tasks_readme` assertions.
- Confirm the implementer did not edit `mission_creation_scaffold.py` (WP01 ownership).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
