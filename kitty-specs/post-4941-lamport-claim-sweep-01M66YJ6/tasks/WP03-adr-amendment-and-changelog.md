---
work_package_id: WP03
title: ADR 2026-10-01-2 factual amendment, changelog and gate re-run
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-008
- FR-009
- SC-003
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 3 - Record and release note
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/adr/4.x/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6604'
---

# Work Package Prompt: WP03 – ADR 2026-10-01-2 factual amendment, changelog and gate re-run

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: your harness

## Objective

Record the accepted current ordering in the ADR that owns the Mission Status Read API —
as a **dated factual amendment**, leaving its decisions, context and consequences intact —
add the `[Unreleased]` changelog entry, and prove every relevant gate green.

## Context & Constraints

Read first: [spec.md](../spec.md) FR-003/FR-008/FR-009, C-002;
[plan.md](../plan.md) "Exact change set" items 5 and the risks table; the target ADR in
full, especially its existing amendments (`## Amendment 2026-10-03`, `2026-10-12`,
`2026-10-29`) — follow their shape.

The amendment must record (per the 2026-10-22 operator ruling quoted in #6604):

- the status path is ordered by **wall clock** `(at, event_id)`;
- **from-lane continuity** (the WP's lane decides which transitions apply);
- the **approved-departure lift** (#4941, PR #6261, `spec-kitty-events` 10.5.1): a non-seed
  departure from `approved` sorts after the approval it followed, with the stored `at`
  untouched;
- the residual: a **non-approval** transition minted on a clock behind the event it follows
  still sorts before that event;
- the D-4/D-5/D-7 consequences that follow: the Java read service ports the same fold, not a
  "Lamport reduction", and its conformance test compares against that fold; "moves them onto
  the Lamport reducer" is superseded prose, not a re-decision;
- **Lamport-primary ordering** stays a post-GA direction (#6609) and needs its own ADR; the
  CLI cannot become Lamport-ordered without a clock on CLI rows (spec-kitty-events#72).

Constraints (C-002 — this is the hard part):

- **Do not rewrite history.** Every existing sentence of the record stays, including
  `:60` "which is the Lamport `reduce_shared_state` reduction", `:149` "moves them onto the
  Lamport reducer" and `:274` "ports the Lamport reduction". The amendment says what
  supersedes what.
- Update the frontmatter `updated:` field to `'2026-10-30'` and add a one-line pointer in
  the Status block ("**Amendment 2026-10-30 (Accepted):** …") the way the 2026-10-03 and
  2026-10-12 amendments are announced.
- Do not touch any other ADR, and do not touch `AGENTS.md`, the C4 pages, the gap table,
  `src/` or `tests/` (WP01/WP02 own those). If WP02 has already landed, reference the same
  facts; if it has not, do not edit its files to "help".
- The changelog root file is a symlink to `docs/changelog/CHANGELOG.md`; edit the target.

## Branch Strategy

Planning artifacts were generated on `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`.
Execution worktrees are allocated per computed lane from `lanes.json`; completed changes
merge back into `kitty/mission-post-4941-lamport-claim-sweep-01M66YJ6`.

## Subtasks

### T010 — The amendment

Append after the 2026-10-29 amendment:

```markdown
## Amendment 2026-10-30 (Accepted): the ordering is wall clock, not Lamport

Factual amendment, tracking #6604. The decision does not change: this record's D-3 to D-5
read path is unchanged, and no new ordering direction is adopted.
...
```

Then the bullets above, each naming its source (ADR `2026-02-09-3` Amendment 2026-10-22,
ADR `2026-10-14-1` Amendment 2026-10-22, #4941 / PR #6261, #6609). Close with one sentence
naming which paragraphs of this record are superseded in *wording* while their decisions
stand.

### T011 — Prove history preserved

`git diff docs/adr/4.x/2026-10-01-2-…md` must show **only**: the `updated:` frontmatter
line, the added Status-block pointer line, and the appended amendment. Any deletion or edit
inside the pre-existing body is a defect: revert it and rework the amendment wording instead.

### T012 — Changelog

Add one entry under `## [Unreleased]` in `docs/changelog/CHANGELOG.md`, in the established
style: bold impact-first lead ending in `(#6604)`, then **Before:** and **After:**, under
1,200 characters, no heading, no list nesting.

Content: before — the living C4 pages, the API/dashboard domain plan and `AGENTS.md` said the
CLI status path was Lamport-ordered and that two reducers disagreed; after — they state the
wall-clock `(at, event_id)` fold with the #4941 approved-departure lift, keep the narrower
non-approval clock-skew residual, and a guard test fails if the old wording returns.

### T013 — Re-run the gates

```bash
uv run pytest tests/architectural/test_status_path_ordering_claims.py -q          # all green
uv run pytest tests/docs/test_changelog_style.py tests/docs/test_unreleased_section.py tests/docs/test_sync_changelog.py -q
uv run python -m scripts.docs.docs_index --write
uv run python -m scripts.docs.freshen_adr_inventory
uv run python -m scripts.docs.check_docs_freshness --ci                            # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

Record the exact commands and results in this WP's history. If `docs_index --write` or
`freshen_adr_inventory` changes a tracked file, include it and say which; if a gate fails for
a reason outside this diff, reproduce it on pristine `origin/main` in a throwaway worktree and
report it rather than working around it.

## Test strategy

The guard is the acceptance test; the docs gates prove no index/inventory drift. No behaviour
test is needed — nothing under `src/` changes in this WP.

## Definition of Done

- [ ] The ADR has a `## Amendment 2026-10-30 (Accepted)` section recording wall clock, the
      lift, the residual, and #6609; `updated: '2026-10-30'`; a Status-block pointer.
- [ ] The ADR diff touches no pre-existing body sentence (T011 proof recorded).
- [ ] One `[Unreleased]` changelog entry with `(#6604)`, under 1,200 characters, passing the
      changelog style tests.
- [ ] The guard test is fully green.
- [ ] `check_docs_freshness --ci` reports `errors=0`; ADR inventory and docs index are
      committed if they changed.
- [ ] No file outside `owned_files` is modified.

## Risks

- **Amendment read as a decision change** → open with "Factual amendment … the decision does
  not change" and never use "we decided".
- **Silently modernising the ADR body** → T011's diff constraint.
- **Changelog gate reds** (length, missing reference, duplicate `[Unreleased]`) → run the
  three changelog tests before claiming done.
- **Index churn** → run `docs_index --write` and `freshen_adr_inventory` as instructed and
  commit their output; do not hand-edit generated files.

## Reviewer guidance

Verify the ADR body is untouched and the amendment is factual and sourced; verify the
changelog entry reads impact-first and names the issue; verify the guard is green and the
docs gates report zero errors. Reject an amendment that changes a decision, and reject a
"fix" that edits the original paragraphs instead of amending them.
