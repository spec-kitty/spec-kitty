---
work_package_id: WP03
title: Changelog fragment, docs and mission trail
dependencies:
- WP01
- WP02
requirement_refs:
- FR-002
- NFR-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7108-subtask-recipe-wp-scoping
merge_target_branch: issue-7108-subtask-recipe-wp-scoping
branch_strategy: Planning artifacts for this mission were generated on issue-7108-subtask-recipe-wp-scoping. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7108-subtask-recipe-wp-scoping unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 3 - Changelog, docs and mission trail
history:
- at: '2026-10-30T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/unreleased/
create_intent:
- docs/changelog/unreleased/7108-subtask-recipe-wp-scoping.fixed.md
execution_mode: planning_artifact
model: deepseek-v4.1-flash-1017
owned_files:
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: documentation
tracker_refs:
- '#7108'
---

# Work Package Prompt: WP03 – Changelog fragment, docs and mission trail

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP03 --note "..."`.

## Objectives & Success Criteria

The recipe change is user-visible (the refusal text and the generated prompt change),
so it needs a changelog fragment — a **per-PR fragment**, never an edit to
`docs/changelog/CHANGELOG.md`. The mission's issue matrix and tracers are then
closed truthfully.

## Subtasks

### T001 — The fragment

Read `docs/changelog/unreleased/README.md` first; it is authoritative. Create
`docs/changelog/unreleased/<id>.fixed.md` where `<id>` is the PR number once the PR
exists (before that, `7108-subtask-recipe-wp-scoping`). One bullet, impact-first
bold lead, `(#7108)` reference, before/after, under 1,200 characters, no heading:

```markdown
- **`move-task` and the generated implement prompt now name the work package when they tell you to mark subtasks done** (#7108). **Before:** the refusal printed `mark-status T001 --status done`, which `mark-status` then refused on any mission whose WPs reuse `T001..`, so the only way past the gate was `--force`. **After:** it prints `mark-status T001 --wp WP02 --status done --mission <slug>`, which records the completion against that work package.
```

### T002 — Style and spelling

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
```

Both must report nothing for the fragment.

### T003 — Mission tracers

Append to the mission tracers with
`spec-kitty agent tracer-append --mission subtask-recipe-wp-scoping-01M6G9TW --category <c> --entry "<text>" --actor <you>`:

- **approach**: the attribution half of #7108 was already fixed on `main`
  (`642359bbae`, #6463); the residual defect is the printed advice, not the write path.
- **design-decisions**: the byte-frozen `agent tasks --help` fixtures stay untouched;
  the `--wp` documentation already there is sufficient, and the emitters are fixed
  instead. Subtask-id namespacing (`WP02.T001`) is explicitly out of scope.
- **tooling-friction**: whatever the run actually hit — including the
  `specify`-on-`main` → `coord` topology → protected-branch refusal that forced
  re-creating the mission on the topic branch.

### T004 — Issue matrix

`spec-kitty agent issue-verdict --mission subtask-recipe-wp-scoping-01M6G9TW ...` to set
`#7108`'s verdict once the work is on the branch. The evidence reference names the
commits and the guard tests. Do not claim FR coverage the mission did not deliver.

### T005 — Docs freshness

`uv run python -m scripts.docs.check_docs_freshness --ci` — expect errors=0. This
mission changes no `--help` surface, so nothing under `docs/api/` should move. Do
**not** rebuild the whole CLI reference (shared asset cache, contended host); if a
freshness check disagrees, report it rather than regenerating everything.

## Definition of Done

- [ ] Fragment passes `check_changelog_style` and `check_spelling --pass unreleased`.
- [ ] `docs/changelog/CHANGELOG.md` is unmodified.
- [ ] Tracers appended, issue matrix verdict set.
- [ ] `check_docs_freshness --ci` errors=0.

## Risks & Mitigations

- **Fake green on docs.** If `check_docs_freshness` reports an error caused by
  another agent's concurrent cache rewrite, say so in the PR's `## Deferred`
  rather than regenerating a churning page set.
- **Overclaiming.** The fragment describes the recipe change only; it must not
  imply that subtask ids became per-WP scoped.
