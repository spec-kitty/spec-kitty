---
work_package_id: WP02
title: 'Operator-facing record: changelog and the cutover how-to'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-005
- C-004
planning_base_branch: issue-6689-backfill-claim-slots
merge_target_branch: issue-6689-backfill-claim-slots
branch_strategy: Planning artifacts for this mission were generated on issue-6689-backfill-claim-slots. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6689-backfill-claim-slots unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Documentation and closeout
history:
- at: '2026-10-30T23:25:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: comms-cleo
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-4-6
owned_files:
- docs/changelog/CHANGELOG.md
- docs/development/how-to/cutover-guard.md
role: communicator
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Operator-facing record: changelog and the cutover how-to

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `comms-cleo`
- **Role**: `communicator`
- **Agent/tool**: `claude`

Run `spec-kitty agent profile show comms-cleo` and
`spec-kitty charter context --action implement --include agent-profile:comms-cleo` first.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

An operator who hits the #6689 block can find out (a) that it is fixed, (b) what changed, and
(c) that a re-run converges without hand-editing anything.

- A `[Unreleased]` changelog entry exists with the `(#6689)` reference, a bold impact-first
  lead, before/after, under 1,200 characters.
- The cutover-guard how-to's recovery table names the slug-identified Mission shape and the
  `migrate backfill-runtime-state --mission <slug>` route.
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
  `tests/architectural/test_no_legacy_terminology.py` passes.

## Context & Constraints

- WP01 lands the behaviour; document the behaviour that actually landed, not the plan.
- `docs/changelog/CHANGELOG.md` is the real file (root `CHANGELOG.md` is a symlink to it).
  Keep the existing entry style in `[Unreleased]`.
- Terminology canon: "Mission", "seed carrier row", "runtime-state cutover". Never
  `feature*` for the Mission object.
- Only touch the docs surface this diff needs. This host is shared with other agents: do
  **not** rebuild the whole `docs/api/cli-commands.md` reference (the installed CLI's global
  asset cache is not safe to race). Verify with the freshness gate instead of trusting a
  full rebuild.
- Do not touch `src/`, never mind "fixing" a doc that disagrees with the code — file the
  drift instead and name it in your hand-off.

## Branch Strategy

- **Strategy**: Current branch at workflow start: issue-6689-backfill-claim-slots. Planning/base branch for this mission: issue-6689-backfill-claim-slots. Completed changes must merge into issue-6689-backfill-claim-slots.
- **Planning base branch**: `issue-6689-backfill-claim-slots`
- **Merge target branch**: `issue-6689-backfill-claim-slots`

## Subtasks & Detailed Guidance

### T008 – Changelog entry for #6689

- **Purpose**: The user-facing record of the fix.
- **Steps**:
  1. Read the top of `docs/changelog/CHANGELOG.md` and match the `[Unreleased]` entry style
     exactly (heading level, bullet shape, blank lines).
  2. Write one entry: a **bold impact-first lead** ending in `(#6689)`, then what changed
     before/after, e.g. lead with "`upgrade --project` no longer stalls on a legacy Mission
     whose `meta.json` carries a slug-valued `mission_id`", then the before (cutover fails
     closed forever with `claim mismatch (deterministic seed payload diverged)`) and the
     after (the seed row carries the declared identity, so verify agrees with the reader and
     the re-run converges).
  3. Keep it under 1,200 characters, no personal data, no machine-local paths.
- **Files**: `docs/changelog/CHANGELOG.md`
- **Notes**: One entry, not one per WP. Do not renumber or reorder existing entries.

### T009 – Cutover how-to: name the shape in the recovery table

- **Purpose**: Where an operator lands when the cutover refuses.
- **Steps**:
  1. Read `docs/development/how-to/cutover-guard.md`, especially the per-symptom recovery
     table (~line 101) and the "Not a `--fix`, informational only" framing.
  2. Add or amend the row that covers "accepted or merged, no stamp; or legacy WP frontmatter"
     so it states that a Mission whose `meta.json` has a slug-valued (or absent) `mission_id`
     now converges on `spec-kitty migrate backfill-runtime-state --mission <slug>`, and that a
     re-run is a no-op once converged.
  3. If the page has an `updated:` frontmatter field, bump it to `2026-10-30`.
- **Files**: `docs/development/how-to/cutover-guard.md`
- **Notes**: Keep the operator-facing language short and imperative, like its neighbours.
  Do not document the internal `_claim_carrier` seam here; that belongs in the code docstring.

### T010 – Docs gates

- **Steps**:
  1. `uv run python -m scripts.docs.check_docs_freshness --ci` → expect errors=0.
  2. `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  3. `uv run pytest tests/cross_cutting/test_docs*.py -q` if such a file exists for the pages
     you touched; otherwise note in the PR body which docs gate you ran.
- **Notes**: If a freshness error is pre-existing on `origin/main`, reproduce it there and
  name it in `## Deferred`; do not regenerate unrelated surfaces to silence it.

## Test Strategy

Docs-only WP: the gates in T010 are the test. Record their exact output in the PR body.

## Risks & Mitigations

- Over-long changelog entry → keep the before/after to one sentence each.
- Docs-freshness churn on a shared host → regenerate nothing; verify only.
- Terminology drift (`feature` for Mission) → run the architectural terminology test.

## Review Guidance

- Changelog entry: `[Unreleased]`, `(#6689)`, bold lead, under 1,200 characters, matches
  neighbours.
- How-to: the row is actionable (names the command) and does not promise a `--fix` that does
  not exist.
- No `src/` change, no unrelated docs regeneration, no machine-local paths.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
