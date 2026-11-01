---
work_package_id: WP02
title: The operator docs and the changelog
dependencies:
- WP01
requirement_refs:
- FR-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6234-upgrade-dry-run-would-apply-heading
merge_target_branch: issue-6234-upgrade-dry-run-would-apply-heading
branch_strategy: Planning artifacts for this mission were generated on issue-6234-upgrade-dry-run-would-apply-heading. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6234-upgrade-dry-run-would-apply-heading unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
phase: Phase 2 - Operator documentation
history:
- at: '2026-11-01T15:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/6234.fixed.md
execution_mode: planning_artifact
owned_files:
- docs/guides/how-to/installation/upgrade-project.md
- docs/changelog/unreleased/6234.fixed.md
role: implementer
tags: []
task_type: docs
tracker_refs:
- '#6234'
---

# Work Package Prompt: WP02 – The operator docs and the changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

WP01 changed what an operator reads in a dry run. This WP tells them what it is called, and
records the change in the unreleased changelog.

Done when:

- `docs/guides/how-to/installation/upgrade-project.md` says, next to the existing `--dry-run`
  invocation, that the preview's migration list is headed `Migrations that would be applied:`
  with `→` markers, and that a real run keeps `Migrations applied:`.
- `docs/changelog/unreleased/6234.fixed.md` exists with an impact-first bold lead, `(#6234)`,
  a before/after, under 1,200 characters, US spelling.
- `uv run --frozen python -m scripts.docs.check_changelog_style` and
  `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` pass, and
  `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` reports errors=0.

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/6234>
- Spec / plan / research / quickstart:
  `kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/{spec,plan,research,quickstart}.md`
- The how-to page's `--dry-run` passage is at
  `docs/guides/how-to/installation/upgrade-project.md` ("The upgrade flow" section, ~line 40).
  The page carries **no** sample output block, so do not invent one: one sentence where the
  invocation already lives is the whole docs change.
- The changelog convention is a fragment per PR under `docs/changelog/unreleased/`, named
  `<id>.<section>.md` (see `docs/changelog/unreleased/README.md`). Use `6234.fixed.md`; rename
  to the PR number at hand-off if one is assigned before the PR opens. Do **not** edit
  `docs/changelog/CHANGELOG.md`.
- Style: bold impact-first lead, then **Before:** / **After:**, under 1,200 characters, US
  spelling. Neighbouring fragments (`docs/changelog/unreleased/6885.fixed.md`) are the model.

Constraints:

- **C-002**: no JSON, flag or contract documentation changes — nothing about this fix changes a
  machine surface.
- No machine-local paths, no personal data, no invented issue numbers.
- Do not touch `docs/api/upgrade-lifecycle.md`'s tables: they describe selection and the
  `--plan-json` contract, neither of which changed.

## Branch Strategy

- **Strategy**: single checkout; planning artifacts were generated on
  `issue-6234-upgrade-dry-run-would-apply-heading`, and completed changes merge into the same
  branch, which is the PR head.
- **Planning base branch**: `issue-6234-upgrade-dry-run-would-apply-heading`
- **Merge target branch**: `issue-6234-upgrade-dry-run-would-apply-heading`

## Subtasks & Detailed Guidance

### Subtask T007 – The how-to sentence

- **Purpose**: An operator reading the upgrade guide should know what the preview's list means
  before they meet it.
- **Steps**: After the `spec-kitty upgrade --dry-run` line in "The upgrade flow", add one
  sentence: the preview's migration list is headed `Migrations that would be applied:` and marks
  each entry with `→`, while a real run heads the same list `Migrations applied:` with `✓`. Keep
  it one sentence plus at most a short clause; do not restructure the section.
- **Files**: `docs/guides/how-to/installation/upgrade-project.md`

### Subtask T008 – The changelog fragment

- **Steps**: Create `docs/changelog/unreleased/6234.fixed.md` with one entry in the shape of
  `docs/changelog/unreleased/6885.fixed.md`:

  ```markdown
  - **`spec-kitty upgrade --dry-run` names its migration list for what it is** (#6234). **Before:** ...
  ```

  Say what the operator saw before (the `DRY RUN - No changes were made` panel followed by a
  green `Migrations applied:` list with `✓`, and a closing "no changes applied"), and what they
  see now (`Migrations that would be applied:` with `→`; a real run unchanged). Under 1,200
  characters.
- **Files**: `docs/changelog/unreleased/6234.fixed.md`
- **Notes**: A fragment, never an edit to `docs/changelog/CHANGELOG.md`.

### Subtask T009 – Verification

- **Steps**:
  - `uv run --frozen python -m scripts.docs.check_changelog_style`
  - `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`
  - `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (expect errors=0)
  - `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`
- **Notes**: The docs freshness checker reads a shared global asset cache on this host
  (20 agents share it); if it reports a failure that is not attributable to this diff, re-run
  once from a clean shell and record the observed message rather than "fixing" it by
  regenerating unrelated pages.

## Test Strategy

Documentation is verified by the repository's own lint scripts (changelog style, spelling, docs
freshness) rather than by prose assertions. The behavioural proof lives in WP01.

## Risks & Mitigations

- **Editing `CHANGELOG.md` instead of adding a fragment** → the release tooling assembles
  fragments; the style check will not catch this, so the reviewer does.
- **Inventing a sample-output block** → the page has none; adding one would pin text this
  mission does not own.
- **A too-long changelog entry** → the style check reports the character budget; keep the
  before/after to one clause each.

## Review Guidance

- Does the sentence describe the shipped wording exactly (both headings, both markers)?
- Is the fragment impact-first, `(#6234)`-referenced, under 1,200 characters, US spelling?
- Was `docs/changelog/CHANGELOG.md` left alone?
- Does the docs freshness check report errors=0?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done` and add
history notes as you go (`spec-kitty agent tasks add-history WP02 --note "..."`).
