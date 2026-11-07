---
work_package_id: WP02
title: Git-remedies checkout renderer (#7178)
dependencies: []
requirement_refs:
- FR-003
- C-001
- C-002
- C-003
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: issue-7183-nightly-reds-remediation
merge_target_branch: issue-7183-nightly-reds-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-7183-nightly-reds-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7183-nightly-reds-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
phase: Phase 1 - Production fix
history:
- at: '2026-11-07T21:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/_git_remedies.py
- src/specify_cli/upgrade/tracked_meta_notice.py
- tests/specify_cli/cli/commands/test_git_remedies.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 - Git-remedies checkout renderer (#7178)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). If this WP was returned from review, address every feedback item first.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- FR-003, C-002, C-003. The gate node `tests/specify_cli/cli/commands/test_git_remedies.py::test_no_inline_destructive_git_advice_in_src` passes with an EMPTY allowlist; notice output is byte-identical; the new renderer has same-PR unit tests.

## Context & Constraints

- Spec User Story 2; research.md row #7178. Gate contract: #3931, empty-allowlist operator ruling 2026-09-30, ADR `2026-09-30-1`.
- `src/specify_cli/upgrade/tracked_meta_notice.py` (from #6673, `dfb190e1a4`) holds `_RESTORE = "git checkout -- {path}"` (about line 23) and formats it at five remedy sites (`_restore_notice` and four branches of `_refusal_notice`). The gate scans `src/specify_cli/**` and excludes only `cli/commands/_git_remedies.py`.
- **Trap**: do NOT use `restore_recipe`. It renders `git restore --source <src> --staged --worktree -- <path>`, which drops the staged edit that the `staged_differs` branch deliberately keeps (5b822c28ca) and fails outright for `index_only` (nothing in HEAD; the "unusable remedy" defect #7131 fixed, pinned at `test_read_tracked_meta_6673.py` around line 404 expecting the checkout form).
- Never add an allowlist entry or change the scanner.

## Subtasks & Detailed Guidance

### Subtask T004 - Add `checkout_file_recipe`

- **Purpose**: the canonical home for the checkout-form recipe text.
- **Steps**:
  1. RED: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_git_remedies.py -q` (expect the gate node to fail listing `('upgrade/tracked_meta_notice.py', 'git checkout -- {path}')`).
  2. Read `restore_recipe` in `src/specify_cli/cli/commands/_git_remedies.py` and add a sibling `checkout_file_recipe(paths: Sequence[str]) -> str` next to it with identical file-scoped validation (non-empty; every entry names a file, a trailing `/` is refused; same error type and message style) and `shlex.quote` on each path. It returns `f"git checkout -- {path_args}"` (index to working tree). Docstring states it renders the destructive file-scoped checkout line and why it is a separate renderer from `restore_recipe`. Reuse any validation helper `restore_recipe` already has instead of copying it (single authority).
- **Files**: `src/specify_cli/cli/commands/_git_remedies.py`.

### Subtask T005 - Route the notice through it

- **Steps**:
  1. Delete `_RESTORE`. Add a private helper in `tracked_meta_notice.py`:
     `def _restore_command(path: str) -> str:` that does a function-level (deferred) `from specify_cli.cli.commands._git_remedies import checkout_file_recipe` and returns `checkout_file_recipe([path])`. The import must be deferred (same precedent: `src/specify_cli/migration/mission_state.py` around line 1570 and `runtime_state_cutover.py` around line 289) because `specify_cli.cli.commands.__init__` imports the whole command surface. Add a one-line comment giving that reason.
  2. Replace the five `_RESTORE.format(path=path)` sites with `_restore_command(path)`.
  3. Leave prose comments and docstrings that mention `git checkout -- <path>` (the gate ignores them).
- **Files**: `src/specify_cli/upgrade/tracked_meta_notice.py`.
- **Notes**: output for `kitty-specs/<slug>/meta.json` is byte-identical (no space, POSIX); the existing pins prove it.

### Subtask T006 - Unit tests for the renderer

- **Steps**: in `tests/specify_cli/cli/commands/test_git_remedies.py`, mirror the `restore_recipe` tests: renders the exact line for one path and for several paths; refuses a directory-scope entry (trailing `/`); refuses an empty list; quotes a path containing a space. Same assertion style (`pytest.raises` with the same error type the sibling uses).
- **Files**: `tests/specify_cli/cli/commands/test_git_remedies.py`.

### Subtask T007 - Evidence and neighbour guards

- Run and record (all must pass): `tests/specify_cli/cli/commands/test_git_remedies.py` (whole file: gate plus new tests), `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`, `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`, `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py`, `tests/architectural/test_destructive_op_routing.py` (cheap insurance; the specific gate file, not the directory).
- Lint and format on the three files; complexity stays at or below 15.
- Strength spot-check (not committed): re-introduce an inline `git checkout -- {path}` literal and confirm the gate fails again.
- Commit: `fix(upgrade): render the tracked-meta restore remedy through the git-remedies home (#7178)`.

## Test Strategy

The gate node plus the new unit tests plus the pinned notice strings.

## Risks & Mitigations

- Import cycle: deferred import. Mitigation: run the notice tests (they import the module).
- A reviewer may ask why not `restore_recipe`: the answer is in the trap note above and in `traces/design-decisions.md`.

## Review Guidance

- Gate allowlist still empty and scanner untouched; `_RESTORE` gone; helper uses a deferred import; notice pins unchanged and green; new tests exist for the renderer; no `restore_recipe` substitution.

## Branch Strategy

- **Strategy**: `single_branch` (no lanes; WPs run one after the other in the write checkout)
- **Planning base branch**: `issue-7183-nightly-reds-remediation`
- **Merge target branch**: `issue-7183-nightly-reds-remediation`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change by hand.

## Rules that bind every WP (charter and spec)

- **Never weaken a test to green it.** A re-pin keeps every original behavioural assertion and adds the new contract. If you cannot re-pin without loosening an assertion or deleting a pin without a stronger home, STOP and report an operator decision.
- Cite the contract-change commit in a comment on the re-pinned lines or in the commit message.
- RED first: run each exact node id on the current tree before editing and keep the failure output (summary line). After the edit run the same ids, then the owning files and named gates. Record the exact commands and passed/failed counts in the WP's `add-history` note and the commit message.
- Run tests as `PWHEADLESS=1 .venv/bin/python -m pytest <ids> -q` (not a bare `uv run`). No full suites, no `make test-fast` over the repo (NO_FULL_HEAVY_SUITES_IN_MISSION); the targeted nodes, owning files and named gates are the verification.
- `uv run --frozen ruff check <files>` and `uv run --frozen ruff format --check --force-exclude <files>` must report 0 issues. No `noqa`, no `type: ignore`, no allowlist additions.
- Touch only this WP's owned files. A tiny justified out-of-map edit needs a one-line rationale in the history note.
- Commit per WP, ending the message with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Do NOT push, open a PR, review, approve, accept or consolidate; the stop point is `for_review`.

## Progress & Status

Progress lives in the status event log, never in this file.

- Progress note: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- Subtask done: `spec-kitty agent tasks mark-status T00x --status done`
- Move: `spec-kitty agent tasks move-task <WPID> --to for_review`
- View: `spec-kitty agent tasks status`

Implementation command: `spec-kitty agent action implement <WPID> --agent claude --mission nightly-reds-remediation-01M6VYS1`
