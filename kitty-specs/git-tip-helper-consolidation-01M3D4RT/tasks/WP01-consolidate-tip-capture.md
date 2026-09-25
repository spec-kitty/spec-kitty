---
work_package_id: WP01
title: 'Consolidate target-branch tip-capture + fold #4593 item1 and #4152 items 2&3'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/git-tip-helper-consolidation
merge_target_branch: fix/git-tip-helper-consolidation
branch_strategy: Planning artifacts for this mission were generated on fix/git-tip-helper-consolidation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/git-tip-helper-consolidation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Consolidation + folds
history:
- at: '2026-09-25T20:50:18Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/core/vcs/
create_intent:
- tests/specify_cli/core/vcs/test_capture_branch_tip.py
- tests/specify_cli/cli/commands/agent/test_issue_4593_behind_count_full_history.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/core/vcs/git.py
- src/specify_cli/lanes/planning_commit_classify.py
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_dependency_graph.py
- src/specify_cli/migration/mission_state.py
- tests/specify_cli/core/vcs/test_capture_branch_tip.py
- tests/lanes/test_lane_base_common_ancestor.py
- tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py
- tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py
- tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py
- tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py
- tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py
- tests/specify_cli/cli/commands/agent/test_issue_4593_behind_count_full_history.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Consolidate target-branch tip-capture + fold #4593 item1 and #4152 items 2&3

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Deliver **one canonical target-branch tip-capture authority** for every
`classify_recorded_pin` caller — resolving the **branch** tip deterministically
(`refs/heads/{ref}`, as merge-preflight and coord-doctor already do) — and fold two
adjacent squad tidies.

> **⚠️ Premise correction (adversarial squad, empirically verified on git 2.43.0).**
> The original #4857 framing (bare `rev-parse` "diverges" from `--verify` on ambiguous
> refs) is FALSE: `git rev-parse <name>` and `git rev-parse --verify <name>` are
> identical (both resolve a branch+tag name collision to the **tag** SHA, exit 0).
> The REAL latent defect: the classifier-tip callers resolve the **bare** branch name,
> so a tag colliding with the target-branch name silently misresolves the pin to the
> tag — whereas `merge/preflight.py:240`, `merge/push_preflight.py:244`, and
> `_coordination_doctor.py:587,636` already resolve `refs/heads/{target_branch}`.
> The canonical helper closes that inconsistency by resolving `refs/heads/{ref}`.

