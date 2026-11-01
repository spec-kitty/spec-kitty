---
work_package_id: WP02
title: 'Reporting surface: acceptance scenario and changelog'
dependencies:
- WP01
requirement_refs:
- FR-005
- SC-001
- SC-002
- SC-005
planning_base_branch: issue-6277-charter-synthesize-json-posix-paths
merge_target_branch: issue-6277-charter-synthesize-json-posix-paths
branch_strategy: Planning artifacts for this mission were generated on issue-6277-charter-synthesize-json-posix-paths. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6277-charter-synthesize-json-posix-paths unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
phase: Phase 2 - Reporting surface
history:
- at: '2026-11-01T15:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/scenarios/charter/charter.feature
create_intent: []
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- tests/scenarios/charter/charter.feature
- tests/scenarios/absorption-ledger.json
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Reporting surface: acceptance scenario and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

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
Use language identifiers in code blocks: ````python`,````bash

---

## Objectives & Success Criteria

The cross-platform contract must be asserted end to end, not only in a unit test, and the
user-facing behaviour change must be recorded.

Done when:

- `tests/scenarios/charter/charter.feature` asserts the full forward-slash paths
  `.kittify/charter-packs/PROVENANCE.md` and `.kittify/charter/synthesis-manifest.yaml`
  again, in both the real-run and dry-run scenarios (FR-005, SC-001, SC-002).
- The absorption-ledger note no longer says the assertion is relaxed pending a decision.
- `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry for #6277 (SC-005).

## Context & Constraints

- Spec: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/spec.md`
- Plan: `kitty-specs/charter-synthesize-json-posix-paths-01M6BTVM/plan.md` (IC-03, IC-04)
- Background: #6266 (`git show 45691a037f`) relaxed the scenario to file-name matching and
  wrote the relaxation reason into `tests/scenarios/absorption-ledger.json`. That reason no
  longer holds once WP01 lands; leaving it would be a stale explanation of a live gate.
- Changelog rules: entry under `[Unreleased]` in `docs/changelog/CHANGELOG.md` (the root
  `CHANGELOG.md` is a symlink to it); bold impact-first lead with `(#6277)`; before/after;
  under 1,200 characters.

## Branch Strategy

- **Strategy**: feature-branch (`issue-6277-charter-synthesize-json-posix-paths`)
- **Planning base branch**: `issue-6277-charter-synthesize-json-posix-paths`
- **Merge target branch**: `issue-6277-charter-synthesize-json-posix-paths`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T006 – Restore the acceptance scenario's full-path assertions

- **Purpose**: guard the cross-platform contract at the CLI acceptance level (FR-005).
- **Steps**:
  - In `tests/scenarios/charter/charter.feature`, replace the two file-name-only
    assertions in each of the fresh-seed and dry-run scenarios with the full
    `.kittify/...` paths (the exact strings #6266 removed).
  - Replace the header comment that explains the file-name relaxation
    ("Reported paths are checked by file name only: on Windows the JSON envelope spells
    them with backslashes (#6277)…") with the contract statement: reported
    repository-relative paths are POSIX on every platform (#6277).
  - In `tests/scenarios/absorption-ledger.json`, drop the trailing sentence about the
    by-name relaxation from the two notes that carry it (the entries absorbing
    `tests/integration/test_charter_synthesize_fresh.py`), keeping the rest of each note
    intact.
- **Files**: `tests/scenarios/charter/charter.feature`,
  `tests/scenarios/absorption-ledger.json`
- **Parallel?**: yes (disjoint from T007).
- **Notes**: keep the scenario's other assertions unchanged; this is not a scenario
  rewrite. JSON must stay valid (2-space indent, trailing newline) so the ledger diff is
  one line per note.

### Subtask T007 – Changelog entry

- **Purpose**: record the behaviour change for consumers of the JSON envelope.
- **Steps**: add a bullet under `[Unreleased]` in `docs/changelog/CHANGELOG.md` with a bold
  impact-first lead: reported repository-relative paths in `charter synthesize --json` are
  POSIX on every OS. State before (`files_written`/`files_planned`/`planned_deletes`/
  `written_artifacts[].path` used `\` on Windows) and after (always `/`, matching the
  committed `synthesis-manifest.yaml`), and end with `(#6277)`.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: yes.
- **Notes**: place it under the existing `[Unreleased]` heading style used by neighbouring
  entries; do not create a new release section.

## Test Strategy

- Run the charter acceptance scenarios for `tests/scenarios/charter/charter.feature` with
  the repository's scenario runner (see `tests/scenarios/` for the runner and `make`
  targets). The built CLI must reflect the working tree, not a stale global install.
- Validate the JSON fixture stays well-formed: `python -m json.tool
  tests/scenarios/absorption-ledger.json > /dev/null`.
- Do not run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Risks & Mitigations

- **Scenario runner needs a built CLI**: run it through the repo's documented target so it
  picks up the working tree; a stale install would fail for the wrong reason.
- **Ledger drift**: the ledger is machine-checked; keep the entry structure and only edit
  the note text.

## Review Guidance

- Confirm the restored assertions are exactly the pre-#6266 strings.
- Confirm no other scenario step or ledger field changed.
- Confirm the changelog entry is under `[Unreleased]`, impact-first, and under 1,200
  characters.
- Confirm the scenario passes against the WP01 fix (not against a skipped/xfailed step).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
