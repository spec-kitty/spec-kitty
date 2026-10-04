---
work_package_id: WP03
title: Rendering gate, decision record and changelog
dependencies:
- WP02
requirement_refs:
- FR-012
- FR-015
- NFR-005
- SC-005
planning_base_branch: issue-4925-upgrade-outcome-single-rendering
merge_target_branch: issue-4925-upgrade-outcome-single-rendering
branch_strategy: Planning artifacts for this mission were generated on issue-4925-upgrade-outcome-single-rendering. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4925-upgrade-outcome-single-rendering unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-outcome-single-rendering-01M444Q6
base_commit: df0040bf2e253e5a181774afda5fc19040b338d4
created_at: '2026-10-04T20:30:01.593434+00:00'
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 3 - Close the class
history:
- at: '2026-10-04T19:11:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_upgrade_outcome_single_rendering.py
- docs/adr/4.x/2026-10-04-2-upgrade-reports-one-outcome.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/architectural/test_upgrade_outcome_single_rendering.py
- docs/adr/4.x/2026-10-04-2-upgrade-reports-one-outcome.md
- docs/adr/4.x/index.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Rendering gate, decision record and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Keep the defect class closed and record the contract (spec FR-012, FR-015, NFR-005).

Done when:

- An architectural gate fails if upgrade presentation code prints its own closing line, assembles its own error list, or the exit code is derived from anything but the outcome kind. Empty allowlist, self-mutation test, non-vacuity floor.
- An ADR under `docs/adr/4.x/` records the upgrade outcome and exit-code contract, including the open operator decision.
- The changelog has an `[Unreleased]` entry and no longer lists the defect as a known limitation.

## Context & Constraints

- Read first: `.kittify/charter/charter.md` (Standing Orders 2, 4, 5), then this mission's `spec.md`, `plan.md`, `data-model.md` and `contracts/upgrade-outcome-contract.md` under `kitty-specs/upgrade-outcome-single-rendering-01M444Q6/`.
- Load doctrine with `spec-kitty charter context --action implement`.
- **Read-only**: `src/specify_cli/upgrade/runner.py` and `src/specify_cli/upgrade/assessment.py` (a sibling mission and an open pull request own them). `worktree_failures` stays `list[str]`.
- Do not change the planner / compatibility exit paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, agent-check flags).
- Do not edit the mission's tracer files under `traces/`; report friction and decisions in your hand-back and the orchestrator records them.
- Use CodeGraph first: `codegraph explore "<symbols>"`.
- In a lane worktree there is no `.venv`: run `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest ...`, and drive the CLI in-process (`CliRunner`), never the global `spec-kitty` binary. Never a bare `uv run`.
- Tests: run only the files named in this prompt. No whole directories, no `make test-fast`, no full `tests/architectural/`.
- New code passes `ruff check`, `ruff format --check --force-exclude <files>` and `mypy --strict` with no new suppressions. Complexity ≤ 15 per function. Repeated literals (3+) become constants.
- No machine-local paths or personal data in code, tests or commit messages.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; use the workspace path that `spec-kitty implement` returns.

- Depends on WP02. Read `contracts/upgrade-outcome-contract.md` and the final shape of `src/specify_cli/upgrade/outcome.py` before writing the gate.
- Read the doctrine for gates: `spec-kitty charter context --include tactic:architectural-gate-non-vacuity`.
- Prose follows the charter's writing rules: name the reader (a maintainer for the ADR; an operator for the changelog), plain language, one Divio type per document, an `updated:` date.

## Subtasks & Detailed Guidance

### Subtask T012 – The gate

- **Steps**: create `tests/architectural/test_upgrade_outcome_single_rendering.py`. Parse `src/specify_cli/cli/commands/upgrade.py` and `src/specify_cli/upgrade/outcome.py` with `ast`. Look at a neighbouring single-authority gate for house style (for example `tests/consolidation/test_single_rollback_authority.py` or `tests/architectural/test_charter_kind_vocabulary_single_authority.py`). Assert:
  1. **Closing lines live in the outcome only.** Import the closing-line constants from `specify_cli.upgrade.outcome` and assert that no string constant (including f-string parts) in `cli/commands/upgrade.py` contains any of their distinguishing fragments (`already up to date`, `Upgrade complete`, `Upgrade failed`, `Dry run complete`, `unresolved tool-surface drift`). Derive the fragments from the constants where possible so a reworded line cannot slip past.
  2. **No error-list assembly outside the outcome.** In `cli/commands/upgrade.py`, no attribute read of `.activation_errors`, `.worktree_failures`, `.drifted_paths` or `.surface_repair_messages` appears inside a function whose name starts with `_display`, `_render` or `_build_` (the presentation functions), and no such function has a parameter named `errors` or `effective_success`.
  3. **One exit-code site.** `derive_exit_code` is called from exactly one place under `src/`, and `typer.Exit(outcome.exit_code)` is the only `typer.Exit` raised after the `finalize_upgrade` call inside `upgrade()`.
  4. **Exit code is a function of kind.** The body of `derive_exit_code` reads `self.kind` and no other outcome field.
