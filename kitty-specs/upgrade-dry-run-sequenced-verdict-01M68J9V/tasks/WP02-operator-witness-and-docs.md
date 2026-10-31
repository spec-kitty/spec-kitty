---
work_package_id: WP02
title: The operator witness and the docs
dependencies:
- WP01
requirement_refs:
- FR-006
- SC-001
- SC-002
- SC-003
- SC-004
- C-004
planning_base_branch: issue-6552-upgrade-dry-run-sequenced-verdict
merge_target_branch: issue-6552-upgrade-dry-run-sequenced-verdict
branch_strategy: Planning artifacts for this mission were generated on issue-6552-upgrade-dry-run-sequenced-verdict. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6552-upgrade-dry-run-sequenced-verdict unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Operator surface
history:
- at: '2026-10-31T08:50:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent:
- tests/upgrade/test_dry_run_sequenced_verdict_cli.py
execution_mode: code_change
owned_files:
- tests/upgrade/test_dry_run_sequenced_verdict_cli.py
- src/specify_cli/upgrade/migrations/README.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The operator witness and the docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

WP01 fixed the runner and pinned it at the runner level. This WP proves the same result
through the surface an operator actually uses — the `upgrade --dry-run` command's rendered
output — and documents the new declaration and the changed wording.

Done when:

- A CLI-level test drives `upgrade --dry-run` on the reported-pair fixture and asserts the
  rendered output lists the predicted migration under `Migrations applied:` with its
  `dry-run: would apply after ...` provenance, and that the run wrote nothing.
- `migrations/README.md` tells a migration author when and how to declare
  `sequenced_after`.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry for #6552: impact-first lead,
  before/after, under 1,200 characters.

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/6552>
- Spec / plan / quickstart:
  `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/{spec,plan,quickstart}.md`
- WP01's test module: `tests/upgrade/test_dry_run_sequenced_verdict.py` (reuse its fixture
  helpers rather than duplicating them; importing helpers from a sibling test module is
  acceptable if the repo does it elsewhere, otherwise extract the fixture into
  `tests/upgrade/conftest.py`-style helpers **inside this WP's owned files only** — if that
  would require editing a file WP01 owns, import from the module instead).

Constraints:

- **C-004**: the worktree pass, `--plan-json` and `compat-planner.json` are out of scope.
- The CLI must be the production entry point (tactic `acceptance-criteria-non-vacuity`): drive
  the typer command, not only `MigrationRunner`.
- Do not add or change a JSON field. `--dry-run --json` keeps its current shape; if you assert
  it, assert the existing `migrations_applied` list.

## Branch Strategy

- **Strategy**: single checkout; planning artifacts were generated on
  `issue-6552-upgrade-dry-run-sequenced-verdict`, and completed changes merge into the same
  branch, which is the PR head.
- **Planning base branch**: `issue-6552-upgrade-dry-run-sequenced-verdict`
- **Merge target branch**: `issue-6552-upgrade-dry-run-sequenced-verdict`

## Subtasks & Detailed Guidance

### Subtask T006 – CLI witness

- **Purpose**: Prove the fix where the operator sees it.
- **Steps**: Add `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`, invoking the `upgrade`
  command through `typer.testing.CliRunner` (see `tests/compat/test_dry_run_parity.py` for the
  established pattern: a module-level `_test_app` with the command registered, `CI=1`, and
  `contextlib.chdir`). Assert:
  - `Migrations applied:` contains `3.2.6_issue_matrix_driver_repoint`;
  - the rendered output carries the prediction provenance (`would apply after
    3.2.6_gate_artifact_merge_drivers`) somewhere an operator can read it, and does not
    contain `3.2.6_issue_matrix_driver_repoint not needed`;
  - the project tree and both ledger partitions are unchanged after the dry run;
  - positive control: the same fixture upgraded for real lists the migration as applied
    (so the assertion cannot pass on a project where nothing was pending).
- **Files**: `tests/upgrade/test_dry_run_sequenced_verdict_cli.py` (new)
- **Notes**: `--no-worktrees` keeps the run offline and focused. If the fixture needs a full
  `init` to render the plan table, keep it to a minimal project — the plan table is not what
  is under test.

### Subtask T007 – Author documentation

- **Purpose**: The declaration is useless if a migration author does not know it exists.
- **Steps**: Add a short section to `src/specify_cli/upgrade/migrations/README.md`: what
  `sequenced_after` means (the migrations whose writes your `detect()` reads), that it is
  preview-only detect-input metadata and **not** execution order (the manifest owns that),
  when to declare it (only when `detect()` genuinely reads the predecessor's write), and that
  leaving it empty keeps today's honest `not needed on the current tree` wording.
- **Files**: `src/specify_cli/upgrade/migrations/README.md`

### Subtask T008 – Changelog

- **Purpose**: A user-visible behaviour change needs an `[Unreleased]` entry.
- **Steps**: Add to `docs/changelog/CHANGELOG.md` under `[Unreleased]` (match the neighbouring
  entries' shape): bold impact-first lead with `(#6552)`, then what the dry run said before
  and what it says now (one short before/after), under 1,200 characters total.
- **Files**: `docs/changelog/CHANGELOG.md`

### Subtask T009 – Verification

- **Steps**:
  - `uv run pytest tests/upgrade/test_dry_run_sequenced_verdict_cli.py tests/upgrade/test_dry_run_sequenced_verdict.py -q`
  - `uv run pytest tests/compat/test_dry_run_parity.py tests/upgrade/test_upgrade_outcome_rendering.py -q`
  - `uv run ruff check tests/upgrade/test_dry_run_sequenced_verdict_cli.py`
  - `uv run ruff format --check --force-exclude tests/upgrade/test_dry_run_sequenced_verdict_cli.py`
  - `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0)
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
- **Notes**: do not run `make test-full`.

## Test Strategy

The CLI assertion is the non-vacuity guard for the whole mission: it must exercise the
rendered command output. Pair the predicted case with the real-run positive control on the
same fixture. Keep the fixture deterministic (no network, `CI=1`, `--no-worktrees`).

## Risks & Mitigations

- **Helper-only test** (green while the CLI wiring is broken): assert on the rendered output,
  not on `UpgradeResult` internals.
- **Global-cache churn in the docs freshness check**: regenerate nothing outside the diff and
  verify with `--ci`.
- **Overlapping ownership with WP01**: import WP01's fixture helpers rather than editing
  WP01's file.

## Review Guidance

- Does the CLI test fail if the prediction is reverted (half-by-half proof)?
- Is the changelog entry impact-first and under 1,200 characters, with `(#6552)`?
- Does the README section clearly separate "detect-input declaration" from "execution order"?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done` and add
history notes as you go (`spec-kitty agent tasks add-history WP02 --note "..."`).