- **SC-001/002 (#4857)**: exactly one code surface captures the classifier tip, and it
  resolves `refs/heads/{ref}`. A test proves the fix RED-first: with a branch and a
  same-named tag at different commits, the OLD bare-name resolution returns the **tag**
  SHA while the new helper returns the **branch** SHA (RED on the old path, GREEN on the
  new); plus valid-ref equivalence and missing-ref → `None`.
- **SC-003 (#4593 item1)**: the move-task behind-count includes source commits
  reachable through TREESAME merges (no history-simplification undercount); fail-open
  fallback preserved.
- **SC-004 (#4152 items 2&3)**: finalize dependency resolution unchanged across
  {absent, present-empty, present-non-empty} `dependencies`; the cyclic-dependency
  test fails if the production path returns exit 0.
- New/changed code: complexity ≤ 15, focused tests for every new branch, ruff + ruff
  format + mypy clean on touched files.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (single canonical authority DIRECTIVE_044;
  ATDD red-first DIRECTIVE_034/041; smallest-viable-diff; locality DIRECTIVE_024).
- Plan: [plan.md](../plan.md) — see **Design D1–D5** for the full seam map.
- Both former helpers terminate at `lanes/planning_commit_classify.classify_recorded_pin`;
  they are the same semantic operation (tip capture for pin classification).
- **C-001**: do NOT fold `implement_support._rev_parse` (distinct `"unknown"`-sentinel,
  base-branch contract) into this consolidation.
- **C-002**: preserve the FR-008b merge-env ratchet — every subprocess in
  `lanes/merge.py` still routes env through `_make_merge_env`
  (`tests/architectural/test_merge_pipeline_ratchets.py`). `lanes/merge._rev_parse`
  stays as-is for its non-tip callers.
- **C-003**: #4593 is message-only; blocking still derives from the full merge-base diff.
- **C-004**: #4152 item2 is pure dead-code removal — zero behaviour change.

### Local environment notes
- Editable install is current — src edits are live; do **NOT** run `uv sync` or bare
  `uv run` (destroys the hand-built `.venv`). Run tests as
  `PWHEADLESS=1 .venv/bin/python -m pytest <file> -q`, **file-scoped and foreground**.
  Do not run whole-dir / `make test-*` sweeps (pre-existing red main + hangs).
- `git checkout -- uv.lock` before any `git add` (local uv rewrites it to an
  artifactory mirror).

## Branch Strategy

- **Planning base branch**: `fix/git-tip-helper-consolidation`
- **Merge target branch**: `fix/git-tip-helper-consolidation`
- Execution worktrees are allocated per computed lane from `lanes.json`. Enter the
  workspace `spec-kitty implement WP01` resolves; do not reconstruct the path.

---

## Subtasks

### T001 — Add `capture_branch_tip` to `core/vcs/git.py`

**Purpose**: one canonical helper resolving a **branch** name to its tip SHA
deterministically, beside `git_rev_list_count`.

**Signature**:
```python
def capture_branch_tip(repo: Path, branch: str, *, env: dict[str, str] | None = None) -> str | None:
```
**Steps**:
1. Run `git rev-parse --verify refs/heads/{branch}` (cwd=`repo`, `capture_output=True`,
   `text=True`, `env=env` when provided). The `refs/heads/` qualification is the
   correctness fix: it resolves the **branch** tip, never a same-named tag (verified:
   bare `dup`→tag SHA, `refs/heads/dup`→branch SHA on git 2.43.0). `--verify` keeps the
   single-object guarantee and the clean non-zero-exit-on-missing behaviour. This
   matches the pattern `merge/preflight.py:240` and `_coordination_doctor.py:587,636`
   already use.
2. Return `result.stdout.strip()` on returncode 0 and non-empty; otherwise `None`.
   **Never raise** on a git failure.
3. Write a docstring stating the ONE contract (FR-002): form
   (`rev-parse --verify refs/heads/{branch}`), why `refs/heads/` (deterministic branch
   tip, not a same-named tag), the optional merge-env pass-through and why it is inert
   for `rev-parse`, and the behaviour on a missing branch (→ `None`, never raises).
   Migrate the substantive contract notes from the old
   `mission_finalize._capture_target_branch_tip` docstring.
4. Keep complexity trivial; no new module-level constants unless a literal repeats ≥3×.

> **Contract note**: callers pass a plain local branch name (`target_branch` /
> `manifest.target_branch` — verified: never a SHA or a qualified/remote ref). The
> helper's domain is "the target-BRANCH tip"; a non-branch input is out of contract.

### T002 — Reroute the six classifier-tip sites; delete the old helper; migrate the seams

**Reroute (replace the tip capture with `capture_branch_tip(...)`)**:
- `lanes/worktree_allocator.py:548` (currently `_rev_parse(repo_root, ...target_branch)`)
- `lanes/implement_support.py:382` and `:506` (currently `_rev_parse_or_none(...)`)
- `cli/commands/agent/tasks_move_task.py:724` (currently `_rev_parse_or_none(...)`)
- `cli/commands/agent/mission_finalize.py:2295` and `:2338` (currently `_capture_target_branch_tip(...)`)
- `cli/commands/agent/tasks_finalize.py:380` (currently `_capture_target_branch_tip(...)`)
- `migration/mission_state.py:1620` (currently `_capture_target_branch_tip(...)`)

**Import hygiene**:
- In `mission_finalize.py`, import the helper module-level and **UNQUALIFIED**:
  `from specify_cli.core.vcs.git import capture_branch_tip`, and call
  `capture_branch_tip(...)` (NOT `git.capture_branch_tip(...)`). This is required so the
  existing monkeypatch seam (below) can intercept the production call — patching
  `mission_finalize.capture_branch_tip` only works if the name lives in that namespace.
- For `worktree_allocator`/`implement_support`/`tasks_move_task`, drop the now-unused
  tip imports after rerouting: `worktree_allocator.py:33` (`_rev_parse`),
  `implement_support.py:22` (`_rev_parse as _rev_parse_or_none`),
  `tasks_move_task.py:692` (function-local import). **ruff F401 will flag these** —
  remove them. **KEEP** the LOCAL `implement_support._rev_parse` def at `:277` and its
  import chain used at `:224` (base-branch, distinct `"unknown"` sentinel — C-001).

**Delete** `_capture_target_branch_tip` from `mission_finalize.py`, and remove its
cross-module imports in `tasks_finalize.py` and `migration/mission_state.py`.

**⚠️ Whack-a-field seams — update, do not leave dangling** (these break on deletion):
- `tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py:1083`
  monkeypatches `seam, "_capture_target_branch_tip"` (seam = the mission_finalize
  module). Repoint to `monkeypatch.setattr(seam, "capture_branch_tip", ...)` — this only
  intercepts the production call because of the module-level unqualified import above.
- `tests/lanes/test_lane_base_common_ancestor.py:371-395` imports and asserts
  `_capture_target_branch_tip(repo, "main") == expected` and `(... "no-such-branch") is None`.
  Repoint to `capture_branch_tip` (the producer-helper assertions move with the helper).
  Note the NEW behaviour: `capture_branch_tip(repo, "main")` resolves `refs/heads/main`,
  so assertions must use a real branch (they already use `"main"` — fine). Natural seed
  for T003.
- Refresh the now-stale docstring/comment references to `_capture_target_branch_tip` in
  `test_issue_4827_repin_orphaned_planning_commit.py`, `test_issue_4141_refresh_planning_commit.py`,
  and `test_finalize_provenance_guard.py` (comment-only; those use real git repos, so
  behaviour is unchanged — just fix the names for accuracy).
- Refresh the two prose references to `_capture_target_branch_tip` in
  `src/specify_cli/lanes/planning_commit_classify.py:28,119` (docstrings) to name
  `capture_branch_tip` — the symbol they cite is being deleted (campsite; owned).

### T003 — Cross-call-path agreement test (FR-003) — RED-first on ambiguous

**New file**: `tests/specify_cli/core/vcs/test_capture_branch_tip.py`. Mark the
divergence-closing assertion `@pytest.mark.regression` and reference `#4857`.

**Cases** (build a real temp git repo):
1. **Valid ref** → `capture_branch_tip(repo, "main")` returns the same SHA as
   `git rev-parse refs/heads/main`; assert equality (NFR-001: no change for the common
   no-collision case).
2. **Missing branch** → `capture_branch_tip(repo, "no-such-branch")` returns `None`,
   never raises.
3. **Tag-collision (the RED-first correctness proof)** → create a branch `dup` at C1 and
   a tag `dup` at C2 (C1 ≠ C2). Assert `capture_branch_tip(repo, "dup")` returns **C1**
   (the branch tip, via `refs/heads/dup`). Demonstrate the OLD behaviour in the same
   test: `git rev-parse dup` / `git rev-parse --verify dup` return **C2** (the tag) —
   i.e. the pre-fix bare resolution silently misresolved to the tag. This is the honest
   RED-first: the assertion `capture_branch_tip(...) == C1` FAILS against a bare-name
   helper and PASSES with `refs/heads/`. Record that you verified the bare form returns
   C2 (do it inline in the test as the contrast).
4. Optionally drive both former call paths against the same repo and assert identical
   results (equivalence of the consolidated authority).

Confirm RED-first empirically: a bare-name `capture_branch_tip` returns C2 → assertion
fails; the `refs/heads/` form returns C1 → passes.

### T004 — #4593 item1: accurate behind-count on merge-rich targets

1. `core/vcs/git.py` `git_rev_list_count` (~L1137): add keyword `full_history: bool = False`;
   when true, insert `--full-history` immediately after `--count`
   (`["git", "rev-list", "--count", "--full-history", rev_range]` then `["--", *pathspecs]`;
   verified compatible with `--count -- <pathspecs>`). Update the docstring to note the
   flag disables history simplification so TREESAME merges of matching commits are not
   pruned — AND that, without `--simplify-merges`, source-relevant **merge commits
   themselves are also counted**, so the count is a conservative upper bound (acceptable:
   message-only, fail-open — C-003), not an exact source-commit count.
2. `cli/commands/agent/tasks_dependency_graph.py:260` (`_count_behind_commits_outside_planning_artifacts`):
   pass `full_history=True` to the `git_rev_list_count(...)` call.
3. **New file** `tests/specify_cli/cli/commands/agent/test_issue_4593_behind_count_full_history.py`,
   `@pytest.mark.regression` (`#4593`): build a merge-rich target branch where a source
   commit arrives via a TREESAME merge to the followed parent. Assert the count now
   **includes** that commit — compute the expected value WITH any counted merge commits,
   or assert `>=`/inclusion rather than a naive exact equality that the merge over-count
   would break (RED without `--full-history`, GREEN with). Assert the fail-open fallback
   (returns raw `behind_count` when the count is undeterminable) and that a linear
   (non-merge) range is unchanged by the flag.

### T005 — #4152 item2: remove dead guard + redundant read

In `mission_finalize._resolve_dependencies_and_refs` (~L1062-1074):
1. Replace
   `frontmatter_deps = list(wp_meta.dependencies) if _raw_frontmatter_has_field(raw_content, "dependencies") else []`
   with `frontmatter_deps = list(wp_meta.dependencies)`.
2. Delete the now-unused `raw_content = wp_file.read_text(encoding="utf-8")` line in
   that loop (confirmed: `raw_content` in that loop is used ONLY at the :1067/:1069 pair;
   the `raw_content` at ~:1514 is a DIFFERENT function's local — do not touch it).
3. **KEEP the `_raw_frontmatter_has_field` import (mission_finalize.py:108)** — it is
   STILL used at `:1515` and `:1516` (a separate function). Only the `:1069` use is
   removed. Do NOT drop the import (dropping it → NameError at :1515-1516). Do NOT touch
   `_raw_frontmatter_dependencies_is_string_form` or other siblings.
4. Justification (C-004): `WPMetadata.dependencies` is `Field(default_factory=list)`
   (`status/wp_metadata.py`), so absent→`[]`; the guarded expression already equals the
   bare `list(wp_meta.dependencies)` for all three cases. Confirm the existing
   dependency-resolution tests stay green (behaviour-preserving); add a focused
   assertion if none directly covers the {absent, present-empty, present-non-empty}
   trio.

### T006 — #4152 item3: load-bearing exit-code assertion

In `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py:764`:

> **⚠️ The nit's own diagnosis is incomplete (verified).** `typer.Exit` has NO `.code`
> attribute — it exposes `.exit_code`. So the current `getattr(exc, "code", 1) or 1`
> ALWAYS yields `1` (attribute absent → default), making the assertion fully blind, not
> merely `0`→`1`. And the WP's first-draft fix `getattr(exc, "code", None)` would return
> `None` on the correct `Exit(1)` path → `assert None == 1` REDS the healthy path. Do
> NOT use that.

Correct fix (the `except` catches `(typer.Exit, SystemExit)`; production `finalize_tasks`
raises `typer.Exit`, `SystemExit` uses `.code`):
```python
exit_code = exc.exit_code if isinstance(exc, typer.Exit) else exc.code
```
so `Exit(1)`→`1` (assert passes), `Exit(0)`→`0` (assert fails — now load-bearing). Keep
the substantive circular-dependency payload assertion. Run the test to confirm it passes
on the correct `Exit(1)` production path, and (RED-first check) fails if you temporarily
force the production path to `Exit(0)`.

### T007 — Blast-radius verification + tracer

1. Run the targeted, file-scoped suites (foreground):
   - `tests/specify_cli/core/vcs/test_capture_branch_tip.py`
   - `tests/specify_cli/core/vcs/test_merge_base_diff_surface.py` (git_rev_list_count home)
   - `tests/lanes/test_lane_base_common_ancestor.py`
   - `tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py`
   - `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py`
   - `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py`
   - `tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py`
   - `tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py`
   - `tests/specify_cli/cli/commands/agent/test_tasks_dependency_readiness.py`
   - `tests/specify_cli/cli/commands/agent/test_issue_4593_behind_count_full_history.py`
   - `tests/architectural/test_merge_pipeline_ratchets.py` (C-002 ratchet still green)
2. `.venv/bin/python -m ruff check <touched files>` and
   `.venv/bin/python -m ruff format --check <touched files>` and
   `.venv/bin/python -m mypy <touched src files>` — all clean.
3. Record commands + passed/failed counts for the PR *Tests run* section.
4. Append findings to the mission tracer files (`tracer-*.md`), committing the append
   immediately (mission commands rewrite the primary mission dir from coord).

## Definition of Done

- [ ] `capture_branch_tip` (resolving `refs/heads/{branch}`) is the sole tip-capture
      authority for all 6 classifier callers; imported module-level unqualified in
      `mission_finalize`.
- [ ] `_capture_target_branch_tip` deleted; all patch/producer/comment seams migrated;
      unused tip imports dropped (ruff F401 clean); local `implement_support._rev_parse`
      + `_raw_frontmatter_has_field` import KEPT.
- [ ] Tag-collision RED-first test present, `@pytest.mark.regression #4857` (branch tip,
      not the same-named tag); valid-ref + missing-ref cases covered.
- [ ] #4593 `--full-history` folded with an issue-pinned regression (conservative
      upper-bound framing; no naive exact-equality); fallback + linear-case preserved.
- [ ] #4152 item2 dead code removed (behaviour-preserving); item3 assertion load-bearing
      via `.exit_code`.
- [ ] Merge-env ratchet green; touched files ruff/format/mypy clean; complexity ≤ 15.
- [ ] No change for the common no-collision case (NFR-001).

## Reviewer Guidance

- Verify the RED-first tag-collision claim: with a branch and same-named tag, the fix
  resolves the BRANCH tip; a bare-name helper would return the tag (the real #4857 defect).
- Confirm `lanes/merge._rev_parse` and `implement_support._rev_parse` were **left alone**
  (C-001/scope), and merge-env ratchet stays green (C-002).
- Confirm no test still patches the deleted `_capture_target_branch_tip` name, and the
  monkeypatch at test_mission_finalize_phases.py intercepts the production call (module-
  level unqualified import).
- Confirm #4152 item2 is behaviour-neutral (resolution identical for {absent, empty,
  non-empty}) and the `_raw_frontmatter_has_field` import survived (used at :1515-1516).
- Confirm #4152 item3 uses `.exit_code` (not `.code`) and reds on a forced `Exit(0)`.
