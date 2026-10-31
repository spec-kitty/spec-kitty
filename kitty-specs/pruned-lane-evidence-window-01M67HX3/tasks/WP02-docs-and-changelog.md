---
work_package_id: WP02
title: The operator-facing record explains the pruned-branch path
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- NFR-003
- SC-004
planning_base_branch: issue-6780-pruned-lane-evidence-window
merge_target_branch: issue-6780-pruned-lane-evidence-window
branch_strategy: Planning artifacts for this mission were generated on issue-6780-pruned-lane-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6780-pruned-lane-evidence-window unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pruned-lane-evidence-window-01M67HX3
base_commit: 72f513446781d5eaa742358703a0c7ca93ce74ec
created_at: '2026-10-31T01:01:54.752947+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Operator-facing record
history:
- at: '2026-10-30T00:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/CHANGELOG.md
- docs/development/how-to/pr-landing.md
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/how-to/pr-landing.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The operator-facing record explains the pruned-branch path

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

1. `docs/changelog/CHANGELOG.md` carries an `[Unreleased]` entry for #6780: bold
   impact-first lead, then before/after, under 1,200 characters.
2. `docs/development/how-to/pr-landing.md` carries a gotcha for a PR-landed lanes Mission
   whose lane branches were pruned: what `accept --mode pr --merge-commit` does with the
   evidence window, what a refused accept is telling the operator, and the two remedies.
3. The touched docs are terminology-clean and the docs freshness check reports
   `errors=0`.

## Context & Constraints

- The shipped refusal/recovery strings come from WP01 in
  `src/specify_cli/consolidation/wp_evidence.py`; quote them verbatim **after** WP01 has
  landed, so a grep of code and docs agrees.
- Changelog conventions: `docs/changelog/CHANGELOG.md` (`CHANGELOG.md` at the repo root is
  a symlink to it); one entry under `[Unreleased]`; `(#6780)` reference in the lead;
  impact-first, before/after, under 1,200 characters.
- No new CLI option is added by this mission, so no generated CLI reference
  regeneration is expected; still run the freshness check and report its result.
- Terminology: "Mission", "work package", "lane branch", "landing commit" are canonical;
  do not use "feature" for a Mission, and do not name the retired `merge` command.
- The gotcha must not claim the gate now inspects anything new: the pass criterion is the
  same owned-file change, only the window's tip stands in for a pruned ref.

## Branch Strategy

- **Strategy**: Feature-branch mission with lanes (`topology: lanes`); all work merges
  into the mission's target branch and a PR carries it to `main`.
- **Planning base branch**: `issue-6780-pruned-lane-evidence-window`
- **Merge target branch**: `issue-6780-pruned-lane-evidence-window`

> Populated by `specify_cli` finalize-tasks. Do not change by hand.

## Subtasks & Detailed Guidance

### Subtask T008 – Changelog `[Unreleased]` entry

- **Purpose**: a reader of the release notes learns that a PR-landed Mission no longer
  refuses every work package once its lane branches are pruned.
- **Steps**:
  1. Read the top of `docs/changelog/CHANGELOG.md` and match the current `[Unreleased]`
     shape.
  2. Add one bullet: bold impact-first lead with `(#6780)`, then **Before:** after a PR
     landing, a pruned lane branch made `accept --mode pr` refuse every done work package
     with `IMPLEMENTATION_UNREADABLE`, which no attestation could lift; **After:** the
     evidence window's tip is the verified landing commit when the lane branch ref is
     gone, the gate's owned-file criterion is unchanged (a hollow work package still
     refuses `IMPLEMENTATION_MISSING`), and the refusal without a verified landing commit
     names the missing branch and both remedies.
  3. Keep it under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes with T009.

### Subtask T009 – `pr-landing.md` gotcha

- **Purpose**: the maintainer runbook is where a PR-landed Mission is closed out; the
  pruned-branch case belongs in its Gotchas section.
- **Steps**:
  1. Read `docs/development/how-to/pr-landing.md` § Gotchas and the surrounding style.
  2. Add one gotcha: a lanes Mission landed through a PR never runs `consolidate`, so its
     lane branches are the only place the evidence window lived; after pruning them, run
     the acceptance with `--mode pr --merge-commit <sha>` so the window's tip is the
     verified landing commit. Name what a refusal means in each case (missing
     implementation vs unreadable window) and the two remedies.
  3. Quote the recovery line from `wp_evidence.py` verbatim so the doc and the CLI agree.
- **Files**: `docs/development/how-to/pr-landing.md`.
- **Parallel?**: Yes with T008.

### Subtask T010 – Docs checks

- **Purpose**: prove the docs surface is consistent.
- **Steps**: from the repo root run
  - `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`)
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  Record the results in the WP history.
- **Files**: none.
- **Notes**: a failure caused by a concurrently regenerated shared cache is re-run once
  and reported, never worked around.

## Test Strategy

- Documentation-only package: the two commands in T010 plus a manual check that the
  quoted strings match the shipped ones exactly.

## Risks & Mitigations

- **Overclaiming** ("the gate now proves the PR landed the files") → quote the criterion
  and keep the limitation explicit.
- **Changelog drift** (wrong placement, missing issue ref) → follow the existing
  `[Unreleased]` entries' shape.

## Review Guidance

- Confirm the changelog entry is under `[Unreleased]`, carries `(#6780)`, and is under
  1,200 characters.
- Confirm the quoted refusal/recovery wording matches the code verbatim.
- Confirm neither doc claims a behavioural change beyond the evidence window's tip.

## Progress & Status

Progress, history, and status live in the status event log (`status.events.jsonl`).

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
