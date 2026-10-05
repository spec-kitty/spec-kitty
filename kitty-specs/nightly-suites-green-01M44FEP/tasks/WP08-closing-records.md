---
work_package_id: WP08
title: 'Closing records: alias decision record, ADR index, changelog, docs index'
dependencies:
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- FR-017
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T09:41:17.492475+00:00'
subtasks:
- T039
- T040
- T041
- T042
phase: Phase 4 - Closing records
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-10-05-1-bare-slug-coordination-directory-alias.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- docs/adr/4.x/2026-10-05-1-bare-slug-coordination-directory-alias.md
- docs/adr/4.x/index.md
- docs/changelog/CHANGELOG.md
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
role: implementer
task_type: implement
---

# Work Package Prompt: WP08 – Closing records: alias decision record, ADR index, changelog, docs index

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then read `.kittify/charter/charter.md` (sections "Quality & Tech-Debt Standing Orders" and "ATDD-First Discipline") and run `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission nightly-suites-green-01M44FEP` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- The Track A alias ruling is recorded as an architecture decision: `docs/adr/4.x/2026-10-05-1-bare-slug-coordination-directory-alias.md` (FR-017).
- Both decision records of this mission (this one and WP05's `2026-10-05-2-runner-relative-performance-budgets.md`) are registered in `docs/adr/4.x/index.md` and the page inventory.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry for the three tracks, and the #5651 "Known issue" line is removed.
- The docs retrieval index is regenerated, and the docs freshness check and the terminology guard pass.

This is a documentation work package. It edits only files under `docs/`. It writes what was built, so it reads the hand-backs and the merged code of WP01 to WP07 first and records what they actually did, not what the plan expected.

## Context & Constraints

Read first: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (FR-017, C-007, C-008), `plan.md` (IC-10), `research.md` (D1 to D3), `research/code-grounding.md` (sections 3 and 9.1 to 9.4), and the three decision files under `kitty-specs/nightly-suites-green-01M44FEP/decisions/`. Then read the hand-backs of WP01 to WP04 (ask the orchestrator for them) and the merged code.

**Why this is a `code_change` work package with docs-only ownership.** A planning-lane claim on the repository root checkout waives code-lane ancestry (`src/specify_cli/lanes/implement_support.py:718-733`), so a `planning_artifact` work package would never see its dependencies' content. As a `code_change` work package it gets its own lane worktree, and `implement` merges the approved tips of its dependency lanes into that worktree (`src/specify_cli/lanes/worktree_allocator.py:1529 _merge_dependency_lane_tips`). It still edits only the five files under `docs/` it owns.

**First check, before writing.** Confirm the lane worktree holds its dependencies: `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md` (WP05), `tests/architectural/test_commit_recipe_strings.py` (WP07), `mission_dir_aliases` in `src/specify_cli/missions/_read_path_resolver.py` (WP02), `COORD_SEED_COMMIT_REFUSED` in `src/specify_cli/consolidation/_constants.py` (WP04), and the WP03 changes in `src/specify_cli/consolidation/bookkeeping_projection.py` (`git log --oneline -- <path>`). Record the result in the hand-back. If one is missing, the dependency merge did not happen as designed: report it with `git log --oneline -15` before writing anything.

**Verified facts (base `9adc68803f`).**

- ADR home and naming: `docs/adr/4.x/`, file name `YYYY-MM-DD-N-descriptive-title-with-dashes.md`. The index is `docs/adr/4.x/index.md` (table from `:44`, last row 2026-10-04). The shared template is `docs/architecture/adr-template.md`. There is no `README` under `docs/adr/`; the index page carries the conventions.
- Registration is tool-driven: from the repository root, `python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/<file>.md` updates the page-inventory lockfile `docs/development/page-inventory.yaml` and adds the row to the index table (`docs/adr/4.x/index.md:31-33`).
- Frontmatter shape to follow: `docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md` (`title`, `description`, `status`, `date`, `updated`).
- The docs retrieval index is `docs/development/docs-retrieval-index.yaml`, generated by `scripts/docs/docs_index.py --write`. WP05 changed headings in `docs/development/testing/testing-flakiness.md`, so the index changes for that page too.
- Changelog: `docs/changelog/CHANGELOG.md`, heading `## [Unreleased] - 4.0.0rc6` at `:18`; the #5651 known-issue bullet is at `:26`; the nightly-repair entry that mentions the open #5651 reproduction is at `:74`. Entry shape is checked by `scripts/docs/check_changelog_style.py`.
- `docs/changelog/CHANGELOG.md` and `docs/adr/4.x/index.md` are contended by every running mission. Make the smallest possible edits (added lines, one removed bullet) so a rebase is trivial.
- Running the documentation tools: use the repository root checkout's environment (`/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python`), never a bare `uv run`.

### Paths owned by running missions (do not edit)

Copied from `research/code-grounding.md` section 6. Paths are relative to `src/specify_cli/` unless they start with `tests/` or are a root file.

| Running mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_wp_integrity_partition_call_shape.py`, `tests/architectural/dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `lanes/compute_and_persist.py`, `lanes/frozen_membership.py`, `lanes/lane_tip.py`, `lanes/models.py`, `cli/commands/agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `lanes/auto_rebase.py`, `lanes/stale_check.py`, `lanes/worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound. Only the body of `_is_bookkeeping` may change, and only in WP03. |
| #3931 | `cli/commands/agent/tasks_move_task*.py`, `cli/commands/_git_remedies.py`, `cli/commands/agent/tasks_parsing_validation.py` |

Also off limits for every work package of this mission: `src/mission_runtime/artifacts.py`, any `.github/workflows/*.yml`, `.github/ci-module-registry.yml`, and `kitty-specs/**`.

**Rule.** An edit outside this work package's `owned_files` needs a one-line rationale in your hand-back. An edit in a path listed above is a STOP: make no such edit, and report to the orchestrator what you found and why the listed path seems to need a change.

### Commit hygiene

This work package changes documentation only, so the failing-test order of charter C-011 does not apply to it. Commit in logical slices (decision record; registration; changelog; regenerated index).

Every commit message ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No commit message or document names an AI tool or a model.

### Tracer files

Do not edit anything under `kitty-specs/`, including `kitty-specs/nightly-suites-green-01M44FEP/traces/`. Put tooling friction, approach changes and design choices in your hand-back as three short lists; the orchestrator appends them to the tracer files.

## Branch Strategy

- **Strategy**: lane worktree per computed lane (`lanes.json`); this mission's topology is `lanes`.
- **Planning base branch**: `issue-5611-5419-nightly-green`
- **Merge target branch**: `issue-5611-5419-nightly-green`
- **Dependencies**: WP03, WP04, WP05, WP06, WP07

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP08 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T039 – Track A decision record

- **Purpose**: FR-017, Track A half.
- **Steps**:
  1. Write `docs/adr/4.x/2026-10-05-1-bare-slug-coordination-directory-alias.md` from the shared template with the frontmatter shape named above. Status `Accepted`, date `2026-10-05`, deciders: Stijn Dejongh (owner), with the operator rulings of 2026-10-05.
  2. Content:
     - Context: the bare-slug coordination Mission shape, why it is genuine (`coordination/transaction.py::_canonical_coord_mission_slug`), the regression from `5b5699e500`, and the three layers of the failure.
     - Decision 1, alias authority: one exact alias set from recorded identity, where it lives (`missions/_read_path_resolver.py::mission_dir_aliases`) and why there and not in `mission_runtime` (the outbound ledger), resolved once and passed to pure classifiers.
     - Decision 2, one directory on the target: the end state and the mechanism WP03 actually built.
     - The closed-world argument: why the alias cannot let foreign content past the reconciliation gate. The set is exact; for the composed name only coordination record kinds are exempt; state the negative controls that pin this (a different `mid8`, a suffixed name, another Mission's name, `spec.md` and source under the composed name, a slug with no recorded identity).
     - The refused-seed backstop and its error code, and why the seeded files are kept (I-SEED-10).
     - Rejected alternatives: one directory name keyed on the primary directory (needs a read fallback for Missions seeded since 2 October); alias without the fold (a split status log on the target); refusing the bare-slug shape (changes a documented contract); threading the alias set through the claim object (edits outside the permitted function).
     - Residuals and follow-ups: the sibling bare-slug anchors of grounding section 3.6 including the second classifier caller in the acceptance package; any consumer WP03 left unconverted for lack of a red proof (for example `phase_bookkeeping.py:567`, if so); where `done` events land, as WP03 measured it; the relation to #5638 and #5644 (different mechanism, cross-reference only).
  3. Cite code by function name and file; a line number only where it helps and is checked against the merged code.
- **Files**: the new ADR (about 160 lines).
- **Parallel?**: No.
- **Notes**: Write for a maintainer who arrives cold. Use the spec's domain terms ("bare-slug coordination Mission", "directory alias set", "PRIMARY partition / COORD partition"); never bare "primary", never "feature" for a Mission, never "legacy mission".

### Subtask T040 – Register both records

- **Purpose**: Keep the ADR index and the page inventory truthful.
- **Steps**:
  1. From the root of your lane worktree run the registration for both files:
     ```bash
     /home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python -m scripts.docs.freshen_adr_inventory \
       docs/adr/4.x/2026-10-05-1-bare-slug-coordination-directory-alias.md \
       docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md
     ```
     If the tool takes one path per call, run it twice.
  2. Check `docs/adr/4.x/index.md` gained exactly two rows dated 2026-10-05, in order, and that `docs/development/page-inventory.yaml` gained the two entries and nothing else changed.
  3. If another mission has taken `2026-10-05-1` or `-2` in the meantime, do not renumber on your own: report to the orchestrator.
- **Files**: `docs/adr/4.x/index.md`, `docs/development/page-inventory.yaml`.
- **Parallel?**: After T039.

### Subtask T041 – Changelog

- **Purpose**: Tell operators what changed.
- **Steps**:
  1. Under `## [Unreleased] - 4.0.0rc6`, add entries in the section shape the file uses (Breaking to Internal; the style guard checks it):
     - Fixed: `spec-kitty consolidate` lands a coordination Mission whose primary directory does not end in its `mid8` onto a protected branch, with one Mission directory on the target (#5651).
     - Changed or Added: `consolidate` stops with `COORD_SEED_COMMIT_REFUSED` (exit 1) when the coordination seed commit is refused, names the kept files and retries on the next run.
     - Internal: the owned-checkout and start-up performance tests are runner-relative (#5419, #5614); a git-subprocess count pin runs per pull request; the commit-recipe gate classifies by recipe shape and moved to the architectural battery (#5708).
  2. Remove the "Known issue" bullet for #5651 at `:26`. In the nightly-repair entry at `:74`, change only the last sentence that says one red stays open, if it would now be false; keep the rest.
  3. Before and after wording: say what the operator saw before and sees now, in plain sentences.
  4. Run `scripts/docs/check_changelog_style.py` the way the repository invokes it (check its `--help`).
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes, alongside T039.
- **Notes**: Issue numbers here are references to work this mission did; the orchestrator owns the issue matrix. Do not change issue priorities or claim an issue closes (spec C-010; #5611 and #5419 close on the next green nightly).

### Subtask T042 – Regenerate the retrieval index, run the checks, hand back

- **Purpose**: Leave the docs gates green.
- **Steps**:
  1. Regenerate: `<root venv python> scripts/docs/docs_index.py --write` (or `-m scripts.docs.docs_index --write` if the script needs the package context). Confirm the diff of `docs/development/docs-retrieval-index.yaml` covers only the two ADRs, the flakiness page, the ADR index and the changelog.
  2. Run `<root venv python> scripts/docs/check_docs_freshness.py --ci` and fix what it reports within your owned files. A finding in a file you do not own is reported, not fixed.
  3. Run `<root venv python> -m pytest tests/architectural/test_no_legacy_terminology.py -n0 -p no:cacheprovider -q`.
  4. Draft, in the hand-back and not in a file, the follow-up issue list the orchestrator will file (spec C-007 and grounding section 8): the sibling bare-slug anchors, unconverted consumers, the `next` cold-start benchmark that asserts nothing, the `timing` marker with no CI job, the 500 ms cold-import budget no job runs, the standing 0.36 s import chain, the two remaining recipe allowlist entries needing an owner and exit date.
  5. Hand-back: commits, command outputs, the list of changed files, tracer notes.
- **Files**: `docs/development/docs-retrieval-index.yaml`.
- **Parallel?**: No; last.

## Test Strategy

### Validation commands

Run from the root of your lane worktree, with the repository root checkout's environment. Never a bare `uv run`.

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python

$PY scripts/docs/docs_index.py --write
$PY scripts/docs/check_docs_freshness.py --ci
$PY scripts/docs/check_changelog_style.py --help   # then run it as the repository does
$PY -m pytest tests/architectural/test_no_legacy_terminology.py -n0 -p no:cacheprovider -q
git diff --stat   # only the five owned files
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, never more than `-n 4` pytest workers. No lint or type check applies: this work package changes no Python file.

### Non-vacuity controls

- The ADR index gains exactly two rows and the page inventory exactly two entries.
- The changelog no longer contains the #5651 known-issue bullet, and contains the three new entries.
- The retrieval index diff names both new ADR pages.
- The decision record states the negative controls and names the mechanism WP03 actually built, checked against the merged code.

**Red first.** This work package is `code_change` only so that its lane receives its dependencies; it changes documentation only, so charter C-011's failing-test rule does not apply to it. Its commits still carry the co-author trailer and no AI or model identifier.

## Definition of Done

- The Track A decision record exists, follows the template, and matches the merged code.
- Both records are in `docs/adr/4.x/index.md` and the page inventory.
- The changelog has the new entries and no #5651 known-issue bullet; the style check passes.
- The retrieval index is regenerated; the docs freshness check and the terminology guard pass.
- Only the five owned files changed.
- The follow-up issue list is in the hand-back.
- Subtasks T039 to T042 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **Dependency content is not in the worktree.** The lane should carry the approved tips of WP03 to WP07; the first check verifies it. A missing dependency is reported, not worked around.
- **A merge of five dependency lanes.** The dependency merge may conflict or bring a lane that was approved late; do not resolve a conflict in a file you do not own, report it.
- **Contended files.** The changelog and the ADR index change under every mission; keep edits to added lines and one removed bullet.
- **ADR number collision.** Another mission may land a `2026-10-05-N` record first; report, do not renumber alone.
- **Writing the plan instead of the result.** The record must describe the mechanism that was built and the residuals that were found.
- **Generated-file noise.** A retrieval-index diff touching unrelated pages means the base was stale; report it rather than committing unrelated churn.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **The record restates the plan.** Check three claims against the merged code: the function name and module of the alias authority, the fold mechanism, the error code and exit code.
- **The closed-world argument is asserted, not argued.** It must name the exactness rule, the record-kind restriction and the negative controls.
- **Residuals omitted.** Compare with the WP03 hand-back: every unconverted consumer and the `done`-event finding must appear.
- **Hand-edited index rows.** The rows must match what `freshen_adr_inventory` produces; re-run it and expect no diff.
- **Changelog entry that says "fixed nightly".** It must say what an operator sees differently.
- **Terminology.** No bare "primary", no "feature" for a Mission, no "sync" as a live transport.
- **Edits outside the five owned files.**

Confirm the trailer on every commit and no AI or model identifier.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Append the new entry at the END of this section; never prepend or insert in the middle.
2. Use the format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>`.
3. The timestamp is the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`), never a future one.

The acceptance system reads the LAST entry as the current state, so order matters.

**Initial entry**:

- 2026-10-05T04:58:23Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done` to record a finished subtask.