- **Non-vacuity**: a floor assertion that the checker visited at least the real tail renderer and both JSON builders (assert their names are among the visited functions), and that it found the closing-line constants in `outcome.py`.
- **Self-mutation**: feed the same checker functions synthetic source strings, one per rule, each containing the violation, and assert each is reported. The checker must therefore be written as pure functions over source text / AST, not inline in the test.
- **No allowlist.** If a rule cannot start empty, stop and report rather than adding an exemption.
- **Files**: `tests/architectural/test_upgrade_outcome_single_rendering.py` (new).

### Subtask T013 – ADR

- **Steps**: write `docs/adr/4.x/2026-10-04-2-upgrade-reports-one-outcome.md`, using `docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md` as the format reference (frontmatter `title`, `description`, `status: Accepted`, `date`, `updated`). Content: context (the exit code had one authority since the earlier exit-honesty fix; the messages and closing line did not, which produced a success line on a failing run); decision (the outcome owns kind, reasons, messages, status word and closing line; the four kinds and their precedence; the contract table; presentation may not build its own); the exit-code rule for unresolved drift, stated as the current contract with the open operator decision and its known cost (generated files misclassified as drift fail unattended upgrades until the classification issue is fixed); consequences (the kind is in JSON; drift on the migrations path now closes with the drift line instead of `Upgrade failed.`; the ordering defect that makes a first run fail on old projects is reported honestly but not fixed); the gate that enforces it. Deciders: the repository owner; mark the drift exit-code rule "pending operator confirmation".
- Add the ADR to `docs/adr/4.x/index.md` in the house order.
- **Files**: the ADR, `docs/adr/4.x/index.md`.

### Subtask T014 – Changelog

- **Steps**: in `docs/changelog/CHANGELOG.md` under `[Unreleased]`, add one entry in the house style (bold impact-first lead with the issue reference, then **Before:** / **After:**). Lead: an upgrade that exits non-zero now always says why, and never prints a success line. Cover: the no-migrations run with drift; the `outcome` and `failure_reasons` JSON keys; the new closing line for drift on the migrations path; the `drift in 0 file(s)` misreport replaced by the real repair-failure reason (reference the second issue as partially addressed; it stays open for its ordering defect); the dry-run help-text correction. Then edit the existing entry for the Windows phantom-repairs fix (search for `Known limitation: \`upgrade --yes\` exiting 1`) to remove the "known limitation" sentence, since this entry supersedes it.
- **Files**: `docs/changelog/CHANGELOG.md`.

### Subtask T015 – Docs index and guards

- **Steps**: an ADR page was added, so regenerate the docs retrieval index (`.venv/bin/python scripts/docs/docs_index.py --write`) and run `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors must be 0) and `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py`. Commit any regenerated index file with the ADR commit; if the index file is outside this WP's `owned_files`, note it as an out-of-map generated edit.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_upgrade_outcome_single_rendering.py tests/architectural/test_no_legacy_terminology.py
ruff check tests/architectural/test_upgrade_outcome_single_rendering.py
ruff format --check --force-exclude tests/architectural/test_upgrade_outcome_single_rendering.py
mypy --strict tests/architectural/test_upgrade_outcome_single_rendering.py
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
```

Do not run the whole `tests/architectural/` directory.

## Risks & Mitigations

- The gate may find a real residual in WP02's output (for example a closing-line fragment left in a docstring or message). Fix the source if it is a one-line change inside `cli/commands/upgrade.py` and say so; otherwise report it.
- The changelog is a hot file; keep the edit to the two places named.

## Review Guidance

- Mutate by hand: add `console.print("Project is already up to date!")` to a renderer and confirm rule 1 fails; pass `errors=` to a renderer and confirm rule 2 fails.
- The gate has no allowlist and its floor assertions name real functions.
- The ADR states the drift exit-code rule as pending operator confirmation, not as settled.
- The changelog entry does not claim the second issue is fixed.

## Amendments from the post-tasks review (binding; these override the text above where they differ)

1. **Rule 1 also covers the status word and the call.** Assert that each JSON builder's `"status"` value is the attribute `outcome.status` (not a conditional expression or literal), and that the tail renderer calls `closing_line()`.
2. **Rule 2 is wider.** Presentation functions (`_display*`, `_render*`, `_build_*`) must not read `.result.errors`, `.result.warnings`, `.activation_errors`, `.worktree_failures`, `.drifted_paths` or `.surface_repair_messages`; they call `outcome.errors()` / `outcome.warnings()`. `upgrade()` itself is allowed to append to `result.warnings` before rendering; the rule is scoped to presentation functions and says so in its docstring.
3. **Rule 4 is about reads.** `derive_exit_code` stores `self.exit_code`; assert that the only attribute it *loads* from `self` is `kind` (AST `Load` context).
4. **Rule 1 scans docstrings too** (they are string constants). WP02 was told to reword them; if one remains, fix it in `cli/commands/upgrade.py` and note the out-of-map edit.

## Activity Log

> Entries are appended in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-04T19:11:03Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
