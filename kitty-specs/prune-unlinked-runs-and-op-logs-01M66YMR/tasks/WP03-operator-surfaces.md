---
work_package_id: WP03
title: 'Operator-facing surfaces: help text, how-to, changelog'
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-014
- C-005
- SC-003
planning_base_branch: issue-6739-prune-unlinked-runs-and-op-logs
merge_target_branch: issue-6739-prune-unlinked-runs-and-op-logs
branch_strategy: Planning artifacts for this mission were generated on issue-6739-prune-unlinked-runs-and-op-logs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6739-prune-unlinked-runs-and-op-logs unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
- T018
phase: Phase 3 - Polish
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_event_logs_doctor.py
- docs/api/cli-commands.md
- docs/guides/how-to/monitoring/clean-up-local-event-logs.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Operator-facing surfaces

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the
status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code
blocks: ````python`, ````bash`, ````yaml`.

---

## Objectives & Success Criteria

An operator who reads the command help, the how-to page or the changelog can predict
exactly which items `doctor event-logs` will now delete and why — including the two
families the issue names — and the generated CLI reference stays fresh.

Done when:

- the `event-logs` command docstring (the help text) describes the new eligibility;
- `docs/api/cli-commands.md` is regenerated from that docstring and the freshness check
  is clean;
- the how-to page's reasons table and "what is never removed" list cover the new
  verdicts;
- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry with `(#6739)`, a bold
  impact-first lead, a before/after and under 1,200 characters;
- the docs freshness, CLI-reference and terminology checks pass.

## Context & Constraints

- Read first: `spec.md` (FR-008, FR-014), `plan.md` (IC-04), `data-model.md` (reason
  and kind vocabulary) and `contracts/doctor-event-logs.md` (the amended contract).
- The vocabulary is fixed by WP02: reasons `past retention; no Mission recorded`,
  `past retention; Op completed`, `past retention; no Op recorded`, `Op is open`;
  kind `op_log`.
- `docs/api/cli-commands.md` is **generated**. Never hand-edit its
  `spec-kitty doctor event-logs` block: change the docstring, then regenerate.
- Writing doctrine: lead with what changed for the operator, keep sentences short,
  no "Mission not found" semantics changed unless the text says so.
- Do not add a new doc page and do not add an ADR: the how-to and the existing ADR
  2026-10-13-2 amendment history already cover the retention tier.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on
  `issue-6739-prune-unlinked-runs-and-op-logs`; completed changes merge back into
  `issue-6739-prune-unlinked-runs-and-op-logs`.
- **Planning base branch**: `issue-6739-prune-unlinked-runs-and-op-logs`
- **Merge target branch**: `issue-6739-prune-unlinked-runs-and-op-logs`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T014 – Update the `event-logs` docstring

- **Purpose**: the docstring is the command's help text and the source of the
  generated reference.
- **Steps**: in `src/specify_cli/cli/commands/_event_logs_doctor.py`, update the
  `event_logs_command` docstring so it states, in the same voice as today:
  - an item is removed only when outside the newest `keep_runs` of its kind AND older
    than `max_age_days`;
  - a run's work is over when its Mission is merged or the run finished, and a run
    that names no Mission is judged on age alone;
  - a glossary log's work is over when its Mission is completed, an Op-scoped log's
    when its Op is completed, and an Op-scoped log whose Op is open is kept;
  - a recorded Mission this checkout cannot find is never removed.
  Keep the examples and the exit-code sentence; keep the `(#6610)` reference and add
  `(#6739)`.
- **Files**: `src/specify_cli/cli/commands/_event_logs_doctor.py`
- **Parallel?**: No — T015 depends on it.
- **Notes**: wrap at the width the other doctor docstrings use; Rich wraps the help,
  but the generated reference mirrors the source lines.

### Subtask T015 – Regenerate the CLI reference and check freshness

- **Purpose**: the freshness gate compares `docs/api/cli-commands.md` with the live
  Typer surface; a stale block fails CI.
- **Steps**:
  ```bash
  uv run python -m scripts.docs.build_cli_reference --write
  uv run python -m scripts.docs.check_cli_reference_freshness
  git diff --stat docs/api/cli-commands.md
  ```
  Confirm the diff touches only the `doctor event-logs` block.
- **Files**: `docs/api/cli-commands.md`
- **Parallel?**: No.
- **Notes**: if the builder writes other unrelated blocks, revert those hunks and say
  so in the WP history — this WP owns only the `event-logs` block.

### Subtask T016 – Update the how-to page

- **Purpose**: the page #6610 introduced is where an operator learns to read the
  reasons.
- **Steps**: in `docs/guides/how-to/monitoring/clean-up-local-event-logs.md`:
  - extend the reasons table with `past retention; no Mission recorded`,
    `past retention; Op completed`, `past retention; no Op recorded` and `Op is open`;
  - update the "An item is removed only when …" prose: a run is over when its Mission
    is merged or the run finished, and a run that names no Mission is judged on age; an
    Op-scoped log is over when its Op is completed; a log whose Op is open is kept;
  - update the `kind` list in the `--json` description to include `op_log`;
  - update "What is never removed" so it says an unknown **Mission** is never removed
    (today's wording conflates it with every unresolved item), and that Op records
    and the Op index stay even when an Op's log is pruned;
  - bump the front-matter `updated:` date.
- **Files**: `docs/guides/how-to/monitoring/clean-up-local-event-logs.md`
- **Parallel?**: Yes (independent of T014/T015).
- **Notes**: keep the page's structure and heading anchors (other pages link to
  `#read-the-reasons` and `#what-is-never-removed`).

### Subtask T017 – Changelog entry

- **Purpose**: this is a user-facing behaviour change; the changelog is the record.
- **Steps**: add one bullet under `[Unreleased]` → `### Fixed` in
  `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it), in the same
  style as the #6610 entry: bold impact-first lead ending in `(#6739)`, then
  **Before:**/**After:** and a short **What to do:** if anything is asked of the
  operator. Under 1,200 characters. Mention both families: run directories whose
  run-index entry is gone, and Op-scoped glossary logs.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: Yes.
- **Notes**: the entry must not claim anything this mission does not do (no new
  config key, no change to the `Mission not found` protection).

### Subtask T018 – Verify

- **Purpose**: prove the surface gates are green.
- **Steps**:
  ```bash
  uv run pytest tests/cli/commands/test_doctor_event_logs.py tests/docs/test_build_cli_reference.py -q
  uv run python -m scripts.docs.check_docs_freshness --ci
  uv run python -m scripts.docs.check_cli_reference_freshness
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  ```
- **Files**: none.
- **Parallel?**: No.
- **Notes**: if `check_docs_freshness` reports a pre-existing error unrelated to this
  diff, reproduce it on a pristine `origin/main` worktree before deciding; cite it in
  the PR's `## Deferred` section rather than skipping the check.

## Test Strategy

The command-rendering test that pins the new vocabulary is WP02's T012 — that WP owns
`tests/cli/commands/test_doctor_event_logs.py`. This WP's red-first proof is the
stale generated reference (T015 fails before T014) and the docs freshness gate; run
them, do not hand-fix their output.

## Risks & Mitigations

- **Hand-edited generated docs.** The freshness gate compares against the live app;
  any hand edit that the builder would not produce fails CI.
- **Changelog gate.** The entry must carry the issue reference, a bold lead and stay
  under the length limit; check with the docs gate.
- **Over-claiming.** Say "a run that names no Mission is judged on age", not "all
  unknown runs are removed".

## Review Guidance

- Compare the how-to reasons table and the docstring against `data-model.md`
  one-for-one; every new reason must appear in both.
- Confirm `docs/api/cli-commands.md` was regenerated (diff shape, not hand-written
  prose).
- Confirm the changelog bullet is in `[Unreleased] → Fixed`, references `(#6739)`,
  and does not describe a config change.
- Confirm the page's heading anchors are unchanged.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) —
never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission prune-unlinked-runs-and-op-logs-01M66YMR`
