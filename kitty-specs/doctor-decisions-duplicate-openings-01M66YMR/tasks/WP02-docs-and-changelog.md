---
work_package_id: WP02
title: Document the finding and record the changelog entry
dependencies:
- WP01
requirement_refs:
- FR-002
- C-002
planning_base_branch: issue-6764-doctor-decisions-duplicate-openings
merge_target_branch: issue-6764-doctor-decisions-duplicate-openings
branch_strategy: Planning artifacts for this mission were generated on issue-6764-doctor-decisions-duplicate-openings. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6764-doctor-decisions-duplicate-openings unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T17:46:26Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Document the finding and record the changelog entry

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `reviewer-renata`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match
for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

An operator reading the CLI reference or the changelog learns that `doctor decisions` now
reports tolerated duplicate openings, that the report is informational (exit code and
`clean` unchanged), and what they should do about it.

- `docs/changelog/CHANGELOG.md` has one `[Unreleased]` entry with a bold impact-first
  lead, the `(#6764)` reference, before/after, and "what to do", under 1,200 characters.
- Docs freshness gate passes, and the legacy-terminology test passes.

The generated CLI reference and the `doctor decisions` help body are documented in WP03
(they live in `src/`, which a planning-artifact package may not own).

## Context & Constraints

- The behaviour being documented is delivered by WP01 (read its prompt and the mission's
  `spec.md` for the exact wording of the finding).
- `docs/changelog/CHANGELOG.md` is the real file; the root `CHANGELOG.md` is a symlink —
  never edit the root path.
- No ADR and no new doc page: this extends an existing page, so no docs-index regeneration
  is expected.
- Keep user-facing prose impact-first and operator-voiced; do not paste internal symbol
  names into the changelog lead.

## Branch Strategy

- **Strategy**: coord topology, one lane; the mission's planning branch is the merge
  target (`issue-6764-doctor-decisions-duplicate-openings`).
- **Planning base branch**: `issue-6764-doctor-decisions-duplicate-openings`
- **Merge target branch**: `issue-6764-doctor-decisions-duplicate-openings`

Claim and run this package with:

```bash
spec-kitty agent action implement WP02 --agent reviewer-renata --mission doctor-decisions-duplicate-openings-01M66YMR
```

## Subtasks & Detailed Guidance

### Subtask T008 – Changelog entry

- **Purpose**: A user-facing behaviour change needs an `[Unreleased]` entry.
- **Steps**:
  1. Open `docs/changelog/CHANGELOG.md` and find `## [Unreleased]` and its newest entries.
  2. Add one bullet at the top of the unreleased list, matching the style of the
     neighbouring #4848 entry:

     ```
     - **`doctor decisions` now names decisions whose log holds duplicate openings it already tolerates** (#6764). **Before:** ...
     ```

     Cover: before (silent tolerance — the command reported the mission clean with no hint
     that the log carried a second opening); after (an informational finding names the
     decision on both the text and `--json` output as `duplicate_openings_tolerated`;
     exit codes, the clean verdict and `--repair` are unchanged, and the log is never
     rewritten); what to do (nothing — the rows are the pre-#4848 write pattern and remain
     readable).
  3. Keep the whole bullet under 1,200 characters and use the `(#6764)` reference.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Parallel?**: yes.
- **Notes**: no emoji, no "we", no undated claims.

### Subtask T009 – Run the docs gates

- **Purpose**: Keep the docs-freshness and terminology gates green.
- **Steps**:
  1. `uv run python -m scripts.docs.check_docs_freshness --ci` — expect `errors=0`.
  2. `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.
  3. Record the exact commands and results in your hand-off note.
- **Files**: none (verification only)
- **Parallel?**: no — last.
- **Notes**: if the freshness check demands an index refresh, run
  `uv run python -m scripts.docs.docs_index --write` and re-check; report if that
  regenerates unrelated pages rather than silently committing them.

## Test Strategy

No behavioural tests in this package; the gates in T010 are the tests.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Documentation overstates the finding as a warning | Say "informational" and state explicitly that exit codes and `clean` do not change. |
| Changelog entry exceeds the 1,200-character budget | Count before committing; trim the "what to do" clause first. |
| Docs freshness red | Run T010 before hand-off. |

## Review Guidance

- The doc text matches the delivered behaviour exactly (no promise of a new flag, no
  promise of an exit-code change).
- The changelog lead is impact-first and names the command.
- Only the two owned files changed.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
